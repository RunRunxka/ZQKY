"""知识点服务门面（TEACHING-LOOP B1 / T20）。

冻结方法名（路由与测试按此对接）：``list_points`` / ``create_point`` / ``get_point`` /
``update_point`` / ``set_archived`` / ``list_textbook_links`` / ``add_textbook_link`` /
``delete_textbook_link`` / ``create_file_import`` / ``get_import`` / ``list_imports`` /
``patch_import`` / ``confirm_import`` / ``create_suggestion_job``。

纪律（与四库一致）：

- SQL 一律走注入的 ``KnowledgeCatalog``（写事务 ``BEGIN IMMEDIATE`` + 延迟外键），
  事务内只做 SQL；跨库读（教材、教学库 ``file_assets``）与模型调用、文件解析一律在
  写事务之外；
- ``PublicationCoordinator`` 包住"核验外部修订 → 本库短事务"的三处发布：
  确认导入、归档/恢复、教材依据新增（以及导入预览落库），锁内不调用模型；
- 表格读取统一用 ``services.tabular.read_table``；导入行为规则在
  ``services.knowledge.imports``，AI 候选提示词/解析在 ``services.knowledge.suggestions``；
- AI 候选走 B0 任务引擎：``engine.store("knowledge").create(kind="suggestion", …)`` →
  ``engine.schedule("knowledge", job_id, executor, uses_model=True)``；执行器在事务外调用
  模型，``JobOutcome.publish`` 在知识点库**同一事务**写入 ``source="ai"`` 的待确认批次并
  置 ``succeeded``。候选绝不直接写正式表。
"""

from __future__ import annotations

import functools
import json
import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import anyio

from app.contracts.knowledge import (
    KNOWLEDGE_ARCHIVED,
    KNOWLEDGE_CODE_CONFLICT,
    KNOWLEDGE_CROSS_SUBJECT_PARENT,
    KNOWLEDGE_CYCLE,
    KNOWLEDGE_IMPORT_BLOCKING_ISSUES,
    KNOWLEDGE_IMPORT_CONFIRMED,
    KNOWLEDGE_PARENT_INVALID,
    KNOWLEDGE_ROW_INVALID,
    KNOWLEDGE_SUGGESTION_NO_EVIDENCE,
    KNOWLEDGE_SUGGESTION_TRUNCATED,
    TEXTBOOK_EVIDENCE_UNAVAILABLE,
    KnowledgeImportConfirmRequest,
    KnowledgeImportConfirmResult,
    KnowledgeImportList,
    KnowledgeImportPatchRequest,
    KnowledgeImportView,
    KnowledgePointCreateRequest,
    KnowledgePointList,
    KnowledgePointRevisionRequest,
    KnowledgePointUpdateRequest,
    KnowledgePointView,
    KnowledgeSuggestionRequest,
    TextbookLinkCreateRequest,
    TextbookLinkList,
    TextbookLinkView,
)
from app.contracts.teaching_loop import (
    ErrorIssue,
    JobView,
    error_details,
)
from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMMessage, LLMRequest
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.knowledge.imports import (
    ImportRecord,
    ImportRowInput,
    ImportRowRecord,
    KnowledgeImportRepository,
)
from app.repositories.knowledge.points import (
    UNSET,
    KnowledgePointRepository,
    LinkRecord,
    PointRecord,
    SubjectRepository,
    TextbookLinkRepository,
    normalize_alias,
    not_found,
    revision_conflict,
)
from app.services.assets.store import AssetStore
from app.services.jobs.engine import FrozenJob, JobContext, JobEngine, JobOutcome
from app.services.knowledge import imports as import_rules
from app.services.knowledge import suggestions as suggestion_rules
from app.services.knowledge.evidence import TextbookEvidenceReader
from app.services.model_runtime import ChatModelHandle
from app.services.publication import PublicationCoordinator
from app.services.submissions.service import execute_command, make_command
from app.services.tabular import SheetTable, read_table

logger = logging.getLogger("zhiqikeyuan.knowledge")

#: 单个上传文件上限（路由先按 multipart 大小拒绝，服务层再兜底）
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
DEFAULT_OWNER_ID = "local"
#: 允许确认入库的批次状态（confirmed 由重复确认单独报错）
CONFIRMABLE_STATES = frozenset({"uploaded", "reviewing"})
#: 允许继续校对的状态
EDITABLE_STATES = frozenset({"uploaded", "reviewing"})

ChatModelResolver = Callable[..., ChatModelHandle]


