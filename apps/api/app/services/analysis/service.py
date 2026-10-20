"""Fixed-score analysis with public JobEngine publication and append-only notes."""
from __future__ import annotations

import functools
import re
import uuid
from typing import Any

import anyio
from pydantic import ValidationError

from app.contracts.b4 import (AnalysisCreateRequest, AnalysisReceipt, AnalysisRunDeleteReceipt, AnalysisRunView,
                              ClassReportRow, EvidenceRow, ItemStatView, NoteRequest, NoteView, Page, StudentReportRow)
from app.contracts.learning_analysis import (
    AnalysisReportReceipt,
    DistributionBucket,
    DistributionResponse,
    ExportArtifactRef,
    KnowledgePointRef,
    KnowledgeStatItem,
    KnowledgeStatsResponse,
    StudentKnowledgeCell,
    StudentKnowledgeResponse,
    StudentKnowledgeRow,
)
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.analysis import AnalysisRepository, dump, load
from app.repositories.teaching.practices import PracticeRepository
from app.repositories.teaching.triggers import (
    ANALYSIS_FROZEN_TRIGGERS,
    LESSON_REVISION_TRIGGERS,
    suspend_triggers,
)
from app.services.jobs.engine import JobOutcome
from app.services.submissions.service import execute_command, make_command
from .aggregate import aggregate
from .snapshot import read_facts

#: 学情报告彻底删除的受引用守卫错误码（跟随施测/练习/原卷 ``*_IN_USE`` 先例）
ANALYSIS_RUN_IN_USE = "ANALYSIS_RUN_IN_USE"

#: R6 图表聚合的学生级行标签（脱敏代称；与 AI 评价 ``build_prompt`` 同源规则）。
_STUDENT_LABEL_MARKERS = ("，", "、")

#: 分数段分布的三档（学生级该次考试得分率）：低 <60% / 中 60–85% / 高 ≥85%。
DISTRIBUTION_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("低 (<60%)", 0.0, 0.6),
    ("中 (60–85%)", 0.6, 0.85),
    ("高 (≥85%)", 0.85, float("inf")),
)

#: 报告导出的文件名清洗：Windows/通用文件系统非法字符与首尾控制空白。
_EXPORT_FILENAME_INVALID = re.compile(r'[\\/:*?"<>|\r\n\t]+')
_EXPORT_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _report_filename(report: dict) -> str:
    """报告导出文件名：``{班级}-{试卷}-学情分析报告.docx``（非法字符替换为 ``-``）。

    班级取参测班级名（名称优先；多班/缺名回落 ``多班级`` / ``未记录班级``）；
    试卷标题取报告冻结的 ``paperTitle``（缺失回落 ``未命名试卷``）。
    """
    names = sorted({
        participant.get("className")
        for participant in report.get("participants", [])
        if isinstance(participant, dict) and isinstance(participant.get("className"), str) and participant.get("className")
    })
    class_label = "、".join(names) if names else "未记录班级"
    paper_label = str(report.get("paperTitle") or "").strip() or "未命名试卷"
    raw = f"{class_label}-{paper_label}-学情分析报告.docx"
    cleaned = _EXPORT_FILENAME_INVALID.sub("-", raw).strip().strip(".")
    return cleaned or "学情分析报告.docx"


