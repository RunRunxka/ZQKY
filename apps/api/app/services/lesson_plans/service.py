"""Real immutable lessons, original-command receipts and terminal AI decisions.

Preparation does no writes and runs outside publication/SQL transactions. Receipt
and preflight read the same SQLite snapshot; the transaction checks the receipt
again before owner/CAS/lineage. Preparation failures also recheck the receipt.
"""
from __future__ import annotations

import functools
import uuid

import anyio

from app.contracts import lesson_plans as lp
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.lesson_plans import LessonPlanRepository, dump, load
from app.services.submissions.service import execute_command, make_command
from .context import freeze_context, invalid, revalidate_context
from .views import lesson_view, proposal_view, revision_view, validate


def snapshot(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True, mode="json")
    return load(dump(value))


def freeze(kind, body):
    return kind.model_validate(snapshot(body))


def content_hash(data, context, source, metadata):
    return canonical_hash(dict(data=data, contextSnapshot=context, source=source, sourceMetadata=metadata))


def conflict(doc, fields=("expectedRevision",)):
    return AppError("教案版本已变化，请查看差异后再选择。", code="REVISION_CONFLICT", status_code=409,
                    details={"currentRevision": doc["revision"], "fields": list(fields)})


async def run(fn, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


class LessonPlanService:
    def __init__(self, catalog, *, analysis_reader, knowledge_catalog, coordinator, job_engine,
                 generation_service, evidence_reader, owner_id="local", asset_store=None, file_assets=None):
        self.catalog, self.analysis, self.knowledge, self.coordinator = catalog, analysis_reader, knowledge_catalog, coordinator
        self.engine, self.generation, self.evidence, self.owner = job_engine, generation_service, evidence_reader, owner_id
        # R7 导出组装（新增注入；缺省 None 时导出按 503 处理，不假成功）
        self.assets, self.file_assets = asset_store, file_assets
        self.repo = LessonPlanRepository()
        self.store = job_engine.store("teaching")

    def register_job_executors(self, registry):
        registry.register("teaching", "lesson_generation", uses_model=True, factory=self.generation.executor_for)

    def _command(self, operation, body, *, imported=False):
        value = snapshot(body)
        value.pop("submissionId")
        if imported:
            value["draft"].pop("updatedAt")
        return make_command(operation=operation, submission_id=body.submission_id, payload=value, owner_id=self.owner)

    def _replay_in(self, conn, command):
        row = conn.execute("SELECT request_hash,result_json FROM command_submissions WHERE owner_id=? AND operation=? AND submission_id=?",
                           (command.owner_id, command.operation, command.submission_id)).fetchone()
        if row is None:
            return None
        if row["request_hash"] != command.request_hash:
            raise AppError("同一提交标识已用于不同请求。", code="SUBMISSION_CONFLICT", status_code=409,
                           details={"fields": ["submissionId"]})
        result = load(row["result_json"])
        if not isinstance(result, dict):
            raise AppError("提交回执损坏。", code="SUBMISSION_CORRUPT", status_code=500)
        return {**result, "replayed": True}

    def _preflight(self, command, inspect=None):
        with self.catalog.read_connection() as conn:
            prior = self._replay_in(conn, command)
            if prior is not None:
                return prior, None
            return None, inspect(conn) if inspect is not None else None

    def _replay(self, command):
        return self._preflight(command)[0]

    def _after_prepare_error(self, command):
        with self.coordinator.publication(operation=command.operation+".preparation_error"):
            return self._replay(command)

    def _publish(self, command, apply, refs=None):
        with self.coordinator.publication(operation=command.operation):
            prior = self._replay(command)
            if prior is not None:
                return prior
            if refs is not None:
                refs()
            outcome = execute_command(catalog=self.catalog, command=command, apply=apply)
        return {**outcome.result, "replayed": outcome.replayed}

    def _current(self, conn, lesson_id, expected_revision, base_revision_id=None):
        doc = self.repo.document(conn, lesson_id, self.owner)
        if doc["revision"] != expected_revision:
            raise conflict(doc)
        if base_revision_id is not None and doc["current_revision_id"] != base_revision_id:
            raise conflict(doc, ("baseRevisionId", "expectedRevision"))
        if doc["archived_at"] is not None:
            # B3 归档移除：残留归档行按只读兜底（文案指向归一化脚本，不再有"恢复"入口）。
            raise AppError("教案状态异常（残留归档数据，请先运行归一化脚本），不能写入。",
                           code="LESSON_INVALID", status_code=422)
        return doc

    def get_lesson(self, lesson_id):
        with self.catalog.read_connection() as conn:
            return lesson_view(self.repo, conn, lesson_id, self.owner)

    def get_revision(self, lesson_id, revision_id):
        with self.catalog.read_connection() as conn:
            self.repo.document(conn, lesson_id, self.owner)
            return revision_view(self.repo.revision(conn, lesson_id, revision_id, self.owner))

    def list_lessons(self, subject_id=None, class_id=None, offset=0, limit=50):
        """教案列表（B3 归档移除）：返回全部正常数据，不再按 archived 过滤。

        旧库残留的 ``archived_at`` 非空行（若有）仍会列出（读取不受影响），
        归一化脚本负责清空该列。
        """
        self._pagination(offset, limit)
        with self.catalog.read_connection() as conn:
            rows, total = self.repo.list_documents(conn, self.owner, subject_id=subject_id, class_id=class_id,
                archived=False, offset=offset, limit=limit)
            items = [validate(lp.LessonSummary, dict(lessonPlanId=row["id"], subjectId=row["subject_id"], classId=row["class_id"],
                revision=row["revision"], currentRevisionId=row["current_revision_id"], title=row["title"], source=row["source"],
                analysisRunId=row["analysis_run_id"], updatedAt=row["updated_at"])) for row in rows]
        return dict(items=items, total=total, offset=offset, limit=limit)

    def list_revisions(self, lesson_id, offset=0, limit=50):
        self._pagination(offset, limit)
        with self.catalog.read_connection() as conn:
            rows, total = self.repo.list_revisions(conn, lesson_id, self.owner, offset=offset, limit=limit)
            items = [validate(lp.LessonRevisionSummary, dict(lessonPlanId=row["lesson_plan_id"], revisionId=row["id"], version=row["version"],
                title=row["title"], contentHash=row["content_hash"], source=row["source"], analysisRunId=row["analysis_run_id"],
                acceptedProposalId=row["accepted_proposal_id"], selectedFields=load(row["selected_fields_json"]),
                reviewState=row["review_state"], createdAt=row["created_at"])) for row in rows]
        return dict(items=items, total=total, offset=offset, limit=limit)

    @staticmethod
    def _pagination(offset, limit):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 200:
            raise invalid("pagination", "offset须非负，limit须为1至200的整数。")

    def create_lesson(self, body):
        body = freeze(lp.LessonCreateRequest, body)
        return self._create(body, source=body.source, data=snapshot(body.data))

    def import_local(self, body):
        body = freeze(lp.LessonImportRequest, body)
        return self._create(body, source="import_local", data=snapshot(body.draft.data), envelope=snapshot(body.draft))

    def _create(self, body, *, source, data, envelope=None):
        command = self._command("lesson.import-local" if envelope is not None else "lesson.create", body, imported=envelope is not None)
        prior = self._replay(command)
        if prior is not None:
            return prior
        try:
            context = freeze_context(self, body.subject_id, body.class_id, body.context)
        except Exception:
            prior = self._after_prepare_error(command)
            if prior is not None:
                return prior
            raise
        metadata = {"localEnvelope": {key: value for key, value in envelope.items() if key != "updatedAt"}} if envelope is not None else {}
        digest = content_hash(data, context, source, metadata)
        def apply(conn):
            lesson_id, revision_id, created_at = uuid.uuid4().hex, uuid.uuid4().hex, now_iso()
            self.repo.insert_document(conn, lesson_id=lesson_id, owner_id=self.owner, subject_id=body.subject_id,
                class_id=body.class_id, revision_id=revision_id, created_at=created_at)
            self.repo.append_revision(conn, lesson_id=lesson_id, owner_id=self.owner, version=1, data=data, content_hash=digest,
                source=source, context=context, source_metadata=metadata, revision_id=revision_id, created_at=created_at, import_envelope=envelope)
            return lesson_view(self.repo, conn, lesson_id, self.owner)
        return self._publish(command, apply, lambda: revalidate_context(self, context))

    def delete_lesson(self, lesson_id, payload):
        """受守卫的彻底删除：物理删除教案行及其自身历史（归档与否都允许删除）。

        守卫（同一写事务内、乐观锁核验之后）：

        - ``expectedRevision`` 不符 → 409 ``REVISION_CONFLICT``（仓库既有语义）；
        - 教案不存在/非本人 → 404 ``NOT_FOUND``；
        - 本行被教案五表之外的表引用 → 409 ``LESSON_IN_USE`` 并在
          ``details.counts`` 列出计数（0010 迁移核实当前为 0 处外部引用，守卫为
          结构性防线：若将来新增引用表，删除会在这一步被挡下而不是留下悬挂行）。

        通过后按子行 → 身份行顺序在同一写事务删除
        ``lesson_proposal_decisions`` → ``lesson_ai_proposals`` →
        ``lesson_generation_inputs`` → ``lesson_revision_reviews`` →
        ``lesson_plan_revisions`` → ``lesson_plans``；五张表的不可变 DELETE 触发器
        在事务内临时摘除、删除后逐字恢复（见仓储 ``delete_lesson_in``）。
        走 ``PublicationCoordinator`` 临界区：删除时不可能有在途的保存/生成/应用写入。
        """
        body = freeze(lp.LessonRevisionRequest, payload)
        with self.coordinator.publication(operation="lesson.delete"):
            with self.catalog.write_transaction() as conn:
                document = self.repo.document(conn, lesson_id, self.owner)
                if document["revision"] != body.expected_revision:
                    raise conflict(document)
                # 教案候选引用（decisions/proposals/inputs）全部指向本教案自身的历史
                # （FK 图谱见仓储 delete_lesson_in），属于删除范围而不是外部引用；
                # 外部引用清单当前为空（0010 迁移核实），保留守卫结构作为防线。
                external = {}
                if external:
                    summary = "、".join(f"{key} {value} 条" for key, value in external.items())
                    raise AppError("教案仍被引用，不能删除（" + summary + "）；归档教案是安全的替代做法。",
                        code="LESSON_IN_USE", status_code=409, details={"counts": external})
                return self.repo.delete_lesson_in(conn, lesson_id, self.owner)

    def save_draft(self, lesson_id, body):
        body = freeze(lp.LessonSaveRequest, body)
        command = self._command("lesson.draft:"+lesson_id, body)
        prior, doc = self._preflight(command, lambda conn: dict(self._current(conn, lesson_id, body.expected_revision)))
        if prior is not None:
            return prior
        data = snapshot(body.data)
        try:
            context = freeze_context(self, doc["subject_id"], doc["class_id"], body.context)
        except Exception:
            prior = self._after_prepare_error(command)
            if prior is not None:
                return prior
            raise
        digest = content_hash(data, context, body.source, {})
        def apply(conn):
            current = self._current(conn, lesson_id, body.expected_revision)
            old = self.repo.revision(conn, lesson_id, current["current_revision_id"], self.owner)
            if old["content_hash"] == digest:
                return lesson_view(self.repo, conn, lesson_id, self.owner)
            revision_id = self.repo.append_revision(conn, lesson_id=lesson_id, owner_id=self.owner, version=current["revision"]+1,
                data=data, content_hash=digest, source=body.source, context=context, source_metadata={})
            self.repo.advance(conn, lesson_id=lesson_id, owner_id=self.owner, old_revision=current["revision"], revision_id=revision_id)
            return lesson_view(self.repo, conn, lesson_id, self.owner)
        return self._publish(command, apply, lambda: revalidate_context(self, context))

    def verify_evidence(self, body):
        body = freeze(lp.LessonEvidenceRequest, body)
        return self.evidence.prepare_selected_evidence(body.selection, body.slices)

    async def generate_proposal(self, lesson_id, body):
        body = freeze(lp.LessonGenerateRequest, body)
        command = self._command("lesson.generate:"+lesson_id, body)
        def inspect(conn):
            self._current(conn, lesson_id, body.base_server_revision, body.base_revision_id)
            return lesson_view(self.repo, conn, lesson_id, self.owner)
        prior, lesson = await run(self._preflight, command, inspect)
        if prior is not None:
            return prior
        try:
            prepared = await run(self.generation.prepare, body, lesson=lp.LessonView.model_validate(lesson), owner_id=self.owner)
        except Exception:
            prior = await run(self._after_prepare_error, command)
            if prior is not None:
                return prior
            raise
        def apply(conn):
            self._current(conn, lesson_id, body.base_server_revision, body.base_revision_id)
            job = self.store.create_in(conn, kind="lesson_generation", owner_id=self.owner,
                frozen_input=snapshot(prepared.frozen_input), model_snapshot=snapshot(prepared.model_snapshot))
            self.generation.insert_input_in(conn, job=job, prepared=prepared, owner_id=self.owner)
            return dict(lessonPlanId=lesson_id, inputHash=job.input_hash, job=job.view().model_dump(by_alias=True, mode="json"), replayed=False)
        result = await run(self._publish, command, apply, lambda: self.generation.revalidate_prepared_refs(prepared.frozen_input))
        if not result["replayed"]:
            record = await run(self.store.get, result["job"]["jobId"])
            self.engine.schedule("teaching", record.job_id, self.generation.executor_for(record), uses_model=True)
        return result

    def get_proposal(self, lesson_id, proposal_id):
        with self.catalog.read_connection() as conn:
            return proposal_view(self.repo, conn, lesson_id, proposal_id, self.owner)

    def _pending(self, conn, lesson_id, proposal_id, body):
        doc = self.repo.document(conn, lesson_id, self.owner)
        proposal = self.repo.proposal(conn, lesson_id, proposal_id, self.owner)
        if self.repo.decision(conn, lesson_id, proposal_id, self.owner) is not None:
            raise AppError("该建议已终结，不能再次应用。", code="LESSON_PROPOSAL_TERMINATED", status_code=409)
        if (doc["current_revision_id"] != proposal["base_revision_id"] or doc["revision"] != proposal["base_server_revision"]
                or body.base_revision_id != proposal["base_revision_id"]):
            raise AppError("该建议基于旧教案版本，须重新生成。", code="LESSON_PROPOSAL_STALE", status_code=409,
                           details={"currentRevision": doc["revision"], "fields": ["baseRevisionId"]})
        self._current(conn, lesson_id, body.expected_revision, body.base_revision_id)
        return doc, proposal

    async def apply_proposal(self, lesson_id, proposal_id, body):
        body = freeze(lp.LessonApplyRequest, body)
        command = self._command("lesson.apply:"+lesson_id+":"+proposal_id, body)
        def inspect(conn):
            _, proposal = self._pending(conn, lesson_id, proposal_id, body)
            return dict(proposal)
        prior, proposal = await run(self._preflight, command, inspect)
        if prior is not None:
            return prior
        fixed = load(proposal["frozen_json"])
        try:
            payload = await run(self.generation.validate_for_apply, load(proposal["payload_json"]), fixed)
            payload = snapshot(payload)
            for field in body.selected_fields:
                if payload["patch"].get(field) is None:
                    raise invalid("selectedFields", "不能选择该建议未提供的字段。", "LESSON_PROPOSAL_INVALID")
            # Full immutable source verification includes byte hashes/body spans.
            # SQL-only active-reference recheck follows inside publication.
            await run(self.evidence.verify_selected_evidence, fixed["scopeSnapshot"], fixed["evidenceRefs"])
            context = validate(lp.LessonContextSnapshot, fixed["contextSnapshot"])
        except Exception:
            prior = await run(self._after_prepare_error, command)
            if prior is not None:
                return prior
            raise
        def apply(conn):
            doc, _ = self._pending(conn, lesson_id, proposal_id, body)
            current = self.repo.revision(conn, lesson_id, doc["current_revision_id"], self.owner)
            data = load(current["data_json"])
            for field in body.selected_fields:
                data[field] = snapshot(payload["patch"][field])
            data = validate(lp.LessonPlanData, data)
            selected = list(body.selected_fields)
            metadata = dict(proposalId=proposal_id, inputHash=proposal["input_hash"], modelFingerprint=proposal["model_fingerprint"],
                selectedFields=selected, generationSource=payload["generationSource"])
            process_metadata = payload["budget"]["stages"] if "process" in selected else []
            revision_id = self.repo.append_revision(conn, lesson_id=lesson_id, owner_id=self.owner, version=doc["revision"]+1,
                data=data, content_hash=content_hash(data, context, "ai_applied", metadata), source="ai_applied", context=context,
                source_metadata=metadata, accepted_proposal_id=proposal_id, selected_fields=selected, process_metadata=process_metadata)
            self.repo.advance(conn, lesson_id=lesson_id, owner_id=self.owner, old_revision=doc["revision"], revision_id=revision_id)
            self.repo.insert_decision(conn, lesson_id=lesson_id, owner_id=self.owner, proposal_id=proposal_id, state="applied",
                selected_fields=selected, revision_id=revision_id)
            return lesson_view(self.repo, conn, lesson_id, self.owner)
        return await run(self._publish, command, apply, lambda: self.generation.revalidate_prepared_refs(fixed))

    def reject_proposal(self, lesson_id, proposal_id, body):
        body = freeze(lp.LessonRejectRequest, body)
        command = self._command("lesson.reject:"+lesson_id+":"+proposal_id, body)
        def inspect(conn):
            self.repo.document(conn, lesson_id, self.owner)
            self.repo.proposal(conn, lesson_id, proposal_id, self.owner)
            if self.repo.decision(conn, lesson_id, proposal_id, self.owner) is not None:
                raise AppError("该建议已终结。", code="LESSON_PROPOSAL_TERMINATED", status_code=409)
        prior, _ = self._preflight(command, inspect)
        if prior is not None:
            return prior
        def apply(conn):
            inspect(conn)
            self.repo.insert_decision(conn, lesson_id=lesson_id, owner_id=self.owner, proposal_id=proposal_id, state="rejected")
            return proposal_view(self.repo, conn, lesson_id, proposal_id, self.owner)
        return self._publish(command, apply)

    def export_lesson(self, lesson_id: str, body) -> dict:
        """组装并落盘教案导出产物（R7-BE 新能力；同步产物，无任务行）。

        - 组装：以空白模板为底（封面 + 目录 + 正文四表 + 自定义模块表），
          ``Preview 所见即导出所得``——正文取当前修订的 ``data``，排版/模块布局
          取请求体（``style``/``modules``）；组装后重开校验（节数/footer PAGE/表数）；
        - 产物落受管资产（``file_assets`` kind='export'，内容寻址 blob）——与 R6
          学情报告产物同一形态（``export_artifacts`` 表被 practice_exports 表级外键
          锁死，不伪造练习占位行）；重复导出生成**新产物**（新资产行、新 id）；
        - 失败不产半成品：blob 先落（原子写），资产登记在单一写事务内提交；
        - 导出请求/产物不落教案修订历史（不递增 revision，不进 CAS）。
        """
        from app.contracts.lesson_plans import LessonExportRequest, LessonExportReceipt, LessonExportArtifactRef
        from app.services.lesson_plans.export import (
            ExportAssemblyError,
            ExportPayload,
            LESSON_EXPORT_MEDIA_TYPE,
            artifact_filename,
            build_document,
        )
        body = LessonExportRequest.model_validate(snapshot(body))
        with self.catalog.read_connection() as conn:
            document = self.repo.document(conn, lesson_id, self.owner)
            if document["archived_at"] is not None:
                raise AppError("教案状态异常（残留归档数据，请先运行归一化脚本），不能导出。",
                               code="LESSON_INVALID", status_code=422)
            revision = self.repo.revision(conn, lesson_id, document["current_revision_id"], self.owner)
        data = load(revision["data_json"])
        payload = ExportPayload.parse({
            "data": data,
            "style": body.style.model_dump(by_alias=True, mode="json"),
            "modules": [module.model_dump(by_alias=True, mode="json", exclude_none=True) for module in body.modules],
            "sectionPages": body.section_pages,
        })
        try:
            content = build_document(payload)
        except ExportAssemblyError as exc:
            raise AppError(f"教案导出组装失败：{exc}", code="LESSON_EXPORT_FAILED", status_code=500) from exc
        asset_store = getattr(self, "assets", None)
        file_assets = getattr(self, "file_assets", None)
        if asset_store is None or file_assets is None:
            raise AppError(
                "导出产物存储未装配：无法落产物，请检查启动日志与依赖。",
                code="SERVICE_UNAVAILABLE", status_code=503, retryable=True,
            )
        file_name = artifact_filename(data)
        stored = asset_store.store_original(content, media_type=LESSON_EXPORT_MEDIA_TYPE, original_name=file_name)
        with self.catalog.write_transaction() as conn:
            asset = file_assets.create_in(
                conn,
                kind="export",
                blob_key=stored.blob_key,
                sha256=stored.sha256,
                media_type=LESSON_EXPORT_MEDIA_TYPE,
                byte_size=stored.byte_size,
                original_name=file_name,
            )
        receipt = LessonExportReceipt(
            artifact=LessonExportArtifactRef(
                artifactId=asset.asset_id, fileName=file_name, byteSize=stored.byte_size
            )
        )
        return snapshot(receipt)