async def _threaded(fn, /, *args: Any, **kwargs: Any):
    """把同步的 SQL/文件/模型解析调用放到 anyio 有界线程执行。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def _issue_error(
    message: str, *, code: str, issue: ErrorIssue, status_code: int = 422
) -> AppError:
    """构造 422/409 的 ``details.issues``（形状来源只有冻结契约 ``error_details``）。"""
    return AppError(
        message,
        code=code,
        status_code=status_code,
        details=error_details(issues=[issue]),
    )


def _issues_error(message: str, *, code: str, issues: Sequence[ErrorIssue]) -> AppError:
    return AppError(
        message,
        code=code,
        status_code=422,
        details=error_details(issues=list(issues)),
    )


def _field_error(message: str, *, fields: Sequence[str]) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=list(fields)),
    )


class KnowledgeService:
    """知识点业务入口；目录、资产、教材证据、发布协调器、模型与任务引擎全部注入。"""

    def __init__(
        self,
        catalog: KnowledgeCatalog,
        *,
        asset_store: AssetStore,
        file_assets: Any,
        evidence: TextbookEvidenceReader | None,
        coordinator: PublicationCoordinator,
        model_resolver: ChatModelResolver | None = None,
        job_engine: JobEngine | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> None:
        self.catalog = catalog
        self.assets = asset_store
        self.file_assets = file_assets
        self.evidence = evidence
        self.coordinator = coordinator
        self.model_resolver = model_resolver
        self.job_engine = job_engine
        self.owner_id = owner_id
        self.subjects = SubjectRepository()
        self.points = KnowledgePointRepository()
        self.links = TextbookLinkRepository()
        self.imports = KnowledgeImportRepository()

    def close(self) -> None:
        """无长连接需要关闭；保留方法以便统一生命周期调用。"""
        return None

    # ------------------------------------------------------------------ 知识点

    def list_points(
        self,
        *,
        subject_id: str | None = None,
        status: str | None = None,
        parent_id: str | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> KnowledgePointList:
        _validate_page(offset=offset, limit=limit)
        with self.catalog.read_connection() as conn:
            items, total = self.points.list_points(
                conn,
                subject_id=subject_id,
                status=status,
                parent_id=parent_id,
                q=q,
                offset=offset,
                limit=limit,
            )
        return KnowledgePointList.model_validate(
            {
                "items": [_point_dict(record) for record in items],
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )

    def create_point(self, payload: KnowledgePointCreateRequest) -> KnowledgePointView:
        if payload.parent_id and payload.parent_code:
            raise _field_error(
                "父节点只能给一个：parentId 或 parentCode。", fields=["parentId", "parentCode"]
            )
        subject_id = payload.subject_id.strip()
        code = payload.code.strip()
        name = payload.name.strip()
        if not name:
            raise _field_error("名称不能为空。", fields=["name"])
        with self.coordinator.publication(operation="knowledge.create"):
            with self.catalog.write_transaction() as conn:
                self.subjects.ensure_subject(conn, subject_id=subject_id, name=subject_id)
                parent_id = _resolve_parent(
                    conn,
                    subject_id=subject_id,
                    parent_id=payload.parent_id,
                    parent_code=payload.parent_code,
                    points=self.points,
                )
                if self.points.get_by_code(conn, subject_id=subject_id, code=code) is not None:
                    raise _conflict(
                        f"学科内编码已存在：{code}。", code=KNOWLEDGE_CODE_CONFLICT
                    )
                record = self.points.create_point(
                    conn,
                    subject_id=subject_id,
                    code=code,
                    name=name,
                    description=payload.description,
                    parent_id=parent_id,
                    sort_order=payload.sort_order,
                    aliases=payload.aliases,
                )
                _log_alias_ambiguity(
                    conn,
                    subject_id=subject_id,
                    aliases=payload.aliases,
                    exclude_point_id=record.point_id,
                    points=self.points,
                )
        return _point_view(record)

    def get_point(self, point_id: str) -> KnowledgePointView:
        with self.catalog.read_connection() as conn:
            record = self.points.get_point(conn, _text(point_id, field="pointId"))
            if record is None:
                raise not_found("知识点不存在。", code="KNOWLEDGE_POINT_NOT_FOUND")
        return _point_view(record)

    def update_point(
        self, point_id: str, payload: KnowledgePointUpdateRequest
    ) -> KnowledgePointView:
        point_id = _text(point_id, field="pointId")
        provided = payload.model_fields_set
        name: str | None = None
        if "name" in provided and payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise _field_error("名称不能为空。", fields=["name"])

        description: str | None = None
        if "description" in payload.clear_fields:
            description = ""
        elif "description" in provided and payload.description and payload.description.strip():
            description = payload.description.strip()

        parent_value: Any = UNSET
        if "parentId" in payload.clear_fields:
            parent_value = None

        aliases: list[str] | None = None
        if "aliases" in payload.clear_fields:
            aliases = []
        elif "aliases" in provided and payload.aliases:
            aliases = list(payload.aliases)

        explicit_parent_id = (
            payload.parent_id if "parent_id" in provided and payload.parent_id else None
        )
        explicit_parent_code = (
            payload.parent_code if "parent_code" in provided and payload.parent_code else None
        )
        if explicit_parent_id and explicit_parent_code:
            raise _field_error(
                "父节点只能给一个：parentId 或 parentCode。", fields=["parentId", "parentCode"]
            )

        with self.coordinator.publication(operation="knowledge.update"):
            with self.catalog.write_transaction() as conn:
                current = self.points.require_point(conn, point_id)
                if current.revision != payload.expected_revision:
                    raise revision_conflict(current.revision)
                if explicit_parent_id or explicit_parent_code:
                    parent_value = _resolve_parent(
                        conn,
                        subject_id=current.subject_id,
                        parent_id=explicit_parent_id,
                        parent_code=explicit_parent_code,
                        points=self.points,
                        point_id=point_id,
                    )
                record = self.points.update_point(
                    conn,
                    point_id,
                    expected_revision=payload.expected_revision,
                    name=name,
                    description=description,
                    parent_id=parent_value,
                    sort_order=payload.sort_order,
                    aliases=aliases,
                )
                if aliases:
                    _log_alias_ambiguity(
                        conn,
                        subject_id=current.subject_id,
                        aliases=aliases,
                        exclude_point_id=point_id,
                        points=self.points,
                    )
        return _point_view(record)

    def set_archived(
        self,
        point_id: str,
        payload: KnowledgePointRevisionRequest,
        *,
        archived: bool,
    ) -> KnowledgePointView:
        point_id = _text(point_id, field="pointId")
        operation = "knowledge.archive" if archived else "knowledge.restore"
        with self.coordinator.publication(operation=operation):
            with self.catalog.write_transaction() as conn:
                record = self.points.set_status(
                    conn,
                    point_id,
                    expected_revision=payload.expected_revision,
                    archived=archived,
                )
        return _point_view(record)

    # ------------------------------------------------------------------ 教材依据

    def list_textbook_links(self, point_id: str) -> TextbookLinkList:
        point_id = _text(point_id, field="pointId")
        with self.catalog.read_connection() as conn:
            self.points.require_point(conn, point_id)
            records = self.links.list_links(conn, point_id=point_id)
        return TextbookLinkList.model_validate(
            {"items": [_link_dict(record) for record in records]}
        )

    def add_textbook_link(
        self, point_id: str, payload: TextbookLinkCreateRequest
    ) -> TextbookLinkView:
        point_id = _text(point_id, field="pointId")
        with self.coordinator.publication(operation="knowledge.textbook-link.create"):
            # 锁内先核验外部教材修订（冻结标题与区间），再写本库短事务；
            # 这里只读教材文本，不调用模型、不做业务解析。
            if self.evidence is None:
                raise AppError(
                    "教材目录未装配，无法核验教材依据。",
                    code=TEXTBOOK_EVIDENCE_UNAVAILABLE,
                    status_code=503,
                    retryable=True,
                )
            evidence = self.evidence.read(
                document_revision_id=payload.document_revision_id,
                char_start=payload.char_start,
                char_end=payload.char_end,
            )
            with self.catalog.write_transaction() as conn:
                current = self.points.require_point(conn, point_id)
                if current.revision != payload.expected_revision:
                    raise revision_conflict(current.revision)
                if current.status == "archived":
                    raise _conflict(
                        "知识点已归档：归档保留历史引用，但不能新增教材依据，请先恢复。",
                        code=KNOWLEDGE_ARCHIVED,
                    )
                record = self.links.create_link(
                    conn,
                    point_id=point_id,
                    knowledge_revision_id=current.revision_id,
                    document_revision_id=evidence.document_revision_id,
                    char_start=evidence.char_start,
                    char_end=evidence.char_end,
                    title_snapshot=evidence.title,
                    source=payload.source,
                    locator=evidence.locator,
                )
        return _link_view(record)

    def delete_textbook_link(
        self, point_id: str, link_id: str, *, expected_revision: int
    ) -> None:
        point_id = _text(point_id, field="pointId")
        link_id = _text(link_id, field="linkId")
        with self.coordinator.publication(operation="knowledge.textbook-link.delete"):
            with self.catalog.write_transaction() as conn:
                current = self.points.require_point(conn, point_id)
                if current.revision != expected_revision:
                    raise revision_conflict(current.revision)
                link = self.links.get_link(conn, link_id)
                if link is None or link.knowledge_point_id != point_id:
                    # 不存在**或**不属于该知识点：都按"找不到"处理，不返回假成功
                    raise not_found("教材依据不存在。", code="KNOWLEDGE_LINK_NOT_FOUND")
                self.links.delete_link(conn, point_id=point_id, link_id=link_id)

    # ------------------------------------------------------------------ 导入

    def create_file_import(
        self,
        *,
        file_name: str,
        content: bytes,
        media_type: str,
        subject_id: str,
        mapping: dict[str, str] | None = None,
        sheet_name: str | None = None,
    ) -> KnowledgeImportView:
        name = _text(file_name, field="fileName")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise _field_error("上传内容不能为空。", fields=["file"])
        if len(content) > MAX_UPLOAD_BYTES:
            raise AppError(
                f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
                code="DOCUMENT_TOO_LARGE",
                status_code=413,
            )
        subject_id = _text(subject_id, field="subjectId")
        payload = bytes(content)
        resolved_media_type = (media_type or "").strip() or "application/octet-stream"

        # ① 受管资产落盘（事务外）；② 教学库登记（跨库写，先做，见任务卡 §8.3）
        stored = self.assets.store_original(
            payload, media_type=resolved_media_type, original_name=name
        )
        asset = self.file_assets.create(
            kind="attachment",
            blob_key=stored.blob_key,
            sha256=stored.sha256,
            media_type=resolved_media_type,
            byte_size=stored.byte_size,
            original_name=name,
        )
        # ③ 表格解析（事务外，统一走 services.tabular）
        tables = read_table(
            payload, file_name=name, media_type=resolved_media_type, sheet_name=sheet_name
        )
        table = tables[0]
        warnings: list[str] = []
        if sheet_name is None and len(tables) > 1:
            warnings.append(
                f"文件有 {len(tables)} 个工作表，已按第一个「{table.name}」预览；"
                "可用 sheetName 指定其他工作表。"
            )
        if not table.headers:
            warnings.append("该工作表没有表头行，无法映射列；请检查文件内容。")
        resolved_mapping = import_rules.auto_map(table.headers)
        if mapping is not None:
            manual = import_rules.validate_mapping(mapping, table.headers)
            resolved_mapping = {**resolved_mapping, **manual}
        # ④ 派生与校验（只读；预览是快照，确认时会以当前库状态重新校验）
        with self.catalog.read_connection() as conn:
            derived = import_rules.derive_file_rows(
                conn,
                subject_id=subject_id,
                table=table,
                mapping=resolved_mapping,
                points=self.points,
            )
        warnings.extend(derived.warnings)
        # ⑤ 本库短事务落库（批次 + 行 + issues/warnings）
        with self.coordinator.publication(operation="knowledge.import.create"):
            with self.catalog.write_transaction() as conn:
                self.subjects.ensure_subject(conn, subject_id=subject_id, name=subject_id)
                record = self.imports.create_import(
                    conn,
                    source="file",
                    subject_id=subject_id,
                    file_asset_id=asset.asset_id,
                    mapping=resolved_mapping,
                    batch_issues=derived.batch_issues,
                    warnings=warnings,
                    rows=derived.rows,
                    state="reviewing",
                    owner_id=self.owner_id,
                )
                rows = self.imports.list_rows(conn, record.import_id)
                versions = _base_versions(conn, rows, self.points)
        return self._import_view(record, rows, base_versions=versions)

    def get_import(self, import_id: str) -> KnowledgeImportView:
        import_id = _text(import_id, field="importId")
        with self.catalog.read_connection() as conn:
            record = self.imports.get_import(conn, import_id)
            if record is None:
                raise not_found("知识点导入不存在。", code="KNOWLEDGE_IMPORT_NOT_FOUND")
            rows = self.imports.list_rows(conn, import_id)
            versions = _base_versions(conn, rows, self.points)
        return self._import_view(record, rows, base_versions=versions)

    def list_imports(
        self, *, state: str | None = None, offset: int = 0, limit: int = DEFAULT_LIST_LIMIT
    ) -> KnowledgeImportList:
        _validate_page(offset=offset, limit=limit)
        items: list[dict[str, Any]] = []
        with self.catalog.read_connection() as conn:
            records, total = self.imports.list_imports(
                conn, state=state, offset=offset, limit=limit
            )
            for record in records:
                items.append(
                    _summary_dict(
                        record,
                        row_count=self.imports.count_rows(conn, record.import_id),
                        blocking_issue_count=_blocking_count(
                            self.imports.issue_codes(conn, record.import_id)
                        ),
                    )
                )
        return KnowledgeImportList.model_validate(
            {"items": items, "total": total, "offset": offset, "limit": limit}
        )

    def patch_import(
        self, import_id: str, payload: KnowledgeImportPatchRequest
    ) -> KnowledgeImportView:
        import_id = _text(import_id, field="importId")
        with self.coordinator.publication(operation="knowledge.import.patch"):
            with self.catalog.write_transaction() as conn:
                record = self.imports.require_import(conn, import_id)
                if record.state == "confirmed":
                    raise _conflict(
                        "导入批次已确认入库，不能继续修改。",
                        code=KNOWLEDGE_IMPORT_CONFIRMED,
                    )
                if record.state not in EDITABLE_STATES:
                    raise _field_error(
                        f"批次状态 {record.state} 不能继续修改。", fields=["state"]
                    )
                if record.revision != payload.expected_revision:
                    raise revision_conflict(record.revision)

                rows = self.imports.list_rows(conn, import_id)
                prior_decisions = {row.row_no: row.decision for row in rows}
                warnings = list(record.warnings)
                mapping_patched = False
                if payload.mapping is not None:
                    if record.source != "file":
                        raise _field_error(
                            "AI 候选批次没有表头映射，不能改映射。", fields=["mapping"]
                        )
                    headers = _headers_of_rows(rows)
                    resolved = import_rules.validate_mapping(payload.mapping, headers)
                    table = _table_from_rows(headers, rows)
                    derived = import_rules.derive_file_rows(
                        conn,
                        subject_id=record.subject_id,
                        table=table,
                        mapping=resolved,
                        points=self.points,
                    )
                    rebuilt = [
                        _with_decision(row, prior_decisions.get(row.row_no))
                        for row in derived.rows
                    ]
                    self.imports.replace_rows(conn, import_id, rebuilt)
                    for warning in derived.warnings:
                        if warning not in warnings:
                            warnings.append(warning)
                    record = self.imports.update_import(
                        conn,
                        import_id,
                        expected_revision=payload.expected_revision,
                        mapping=resolved,
                        batch_issues=derived.batch_issues,
                        warnings=warnings,
                    )
                    mapping_patched = True
                if payload.rows:
                    for item in payload.rows:
                        self.imports.update_row(
                            conn,
                            import_id,
                            item.row_no,
                            decision=item.decision,
                            base_revision=item.expected_revision,
                        )
                    if not mapping_patched:
                        record = self.imports.touch_import(conn, import_id)
                if not mapping_patched and not payload.rows:
                    raise _field_error(
                        "补丁至少要包含 mapping 或 rows 之一。", fields=["mapping", "rows"]
                    )
                rows = self.imports.list_rows(conn, import_id)
                versions = _base_versions(conn, rows, self.points)
        return self._import_view(record, rows, base_versions=versions)

    def confirm_import(
        self, import_id: str, payload: KnowledgeImportConfirmRequest
    ) -> KnowledgeImportConfirmResult:
        import_id = _text(import_id, field="importId")
        actions: dict[int, tuple[str, int | None]] = {}
        serialized: list[dict[str, Any]] = []
        for item in payload.actions or []:
            if item.row_no in actions:
                raise _field_error(
                    f"同一行在 actions 里出现多次：{item.row_no}。", fields=["actions"]
                )
            actions[item.row_no] = (item.decision, item.expected_revision)
            serialized.append(
                {
                    "rowNo": item.row_no,
                    "decision": item.decision,
                    "expectedRevision": item.expected_revision,
                }
            )
        serialized.sort(key=lambda item: item["rowNo"])
        command = make_command(
            operation="knowledge.import.confirm",
            submission_id=payload.submission_id,
            payload={
                "importId": import_id,
                "expectedRevision": payload.expected_revision,
                "actions": serialized,
            },
            owner_id=self.owner_id,
        )
        with self.coordinator.publication(operation="knowledge.import.confirm"):
            outcome = execute_command(
                catalog=self.catalog,
                command=command,
                expected_revision=None,
                apply=lambda conn: self._apply_confirm(
                    conn,
                    import_id=import_id,
                    expected_revision=payload.expected_revision,
                    actions=actions,
                ),
                table="knowledge_submissions",
            )
        result = dict(outcome.result)
        result["replayed"] = outcome.replayed
        return KnowledgeImportConfirmResult.model_validate(result)

    # ------------------------------------------------------------------ AI 候选

    async def create_suggestion_job(self, payload: KnowledgeSuggestionRequest) -> JobView:
        """建知识点候选任务（queued）并调度执行；``202`` 只代表接受任务。

        这一步是 async 的：冻结输入里的教材证据读取要在线程池里做，任务调度必须在
        事件循环线程上（``engine.schedule``）。模型调用发生在执行器里、事务之外。
        """
        if self.job_engine is None:
            raise AppError(
                "知识点 AI 候选未装配任务引擎（job_engine），无法创建任务；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if self.model_resolver is None:
            raise AppError(
                "知识点 AI 候选未装配模型解析器（model_resolver），无法调用聊天模型；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        subject_id = payload.subject_id.strip()
        profile_id = payload.model_profile_id.strip()
        # 学科按需登记（与人工建立一致），候选批次的外键因此始终有效
        await _threaded(self._ensure_subject, subject_id)
        allowed_points = await _threaded(self._active_point_ids, subject_id)
        materials = [
            suggestion_rules.material_entry(item.id, item.text) for item in payload.materials
        ]
        textbook: list[dict[str, Any]] = []
        for item in payload.textbook_evidence:
            if self.evidence is None:
                raise AppError(
                    "教材目录未装配，无法读取教材证据；请检查后端启动配置。",
                    code=TEXTBOOK_EVIDENCE_UNAVAILABLE,
                    status_code=503,
                    retryable=True,
                )
            evidence = await _threaded(
                self.evidence.read,
                document_revision_id=item.document_revision_id,
                char_start=item.char_start,
                char_end=item.char_end,
            )
            textbook.append(suggestion_rules.textbook_entry(evidence))
        if not materials and not textbook:
            raise AppError(
                "AI 候选至少需要一份证据（materials 或 textbookEvidence）。",
                code=KNOWLEDGE_SUGGESTION_NO_EVIDENCE,
                status_code=422,
            )
        total_chars = sum(len(item["text"]) for item in [*materials, *textbook])
        if total_chars > suggestion_rules.MAX_EVIDENCE_CHARS:
            raise _field_error(
                f"证据文本合计 {total_chars} 字，超过单次候选预算 "
                f"{suggestion_rules.MAX_EVIDENCE_CHARS} 字；请拆分后再试。",
                fields=["materials", "textbookEvidence"],
            )
        evidence_ids = [item["id"] for item in materials] + [item["id"] for item in textbook]
        frozen_input = {
            "contractVersion": suggestion_rules.SUGGESTION_CONTRACT_VERSION,
            "subjectId": subject_id,
            "modelProfileId": profile_id,
            "allowedKnowledgePointIds": allowed_points,
            "evidenceIds": evidence_ids,
            "materials": materials,
            "textbookEvidence": textbook,
            "instructions": payload.instructions or "",
        }
        model_snapshot = await self._freeze_model_snapshot(profile_id)
        store = self.job_engine.store("knowledge")
        record = await _threaded(
            store.create,
            kind="suggestion",
            frozen_input=frozen_input,
            model_snapshot=model_snapshot,
            owner_id=self.owner_id,
        )
        self.job_engine.schedule(
            "knowledge", record.job_id, self._suggestion_executor, uses_model=True
        )
        return record.view()

    def suggestion_job_view(self, job_id: str) -> JobView:
        """按 id 读取候选任务视图（供隔离测试与恢复入口复用）。"""
        if self.job_engine is None:
            raise AppError(
                "知识点 AI 候选未装配任务引擎（job_engine）。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        return self.job_engine.store("knowledge").get(job_id).view()

    # ------------------------------------------------------------------ 内部

    def _ensure_subject(self, subject_id: str) -> None:
        """学科按需登记（``INSERT OR IGNORE``，与人工建立知识点同一套语义）。

        AI 候选不因"学科还没有知识点"而拒绝：候选批次需要 ``subjects`` 外键，
        这里先幂等登记，已存在的学科名称与状态一律不改写。
        """
        with self.catalog.write_transaction() as conn:
            self.subjects.ensure_subject(conn, subject_id=subject_id, name=subject_id)

    def _active_point_ids(self, subject_id: str) -> list[str]:
        """候选允许引用的既有知识点集合（该学科 active 知识点）。"""
        with self.catalog.read_connection() as conn:
            return self.points.list_point_ids(conn, subject_id=subject_id, status="active")

    async def _freeze_model_snapshot(self, profile_id: str) -> dict[str, Any]:
        """冻结 ``profileId`` 与非敏感指纹；解析失败时指纹留空（执行器会失败并报可读原因）。"""
        snapshot: dict[str, Any] = {
            "profileId": profile_id,
            "fingerprint": "",
            "contractVersion": suggestion_rules.SUGGESTION_CONTRACT_VERSION,
        }
        if self.model_resolver is None:
            return snapshot
        try:
            handle = await _threaded(self.model_resolver, profile_id)
        except Exception:  # noqa: BLE001 - 配置失效留给执行器报稳定错误码
            return snapshot
        if isinstance(handle, ChatModelHandle):
            snapshot["fingerprint"] = suggestion_rules.model_fingerprint(
                model_id=handle.model_id,
                protocol=_protocol_value(handle.config.protocol),
                base_url=handle.config.baseUrl,
                api_format=handle.config.apiFormat or "",
            )
        return snapshot

    async def _resolve_for_job(self, profile_id: str) -> ChatModelHandle:
        if self.model_resolver is None:
            raise AppError(
                "知识点 AI 候选未装配模型解析器（model_resolver）。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if not profile_id:
            raise AppError(
                "该任务没有冻结模型配置，无法继续；请重新发起候选。",
                code="MODEL_PROFILE_NOT_FOUND",
                status_code=404,
            )
        try:
            handle = await _threaded(self.model_resolver, profile_id)
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - 未知解析故障按上游不可用处理
            raise AppError(
                "模型配置解析失败：请检查模型设置后重试。",
                code="UPSTREAM_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if not isinstance(handle, ChatModelHandle):
            raise AppError(
                "模型解析器返回的句柄不符合契约，已停止候选。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
            )
        return handle

    async def _suggestion_executor(self, frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
        """执行器：事务外解析模型并调用；返回 ``publish`` 在知识点库同一事务写批次。"""
        snapshot = frozen.model_snapshot if isinstance(frozen.model_snapshot, dict) else {}
        profile_id = str(snapshot.get("profileId") or frozen.input.get("modelProfileId") or "")
        handle = await self._resolve_for_job(profile_id)

        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=suggestion_rules.system_instruction(frozen.input)),
                LLMMessage(role="user", content=suggestion_rules.render_evidence(frozen.input)),
            ],
            maxOutputTokens=suggestion_rules.MAX_OUTPUT_TOKENS,
            params={},
        )
        response = await handle.provider.complete(handle.config, request)
        if response.finishReason == FINISH_LENGTH:
            raise AppError(
                "模型输出被截断（结束原因 length），候选批次未生成；"
                "请提高该模型的输出上限或缩小证据范围后重试。",
                code=KNOWLEDGE_SUGGESTION_TRUNCATED,
                status_code=422,
            )
        allowed_points = [str(item) for item in frozen.input.get("allowedKnowledgePointIds") or []]
        allowed_evidence = [str(item) for item in frozen.input.get("evidenceIds") or []]
        candidates, raw_items = suggestion_rules.parse_candidates(
            response.text,
            allowed_point_ids=allowed_points,
            allowed_evidence_ids=allowed_evidence,
        )
        if await ctx.cancellation_requested():
            # 取消优先于迟到结果：不登记资产、不发布；引擎随后置 cancelled
            return JobOutcome(result={"cancelled": True, "candidateCount": 0}, publish=None)

        # 事务外：模型原始输出登记为教学库受管资产（跨库逻辑引用，见任务卡 §8.3）
        original = json.dumps(
            {
                "jobId": frozen.job_id,
                "model": {"profileId": profile_id, "fingerprint": snapshot.get("fingerprint", "")},
                "candidates": raw_items,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        original_name = f"knowledge-suggestion-{frozen.job_id}.json"
        stored = await _threaded(
            self.assets.store_original,
            original,
            media_type="application/json",
            original_name=original_name,
        )
        asset = await _threaded(
            self.file_assets.create,
            kind="attachment",
            blob_key=stored.blob_key,
            sha256=stored.sha256,
            media_type="application/json",
            byte_size=stored.byte_size,
            original_name=original_name,
        )

        subject_id = str(frozen.input.get("subjectId") or "")
        sources = [
            import_rules.AiRowSource(
                candidate=candidate,
                raw=raw,
                issues=suggestion_rules.hint_issues(candidate, raw),
            )
            for candidate, raw in zip(candidates, raw_items, strict=True)
        ]
        import_id = uuid.uuid4().hex

        def publish(conn: Any) -> None:
            """与任务 succeeded 同一事务：写 AI 待确认批次与候选行（不写正式表）。"""
            derived = import_rules.derive_ai_rows(
                conn, subject_id=subject_id, sources=sources, points=self.points
            )
            self.subjects.ensure_subject(conn, subject_id=subject_id, name=subject_id)
            self.imports.create_import(
                conn,
                source="ai",
                subject_id=subject_id,
                file_asset_id=asset.asset_id,
                mapping={},
                batch_issues=[],
                warnings=[
                    "AI 候选批次：候选尚未入库，请逐行校对后用确认接口建账。",
                    *derived.warnings,
                ],
                rows=derived.rows,
                state="reviewing",
                import_id=import_id,
                owner_id=self.owner_id,
            )

        return JobOutcome(
            result={"importId": import_id, "candidateCount": len(candidates)},
            publish=publish,
        )

    def _apply_confirm(
        self,
        conn: Any,
        *,
        import_id: str,
        expected_revision: int,
        actions: dict[int, tuple[str, int | None]],
    ) -> dict[str, Any]:
        """确认入库的 apply：整批在调用方事务里，任一步失败整体回滚。"""
        record = self.imports.get_import(conn, import_id)
        if record is None:
            raise not_found("知识点导入不存在。", code="KNOWLEDGE_IMPORT_NOT_FOUND")
        if record.state == "confirmed":
            raise _conflict("该导入批次已确认入库。", code=KNOWLEDGE_IMPORT_CONFIRMED)
        if record.state not in CONFIRMABLE_STATES:
            raise AppError(
                f"批次状态 {record.state} 不能确认入库。",
                code="INVALID_REQUEST",
                status_code=422,
                details=error_details(fields=["state"]),
            )
        if record.revision != expected_revision:
            raise revision_conflict(record.revision)
        rows = self.imports.list_rows(conn, import_id)
        if not rows:
            raise _issues_error(
                "导入批次没有任何行，无法确认。",
                code=KNOWLEDGE_ROW_INVALID,
                issues=[
                    ErrorIssue(code="KNOWLEDGE_ROW_INVALID", message="批次没有任何可入库的行。")
                ],
            )
        plan, blocking, request_issues = import_rules.plan_confirm(
            conn,
            subject_id=record.subject_id,
            rows=rows,
            actions=actions,
            points=self.points,
        )
        if request_issues:
            raise _issues_error(
                "导入批次还有行没有最终动作，未写入任何知识点。",
                code=KNOWLEDGE_ROW_INVALID,
                issues=request_issues,
            )
        if blocking:
            raise _issues_error(
                "导入批次存在阻断问题，未写入任何知识点。",
                code=KNOWLEDGE_IMPORT_BLOCKING_ISSUES,
                issues=blocking,
            )
        created: list[dict[str, Any]] = []
        updated: list[dict[str, Any]] = []
        ignored: list[int] = []
        created_by_code: dict[str, str] = {}
        for entry in plan:
            if entry.action == "ignore":
                ignored.append(entry.row_no)
                continue
            if entry.action == "create":
                parent_id = entry.parent_point_id
                if entry.parent_code:
                    parent_id = created_by_code.get(entry.parent_code, parent_id)
                if entry.parent_code and parent_id is None:
                    raise _issue_error(
                        f"父级编码 {entry.parent_code} 无法解析，整批未写入。",
                        code=KNOWLEDGE_PARENT_INVALID,
                        issue=ErrorIssue(
                            row=entry.row_no,
                            field="parentCode",
                            code=KNOWLEDGE_PARENT_INVALID,
                            message="父级编码无法解析（父节点未被创建）。",
                        ),
                    )
                point = self.points.create_point(
                    conn,
                    subject_id=record.subject_id,
                    code=entry.code,
                    name=entry.name,
                    description=entry.description,
                    parent_id=parent_id,
                    aliases=entry.aliases,
                )
                created_by_code[entry.code] = point.point_id
                created.append(_applied_dict(entry.row_no, point))
                continue
            point = self.points.update_point(
                conn,
                entry.target_point_id or "",
                expected_revision=(
                    entry.expected_revision if entry.expected_revision is not None else 0
                ),
                name=entry.name,
                description=entry.description or None,
                aliases=list(entry.aliases) or None,
            )
            updated.append(_applied_dict(entry.row_no, point))
        confirmed = self.imports.mark_confirmed(conn, import_id)
        return KnowledgeImportConfirmResult.model_validate(
            {
                "importId": import_id,
                "state": confirmed.state,
                "created": created,
                "updated": updated,
                "ignored": ignored,
                "replayed": False,
            }
        ).model_dump(by_alias=True, mode="json")

    def _import_view(
        self,
        record: ImportRecord,
        rows: Sequence[ImportRowRecord],
        *,
        base_versions: dict[int, int | None] | None = None,
    ) -> KnowledgeImportView:
        asset = self.file_assets.get(record.file_asset_id)
        if asset is None:
            raise AppError(
                "知识点导入缺少受管文件登记（跨库引用失效）。",
                code="KNOWLEDGE_IMPORT_ASSET_MISSING",
                status_code=500,
            )
        versions = base_versions or {}
        payload = _summary_dict(
            record,
            row_count=len(rows),
            blocking_issue_count=_blocking_count(
                [str(issue.get("code", "")) for issue in record.batch_issues]
                + [str(issue.get("code", "")) for row in rows for issue in row.issues]
            ),
        )
        # 详情视图不含 rowCount/blockingIssueCount（那是 KnowledgeImportSummary 的字段）
        payload.pop("rowCount", None)
        payload.pop("blockingIssueCount", None)
        payload.update(
            {
                "fileAsset": asset.ref().model_dump(by_alias=True, mode="json"),
                "headers": _headers_of_rows(rows),
                "mapping": dict(record.mapping),
                "warnings": list(record.warnings),
                "issues": [_issue_dict(item) for item in record.batch_issues],
                "rows": [
                    _row_dict(row, base_version=versions.get(row.row_no)) for row in rows
                ],
            }
        )
        return KnowledgeImportView.model_validate(payload)


# --------------------------------------------------------------------------- 装配


def build_knowledge_service(
    catalog: KnowledgeCatalog,
    *,
    asset_store: AssetStore,
    file_assets: Any,
    evidence: TextbookEvidenceReader | None = None,
    coordinator: PublicationCoordinator,
    model_resolver: ChatModelResolver | None = None,
    job_engine: JobEngine | None = None,
) -> KnowledgeService:
    """装配入口（CTRL 在 ``main.py`` 调用）。

    ``evidence`` 允许为 ``None``（隔离环境/教材目录未装配）：此时任何 ``textbookEvidence``
    请求 503 ``TEXTBOOK_EVIDENCE_UNAVAILABLE``，只给 ``materials`` 的 AI 任务仍可用。
    ``model_resolver``/``job_engine`` 为 ``None`` 时 AI 候选 503，不返回假成功。
    """
    return KnowledgeService(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        evidence=evidence,
        coordinator=coordinator,
        model_resolver=model_resolver,
        job_engine=job_engine,
    )


# --------------------------------------------------------------------------- 视图构造


def _point_dict(record: PointRecord) -> dict[str, Any]:
    return {
        "id": record.point_id,
        "subjectId": record.subject_id,
        "code": record.code,
        "name": record.name,
        "description": record.description,
        "parentId": record.parent_id,
        "parentCode": record.parent_code,
        "sortOrder": record.sort_order,
        "status": record.status,
        "revision": record.revision,
        "revisionId": record.revision_id,
        "version": record.version,
        "aliases": list(record.aliases),
        "createdAt": record.created_at,
    }


def _point_view(record: PointRecord) -> KnowledgePointView:
    return KnowledgePointView.model_validate(_point_dict(record))


def _link_dict(record: LinkRecord) -> dict[str, Any]:
    return {
        "linkId": record.link_id,
        "knowledgePointId": record.knowledge_point_id,
        "knowledgeRevisionId": record.knowledge_revision_id,
        "documentRevisionId": record.document_revision_id,
        "charStart": record.char_start,
        "charEnd": record.char_end,
        "titleSnapshot": record.title_snapshot,
        "locatorHash": record.locator_hash,
        "source": record.source,
        "createdAt": record.created_at,
    }


def _link_view(record: LinkRecord) -> TextbookLinkView:
    return TextbookLinkView.model_validate(_link_dict(record))


def _issue_dict(issue: Any) -> dict[str, Any]:
    if isinstance(issue, ErrorIssue):
        return issue.model_dump(exclude_none=True)
    return dict(issue)


def _row_dict(record: ImportRowRecord, *, base_version: int | None = None) -> dict[str, Any]:
    return {
        "rowNo": record.row_no,
        "name": record.name,
        "code": record.code,
        "parentCode": record.parent_code,
        "description": record.description,
        "aliases": list(record.aliases),
        "targetKnowledgePointId": record.target_knowledge_point_id,
        "baseRevision": record.base_revision,
        "baseVersion": base_version,
        "decision": record.decision,
        "issues": [_issue_dict(item) for item in record.issues],
    }


def _summary_dict(
    record: ImportRecord, *, row_count: int, blocking_issue_count: int
) -> dict[str, Any]:
    return {
        "importId": record.import_id,
        "source": record.source,
        "subjectId": record.subject_id,
        "state": record.state,
        "revision": record.revision,
        "rowCount": row_count,
        "blockingIssueCount": blocking_issue_count,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def _applied_dict(row_no: int, point: PointRecord) -> dict[str, Any]:
    return {
        "rowNo": row_no,
        "knowledgePointId": point.point_id,
        "revisionId": point.revision_id,
        "version": point.version,
    }


# --------------------------------------------------------------------------- 内部工具


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _field_error(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _validate_page(*, offset: int, limit: int) -> None:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _field_error("offset 必须是不小于 0 的整数。", fields=["offset"])
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise _field_error("limit 必须是不小于 1 的整数。", fields=["limit"])
    if limit > MAX_LIST_LIMIT:
        raise _field_error(f"limit 不能超过 {MAX_LIST_LIMIT}。", fields=["limit"])


def _protocol_value(protocol: Any) -> str:
    value = getattr(protocol, "value", None)
    return str(value if value is not None else protocol or "")


def _resolve_parent(
    conn: Any,
    *,
    subject_id: str,
    parent_id: str | None,
    parent_code: str | None,
    points: KnowledgePointRepository,
    point_id: str | None = None,
) -> str | None:
    """父节点解析：同库同科、已存在、非自指、无环。

    错误一律带 ``details.issues``，``field`` 取**实际入参字段**（``parentId`` 或
    ``parentCode``）：不存在/跨学科/归档/自指 → 422 ``KNOWLEDGE_PARENT_INVALID``（归档为
    409 ``KNOWLEDGE_ARCHIVED``）；``point_id`` 给出时（更新/改父）先预检成环 →
    422 ``KNOWLEDGE_CYCLE``。DB 触发器仍是兜底（见 ``translate_integrity_error``）。
    """
    field = "parentId" if parent_id is not None else "parentCode"
    resolved: str | None = None
    if parent_id is not None:
        parent = points.get_point(conn, _text(parent_id, field="parentId"))
        if parent is None:
            raise _issue_error(
                "父节点不存在。",
                code=KNOWLEDGE_PARENT_INVALID,
                issue=ErrorIssue(
                    field="parentId",
                    code=KNOWLEDGE_PARENT_INVALID,
                    message="parentId 指向的知识点不存在。",
                ),
            )
        if parent.subject_id != subject_id:
            raise _issue_error(
                "父节点必须与知识点同学科。",
                code=KNOWLEDGE_CROSS_SUBJECT_PARENT,
                issue=ErrorIssue(
                    field="parentId",
                    code=KNOWLEDGE_CROSS_SUBJECT_PARENT,
                    message="parentId 指向的知识点属于其他学科。",
                ),
            )
        if parent.status == "archived":
            raise _issue_error(
                "父节点已归档：归档保留历史引用，但不能作为新引用的父节点。",
                code=KNOWLEDGE_ARCHIVED,
                issue=ErrorIssue(
                    field="parentId",
                    code=KNOWLEDGE_ARCHIVED,
                    message="parentId 指向的知识点已归档，请先恢复。",
                ),
                status_code=409,
            )
        resolved = parent.point_id
    elif parent_code is not None:
        code = _text(parent_code, field="parentCode")
        parent = points.get_by_code(conn, subject_id=subject_id, code=code)
        if parent is None:
            raise _issue_error(
                f"父级编码「{code}」在本学科内不存在。",
                code=KNOWLEDGE_PARENT_INVALID,
                issue=ErrorIssue(
                    field="parentCode",
                    code=KNOWLEDGE_PARENT_INVALID,
                    message=f"parentCode「{code}」在本学科内不存在。",
                ),
            )
        if parent.status == "archived":
            raise _issue_error(
                "父节点已归档：归档保留历史引用，但不能作为新引用的父节点。",
                code=KNOWLEDGE_ARCHIVED,
                issue=ErrorIssue(
                    field="parentCode",
                    code=KNOWLEDGE_ARCHIVED,
                    message=f"parentCode「{code}」对应的知识点已归档，请先恢复。",
                ),
                status_code=409,
            )
        resolved = parent.point_id
    else:
        return None

    if point_id is not None:
        if resolved == point_id:
            raise _issue_error(
                "父节点非法：知识点不能把自己作为父节点。",
                code=KNOWLEDGE_PARENT_INVALID,
                issue=ErrorIssue(
                    field=field,
                    code=KNOWLEDGE_PARENT_INVALID,
                    message=f"{field} 指向本知识点自身，不能作为父节点。",
                ),
            )
        if points.would_create_cycle(conn, point_id=point_id, parent_id=resolved):
            raise _issue_error(
                "父节点变更会形成环（新父节点是本节点的后代）。",
                code=KNOWLEDGE_CYCLE,
                issue=ErrorIssue(
                    field=field,
                    code=KNOWLEDGE_CYCLE,
                    message=f"{field} 指向的父节点是本知识点的后代，会形成环。",
                ),
            )
    return resolved


def _log_alias_ambiguity(
    conn: Any,
    *,
    subject_id: str,
    aliases: Sequence[str],
    exclude_point_id: str,
    points: KnowledgePointRepository,
) -> None:
    """跨知识点同名/同别名只记 warning，绝不自动合并（B1 任务卡 §2.3）。"""
    for alias in aliases:
        normalized = normalize_alias(alias)
        others = points.points_with_alias(
            conn,
            subject_id=subject_id,
            normalized_alias=normalized,
            exclude_point_id=exclude_point_id,
        )
        if others:
            logger.warning(
                "知识点别名歧义（只提示，不合并）：别名「%s」在学科 %s 内已指向 %s",
                alias,
                subject_id,
                ", ".join(others[:5]),
            )


def _blocking_count(codes: Sequence[str]) -> int:
    return sum(1 for code in codes if code in import_rules.BLOCKING_ISSUE_CODES)


def _base_versions(
    conn: Any, rows: Sequence[ImportRowRecord], points: KnowledgePointRepository
) -> dict[int, int | None]:
    """预览冻结的基线版本号：按 base_revision_id 读修订 version（不可变行）。"""
    versions: dict[int, int | None] = {}
    for row in rows:
        versions[row.row_no] = (
            points.version_of_revision(conn, row.base_revision_id)
            if row.base_revision_id
            else None
        )
    return versions


def _headers_of_rows(rows: Sequence[ImportRowRecord]) -> list[str]:
    headers: list[str] = []
    for row in rows:
        for header in row.raw_cells:
            if header not in headers:
                headers.append(header)
    return headers


def _table_from_rows(headers: Sequence[str], rows: Sequence[ImportRowRecord]) -> SheetTable:
    body: list[list[str]] = []
    for row in rows:
        body.append([str(row.raw_cells.get(header, "")) for header in headers])
    return SheetTable(name="preview", headers=list(headers), rows=body)


def _with_decision(row: ImportRowInput, decision: str | None) -> ImportRowInput:
    if decision is None:
        return row
    return replace(row, decision=decision)


__all__ = [
    "DEFAULT_LIST_LIMIT",
    "MAX_LIST_LIMIT",
    "MAX_UPLOAD_BYTES",
    "KnowledgeService",
    "build_knowledge_service",
]