class AnalysisService:
    def __init__(self, catalog, *, job_engine, asset_store, file_assets=None, knowledge_catalog=None, owner_id="local"):
        self.catalog, self.engine, self.assets, self.owner = catalog, job_engine, asset_store, owner_id
        self.file_assets = file_assets
        self.knowledge_catalog = knowledge_catalog
        self.repo = AnalysisRepository()
        # R10-BE：报告删除级联其派生练习（连带历史），只借仓储不借服务（同事务、同 owner 语义）
        self.practices = PracticeRepository(catalog)
        self.store = job_engine.store("teaching")

    def register_job_executors(self, registry):
        registry.register(domain="teaching", kind="analysis", uses_model=False, factory=lambda _record: self.execute_job)

    def _command(self, assessment_id, payload):
        return make_command(operation=f"analysis.create:{assessment_id}", submission_id=payload.submission_id,
                            owner_id=self.owner, payload={"assessmentId": assessment_id,
                            "scoreRevisionId": payload.score_revision_id,
                            "selectedParticipantIds": sorted(payload.selected_participant_ids), "ruleCode": payload.rule_code})

    def _prior(self, command):
        # Read-only early replay precedes all fixed-source and filesystem checks. The
        # authoritative duplicate race is still resolved by execute_command's transaction.
        with self.catalog.read_connection() as conn:
            row = conn.execute("SELECT request_hash,result_json FROM command_submissions "
                               "WHERE owner_id=? AND operation=? AND submission_id=?",
                               (command.owner_id, command.operation, command.submission_id)).fetchone()
            if row is None:
                return None
            if row["request_hash"] != command.request_hash:
                raise AppError("同一提交标识已用于不同请求。", code="SUBMISSION_CONFLICT", status_code=409,
                               details={"fields": ["submissionId"]})
            return load(row["result_json"])

    async def create_run(self, assessment_id: str, payload: AnalysisCreateRequest) -> AnalysisReceipt:
        command = self._command(assessment_id, payload)
        prior = await anyio.to_thread.run_sync(self._prior, command)
        if prior is not None:
            return AnalysisReceipt.model_validate({**prior, "replayed": True})
        facts = await anyio.to_thread.run_sync(read_facts, self.catalog, assessment_id, payload, self.owner)
        await anyio.to_thread.run_sync(self._verify_assets, facts)
        input_hash = canonical_hash(facts)

        def apply(conn):
            row = conn.execute("SELECT * FROM analysis_runs WHERE owner_id=? AND input_hash=?",
                               (self.owner, input_hash)).fetchone()
            if row is not None:
                return self._receipt(row, reused=True)
            run_id = uuid.uuid4().hex
            job = self.store.create_in(conn, kind="analysis", owner_id=self.owner,
                                       frozen_input={"runId": run_id, "ownerId": self.owner,
                                                     "facts": facts, "inputHash": input_hash})
            self.repo.create_in(conn, run_id=run_id, owner_id=self.owner, input_hash=input_hash, facts=facts, job_id=job.job_id)
            return {"runId": run_id, "inputHash": input_hash, "scoreRevisionId": facts["scoreRevisionId"],
                    "paperRevisionId": facts["paperRevisionId"], "job": job.view().model_dump(by_alias=True),
                    "replayed": False, "reused": False}

        outcome = await anyio.to_thread.run_sync(functools.partial(execute_command, catalog=self.catalog,
                                                                   command=command, apply=apply))
        receipt = AnalysisReceipt.model_validate({**outcome.result, "replayed": outcome.replayed})
        if not outcome.replayed and not receipt.reused:
            self.engine.schedule("teaching", receipt.job.job_id, self.execute_job, uses_model=False)
        return receipt

    def _verify_assets(self, facts):
        # Bytes are verified outside SQL/publication locks; fixed declarations are
        # retained even for non-loss evidence. Replay never visits this path.
        declarations = {}
        for item in facts["items"]:
            for asset in item["assets"]:
                aid, sha = asset.get("assetId"), asset.get("sha256")
                if not aid or not isinstance(sha, str) or len(sha) != 64:
                    raise AppError("固定题面资产声明损坏。", code="ANALYSIS_SOURCE_CORRUPT", status_code=500)
                if aid in declarations and declarations[aid] != sha:
                    raise AppError("固定题面资产指纹冲突。", code="ANALYSIS_SOURCE_CORRUPT", status_code=500)
                declarations[aid] = sha
        if not declarations:
            return
        with self.catalog.read_connection() as conn:
            rows = {aid: conn.execute("SELECT * FROM file_assets WHERE id=? AND owner_id=?",
                                     (aid, self.owner)).fetchone() for aid in declarations}
        for aid, sha in declarations.items():
            row = rows[aid]
            if row is None or row["sha256"] != sha:
                raise AppError("固定题面受管资产不存在或指纹不符。", code="ANALYSIS_ASSET_INVALID", status_code=500)
            if self.assets.verify(row["blob_key"]) != row["byte_size"]:
                raise AppError("固定题面受管资产大小不符。", code="ANALYSIS_ASSET_INVALID", status_code=500)

    async def execute_job(self, frozen, context):
        payload = frozen.input
        try:
            facts, run_id, owner = payload["facts"], payload["runId"], payload["ownerId"]
            if canonical_hash(payload) != frozen.input_hash or canonical_hash(facts) != payload["inputHash"]:
                raise ValueError("input mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("分析任务冻结输入损坏。", code="ANALYSIS_INPUT_CORRUPT", status_code=500) from exc
        if await context.cancellation_requested():
            return JobOutcome(result={"runId": run_id})
        # Pure computation on the accepted immutable input, no active/current lookup.
        result = await anyio.to_thread.run_sync(aggregate, facts)

        def publish(conn):
            row = self.repo.require_in(conn, run_id, owner)
            if row["job_id"] != frozen.job_id or row["input_hash"] != payload["inputHash"] or load(row["input_json"]) != facts:
                raise AppError("分析任务与报告归属不符。", code="ANALYSIS_INPUT_CORRUPT", status_code=500)
            if row["report_ready"]:
                raise AppError("该分析已封存。", code="IMMUTABLE_REVISION", status_code=409)
            self.repo.publish_in(conn, run_id, facts, result)
        return JobOutcome(result={"runId": run_id, "inputHash": payload["inputHash"], "reportReady": True}, publish=publish)

    def _receipt(self, row, *, reused):
        return {"runId": row["id"], "inputHash": row["input_hash"], "scoreRevisionId": row["score_revision_id"],
                "paperRevisionId": row["paper_revision_id"], "job": self.store.get(row["job_id"]).view().model_dump(by_alias=True),
                "replayed": False, "reused": reused}

    def _class_names_in(self, conn, class_ids, owner_id):
        """按同 owner 实时读取班级展示名（“名称优先”的共享来源）。

        ``classId`` 已随事实冻结；这里只补展示名：班级行缺失/不属于该 owner 时
        返回映射缺项（调用方落 null），归档班级不过滤、照常可读。
        """
        ids = sorted({cid for cid in class_ids if isinstance(cid, str) and cid})
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT id,name FROM classes WHERE owner_id=? AND id IN ({placeholders})",
            (owner_id, *ids)).fetchall()
        return {r["id"]: r["name"] for r in rows if isinstance(r["name"], str) and r["name"]}

    def _view(self, conn, row):
        facts = load(row["input_json"])
        try:
            # 班名走“名称优先”：input_json 只冻结 classId；详情/视图读路径按同 owner
            # 实时补 classes.name（班名缺失才 null），不回写冻结事实。
            names = self._class_names_in(conn, {p["classId"] for p in facts["participants"]}, row["owner_id"])
            participants = [{**p, "className": names.get(p["classId"])} for p in facts["participants"]]
            return AnalysisRunView(runId=row["id"], assessmentId=row["assessment_id"], subjectId=row["subject_id"],
                                   scoreRevisionId=row["score_revision_id"], paperRevisionId=row["paper_revision_id"],
                                   paperTitle=facts["paperTitle"], inputHash=row["input_hash"], ruleCode=row["rule_code"],
                                   selectionSnapshot=facts["selectionSnapshot"], participants=participants,
                                   knowledgePoints=facts["knowledgePoints"], job=self.store.get(row["job_id"]).view(),
                                   reportReady=bool(row["report_ready"]), archivedAt=row["archived_at"],
                                   createdAt=row["created_at"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise AppError("分析报告快照损坏。", code="ANALYSIS_ROW_CORRUPT", status_code=500) from exc

    def get_run(self, run_id):
        with self.catalog.read_connection() as conn:
            return self._view(conn, self.repo.require_in(conn, run_id, self.owner))

    @staticmethod
    def _page(offset, limit):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise AppError("分页范围非法。", code="INVALID_REQUEST", status_code=422,
                           details={"issues": [{"field": "offset/limit", "code": "PAGE_INVALID", "message": "分页范围非法。"}]})

    def list_runs(self, *, assessment_id=None, score_revision_id=None, offset=0, limit=50):
        """报告列表（B3 归档移除）：返回全部行；``archivedAt`` 只作为旧库残留的只读
        字段透出，归一化脚本负责清空。不再提供 archived 过滤参数。"""
        self._page(offset, limit)
        where, args = ["owner_id=?"], [self.owner]
        for column, value in (("assessment_id", assessment_id), ("score_revision_id", score_revision_id)):
            if value is not None:
                where.append(f"{column}=?")
                args.append(value)
        with self.catalog.read_connection() as conn:
            clause = " AND ".join(where)
            total = conn.execute(f"SELECT count(*) FROM analysis_runs WHERE {clause}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM analysis_runs WHERE {clause} ORDER BY created_at,id LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            return Page[AnalysisRunView](items=[self._view(conn, r) for r in rows], total=total, offset=offset, limit=limit)

    def delete_run(self, run_id: str) -> AnalysisRunDeleteReceipt:
        """删除报告：拆开可拆交叉引用（级联/置空）后物理删除报告与其全部冻结子表行。

        R10-BE（2026-10-13 用户裁定「舍弃所有归档功能，只留删除」+「拆开交叉引用」）：
        报告的下游引用不再一律 409 挡删除，按"引用行是否属于本删除链"分流——

        - **级联**：``practice_sets.analysis_run_id``（NOT NULL）——练习由该报告派生，
          随报告一并连带历史彻底删除（走 ``PracticeRepository.delete_set_with_history_in``，
          含 reviewed 修订/导出/转换/工件；其转换生成的原卷修订只摘来源指针）；
        - **置空**：``lesson_plan_revisions.analysis_run_id``（可空来源指针）——教案本体保留，
          只摘除来源（同事务摘除 ``lesson_plan_revisions_immutable_update`` 后置 NULL）；
        - **409 逐项列出**（不可拆的冻结血缘）：``lesson_generation_inputs`` /
          ``lesson_ai_proposals`` 的 ``analysis_run_id`` 为 NOT NULL 且行不可变——
          删报告会破坏已应用 AI 教案的血缘，拒绝并列出计数（``ANALYSIS_RUN_IN_USE``）。

        三类处理与报告子行删除在同一写事务内完成（任一步失败整体回滚）；删除后
        ``practiceSets``/``lessonRevisions`` 引用自然归零。归档与未归档报告同样可删；
        不存在/非本人 → 404 ``ANALYSIS_NOT_FOUND``。回执带级联计数。
        """
        labels = {"lessonGenerationInputs": "教案生成输入", "lessonProposals": "教案 AI 候选"}
        with self.catalog.write_transaction() as conn:
            self.repo.require_in(conn, run_id, self.owner)
            counts = self.repo.count_references_in(conn, run_id)
            frozen = {
                key: counts[key]
                for key in ("lessonGenerationInputs", "lessonProposals")
                if counts[key] > 0
            }
            if frozen:
                summary = "、".join(f"{labels[key]} {value} 条" for key, value in frozen.items())
                raise AppError(
                    "学情报告仍被教案的冻结生成血缘引用，不能删除（" + summary + "）；"
                    "这些行的来源指针是 NOT NULL 的不可变历史，删除会破坏已应用 AI 教案的血缘。",
                    code=ANALYSIS_RUN_IN_USE, status_code=409, details={"counts": counts})
            practice_ids = self.repo.practice_set_ids_in(conn, run_id)
            with suspend_triggers(conn, ANALYSIS_FROZEN_TRIGGERS + LESSON_REVISION_TRIGGERS):
                for set_id in practice_ids:
                    self.practices.delete_set_with_history_in(conn, set_id)
                unlinked = self.repo.unlink_lesson_revisions_in(conn, run_id)
                self.repo.delete_run_in(conn, run_id, self.owner)
        return AnalysisRunDeleteReceipt(
            deleted=True, runId=run_id,
            removedPracticeSets=len(practice_ids), unlinkedLessonRevisions=int(unlinked),
        )

    def _ready(self, conn, run_id, *, owner=None, class_id=None, participant_id=None, knowledge_point_id=None):
        row = self.repo.require_in(conn, run_id, owner or self.owner)
        if not row["report_ready"]:
            raise AppError("分析报告尚未完成。", code="REPORT_NOT_READY", status_code=409,
                           details={"runId": run_id, "fields": ["reportReady"]})
        facts = load(row["input_json"])
        candidates = {"classId": ({p["classId"] for p in facts["participants"]}, class_id),
                      "participantId": ({p["participantId"] for p in facts["participants"]}, participant_id),
                      "knowledgePointId": ({k["knowledgePointId"] for k in facts["knowledgePoints"]}, knowledge_point_id)}
        for field, (values, value) in candidates.items():
            if value is not None and value not in values:
                raise AppError("筛选身份不属于本报告。", code="ANALYSIS_FILTER_INVALID", status_code=422,
                               details={"issues": [{"field": field, "code": "NOT_IN_REPORT", "message": "筛选身份不属于本报告。"}]})
        if class_id and participant_id and next(p for p in facts["participants"] if p["participantId"] == participant_id)["classId"] != class_id:
            raise AppError("班级与参测人次筛选不一致。", code="ANALYSIS_FILTER_INVALID", status_code=422,
                           details={"issues": [{"field": "participantId", "code": "CLASS_MISMATCH", "message": "班级与人次筛选不一致。"}]})
        return row, facts

    def list_report_rows(self, run_id, kind, *, class_id=None, participant_id=None, knowledge_point_id=None, offset=0, limit=50):
        self._page(offset, limit)
        with self.catalog.read_connection() as conn:
            row, facts = self._ready(conn, run_id, class_id=class_id, participant_id=participant_id, knowledge_point_id=knowledge_point_id)
            where, args = ["r.run_id=?"], [run_id]
            model = {"classes": ClassReportRow, "students": StudentReportRow, "evidence": EvidenceRow}.get(kind)
            if model is None:
                raise AppError("未知报告视图。", code="INVALID_REQUEST", status_code=422)
            if kind == "classes":
                base, order = "analysis_class_results r", "r.class_id,r.knowledge_point_id"
                if participant_id:
                    class_id = next(p for p in facts["participants"] if p["participantId"] == participant_id)["classId"]
                if class_id:
                    where.append("r.class_id=?"); args.append(class_id)
            else:
                base = ("analysis_student_results r" if kind == "students" else "analysis_evidence r")
                base += " JOIN analysis_participants p ON p.run_id=r.run_id AND p.participant_id=r.participant_id"
                order = "r.participant_id," + ("r.knowledge_point_id" if kind == "students" else "r.item_id")
                if participant_id:
                    where.append("r.participant_id=?"); args.append(participant_id)
                if class_id:
                    where.append("p.class_id=?"); args.append(class_id)
                if kind == "evidence":
                    base += " JOIN analysis_item_snapshots i ON i.run_id=r.run_id AND i.item_id=r.item_id"
            if knowledge_point_id:
                where.append("EXISTS(SELECT 1 FROM json_each(i.snapshot_json,'$.knowledgePoints') k "
                             "WHERE json_extract(k.value,'$.knowledgePointId')=?)" if kind == "evidence" else "r.knowledge_point_id=?")
                args.append(knowledge_point_id)
            clause = " AND ".join(where)
            total = conn.execute(f"SELECT count(*) FROM {base} WHERE {clause}", args).fetchone()[0]
            columns = "r.*,p.snapshot_json AS participant_json,i.snapshot_json AS item_json" if kind == "evidence" else (
                "r.class_id,r.payload_json" if kind == "classes" else "r.payload_json")
            records = conn.execute(f"SELECT {columns} FROM {base} WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            items = []
            try:
                # 班名走“名称优先”：payload_json/snapshot_json 只冻结 classId；本页读路径
                # 按同 owner 补 classes.name（班名缺失才 null），归档班照常可读。
                payloads = [load(record["payload_json"]) for record in records] if kind != "evidence" else None
                participants_json = [load(record["participant_json"]) for record in records] if kind == "evidence" else None
                if kind == "classes":
                    names = self._class_names_in(conn, (record["class_id"] for record in records), self.owner)
                elif kind == "students":
                    names = self._class_names_in(conn, (p["participant"]["classId"] for p in payloads), self.owner)
                else:
                    names = self._class_names_in(conn, (p["classId"] for p in participants_json), self.owner)
                for index, record in enumerate(records):
                    if kind == "evidence":
                        item = load(record["item_json"])
                        participant = {**participants_json[index], "className": names.get(participants_json[index]["classId"])}
                        items.append(model(evidenceId=record["id"], runId=run_id, scoreRevisionId=row["score_revision_id"],
                                           paperRevisionId=row["paper_revision_id"], participant=participant,
                                           scoreUnits=record["score_units"], status=record["status"], **item))
                    elif kind == "classes":
                        items.append(model.model_validate({**payloads[index], "className": names.get(record["class_id"])}))
                    else:
                        payload = payloads[index]
                        participant = {**payload["participant"], "className": names.get(payload["participant"]["classId"])}
                        items.append(model.model_validate({**payload, "participant": participant}))
            except (KeyError, TypeError, ValidationError) as exc:
                raise AppError("分析证据结构损坏。", code="ANALYSIS_ROW_CORRUPT", status_code=500) from exc
            return Page[model](items=items, total=total, offset=offset, limit=limit)

    def item_stats(self, run_id):
        """图表聚合（C2）：按题号聚合全班得分率（匿名，不含个人身份）。

        口径：``score_rate = Σrecorded(score_units) / (recorded_count × max_score_units)``；
        missing/absent/exempt 不进分母（与 any_loss_v1 的"有效得分"口径一致）。
        无人有效作答的题 ``score_rate`` 为 null（前端画空档）。
        """
        with self.catalog.read_connection() as conn:
            self._ready(conn, run_id)
            records = conn.execute(
                """SELECT r.item_id AS item_id, i.snapshot_json AS item_json,
                          SUM(CASE WHEN r.status='recorded' AND r.score_units IS NOT NULL THEN r.score_units ELSE 0 END) AS total_score,
                          SUM(CASE WHEN r.status='recorded' AND r.score_units IS NOT NULL THEN 1 ELSE 0 END) AS recorded_count
                   FROM analysis_evidence r
                   JOIN analysis_item_snapshots i ON i.run_id=r.run_id AND i.item_id=r.item_id
                   WHERE r.run_id=?
                   GROUP BY r.item_id ORDER BY r.item_id""",
                (run_id,),
            ).fetchall()
        items: list[ItemStatView] = []
        for record in records:
            snapshot = load(record["item_json"])
            max_units = int(snapshot.get("maxScoreUnits") or 0)
            recorded = int(record["recorded_count"] or 0)
            total = int(record["total_score"] or 0)
            items.append(ItemStatView(
                itemId=record["item_id"],
                itemPath=str(snapshot.get("itemPath") or record["item_id"]),
                maxScoreUnits=max_units,
                recordedCount=recorded,
                totalScoreUnits=total,
                scoreRate=(total / (recorded * max_units)) if recorded > 0 and max_units > 0 else None,
            ))
        return items

    def add_note(self, run_id, payload: NoteRequest):
        command = make_command(operation=f"analysis.note:{run_id}", submission_id=payload.submission_id,
                               owner_id=self.owner, payload=payload.model_dump(by_alias=True, exclude={"submission_id"}))
        def apply(conn):
            self._ready(conn, run_id, participant_id=payload.participant_id, knowledge_point_id=payload.knowledge_point_id)
            if not payload.note.strip():
                raise AppError("备注不能为空。", code="INVALID_REQUEST", status_code=422,
                               details={"issues": [{"field": "note", "code": "EMPTY_NOTE", "message": "备注不能为空。"}]})
            value = {"noteId": uuid.uuid4().hex, "runId": run_id, "participantId": payload.participant_id,
                     "knowledgePointId": payload.knowledge_point_id, "note": payload.note,
                     "createdAt": now_iso(), "replayed": False}
            conn.execute("INSERT INTO analysis_teacher_notes(id,run_id,participant_id,knowledge_point_id,note,created_at) VALUES(?,?,?,?,?,?)",
                         (value["noteId"], run_id, payload.participant_id, payload.knowledge_point_id, payload.note, value["createdAt"]))
            return value
        outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return NoteView.model_validate({**outcome.result, "replayed": outcome.replayed})

    def list_notes(self, run_id, *, offset=0, limit=50):
        self._page(offset, limit)
        with self.catalog.read_connection() as conn:
            self._ready(conn, run_id)
            total = conn.execute("SELECT count(*) FROM analysis_teacher_notes WHERE run_id=?", (run_id,)).fetchone()[0]
            rows = conn.execute("SELECT * FROM analysis_teacher_notes WHERE run_id=? ORDER BY created_at,id LIMIT ? OFFSET ?", (run_id, limit, offset)).fetchall()
            return Page[NoteView](items=[NoteView(noteId=r["id"], runId=run_id, participantId=r["participant_id"],
                knowledgePointId=r["knowledge_point_id"], note=r["note"], createdAt=r["created_at"]) for r in rows],
                total=total, offset=offset, limit=limit)

    def read_ready_report(self, run_id, owner_id="local") -> dict:
        """Public fixed facts for T80; original surfaces contain no participant data."""
        with self.catalog.read_connection() as conn:
            row, facts = self._ready(conn, run_id, owner=owner_id)
            value = self._view(conn, row).model_dump(by_alias=True)
            value.update(originalQuestionRevisionIds=facts["originalQuestionRevisionIds"],
                         originalQuestionContents=facts["originalQuestionContents"],
                         students=[load(r[0]) for r in conn.execute("SELECT payload_json FROM analysis_student_results WHERE run_id=? ORDER BY participant_id,knowledge_point_id", (run_id,))],
                         classes=[load(r[0]) for r in conn.execute("SELECT payload_json FROM analysis_class_results WHERE run_id=? ORDER BY class_id,knowledge_point_id", (run_id,))])
            return value

    # ---------------------------------------------------------------- R6 图表聚合（冻结端点口径）

    def _item_rates_in(self, conn, run_id: str) -> dict[str, dict]:
        """按题聚合全班得分率（与 item_stats 同口径），返回 ``{itemId: {...}}``。

        口径：``score_rate = Σrecorded(score_units) / (recorded_count × max_score_units)``；
        missing/absent/exempt 不进分母（any_loss_v1 的"有效得分"口径）；
        无人有效作答的题 ``scoreRate`` 为 None（参与知识点加权时按"无依据"处理，不计入）。
        """
        records = conn.execute(
            """SELECT r.item_id AS item_id, i.snapshot_json AS item_json,
                      SUM(CASE WHEN r.status='recorded' AND r.score_units IS NOT NULL THEN r.score_units ELSE 0 END) AS total_score,
                      SUM(CASE WHEN r.status='recorded' AND r.score_units IS NOT NULL THEN 1 ELSE 0 END) AS recorded_count
               FROM analysis_evidence r
               JOIN analysis_item_snapshots i ON i.run_id=r.run_id AND i.item_id=r.item_id
               WHERE r.run_id=?
               GROUP BY r.item_id""",
            (run_id,),
        ).fetchall()
        rates: dict[str, dict] = {}
        for record in records:
            snapshot = load(record["item_json"])
            max_units = int(snapshot.get("maxScoreUnits") or 0)
            recorded = int(record["recorded_count"] or 0)
            total = int(record["total_score"] or 0)
            rates[record["item_id"]] = {
                "maxScoreUnits": max_units,
                "recordedCount": recorded,
                "totalScoreUnits": total,
                "scoreRate": (total / (recorded * max_units)) if recorded > 0 and max_units > 0 else None,
            }
        return rates

    def _primary_links_of(self, facts: dict) -> dict[str, list[str]]:
        """报告冻结事实里的 **primary** 知识点链接：``{itemId: [knowledgePointId]}``。

        口径（任务卡冻结）：知识点聚合只走 primary 链接（``paper_item_knowledge``
        冻结快照）；secondary 链接不参与（避免同名知识点被重复计数放大）。
        未挂任何 primary 的小题不计入知识点聚合（口径注明于路由 docstring）。
        """
        links: dict[str, list[str]] = {}
        for item in facts.get("items", []):
            primaries = sorted({
                kp["knowledgePointId"]
                for kp in item.get("knowledgePoints", [])
                if isinstance(kp, dict) and kp.get("role") == "primary" and kp.get("knowledgePointId")
            })
            if primaries:
                links[item["itemId"]] = primaries
        return links

    def _knowledge_paths_in(self, conn, knowledge_point_ids) -> dict[str, str | None]:
        """按知识点库（R3 ``app.state.knowledge``）实时读取目录路径。

        路径 = 自节点向上沿 ``parent_id`` 的 ``code`` 链倒序「 / 」拼接；知识点库未装配、
        节点缺失或环/断链时该知识点落 ``None``（前端显示空路径，不伪造）。
        """
        catalog = self.knowledge_catalog
        ids = sorted({k for k in knowledge_point_ids if isinstance(k, str) and k})
        if not ids or catalog is None:
            return {k: None for k in ids}
        get_point = getattr(catalog, "get_point", None)
        if not callable(get_point):
            return {k: None for k in ids}
        paths: dict[str, str | None] = {}
        with catalog.read_connection() as kconn:
            for point_id in ids:
                try:
                    node = get_point(kconn, point_id)
                except Exception:  # noqa: BLE001 - 跨库读取失败按"无路径"处理
                    node = None
                if node is None:
                    paths[point_id] = None
                    continue
                codes: list[str] = []
                seen: set[str] = set()
                current = node
                while current is not None and current.point_id not in seen:
                    seen.add(current.point_id)
                    codes.append(current.code)
                    if not current.parent_id:
                        break
                    try:
                        current = get_point(kconn, current.parent_id)
                    except Exception:  # noqa: BLE001
                        break
                paths[point_id] = " / ".join(reversed(codes)) if codes else None
        return paths

    def knowledge_stats(self, run_id: str) -> KnowledgeStatsResponse:
        """知识点得分率（冻结形状，``scoreRate`` 降序）。

        口径：先按题（item_stats 同口径）算全班得分率，再对每个知识点把它 primary
        链接的小题按 **满分加权** 平均：``scoreRate = Σ(rate_i × max_i) / Σ(max_i)``，
        其中无有效作答（``scoreRate`` 为 None）的小题不计入（该知识点全部小题均无
        依据时不出现在结果里）。``questionCount`` 是参与加权的小题数（≤ primary 链接数）。
        """
        with self.catalog.read_connection() as conn:
            row, facts = self._ready(conn, run_id)
            rates = self._item_rates_in(conn, run_id)
            paths = self._knowledge_paths_in(
                conn, {kp["knowledgePointId"] for kp in facts.get("knowledgePoints", [])}
            )
        links = self._primary_links_of(facts)
        names = {kp["knowledgePointId"]: kp.get("name") or kp["knowledgePointId"]
                 for kp in facts.get("knowledgePoints", [])}
        totals: dict[str, tuple[float, int]] = {}
        for item_id, knowledge_ids in links.items():
            rate = rates.get(item_id)
            if rate is None or rate["scoreRate"] is None or rate["maxScoreUnits"] <= 0:
                continue
            for knowledge_id in knowledge_ids:
                weight_total, count = totals.get(knowledge_id, (0.0, 0))
                totals[knowledge_id] = (
                    weight_total + rate["scoreRate"] * rate["maxScoreUnits"],
                    count + rate["maxScoreUnits"],
                )
        items: list[KnowledgeStatItem] = []
        for knowledge_id, (weight_total, max_total) in totals.items():
            if max_total <= 0:
                continue
            items.append(KnowledgeStatItem(
                knowledgePointId=knowledge_id,
                name=names.get(knowledge_id, knowledge_id),
                path=paths.get(knowledge_id),
                scoreRate=weight_total / max_total,
                questionCount=sum(
                    1 for item_id, ids in links.items()
                    if knowledge_id in ids and rates.get(item_id) is not None
                    and rates[item_id]["scoreRate"] is not None
                ),
            ))
        items.sort(key=lambda item: (-item.score_rate, item.knowledge_point_id))
        return KnowledgeStatsResponse(items=items)

    def _participant_labels(self, facts: dict) -> dict[str, str]:
        """参测人次的脱敏展示标签（学生A/学生B…，与 AI 评价代称同源；不是姓名）。"""
        labels: dict[str, str] = {}
        for index, participant in enumerate(facts.get("participants", [])):
            pid = participant.get("participantId")
            if isinstance(pid, str) and pid:
                labels[pid] = self._alias_of(index)
        return labels

    @staticmethod
    def _alias_of(index: int) -> str:
        if index < 26:
            return f"学生{chr(ord('A') + index)}"
        return f"学生{index + 1}"

    def student_knowledge(self, run_id: str) -> StudentKnowledgeResponse:
        """学生 × 知识点矩阵（冻结形状；``label`` 为脱敏代称，不是学生姓名）。

        口径：单元得分率 = 该生在该知识点 primary 链接小题上的
        ``Σrecorded(score_units) / Σ(max_score_units)``（只数 recorded；有部分有效成绩
        也照实算）；无任何 recorded 依据 → ``scoreRate=None``（不补 0）。
        学生行按参测人次排序（脱敏代称按 facts 顺序），知识点列按冻结事实顺序。
        """
        with self.catalog.read_connection() as conn:
            row, facts = self._ready(conn, run_id)
            evidence = conn.execute(
                "SELECT participant_id, item_id, status, score_units FROM analysis_evidence "
                "WHERE run_id=? ORDER BY participant_id, item_id",
                (run_id,),
            ).fetchall()
        links = self._primary_links_of(facts)
        knowledge_order = [kp["knowledgePointId"] for kp in facts.get("knowledgePoints", [])]
        names = {kp["knowledgePointId"]: kp.get("name") or kp["knowledgePointId"]
                 for kp in facts.get("knowledgePoints", [])}
        knowledge_ids = [kid for kid in knowledge_order if any(kid in ids for ids in links.values())]
        max_by_item = {item["itemId"]: int(item.get("maxScoreUnits") or 0)
                       for item in facts.get("items", [])}
        per_participant: dict[str, dict[str, tuple[int, int]]] = {}
        for record in evidence:
            pid = record["participant_id"]
            if record["status"] != "recorded" or record["score_units"] is None:
                continue
            cap = max_by_item.get(record["item_id"], 0)
            if cap <= 0:
                continue
            for knowledge_id in links.get(record["item_id"], ()):
                got, max_total = per_participant.setdefault(pid, {}).get(knowledge_id, (0, 0))
                per_participant[pid][knowledge_id] = (
                    got + int(record["score_units"]),
                    max_total + cap,
                )
        # 未选中人次（无任何 evidence 行）也要出现在矩阵里（行齐全，单元全 null）。
        labels = self._participant_labels(facts)
        rows: list[StudentKnowledgeRow] = []
        for participant in facts.get("participants", []):
            pid = participant.get("participantId")
            cells: list[StudentKnowledgeCell] = []
            for knowledge_id in knowledge_ids:
                got, max_total = per_participant.get(pid, {}).get(knowledge_id, (0, 0))
                cells.append(StudentKnowledgeCell(
                    knowledgePointId=knowledge_id,
                    scoreRate=(got / max_total) if max_total > 0 else None,
                    questionCount=sum(1 for item_id, ids in links.items() if knowledge_id in ids),
                ))
            rows.append(StudentKnowledgeRow(label=labels.get(pid, "学生未知"), cells=cells))
        return StudentKnowledgeResponse(
            knowledgePoints=[
                KnowledgePointRef(knowledgePointId=kid, name=names.get(kid, kid))
                for kid in knowledge_ids
            ],
            students=rows,
        )

    def distribution(self, run_id: str) -> DistributionResponse:
        """分数段分布（冻结形状）：学生级该次考试得分率分档。

        口径：学生级得分率 = 该生**全部计分小题**的 recorded 得分合计 / 满分合计；
        该生没有任何 recorded 依据（全 missing/absent/exempt）→ 不进任何分档。
        分档：低 <60% / 中 60–85% / 高 ≥85%；``count`` 按学生（人次即学生，报告已按
        "同学生只能选一个人次"约束冻结）计数。
        """
        with self.catalog.read_connection() as conn:
            row, facts = self._ready(conn, run_id)
            evidence = conn.execute(
                "SELECT participant_id, item_id, status, score_units FROM analysis_evidence "
                "WHERE run_id=?",
                (run_id,),
            ).fetchall()
        max_by_item = {item["itemId"]: int(item.get("maxScoreUnits") or 0)
                       for item in facts.get("items", [])}
        got: dict[str, int] = {}
        max_total: dict[str, int] = {}
        for record in evidence:
            pid = record["participant_id"]
            cap = max_by_item.get(record["item_id"], 0)
            if cap <= 0:
                continue
            max_total[pid] = max_total.get(pid, 0) + cap
            if record["status"] == "recorded" and record["score_units"] is not None:
                got[pid] = got.get(pid, 0) + int(record["score_units"])
        counts = [0, 0, 0]
        for pid, cap in max_total.items():
            if cap <= 0 or pid not in got:
                continue
            rate = got[pid] / cap
            for index, (_, low, high) in enumerate(DISTRIBUTION_BUCKETS):
                if low <= rate < high or (high == float("inf") and rate >= low):
                    counts[index] += 1
                    break
        return DistributionResponse(buckets=[
            DistributionBucket(label=label, count=count)
            for (label, _low, _high), count in zip(DISTRIBUTION_BUCKETS, counts)
        ])

    # ---------------------------------------------------------------- R6 报告导出

    def export_report(self, run_id: str, *, file_assets: Any = None) -> AnalysisReportReceipt:
        """渲染学情分析报告 docx → 落受管资产（kind='export'）+ blob（201 回执）。

        - 内容：标题「学情分析报告」+ 班级/试卷/时间 + 五项指标数据表（小题得分率表、
          热力图口径表、知识点排行、学生×知识点矩阵摘要（label 脱敏）、分数段分布）
          + 教师备注（``analysis_teacher_notes``，含教师手动保存的 AI 评价）；
        - **存储口径（对归档 b4 的审计结论与本批适配）**：归档 b4 把导出产物元数据落
          ``export_artifacts`` 表，但该表被 ``FOREIGN KEY(export_id,owner_id) →
          practice_exports(id,owner_id)`` **表级外键**锁死，``practice_exports`` 行又被
          ``export_source`` 触发器锁死在「已 reviewed 的练习修订」上——分析报告没有
          练习链路（练习域归后续批次），伪造 practice_revisions/practice_exports/
          workflow_jobs 占位行是业务表污染，不走。本批产物元数据落 ``file_assets``
          （kind='export'，b4 资产口径本身支持，含指纹/大小/media_type/原名），回执
          ``artifactId`` = 受管资产 id（内容寻址、唯一、不可变）；下载端点按资产身份
          读取（``ExportArtifactsService`` 的分析报告分支）。练习域回归后如需统一
          元数据表，由总控追加迁移（append-only），本批不越权改登记迁移；
        - 重复导出**生成新产物**（内容寻址 blob 不覆盖，资产登记新行、回执新 id）；
        - 失败如实报错不产半成品：blob 先落（``store_original`` 原子写），资产登记在
          **单一写事务**提交；登记失败整体回滚（blob 成为孤儿文件由内容寻址语义兜底，
          不产生引用它的记录）。
        """
        asset_store = self.assets
        if asset_store is None:
            raise AppError(
                "报告导出缺少受管资产装配：无法落产物，请检查启动日志与依赖。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if file_assets is None:
            file_assets = self.file_assets
        if file_assets is None:
            raise AppError(
                "报告导出缺少受管资产登记装配：无法登记产物，请检查启动日志与依赖。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        from app.services.analysis.report_docx import build_report_document

        report = self.read_ready_report(run_id)
        notes = self.list_notes(run_id, offset=0, limit=200)
        content = build_report_document(
            report=report,
            knowledge_stats=self.knowledge_stats(run_id),
            student_knowledge=self.student_knowledge(run_id),
            distribution=self.distribution(run_id),
            item_stats=self.item_stats(run_id),
            notes=[note.model_dump(by_alias=True) for note in notes.items],
        )
        file_name = _report_filename(report)
        stored = asset_store.store_original(
            content, media_type=_EXPORT_MEDIA_TYPE, original_name=file_name
        )
        with self.catalog.write_transaction() as conn:
            asset = file_assets.create_in(
                conn,
                kind="export",
                blob_key=stored.blob_key,
                sha256=stored.sha256,
                media_type=_EXPORT_MEDIA_TYPE,
                byte_size=stored.byte_size,
                original_name=file_name,
            )
        return AnalysisReportReceipt(
            artifact=ExportArtifactRef(
                artifactId=asset.asset_id, fileName=file_name, byteSize=stored.byte_size
            ),
        )
