"""知识点服务门面（TEACHING-LOOP B1 / T20）。

冻结方法名（路由与测试按此对接）：``list_points`` / ``create_point`` / ``get_point`` /
``update_point`` / ``set_archived`` / ``list_textbook_links`` / ``add_textbook_link`` /
``delete_textbook_link`` / ``create_file_import`` / ``get_import`` / ``list_imports`` /
``patch_import`` / ``confirm_import`` / ``discard_import`` / ``create_suggestion_job``。

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
from collections.abc import Mapping
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
    KNOWLEDGE_POINT_IN_USE,
    KNOWLEDGE_ROW_INVALID,
    KNOWLEDGE_SUGGESTION_NO_EVIDENCE,
    KNOWLEDGE_SUGGESTION_TRUNCATED,
    TEXTBOOK_EVIDENCE_UNAVAILABLE,
    KnowledgeExtractionPreview,
    KnowledgeExtractionRequest,
    KnowledgeImportConfirmRequest,
    KnowledgeImportConfirmResult,
    KnowledgeImportDiscardRequest,
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
from app.services.knowledge import extraction as extraction_rules
from app.services.knowledge import imports as import_rules
from app.services.knowledge import suggestions as suggestion_rules
from app.services.knowledge.evidence import TextbookEvidenceReader
from app.services.knowledge.references import in_use_error
from app.services.model_runtime import (
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    ChatModelHandle,
    fingerprint_of_handle,
    resolve_frozen_model,
)
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
#: 知识点列表范围（任务②）：缺省不过滤；taught = 任教范围内有教材依据
POINT_SCOPES = frozenset({"taught", "subject"})

ChatModelResolver = Callable[..., ChatModelHandle]


#: 缺可核对指纹 / 配置已漂移的可读文案（与 ``model_runtime.resolve_frozen_model``
#: 和题库服务同一口径：错误码是契约，文案只影响可读性）
MODEL_FINGERPRINT_MISSING_MESSAGE = (
    "任务缺少可核对的冻结模型指纹；请重新发起任务（旧任务不自动重放）。"
)
MODEL_CONFIG_DRIFT_MESSAGE = (
    "模型配置自任务创建后已变化（同 profile 的模型/地址/格式与冻结指纹不一致）；"
    "本次调用已停止，请重新发起任务。"
)


def _build_frozen_model_resolver(
    repo: Any | None, secrets: Any | None, auth_service: Any | None
):
    """共享 ``resolve_frozen_model`` 的注入适配（仓储 + 凭证齐备时返回可调用对象）。

    与题库/原卷同一注入形参名（``model_config_repo`` / ``secret_store`` /
    ``model_auth_service``）；缺失时服务用注入的 ``model_resolver`` 解析后按
    ``fingerprint_of_handle`` 核对（判定与错误码一致）。
    """
    if repo is None or secrets is None:
        return None

    def resolve(snapshot: Mapping[str, Any]) -> ChatModelHandle:
        return resolve_frozen_model(repo, secrets, snapshot, auth_service=auth_service)

    return resolve


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
        model_config_repo: Any | None = None,
        secret_store: Any | None = None,
        model_auth_service: Any | None = None,
        reference_checker: Any | None = None,
        scope_reader: Any | None = None,
    ) -> None:
        self.catalog = catalog
        self.assets = asset_store
        self.file_assets = file_assets
        self.evidence = evidence
        self.coordinator = coordinator
        self.model_resolver = model_resolver
        self.job_engine = job_engine
        self.owner_id = owner_id
        # RV04（知识点侧）：仓储 + 凭证齐备时走共享 resolve_frozen_model；否则用注入的
        # resolver 解析后按同一指纹算法核对（见 _resolve_frozen_handle）
        self._frozen_model_resolver = _build_frozen_model_resolver(
            model_config_repo, secret_store, model_auth_service
        )
        self.subjects = SubjectRepository()
        self.points = KnowledgePointRepository()
        self.links = TextbookLinkRepository()
        self.imports = KnowledgeImportRepository()
        # 任务①：跨库引用守卫端口（缺失时彻底删除 503，不静默放行）
        self.reference_checker = reference_checker
        # 任务②：教材范围查询端口（缺失时带 scope=taught 的调用 503，旧调用不变）
        self.scope_reader = scope_reader

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
        scope: str | None = None,
        grade_id: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> KnowledgePointList:
        _validate_page(offset=offset, limit=limit)
        scope_key = None
        if scope is not None:
            scope_key = _text(scope, field="scope")
            if scope_key not in POINT_SCOPES:
                raise _field_error(
                    f"scope 必须是 {sorted(POINT_SCOPES)} 之一。", fields=["scope"]
                )
        # 任务②：scope=taught 先在教材目录解析任教范围（端口缺失 503 / 未就绪 409），
        # 再把命中的知识点 id 集合下推给仓储；不带 scope 的旧调用不走这条路。
        scope_point_ids: set[str] | None = None
        if scope_key == "taught":
            scope_point_ids = self._taught_scope_point_ids()
        grade_point_ids: set[str] | None = None
        if grade_id is not None:
            grade_id = _text(grade_id, field="gradeId")
            grade_point_ids = self._grade_hit_point_ids(grade_id)
        with self.catalog.read_connection() as conn:
            items, total = self.points.list_points(
                conn,
                subject_id=subject_id,
                status=status,
                parent_id=parent_id,
                q=q,
                scope_point_ids=None if scope_point_ids is None else scope_point_ids,
                grade_point_ids=None if grade_point_ids is None else grade_point_ids,
                offset=offset,
                limit=limit,
            )
            # 视图补 gradeIds：按本页知识点批量取教材依据修订，再经教材目录批量映射
            grade_ids_map = self._grade_ids_for_page(conn, [record.point_id for record in items])
        return KnowledgePointList.model_validate(
            {
                "items": [
                    _point_dict(record, grade_ids=grade_ids_map.get(record.point_id, []))
                    for record in items
                ],
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )

    def _require_scope_reader(self) -> Any:
        """任务②：范围端口缺失 → 503（带 scope 的调用不可用，不静默回退全部）。"""
        if self.scope_reader is None:
            raise AppError(
                "知识点教材范围查询未装配（scope_reader），无法按任教范围筛选；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        return self.scope_reader

    def _taught_scope_point_ids(self) -> set[str]:
        """任教范围命中的知识点 id 集合：范围修订 ∩ textbook_knowledge_links。"""
        reader = self._require_scope_reader()
        snapshot = reader.resolve_taught_scope()
        with self.catalog.read_connection() as conn:
            return self.points.point_ids_with_revision_links(
                conn, document_revision_ids=list(snapshot.revision_ids)
            )

    def _grade_hit_point_ids(self, grade_id: str) -> set[str]:
        """年级命中的知识点 id 集合：教材依据修订的年级集合里包含该年级。"""
        reader = self._require_scope_reader()
        with self.catalog.read_connection() as conn:
            revisions_by_point = self.points.document_revisions_by_point(
                conn, point_ids=self.points.list_point_ids(conn)
            )
        all_revisions: set[str] = set()
        for revision_ids in revisions_by_point.values():
            all_revisions.update(revision_ids)
        if not all_revisions:
            return set()
        grade_ids_by_revision = reader.grade_ids_of_revisions(tuple(sorted(all_revisions)))
        hits: set[str] = set()
        for point_id, revision_ids in revisions_by_point.items():
            for revision_id in revision_ids:
                if grade_id in grade_ids_by_revision.get(revision_id, ()):
                    hits.add(point_id)
                    break
        return hits

    def _grade_ids_for_page(
        self, conn: Any, point_ids: Sequence[str]
    ) -> dict[str, list[str]]:
        """本页知识点的 ``gradeIds`` 视图（批量两步：本库修订 → 教材目录年级）。"""
        if not point_ids:
            return {}
        revisions_by_point = self.points.document_revisions_by_point(conn, point_ids=point_ids)
        if not revisions_by_point:
            return {}
        all_revisions: set[str] = set()
        for revision_ids in revisions_by_point.values():
            all_revisions.update(revision_ids)
        grade_ids_by_revision: dict[str, Sequence[str]] = {}
        if self.scope_reader is not None:
            try:
                grade_ids_by_revision = self.scope_reader.grade_ids_of_revisions(
                    tuple(sorted(all_revisions))
                )
            except AppError:
                # 视图补充字段读取失败不改变列表语义：gradeIds 留空（不伪造年级）
                grade_ids_by_revision = {}
        return self.points.grade_ids_from_revisions(
            revisions_by_point, grade_ids_by_revision
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

    def delete_point(self, point_id: str, payload: KnowledgePointRevisionRequest) -> None:
        """彻底删除（任务①）：跨库守卫 → 同一写事务删除别名/修订/身份行。

        - 守卫：任一库仍有引用 → 409 ``KNOWLEDGE_POINT_IN_USE`` + ``details.counts``
          逐项计数；守卫端口缺失 → 503 ``SERVICE_UNAVAILABLE``（不静默放行）；
        - 本学科仍有子节点 → 409 ``KNOWLEDGE_POINT_IN_USE``（子节点引用父节点，
          先处理子节点）；404 ``KNOWLEDGE_POINT_NOT_FOUND`` / 409 ``REVISION_CONFLICT``
          语义与既有更新一致；
        - 引用计数在发布协调器锁内、删除写事务之前完成（锁内只做数据库读取）。
        """
        point_id = _text(point_id, field="pointId")
        with self.coordinator.publication(operation="knowledge.delete"):
            # ① 跨库引用守卫（端口缺失 503，绝不静默放行）
            if self.reference_checker is None:
                raise AppError(
                    "知识点引用检查未装配（reference_checker），无法彻底删除；"
                    "请检查后端启动配置。",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                )
            # ② 本库前置校验：存在 / 子节点（都在守卫计数之前给出可定位错误）
            with self.catalog.read_connection() as conn:
                current = self.points.require_point(conn, point_id)
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM knowledge_points WHERE parent_id = ?",
                    (point_id,),
                ).fetchone()
                child_count = int(row["total"]) if row is not None else 0
                if child_count:
                    raise _conflict(
                        f"该知识点还有 {child_count} 个子节点；先删除或移动子节点。",
                        code=KNOWLEDGE_POINT_IN_USE,
                    )
            counts = self.reference_checker.count_references(point_id)
            if counts.total:
                raise in_use_error(counts)
            # ③ 同一写事务删除：别名 → 修订 → 身份（乐观锁在仓储删除方法内核对）
            with self.catalog.write_transaction() as conn:
                self.points.delete_point(
                    conn, point_id, expected_revision=payload.expected_revision
                )
        return None

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
            # 视图补 uploadedFileName：按本页批次批量取教学库受管文件（不做 N+1）
            asset_ids = [record.file_asset_id for record in records]
            asset_names = {
                asset_id: _asset_original_name(asset)
                for asset_id, asset in (self.file_assets.get_many(asset_ids).items())
            }
            for record in records:
                items.append(
                    _summary_dict(
                        record,
                        row_count=self.imports.count_rows(conn, record.import_id),
                        blocking_issue_count=_blocking_count(
                            self.imports.issue_codes(conn, record.import_id)
                        ),
                        uploaded_file_name=asset_names.get(record.file_asset_id),
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

    def discard_import(
        self, import_id: str, payload: KnowledgeImportDiscardRequest
    ) -> KnowledgeImportView:
        """放弃未确认批次（误上传清理）：状态置 ``cancelled``，记录/文件/预览行保留。

        已确认批次不可放弃（已入库的知识点与历史不动）；重复放弃按幂等返回当前
        记录，不再递增 revision。``cancelled`` 不在 ``EDITABLE_STATES`` /
        ``CONFIRMABLE_STATES`` 内，放弃后不能再 patch/confirm。
        """
        import_id = _text(import_id, field="importId")
        with self.coordinator.publication(operation="knowledge.import.discard"):
            with self.catalog.write_transaction() as conn:
                record = self.imports.require_import(conn, import_id)
                if record.state == "confirmed":
                    raise _conflict(
                        "该导入批次已确认入库，不能放弃；已写入的知识点保留。",
                        code=KNOWLEDGE_IMPORT_CONFIRMED,
                    )
                if record.revision != payload.expected_revision:
                    raise revision_conflict(record.revision)
                record = self.imports.mark_cancelled(conn, import_id)
                rows = self.imports.list_rows(conn, import_id)
                versions = _base_versions(conn, rows, self.points)
        return self._import_view(record, rows, base_versions=versions)

    # ------------------------------------------------------------------ 提取（任务③）

    def extraction_preview(self, subject_id: str) -> KnowledgeExtractionPreview:
        """预览某学科全部已入库教材的提取清单（只读；未就绪书册带 reason）。"""
        if self.evidence is None:
            raise AppError(
                "教材目录未装配，无法预览提取来源。",
                code=TEXTBOOK_EVIDENCE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        return extraction_rules.build_preview(
            self.evidence._catalog, subject_id=_text(subject_id, field="subjectId")
        )

    def catalog_of_evidence(self) -> Any:
        """教材目录（经 evidence reader 注入的 catalog）；缺失时 503。"""
        if self.evidence is None:
            raise AppError(
                "教材目录未装配，无法进行教材提取。",
                code=TEXTBOOK_EVIDENCE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        return self.evidence._catalog

    async def create_extraction_jobs(
        self, payload: KnowledgeExtractionRequest
    ) -> list[JobView]:
        """提取任务受理（202）：每个书册一个 AI 候选任务；未就绪书册 409 逐册列出。

        - ``documentIds`` 缺省 = 该学科全部就绪书册；指定时仅这些；
        - 证据 = 该书册正文 chunk 区间（region="body"，经既有 evidence reader 核验），
          复用既有 AI 候选链（冻结输入、模型指纹、执行器、``source="ai"`` 批次）；
        - 候选只进待确认批次，绝不直接写正式表；
        - 任何书册都没有可用证据（无正文 chunk）→ 422（不建空任务）。
        """
        if self.job_engine is None:
            raise AppError(
                "知识点提取未装配任务引擎（job_engine），无法创建任务；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if self.model_resolver is None:
            raise AppError(
                "知识点提取未装配模型解析器（model_resolver），无法调用聊天模型；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        catalog = self.catalog_of_evidence()
        subject_id = _text(payload.subject_id, field="subjectId")
        profile_id = _text(payload.model_profile_id, field="modelProfileId")
        submission_id = _text(payload.submission_id, field="submissionId")
        # 受理校验（在教材目录里逐册核验；未就绪 409 逐册列出，不部分受理）
        targets = extraction_rules.resolve_target_documents(
            catalog, subject_id=subject_id, document_ids=payload.document_ids
        )
        if not targets:
            raise _field_error("该学科没有就绪的教材，无法发起提取。", fields=["subjectId"])
        # 学科按需登记（与人工建立一致）
        await _threaded(self._ensure_subject, subject_id)
        allowed_points = await _threaded(self._active_point_ids, subject_id)
        model_snapshot = await self._freeze_model_snapshot(profile_id)
        views: list[JobView] = []
        for entry in targets:
            revision = catalog.get_revision(entry.revision_id)  # 受理已核验非空
            ranges = extraction_rules.collect_document_evidence(
                catalog, entry=entry, revision=revision
            )
            if not ranges:
                raise _field_error(
                    f"教材「{entry.title}」没有可提取的正文分块，无法发起提取。",
                    fields=["documentIds"],
                )
            # 逐区间经既有 evidence reader 读取并冻结（标题/文本/sha256，预算外 422）
            textbook: list[dict[str, Any]] = []
            extraction_evidence: list[dict[str, Any]] = []
            for item in ranges:
                evidence = await _threaded(
                    self.evidence.read,
                    document_revision_id=item.document_revision_id,
                    char_start=item.char_start,
                    char_end=item.char_end,
                )
                textbook.append(suggestion_rules.textbook_entry(evidence))
                extraction_evidence.append(
                    {
                        "documentRevisionId": evidence.document_revision_id,
                        "charStart": evidence.char_start,
                        "charEnd": evidence.char_end,
                        "title": evidence.title,
                    }
                )
            total_chars = sum(len(item["text"]) for item in textbook)
            if total_chars > suggestion_rules.MAX_EVIDENCE_CHARS:
                raise _field_error(
                    f"教材「{entry.title}」的正文证据合计 {total_chars} 字，超过单次候选预算 "
                    f"{suggestion_rules.MAX_EVIDENCE_CHARS} 字；请缩小提取范围后重试。",
                    fields=["documentIds"],
                )
            frozen_input = {
                "contractVersion": suggestion_rules.SUGGESTION_CONTRACT_VERSION,
                "subjectId": subject_id,
                "modelProfileId": profile_id,
                "allowedKnowledgePointIds": allowed_points,
                "evidenceIds": [item["id"] for item in textbook],
                "materials": [],
                "textbookEvidence": textbook,
                "instructions": "",
                # 提取任务专用：候选行冻结证据坐标（确认后自动建教材依据用）
                "extraction": {
                    "submissionId": submission_id,
                    "documentId": entry.document_id,
                    "documentTitle": entry.title,
                    "gradeIds": list(entry.grade_ids),
                },
            }
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
            views.append(record.view())
        return views

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

    def register_job_executors(self, registry: Any) -> None:
        """把知识点 AI 候选执行器注册进公共注册表（B3/G0 · B2-RV01）。

        公共 ``POST /workflow-jobs/{id}/retry`` 经此调度；factory 只依赖任务行
        （``frozen_input`` / ``model_snapshot``），重试**不重新冻结**输入与指纹，
        执行体与首次调度完全同一份（``_suggestion_executor``）。未注册类型保持
        ``queued``，用户可再次 retry（不伪造成功）。
        """
        registry.register(
            "knowledge",
            "suggestion",
            uses_model=True,
            factory=lambda _record: self._suggestion_executor,
        )

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
            snapshot["fingerprint"] = fingerprint_of_handle(handle)
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

    async def _resolve_frozen_handle(self, snapshot: Any) -> ChatModelHandle:
        """解析候选任务的模型并核对**冻结指纹**（B3/G0 v2 · B2-RV04 知识点侧）。

        与题库服务同一口径：缺指纹 422 ``MODEL_FINGERPRINT_MISSING``、漂移 409
        ``MODEL_CONFIG_DRIFT``，都在任何模型调用**之前**判定（零上游请求、零候选批次）。

        - 注入仓储 + 凭证时直接走共享 ``resolve_frozen_model``（唯一实现）；
        - 只注入 ``model_resolver`` 时先解析、再核对：解析失败保留既有可读错误码
          （``MODEL_PROFILE_NOT_FOUND`` / ``MODEL_NOT_CONFIGURED`` /
          ``UPSTREAM_UNAVAILABLE``），解析成功后再比对 ``fingerprint_of_handle``；
          快照没有可核对指纹（创建时解析就失败的行）→ 422 ``MODEL_FINGERPRINT_MISSING``，
          不静默放行；用户按可读错误重新发起候选即可。
        """
        payload = snapshot if isinstance(snapshot, Mapping) else {}
        profile_id = str(
            payload.get("profileId") or payload.get("modelProfileId") or ""
        ).strip()
        fingerprint = str(
            payload.get("fingerprint") or payload.get("modelFingerprint") or ""
        ).strip()
        if self._frozen_model_resolver is not None:
            # 共享实现（唯一口径）：缺指纹 422、漂移 409，都在任何模型调用之前
            return await _threaded(
                self._frozen_model_resolver,
                {"profileId": profile_id, "fingerprint": fingerprint},
            )
        handle = await self._resolve_for_job(profile_id)
        if not fingerprint:
            raise AppError(
                MODEL_FINGERPRINT_MISSING_MESSAGE,
                code=MODEL_FINGERPRINT_MISSING,
                status_code=422,
            )
        if fingerprint_of_handle(handle) != fingerprint:
            raise AppError(
                MODEL_CONFIG_DRIFT_MESSAGE,
                code=MODEL_CONFIG_DRIFT,
                status_code=409,
            )
        return handle

    async def _suggestion_executor(self, frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
        """执行器：事务外解析模型（并核对冻结指纹）后调用；发布与任务终态同事务。"""
        snapshot = (
            dict(frozen.model_snapshot) if isinstance(frozen.model_snapshot, dict) else {}
        )
        if not snapshot.get("profileId") and not snapshot.get("modelProfileId"):
            # 历史行兼容：profile 冻结在输入里时照旧取用（指纹仍只信任务快照）
            fallback = str(frozen.input.get("modelProfileId") or "").strip()
            if fallback:
                snapshot["profileId"] = fallback
        handle = await self._resolve_frozen_handle(snapshot)

        # 提取任务按单册证据提炼，输出预算比手输候选更高（真机实测：2048 会因整册候选截断被拒）；
        # 调用等待同步放宽到有界上限（默认 30 秒对整册证据不够，真机实测撞 UPSTREAM_TIMEOUT）
        extraction = isinstance(frozen.input.get("extraction"), dict)
        max_output_tokens = (
            suggestion_rules.EXTRACTION_MAX_OUTPUT_TOKENS
            if extraction
            else suggestion_rules.MAX_OUTPUT_TOKENS
        )
        config = (
            replace(handle.config, timeoutSeconds=suggestion_rules.EXTRACTION_TIMEOUT_SECONDS)
            if extraction
            else handle.config
        )
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=suggestion_rules.system_instruction(frozen.input)),
                LLMMessage(role="user", content=suggestion_rules.render_evidence(frozen.input)),
            ],
            maxOutputTokens=max_output_tokens,
            params={},
        )
        if await ctx.cancellation_requested():
            return JobOutcome(result={"cancelled": True, "candidateCount": 0}, publish=None)
        response = await handle.provider.complete(config, request)
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

        # 事务外：模型原始输出登记为教学库受管资产（跨库逻辑引用，见任务卡 §8.3）；
        # 记录的模型身份取**本次实际执行**的句柄指纹（已与冻结值核对一致）
        original = json.dumps(
            {
                "jobId": frozen.job_id,
                "model": {
                    "profileId": handle.profile_id,
                    "fingerprint": fingerprint_of_handle(handle),
                },
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
        # 任务③：提取任务的教材证据坐标按"模型回引的证据 id"冻结进候选行
        # raw_cells（保留键 knowledgeExtractionEvidence），确认后自动建教材依据用。
        is_extraction = isinstance(frozen.input.get("extraction"), dict)
        textbook_entries_by_id = {
            str(item.get("id")): item for item in frozen.input.get("textbookEvidence") or []
        }
        sources: list[import_rules.AiRowSource] = []
        for candidate, raw in zip(candidates, raw_items, strict=True):
            source_issues = list(suggestion_rules.hint_issues(candidate, raw))
            raw_payload: dict[str, Any] = dict(raw)
            if is_extraction:
                entries: list[dict[str, Any]] = []
                for evidence_id in candidate.evidence_ids:
                    item = textbook_entries_by_id.get(evidence_id)
                    if item is None:
                        continue
                    entries.append(
                        {
                            "documentRevisionId": item.get("documentRevisionId"),
                            "charStart": item.get("charStart"),
                            "charEnd": item.get("charEnd"),
                            "title": item.get("title"),
                        }
                    )
                if entries:
                    merged_hint, hint_text = extraction_rules.build_extraction_evidence(entries)
                    raw_payload = extraction_rules.freeze_evidence_into_raw_cells(
                        raw_payload, merged_hint
                    )
                    if hint_text:
                        source_issues.append(
                            ErrorIssue(code=extraction_rules.EXTRACTION_EVIDENCE_KEY, message=hint_text)
                        )
            sources.append(
                import_rules.AiRowSource(candidate=candidate, raw=raw_payload, issues=tuple(source_issues))
            )
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
        # 任务③：新建行的教材证据坐标（raw_cells 冻结；确认时为新建知识点自动建依据）
        row_evidence: dict[int, list[dict[str, Any]]] = {}
        row_codes: dict[int, str] = {}
        for record_row in rows:
            row_codes[record_row.row_no] = record_row.code
            entries = extraction_rules.extract_evidence_from_raw_cells(record_row.raw_cells)
            if entries:
                row_evidence[record_row.row_no] = entries
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
        # 任务③：由本批 AI 候选带入证据的**新建**知识点自动建教材依据
        # （source="ai_confirmed"，既有枚举值；update 行不自动建依据）
        if created_by_code and row_evidence:
            extraction_rules.confirm_textbook_links(
                conn,
                created_by_code=created_by_code,
                row_evidence=row_evidence,
                row_codes=row_codes,
                links=self.links,
                points=self.points,
            )
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
            uploaded_file_name=_asset_original_name(asset),
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
    model_config_repo: Any | None = None,
    secret_store: Any | None = None,
    model_auth_service: Any | None = None,
    reference_checker: Any | None = None,
    scope_reader: Any | None = None,
) -> KnowledgeService:
    """装配入口（CTRL 在 ``main.py`` 调用）。

    ``evidence`` 允许为 ``None``（隔离环境/教材目录未装配）：此时任何 ``textbookEvidence``
    请求 503 ``TEXTBOOK_EVIDENCE_UNAVAILABLE``，只给 ``materials`` 的 AI 任务仍可用。
    ``model_resolver``/``job_engine`` 为 ``None`` 时 AI 候选 503，不返回假成功。

    B3/G0 v2 追加注入（RV04）：``model_config_repo`` + ``secret_store``（+ ``model_auth_service``）
    使候选执行器的冻结指纹核对走共享 ``resolve_frozen_model``；缺省时用 ``model_resolver``
    解析后按 ``fingerprint_of_handle`` 核对（同一判定与错误码）。形参名与题库/原卷一致。

    任务①②追加注入：``reference_checker``（跨库引用计数，缺失时彻底删除 503）、
    ``scope_reader``（任教范围解析，缺失时带 scope=taught 的调用 503，旧调用不变）。
    """
    return KnowledgeService(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        evidence=evidence,
        coordinator=coordinator,
        model_resolver=model_resolver,
        job_engine=job_engine,
        model_config_repo=model_config_repo,
        secret_store=secret_store,
        model_auth_service=model_auth_service,
        reference_checker=reference_checker,
        scope_reader=scope_reader,
    )


# --------------------------------------------------------------------------- 视图构造


def _point_dict(record: PointRecord, *, grade_ids: Sequence[str] = ()) -> dict[str, Any]:
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
        "gradeIds": list(grade_ids),
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
    record: ImportRecord,
    *,
    row_count: int,
    blocking_issue_count: int,
    uploaded_file_name: str | None = None,
) -> dict[str, Any]:
    return {
        "importId": record.import_id,
        "source": record.source,
        "subjectId": record.subject_id,
        "state": record.state,
        "revision": record.revision,
        "rowCount": row_count,
        "blockingIssueCount": blocking_issue_count,
        "uploadedFileName": uploaded_file_name,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def _asset_original_name(asset: Any) -> str | None:
    """教学库 ``file_assets.original_name``（缺失/损坏时 None，不伪造文件名）。"""
    name = getattr(asset, "original_name", None)
    if isinstance(name, str) and name.strip():
        return name
    return None


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
    "POINT_SCOPES",
    "KnowledgeService",
    "build_knowledge_service",
]
