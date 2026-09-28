"""题库服务：导入拆题、校对编辑、拆分/合并、AI 整理建议、幂等确认入库与题目管理。

不变量：
- 解析、文件与模型调用一律在 SQL 写事务之外执行；
- 未归属原文块永久保留：拆题只记录 spans，从不删除 ``question_source_blocks``；
- AI 建议只落 ``pending``，应用前核对 ``base_draft_revision``，绝不直接覆盖人工草稿；
- 确认入库在单个事务内完成：同 submissionId 同载荷返回原结果，同键不同载荷 409；
- 任一草稿校验失败整体不确认，返回逐条 failures（HTTP 200 + ``ConfirmResult.failures``）；
- 题库没有任何指向教材索引与教材向量库的路径。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Sequence

from app.core.exceptions import AppError
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.question_bank.records import (
    DraftInput,
    DraftRecord,
    JobRecord,
    SourceBlockInput,
    SourceBlockRecord,
    SuggestionInput,
)
from app.schemas.question_bank import (
    ConfirmFailure,
    ConfirmResult,
    DraftPatchRequest,
    DraftSplitRequest,
    DraftMergeRequest,
    DraftView,
    OrganizeJobView,
    OrganizeRequest,
    QuestionConfirmRequest,
    QuestionDetail,
    QuestionImportDetail,
    QuestionImportList,
    QuestionList,
    QuestionPatchRequest,
    SuggestionApplyRequest,
)
from app.schemas.textbook import MAX_UPLOAD_BYTES
from app.services.document_parsing.parser import (
    PARSER_VERSION,
    SUPPORTED_SUFFIXES,
    ParsedDocument,
    parse_document,
)
from app.services.question_bank import fingerprint as fp
from app.services.question_bank import rules, validation, views
from app.services.question_bank.blobs import QuestionBlobStore
from app.services.question_bank.organizer import (
    BATCH_LEVEL_ORGANIZER_ERRORS,
    DEFAULT_ORGANIZE_MODEL,
    JOB_LEVEL_ORGANIZER_ERRORS,
    LOCAL_MODEL_POLICY,
    MAX_OUTPUT_TOKENS,
    ORGANIZE_INSTRUCTION,
    Batch,
    LocalModelCatalog,
    OllamaModelCatalog,
    OllamaOrganizerModel,
    OrganizerCall,
    OrganizerModel,
    batch_from_snapshot,
    batch_snapshot,
    match_installed_model,
    normalize_reply,
    pack_batches,
)

logger = logging.getLogger("zhiqikeyuan.question_bank")

DEFAULT_OWNER_ID = "local-user"
DEFAULT_IMPORT_LIMIT = 50
MAX_IMPORT_LIMIT = 200
DEFAULT_LIST_LIMIT = 20

SPLIT_NOTE = "已按原文偏移拆分为两道草稿；本行仅保留，不再参与确认。"
MERGE_NOTE = "已与同批草稿合并；本行仅保留，不再参与确认。"


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


class QuestionBankService:
    """题库业务入口；目录（SQLite）与模型端口都由构造参数注入，测试可整体替换。

    AI 整理的模型语义（v1.2 唯一化）：**只用本机 Ollama 的本地模型，绝不调用云端聊天模型**。
    ``OrganizeRequest.modelProfileId`` 是可选的本地模型名覆盖（省略/空串 → ``default_model``）；
    调用上游前先用本机 ``/api/tags`` 校验在场（tag 归一复用 B1 的 ``model_names_match``），
    不在场一律 422 ``ORGANIZER_MODEL_MISSING``；profile 标识（UUID）永远不会被当成模型名发出。
    """

    def __init__(
        self,
        catalog: QuestionBankCatalog,
        settings: Any,
        *,
        organizer: OrganizerModel | None = None,
        model_catalog: LocalModelCatalog | None = None,
        default_model: str = DEFAULT_ORGANIZE_MODEL,
        parser: Callable[..., ParsedDocument] = parse_document,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> None:
        self.catalog = catalog
        self.settings = settings
        self.owner_id = owner_id
        self.parser = parser
        self.default_model = (default_model or "").strip() or DEFAULT_ORGANIZE_MODEL
        self.blobs = QuestionBlobStore(settings.question_bank_root)
        # 默认实现只连本机回环 Ollama；AI 整理必须可注入替身，测试与总控都替换它。
        self.organizer: OrganizerModel = (
            organizer
            if organizer is not None
            else OllamaOrganizerModel(settings.embedding_base_url)
        )
        # 在场校验同样可注入替身：测试不得依赖真实 Ollama /api/tags
        self.model_catalog: LocalModelCatalog = (
            model_catalog
            if model_catalog is not None
            else OllamaModelCatalog(settings.embedding_base_url)
        )

    def close(self) -> None:
        """无长连接需要关闭；保留方法以便统一生命周期调用。"""
        return None

    def _resolve_local_model(self, requested: str) -> str:
        """把请求里的模型字段解析为本机已安装的模型名；不在场一律 422。

        - 空串/未给 → 服务端默认整理模型；
        - 命中按 B1 的 tag 归一（``qwen2.5`` 与 ``qwen2.5:latest`` 等价；不做包含匹配）；
        - 返回命中的**已安装名**，保证传给 ``/api/chat`` 的名字一定来自本机列表；
        - 错误信息不回显请求原文，只给固定策略说明与可操作提示。
        """
        target = (requested or "").strip() or self.default_model
        installed = self.model_catalog.installed_models()
        matched = match_installed_model(target, installed)
        if matched is None:
            raise AppError(
                f"{LOCAL_MODEL_POLICY}；本机没有名为该名称的模型，该次整理未执行。"
                f"请先用 `ollama pull {self.default_model}` 安装默认整理模型，"
                "或在请求里指定一个本机已安装的模型名。",
                code="ORGANIZER_MODEL_MISSING",
                status_code=422,
            )
        return matched

    # ------------------------------------------------------------------ 导入

    def create_import(
        self,
        *,
        file_name: str,
        data: bytes,
        subject_id: str = "",
        grade_id: str = "",
        owner_id: str | None = None,
    ) -> QuestionImportDetail:
        name = (file_name or "").strip()
        if not name:
            raise _invalid("上传文件名不能为空。")
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise _invalid(
                f"不支持的题目文件类型「{suffix or name}」：仅支持 .md / .txt / .pdf / .docx。",
                code="UNSUPPORTED_DOCUMENT_FORMAT",
            )
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppError(
                f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
                code="DOCUMENT_TOO_LARGE",
                status_code=413,
            )
        # 文件落盘在事务外：内容寻址写入 blobs/<sha256>
        blob_id, size = self.blobs.write(data)
        record = self.catalog.create_import(
            owner_id=owner_id or self.owner_id,
            file_sha256=blob_id,
            original_blob_id=blob_id,
            uploaded_file_name=name,
            uploaded_bytes=size,
            state="extracting",
        )
        warnings: list[str] = []
        try:
            parsed = self.parser(
                path=self.blobs.path_of(blob_id),
                file_name=name,
                parser_version=PARSER_VERSION,
                allow_empty_text=True,
            )
        except AppError as exc:
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code=exc.code,
                warnings=[str(exc)],
            )
            return self.get_import_detail(record.import_id)
        except Exception as exc:  # noqa: BLE001 - 解析层未预期异常也要留痕，不伪装成功
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code="DOCUMENT_PARSE_FAILED",
                warnings=[f"解析失败：{exc.__class__.__name__}"],
            )
            return self.get_import_detail(record.import_id)

        warnings.extend(parsed.warnings)
        blocks = self._parsed_blocks(parsed)
        if not any(block.text.strip() for block in blocks):
            # 扫描件与空文档都走这一支：不产生任何草稿，也不假装完成
            if parsed.needs_ocr:
                code = "DOCUMENT_NEEDS_OCR"
                warnings.append("该文件没有文本层（疑似扫描件），需要 OCR 后才能拆题。")
            else:
                code = "DOCUMENT_EMPTY"
                warnings.append("该文件没有可提取的文本内容，无法拆题。")
            if blocks:
                self.catalog.add_source_blocks(record.import_id, blocks)
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code=code,
                warnings=warnings,
            )
            return self.get_import_detail(record.import_id)

        stored = self.catalog.add_source_blocks(record.import_id, blocks)
        split = rules.split_questions(rules.blocks_from_records(stored))
        drafts = [
            self._draft_input(
                draft.content,
                draft.source_spans,
                metadata=self._default_metadata(subject_id=subject_id, grade_id=grade_id),
                warnings=draft.warnings,
                extraction_method="rule",
            )
            for draft in split
        ]
        if drafts:
            self.catalog.create_drafts(record.import_id, drafts)
        else:
            warnings.append("未识别到任何题号起始行，原文已全部保留为未归属块，请人工整理。")
        self.catalog.update_import(
            record.import_id,
            expected_revision=record.revision,
            state="needs_review",
            warnings=warnings,
        )
        return self.get_import_detail(record.import_id)

    def get_import_detail(self, import_id: str) -> QuestionImportDetail:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        drafts = self.catalog.list_drafts(import_id)
        blocks = self.catalog.list_source_blocks(import_id)
        unassigned = [block for block in blocks if not self._is_assigned(block, drafts)]
        return views.import_detail(record, drafts=drafts, unassigned=unassigned)

    def list_imports(self, *, limit: int = DEFAULT_IMPORT_LIMIT) -> QuestionImportList:
        if limit < 1 or limit > MAX_IMPORT_LIMIT:
            raise _invalid(f"limit 必须在 1..{MAX_IMPORT_LIMIT} 之间。")
        summaries = []
        for record in self.catalog.list_imports(limit=limit):
            drafts = self.catalog.list_drafts(record.import_id)
            blocks = self.catalog.list_source_blocks(record.import_id)
            summaries.append(
                views.import_summary(
                    record,
                    draft_count=len(drafts),
                    reviewed_count=sum(1 for draft in drafts if draft.review_state == "reviewed"),
                    unassigned_count=sum(
                        1 for block in blocks if not self._is_assigned(block, drafts)
                    ),
                )
            )
        return QuestionImportList(imports=summaries)

    # ------------------------------------------------------------------ 草稿

    def patch_draft(self, draft_id: str, body: DraftPatchRequest) -> DraftView:
        record = self.catalog.get_draft(draft_id)
        if record is None:
            raise _not_found("草稿不存在。", code="DRAFT_NOT_FOUND")
        content = body.content.model_dump(mode="json")
        updated = self.catalog.update_draft(
            draft_id,
            expected_revision=body.expectedRevision,
            content=content,
            metadata=body.metadata.model_dump(mode="json"),
            review_state=body.reviewState,
            missing_answer_acknowledged=body.missingAnswerAcknowledged,
            content_fingerprint=fp.content_fingerprint(content),
        )
        return views.draft_view(updated)

    def split_draft(
        self,
        import_id: str,
        body: DraftSplitRequest,
        *,
        draft_id: str | None = None,
    ) -> QuestionImportDetail:
        if self.catalog.get_import(import_id) is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        drafts = self.catalog.list_drafts(import_id)
        target = self._resolve_split_target(drafts, draft_id=draft_id, char_offset=body.charOffset)
        if target.review_state == "excluded":
            raise _conflict("已排除的草稿不能拆分。", code="DRAFT_EXCLUDED")
        if target.revision != body.expectedRevision:
            raise _conflict(
                f"草稿已被其他操作更新（当前 revision={target.revision}），请刷新后重试。",
                code="REVISION_CONFLICT",
            )
        blocks = self.catalog.list_source_blocks(import_id)
        lines = [
            line
            for line in rules.lines_from_blocks(rules.blocks_from_records(blocks))
            if rules.line_touches_spans(line, target.source_spans)
        ]
        if not lines:
            raise _invalid("草稿没有可定位的原文区间，无法拆分。", code="DRAFT_SPAN_EMPTY")
        start = min(line.char_start for line in lines)
        end = max(line.char_end for line in lines)
        if not start < body.charOffset < end:
            raise _invalid(
                f"charOffset 必须落在草稿原文区间内（{start}..{end}）。"
            )
        left_lines, right_lines = rules.cut_lines(lines, body.charOffset)
        left = self._split_half(left_lines)
        right = self._split_half(right_lines)
        self.catalog.replace_draft_set(
            import_id,
            excluded=[(target.draft_id, target.revision, SPLIT_NOTE)],
            created=[
                self._draft_input(
                    left.content,
                    left.source_spans,
                    metadata=dict(target.metadata),
                    warnings=left.warnings,
                    extraction_method="manual",
                ),
                self._draft_input(
                    right.content,
                    right.source_spans,
                    metadata=dict(target.metadata),
                    warnings=right.warnings,
                    extraction_method="manual",
                ),
            ],
        )
        return self.get_import_detail(import_id)

    def merge_drafts(self, import_id: str, body: DraftMergeRequest) -> QuestionImportDetail:
        if self.catalog.get_import(import_id) is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        by_id = {draft.draft_id: draft for draft in self.catalog.list_drafts(import_id)}
        if len(body.expectedRevisions) < 2:
            raise _invalid("合并至少需要两道草稿。")
        chosen: list[DraftRecord] = []
        for draft_id, expected_revision in body.expectedRevisions.items():
            draft = by_id.get(draft_id)
            if draft is None:
                raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
            if draft.review_state == "excluded":
                raise _conflict("已排除的草稿不能参与合并。", code="DRAFT_EXCLUDED")
            if draft.revision != expected_revision:
                raise _conflict(
                    f"草稿已被其他操作更新（当前 revision={draft.revision}），请刷新后重试。",
                    code="REVISION_CONFLICT",
                )
            chosen.append(draft)
        chosen.sort(key=lambda draft: self._draft_start(draft))
        merged_content = self._merge_content([draft.content for draft in chosen])
        merged_spans = self._merge_spans([draft.source_spans for draft in chosen])
        self.catalog.replace_draft_set(
            import_id,
            excluded=[(draft.draft_id, draft.revision, MERGE_NOTE) for draft in chosen],
            created=[
                self._draft_input(
                    merged_content,
                    merged_spans,
                    metadata=dict(chosen[0].metadata),
                    warnings=("已由多道草稿合并，需重新校对。",),
                    extraction_method="manual",
                )
            ],
        )
        return self.get_import_detail(import_id)

    # ------------------------------------------------------------- AI 整理

    def organize(self, import_id: str, body: OrganizeRequest) -> OrganizeJobView:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        if record.state == "failed":
            raise _invalid("该导入解析失败，不能进行 AI 整理。", code="IMPORT_PARSE_FAILED")
        if record.state == "cancelled":
            raise _conflict("该导入已取消，不能进行 AI 整理。", code="IMPORT_CANCELLED")
        if record.state == "confirmed":
            raise _conflict("该导入已确认入库，不能再次发起 AI 整理。", code="IMPORT_ALREADY_CONFIRMED")
        # 模型闸门先于取草稿：配置不对时立即 422，不建任务、不发上游、不回显请求原文
        model_name = self._resolve_local_model(body.modelProfileId)
        all_drafts = self.catalog.list_drafts(import_id)
        selected = self._select_drafts(all_drafts, body.draftIds)
        blocks = self.catalog.list_source_blocks(import_id)
        draft_blocks = {
            draft.draft_id: [block for block in blocks if self._intersects(draft, block)]
            for draft in selected
        }
        if body.includeUnassigned:
            self._attach_unassigned(draft_blocks, selected, all_drafts, blocks)
        batches: list[Batch] = []
        for draft in selected:
            chunk = [
                (block.block_id, block.text) for block in draft_blocks[draft.draft_id]
            ]
            if not chunk:
                continue
            batches.extend(
                pack_batches(draft.draft_id, chunk, start_index=len(batches))
            )
        if not batches:
            raise _invalid(
                "所选草稿没有可整理的原文块；请检查草稿来源区间。",
                code="ORGANIZE_TARGET_EMPTY",
            )
        checkpoint: dict[str, Any] = {
            # 请求原文与解析结果都留痕：恢复时不再需要重新解释 profile 标识
            "modelProfileId": (body.modelProfileId or "").strip(),
            "resolvedModel": model_name,
            "includeUnassigned": body.includeUnassigned,
            "instruction": ORGANIZE_INSTRUCTION,
            "drafts": [
                {"draftId": draft.draft_id, "revision": draft.revision} for draft in selected
            ],
            "batches": batch_snapshot(batches),
            "nextBatchIndex": 0,
            "suggestionIds": [],
            "failedBatches": [],
        }
        job = self.catalog.create_job(kind="organize", state="running", checkpoint=checkpoint)
        return self.run_organize_job(job.job_id)

    def run_organize_job(self, job_id: str) -> OrganizeJobView:
        job = self.catalog.get_job(job_id)
        if job is None:
            raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
        if job.state in ("succeeded", "failed", "cancelled"):
            return self._job_view(job)
        checkpoint = dict(job.checkpoint)
        batches = [batch_from_snapshot(item) for item in checkpoint.get("batches", [])]
        drafts_snapshot = {
            str(item.get("draftId")): int(item.get("revision", 0))
            for item in checkpoint.get("drafts", [])
        }
        failed: list[dict[str, Any]] = list(checkpoint.get("failedBatches", []))
        suggestion_ids: list[str] = list(checkpoint.get("suggestionIds", []))
        instruction = str(checkpoint.get("instruction") or ORGANIZE_INSTRUCTION)
        start = int(checkpoint.get("nextBatchIndex", 0))
        # 恢复/续跑前重新确认本机在场（含 v1.0/v1.1 遗留 checkpoint：那时可能存的是 profile 标识）
        try:
            model_name = self._resolve_local_model(
                str(checkpoint.get("resolvedModel") or checkpoint.get("modelProfileId") or "")
            )
        except AppError as exc:
            if exc.code not in JOB_LEVEL_ORGANIZER_ERRORS:
                raise
            updated = self.catalog.update_job(
                job_id, state="failed", error_code=exc.code, checkpoint=checkpoint
            )
            return self._job_view(updated)
        try:
            for index in range(start, len(batches)):
                current = self.catalog.get_job(job_id)
                if current is None:
                    raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
                if current.state == "cancelled":
                    return self._job_view(current)
                batch = batches[index]
                # 先记进度再调用模型：崩溃后重放同一批，不会漏批也不会重复落建议
                checkpoint["nextBatchIndex"] = index
                code: str | None = None
                message: str | None = None
                try:
                    raw = self.organizer.organize(
                        OrganizerCall(
                            job_id=job_id,
                            batch_index=index,
                            model_name=model_name,
                            instruction=instruction,
                            input_text=batch.input_text,
                            max_output_tokens=MAX_OUTPUT_TOKENS,
                        )
                    )
                    parsed = normalize_reply(raw, batch.block_ids)
                except AppError as exc:
                    if exc.code in JOB_LEVEL_ORGANIZER_ERRORS:
                        self.catalog.update_job(
                            job_id, state="failed", error_code=exc.code, checkpoint=checkpoint
                        )
                        return self._job_view(self.catalog.get_job(job_id) or job)
                    code = (
                        exc.code
                        if exc.code in BATCH_LEVEL_ORGANIZER_ERRORS
                        else "ORGANIZER_INVALID_CONTENT"
                    )
                    message = str(exc)
                else:
                    draft = self.catalog.get_draft(batch.draft_id)
                    base_revision = drafts_snapshot.get(batch.draft_id, 0)
                    if draft is None:
                        code = "ORGANIZE_TARGET_MISSING"
                        message = "该批目标草稿已不存在，原文保留，建议未落库。"
                    elif draft.revision != base_revision:
                        code = "ORGANIZE_DRAFT_CHANGED"
                        message = "该批目标草稿在整理期间被编辑，建议已丢弃，请重新整理。"
                    else:
                        created = self.catalog.create_suggestions(
                            [
                                SuggestionInput(
                                    organization_job_id=job_id,
                                    target_draft_id=batch.draft_id,
                                    base_draft_revision=base_revision,
                                    proposed_content=parsed["content"],
                                    proposed_metadata=dict(draft.metadata),
                                    source_block_ids=tuple(parsed["source_block_ids"]),
                                    state="pending",
                                )
                            ]
                        )
                        suggestion_ids.extend(item.suggestion_id for item in created)
                if code is not None:
                    failed.append({"index": index, "code": code, "message": message or ""})
                checkpoint["nextBatchIndex"] = index + 1
                checkpoint["suggestionIds"] = suggestion_ids
                checkpoint["failedBatches"] = failed
                self.catalog.update_job(job_id, checkpoint=checkpoint)
        except BaseException:
            # 未预期异常：保留 running 与已完成的进度，重启后由 recover 续跑
            try:
                self.catalog.update_job(job_id, checkpoint=checkpoint)
            except Exception:  # noqa: BLE001 - 保存进度失败不掩盖原始异常
                logger.exception("保存题库整理任务 %s 进度失败", job_id)
            raise
        checkpoint["suggestionIds"] = suggestion_ids
        checkpoint["failedBatches"] = failed
        if suggestion_ids:
            updated = self.catalog.update_job(
                job_id, state="succeeded", checkpoint=checkpoint, clear_error=True
            )
        else:
            updated = self.catalog.update_job(
                job_id,
                state="failed",
                checkpoint=checkpoint,
                error_code=(failed[-1]["code"] if failed else "ORGANIZE_NO_SUGGESTION"),
            )
        return self._job_view(updated)

    def cancel_organize_job(self, job_id: str) -> OrganizeJobView:
        job = self.catalog.get_job(job_id)
        if job is None:
            raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
        if job.state in ("queued", "running"):
            job = self.catalog.update_job(job_id, state="cancelled")
        return self._job_view(job)

    def recover_organize_jobs(self, *, max_jobs: int = 8) -> int:
        """重启恢复：续跑未完成的整理任务；已完成/已取消的不重复执行。"""
        recovered = 0
        for job in self.catalog.pending_jobs(
            kinds=["organize"], states=["queued", "running"], limit=max_jobs
        ):
            try:
                self.run_organize_job(job.job_id)
            except Exception:  # noqa: BLE001 - 单条恢复失败不影响其他任务
                logger.exception("恢复题库整理任务 %s 失败", job.job_id)
                continue
            recovered += 1
        return recovered

    def get_organize_job(self, job_id: str) -> OrganizeJobView:
        job = self.catalog.get_job(job_id)
        if job is None:
            raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
        return self._job_view(job)

    def list_suggestions(self, *, job_id: str | None = None, draft_id: str | None = None):
        records = self.catalog.list_suggestions(
            organization_job_id=job_id, target_draft_id=draft_id
        )
        return [views.suggestion_view(record) for record in records]

    def apply_suggestion(
        self, suggestion_id: str, body: SuggestionApplyRequest
    ) -> DraftView:
        warning = f"已应用 AI 建议 {suggestion_id}：内容需重新校对。"
        _suggestion, draft = self.catalog.apply_suggestion(
            suggestion_id,
            expected_draft_revision=body.expectedDraftRevision,
            accept=body.accept,
            warning=warning,
        )
        return views.draft_view(draft)

    # ------------------------------------------------------------- 确认入库

    def confirm(self, body: QuestionConfirmRequest) -> ConfirmResult:
        record = self.catalog.get_import(body.importId)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        request_fingerprint = fp.request_fingerprint(
            {
                "importId": body.importId,
                "items": [
                    {
                        "draftId": item.draftId,
                        "expectedDraftRevision": item.expectedDraftRevision,
                    }
                    for item in body.items
                ],
                "duplicateResolutions": sorted(
                    (
                        {
                            "draftId": resolution.draftId,
                            "action": resolution.action,
                            "existingQuestionId": resolution.existingQuestionId,
                        }
                        for resolution in body.duplicateResolutions
                    ),
                    key=lambda item: item["draftId"],
                ),
            }
        )
        with self.catalog.write_transaction() as conn:
            if self.catalog.import_in(conn, body.importId) is None:
                raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
            existing = self.catalog.submission_in(conn, body.submissionId)
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise _conflict(
                        "同一提交键已登记不同载荷的确认请求，拒绝复用原结果。",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return ConfirmResult.model_validate(existing.result)

            plan, failures = self._plan_confirm(conn, body)
            if failures:
                # 任一草稿不合法 -> 整体不确认；不写 submission，修正后可用同一提交键重试
                return ConfirmResult(
                    confirmedQuestionIds=[],
                    linkedQuestionIds=[],
                    skippedDraftIds=[],
                    failures=failures,
                )

            confirmed: list[str] = []
            linked: list[str] = []
            skipped: list[str] = []
            for step in plan:
                draft = step["draft"]
                if step["action"] in ("skip", "none") and step["duplicates"]:
                    target = step["duplicates"][0]["question"]
                    self.catalog.mark_draft_duplicate_in(
                        conn,
                        draft.draft_id,
                        question_id=target.question_id,
                        warning=(
                            f"已跳过：与已有题目 {target.question_id} 内容相同"
                            "（指纹不含答案与解析）。"
                        ),
                    )
                    skipped.append(draft.draft_id)
                    continue
                if step["action"] == "link_existing":
                    target_id = step["targetQuestionId"]
                    added = self.catalog.add_question_sources_in(
                        conn,
                        target_id,
                        source_spans=draft.source_spans,
                        import_id=body.importId,
                    )
                    self.catalog.mark_draft_duplicate_in(
                        conn,
                        draft.draft_id,
                        question_id=target_id,
                        warning=(
                            f"已并入已有题目 {target_id}（新增 {added} 条来源，"
                            "未修改已有题内容）。"
                        ),
                        review_state="excluded",
                    )
                    if target_id not in linked:
                        linked.append(target_id)
                    continue
                question = self.catalog.insert_question_in(
                    conn,
                    owner_id=self.owner_id,
                    content=draft.content,
                    metadata=draft.metadata,
                    answer_state=validation.answer_state_of(step["content"]),
                    content_fingerprint=step["fingerprint"],
                    source_spans=draft.source_spans,
                    import_id=body.importId,
                )
                confirmed.append(question.question_id)

            result = ConfirmResult(
                confirmedQuestionIds=confirmed,
                linkedQuestionIds=linked,
                skippedDraftIds=skipped,
                failures=[],
            )
            self.catalog.save_submission_in(
                conn,
                submission_id=body.submissionId,
                request_fingerprint=request_fingerprint,
                result=result.model_dump(mode="json"),
            )
            if confirmed or linked:
                self.catalog.set_import_state_in(conn, body.importId, state="confirmed")
            return result

    # ---------------------------------------------------------------- 题目

    def list_questions(
        self,
        *,
        subject_id: str | None = None,
        grade_id: str | None = None,
        edition_id: str | None = None,
        status: str | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIST_LIMIT,
        owner_id: str | None = None,
    ) -> QuestionList:
        records, total = self.catalog.list_questions(
            owner_id=owner_id or self.owner_id,
            subject_id=subject_id,
            grade_id=grade_id,
            edition_id=edition_id,
            status=status,
            query=query,
            offset=offset,
            limit=limit,
        )
        return QuestionList(
            questions=[views.question_summary(record) for record in records],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_question(self, question_id: str) -> QuestionDetail:
        record = self.catalog.get_question(question_id)
        if record is None:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        return views.question_detail(record)

    def patch_question(self, question_id: str, body: QuestionPatchRequest) -> QuestionDetail:
        record = self.catalog.get_question(question_id)
        if record is None:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        content = body.content.model_dump(mode="json")
        updated = self.catalog.patch_question(
            question_id,
            expected_revision=body.expectedRevision,
            content=content,
            metadata=body.metadata.model_dump(mode="json"),
            answer_state=validation.answer_state_of(body.content),
            content_fingerprint=fp.content_fingerprint(content),
        )
        return views.question_detail(updated)

    def delete_question(self, question_id: str, *, expected_revision: int | None = None) -> None:
        record = self.catalog.get_question(question_id)
        if record is None:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        self.catalog.archive_question(question_id, expected_revision=expected_revision)

    # ------------------------------------------------------------------ 内部

    def _plan_confirm(
        self, conn, body: QuestionConfirmRequest
    ) -> tuple[list[dict[str, Any]], list[ConfirmFailure]]:
        resolutions = {item.draftId: item for item in body.duplicateResolutions}
        plan: list[dict[str, Any]] = []
        failures: list[ConfirmFailure] = []
        seen: set[str] = set()
        for item in body.items:
            draft_id = item.draftId
            if draft_id in seen:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_DUPLICATED_IN_REQUEST",
                        message="同一草稿在一次确认请求里出现多次。",
                    )
                )
                continue
            seen.add(draft_id)
            draft = self.catalog.draft_in(conn, draft_id)
            if draft is None:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_NOT_FOUND",
                        message="草稿不存在。",
                    )
                )
                continue
            if draft.import_id != body.importId:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_IMPORT_MISMATCH",
                        message="草稿不属于该导入。",
                    )
                )
                continue
            if draft.revision != item.expectedDraftRevision:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="REVISION_CONFLICT",
                        message=(
                            f"草稿已被更新（当前 revision={draft.revision}），请刷新后重试。"
                        ),
                    )
                )
                continue
            try:
                content = validation.parse_content(draft.content)
            except AppError as exc:
                failures.append(
                    ConfirmFailure(draftId=draft_id, code=exc.code, message=str(exc))
                )
                continue
            issue = validation.validate_for_confirm(
                content=content,
                review_state=draft.review_state,
                missing_answer_acknowledged=draft.missing_answer_acknowledged,
            )
            if issue is not None:
                failures.append(
                    ConfirmFailure(draftId=draft_id, code=issue.code, message=issue.message)
                )
                continue

            content_payload = content.model_dump(mode="json")
            fingerprint = fp.content_fingerprint(content_payload)
            duplicates = [
                {"question": question, "fingerprint": question.content_fingerprint}
                for question in self.catalog.questions_by_fingerprint_in(
                    conn, self.owner_id, fingerprint
                )
            ]
            resolution = resolutions.get(draft_id)
            action = resolution.action if resolution is not None else "none"
            target_question_id: str | None = None
            if resolution is not None and resolution.existingQuestionId is not None:
                target_question_id = resolution.existingQuestionId
            if action == "link_existing":
                candidate_ids = {entry["question"].question_id for entry in duplicates}
                if not candidate_ids:
                    failures.append(
                        ConfirmFailure(
                            draftId=draft_id,
                            code="DUPLICATE_RESOLUTION_INVALID",
                            message="没有可关联的重复题目，link_existing 无法执行。",
                        )
                    )
                    continue
                if target_question_id is None:
                    target_question_id = duplicates[0]["question"].question_id
                elif target_question_id not in candidate_ids:
                    failures.append(
                        ConfirmFailure(
                            draftId=draft_id,
                            code="DUPLICATE_RESOLUTION_INVALID",
                            message="existingQuestionId 与内容指纹不匹配的重复题不一致。",
                        )
                    )
                    continue
            if action == "edit_as_new" and duplicates:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DUPLICATE_UNRESOLVED",
                        message=(
                            "内容与已有题目完全相同（指纹不含答案与解析）；"
                            "edit_as_new 需要内容确实不同。"
                        ),
                    )
                )
                continue
            plan.append(
                {
                    "draft": draft,
                    "content": content,
                    "fingerprint": fingerprint,
                    "duplicates": duplicates,
                    "action": action,
                    "targetQuestionId": target_question_id,
                }
            )
        return plan, failures

    def _parsed_blocks(self, parsed: ParsedDocument) -> list[SourceBlockInput]:
        blocks: list[SourceBlockInput] = []
        for index, block in enumerate(parsed.source_map):
            text = parsed.normalized_text[block.char_start : block.char_end]
            blocks.append(
                SourceBlockInput(ordinal=index, text=text, locator=block.to_json())
            )
        return blocks

    @staticmethod
    def _default_metadata(*, subject_id: str, grade_id: str) -> dict[str, Any]:
        return {
            "stageId": "",
            "gradeId": grade_id or "",
            "subjectId": subject_id or "",
            "editionId": "",
            "knowledgeTags": [],
            "difficulty": "unspecified",
        }

    def _draft_input(
        self,
        content: dict[str, Any],
        source_spans: list[dict[str, Any]],
        *,
        metadata: dict[str, Any],
        warnings: Sequence[str] = (),
        extraction_method: str = "rule",
    ) -> DraftInput:
        validated = validation.parse_content(content).model_dump(mode="json")
        return DraftInput(
            content=validated,
            metadata=metadata,
            source_spans=source_spans,
            extraction_method=extraction_method,
            review_state="needs_review",
            warnings=tuple(warnings),
            content_fingerprint=fp.content_fingerprint(validated),
        )

    @staticmethod
    def _block_range(block: SourceBlockRecord) -> tuple[int, int]:
        locator = block.locator
        start = locator.get("charStart")
        end = locator.get("charEnd")
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            start = 0
        if not isinstance(end, int) or isinstance(end, bool) or end < start:
            end = start + len(block.text)
        return start, end

    def _intersects(self, draft: DraftRecord, block: SourceBlockRecord) -> bool:
        start, end = self._block_range(block)
        for span in draft.source_spans:
            if span.get("blockId") != block.block_id:
                continue
            span_start = span.get("charStart")
            span_end = span.get("charEnd")
            if not isinstance(span_start, int) or not isinstance(span_end, int):
                continue
            if span_start < end and span_end > start:
                return True
        return False

    def _is_assigned(self, block: SourceBlockRecord, drafts: Sequence[DraftRecord]) -> bool:
        return any(self._intersects(draft, block) for draft in drafts)

    @staticmethod
    def _draft_start(draft: DraftRecord) -> int:
        starts = [
            span.get("charStart")
            for span in draft.source_spans
            if isinstance(span.get("charStart"), int)
        ]
        return min(starts) if starts else 0

    def _resolve_split_target(
        self,
        drafts: Sequence[DraftRecord],
        *,
        draft_id: str | None,
        char_offset: int,
    ) -> DraftRecord:
        if not drafts:
            raise _invalid("该导入还没有草稿，无法拆分。", code="IMPORT_HAS_NO_DRAFT")
        if draft_id is not None:
            for draft in drafts:
                if draft.draft_id == draft_id:
                    return draft
            raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
        # 契约缺口：DraftSplitRequest 没有 draftId 字段；缺省时按 charOffset 唯一命中草稿，
        # 命中不唯一一律 422，不猜测用户意图（变更建议见结果卡）。
        candidates = [
            draft
            for draft in drafts
            if draft.review_state != "excluded" and self._covers_offset(draft, char_offset)
        ]
        if len(candidates) == 1:
            return candidates[0]
        raise _invalid(
            "无法唯一确定要拆分的草稿：请在查询参数 draftId 中显式给出草稿 id。",
            code="DRAFT_ID_REQUIRED",
        )

    def _covers_offset(self, draft: DraftRecord, char_offset: int) -> bool:
        for span in draft.source_spans:
            start = span.get("charStart")
            end = span.get("charEnd")
            if isinstance(start, int) and isinstance(end, int) and start < char_offset < end:
                return True
        return False

    @staticmethod
    def _split_half(lines: Sequence[rules.RuleLine]) -> rules.SplitDraft:
        parsed = rules.drafts_from_lines(lines)
        if parsed:
            return parsed[0]
        return rules.fallback_draft(lines)

    def _select_drafts(
        self, all_drafts: Sequence[DraftRecord], draft_ids: Sequence[str]
    ) -> list[DraftRecord]:
        if draft_ids:
            by_id = {draft.draft_id: draft for draft in all_drafts}
            selected: list[DraftRecord] = []
            for draft_id in draft_ids:
                draft = by_id.get(draft_id)
                if draft is None:
                    raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
                if draft.review_state == "excluded":
                    raise _conflict("已排除的草稿不能参与 AI 整理。", code="DRAFT_EXCLUDED")
                selected.append(draft)
        else:
            selected = [
                draft for draft in all_drafts if draft.review_state != "excluded"
            ]
        if not selected:
            raise _invalid("没有可整理的草稿。", code="ORGANIZE_TARGET_EMPTY")
        return selected

    def _attach_unassigned(
        self,
        draft_blocks: dict[str, list[SourceBlockRecord]],
        selected: Sequence[DraftRecord],
        all_drafts: Sequence[DraftRecord],
        blocks: Sequence[SourceBlockRecord],
    ) -> None:
        """``includeUnassigned``：把未归属块挂到其前一道所选草稿（无前驱则挂第一道）。"""
        ordered = list(selected)
        for block in blocks:
            if self._is_assigned(block, all_drafts):
                continue
            if not block.text.strip():
                continue
            start, _end = self._block_range(block)
            host = ordered[0]
            for draft in ordered:
                if self._draft_start(draft) <= start:
                    host = draft
                else:
                    break
            draft_blocks.setdefault(host.draft_id, []).append(block)

    def _job_view(self, job: JobRecord) -> OrganizeJobView:
        """建议明细只给仍可处理的 ``pending`` 项；``suggestionCount`` 与 ``failedBatches``
        始终是任务的累计事实，便于前端显示「已处理 N/M」。
        """
        all_suggestions = self.catalog.list_suggestions(organization_job_id=job.job_id)
        pending = [item for item in all_suggestions if item.state == "pending"]
        return views.organize_job_view(
            job,
            suggestions=pending,
            suggestion_count=len(all_suggestions),
        )

    @staticmethod
    def _merge_spans(groups: Sequence[Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
        merged: dict[str, list[int]] = {}
        order: list[str] = []
        for spans in groups:
            for span in spans:
                block_id = span.get("blockId")
                start = span.get("charStart")
                end = span.get("charEnd")
                if not isinstance(block_id, str) or not isinstance(start, int) or not isinstance(end, int):
                    continue
                if block_id not in merged:
                    merged[block_id] = [start, end]
                    order.append(block_id)
                else:
                    merged[block_id][0] = min(merged[block_id][0], start)
                    merged[block_id][1] = max(merged[block_id][1], end)
        return [
            {"blockId": block_id, "charStart": merged[block_id][0], "charEnd": merged[block_id][1]}
            for block_id in order
        ]

    def _merge_content(self, contents: Sequence[dict[str, Any]]) -> dict[str, Any]:
        stems = [str(content.get("stemMarkdown", "")).strip() for content in contents]
        stem = "\n\n".join(item for item in stems if item) or "（合并草稿）"
        options: list[dict[str, str]] = []
        used: set[str] = set()
        for content in contents:
            for option in content.get("options") or []:
                key = str(option.get("key", "")).strip()
                text = str(option.get("textMarkdown", "")).strip()
                if not key or not text:
                    continue
                if key in used:
                    key = self._next_option_key(used)
                used.add(key)
                options.append({"key": key, "textMarkdown": text})
        choice_keys: list[str] = []
        accepted: bool | None = None
        answer_texts: list[str] = []
        for content in contents:
            answer = content.get("answer") or {}
            for key in answer.get("choiceKeys") or []:
                if key not in choice_keys:
                    choice_keys.append(str(key))
            if accepted is None and answer.get("accepted") is not None:
                accepted = bool(answer["accepted"])
            text = answer.get("textMarkdown")
            if isinstance(text, str) and text.strip():
                answer_texts.append(text.strip())
        answer: dict[str, Any] | None = None
        if choice_keys or accepted is not None or answer_texts:
            answer = {
                "choiceKeys": choice_keys,
                "accepted": accepted,
                "textMarkdown": "\n".join(answer_texts) if answer_texts else None,
            }
        explanations = [
            str(content.get("explanationMarkdown")).strip()
            for content in contents
            if content.get("explanationMarkdown")
        ]
        asset_ids: list[str] = []
        for content in contents:
            for asset_id in content.get("assetIds") or []:
                if asset_id not in asset_ids:
                    asset_ids.append(str(asset_id))
        types = {str(content.get("type")) for content in contents}
        question_type = types.pop() if len(types) == 1 else "other"
        payload = {
            "type": question_type,
            "stemMarkdown": stem,
            "options": options,
            "answer": answer,
            "explanationMarkdown": "\n".join(explanations) if explanations else None,
            "assetIds": asset_ids,
        }
        return validation.parse_content(payload).model_dump(mode="json")

    @staticmethod
    def _next_option_key(used: set[str]) -> str:
        for code in range(ord("A"), ord("Z") + 1):
            candidate = chr(code)
            if candidate not in used:
                return candidate
        return f"X{len(used) + 1}"


def build_question_bank_service(
    catalog: QuestionBankCatalog,
    settings: Any,
    *,
    organizer: OrganizerModel | None = None,
    model_catalog: LocalModelCatalog | None = None,
    default_model: str = DEFAULT_ORGANIZE_MODEL,
) -> QuestionBankService:
    """装配入口：总控在 main.py 里用 ``settings.question_bank_root`` 构造目录与本服务。

    ``organizer`` / ``model_catalog`` 都可注入替身；``default_model`` 是省略
    ``modelProfileId`` 时使用的本机模型名（默认与 RAG 概括同一默认 ``qwen2.5:7b``）。
    """
    return QuestionBankService(
        catalog,
        settings,
        organizer=organizer,
        model_catalog=model_catalog,
        default_model=default_model,
    )
