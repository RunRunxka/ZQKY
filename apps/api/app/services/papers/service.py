"""原卷服务门面（TEACHING-LOOP B2 / T40）。

装配：``build_paper_service(teaching_catalog, *, asset_store, file_assets, knowledge_catalog,
coordinator, model_resolver, job_engine)``。所有 SQL 只经 ``TeachingCatalog`` 的
``write_transaction()`` / ``read_connection()``；DOCX 解析走 T10 ``parse_docx_rich``；
跨库知识点校验只读复用 B1 ``KnowledgePointRepository``（不写知识点库）。

关键语义（与冻结契约 ``app/contracts/papers.py`` 一致）：

- **导入**：DOCX 真实字节先写受管资产（blob 在事务外），解析（事务外）后在一个写事务里
  登记资产行 + ``papers`` + draft 修订（version=1，标题快照 = ``papers.title``）+
  全部原文块 + 规则候选题目 + 问题清单；
  非 docx → 422 ``UNSUPPORTED_DOCUMENT_FORMAT``，整文件不可解析/无内容块 → 422
  ``PAPER_IMPORT_PARSE_FAILED``；
- **草稿 PATCH**：整表替换 ``items``（``blocks``/``issues`` 提供则更新处置），
  核 ``expectedRevision``（= ``papers.revision`` 编辑锁），同事务 ``revision + 1``；
  跨库知识点校验在发布临界区内、**写事务之外**先做（``operation="paper.draft"``）；
  当前修订已确认时**自动新建 draft 修订**（version+1，逐行复制内容，旧修订/旧施测不变），
  服务绝不写入已确认修订；已归档原卷 → 409 ``PAPER_NOT_EDITABLE``；
- **问题处置（B3/G0 · B2-RV02）**：``resolved``/``excluded`` 必须带**结构化** ``resolution``：
  ``supplement_text``（目标块必须是段落块，文本追加进 ``block_json``）/
  ``supplement_asset``（``blobs/<64hex>`` 受管键，``AssetStore`` 校验字节散列后在目标块后
  插入图片块）/ ``exclude``（必须有理由，且**内容损失类问题码不允许排除**）。
  空 ``{}`` / 缺字段 / 任意 JSON 一律 422 + ``details.issues`` 定位；
- **确认**：``operation="paper.confirm"`` + ``submissionId`` 幂等（同一提交重放返回原结果），
  闸门与知识点复核都在 ``PublicationCoordinator`` 内（写事务前用
  ``require_active_knowledge_references`` 复核存在/修订/学科/未归档，归档 → 409
  ``KNOWLEDGE_ARCHIVED``，**不释放协调锁后才写引用**）；同一事务内过闸门：
  草稿归属 → 题号唯一/无环/只有叶子计分 → 每个计分叶有知识点 →
  **每个计分叶有实质题面**且富内容引用的共同材料/资产都在本修订的块集合里 →
  叶子合计 = 总分 > 0 → 无未归属块 → 无 open 的 blocking 问题；然后置 confirmed +
  更新 ``current_revision_id`` + ``papers.revision + 1`` + 写提交结果（不要求答案/解析/评分点）；
- **修订内容读取**：``blocks[].content`` 返回持久化 ``block_json``（未归属块也有正文）；
  标题读**修订级快照** ``paper_revisions.title_snapshot``（B3/G0 · B2-RV11），
  空快照按 500 ``PAPER_ROW_CORRUPT`` 处理（迁移已回填，不允许回退到可变 ``papers.title``）；
  受管资产经 ``GET /papers/{id}/revisions/{rid}/assets/{assetId}/content`` 受控读取
  （只放行被该修订图片块引用过的 ``blobs/<64hex>``）；
- **AI 建议**：``teaching:paper_mapping`` 经任务引擎（``uses_model=True``）；注册进公共执行器
  注册表（``register_job_executors``），公共 retry 与首次调度共用同一份执行器；冻结草稿版本、
  计分叶子、允许知识点与模型指纹；输出四类非法（JSON/截断/未知知识点/未知题目/证据越界）
  一律失败；执行前用冻结快照复核真实配置指纹（缺指纹 422 ``MODEL_FINGERPRINT_MISSING``、
  漂移 409 ``MODEL_CONFIG_DRIFT``，不换模型、不发布）；发布事务内再核
  ``papers.revision == baseRevision``（过期 → 409
  ``PAPER_PROPOSAL_STALE``，零建议落库）；应用时只写**已有知识点**（``source="ai_confirmed"``），
  新知识点候选先走 T20 候选确认再由教师单独绑定（本服务不创建知识点）。
"""

from __future__ import annotations

import functools
import hashlib
import sqlite3
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import anyio

from app.contracts.papers import (
    CONTENT_LOSS_ISSUE_CODES,
    KNOWLEDGE_REFERENCE_INVALID,
    NO_SCORED_ITEMS,
    PAPER_BLOCK_INVALID,
    PAPER_BLOCK_UNASSIGNED,
    PAPER_IMPORT_ASSET_INVALID,
    PAPER_IMPORT_PARSE_FAILED,
    PAPER_ISSUE_BLOCKING,
    PAPER_ISSUE_NOT_FOUND,
    PAPER_NOT_EDITABLE,
    PAPER_NOT_FOUND,
    PAPER_PROPOSAL_INVALID,
    PAPER_PROPOSAL_NOT_FOUND,
    PAPER_PROPOSAL_STALE,
    PAPER_REVISION_STALE,
    PAPER_TOTAL_MISMATCH,
    SCORED_ITEM_MUST_BE_LEAF,
    ITEM_CYCLE,
    ITEM_KNOWLEDGE_MISSING,
    ITEM_PARENT_INVALID,
    ITEM_QUESTION_NO_DUPLICATE,
    ITEM_SCORE_INVALID,
    PaperBlockPatch,
    PaperConfirmRequest,
    PaperConfirmResult,
    PaperDraftPatchRequest,
    PaperImportView,
    PaperIssuePatch,
    PaperIssueResolution,
    PaperItemInput,
    PaperItemKnowledgeView,
    PaperItemView,
    PaperList,
    PaperProposalDecisionRequest,
    PaperProposalItemView,
    PaperProposalJobRequest,
    PaperProposalView,
    PaperRevisionContentView,
    PaperSourceBlockView,
    PaperIssueView,
    PaperView,
)
from app.contracts.teaching_loop import (
    ErrorIssue,
    JobView,
    RichOrigin,
    error_details,
)
from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.knowledge.points import KnowledgePointRepository, PointRecord
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.papers import (
    BlockRecord,
    ItemKnowledgeRecord,
    ItemRecord,
    PaperRecord,
    PaperRepository,
    ProposalRecord,
    RevisionCopyMap,
    RevisionRecord,
)
from app.services.assets.store import AssetStore, is_managed_blob_key
from app.services.knowledge_refs import (
    KnowledgeReference,
    require_active_knowledge_references,
)
from app.services.model_runtime import (
    MODEL_FINGERPRINT_MISSING,
    ChatModelHandle,
    fingerprint_of_handle,
    resolve_frozen_model,
)
from app.services.papers import imports as import_rules
from app.services.papers import proposals as proposal_rules
from app.services.papers.proposals import ProposalDraft, ProposalRunner
from app.services.papers.reader import ConfirmedPaperReaderAdapter
from app.services.publication import PublicationCoordinator
from app.services.rich_content import parse_docx_rich
from app.services.submissions.service import execute_command, make_command

DEFAULT_MEDIA_TYPE = "application/octet-stream"
#: 富内容解析器版本（写进 origin.sourceLocator，便于回溯解析口径）
RICH_PARSER_VERSION = "zqky-rich-v1"
MAX_TITLE_CHARS = 200
#: 服务级 issue code（不新增顶层错误码；details.issues 里的定位码）
ITEM_ORDINAL_DUPLICATE = "ITEM_ORDINAL_DUPLICATE"
ITEM_ID_INVALID = "ITEM_ID_INVALID"
ITEM_KNOWLEDGE_DUPLICATE = "ITEM_KNOWLEDGE_DUPLICATE"
#: 确认闸门（B3/G0 · B2-RV02）：计分叶没有实质题面
ITEM_STEM_MISSING = "ITEM_STEM_MISSING"
#: 确认闸门（B3/G0 · B2-RV02）：计分叶富内容引用的共同材料/资产不在本修订的块集合里
ITEM_MATERIAL_MISSING = "ITEM_MATERIAL_MISSING"
#: 问题处置（B3/G0 · B2-RV02）：resolution 形状/内容不合法（逐条可定位）
PAPER_ISSUE_RESOLUTION_INVALID = "PAPER_ISSUE_RESOLUTION_INVALID"
#: 受控资产内容读取（B3/G0 · B2-RV03）：资产键合法但未被该修订的图片块引用
PAPER_ASSET_NOT_FOUND = "PAPER_ASSET_NOT_FOUND"
#: 整表替换后，块引用已删除题目时的记录码（warning）
BLOCK_ITEM_RESET = "PAPER_BLOCK_ITEM_RESET"
#: 补录图片块的 payload id 前缀（行 id = ``<修订 id>:<payload id>``，全局唯一）
SUPPLEMENT_BLOCK_PREFIX = "supplement-"
#: 补录图片块未知原始尺寸（不猜测；前端按自然尺寸渲染）
SUPPLEMENT_IMAGE_SIZE = 0

#: 契约错误码 → 可读文案（DB 触发器兜底路径使用）
_TRIGGER_MESSAGES = {
    "NO_SCORED_ITEMS": ("没有计分小题：至少一道叶子题必须计分。", NO_SCORED_ITEMS),
    "PAPER_TOTAL_MISMATCH": (
        "总分与计分叶子合计不一致，确认被拒绝。",
        PAPER_TOTAL_MISMATCH,
    ),
    "ITEM_KNOWLEDGE_MISSING": (
        "存在没有知识点关联的计分小题，确认被拒绝。",
        ITEM_KNOWLEDGE_MISSING,
    ),
    "SCORED_ITEM_MUST_BE_LEAF": (
        "计分题不能有子题（只有叶子计分），确认被拒绝。",
        SCORED_ITEM_MUST_BE_LEAF,
    ),
    "IMMUTABLE_REVISION": ("该修订已确认，不可修改。", PAPER_NOT_EDITABLE),
    "ITEM_CYCLE": ("父子关系会形成环。", ITEM_CYCLE),
    "USE_CONFIRM_TRANSITION": (
        "确认必须走确认闸门，不能直接写入 confirmed 修订。",
        PAPER_NOT_EDITABLE,
    ),
    "PAPER_NOT_CONFIRMED": ("只能使用已确认的原卷修订。", PAPER_NOT_EDITABLE),
}


# --------------------------------------------------------------------------- 内部类型


@dataclass(frozen=True)
class _KnowledgeRef:
    point_id: str
    revision_id: str
    name: str
    code: str


@dataclass(frozen=True)
class _NormalizedItem:
    item_id: str
    parent_item_id: str | None
    question_no: str
    ordinal: int
    is_scored: bool
    max_score_units: int | None
    content: dict[str, Any]
    source_locator: dict[str, Any]
    knowledge: tuple[ItemKnowledgeRecord, ...]

    def as_row(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "parent_item_id": self.parent_item_id,
            "question_no": self.question_no,
            "ordinal": self.ordinal,
            "is_scored": self.is_scored,
            "max_score_units": self.max_score_units,
            "content": self.content,
            "source_locator": self.source_locator,
        }


