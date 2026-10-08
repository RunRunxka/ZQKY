"""Fixed-score analysis with public JobEngine publication and append-only notes."""
from __future__ import annotations

import functools
import uuid

import anyio
from pydantic import ValidationError

from app.contracts.b4 import (AnalysisCreateRequest, AnalysisReceipt, AnalysisRunView,
                              ClassReportRow, EvidenceRow, NoteRequest, NoteView, Page, StudentReportRow)
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.analysis import AnalysisRepository, dump, load
from app.services.jobs.engine import JobOutcome
from app.services.submissions.service import execute_command, make_command
from .aggregate import aggregate
from .snapshot import read_facts


class AnalysisService:
    def __init__(self, catalog, *, job_engine, asset_store, owner_id="local"):
        self.catalog, self.engine, self.assets, self.owner = catalog, job_engine, asset_store, owner_id
        self.repo = AnalysisRepository()
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

    def list_runs(self, *, assessment_id=None, score_revision_id=None, archived=None, offset=0, limit=50):
        self._page(offset, limit)
        where, args = ["owner_id=?"], [self.owner]
        for column, value in (("assessment_id", assessment_id), ("score_revision_id", score_revision_id)):
            if value is not None:
                where.append(f"{column}=?")
                args.append(value)
        if archived is not None:
            # 缺省返回全部；True 只看已归档，False 只看未归档（已归档报告仍可按 id 读取）。
            where.append("archived_at IS NOT NULL" if archived else "archived_at IS NULL")
        with self.catalog.read_connection() as conn:
            clause = " AND ".join(where)
            total = conn.execute(f"SELECT count(*) FROM analysis_runs WHERE {clause}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM analysis_runs WHERE {clause} ORDER BY created_at,id LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            return Page[AnalysisRunView](items=[self._view(conn, r) for r in rows], total=total, offset=offset, limit=limit)

    def set_archived(self, run_id: str, payload, *, archived: bool) -> AnalysisRunView:
        """软归档/恢复：只写 ``archived_at``，报告内容与子表一概不动。

        ``analysis_no_delete`` 触发器保持报告不可删除，本方法也不绕过它；
        ``analysis_inputs_fixed``（0011 升级版）只放行已封存报告的 archived_at 写。
        报告没有 revision 列，按"存在性 + 幂等"语义处理：重复归档/重复恢复返回
        当前视图，不报错；归档不要求 report_ready（未完成任务也可先行归档隐藏）。
        """
        with self.catalog.write_transaction() as conn:
            row = self.repo.require_in(conn, run_id, self.owner)
            if bool(row["archived_at"]) is not archived:
                conn.execute("UPDATE analysis_runs SET archived_at=? WHERE id=?",
                             (now_iso() if archived else None, run_id))
        return self.get_run(run_id)

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