# --------------------------------------------------------------------------- 小工具


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=list(fields)) if fields else None,
    )


def _issue_error(
    message: str, *, code: str, status_code: int, issues: list[ErrorIssue]
) -> AppError:
    return AppError(
        message,
        code=code,
        status_code=status_code,
        details=error_details(issues=list(issues)),
    )


def _issue(
    row: int | None, *, code: str, message: str, field: str | None = None
) -> ErrorIssue:
    return ErrorIssue(row=row, column=field, field=field, code=code, message=message)


def _raise_first(message: str, issues: list[ErrorIssue], *, status_code: int = 422) -> None:
    """以**第一条** issue 的 code 作为顶层错误码抛出（可定位、可测）。"""
    if not issues:
        return
    raise _issue_error(message, code=issues[0].code, status_code=status_code, issues=issues)


def _clean_text(value: object, *, field: str, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    text = value.strip()
    if maximum is not None and len(text) > maximum:
        raise _invalid(f"{field} 不能超过 {maximum} 个字符。", fields=[field])
    return text


def _stale_conflict(current: int) -> AppError:
    return AppError(
        "原卷已被其他操作更新，请刷新后重试。",
        code=PAPER_REVISION_STALE,
        status_code=409,
        details=error_details(current_revision=current),
    )


def _score_text(units: int | None) -> str:
    """整数分（×100）→ 十进制字符串（去掉无意义的尾随 0）。"""
    value = int(units or 0)
    whole, fraction = divmod(value, 100)
    if fraction == 0:
        return str(whole)
    return f"{whole}.{fraction:02d}".rstrip("0")


def _parse_score_units(text: str) -> int:
    """十进制字符串 → ×100 整数；非法（≤0、>2 位小数、非有限值）抛 ``ITEM_SCORE_INVALID``。"""
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError) as exc:
        raise _issue_error(
            "满分必须是十进制数字字符串。",
            code=ITEM_SCORE_INVALID,
            status_code=422,
            issues=[
                _issue(None, code=ITEM_SCORE_INVALID, message="maxScore 不是合法十进制数。", field="maxScore")
            ],
        ) from exc
    if not value.is_finite() or value <= 0:
        raise _issue_error(
            "满分必须大于 0。",
            code=ITEM_SCORE_INVALID,
            status_code=422,
            issues=[
                _issue(None, code=ITEM_SCORE_INVALID, message="maxScore 必须大于 0。", field="maxScore")
            ],
        )
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise _issue_error(
            "满分最多两位小数。",
            code=ITEM_SCORE_INVALID,
            status_code=422,
            issues=[
                _issue(
                    None,
                    code=ITEM_SCORE_INVALID,
                    message="maxScore 最多两位小数。",
                    field="maxScore",
                )
            ],
        )
    units = value * 100
    if units != units.to_integral_value():
        raise _issue_error(
            "满分最多两位小数。",
            code=ITEM_SCORE_INVALID,
            status_code=422,
            issues=[
                _issue(None, code=ITEM_SCORE_INVALID, message="maxScore 无法用 ×100 整数表示。", field="maxScore")
            ],
        )
    result = int(units)
    if result > 999999:
        raise _issue_error(
            "满分超出可表示范围。",
            code=ITEM_SCORE_INVALID,
            status_code=422,
            issues=[
                _issue(None, code=ITEM_SCORE_INVALID, message="maxScore 超出上限 9999.99。", field="maxScore")
            ],
        )
    return result


def _translate_integrity_error(exc: sqlite3.IntegrityError) -> AppError:
    """把 DB 约束/触发器错误翻译成契约错误码（触发器是确认闸门的最后兜底）。"""
    text = str(exc)
    for marker, (message, code) in _TRIGGER_MESSAGES.items():
        if marker in text:
            status_code = 409 if code == PAPER_NOT_EDITABLE else 422
            return AppError(message, code=code, status_code=status_code)
    if "UNIQUE" in text and "paper_items" in text and "question_no" in text:
        return AppError("题号在同一修订内必须唯一。", code=ITEM_QUESTION_NO_DUPLICATE, status_code=422)
    if "UNIQUE" in text and "paper_items" in text and "ordinal" in text:
        return AppError("题目序号在同一修订内必须唯一。", code=ITEM_ORDINAL_DUPLICATE, status_code=422)
    if "FOREIGN KEY" in text:
        return AppError(
            "题目父引用或块归属指向不存在的行。", code=ITEM_PARENT_INVALID, status_code=422
        )
    if "CHECK constraint failed" in text:
        return AppError(
            "草稿内容违反原卷约束（分值/块处置/归属）。",
            code=PAPER_BLOCK_INVALID,
            status_code=422,
        )
    return AppError(
        "原卷写入违反数据库约束。", code="INVALID_REQUEST", status_code=422
    )


def _is_leaf(item: ItemRecord | _NormalizedItem, children: Mapping[str, int]) -> bool:
    return children.get(item.item_id, 0) == 0


def _child_counts(items: Sequence[ItemRecord | _NormalizedItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if item.parent_item_id is not None:
            counts[item.parent_item_id] = counts.get(item.parent_item_id, 0) + 1
    return counts


async def _threaded(fn, /, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


# --------------------------------------------------------------------------- 服务


class PaperService:
    """原卷导入 / 草稿 / 确认 / AI 建议 / 已确认读取的用例入口。"""

    def __init__(
        self,
        catalog: TeachingCatalog,
        *,
        asset_store: AssetStore,
        file_assets: FileAssetsRepository,
        knowledge_catalog: Any | None,
        coordinator: PublicationCoordinator,
        model_resolver: Any | None = None,
        job_engine: Any | None = None,
        model_config_repo: Any | None = None,
        secret_store: Any | None = None,
        model_auth_service: Any | None = None,
        owner_id: str = "local",
    ) -> None:
        self._catalog = catalog
        self._assets = asset_store
        self._file_assets = file_assets
        self._knowledge = knowledge_catalog
        self._points = KnowledgePointRepository()
        self._coordinator = coordinator
        self._model_resolver = model_resolver
        self._job_engine = job_engine
        #: RV04 冻结模型核对：装配了原始仓储/凭证时直接用公共 ``resolve_frozen_model``；
        #: 只装配 resolver 时按 ``fingerprint_of_handle`` 走同一份核对（错误码一致）
        self._model_config_repo = model_config_repo
        self._secret_store = secret_store
        self._model_auth_service = model_auth_service
        self._owner_id = owner_id
        self._papers = PaperRepository(catalog)
        self._reader = ConfirmedPaperReaderAdapter(catalog)

    # ---------------------------------------------------------------- 导入

    def create_import(
        self,
        *,
        file_name: str,
        content: bytes,
        media_type: str,
        subject_id: str,
        title: str | None = None,
    ) -> PaperImportView:
        file_name = _clean_text(file_name, field="fileName", maximum=300)
        subject_id = _clean_text(subject_id, field="subjectId", maximum=64)
        media_type = (media_type or "").strip() or DEFAULT_MEDIA_TYPE
        if title is not None:
            title = _clean_text(title, field="title", maximum=MAX_TITLE_CHARS)
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise _invalid("上传的原卷文件为空。", fields=["file"])
        if Path(file_name).suffix.lower() != ".docx":
            raise AppError(
                f"原卷导入只支持 .docx，收到「{Path(file_name).suffix or file_name}」。",
                code="UNSUPPORTED_DOCUMENT_FORMAT",
                status_code=422,
            )

        # 1) 原件字节先落受管资产（内容寻址、幂等）；资产行与 paper/revision 同一事务登记
        stored = self._assets.store_original(
            bytes(content), media_type=media_type, original_name=file_name
        )
        if stored.sha256 != hashlib.sha256(bytes(content)).hexdigest():
            raise AppError(
                "上传内容与受管资产散列不一致，已停止导入。",
                code=PAPER_IMPORT_ASSET_INVALID,
                status_code=422,
            )
        asset_id = uuid.uuid4().hex
        origin = RichOrigin(
            originalAssetId=asset_id,
            originalSha256=stored.sha256,
            sourceLocator={"fileName": file_name, "parserVersion": RICH_PARSER_VERSION},
        )
        analysis = self._analyze(content, file_name=file_name, origin=origin)

        item_ids: dict[str, str] = {}
        for candidate in analysis.items:
            item_ids[candidate.question_no] = uuid.uuid4().hex
        # 块行 id 带修订命名空间：解析器块 id 是文档内序号（p1/t2/…），跨修订不唯一，
        # 而 paper_source_blocks.id 是全局主键；block_json.id 仍保存解析器原始 id。
        revision_id = uuid.uuid4().hex
        block_ids = {block.block_id: f"{revision_id}:{block.block_id}" for block in analysis.blocks}
        rows = [
            _NormalizedItem(
                item_id=item_ids[candidate.question_no],
                parent_item_id=(
                    item_ids.get(candidate.parent_question_no)
                    if candidate.parent_question_no
                    else None
                ),
                question_no=candidate.question_no,
                ordinal=candidate.ordinal,
                is_scored=candidate.is_scored,
                max_score_units=(
                    _parse_score_units(candidate.max_score)
                    if candidate.is_scored and candidate.max_score
                    else None
                ),
                content=dict(candidate.content),
                source_locator=dict(candidate.locator),
                knowledge=(),
            )
            for candidate in analysis.items
        ]
        blocks = [
            {
                "block_id": block_ids[block.block_id],
                "ordinal": block.ordinal,
                "kind": block.kind,
                "block": block.payload,
                "locator": block.locator,
                "disposition": block.disposition,
                "item_id": (
                    item_ids.get(block.item_question_no) if block.item_question_no else None
                ),
                "exclude_reason": block.exclude_reason,
            }
            for block in analysis.blocks
        ]
        issues = [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "block_id": block_ids.get(issue.block_id) if issue.block_id else None,
                "locator": issue.locator,
            }
            for issue in analysis.issues
        ]
        paper_title = title or _clean_text(Path(file_name).stem, field="title", maximum=MAX_TITLE_CHARS)

        try:
            with self._catalog.write_transaction() as conn:
                asset = self._file_assets.create_in(
                    conn,
                    kind="paper",
                    blob_key=stored.blob_key,
                    sha256=stored.sha256,
                    media_type=media_type,
                    byte_size=stored.byte_size,
                    original_name=file_name,
                    owner_id=self._owner_id,
                    asset_id=asset_id,
                )
                paper = self._papers.create_paper_in(
                    conn,
                    subject_id=subject_id,
                    title=paper_title,
                    owner_id=self._owner_id,
                )
                revision = self._papers.create_revision_in(
                    conn,
                    paper_id=paper.paper_id,
                    version=1,
                    source_file_id=asset.asset_id,
                    total_score_units=analysis.total_score_units,
                    title_snapshot=paper_title,
                    title_snapshot_source="revision",
                    revision_id=revision_id,
                )
                self._papers.insert_items_in(
                    conn,
                    paper_revision_id=revision.revision_id,
                    items=[item.as_row() for item in rows],
                )
                self._papers.insert_blocks_in(
                    conn, paper_revision_id=revision.revision_id, blocks=blocks
                )
                self._papers.insert_issues_in(
                    conn, paper_revision_id=revision.revision_id, issues=issues
                )
                self._papers.set_current_revision_in(
                    conn, paper.paper_id, revision.revision_id
                )
        except sqlite3.IntegrityError as exc:  # pragma: no cover - 导入行由本服务构造
            raise _translate_integrity_error(exc) from exc

        paper_view = self.get_paper(paper.paper_id)
        return PaperImportView(
            paper=paper_view,
            revision=self.get_revision_content(paper.paper_id, revision.revision_id),
            warnings=list(analysis_warnings(analysis)),
        )

    def _analyze(self, content: bytes, *, file_name: str, origin: RichOrigin):
        with tempfile.TemporaryDirectory(prefix="zqky-paper-") as directory:
            path = Path(directory) / "source.docx"
            path.write_bytes(bytes(content))
            try:
                parsed = parse_docx_rich(
                    path=path, file_name=file_name, assets=self._assets, origin=origin
                )
            except AppError as exc:
                raise self._import_error(exc) from exc
        if not parsed.blocks:
            raise AppError(
                "DOCX 没有可用的内容块（整文件不可解析）；请另存为 .docx 后重试。",
                code=PAPER_IMPORT_PARSE_FAILED,
                status_code=422,
            )
        return import_rules.analyze_paper(parsed=parsed, origin=origin)

    @staticmethod
    def _import_error(exc: AppError) -> AppError:
        if exc.code in ("DOCUMENT_PARSE_FAILED", "DOCUMENT_FILE_MISSING", "DOCUMENT_PARSER_UNAVAILABLE"):
            return AppError(
                f"原卷 DOCX 无法解析：{exc}",
                code=PAPER_IMPORT_PARSE_FAILED,
                status_code=422,
            )
        return exc

    # ---------------------------------------------------------------- 原卷查询

    def list_papers(
        self,
        *,
        subject_id: str | None = None,
        status: str | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaperList:
        with self._catalog.read_connection() as conn:
            summaries, total = self._papers.list_papers(
                conn, subject_id=subject_id, status=status, q=q, offset=offset, limit=limit
            )
        return PaperList(
            items=[self._paper_view(summary) for summary in summaries],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_paper(self, paper_id: str) -> PaperView:
        paper_id = _clean_text(paper_id, field="paperId")
        with self._catalog.read_connection() as conn:
            summary = self._papers.summary_in(conn, paper_id)
        return self._paper_view(summary)

    def get_revision_content(self, paper_id: str, revision_id: str) -> PaperRevisionContentView:
        paper_id = _clean_text(paper_id, field="paperId")
        revision_id = _clean_text(revision_id, field="revisionId")
        with self._catalog.read_connection() as conn:
            paper = self._papers.require_paper_in(conn, paper_id)
            revision = self._papers.require_revision_of_paper_in(conn, paper_id, revision_id)
            return self._render_content_in(conn, paper, revision)

    def get_revision_asset_content(
        self, paper_id: str, revision_id: str, asset_id: str
    ) -> tuple[bytes, str]:
        """受控读取该修订图片块引用过的受管资产字节（B3/G0 · B2-RV03）。

        - ``asset_id`` 必须是受管键 ``blobs/<64hex>``（否则 422 ``INVALID_ASSET_KEY``）；
        - 该键必须被**本修订**（且属于该原卷）的图片块引用，否则 404
          ``PAPER_ASSET_NOT_FOUND``（不泄漏其它修订/其它卷的资产，也不开任意路径读取）；
        - 返回真实字节 + 按魔数识别的 media type；``AssetStore.read`` 会重算 sha256。
        """
        paper_id = _clean_text(paper_id, field="paperId")
        revision_id = _clean_text(revision_id, field="revisionId")
        if not is_managed_blob_key(asset_id):
            raise AppError(
                "资产键必须是受管键 blobs/<64 位小写 hex>。",
                code="INVALID_ASSET_KEY",
                status_code=422,
            )
        with self._catalog.read_connection() as conn:
            self._papers.require_paper_in(conn, paper_id)
            revision = self._papers.require_revision_of_paper_in(conn, paper_id, revision_id)
            referenced = {
                block.block.get("assetId")
                for block in self._papers.list_blocks_in(conn, revision.revision_id)
                if block.kind == "image"
            }
        if asset_id not in referenced:
            raise AppError(
                "该资产没有被这个修订的图片块引用，不能读取。",
                code=PAPER_ASSET_NOT_FOUND,
                status_code=404,
            )
        # 事务外读取真实字节（AssetStore.read 重算 sha256，缺失/损坏不返回可疑内容）
        data = self._assets.read(asset_id)
        return data, _image_media_type(data)

    # ---------------------------------------------------------------- 草稿

    def patch_draft(
        self, paper_id: str, payload: PaperDraftPatchRequest
    ) -> PaperRevisionContentView:
        paper_id = _clean_text(paper_id, field="paperId")
        requested_points = [
            entry.knowledge_point_id
            for item in payload.items or []
            for entry in item.knowledge
        ]
        with self._coordinator.publication(operation="paper.draft"):
            # 1) 只读预检（本库）：存在 / 未归档 / 编辑锁
            with self._catalog.read_connection() as conn:
                paper = self._papers.require_paper_in(conn, paper_id)
                revision = self._current_revision_in(conn, paper)
                subject_id = paper.subject_id
            self._require_editable_paper(paper)
            if paper.revision != payload.expected_revision:
                raise _stale_conflict(paper.revision)
            # 2) 跨库知识点校验（写事务外，发布临界区内）
            refs = self._load_knowledge_refs(subject_id, requested_points)
            # 3) 写事务
            try:
                with self._catalog.write_transaction() as conn:
                    paper = self._papers.require_paper_in(conn, paper_id)
                    if paper.revision != payload.expected_revision:
                        raise _stale_conflict(paper.revision)
                    revision = self._current_revision_in(conn, paper)
                    copied = None
                    if revision.state == "confirmed":
                        revision, copied = self._fork_draft_in(conn, paper, revision)
                    elif revision.state != "draft":
                        raise AppError(
                            "原卷修订状态不合法。",
                            code="PAPER_ROW_CORRUPT",
                            status_code=500,
                        )
                    if payload.title is not None:
                        self._set_paper_title_in(conn, paper_id, payload.title)
                    # 草稿保存时同步修订级标题快照（= papers.title）；已确认修订不受影响
                    titled = self._papers.require_paper_in(conn, paper_id)
                    self._papers.set_revision_title_snapshot_in(
                        conn, revision.revision_id, titled.title, source="revision"
                    )
                    if payload.items is not None:
                        self._replace_items_in(
                            conn, revision, payload.items, refs, id_map=copied
                        )
                    if payload.blocks is not None:
                        self._apply_blocks_in(conn, revision, payload.blocks, id_map=copied)
                    if payload.issues is not None:
                        self._apply_issues_in(conn, revision, payload.issues, id_map=copied)
                    self._papers.bump_revision_in(conn, paper_id)
                    paper = self._papers.require_paper_in(conn, paper_id)
                    # 重新读修订：本次写入可能已更新总分/状态（局部对象不能当权威）
                    revision = self._papers.require_revision_in(conn, revision.revision_id)
                    return self._render_content_in(conn, paper, revision)
            except sqlite3.IntegrityError as exc:
                raise _translate_integrity_error(exc) from exc

    # ---------------------------------------------------------------- 确认

    def confirm(self, paper_id: str, payload: PaperConfirmRequest) -> PaperConfirmResult:
        paper_id = _clean_text(paper_id, field="paperId")
        command = make_command(
            operation="paper.confirm",
            submission_id=payload.submission_id,
            payload={"paperId": paper_id, "expectedRevision": payload.expected_revision},
            owner_id=self._owner_id,
        )
        # B3/G0 · B2-RV06：知识点复核与域内写事务都在同一个发布临界区内；
        # 已登记提交（重放）不重新复核，保证幂等重放返回原结果、不因事后归档改变历史。
        with self._coordinator.publication(operation="paper.confirm"):
            with self._catalog.read_connection() as conn:
                recorded = self._papers.submission_recorded_in(
                    conn,
                    owner_id=self._owner_id,
                    operation="paper.confirm",
                    submission_id=payload.submission_id,
                )
            if not recorded:
                self._recheck_confirm_knowledge(paper_id, payload.expected_revision)
            try:
                outcome = execute_command(
                    catalog=self._catalog,
                    command=command,
                    apply=lambda conn: self._apply_confirm(
                        conn, paper_id=paper_id, expected_revision=payload.expected_revision
                    ),
                    table="command_submissions",
                )
            except sqlite3.IntegrityError as exc:
                raise _translate_integrity_error(exc) from exc
        result = PaperConfirmResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    def _recheck_confirm_knowledge(self, paper_id: str, expected_revision: int) -> None:
        """确认前复核草稿引用的知识点（跨库只读；必须在发布临界区内、写事务之前调用）。

        草稿绑定时的 active 检查不能代表确认时刻的状态：知识点可能在草稿期被归档。
        历史已确认关联不受影响（本方法只核**新发布**的引用）。
        """
        with self._catalog.read_connection() as conn:
            paper = self._papers.require_paper_in(conn, paper_id)
            self._require_editable_paper(paper)
            if paper.revision != expected_revision:
                raise _stale_conflict(paper.revision)
            revision = self._current_revision_in(conn, paper)
            references = self._revision_knowledge_references(conn, revision)
        if not references:
            return
        if self._knowledge is None:
            raise AppError(
                "知识点库未装配，无法复核知识点关联；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        require_active_knowledge_references(
            self._knowledge, references, expected_subject_id=paper.subject_id
        )

    def _revision_knowledge_references(
        self, conn: sqlite3.Connection, revision: RevisionRecord
    ) -> list[KnowledgeReference]:
        """修订内去重后的知识点引用（身份 + 内容修订；不刷新名称快照）。"""
        references: list[KnowledgeReference] = []
        seen: set[tuple[str, str]] = set()
        for item in self._papers.list_items_in(conn, revision.revision_id):
            for entry in item.knowledge:
                key = (entry.knowledge_point_id, entry.knowledge_revision_id)
                if key in seen:
                    continue
                seen.add(key)
                references.append(
                    KnowledgeReference(
                        knowledge_point_id=entry.knowledge_point_id,
                        knowledge_revision_id=entry.knowledge_revision_id,
                    )
                )
        return references

    def _apply_confirm(
        self, conn: sqlite3.Connection, *, paper_id: str, expected_revision: int
    ) -> dict[str, Any]:
        paper = self._papers.require_paper_in(conn, paper_id)
        self._require_editable_paper(paper)
        if paper.revision != expected_revision:
            raise _stale_conflict(paper.revision)
        revision = self._current_revision_in(conn, paper)
        if revision.state == "confirmed":
            raise AppError(
                "该原卷修订已确认，不能重复确认；修改会自动新建草稿修订。",
                code=PAPER_NOT_EDITABLE,
                status_code=409,
            )
        if revision.state != "draft":
            raise AppError("原卷修订状态不合法。", code="PAPER_ROW_CORRUPT", status_code=500)

        items = self._papers.list_items_in(conn, revision.revision_id)
        self._validate_item_tree(items)
        children = _child_counts(items)
        scored_leaves = [
            item for item in items if item.is_scored and _is_leaf(item, children)
        ]
        missing = [item for item in scored_leaves if not item.knowledge]
        if missing:
            raise _issue_error(
                "存在没有知识点关联的计分小题，不能确认。",
                code=ITEM_KNOWLEDGE_MISSING,
                status_code=422,
                issues=[
                    _issue(
                        item.ordinal,
                        code=ITEM_KNOWLEDGE_MISSING,
                        message=f"题 {item.question_no} 是计分叶子但没有知识点关联。",
                        field="knowledge",
                    )
                    for item in missing
                ],
            )
        total = sum(int(item.max_score_units or 0) for item in scored_leaves)
        if not scored_leaves:
            raise _issue_error(
                "没有计分小题，不能确认。",
                code=NO_SCORED_ITEMS,
                status_code=422,
                issues=[
                    _issue(
                        None,
                        code=NO_SCORED_ITEMS,
                        message="至少一道叶子题必须计分。",
                        field="items",
                    )
                ],
            )
        if total <= 0 or total != revision.total_score_units:
            raise _issue_error(
                "总分必须大于 0 且等于计分叶子合计，不能确认。",
                code=PAPER_TOTAL_MISMATCH,
                status_code=422,
                issues=[
                    _issue(
                        None,
                        code=PAPER_TOTAL_MISMATCH,
                        message=(
                            f"计分叶子合计 {_score_text(total)} 与草稿总分 "
                            f"{_score_text(revision.total_score_units)} 不一致。"
                        ),
                        field="totalScoreUnits",
                    )
                ],
            )
        unassigned = self._papers.list_blocks_in(conn, revision.revision_id)
        pending = [block for block in unassigned if block.disposition == "unassigned"]
        if pending:
            raise _issue_error(
                "仍有未归属的原文块，不能确认。",
                code=PAPER_BLOCK_UNASSIGNED,
                status_code=422,
                issues=[
                    _issue(
                        block.ordinal,
                        code=PAPER_BLOCK_UNASSIGNED,
                        message=f"第 {block.ordinal} 个原文块未归属；请指定归属或填写排除理由。",
                        field="blocks",
                    )
                    for block in pending
                ],
            )
        blocking = [
            issue
            for issue in self._papers.list_issues_in(conn, revision.revision_id)
            if issue.severity == "blocking" and issue.status == "open"
        ]
        if blocking:
            raise _issue_error(
                "仍有未解决的阻断问题，不能确认。",
                code=PAPER_ISSUE_BLOCKING,
                status_code=422,
                issues=[
                    _issue(
                        None,
                        code=PAPER_ISSUE_BLOCKING,
                        message=f"{issue.code}：{issue.message}",
                        field="issues",
                    )
                    for issue in blocking
                ],
            )
        # B3/G0 · B2-RV02：计分叶必须有实质题面，富内容引用的共同材料/资产必须在本修订里。
        # 不要求答案/解析/评分点；只拒绝"内容为空"或"引用已丢失"的假题面。
        self._validate_leaf_substance_in(conn, revision, scored_leaves)
        self._papers.set_revision_total_in(conn, revision.revision_id, total)
        self._papers.confirm_revision_in(conn, revision.revision_id)
        self._papers.set_current_revision_in(conn, paper_id, revision.revision_id)
        self._papers.bump_revision_in(conn, paper_id)
        return {
            "paperId": paper_id,
            "paperRevisionId": revision.revision_id,
            "state": "confirmed",
            "totalScoreUnits": total,
            "scoredLeafCount": len(scored_leaves),
            "replayed": False,
        }

    # ---------------------------------------------------------------- AI 建议

    async def create_proposal_job(
        self, paper_id: str, payload: PaperProposalJobRequest
    ) -> JobView:
        if self._job_engine is None:
            raise AppError(
                "原卷 AI 建议未装配任务引擎（job_engine），无法创建任务；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if self._model_resolver is None:
            raise AppError(
                "原卷 AI 建议未装配模型解析器（model_resolver），无法调用聊天模型；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        paper_id = _clean_text(paper_id, field="paperId")
        profile_id = _clean_text(payload.model_profile_id, field="modelProfileId", maximum=128)
        with self._catalog.read_connection() as conn:
            paper = self._papers.require_paper_in(conn, paper_id)
            revision = self._current_revision_in(conn, paper)
            items = self._papers.list_items_in(conn, revision.revision_id)
        if paper.revision != payload.expected_revision:
            raise _stale_conflict(paper.revision)
        if paper.status == "archived":
            raise self._not_editable("原卷已归档")
        if revision.state != "draft":
            raise self._not_editable("只有草稿修订可以发起 AI 建议")
        children = _child_counts(items)
        leaves = [item for item in items if item.is_scored and _is_leaf(item, children)]
        if not leaves:
            raise _issue_error(
                "该草稿还没有计分叶子，无法发起知识点建议。",
                code=NO_SCORED_ITEMS,
                status_code=422,
                issues=[
                    _issue(None, code=NO_SCORED_ITEMS, message="先补全计分小题。", field="items")
                ],
            )
        if len(leaves) > proposal_rules.MAX_ITEMS:
            raise _invalid(
                f"计分小题 {len(leaves)} 道超过单次建议上限 "
                f"{proposal_rules.MAX_ITEMS} 道；请先整理草稿后再发起（不静默截断）。",
                fields=["items"],
            )
        allowed_points = await _threaded(self._active_points, paper.subject_id)
        frozen_input = {
            "contractVersion": proposal_rules.PROPOSAL_CONTRACT_VERSION,
            "paperId": paper.paper_id,
            "paperRevisionId": revision.revision_id,
            "baseRevision": paper.revision,
            "subjectId": paper.subject_id,
            "title": paper.title,
            "modelProfileId": profile_id,
            "allowedItemIds": [item.item_id for item in leaves],
            "allowedKnowledgePointIds": [point["id"] for point in allowed_points],
            "allowedKnowledgePoints": allowed_points,
            "items": [
                {
                    "itemId": item.item_id,
                    "questionNo": item.question_no,
                    "maxScore": _score_text(item.max_score_units),
                    "stemText": _stem_text(item.content),
                }
                for item in leaves
            ],
        }
        model_snapshot = await self._freeze_model_snapshot(profile_id)
        store = self._job_engine.store("teaching")
        record = await _threaded(
            store.create,
            kind="paper_mapping",
            frozen_input=frozen_input,
            model_snapshot=model_snapshot,
            owner_id=self._owner_id,
        )
        # 首次调度与公共 retry 走**同一份**执行器（``_paper_mapping_executor``）
        self._job_engine.schedule(
            "teaching",
            record.job_id,
            self._paper_mapping_executor(),
            uses_model=True,
        )
        return record.view()

    def register_job_executors(self, registry: Any) -> None:
        """把原卷 AI 建议执行器注册进公共注册表（B3/G0 · B2-RV01）。

        公共 ``POST /workflow-jobs/{id}/retry`` 经此调度；factory 只依赖任务行
        （``frozen_input`` / ``model_snapshot``），重试**不重新冻结**输入与指纹，执行体与
        首次调度完全同一份（``_paper_mapping_executor``）：调用前用冻结快照核对真实配置
        指纹（缺指纹 422 ``MODEL_FINGERPRINT_MISSING`` / 漂移 409 ``MODEL_CONFIG_DRIFT``，
        不调用模型、不发布），候选写入仍与任务 ``succeeded`` 同事务（``publish``）。
        未注册的类型由注册表返回 ``False``：任务保持 ``queued``，用户可再次 retry。
        """
        registry.register(
            "teaching",
            "paper_mapping",
            uses_model=True,
            factory=lambda _record: self._paper_mapping_executor(),
        )

    def _paper_mapping_executor(self) -> ProposalRunner:
        """原卷 AI 建议执行器（首次调度与 retry 唯一实现，含冻结指纹核对与同事务发布）。"""
        return ProposalRunner(
            resolve_model=self._resolve_model_for_job,
            publish_proposal=self._publish_proposal,
        )

    def get_proposal(self, proposal_id: str) -> PaperProposalView:
        proposal_id = _clean_text(proposal_id, field="proposalId")
        with self._catalog.read_connection() as conn:
            proposal = self._papers.require_proposal_in(conn, proposal_id)
            if proposal.target_kind != "paper_revision":
                raise AppError(
                    "该建议不是原卷建议。", code=PAPER_PROPOSAL_NOT_FOUND, status_code=404
                )
            stale = self._proposal_stale_in(conn, proposal)
        return self._render_proposal(proposal, stale=stale)

    def apply_proposal(
        self, proposal_id: str, payload: PaperProposalDecisionRequest
    ) -> PaperRevisionContentView:
        proposal_id = _clean_text(proposal_id, field="proposalId")
        if not payload.selections:
            raise _issue_error(
                "没有选择任何建议，无法应用。",
                code=PAPER_PROPOSAL_INVALID,
                status_code=422,
                issues=[
                    _issue(None, code=PAPER_PROPOSAL_INVALID, message="至少选择一条建议。", field="selections")
                ],
            )
        with self._coordinator.publication(operation="paper.proposal.apply"):
            with self._catalog.read_connection() as conn:
                proposal = self._papers.require_proposal_in(conn, proposal_id)
                if proposal.target_kind != "paper_revision":
                    raise AppError(
                        "该建议不是原卷建议。",
                        code=PAPER_PROPOSAL_NOT_FOUND,
                        status_code=404,
                    )
                revision = self._papers.require_revision_in(conn, proposal.target_id)
                paper = self._papers.require_paper_in(conn, revision.paper_id)
                revision_items = self._papers.list_items_in(conn, revision.revision_id)
            self._require_proposal_pending(proposal)
            if paper.revision != payload.expected_revision:
                raise _stale_conflict(paper.revision)
            if paper.status == "archived":
                raise self._not_editable("原卷已归档")
            if revision.state != "draft":
                raise self._not_editable("只有草稿修订可以应用建议")
            if paper.revision != proposal.base_revision:
                raise self._proposal_stale_error(paper.revision)
            selections = self._validate_selections(proposal, revision_items, payload)
            refs = self._load_knowledge_refs(
                paper.subject_id, [entry["knowledgePointId"] for entry in selections]
            )
            try:
                with self._catalog.write_transaction() as conn:
                    paper = self._papers.require_paper_in(conn, paper.paper_id)
                    if paper.revision != payload.expected_revision:
                        raise _stale_conflict(paper.revision)
                    revision = self._current_revision_in(conn, paper)
                    if revision.revision_id != proposal.target_id:
                        raise self._proposal_stale_error(paper.revision)
                    if paper.revision != proposal.base_revision:
                        raise self._proposal_stale_error(paper.revision)
                    if revision.state != "draft":
                        raise self._not_editable("只有草稿修订可以应用建议")
                    existing = {
                        (item.item_id, entry.knowledge_point_id)
                        for item in self._papers.list_items_in(conn, revision.revision_id)
                        for entry in item.knowledge
                    }
                    applied = 0
                    for entry in selections:
                        key = (entry["itemId"], entry["knowledgePointId"])
                        if key in existing:
                            continue  # 已有同题同知识点关联：不覆盖、不重复
                        ref = refs[entry["knowledgePointId"]]
                        self._papers.insert_item_knowledge_in(
                            conn,
                            item_id=entry["itemId"],
                            paper_revision_id=revision.revision_id,
                            knowledge=(
                                ItemKnowledgeRecord(
                                    knowledge_point_id=ref.point_id,
                                    knowledge_revision_id=ref.revision_id,
                                    knowledge_name_snapshot=ref.name,
                                    role="primary",
                                    source="ai_confirmed",
                                ),
                            ),
                        )
                        existing.add(key)
                        applied += 1
                    self._papers.set_proposal_state_in(conn, proposal.proposal_id, "applied")
                    self._papers.bump_revision_in(conn, paper.paper_id)
                    paper = self._papers.require_paper_in(conn, paper.paper_id)
                    revision = self._papers.require_revision_in(conn, revision.revision_id)
                    return self._render_content_in(conn, paper, revision)
            except sqlite3.IntegrityError as exc:
                raise _translate_integrity_error(exc) from exc

    def reject_proposal(
        self, proposal_id: str, payload: PaperProposalDecisionRequest
    ) -> PaperProposalView:
        # 拒绝只关建议状态、不改草稿内容：因此不核 expectedRevision（过期建议也可清理）
        proposal_id = _clean_text(proposal_id, field="proposalId")
        with self._catalog.write_transaction() as conn:
            proposal = self._papers.require_proposal_in(conn, proposal_id)
            if proposal.target_kind != "paper_revision":
                raise AppError(
                    "该建议不是原卷建议。", code=PAPER_PROPOSAL_NOT_FOUND, status_code=404
                )
            self._require_proposal_pending(proposal)
            self._papers.set_proposal_state_in(conn, proposal.proposal_id, "rejected")
            updated = self._papers.require_proposal_in(conn, proposal.proposal_id)
            stale = self._proposal_stale_in(conn, updated)
        return self._render_proposal(updated, stale=stale)

    def confirmed_reader(self) -> ConfirmedPaperReaderAdapter:
        return self._reader

    # ---------------------------------------------------------------- 内部：公共

    def _paper_view(self, summary) -> PaperView:
        return PaperView(
            paperId=summary.paper_id,
            subjectId=summary.subject_id,
            title=summary.title,
            status=summary.status,
            revision=summary.revision,
            currentRevisionId=summary.current_revision_id,
            currentState=summary.current_state,
            version=summary.version,
            totalScoreUnits=summary.total_score_units,
            totalScore=_score_text(summary.total_score_units),
            itemCount=summary.item_count,
            scoredLeafCount=summary.scored_leaf_count,
            blockingIssueCount=summary.blocking_issue_count,
            createdAt=summary.created_at,
        )

    def _render_content_in(
        self, conn: sqlite3.Connection, paper: PaperRecord, revision: RevisionRecord
    ) -> PaperRevisionContentView:
        items = self._papers.list_items_in(conn, revision.revision_id)
        blocks = self._papers.list_blocks_in(conn, revision.revision_id)
        issues = self._papers.list_issues_in(conn, revision.revision_id)
        return PaperRevisionContentView(
            paperId=paper.paper_id,
            paperRevisionId=revision.revision_id,
            version=revision.version,
            state=revision.state,
            subjectId=paper.subject_id,
            # B3/G0 · B2-RV11：固定修订读自己的标题快照，不读可变 papers.title
            title=revision.title_snapshot,
            totalScoreUnits=revision.total_score_units,
            totalScore=_score_text(revision.total_score_units),
            confirmedAt=revision.confirmed_at,
            createdAt=revision.created_at,
            items=[
                PaperItemView(
                    itemId=item.item_id,
                    parentItemId=item.parent_item_id,
                    questionNo=item.question_no,
                    ordinal=item.ordinal,
                    isScored=item.is_scored,
                    maxScoreUnits=item.max_score_units,
                    maxScore=(
                        _score_text(item.max_score_units)
                        if item.max_score_units is not None
                        else None
                    ),
                    content=dict(item.content),
                    sourceLocator=dict(item.source_locator),
                    knowledge=[
                        PaperItemKnowledgeView(
                            knowledgePointId=entry.knowledge_point_id,
                            knowledgeRevisionId=entry.knowledge_revision_id,
                            knowledgeNameSnapshot=entry.knowledge_name_snapshot,
                            role=entry.role,
                            source=entry.source,
                        )
                        for entry in item.knowledge
                    ],
                )
                for item in items
            ],
            blocks=[
                PaperSourceBlockView(
                    blockId=block.block_id,
                    ordinal=block.ordinal,
                    kind=block.kind,
                    locator=dict(block.locator),
                    disposition=block.disposition,
                    itemId=block.item_id,
                    excludeReason=block.exclude_reason,
                    # B3/G0 · B2-RV03：返回持久化块内容（未归属块也有正文可审阅）
                    content=dict(block.block),
                )
                for block in blocks
            ],
            issues=[
                PaperIssueView(
                    issueId=issue.issue_id,
                    code=issue.code,
                    severity=issue.severity,
                    message=issue.message,
                    blockId=issue.block_id,
                    locator=dict(issue.locator),
                    status=issue.status,
                    resolution=dict(issue.resolution) if issue.resolution else None,
                )
                for issue in issues
            ],
        )

    def _current_revision_in(
        self, conn: sqlite3.Connection, paper: PaperRecord
    ) -> RevisionRecord:
        if paper.current_revision_id is None:
            raise AppError(
                "该原卷还没有修订。", code=PAPER_NOT_FOUND, status_code=404
            )
        return self._papers.require_revision_of_paper_in(
            conn, paper.paper_id, paper.current_revision_id
        )

    def _require_editable_paper(self, paper: PaperRecord) -> None:
        if paper.status == "archived":
            raise self._not_editable("原卷已归档")

    @staticmethod
    def _not_editable(detail: str) -> AppError:
        return AppError(
            f"{detail}：不能修改或确认；请先恢复。", code=PAPER_NOT_EDITABLE, status_code=409
        )

    def _set_paper_title_in(
        self, conn: sqlite3.Connection, paper_id: str, title: str
    ) -> None:
        clean = _clean_text(title, field="title", maximum=MAX_TITLE_CHARS)
        conn.execute("UPDATE papers SET title = ? WHERE id = ?", (clean, paper_id))

    # ---------------------------------------------------------------- 内部：草稿写

    def _fork_draft_in(
        self, conn: sqlite3.Connection, paper: PaperRecord, source: RevisionRecord
    ) -> tuple[RevisionRecord, RevisionCopyMap]:
        """已确认修订不可写：新建 version+1 的草稿修订并逐行复制内容（旧修订不变）。

        返回新草稿与逐行 id 映射：客户端请求仍以旧修订的 itemId/blockId/issueId 表达时，
        由调用方经映射翻译到新草稿（同一份编辑意图，不要求客户端先刷新）。
        """
        if source.source_practice_revision_id is not None:
            raise AppError("请从固定练习审核版建立新草稿，再转换新原卷。", code="PRACTICE_PAPER_EDIT_REQUIRES_NEW_REVISION", status_code=422)
        version = self._papers.next_version_in(conn, paper.paper_id)
        draft = self._papers.create_revision_in(
            conn,
            paper_id=paper.paper_id,
            version=version,
            source_file_id=source.source_file_id,
            total_score_units=source.total_score_units,
            title_snapshot=paper.title,
            title_snapshot_source="revision",
        )
        copied = self._papers.copy_revision_content_in(
            conn, source_revision_id=source.revision_id, target_revision_id=draft.revision_id
        )
        self._papers.set_current_revision_in(conn, paper.paper_id, draft.revision_id)
        return draft, copied

    def _replace_items_in(
        self,
        conn: sqlite3.Connection,
        revision: RevisionRecord,
        payload_items: Sequence[PaperItemInput],
        refs: Mapping[str, _KnowledgeRef],
        *,
        id_map: RevisionCopyMap | None = None,
    ) -> None:
        existing = self._papers.list_items_in(conn, revision.revision_id)
        existing_ids = {item.item_id for item in existing}
        provided = [item.item_id for item in payload_items if item.item_id is not None]
        normalized = self._normalize_items(
            payload_items,
            existing_ids=existing_ids,
            taken_ids=self._papers.taken_item_ids_in(conn, provided) - existing_ids,
            refs=refs,
            id_map=id_map.item_map if id_map is not None else None,
        )
        self._papers.delete_items_in(conn, revision.revision_id)
        self._papers.insert_items_in(
            conn,
            paper_revision_id=revision.revision_id,
            items=[item.as_row() for item in _parents_first(normalized)],
        )
        for item in normalized:
            self._papers.insert_item_knowledge_in(
                conn,
                item_id=item.item_id,
                paper_revision_id=revision.revision_id,
                knowledge=item.knowledge,
            )
        reset = self._papers.clear_block_item_refs_in(
            conn,
            paper_revision_id=revision.revision_id,
            keep_item_ids=[item.item_id for item in normalized],
        )
        total = sum(
            int(item.max_score_units or 0) for item in normalized if item.is_scored
        )
        self._papers.set_revision_total_in(conn, revision.revision_id, total)
        if reset:
            self._papers.insert_issues_in(
                conn,
                paper_revision_id=revision.revision_id,
                issues=[
                    {
                        "code": BLOCK_ITEM_RESET,
                        "severity": "warning",
                        "message": (
                            f"整表替换题目后有 {reset} 个原文块的归属题目被删除，已重置为未归属；"
                            "请重新指定归属。"
                        ),
                        "block_id": None,
                        "locator": {},
                    }
                ],
            )

    def _apply_blocks_in(
        self,
        conn: sqlite3.Connection,
        revision: RevisionRecord,
        patches: Sequence[PaperBlockPatch],
        *,
        id_map: RevisionCopyMap | None = None,
    ) -> None:
        copied = _copied_maps(id_map)
        blocks = {block.block_id: block for block in self._papers.list_blocks_in(conn, revision.revision_id)}
        item_ids = {item.item_id for item in self._papers.list_items_in(conn, revision.revision_id)}
        issues: list[ErrorIssue] = []
        for row, patch in enumerate(patches):
            block_id = copied["block"].get(patch.block_id, patch.block_id)
            block = blocks.get(block_id)
            if block is None:
                issues.append(
                    _issue(
                        row,
                        code=PAPER_BLOCK_INVALID,
                        message=f"原文块 {patch.block_id} 不在该修订内。",
                        field="blockId",
                    )
                )
                continue
            item_id = (
                copied["item"].get(patch.item_id, patch.item_id)
                if patch.item_id is not None
                else None
            )
            exclude_reason = patch.exclude_reason
            if patch.disposition == "item":
                if item_id is None or item_id not in item_ids:
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_BLOCK_INVALID,
                            message="归属 item 时必须给出本修订内存在的 itemId。",
                            field="itemId",
                        )
                    )
                    continue
                exclude_reason = None
            elif patch.disposition == "excluded":
                if not isinstance(exclude_reason, str) or not exclude_reason.strip():
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_BLOCK_INVALID,
                            message="排除块必须给出非空 excludeReason。",
                            field="excludeReason",
                        )
                    )
                    continue
                item_id = None
            else:
                if item_id is not None or exclude_reason is not None:
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_BLOCK_INVALID,
                            message="shared_material/unassigned 不能携带 itemId 或 excludeReason。",
                            field="disposition",
                        )
                    )
                    continue
                item_id = None
                exclude_reason = None
            self._papers.update_block_in(
                conn,
                paper_revision_id=revision.revision_id,
                block_id=block_id,
                disposition=patch.disposition,
                item_id=item_id,
                exclude_reason=exclude_reason,
            )
        _raise_first("原文块处置不合法。", issues)

    def _apply_issues_in(
        self,
        conn: sqlite3.Connection,
        revision: RevisionRecord,
        patches: Sequence[PaperIssuePatch],
        *,
        id_map: RevisionCopyMap | None = None,
    ) -> None:
        """问题处置（B3/G0 · B2-RV02）：结构化 resolution + 真实补录副作用。

        - ``resolved``/``excluded`` 都必须带 ``resolution``（缺 → 阻断问题保持
          ``PAPER_ISSUE_BLOCKING``，其余问题 ``PAPER_ISSUE_RESOLUTION_INVALID``）；
        - ``supplement_text`` 追加进目标段落块的 ``block_json``（内容真的发生变化）；
          ``supplement_asset`` 核验受管资产字节散列后在目标块后插入图片块；
        - ``exclude`` 只允许**非内容损失**的问题码，且必须有理由；
        - 任一条不合法都逐条报告（``details.issues`` 带 row/field），整批随事务回滚。
        """
        copied = _copied_maps(id_map)
        blocks = {
            block.block_id: block
            for block in self._papers.list_blocks_in(conn, revision.revision_id)
        }
        issues: list[ErrorIssue] = []
        for row, patch in enumerate(patches):
            issue_id = copied["issue"].get(patch.issue_id, patch.issue_id)
            record = self._papers.get_issue_in(conn, revision.revision_id, issue_id)
            if record is None:
                issues.append(
                    _issue(
                        row,
                        code=PAPER_ISSUE_NOT_FOUND,
                        message=f"问题 {patch.issue_id} 不在该修订内（可能已被刷新）。",
                        field="issueId",
                    )
                )
                continue
            if patch.status == "open":
                if patch.resolution is not None:
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_ISSUE_RESOLUTION_INVALID,
                            message="把问题置回 open 时不能携带处置；请改为 resolved/excluded。",
                            field="resolution",
                        )
                    )
                    continue
                self._papers.update_issue_in(
                    conn,
                    paper_revision_id=revision.revision_id,
                    issue_id=issue_id,
                    status="open",
                    resolution=None,
                )
                continue
            resolution = patch.resolution
            if resolution is None:
                if record.severity == "blocking":
                    # 既有语义（B2 测试依赖）：阻断问题必须有处置，field=resolution
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_ISSUE_BLOCKING,
                            message=(
                                "解决或排除阻断问题必须给出结构化处置"
                                "（supplement_text/supplement_asset/exclude）。"
                            ),
                            field="resolution",
                        )
                    )
                else:
                    issues.append(
                        _issue(
                            row,
                            code=PAPER_ISSUE_RESOLUTION_INVALID,
                            message="解决或排除问题必须给出结构化处置。",
                            field="resolution",
                        )
                    )
                continue
            rejected = self._apply_resolution_in(
                conn,
                revision,
                record,
                resolution,
                blocks,
                block_map=copied["block"],
                row=row,
            )
            if rejected:
                issues.extend(rejected)
                continue
            payload = resolution.model_dump(by_alias=True, exclude_none=True)
            target = payload.get("targetBlockId")
            if isinstance(target, str):
                # 客户端可能仍以旧修订的块 id 表达（自动 fork 后）：落库为**本修订**的 id
                payload["targetBlockId"] = copied["block"].get(target, target)
            self._papers.update_issue_in(
                conn,
                paper_revision_id=revision.revision_id,
                issue_id=issue_id,
                status=patch.status,
                resolution=payload,
            )
        _raise_first("问题处置不合法。", issues)

    def _apply_resolution_in(
        self,
        conn: sqlite3.Connection,
        revision: RevisionRecord,
        record,
        resolution: PaperIssueResolution,
        blocks: Mapping[str, BlockRecord],
        *,
        block_map: Mapping[str, str],
        row: int,
    ) -> list[ErrorIssue]:
        """校验并执行一条结构化处置；返回逐条可定位的拒绝原因（空列表 = 已执行）。"""

        def reject(code: str, message: str, field: str | None) -> ErrorIssue:
            return _issue(row, code=code, message=message, field=field)

        kind = resolution.kind
        raw_target = (resolution.target_block_id or "").strip()
        target = block_map.get(raw_target, raw_target)
        text = (resolution.text or "").strip()
        asset_key = (resolution.asset_id or "").strip()
        reason = (resolution.reason or "").strip()
        rejected: list[ErrorIssue] = []

        if kind == "supplement_text":
            if not target:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录文本必须给出 targetBlockId（要补录进哪个原文块）。",
                        "targetBlockId",
                    )
                )
            if not text:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录文本的 text 不能为空。",
                        "text",
                    )
                )
            if resolution.asset_id is not None or resolution.reason is not None:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录文本不能携带 assetId/reason；请按 kind 只填对应字段。",
                        "kind",
                    )
                )
        elif kind == "supplement_asset":
            if not target:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录资产必须给出 targetBlockId（图片补录到哪个块之后）。",
                        "targetBlockId",
                    )
                )
            if not asset_key:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录资产的 assetId 不能为空。",
                        "assetId",
                    )
                )
            elif not is_managed_blob_key(asset_key):
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录资产的 assetId 必须是受管键 blobs/<64 位小写 hex>。",
                        "assetId",
                    )
                )
            if resolution.text is not None or resolution.reason is not None:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "补录资产不能携带 text/reason；请按 kind 只填对应字段。",
                        "kind",
                    )
                )
        else:  # exclude
            if not reason:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "排除问题必须给出理由 reason。",
                        "reason",
                    )
                )
            if record.code in CONTENT_LOSS_ISSUE_CODES:
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        f"{record.code} 属于内容损失，必须补录内容（supplement_text/"
                        "supplement_asset），不能仅以排除放行。",
                        "kind",
                    )
                )
            if (
                resolution.target_block_id is not None
                or resolution.text is not None
                or resolution.asset_id is not None
            ):
                rejected.append(
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        "排除不能携带 targetBlockId/text/assetId；请按 kind 只填对应字段。",
                        "kind",
                    )
                )
        if rejected:
            return rejected
        if kind == "exclude":
            # 排除只关问题状态（理由已校验），不触碰任何块；内容损失码已在上面拒绝
            return []

        block = self._find_block(blocks, target)
        if block is None:
            return [
                reject(
                    PAPER_ISSUE_RESOLUTION_INVALID,
                    f"目标原文块 {target} 不在该修订内（可能已被刷新）。",
                    "targetBlockId",
                )
            ]
        if kind == "supplement_text":
            if block.kind != "paragraph":
                return [
                    reject(
                        PAPER_ISSUE_RESOLUTION_INVALID,
                        f"目标块是 {block.kind} 块，不能追加文本；请选择段落块"
                        "（表格/公式/图片请用 supplement_asset 补录）。",
                        "targetBlockId",
                    )
                ]
            existing = block.block.get("text")
            merged = (
                f"{existing}\n{text}" if isinstance(existing, str) and existing.strip() else text
            )
            updated = {**block.block, "text": merged}
            self._papers.update_block_payload_in(
                conn,
                paper_revision_id=revision.revision_id,
                block_id=block.block_id,
                block=updated,
            )
            return []
        # supplement_asset
        try:
            # ``AssetStore.read`` 按文件名重算 sha256：字节与受管键不符 → ASSET_CORRUPT
            self._assets.read(asset_key)
        except AppError as exc:
            return [
                reject(
                    PAPER_ISSUE_RESOLUTION_INVALID,
                    f"补录资产不可读（{exc.code}）：{exc}",
                    "assetId",
                )
            ]
        payload_id = f"{SUPPLEMENT_BLOCK_PREFIX}{uuid.uuid4().hex[:16]}"
        payload = {
            "id": payload_id,
            "kind": "image",
            "assetId": asset_key,
            "width": SUPPLEMENT_IMAGE_SIZE,
            "height": SUPPLEMENT_IMAGE_SIZE,
        }
        self._papers.insert_block_after_in(
            conn,
            paper_revision_id=revision.revision_id,
            after_block_id=block.block_id,
            block=payload,
            kind="image",
            disposition=block.disposition,
            item_id=block.item_id,
            locator=dict(block.locator),
        )
        return []

    @staticmethod
    def _find_block(
        blocks: Mapping[str, BlockRecord], identifier: str
    ) -> BlockRecord | None:
        """按行 id 或解析器 payload id 找块（客户端可能持有旧修订 id 或块内 id）。"""
        if not identifier:
            return None
        found = blocks.get(identifier)
        if found is not None:
            return found
        for block in blocks.values():
            payload_id = block.block.get("id")
            if isinstance(payload_id, str) and payload_id == identifier:
                return block
        return None

    # ---------------------------------------------------------------- 内部：校验

    def _normalize_items(
        self,
        payload_items: Sequence[PaperItemInput],
        *,
        existing_ids: set[str],
        refs: Mapping[str, _KnowledgeRef],
        id_map: Mapping[str, str] | None = None,
        taken_ids: set[str] | None = None,
    ) -> list[_NormalizedItem]:
        """整表替换前的归一化与可定位校验。

        ``id_map`` 只在"改已确认卷自动新建草稿修订"时给出：客户端仍以旧修订的
        ``itemId``/``parentItemId`` 表达同一份编辑意图，这里翻译到新草稿的行 id；
        ``itemId`` 也可以由客户端**为新建题目指定**（只要该 id 尚未被任何修订占用），
        否则新建父容器与子题的父子关系无从表达。
        """
        mapping = dict(id_map or {})
        taken = set(taken_ids or ())

        def resolve(identifier: str | None) -> str | None:
            if identifier is None:
                return None
            return mapping.get(identifier, identifier)

        issues: list[ErrorIssue] = []
        prepared: list[tuple[int, PaperItemInput, str, str | None]] = []
        seen_ids: set[str] = set()
        for row, item in enumerate(payload_items):
            if item.item_id is not None:
                item_id = resolve(item.item_id) or item.item_id
                if item_id in seen_ids:
                    issues.append(
                        _issue(row, code=ITEM_ID_INVALID, message="itemId 在请求里重复。", field="itemId")
                    )
                    continue
                if item_id not in existing_ids and item_id in taken:
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_ID_INVALID,
                            message="itemId 已被其他修订占用（题目 id 全局唯一，不能跨修订复用）。",
                            field="itemId",
                        )
                    )
                    continue
                seen_ids.add(item_id)
            else:
                item_id = uuid.uuid4().hex
                seen_ids.add(item_id)
            prepared.append((row, item, item_id, resolve(item.parent_item_id)))
        _raise_first("草稿题目不合法。", issues)

        by_id = {item_id: item for _row, item, item_id, _parent in prepared}
        parent_of = {item_id: parent for _row, _item, item_id, parent in prepared}
        issues = []
        seen_no: dict[str, int] = {}
        seen_ordinal: dict[int, int] = {}
        for row, item, item_id, parent_id in prepared:
            question_no = item.question_no.strip()
            if question_no in seen_no:
                issues.append(
                    _issue(
                        row,
                        code=ITEM_QUESTION_NO_DUPLICATE,
                        message=f"题号 {question_no} 与第 {seen_no[question_no]} 行重复。",
                        field="questionNo",
                    )
                )
            else:
                seen_no[question_no] = row
            if item.ordinal in seen_ordinal:
                issues.append(
                    _issue(
                        row,
                        code=ITEM_ORDINAL_DUPLICATE,
                        message=f"序号 {item.ordinal} 与第 {seen_ordinal[item.ordinal]} 行重复。",
                        field="ordinal",
                    )
                )
            else:
                seen_ordinal[item.ordinal] = row
            if parent_id is not None:
                if parent_id == item_id:
                    issues.append(
                        _issue(row, code=ITEM_PARENT_INVALID, message="题目不能把自己作为父题。", field="parentItemId")
                    )
                elif parent_id not in by_id:
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_PARENT_INVALID,
                            message="父题必须在本批题目内（整表替换）。",
                            field="parentItemId",
                        )
                    )
        _raise_first("草稿题目不合法。", issues)

        # 环检测：沿父链上溯，遇到自身或超过深度即视为成环
        for row, _item, item_id, parent_id in prepared:
            seen: set[str] = set()
            current = parent_id
            while current is not None:
                if current == item_id or current in seen or len(seen) > len(prepared):
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_CYCLE,
                            message="父子关系会形成环。",
                            field="parentItemId",
                        )
                    )
                    break
                seen.add(current)
                parent = by_id.get(current)
                current = parent_of.get(current) if parent is not None else None
        _raise_first("草稿题目不合法。", issues)

        children: dict[str, int] = {}
        for _row, _item, _item_id, parent_id in prepared:
            if parent_id is not None:
                children[parent_id] = children.get(parent_id, 0) + 1

        normalized: list[_NormalizedItem] = []
        for row, item, item_id, parent_id in prepared:
            max_score_units: int | None = None
            if item.is_scored:
                if children.get(item_id):
                    issues.append(
                        _issue(
                            row,
                            code=SCORED_ITEM_MUST_BE_LEAF,
                            message="有子题的题目不能计分（只有叶子计分）。",
                            field="isScored",
                        )
                    )
                if item.max_score is None:
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_SCORE_INVALID,
                            message="计分题必须给出 maxScore。",
                            field="maxScore",
                        )
                    )
                else:
                    try:
                        max_score_units = _parse_score_units(item.max_score)
                    except AppError as exc:
                        issues.append(
                            _issue(
                                row,
                                code=ITEM_SCORE_INVALID,
                                message=str(exc),
                                field="maxScore",
                            )
                        )
            else:
                if item.max_score is not None:
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_SCORE_INVALID,
                            message="不计分的容器不能带 maxScore。",
                            field="maxScore",
                        )
                    )
            knowledge_entries: list[ItemKnowledgeRecord] = []
            seen_points: set[str] = set()
            for entry in item.knowledge:
                if entry.knowledge_point_id in seen_points:
                    issues.append(
                        _issue(
                            row,
                            code=ITEM_KNOWLEDGE_DUPLICATE,
                            message=f"知识点 {entry.knowledge_point_id} 在同一题重复关联。",
                            field="knowledge",
                        )
                    )
                    continue
                seen_points.add(entry.knowledge_point_id)
                ref = refs.get(entry.knowledge_point_id)
                if ref is None:
                    issues.append(
                        _issue(
                            row,
                            code=KNOWLEDGE_REFERENCE_INVALID,
                            message=f"知识点 {entry.knowledge_point_id} 不存在、已归档或不属于该卷学科。",
                            field="knowledge",
                        )
                    )
                    continue
                knowledge_entries.append(
                    ItemKnowledgeRecord(
                        knowledge_point_id=ref.point_id,
                        knowledge_revision_id=ref.revision_id,
                        knowledge_name_snapshot=ref.name,
                        role=entry.role,
                        source="human",
                    )
                )
            normalized.append(
                _NormalizedItem(
                    item_id=item_id,
                    parent_item_id=parent_id,
                    question_no=item.question_no.strip(),
                    ordinal=item.ordinal,
                    is_scored=item.is_scored,
                    max_score_units=max_score_units,
                    content=dict(item.content),
                    source_locator=dict(item.source_locator),
                    knowledge=tuple(knowledge_entries),
                )
            )
        _raise_first("草稿题目不合法。", issues)
        return normalized

    def _validate_item_tree(self, items: Sequence[ItemRecord]) -> None:
        """确认前的兜底结构校验（题号唯一/序号唯一/无环/只有叶子计分/分值>0）。"""
        issues: list[ErrorIssue] = []
        seen_no: dict[str, int] = {}
        seen_ordinal: dict[int, int] = {}
        for item in items:
            if item.question_no in seen_no:
                issues.append(
                    _issue(
                        item.ordinal,
                        code=ITEM_QUESTION_NO_DUPLICATE,
                        message=f"题号 {item.question_no} 重复。",
                        field="questionNo",
                    )
                )
            else:
                seen_no[item.question_no] = item.ordinal
            if item.ordinal in seen_ordinal:
                issues.append(
                    _issue(
                        item.ordinal,
                        code=ITEM_ORDINAL_DUPLICATE,
                        message=f"序号 {item.ordinal} 重复。",
                        field="ordinal",
                    )
                )
            else:
                seen_ordinal[item.ordinal] = item.ordinal
        by_id = {item.item_id: item for item in items}
        children = _child_counts(items)
        for item in items:
            seen: set[str] = set()
            current = item.parent_item_id
            while current is not None:
                if current == item.item_id or current in seen or len(seen) > len(items):
                    issues.append(
                        _issue(
                            item.ordinal,
                            code=ITEM_CYCLE,
                            message="父子关系会形成环。",
                            field="parentItemId",
                        )
                    )
                    break
                seen.add(current)
                parent = by_id.get(current)
                if parent is None:
                    issues.append(
                        _issue(
                            item.ordinal,
                            code=ITEM_PARENT_INVALID,
                            message="父题不在同一修订内。",
                            field="parentItemId",
                        )
                    )
                    break
                current = parent.parent_item_id
            if item.is_scored and children.get(item.item_id):
                issues.append(
                    _issue(
                        item.ordinal,
                        code=SCORED_ITEM_MUST_BE_LEAF,
                        message="有子题的题目不能计分。",
                        field="isScored",
                    )
                )
            if item.is_scored and (item.max_score_units is None or item.max_score_units <= 0):
                issues.append(
                    _issue(
                        item.ordinal,
                        code=ITEM_SCORE_INVALID,
                        message="计分题缺少正整数满分。",
                        field="maxScore",
                    )
                )
        _raise_first("草稿结构不合法，不能确认。", issues)

    def _validate_leaf_substance_in(
        self,
        conn: sqlite3.Connection,
        revision: RevisionRecord,
        scored_leaves: Sequence[ItemRecord],
    ) -> None:
        """确认闸门（B3/G0 · B2-RV02）：计分叶必须有实质题面且材料/资产引用未丢失。

        - ``content.stemBlocks`` 至少含一个**有可见内容**的块（段落文本/表格单元格/
          公式/图片资产任一非空）；空 ``{}`` 或只有空段落一律拒绝；
        - 富内容 ``sharedMaterials[].blocks[].id`` 与 ``assets[].assetId`` 必须能在
          **本修订**的块集合里找到（共同材料被删除/未补录 → 拒绝）。
        不要求答案、解析或评分点。
        """
        blocks = self._papers.list_blocks_in(conn, revision.revision_id)
        persisted_ids: set[str] = set()
        persisted_asset_ids: set[str] = set()
        for block in blocks:
            persisted_ids.add(block.block_id)
            payload_id = block.block.get("id")
            if isinstance(payload_id, str) and payload_id:
                persisted_ids.add(payload_id)
            if block.kind == "image":
                asset_id = block.block.get("assetId")
                if isinstance(asset_id, str) and asset_id:
                    persisted_asset_ids.add(asset_id)

        issues: list[ErrorIssue] = []
        for item in scored_leaves:
            content = item.content if isinstance(item.content, dict) else {}
            stem_blocks = content.get("stemBlocks")
            if not _stem_has_substance(stem_blocks):
                issues.append(
                    _issue(
                        item.ordinal,
                        code=ITEM_STEM_MISSING,
                        message=(
                            f"题 {item.question_no} 是计分小题但没有实质题面"
                            "（stemBlocks 为空或不含可见内容）；请补全题干后再确认。"
                        ),
                        field="content",
                    )
                )
                continue
            missing_materials: list[str] = []
            for material in content.get("sharedMaterials") or []:
                if not isinstance(material, dict):
                    continue
                for block in material.get("blocks") or []:
                    if not isinstance(block, dict):
                        continue
                    block_id = block.get("id")
                    if isinstance(block_id, str) and block_id and block_id not in persisted_ids:
                        missing_materials.append(block_id)
            missing_assets: list[str] = []
            for asset in content.get("assets") or []:
                if not isinstance(asset, dict):
                    continue
                asset_id = asset.get("assetId")
                if (
                    isinstance(asset_id, str)
                    and asset_id
                    and asset_id not in persisted_asset_ids
                ):
                    missing_assets.append(asset_id)
            if missing_materials or missing_assets:
                issues.append(
                    _issue(
                        item.ordinal,
                        code=ITEM_MATERIAL_MISSING,
                        message=(
                            f"题 {item.question_no} 的题面引用了本修订不存在的"
                            f"共同材料/资产：{[*missing_materials, *missing_assets]}；"
                            "请补录必要共同材料后再确认。"
                        ),
                        field="content",
                    )
                )
        _raise_first("计分小题题面不完整，不能确认。", issues)

    def _load_knowledge_refs(
        self, subject_id: str, point_ids: Sequence[str]
    ) -> dict[str, _KnowledgeRef]:
        """跨库只读校验：存在、同学科、未归档（写事务外、发布临界区内执行）。"""
        unique: list[str] = []
        seen: set[str] = set()
        for point_id in point_ids:
            if point_id in seen:
                continue
            seen.add(point_id)
            unique.append(point_id)
        if not unique:
            return {}
        if self._knowledge is None:
            raise AppError(
                "知识点库未装配，无法校验知识点关联；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        refs: dict[str, _KnowledgeRef] = {}
        invalid: list[str] = []
        with self._knowledge.read_connection() as conn:
            for point_id in unique:
                point = self._points.get_point(conn, point_id)
                if point is None or point.status != "active" or point.subject_id != subject_id:
                    invalid.append(point_id)
                    continue
                refs[point_id] = _KnowledgeRef(
                    point_id=point.point_id,
                    revision_id=point.revision_id,
                    name=point.name,
                    code=point.code,
                )
        if invalid:
            # 一次报出全部非法引用（逐条可定位），不因第一条失败就吞掉其余问题
            raise self._knowledge_reference_error(invalid, subject_id=subject_id)
        return refs

    @staticmethod
    def _knowledge_reference_error(point_ids: Sequence[str], *, subject_id: str) -> AppError:
        return _issue_error(
            "知识点关联非法：必须存在、未归档且与该卷同学科。",
            code=KNOWLEDGE_REFERENCE_INVALID,
            status_code=422,
            issues=[
                _issue(
                    None,
                    code=KNOWLEDGE_REFERENCE_INVALID,
                    message=f"知识点 {point_id} 不存在、已归档或不属于学科 {subject_id}。",
                    field="knowledgePointId",
                )
                for point_id in point_ids
            ],
        )

    def _active_points(self, subject_id: str) -> list[dict[str, Any]]:
        if self._knowledge is None:
            raise AppError(
                "知识点库未装配，无法列出可用知识点；请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        # 全量分页取回该学科 active 知识点（提示词只渲染前 MAX_ALLOWED_POINTS 条，
        # 但"允许集合"必须完整，否则合法既有知识点会被无谓地判为越界）
        points: list[PointRecord] = []
        offset = 0
        page_size = 200
        with self._knowledge.read_connection() as conn:
            while True:
                page, total = self._points.list_points(
                    conn,
                    subject_id=subject_id,
                    status="active",
                    offset=offset,
                    limit=page_size,
                )
                points.extend(page)
                offset += page_size
                if len(points) >= total or not page:
                    break
        return [
            {
                "id": point.point_id,
                "code": point.code,
                "name": point.name,
                "revisionId": point.revision_id,
            }
            for point in points
        ]

    # ---------------------------------------------------------------- 内部：AI 建议

    async def _freeze_model_snapshot(self, profile_id: str) -> dict[str, Any]:
        """冻结任务模型快照：``profileId`` + **非敏感指纹**（不含凭证）。

        解析失败（配置不存在/不可调用）按解析器的稳定错误码向上抛，不落一个"没有指纹"
        的任务；指纹用 ``fingerprint_of_handle``（与执行期核对同一实现）。
        """
        snapshot: dict[str, Any] = {
            "profileId": profile_id,
            "fingerprint": "",
            "contractVersion": proposal_rules.PROPOSAL_CONTRACT_VERSION,
        }
        if self._model_resolver is None or not callable(self._model_resolver):
            raise AppError(
                "原卷 AI 建议未装配模型解析器（model_resolver），无法冻结模型指纹；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        handle = await _threaded(self._model_resolver, profile_id)
        if not isinstance(handle, ChatModelHandle):
            raise AppError(
                "模型解析器返回的句柄不符合契约，已停止创建建议任务。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
            )
        snapshot["fingerprint"] = fingerprint_of_handle(handle)
        return snapshot

    async def _resolve_model_for_job(self, snapshot: Mapping[str, object]) -> ChatModelHandle:
        """按**冻结快照**解析本次调用模型（B3/G0 · B2-RV04）。

        装配了原始仓储/凭证时直接用公共 ``resolve_frozen_model``（缺指纹 422 /
        漂移 409）；只装配 resolver 时按 profileId 解析，由 ``ProposalRunner`` 用
        ``fingerprint_of_handle`` 做同一份核对（错误码与拒绝语义一致）。
        """
        profile_id = str(
            snapshot.get("profileId") or snapshot.get("modelProfileId") or ""
        ).strip()
        frozen = str(
            snapshot.get("fingerprint") or snapshot.get("modelFingerprint") or ""
        ).strip()
        if not frozen:
            # 旧任务/无指纹快照：明确失败，要求重新发起（``ProposalRunner`` 亦会兜底复核）
            raise AppError(
                "任务缺少可核对的冻结模型指纹；请重新发起建议（旧任务不自动重放）。",
                code=MODEL_FINGERPRINT_MISSING,
                status_code=422,
            )
        if self._model_config_repo is not None and self._secret_store is not None:
            return await _threaded(
                resolve_frozen_model,
                self._model_config_repo,
                self._secret_store,
                snapshot,
                auth_service=self._model_auth_service,
            )
        return await _threaded(
            proposal_rules.resolve_model_for_job, self._model_resolver, profile_id
        )

    def _publish_proposal(self, conn: sqlite3.Connection, draft: ProposalDraft) -> None:
        """在任务结果发布事务内写 ``ai_proposals``；草稿版本变化即 409（整批回滚）。"""
        paper = self._papers.get_paper_in(conn, draft.paper_id)
        if paper is None:
            raise AppError("原卷不存在。", code=PAPER_NOT_FOUND, status_code=404)
        if paper.revision != draft.base_revision:
            raise self._proposal_stale_error(paper.revision)
        if paper.current_revision_id != draft.paper_revision_id:
            raise self._proposal_stale_error(paper.revision)
        revision = self._papers.require_revision_in(conn, draft.paper_revision_id)
        if revision.state != "draft":
            raise self._not_editable("只有草稿修订可以写入建议")
        payload = {
            "contractVersion": proposal_rules.PROPOSAL_CONTRACT_VERSION,
            "paperId": draft.paper_id,
            "paperRevisionId": draft.paper_revision_id,
            "baseRevision": draft.base_revision,
            "subjectId": draft.subject_id,
            "items": [item.payload() for item in draft.items],
            "rawItems": [dict(item) for item in draft.raw_items],
            "model": dict(draft.model),
            "allowedItemIds": list(draft.allowed_item_ids),
            "allowedKnowledgePointIds": list(draft.allowed_point_ids),
        }
        self._papers.create_proposal_in(
            conn,
            job_id=draft.job_id,
            target_revision_id=draft.paper_revision_id,
            base_revision=draft.base_revision,
            payload=payload,
            proposal_id=draft.proposal_id,
        )

    def _validate_selections(
        self,
        proposal: ProposalRecord,
        items: Sequence[ItemRecord],
        payload: PaperProposalDecisionRequest,
    ) -> list[dict[str, str]]:
        proposed: dict[str, str | None] = {}
        for entry in proposal.payload.get("items") or []:
            if isinstance(entry, dict) and isinstance(entry.get("itemId"), str):
                proposed[entry["itemId"]] = entry.get("knowledgePointId")
        by_id = {item.item_id: item for item in items}
        issues: list[ErrorIssue] = []
        selections: list[dict[str, str]] = []
        for row, selection in enumerate(payload.selections):
            item = by_id.get(selection.item_id)
            if item is None or not item.is_scored:
                issues.append(
                    _issue(
                        row,
                        code=PAPER_PROPOSAL_INVALID,
                        message="选择引用了不属于该修订的计分小题。",
                        field="itemId",
                    )
                )
                continue
            if proposed.get(selection.item_id) != selection.knowledge_point_id:
                issues.append(
                    _issue(
                        row,
                        code=PAPER_PROPOSAL_INVALID,
                        message="选择与建议内容不一致（题目与知识点的对应关系不符）。",
                        field="knowledgePointId",
                    )
                )
                continue
            selections.append(
                {
                    "itemId": selection.item_id,
                    "knowledgePointId": selection.knowledge_point_id,
                }
            )
        _raise_first("应用建议的选择不合法。", issues)
        return selections

    def _proposal_stale_in(self, conn: sqlite3.Connection, proposal: ProposalRecord) -> bool:
        if proposal.state != "pending":
            return False
        revision = self._papers.get_revision_in(conn, proposal.target_id)
        if revision is None:
            return True
        paper = self._papers.get_paper_in(conn, revision.paper_id)
        if paper is None:
            return True
        return (
            paper.revision != proposal.base_revision
            or paper.current_revision_id != proposal.target_id
            or revision.state != "draft"
        )

    def _require_proposal_pending(self, proposal: ProposalRecord) -> None:
        if proposal.state != "pending":
            raise AppError(
                f"建议当前状态为 {proposal.state}，不能再应用或拒绝。",
                code=PAPER_PROPOSAL_INVALID,
                status_code=409,
            )

    @staticmethod
    def _proposal_stale_error(current: int) -> AppError:
        return AppError(
            "草稿已被更新，该建议已过期；请重新发起建议。",
            code=PAPER_PROPOSAL_STALE,
            status_code=409,
            details=error_details(current_revision=current),
        )

    def _render_proposal(self, proposal: ProposalRecord, *, stale: bool) -> PaperProposalView:
        items: list[PaperProposalItemView] = []
        for entry in proposal.payload.get("items") or []:
            if not isinstance(entry, dict):
                continue
            items.append(
                PaperProposalItemView(
                    itemId=str(entry.get("itemId") or ""),
                    questionNo=str(entry.get("questionNo") or ""),
                    knowledgePointId=entry.get("knowledgePointId"),
                    proposedCode=entry.get("proposedCode"),
                    proposedName=entry.get("proposedName"),
                    evidence=[str(value) for value in entry.get("evidence") or []],
                    ambiguity=bool(entry.get("ambiguity", False)),
                )
            )
        return PaperProposalView(
            proposalId=proposal.proposal_id,
            jobId=proposal.job_id,
            state=proposal.state,
            baseRevision=proposal.base_revision,
            stale=stale,
            items=items,
            issues=[],
            createdAt=proposal.created_at,
        )


# --------------------------------------------------------------------------- 模块级工具


def _copied_maps(
    id_map: RevisionCopyMap | None,
) -> dict[str, Mapping[str, str]]:
    """把逐行 id 映射拆成按对象类别取用的三张表（无 fork 时全为空）。"""
    if id_map is None:
        return {"item": {}, "block": {}, "issue": {}}
    return {"item": id_map.item_map, "block": id_map.block_map, "issue": id_map.issue_map}


def _parents_first(items: Sequence[_NormalizedItem]) -> list[_NormalizedItem]:
    """父题先于子题返回（外键写入顺序友好；事务内已 defer 外键，此处只求稳定）。"""
    depth: dict[str, int] = {}
    by_id = {item.item_id: item for item in items}
    for item in items:
        level = 0
        current = item.parent_item_id
        while current is not None and level <= len(items):
            level += 1
            parent = by_id.get(current)
            current = parent.parent_item_id if parent is not None else None
        depth[item.item_id] = level
    return sorted(items, key=lambda item: (depth[item.item_id], item.ordinal))


def _stem_text(content: Mapping[str, Any]) -> str:
    """从富内容快照里取题干可见文本（供 AI 建议；只读、不猜）。"""
    pieces: list[str] = []
    for block in content.get("stemBlocks") or []:
        if not isinstance(block, dict):
            continue
        if block.get("kind") == "paragraph":
            pieces.append(str(block.get("text") or ""))
        elif block.get("kind") == "table":
            for cell in block.get("cells") or []:
                if isinstance(cell, dict) and cell.get("text"):
                    pieces.append(str(cell["text"]))
        elif block.get("kind") == "formula":
            pieces.append("[公式]")
        elif block.get("kind") == "image":
            pieces.append("[图片]")
    return "\n".join(piece for piece in pieces if piece)


def _stem_has_substance(stem_blocks: object) -> bool:
    """题干块列表里是否存在可见内容（段落文本/表格单元格/公式/图片资产）。"""
    if not isinstance(stem_blocks, list) or not stem_blocks:
        return False
    for block in stem_blocks:
        if not isinstance(block, dict):
            continue
        kind = block.get("kind")
        if kind == "paragraph":
            if str(block.get("text") or "").strip():
                return True
        elif kind == "table":
            for cell in block.get("cells") or []:
                if isinstance(cell, dict) and str(cell.get("text") or "").strip():
                    return True
        elif kind == "formula":
            if str(block.get("latex") or "").strip() or str(
                block.get("ommlXml") or ""
            ).strip():
                return True
        elif kind == "image":
            if str(block.get("assetId") or "").strip():
                return True
    return False


def _image_media_type(data: bytes) -> str:
    """按字节魔数给出图片 media type（受控资产内容路由用；不认识 → 八位字节流）。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return "application/octet-stream"


def analysis_warnings(analysis) -> list[str]:
    """导入响应里的可见告警：T10 告警 + 解析损失（未知对象等）的可读提示。"""
    return [
        f"{issue.code}：{issue.message}"
        for issue in analysis.issues
        if issue.severity in ("blocking", "info")
    ]


def build_paper_service(
    teaching_catalog: TeachingCatalog,
    *,
    asset_store: AssetStore,
    file_assets: FileAssetsRepository,
    knowledge_catalog: Any | None,
    coordinator: PublicationCoordinator,
    model_resolver: Any | None,
    job_engine: Any | None,
    model_config_repo: Any | None = None,
    secret_store: Any | None = None,
    model_auth_service: Any | None = None,
) -> PaperService:
    """原卷服务工厂（CTRL 装配入口）；依赖为 ``None`` 时对应能力 503，不降级成假成功。

    ``model_config_repo`` / ``secret_store`` 可选：给出时 AI 建议执行器直接用公共
    ``resolve_frozen_model`` 核对冻结指纹；未给出时用注入的 ``model_resolver`` 解析后
    按同一份 ``fingerprint_of_handle`` 规则核对（缺指纹/漂移的错误码与拒绝语义一致）。
    """
    return PaperService(
        teaching_catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        knowledge_catalog=knowledge_catalog,
        coordinator=coordinator,
        model_resolver=model_resolver,
        job_engine=job_engine,
        model_config_repo=model_config_repo,
        secret_store=secret_store,
        model_auth_service=model_auth_service,
    )


__all__ = ["PaperService", "build_paper_service"]
