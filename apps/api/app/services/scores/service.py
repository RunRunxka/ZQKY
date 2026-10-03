"""成绩服务门面（TEACHING-LOOP B3 / T60）。

装配：``build_score_service(catalog, *, asset_store, file_assets, assessment_service,
paper_reader, publication_coordinator)``（签名由 B3 任务卡冻结，CTRL 的 ``app.main`` 调用）。
所有 SQL 只经 ``ScoreRepository`` 与 ``AssessmentRepository``，文件解析统一走
``read_score_sheet``（公式视图 + data_only 缓存视图，不重算公式），资产本体走 ``AssetStore``，
登记走 ``FileAssetsRepository``；解析/文件 IO 一律在数据库事务外，写事务内只做 SQL。

关键语义（与冻结契约 ``app/contracts/scores.py`` 一致）：

- **上传即预览**：原件落受管资产（``kind='score_sheet'``），行写入
  ``score_import_rows.raw_cells_json``（物理行列 + 两视图 + 是否公式）；表头自动识别映射到
  已确认原卷的计分叶 ``question_no`` / 题号路径，识别不了的留给教师 PATCH。
- **四态**：0=recorded(0)、空=missing、缺考=absent、免考=exempt；Decimal 文本 ×100 整数；
  非 recorded 不得有分；缺行/缺列/未映射叶显式 missing，绝不补 0；越界 422
  ``SCORE_CELL_OVER_MAX``（带原表物理 row/column）。
- **行定位**：显式 ``participantId`` → 学号文本（前导零保留）→ 姓名；同名/多个人次等
  多义行给候选并要求人工指定，服务端不猜。
- **确认（单事务）**：重放优先（``submissionId``）→ 三版本校验（导入锁 / 施测锁 / active=base）
  → 阻断问题与承认范围校验（``SCORE_ACKNOWLEDGEMENT_MISMATCH``）→ 在
  ``PublicationCoordinator`` 内重读参测人次与原卷叶 → draft 修订 + 全矩阵 + 快照 → 封存
  （DB 闸门按该修订自己的快照核完整性）→ active + 施测版本 +1 → 导入 confirmed + 幂等结果。
- **修正**：base 必须等于当前 active（否则 409 ``SCORE_NO_BASE_REVISION`` /
  ``SCORE_BASE_REVISION_CONFLICT``）；从不可变 base 复制全矩阵 + 修正当时参测快照生成新完整
  版本，审计（原值/新值/理由）逐条落 ``score_revision_corrections``；同样 ``submissionId`` 幂等。
- **读**：修订视图含冻结快照；矩阵分页 ``items`` 不分页（固定叶）、``rows`` 分页；
  ``totalUnits`` 只在该人次全 recorded 时非空；missing/absent 口径与确认预览一致。
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping, Sequence

from app.contracts.scores import (
    SCORE_ACKNOWLEDGEMENT_MISMATCH,
    SCORE_ASSESSMENT_REVISION_CONFLICT,
    SCORE_BASE_REVISION_CONFLICT,
    SCORE_CELL_INVALID,
    SCORE_CORRECTION_INVALID,
    SCORE_IMPORT_NOT_EDITABLE,
    SCORE_IMPORT_REVISION_CONFLICT,
    SCORE_ITEM_UNKNOWN,
    SCORE_MAPPING_INVALID,
    SCORE_MATRIX_INCOMPLETE,
    SCORE_NO_BASE_REVISION,
    SCORE_PARTICIPANT_UNKNOWN,
    SCORE_REVISION_NOT_FOUND,
    ScoreAbsenceAcknowledgement,
    ScoreColumnMapping,
    ScoreImportConfirmRequest,
    ScoreImportConfirmResult,
    ScoreImportList,
    ScoreImportRefreshRequest,
    ScoreImportRowList,
    ScoreImportRowView,
    ScoreImportSummary,
    ScoreImportView,
    ScoreItemSnapshot,
    ScoreMatrixPage,
    ScoreParticipantSnapshot,
    ScorePreviewAcknowledgements,
    ScoreMissingAcknowledgement,
    ScoreRawCellView,
    ScoreRevisionCorrectRequest,
    ScoreRevisionCorrectResult,
    ScoreRevisionList,
    ScoreRevisionView,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.assessments import AssessmentRepository, ParticipantRecord
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.scores import (
    DEFAULT_OWNER_ID,
    MAX_PAGE_LIMIT,
    AssessmentContext,
    RawCellRecord,
    RowPayload,
    ScoreCorrectionRecord,
    ScoreImportRecord,
    ScoreRepository,
)
from app.services.assets.store import AssetStore
from app.services.scores import imports as analysis
from app.contracts.scores import ScoreImportPatchRequest
from app.services.scores.imports import CellInput, Leaf, ParticipantRef, PreviewMatrix
from app.services.scores.matrix import build_matrix_page
from app.services.submissions.service import execute_command, make_command
from app.services.tabular import read_score_sheet

#: 提交幂等身份里的操作名（与 roster/assessments 同表：``command_submissions``）
CONFIRM_OPERATION = "score_import.confirm"
CORRECT_OPERATION = "score_revision.correct"

#: 可编辑（尚未确认）的批次状态
EDITABLE_IMPORT_STATES: frozenset[str] = frozenset({"uploaded", "reviewing"})

DEFAULT_MEDIA_TYPE = "application/octet-stream"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
ASSESSMENT_NOT_FOUND = "ASSESSMENT_NOT_FOUND"
SCORE_ROW_CORRUPT = "SCORE_ROW_CORRUPT"
_ASSET_MISSING = "ASSET_MISSING"
_DEFAULT_MAX_COLUMNS = 16384


# --------------------------------------------------------------------------- 小工具


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。", fields=[field])
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    text = value.strip() if isinstance(value, str) else ""
    return text or None


def _page(offset: object, limit: object) -> tuple[int, int]:
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise _invalid("offset 必须是不小于 0 的整数。", fields=["offset"])
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or limit > MAX_PAGE_LIMIT
    ):
        raise _invalid(f"limit 必须是 1..{MAX_PAGE_LIMIT} 的整数。", fields=["limit"])
    return offset, limit


def _invalid(message: str, *, fields: list[str] | None = None) -> AppError:
    return AppError(
        message,
        code="INVALID_REQUEST",
        status_code=422,
        details=error_details(fields=fields) if fields else None,
    )


def _issue(
    row: int | None,
    *,
    code: str,
    message: str,
    column: str | None = None,
    field: str | None = None,
) -> ErrorIssue:
    return ErrorIssue(row=row, column=column, field=field, code=code, message=message)


def _issues_error(
    message: str, *, code: str, status_code: int, issues: Sequence[ErrorIssue]
) -> AppError:
    return AppError(
        message,
        code=code,
        status_code=status_code,
        details=error_details(issues=list(issues)),
    )


def _require_editable(record: ScoreImportRecord) -> None:
    if record.state == "confirmed":
        raise AppError(
            "该成绩批次已确认，不能再修改或再次确认（重放请使用相同 submissionId）。",
            code=SCORE_IMPORT_NOT_EDITABLE,
            status_code=409,
        )
    if record.state not in EDITABLE_IMPORT_STATES:
        raise AppError(
            f"批次状态为 {record.state}，不允许修改或确认。",
            code=SCORE_IMPORT_NOT_EDITABLE,
            status_code=409,
        )


def _check_import_revision(current: int, expected: int) -> None:
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
        raise _invalid("expectedRevision 必须是不小于 0 的整数。", fields=["expectedRevision"])
    if current != expected:
        raise AppError(
            "成绩导入批次已被其他操作更新，请刷新后重试。",
            code=SCORE_IMPORT_REVISION_CONFLICT,
            status_code=409,
            details=error_details(current_revision=current),
        )


def _assessment_conflict(current: int) -> AppError:
    return AppError(
        "施测已被其他操作更新（参测人次/版本变化），请刷新后重试。",
        code=SCORE_ASSESSMENT_REVISION_CONFLICT,
        status_code=409,
        details=error_details(current_revision=current),
    )


def _base_conflict(message: str, *, field: str = "baseScoreRevisionId") -> AppError:
    return _issues_error(
        message,
        code=SCORE_BASE_REVISION_CONFLICT,
        status_code=409,
        issues=[
            _issue(
                None,
                code=SCORE_BASE_REVISION_CONFLICT,
                message="本次导入所基于的正式成绩版本已不是当前 active；请刷新后重试。",
                field=field,
            )
        ],
    )


def _check_preview_context(record: ScoreImportRecord, context: AssessmentContext) -> None:
    """A normal edit may not replace the frozen assessment/base with a fresh one."""
    if record.summary.get("assessmentRevision") != context.revision:
        raise _assessment_conflict(context.revision)
    if record.base_score_revision_id != context.active_score_revision_id:
        raise _base_conflict("当前 active/base 已变化；校对未写入，请新建导入。")


def _raise_cell_errors(preview: PreviewMatrix) -> None:
    """上传/校对阶段的**解析**错误一律 422（带原表物理 row/column），不静默落 missing。

    语义冲突（缺考与数值同时出现、标记与快照矛盾）不在这里阻断：它们落预览成为阻断问题，
    由确认前的检查拒绝，教师可按原表坐标 PATCH 校正后重建预览。
    """
    if not preview.parse_errors:
        return
    first = preview.parse_errors[0]
    raise _issues_error(
        "成绩表格存在无法解析的单元格；本次修改未生效，请修正原表后重试。",
        code=first.code or SCORE_CELL_INVALID,
        status_code=422,
        issues=preview.parse_errors,
    )


def _raw_cells(cells: Sequence[analysis.SheetCell]) -> tuple[RawCellRecord, ...]:
    return tuple(
        RawCellRecord(
            row=cell.row,
            column=cell.letter,
            text=cell.text,
            cached_text=cell.cached_text,
            is_formula=cell.is_formula,
        )
        for cell in cells
    )


def _cell_inputs_of(cells: Sequence[RawCellRecord]) -> dict[str, CellInput]:
    inputs: dict[str, CellInput] = {}
    for cell in cells:
        text = cell.parse_input()
        inputs[cell.column] = CellInput(
            row=cell.row,
            column=cell.column,
            text=text,
            blank=text.strip() == "",
            # 教师校正值是字面量；未校正的公式格用缓存视图文本
            is_formula=cell.is_formula and not cell.has_correction(),
        )
    return inputs


def _extracted_to_payload(
    row: analysis.ExtractedRow, *, preview: PreviewMatrix | None
) -> RowPayload:
    issues: tuple[ErrorIssue, ...] = ()
    if preview is not None:
        match = preview.row_matches.get(row.row_no)
        issues = match.issues if match is not None else ()
    return RowPayload(
        row_no=row.row_no, participant_id=None, cells=_raw_cells(row.cells), issues=issues
    )


# --------------------------------------------------------------------------- 服务


class ScoreService:
    """成绩导入 / 确认 / 修正 / 只读矩阵的用例入口。"""

    def __init__(
        self,
        catalog: TeachingCatalog,
        *,
        asset_store: AssetStore | None,
        file_assets: FileAssetsRepository | None,
        assessment_service: Any | None = None,
        paper_reader: Any | None = None,
        publication_coordinator: Any | None = None,
        owner_id: str = DEFAULT_OWNER_ID,
    ) -> None:
        self._catalog = catalog
        self._asset_store = asset_store
        self._file_assets = file_assets
        #: 施测读取的共享端口（交叉读取参测人次/标题；为 None 时回退本人持有仓储）
        self._assessment_service = assessment_service
        self._paper_reader = paper_reader
        self._coordinator = publication_coordinator
        self._owner_id = owner_id
        self._scores = ScoreRepository(catalog)
        self._assessments = AssessmentRepository(catalog)

    # ---------------------------------------------------------------- 依赖闸门

    def _require_assets(self) -> tuple[AssetStore, FileAssetsRepository]:
        if self._asset_store is None or self._file_assets is None:
            raise AppError(
                "成绩服务缺少受管资产装配：无法上传/读取成绩原件，请检查启动日志与依赖。",
                code=SERVICE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        return self._asset_store, self._file_assets

    def _require_coordinator(self) -> Any:
        if self._coordinator is None:
            raise AppError(
                "成绩服务缺少发布协调器装配：无法确认/修正成绩，请检查启动日志与依赖。",
                code=SERVICE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        return self._coordinator

    # ---------------------------------------------------------------- 读取辅助

    def _assessment_context(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> AssessmentContext:
        context = self._scores.assessment_context_in(conn, assessment_id)
        if context is None:
            raise AppError(
                f"施测不存在：{assessment_id}。",
                code=ASSESSMENT_NOT_FOUND,
                status_code=404,
            )
        return context

    def _participants(
        self, conn: sqlite3.Connection, assessment_id: str
    ) -> tuple[ParticipantRef, ...]:
        records = self._assessments.list_participants_in(conn, assessment_id)
        return tuple(_ref_from_record(record) for record in records)

    def _leaves(self, paper_revision_id: str) -> tuple[Leaf, ...]:
        reader = self._paper_reader
        if reader is None:
            raise AppError(
                "成绩服务缺少已确认原卷读取端口：无法确定固定计分叶，请检查启动日志与依赖。",
                code=SERVICE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        method = getattr(reader, "read", None)
        if not callable(method):
            raise AppError(
                "已确认原卷读取端口缺少 read()，无法确定固定计分叶。",
                code=SERVICE_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        snapshot = method(_text(paper_revision_id, field="paperRevisionId"))
        items = {item.item_id: item for item in snapshot.items}

        def path_of(item: Any) -> str:
            # Practice nodes already carry the teacher's complete final number.
            # File papers retain their existing hierarchical relative labels.
            if getattr(snapshot, "source_practice_revision_id", None) is not None:
                return item.question_no
            parts = [item.question_no]
            parent = item.parent_item_id
            seen: set[str] = set()
            while parent and parent in items and parent not in seen:
                seen.add(parent)
                ancestor = items[parent]
                parts.append(ancestor.question_no)
                parent = ancestor.parent_item_id
            return "/".join(reversed(parts))

        leaves = [
            analysis.build_leaf(
                item_id=item.item_id,
                question_no=item.question_no,
                item_path=path_of(item),
                ordinal=item.ordinal,
                max_score_units=item.max_score_units,
            )
            for item in snapshot.scored_leaves
        ]
        leaves.sort(key=lambda leaf: (leaf.ordinal, leaf.item_id))
        if not leaves:
            raise AppError(
                "已确认原卷没有计分叶子，无法建立成绩矩阵。",
                code=SCORE_MATRIX_INCOMPLETE,
                status_code=422,
            )
        return tuple(leaves)

    def _mapping_of(self, record: ScoreImportRecord) -> ScoreColumnMapping | None:
        if record.mapping is None:
            return None
        try:
            return analysis.normalize_mapping(ScoreColumnMapping.model_validate(record.mapping))
        except Exception as exc:
            raise AppError(
                f"教学库数据损坏：批次 {record.import_id} 的列映射结构不符。",
                code=SCORE_ROW_CORRUPT,
                status_code=500,
            ) from exc

    def _row_inputs(
        self, record: ScoreImportRecord, mapping: ScoreColumnMapping
    ) -> tuple[analysis.RowInput, ...]:
        rows: list[analysis.RowInput] = []
        for row in record.rows:
            cells = _cell_inputs_of(row.cells)
            for entry in mapping.item_columns:
                letter = entry.column.upper()
                cells.setdefault(
                    letter, CellInput(row=row.row_no, column=letter, text="", blank=True)
                )
            for column in (mapping.student_no_column, mapping.name_column, mapping.total_column, mapping.attendance_column):
                if column:
                    cells.setdefault(
                        column.upper(),
                        CellInput(
                            row=row.row_no, column=column.upper(), text="", blank=True
                        ),
                    )
            rows.append(
                analysis.RowInput(
                    row_no=row.row_no,
                    explicit_participant_id=row.participant_id,
                    cells=cells,
                )
            )
        return tuple(rows)

    def _preview(
        self,
        record: ScoreImportRecord,
        *,
        mapping: ScoreColumnMapping | None,
        participants: Sequence[ParticipantRef],
        leaves: Sequence[Leaf],
    ) -> PreviewMatrix | None:
        if mapping is None:
            return None
        return analysis.build_preview(
            participants=participants,
            leaves=leaves,
            mapping=mapping,
            rows=self._row_inputs(record, mapping),
        )

    def _sheet_meta(self, record: ScoreImportRecord) -> dict[str, Any]:
        sheet = record.summary.get("sheet")
        return sheet if isinstance(sheet, dict) else {}

    def _mapping_warnings(
        self,
        record: ScoreImportRecord,
        *,
        mapping: ScoreColumnMapping | None,
        leaves: Sequence[Leaf],
    ) -> tuple[str, ...]:
        """映射相关提示：保留上传时的表头歧义提示，未映射叶数量按当前映射重算。"""
        stored = record.summary.get("mappingWarnings")
        kept = [
            item
            for item in (stored if isinstance(stored, list) else [])
            if isinstance(item, str) and not item.startswith("有 ")
        ]
        warning = analysis.unmapped_leaves_warning(
            leaf_count=len(leaves),
            mapped_count=len({entry.item_id for entry in mapping.item_columns})
            if mapping is not None
            else 0,
        )
        if warning:
            kept.append(warning)
        return tuple(kept)

    def _sheet_warnings(self, record: ScoreImportRecord) -> tuple[str, ...]:
        value = record.summary.get("sheetWarnings")
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, str))

    def _sheet_bounds(self, record: ScoreImportRecord) -> tuple[int, int]:
        sheet = self._sheet_meta(record)
        max_row = sheet.get("maxRow")
        max_column = sheet.get("maxColumn")
        row = max_row if isinstance(max_row, int) and not isinstance(max_row, bool) else 0
        column = (
            max_column
            if isinstance(max_column, int) and not isinstance(max_column, bool)
            else 0
        )
        return max(1, row), column or _DEFAULT_MAX_COLUMNS

    # ---------------------------------------------------------------- 上传/预览

    def create_score_import(
        self,
        assessment_id: str,
        *,
        file_name: str,
        content: bytes,
        media_type: str = "",
        work_sheet: str | None = None,
        base_score_revision_id: str | None = None,
    ) -> ScoreImportView:
        """上传教师 XLSX 小题得分 → 解析 → 预览持久化（一次写事务）。"""
        asset_store, file_assets = self._require_assets()
        assessment_id = _text(assessment_id, field="assessmentId")
        file_name = _text(file_name, field="fileName")
        media_type = (media_type or "").strip() or DEFAULT_MEDIA_TYPE
        work_sheet = _optional_text(work_sheet, field="workSheet")
        base_provided = _optional_text(base_score_revision_id, field="baseScoreRevisionId")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise _invalid("上传的成绩文件为空。", fields=["file"])

        with self._catalog.read_connection() as conn:
            context = self._assessment_context(conn, assessment_id)
            participants = self._participants(conn, assessment_id)
        if base_provided is not None and base_provided != context.active_score_revision_id:
            raise _base_conflict("上传时给出的 baseScoreRevisionId 不是当前 active 成绩版本。")
        base = base_provided if base_provided is not None else context.active_score_revision_id

        # 解析（事务外，绝不进写事务）
        sheets = read_score_sheet(bytes(content), sheet_name=work_sheet)
        sheet_warnings: list[str] = []
        warnings: list[str] = []
        grid = analysis.sheet_grid(sheets[0])
        if len(sheets) > 1:
            sheet_warnings.append(
                f"文件含 {len(sheets)} 个工作表，仅处理第一个「{grid.name}」；"
                "如需其他工作表请指定 workSheet 并重新上传。"
            )
        leaves = self._leaves(context.paper_revision_id)
        auto = analysis.auto_map(grid, leaves)
        warnings.extend(auto.warnings)
        mapping = auto.mapping
        preview: PreviewMatrix | None = None
        if mapping is not None:
            analysis.validate_mapping(
                mapping,
                sheet_name=grid.name,
                max_row=grid.max_row,
                max_column=grid.max_column,
                leaves=leaves,
            )
            extracted = analysis.extract_rows(
                grid, header_row=mapping.header_row, mapping=mapping
            )
            row_inputs = tuple(
                analysis.RowInput(
                    row_no=row.row_no,
                    explicit_participant_id=None,
                    cells={
                        cell.letter: CellInput(
                            row=cell.row,
                            column=cell.letter,
                            text=cell.parse_input(),
                            blank=cell.parse_input().strip() == "",
                            is_formula=cell.is_formula,
                        )
                        for cell in row.cells
                    },
                )
                for row in extracted
            )
            preview = analysis.build_preview(
                participants=participants, leaves=leaves, mapping=mapping, rows=row_inputs
            )
            _raise_cell_errors(preview)
            warnings.extend(preview.warnings)
            payloads = [
                _extracted_to_payload(row, preview=preview) for row in extracted
            ]
        else:
            header_row = analysis.detect_header_row(grid) or 1
            payloads = [
                _extracted_to_payload(row, preview=None)
                for row in analysis.extract_raw_rows(grid, header_row=header_row)
            ]
            warnings.append(
                "还没有可用的列映射；请先指定学号/姓名列与计分列后才能确认。"
            )

        summary = self._summary_payload(
            context=context,
            sheet={
                "name": grid.name,
                "maxRow": grid.max_row,
                "maxColumn": grid.max_column,
                "headerRow": mapping.header_row if mapping is not None else None,
            },
            preview=preview,
            warnings=warnings,
            base=base,
            row_count=len(payloads),
            sheet_warnings=sheet_warnings,
            item_ids=[leaf.item_id for leaf in leaves],
            mapping_warnings=auto.warnings,
        )
        stored = asset_store.store_original(
            bytes(content), media_type=media_type, original_name=file_name
        )
        with self._catalog.write_transaction() as conn:
            asset = file_assets.create_in(
                conn,
                kind="score_sheet",
                blob_key=stored.blob_key,
                sha256=stored.sha256,
                media_type=media_type,
                byte_size=stored.byte_size,
                original_name=file_name,
            )
            record = self._scores.create_import_in(
                conn,
                assessment_id=assessment_id,
                file_asset_id=asset.asset_id,
                base_score_revision_id=base,
                work_sheet=grid.name,
                mapping=(
                    mapping.model_dump(by_alias=True) if mapping is not None else None
                ),
                summary=summary,
                rows=payloads,
            )
            import_id = record.import_id
        return self.get_score_import(import_id)

    def _summary_payload(
        self,
        *,
        context: AssessmentContext,
        sheet: Mapping[str, Any] | None,
        preview: PreviewMatrix | None,
        warnings: Sequence[str],
        base: str | None,
        row_count: int,
        sheet_warnings: Sequence[str] = (),
        item_ids: Sequence[str] = (),
        mapping_warnings: Sequence[str] = (),
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "warnings": list(warnings),
            "sheetWarnings": list(sheet_warnings),
            "mappingWarnings": list(mapping_warnings),
            "updatedAt": now_iso(),
            "assessmentRevision": context.revision,
            "baseScoreRevisionId": base,
            "rowCount": row_count,
        }
        if item_ids:
            payload["itemIds"] = list(item_ids)
        if sheet:
            payload["sheet"] = dict(sheet)
        if preview is not None:
            payload["issues"] = [issue.model_dump(exclude_none=True) for issue in preview.blocking_issues]
            payload["preview"] = {
                "participantCount": preview.participant_count,
                "resolvedRowCount": sum(
                    1 for pid in preview.row_participant.values() if pid is not None
                ),
                "missingCellCount": preview.missing_cell_count,
                "missingParticipantIds": list(preview.missing_participant_ids),
                "absentByClass": {
                    class_id: list(ids)
                    for class_id, ids in preview.absent_by_class.items()
                },
            }
        return payload

    # ---------------------------------------------------------------- 批次读取

    def get_score_import(self, import_id: str) -> ScoreImportView:
        with self._catalog.read_connection() as conn:
            record = self._scores.require_in(conn, import_id)
            context = self._assessment_context(conn, record.assessment_id)
            participants = self._participants(conn, record.assessment_id)
        return self._render_import(
            record,
            context=context,
            participants=participants,
            frozen=record.state == "confirmed",
        )

    def list_score_imports(
        self, *, assessment_id: str | None = None, offset: int = 0, limit: int = 50
    ) -> ScoreImportList:
        offset, limit = _page(offset, limit)
        assessment_filter = _optional_text(assessment_id, field="assessmentId")
        with self._catalog.read_connection() as conn:
            records, total = self._scores.list_in(
                conn, assessment_id=assessment_filter, offset=offset, limit=limit
            )
        return ScoreImportList(
            items=[
                ScoreImportSummary(
                    importId=record.import_id,
                    assessmentId=record.assessment_id,
                    state=record.state,
                    revision=record.revision,
                    rowCount=record.row_count,
                    createdAt=record.created_at,
                    updatedAt=record.updated_at,
                )
                for record in records
            ],
            total=total,
            offset=offset,
            limit=limit,
        )

    def list_score_import_rows(
        self, import_id: str, *, offset: int = 0, limit: int = 50
    ) -> ScoreImportRowList:
        offset, limit = _page(offset, limit)
        with self._catalog.read_connection() as conn:
            record = self._scores.require_in(conn, import_id)
            context = self._assessment_context(conn, record.assessment_id)
            participants = self._participants(conn, record.assessment_id)
        mapping = self._mapping_of(record)
        preview: PreviewMatrix | None = None
        if (mapping is not None and record.state != "confirmed"
                and record.summary.get("assessmentRevision") == context.revision
                and record.base_score_revision_id == context.active_score_revision_id):
            preview = self._preview(
                record,
                mapping=mapping,
                participants=participants,
                leaves=self._leaves(context.paper_revision_id),
            )
        return self._render_rows(
            record,
            mapping=mapping,
            preview=preview,
            participants=participants,
            offset=offset,
            limit=limit,
        )

    # ---------------------------------------------------------------- 校对 PATCH

    def patch_score_import(
        self, import_id: str, payload: ScoreImportPatchRequest
    ) -> ScoreImportView:
        """生效的映射/行定位/单元格校正：CAS + 重算预览 + ``revision``/``previewVersion`` 各 +1。"""
        import_id = _text(import_id, field="importId")
        if payload.mapping is None and not payload.rows:
            raise _invalid(
                "补丁必须包含 mapping 或 rows 至少一项。", fields=["mapping", "rows"]
            )
        with self._catalog.read_connection() as conn:
            record = self._scores.require_in(conn, import_id)
            _require_editable(record)
            _check_import_revision(record.revision, payload.expected_revision)
            context = self._assessment_context(conn, record.assessment_id)
            _check_preview_context(record, context)
            participants = self._participants(conn, record.assessment_id)
        leaves = self._leaves(context.paper_revision_id)
        current_mapping = self._mapping_of(record)
        new_mapping = analysis.normalize_mapping(payload.mapping) if payload.mapping is not None else current_mapping
        sheet_meta = dict(self._sheet_meta(record))
        max_row, max_column = self._sheet_bounds(record)

        rebuild = False
        if payload.mapping is not None:
            if new_mapping.work_sheet != (record.work_sheet or ""):
                rebuild = True
            elif current_mapping is None:
                rebuild = True
            elif new_mapping != current_mapping:
                # 表头、身份/计分/元数据列都能改变有效物理行集合，必须从原件重提取。
                rebuild = True
            else:
                analysis.validate_mapping(
                    new_mapping,
                    sheet_name=str(sheet_meta.get("name") or record.work_sheet or ""),
                    max_row=max_row,
                    max_column=max_column,
                    leaves=leaves,
                )
        rebuild_warnings: list[str] = []
        if rebuild:
            same_sheet = new_mapping is not None and new_mapping.work_sheet == (
                record.work_sheet or ""
            )
            base_rows, header_row, sheet_meta = self._rebuild_rows(
                record, mapping=new_mapping, leaves=leaves
            )
            max_row, max_column = self._bounds_of(sheet_meta)
            if same_sheet:
                # 同表重建仅保留仍存在的物理行与坐标，不把被排除的旧表头复活。
                base_rows = self._preserve_edits(record, base_rows)
            else:
                rebuild_warnings.append(
                    "已切换工作表并按原件重建预览行；之前的行定位与单元格校正不再适用，请重新校对。"
                )
        else:
            header_row = new_mapping.header_row if new_mapping is not None else int(sheet_meta.get("headerRow") or 1)
            base_rows = [self._as_payload(row) for row in record.rows]

        patched_rows = self._apply_row_patches(
            base_rows,
            patches=list(payload.rows),
            participants=participants,
            max_column=max_column,
        )

        row_inputs = tuple(
            analysis.RowInput(
                row_no=row.row_no,
                explicit_participant_id=row.participant_id,
                cells=_cell_inputs_of(row.cells),
            )
            for row in patched_rows
        )
        preview: PreviewMatrix | None = None
        if new_mapping is not None:
            preview = analysis.build_preview(
                participants=participants,
                leaves=leaves,
                mapping=new_mapping,
                rows=row_inputs,
            )
            _raise_cell_errors(preview)
            warnings = list(preview.warnings)
        else:
            warnings = [
                "还没有可用的列映射；请先指定学号/姓名列与计分列后才能确认。"
            ]
        warnings = (
            rebuild_warnings
            + list(
                self._mapping_warnings(record, mapping=new_mapping, leaves=leaves)
            )
            + warnings
        )
        summary = self._summary_payload(
            context=context,
            sheet={**sheet_meta, "headerRow": header_row} if sheet_meta else None,
            preview=preview,
            warnings=warnings,
            base=record.base_score_revision_id,
            row_count=len(patched_rows),
            sheet_warnings=self._sheet_warnings(record),
            item_ids=[leaf.item_id for leaf in leaves],
            mapping_warnings=self._mapping_warnings(record, mapping=new_mapping, leaves=leaves),
        )
        final_rows = [
            RowPayload(
                row_no=row.row_no,
                participant_id=row.participant_id,
                cells=row.cells,
                issues=(
                    preview.row_matches[row.row_no].issues
                    if preview is not None and row.row_no in preview.row_matches
                    else row.issues
                ),
            )
            for row in patched_rows
        ]
        with self._catalog.write_transaction() as conn:
            current = self._scores.require_in(conn, import_id)
            _require_editable(current)
            _check_import_revision(current.revision, payload.expected_revision)
            fresh_context = self._assessment_context(conn, current.assessment_id)
            _check_preview_context(current, fresh_context)
            if fresh_context.revision != context.revision or fresh_context.paper_revision_id != context.paper_revision_id:
                raise _assessment_conflict(fresh_context.revision)
            self._scores.apply_patch_in(
                conn,
                import_id,
                expected_revision=payload.expected_revision,
                mapping=(
                    new_mapping.model_dump(by_alias=True)
                    if payload.mapping is not None
                    else None
                ),
                work_sheet=new_mapping.work_sheet if new_mapping is not None else None,
                replace_rows=final_rows if rebuild else None,
                row_updates=None if rebuild else final_rows,
                summary=summary,
            )
        return self.get_score_import(import_id)

    def refresh_import(
        self, import_id: str, payload: ScoreImportRefreshRequest
    ) -> ScoreImportView:
        """教师明确刷新施测上下文；原件、物理行、人工定位与格修正均保留。"""
        import_id = _text(import_id, field="importId")
        with self._catalog.read_connection() as conn:
            record = self._scores.require_in(conn, import_id)
            _require_editable(record)
            _check_import_revision(record.revision, payload.expected_import_revision)
            context = self._assessment_context(conn, record.assessment_id)
            if context.revision != payload.expected_assessment_revision:
                raise _assessment_conflict(context.revision)
            if (payload.base_score_revision_id != record.base_score_revision_id
                    or context.active_score_revision_id != record.base_score_revision_id):
                raise _base_conflict("当前 active/base 成绩版本已变化；请新建导入，不能通过刷新更换 base。")
            participants = self._participants(conn, record.assessment_id)
        leaves = self._leaves(context.paper_revision_id)
        mapping = self._mapping_of(record)
        preview = self._preview(record, mapping=mapping, participants=participants, leaves=leaves)
        if preview is not None:
            _raise_cell_errors(preview)
        warnings = list(preview.warnings) if preview is not None else ["还没有可用的列映射；请先指定身份与计分列。"]
        summary = self._summary_payload(
            context=context, sheet=self._sheet_meta(record), preview=preview,
            warnings=warnings, base=record.base_score_revision_id, row_count=record.row_count,
            sheet_warnings=self._sheet_warnings(record), item_ids=[leaf.item_id for leaf in leaves],
            mapping_warnings=self._mapping_warnings(record, mapping=mapping, leaves=leaves),
        )
        rows = [RowPayload(
            row_no=row.row_no, participant_id=row.participant_id, cells=row.cells,
            issues=(preview.row_matches[row.row_no].issues
                    if preview is not None and row.row_no in preview.row_matches else row.issues),
        ) for row in record.rows]
        with self._catalog.write_transaction() as conn:
            current = self._scores.require_in(conn, import_id)
            _require_editable(current)
            _check_import_revision(current.revision, payload.expected_import_revision)
            fresh_context = self._assessment_context(conn, current.assessment_id)
            if fresh_context.revision != payload.expected_assessment_revision:
                raise _assessment_conflict(fresh_context.revision)
            if (current.base_score_revision_id != payload.base_score_revision_id
                    or fresh_context.active_score_revision_id != payload.base_score_revision_id):
                raise _base_conflict("刷新期间 active/base 成绩版本已变化；本次刷新未写入。")
            self._scores.apply_patch_in(
                conn, import_id, expected_revision=payload.expected_import_revision,
                work_sheet=current.work_sheet, row_updates=rows, summary=summary,
            )
        return self.get_score_import(import_id)

    def _apply_row_patches(
        self,
        base_rows: Sequence[RowPayload],
        *,
        patches: Sequence[Any],
        participants: Sequence[ParticipantRef],
        max_column: int,
    ) -> list[RowPayload]:
        participant_ids = {item.participant_id for item in participants}
        by_no = {row.row_no: row for row in base_rows}
        row_patches = {patch.row_no: patch for patch in patches}
        if len(row_patches) != len(patches):
            raise _invalid("rows 里同一行号出现了多次。", fields=["rows"])
        for patch in patches:
            if patch.row_no not in by_no:
                raise _issues_error(
                    f"批次中不存在第 {patch.row_no} 行。",
                    code="INVALID_REQUEST",
                    status_code=422,
                    issues=[
                        _issue(
                            patch.row_no,
                            code="INVALID_REQUEST",
                            message="批次中不存在该行；行号来自上传时的原表。",
                            field="rowNo",
                        )
                    ],
                )
        patched: list[RowPayload] = []
        for row in base_rows:
            patch = row_patches.get(row.row_no)
            if patch is None:
                patched.append(row)
                continue
            explicit = row.participant_id
            provided = set(patch.model_fields_set)
            if "participantId" in provided or "participant_id" in provided:
                explicit = _optional_text(patch.participant_id, field="participantId")
                if explicit is not None and explicit not in participant_ids:
                    raise _issues_error(
                        f"第 {patch.row_no} 行指定的参测人次不存在。",
                        code=SCORE_PARTICIPANT_UNKNOWN,
                        status_code=422,
                        issues=[
                            _issue(
                                patch.row_no,
                                code=SCORE_PARTICIPANT_UNKNOWN,
                                message="指定的 participantId 不属于本次施测；请重新选择。",
                                field="participantId",
                            )
                        ],
                    )
            cells = list(row.cells)
            for cell_patch in patch.cells:
                if cell_patch.row != patch.row_no:
                    raise _issues_error(
                        f"第 {patch.row_no} 行的单元格校正行号不一致。",
                        code="INVALID_REQUEST",
                        status_code=422,
                        issues=[
                            _issue(
                                patch.row_no,
                                code="INVALID_REQUEST",
                                message="单元格校正的 row 必须等于所在行的 rowNo。",
                                column=cell_patch.column,
                                field="cells",
                            )
                        ],
                    )
                try:
                    index = analysis.column_index(cell_patch.column)
                except ValueError as exc:
                    raise _issues_error(
                        f"第 {patch.row_no} 行的列字母非法。",
                        code=SCORE_MAPPING_INVALID,
                        status_code=422,
                        issues=[
                            _issue(
                                patch.row_no,
                                code=SCORE_MAPPING_INVALID,
                                message="列字母只能是 A-Z（最多 3 位）。",
                                column=cell_patch.column,
                                field="cells",
                            )
                        ],
                    ) from exc
                if index > max_column:
                    raise _issues_error(
                        f"第 {patch.row_no} 行的列超出原表范围。",
                        code=SCORE_MAPPING_INVALID,
                        status_code=422,
                        issues=[
                            _issue(
                                patch.row_no,
                                code=SCORE_MAPPING_INVALID,
                                message="列超出上传工作表的最大列。",
                                column=cell_patch.column,
                                field="cells",
                            )
                        ],
                    )
                letter = analysis.column_letter(index)
                replaced = False
                for position, cell in enumerate(cells):
                    if cell.column == letter:
                        cells[position] = RawCellRecord(
                            row=cell.row,
                            column=cell.column,
                            text=cell.text,
                            cached_text=cell.cached_text,
                            is_formula=cell.is_formula,
                            corrected_text=cell_patch.text,
                        )
                        replaced = True
                        break
                if not replaced:
                    cells.append(
                        RawCellRecord(
                            row=patch.row_no,
                            column=letter,
                            text="",
                            cached_text="",
                            is_formula=False,
                            corrected_text=cell_patch.text,
                        )
                    )
            patched.append(
                RowPayload(
                    row_no=row.row_no,
                    participant_id=explicit,
                    cells=tuple(cells),
                    issues=row.issues,
                )
            )
        return patched

    def _as_payload(self, row: Any) -> RowPayload:
        if isinstance(row, RowPayload):
            return row
        return RowPayload(
            row_no=row.row_no,
            participant_id=row.participant_id,
            cells=tuple(row.cells),
            issues=tuple(row.issues),
        )

    def _rebuild_rows(
        self,
        record: ScoreImportRecord,
        *,
        mapping: ScoreColumnMapping | None,
        leaves: Sequence[Leaf],
    ) -> tuple[list[RowPayload], int, dict[str, Any]]:
        """映射改变时按原件重读并重建有效物理行（文件 IO 在事务外）。"""
        _, file_assets = self._require_assets()
        asset = file_assets.get(record.file_asset_id)
        if asset is None:
            raise AppError(
                "成绩批次关联的受管资产登记缺失。", code=_ASSET_MISSING, status_code=500
            )
        asset_store = self._asset_store
        assert asset_store is not None  # 由 _require_assets 保证
        content = asset_store.read(asset.blob_key)
        sheet_name = mapping.work_sheet if mapping is not None else record.work_sheet
        sheets = read_score_sheet(content, sheet_name=sheet_name)
        grid = analysis.sheet_grid(sheets[0])
        if mapping is None:  # pragma: no cover - 调用方保证有新映射
            header_row = analysis.detect_header_row(grid) or 1
            meta = {
                "name": grid.name,
                "maxRow": grid.max_row,
                "maxColumn": grid.max_column,
                "headerRow": header_row,
            }
            return (
                [
                    _extracted_to_payload(row, preview=None)
                    for row in analysis.extract_raw_rows(grid, header_row=header_row)
                ],
                header_row,
                meta,
            )
        analysis.validate_mapping(
            mapping,
            sheet_name=grid.name,
            max_row=grid.max_row,
            max_column=grid.max_column,
            leaves=leaves,
        )
        extracted = analysis.extract_rows(
            grid, header_row=mapping.header_row, mapping=mapping
        )
        meta = {
            "name": grid.name,
            "maxRow": grid.max_row,
            "maxColumn": grid.max_column,
            "headerRow": mapping.header_row,
        }
        return (
            [_extracted_to_payload(row, preview=None) for row in extracted],
            mapping.header_row,
            meta,
        )

    def _preserve_edits(
        self, record: ScoreImportRecord, payloads: Sequence[RowPayload]
    ) -> list[RowPayload]:
        """同一工作表重建行时保留教师编辑（显式 participantId + 按坐标的单元格校正）。"""
        previous = {row.row_no: row for row in record.rows}
        preserved: list[RowPayload] = []
        for payload in payloads:
            old = previous.get(payload.row_no)
            if old is None:
                preserved.append(payload)
                continue
            corrections = {
                cell.column: cell.corrected_text
                for cell in old.cells
                if cell.corrected_text is not None
            }
            cells: list[RawCellRecord] = []
            for cell in payload.cells:
                corrected = corrections.pop(cell.column, None)
                if corrected is None:
                    cells.append(cell)
                else:
                    cells.append(
                        RawCellRecord(
                            row=cell.row,
                            column=cell.column,
                            text=cell.text,
                            cached_text=cell.cached_text,
                            is_formula=cell.is_formula,
                            corrected_text=corrected,
                        )
                    )
            for column, corrected in corrections.items():
                cells.append(
                    RawCellRecord(
                        row=payload.row_no,
                        column=column,
                        text="",
                        cached_text="",
                        is_formula=False,
                        corrected_text=corrected,
                    )
                )
            preserved.append(
                RowPayload(
                    row_no=payload.row_no,
                    participant_id=old.participant_id,
                    cells=tuple(cells),
                    issues=payload.issues,
                )
            )
        return preserved

    def _bounds_of(self, sheet_meta: Mapping[str, Any]) -> tuple[int, int]:
        max_row = sheet_meta.get("maxRow")
        max_column = sheet_meta.get("maxColumn")
        row = max_row if isinstance(max_row, int) and not isinstance(max_row, bool) else 0
        column = (
            max_column
            if isinstance(max_column, int) and not isinstance(max_column, bool)
            else 0
        )
        return max(1, row), column or _DEFAULT_MAX_COLUMNS

    # ---------------------------------------------------------------- 确认

    def confirm_score_import(
        self, import_id: str, payload: ScoreImportConfirmRequest
    ) -> ScoreImportConfirmResult:
        """确认成绩导入：单事务写 draft 修订 + 全矩阵 + 封存 + active + 施测版本（幂等）。"""
        import_id = _text(import_id, field="importId")
        coordinator = self._require_coordinator()
        command = make_command(
            operation=CONFIRM_OPERATION,
            submission_id=payload.submission_id,
            payload={"importId": import_id, **payload.model_dump(by_alias=True)},
            owner_id=self._owner_id,
        )
        with coordinator.publication(operation="score_import.confirm"):
            # 协调器内重读施测与原卷叶；写事务内再次复核同一 fixed paperRevisionId
            with self._catalog.read_connection() as conn:
                record = self._scores.require_in(conn, import_id)
                context = self._assessment_context(conn, record.assessment_id)
            leaves = self._leaves(context.paper_revision_id)
            outcome = execute_command(
                catalog=self._catalog,
                command=command,
                apply=lambda conn: self._apply_confirm(
                    conn,
                    import_id=import_id,
                    payload=payload,
                    leaves=leaves,
                    paper_revision_id=context.paper_revision_id,
                ),
                table="command_submissions",
            )
        result = ScoreImportConfirmResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    def _apply_confirm(
        self,
        conn: sqlite3.Connection,
        *,
        import_id: str,
        payload: ScoreImportConfirmRequest,
        leaves: Sequence[Leaf],
        paper_revision_id: str,
    ) -> dict[str, Any]:
        record = self._scores.require_in(conn, import_id)
        _require_editable(record)
        _check_import_revision(record.revision, payload.expected_import_revision)

        context = self._assessment_context(conn, record.assessment_id)
        if context.revision != payload.expected_assessment_revision:
            raise _assessment_conflict(context.revision)
        if record.summary.get("assessmentRevision") != context.revision:
            raise _assessment_conflict(context.revision)
        if context.paper_revision_id != paper_revision_id:
            raise AppError(
                "施测引用的原卷修订与读取到的计分叶不一致；本次确认已整体回滚。",
                code=SCORE_MATRIX_INCOMPLETE,
                status_code=500,
            )
        # 三版本语义互不替代：请求 base == 导入冻结点 == 当前 active（首个版本三者都是 null）
        if record.base_score_revision_id != payload.base_score_revision_id:
            raise _base_conflict("确认请求的 baseScoreRevisionId 与导入冻结点不一致。")
        if context.active_score_revision_id != record.base_score_revision_id:
            raise _base_conflict("当前 active 成绩版本已变化，本次确认未写入。")

        mapping = self._mapping_of(record)
        if mapping is None:
            raise _issues_error(
                "尚未指定列映射，无法确认；请先完成映射与校对。",
                code=SCORE_MAPPING_INVALID,
                status_code=422,
                issues=[
                    _issue(
                        None,
                        code=SCORE_MAPPING_INVALID,
                        message="mapping 缺失（没有识别到学号/姓名列或计分列）。",
                        field="mapping",
                    )
                ],
            )
        participants = self._participants(conn, record.assessment_id)
        if not participants:
            raise AppError(
                "本次施测没有参测人次，无法建立成绩矩阵。",
                code=SCORE_MATRIX_INCOMPLETE,
                status_code=422,
            )
        preview = analysis.build_preview(
            participants=participants,
            leaves=leaves,
            mapping=mapping,
            rows=self._row_inputs(record, mapping),
        )
        _raise_cell_errors(preview)
        blocking = preview.blocking_issues
        if blocking:
            raise _issues_error(
                "成绩校对仍有阻断问题（未消歧行/缺考与数值冲突等）；本次确认未写入。",
                code=blocking[0].code or SCORE_CELL_INVALID,
                status_code=422,
                issues=list(blocking),
            )
        ack_issues = self._acknowledgement_issues(record, preview, payload)
        if ack_issues:
            raise _issues_error(
                "承认范围与当前预览不一致；本次确认未写入，请刷新预览后逐类承认。",
                code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                status_code=422,
                issues=ack_issues,
            )

        participant_snapshot = [
            ScoreParticipantSnapshot(
                participantId=item.participant_id,
                studentId=item.student_id,
                studentNo=item.student_no,
                name=item.name,
                classId=item.class_id,
                attemptNo=item.attempt_no,
                attendance=item.attendance,
            )
            for item in participants
        ]
        item_snapshot = [
            ScoreItemSnapshot(
                itemId=leaf.item_id,
                itemPath=leaf.item_path,
                maxScoreUnits=leaf.max_score_units,
            )
            for leaf in leaves
        ]
        version = self._scores.next_version_in(conn, record.assessment_id)
        revision_id = self._scores.insert_revision_in(
            conn,
            assessment_id=record.assessment_id,
            version=version,
            source_import_id=record.import_id,
            base_revision_id=record.base_score_revision_id,
            participant_snapshot=participant_snapshot,
            item_snapshot=item_snapshot,
        )
        self._scores.insert_matrix_in(
            conn,
            revision_id=revision_id,
            assessment_id=record.assessment_id,
            paper_revision_id=paper_revision_id,
            cells=[
                (participant_id, item_id, cell.status, cell.units)
                for (participant_id, item_id), cell in preview.cells.items()
            ],
        )
        # 封存闸门按**该修订自己的**快照核完整性（人次 × 叶全覆盖）
        self._scores.seal_revision_in(conn, revision_id)
        assessment_revision = self._scores.set_active_revision_in(
            conn,
            record.assessment_id,
            revision_id=revision_id,
            expected_revision=payload.expected_assessment_revision,
        )
        # 冻结生效人次与问题（确认后批次只读，渲染不再重算）
        frozen_rows = [
            RowPayload(
                row_no=row.row_no,
                participant_id=preview.row_participant.get(row.row_no),
                cells=row.cells,
                issues=(
                    preview.row_matches[row.row_no].issues
                    if row.row_no in preview.row_matches
                    else row.issues
                ),
            )
            for row in record.rows
        ]
        self._scores.update_rows_in(conn, import_id, frozen_rows)
        summary = {
            **record.summary,
            "warnings": list(record.warnings) + list(preview.warnings),
            "updatedAt": now_iso(),
            "assessmentRevision": assessment_revision,
            "baseScoreRevisionId": record.base_score_revision_id,
            "itemIds": [item.item_id for item in item_snapshot],
            "preview": {
                "participantCount": preview.participant_count,
                "resolvedRowCount": sum(
                    1 for pid in preview.row_participant.values() if pid is not None
                ),
                "missingCellCount": preview.missing_cell_count,
                "missingParticipantIds": list(preview.missing_participant_ids),
                "absentByClass": {
                    class_id: list(ids)
                    for class_id, ids in preview.absent_by_class.items()
                },
            },
            "acknowledged": {
                "previewVersion": payload.preview_version,
                "submissionId": payload.submission_id,
                "absences": [
                    {
                        "classId": item.class_id,
                        "participantIds": list(item.participant_ids),
                    }
                    for item in payload.absences
                ],
                "missing": (
                    {
                        "participantIds": list(payload.missing.participant_ids),
                        "cellCount": payload.missing.cell_count,
                    }
                    if payload.missing is not None
                    else None
                ),
            },
        }
        self._scores.mark_confirmed_in(
            conn,
            import_id,
            expected_revision=payload.expected_import_revision,
            summary=summary,
        )
        result = ScoreImportConfirmResult(
            importId=import_id,
            state="confirmed",
            revisionId=revision_id,
            assessmentRevision=assessment_revision,
            activeScoreRevisionId=revision_id,
            replayed=False,
        )
        return result.model_dump(by_alias=True)

    def _acknowledgement_issues(
        self,
        record: ScoreImportRecord,
        preview: PreviewMatrix,
        payload: ScoreImportConfirmRequest,
    ) -> list[ErrorIssue]:
        issues: list[ErrorIssue] = []
        if payload.preview_version != record.preview_version:
            issues.append(
                _issue(
                    None,
                    code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                    message=(
                        f"承认的是预览版本 {payload.preview_version}，"
                        f"当前预览版本是 {record.preview_version}；请刷新预览。"
                    ),
                    field="previewVersion",
                )
            )
        expected_absences = {
            class_id: set(ids) for class_id, ids in preview.absent_by_class.items()
        }
        provided_absences, duplicates = _collect_absences(payload.absences)
        if duplicates:
            issues.append(
                _issue(
                    None,
                    code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                    message="absences 里同一班级出现多次。",
                    field="absences",
                )
            )
        for class_id in sorted(set(expected_absences) - set(provided_absences)):
            ids = "、".join(sorted(expected_absences[class_id]))
            issues.append(
                _issue(
                    None,
                    code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                    message=f"班级 {class_id} 的缺考人次未承认：{ids}。",
                    field="absences",
                )
            )
        for class_id in sorted(set(provided_absences) - set(expected_absences)):
            issues.append(
                _issue(
                    None,
                    code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                    message=f"班级 {class_id} 并没有预览到的缺考人次；请刷新。",
                    field="absences",
                )
            )
        for class_id in sorted(set(expected_absences) & set(provided_absences)):
            for participant_id in sorted(
                expected_absences[class_id] - provided_absences[class_id]
            ):
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message=f"缺考人次 {participant_id}（班级 {class_id}）未承认。",
                        field="participantIds",
                    )
                )
            for participant_id in sorted(
                provided_absences[class_id] - expected_absences[class_id]
            ):
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message=f"承认的缺考人次 {participant_id}（班级 {class_id}）与预览不符。",
                        field="participantIds",
                    )
                )
        expected_missing = set(preview.missing_participant_ids)
        if preview.missing_cell_count == 0:
            if payload.missing is not None:
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message="当前预览没有 missing 单元格，不应携带 missing 承认。",
                        field="missing",
                    )
                )
        elif payload.missing is None:
            issues.append(
                _issue(
                    None,
                    code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                    message=(
                        f"预览还有 {preview.missing_cell_count} 个 missing 单元格"
                        f"（{len(expected_missing)} 个人次）未承认。"
                    ),
                    field="missing",
                )
            )
        else:
            provided_missing = set(payload.missing.participant_ids)
            for participant_id in sorted(expected_missing - provided_missing):
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message=f"missing 人次 {participant_id} 未承认。",
                        field="participantIds",
                    )
                )
            for participant_id in sorted(provided_missing - expected_missing):
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message=f"承认的 missing 人次 {participant_id} 与预览不符。",
                        field="participantIds",
                    )
                )
            if payload.missing.cell_count != preview.missing_cell_count:
                issues.append(
                    _issue(
                        None,
                        code=SCORE_ACKNOWLEDGEMENT_MISMATCH,
                        message=(
                            f"承认 {payload.missing.cell_count} 个 missing 单元，"
                            f"预览是 {preview.missing_cell_count} 个。"
                        ),
                        field="cellCount",
                    )
                )
        return issues

    # ---------------------------------------------------------------- 修订读取

    def list_score_revisions(self, assessment_id: str) -> ScoreRevisionList:
        assessment_id = _text(assessment_id, field="assessmentId")
        with self._catalog.read_connection() as conn:
            self._assessment_context(conn, assessment_id)
            revisions = self._scores.list_revisions_in(conn, assessment_id)
        return ScoreRevisionList(
            items=[revision.view() for revision in revisions], total=len(revisions)
        )

    def get_score_revision(self, revision_id: str) -> ScoreRevisionView:
        revision_id = _text(revision_id, field="revisionId")
        with self._catalog.read_connection() as conn:
            revision = self._scores.require_revision_in(conn, revision_id)
        return revision.view()

    def get_score_matrix(
        self, revision_id: str, *, offset: int = 0, limit: int = 50
    ) -> ScoreMatrixPage:
        offset, limit = _page(offset, limit)
        revision_id = _text(revision_id, field="revisionId")
        with self._catalog.read_connection() as conn:
            revision = self._scores.require_revision_in(conn, revision_id)
            page_participants = list(revision.participant_snapshot)[
                offset : offset + limit
            ]
            cells = self._scores.matrix_cells_in(
                conn,
                revision_id,
                participant_ids=[item.participant_id for item in page_participants],
            )
            stats = self._scores.matrix_stats_in(conn, revision_id)
        cell_map = {
            (cell.participant_id, cell.item_id): (cell.status, cell.score_units)
            for cell in cells
        }
        return build_matrix_page(
            revision, cells=cell_map, stats=stats, offset=offset, limit=limit
        )

    # ---------------------------------------------------------------- 修正

    def correct_scores(
        self, assessment_id: str, payload: ScoreRevisionCorrectRequest
    ) -> ScoreRevisionCorrectResult:
        """修正 = 从不可变 base 复制全矩阵 + 修正当时参测快照 → 新完整版本（本身即完整确认）。"""
        assessment_id = _text(assessment_id, field="assessmentId")
        coordinator = self._require_coordinator()
        command = make_command(
            operation=CORRECT_OPERATION,
            submission_id=payload.submission_id,
            payload={"assessmentId": assessment_id, **payload.model_dump(by_alias=True)},
            owner_id=self._owner_id,
        )
        with coordinator.publication(operation="score_revision.correct"):
            outcome = execute_command(
                catalog=self._catalog,
                command=command,
                apply=lambda conn: self._apply_correct(
                    conn, assessment_id=assessment_id, payload=payload
                ),
                table="command_submissions",
            )
        result = ScoreRevisionCorrectResult.model_validate(outcome.result)
        return result.model_copy(update={"replayed": outcome.replayed})

    def _apply_correct(
        self,
        conn: sqlite3.Connection,
        *,
        assessment_id: str,
        payload: ScoreRevisionCorrectRequest,
    ) -> dict[str, Any]:
        context = self._assessment_context(conn, assessment_id)
        if context.revision != payload.expected_assessment_revision:
            raise _assessment_conflict(context.revision)
        base = self._scores.get_revision_in(conn, payload.base_score_revision_id)
        if base is None or base.assessment_id != assessment_id:
            raise AppError(
                f"成绩修订不存在或不属于本次施测：{payload.base_score_revision_id}。",
                code=SCORE_REVISION_NOT_FOUND,
                status_code=404,
            )
        if base.state != "confirmed":
            raise _base_conflict("只能从已确认的正式成绩版本建立修正。")
        if context.active_score_revision_id is None:
            raise AppError(
                "本次施测还没有正式成绩版本，不能执行修正。",
                code=SCORE_NO_BASE_REVISION,
                status_code=409,
            )
        if context.active_score_revision_id != payload.base_score_revision_id:
            raise _base_conflict("baseScoreRevisionId 必须等于当前 active 成绩版本。")

        base_cells = {
            (cell.participant_id, cell.item_id): cell
            for cell in self._scores.matrix_cells_in(conn, base.revision_id)
        }
        base_participants = {item.participant_id for item in base.participant_snapshot}
        items = {item.item_id: item for item in base.item_snapshot}
        seen: set[tuple[str, str]] = set()
        validated: list[tuple[str, str, str, int | None]] = []
        for entry in payload.corrections:
            key = (entry.participant_id, entry.item_id)
            if key in seen:
                raise self._correction_invalid(
                    f"同一（人次 {entry.participant_id}, 小题 {entry.item_id}）在一次修正里重复出现。"
                )
            seen.add(key)
            if entry.participant_id not in base_participants:
                raise _issues_error(
                    "修正指向的参测人次不在 base 成绩版本内。",
                    code=SCORE_PARTICIPANT_UNKNOWN,
                    status_code=422,
                    issues=[
                        _issue(
                            None,
                            code=SCORE_PARTICIPANT_UNKNOWN,
                            message=f"参测人次 {entry.participant_id} 不在 base 快照内。",
                            field="participantId",
                        )
                    ],
                )
            item = items.get(entry.item_id)
            if item is None:
                raise _issues_error(
                    "修正指向的小题不在 base 成绩版本内。",
                    code=SCORE_ITEM_UNKNOWN,
                    status_code=422,
                    issues=[
                        _issue(
                            None,
                            code=SCORE_ITEM_UNKNOWN,
                            message=f"小题 {entry.item_id} 不在 base 快照内。",
                            field="itemId",
                        )
                    ],
                )
            new_units: int | None = None
            if entry.status == "recorded":
                parsed = analysis.parse_score_text(
                    entry.score_text or "", max_units=item.max_score_units
                )
                if parsed.is_error or parsed.status != "recorded" or parsed.units is None:
                    raise _issues_error(
                        "修正的分数不合法。",
                        code=parsed.code or SCORE_CELL_INVALID,
                        status_code=422,
                        issues=[
                            _issue(
                                None,
                                code=parsed.code or SCORE_CELL_INVALID,
                                message=parsed.message or "recorded 修正必须填写数值分数；空白、缺考与免考应选择对应状态。",
                                field="scoreText",
                            )
                        ],
                    )
                new_units = parsed.units
            old = base_cells.get(key)
            if old is None:  # pragma: no cover - 封存闸门保证矩阵完整
                raise AppError(
                    "教学库数据损坏：base 成绩版本的矩阵不完整。",
                    code=SCORE_MATRIX_INCOMPLETE,
                    status_code=500,
                )
            if old.status == entry.status and old.score_units == new_units:
                raise self._correction_invalid(
                    f"修正没有改变任何值（人次 {entry.participant_id}，小题 {entry.item_id}）。"
                )
            validated.append((entry.participant_id, entry.item_id, entry.status, new_units))

        # 修正当时的参测快照（可能含新增补考人次）；固定叶从不可变 base 复制
        participants = self._participants(conn, assessment_id)
        if not participants:
            raise AppError(
                "本次施测没有参测人次，无法建立成绩矩阵。",
                code=SCORE_MATRIX_INCOMPLETE,
                status_code=422,
            )
        participant_snapshot = [
            ScoreParticipantSnapshot(
                participantId=item.participant_id,
                studentId=item.student_id,
                studentNo=item.student_no,
                name=item.name,
                classId=item.class_id,
                attemptNo=item.attempt_no,
                attendance=item.attendance,
            )
            for item in participants
        ]
        item_snapshot = list(base.item_snapshot)
        changes = {(pid, iid): (status, units) for pid, iid, status, units in validated}
        matrix: list[tuple[str, str, str, int | None]] = []
        for participant in participants:
            for item in item_snapshot:
                key = (participant.participant_id, item.item_id)
                old = base_cells.get(key)
                if old is not None:
                    status, units = old.status, old.score_units
                elif participant.attendance in ("absent", "exempt"):
                    status, units = participant.attendance, None
                else:
                    status, units = "missing", None
                if key in changes:
                    status, units = changes[key]
                matrix.append((key[0], key[1], status, units))

        version = self._scores.next_version_in(conn, assessment_id)
        revision_id = self._scores.insert_revision_in(
            conn,
            assessment_id=assessment_id,
            version=version,
            source_import_id=None,
            base_revision_id=payload.base_score_revision_id,
            participant_snapshot=participant_snapshot,
            item_snapshot=item_snapshot,
        )
        self._scores.insert_matrix_in(
            conn,
            revision_id=revision_id,
            assessment_id=assessment_id,
            paper_revision_id=context.paper_revision_id,
            cells=matrix,
        )
        self._scores.seal_revision_in(conn, revision_id)
        assessment_revision = self._scores.set_active_revision_in(
            conn,
            assessment_id,
            revision_id=revision_id,
            expected_revision=payload.expected_assessment_revision,
        )
        now = now_iso()
        self._scores.insert_corrections_in(
            conn,
            revision_id,
            [
                ScoreCorrectionRecord(
                    revision_id=revision_id,
                    seq=index,
                    participant_id=participant_id,
                    item_id=item_id,
                    old_status=base_cells[(participant_id, item_id)].status,
                    old_score_units=base_cells[(participant_id, item_id)].score_units,
                    new_status=status,
                    new_score_units=units,
                    reason=payload.reason,
                    created_at=now,
                )
                for index, (participant_id, item_id, status, units) in enumerate(
                    validated, start=1
                )
            ],
        )
        result = ScoreRevisionCorrectResult(
            revisionId=revision_id,
            baseRevisionId=payload.base_score_revision_id,
            version=version,
            assessmentRevision=assessment_revision,
            activeScoreRevisionId=revision_id,
            replayed=False,
        )
        return result.model_dump(by_alias=True)

    def _correction_invalid(self, message: str) -> AppError:
        return _issues_error(
            message or "修正不合法。",
            code=SCORE_CORRECTION_INVALID,
            status_code=422,
            issues=[
                _issue(
                    None,
                    code=SCORE_CORRECTION_INVALID,
                    message=message or "修正不合法。",
                    field="corrections",
                )
            ],
        )

    # ---------------------------------------------------------------- 渲染

    def _render_import(
        self,
        record: ScoreImportRecord,
        *,
        context: AssessmentContext,
        participants: Sequence[ParticipantRef],
        frozen: bool,
    ) -> ScoreImportView:
        _, file_assets = self._require_assets()
        asset = file_assets.get(record.file_asset_id)
        if asset is None:
            raise AppError(
                "成绩批次关联的受管资产登记缺失。", code=_ASSET_MISSING, status_code=500
            )
        mapping = self._mapping_of(record)
        stale = not frozen and (
            record.summary.get("assessmentRevision") != context.revision
            or record.base_score_revision_id != context.active_score_revision_id
        )
        use_stored_preview = frozen or stale
        preview: PreviewMatrix | None = None
        leaves: tuple[Leaf, ...] = ()
        if mapping is not None and not use_stored_preview:
            leaves = self._leaves(context.paper_revision_id)
        if use_stored_preview:
            stored_mapping_warnings = record.summary.get("mappingWarnings")
            mapping_warnings = (
                tuple(
                    item
                    for item in stored_mapping_warnings
                    if isinstance(item, str)
                )
                if isinstance(stored_mapping_warnings, list)
                else ()
            )
        else:
            mapping_warnings = self._mapping_warnings(
                record, mapping=mapping, leaves=leaves
            )
        warnings = (
            list(self._sheet_warnings(record))
            + list(mapping_warnings)
            + list(record.warnings)
        )
        if mapping is not None and not use_stored_preview:
            preview = self._preview(
                record, mapping=mapping, participants=participants, leaves=leaves
            )
            assert preview is not None
            warnings.extend(preview.warnings)
        if stale:
            warnings.append("施测或当前正式成绩版本已变化；当前仍展示原预览范围，请明确刷新并重新校对。")
        if use_stored_preview:
            numbers = record.summary.get("preview")
            numbers = numbers if isinstance(numbers, dict) else {}
            resolved = int(numbers.get("resolvedRowCount") or 0)
            missing_cells = int(numbers.get("missingCellCount") or 0)
            blocking: list[ErrorIssue] = ([] if frozen else [
                ErrorIssue.model_validate(issue) for issue in record.summary.get("issues", [])
            ])
        else:
            resolved = (
                sum(1 for pid in preview.row_participant.values() if pid is not None)
                if preview is not None
                else 0
            )
            missing_cells = preview.missing_cell_count if preview is not None else 0
            blocking = list(preview.blocking_issues) if preview is not None else []
        if stale:
            code = (SCORE_ASSESSMENT_REVISION_CONFLICT
                    if record.summary.get("assessmentRevision") != context.revision
                    else SCORE_BASE_REVISION_CONFLICT)
            blocking.append(_issue(None, code=code,
                                   message="当前预览依据已变化；请明确刷新，active/base变化时须新建导入。",
                                   field="expectedAssessmentRevision" if code == SCORE_ASSESSMENT_REVISION_CONFLICT else "baseScoreRevisionId"))
        numbers = record.summary.get("preview") if use_stored_preview else None
        if preview is not None:
            absent_by_class = preview.absent_by_class
            missing_ids = preview.missing_participant_ids
        elif isinstance(numbers, dict):
            absent_by_class = numbers.get("absentByClass") or {}
            missing_ids = numbers.get("missingParticipantIds") or []
        else:
            absent_by_class, missing_ids = {}, []
        required = ScorePreviewAcknowledgements(
            absences=[
                ScoreAbsenceAcknowledgement(classId=class_id, participantIds=list(ids))
                for class_id, ids in sorted(absent_by_class.items()) if ids
            ],
            missing=(ScoreMissingAcknowledgement(participantIds=list(missing_ids), cellCount=missing_cells)
                     if missing_cells else None),
        )
        return ScoreImportView(
            importId=record.import_id,
            assessmentId=record.assessment_id,
            assessmentTitle=context.title,
            state=record.state,
            revision=record.revision,
            previewVersion=record.preview_version,
            fileAsset=asset.ref(),
            mapping=mapping,
            baseScoreRevisionId=record.base_score_revision_id,
            warnings=warnings,
            issues=blocking,
            rowCount=record.row_count,
            resolvedRowCount=resolved,
            missingCellCount=missing_cells,
            requiredAcknowledgements=required,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )

    def _render_rows(
        self,
        record: ScoreImportRecord,
        *,
        mapping: ScoreColumnMapping | None,
        preview: PreviewMatrix | None,
        participants: Sequence[ParticipantRef],
        offset: int,
        limit: int,
    ) -> ScoreImportRowList:
        names = {item.participant_id: item.name for item in participants}
        rows = list(record.rows)[offset : offset + limit]
        items = [
            self._row_view(row, mapping=mapping, preview=preview, names=names)
            for row in rows
        ]
        return ScoreImportRowList(
            items=items, total=len(record.rows), offset=offset, limit=limit
        )

    def _row_view(
        self,
        row: Any,
        *,
        mapping: ScoreColumnMapping | None,
        preview: PreviewMatrix | None,
        names: Mapping[str, str],
    ) -> ScoreImportRowView:
        cells: list[ScoreRawCellView] = []
        match = preview.row_matches.get(row.row_no) if preview is not None else None
        participant_id = (preview.row_participant.get(row.row_no)
                          if preview is not None else row.participant_id)
        if mapping is not None:
            stored = {cell.column: cell for cell in row.cells}
            columns = [(entry.column, entry.item_id) for entry in mapping.item_columns]
            columns.extend((letter, None) for letter in (mapping.total_column, mapping.attendance_column) if letter)
            for letter, item_id in columns:
                cell = stored.get(letter)
                if cell is not None:
                    view = cell.view()
                else:
                    view = ScoreRawCellView(row=row.row_no, column=letter,
                                            text="", cachedText="", isFormula=False)
                effective = (preview.cells.get((participant_id, item_id))
                             if preview is not None and participant_id and item_id else None)
                if effective is not None:
                    view = view.model_copy(update={"effective_status": effective.status, "score_units": effective.units})
                cells.append(view)
        else:
            # 尚无身份映射时仍暴露原表证据，教师才能完成手动映射；不伪造得分状态。
            cells = [cell.view() for cell in row.cells]
        issues: list[ErrorIssue] = (
            list(match.issues) if match is not None else list(row.issues)
        )
        if preview is not None:
            issues.extend(issue for issue in preview.cell_errors if issue.row == row.row_no)
        return ScoreImportRowView(
            rowNo=row.row_no,
            participantId=participant_id,
            participantName=names.get(participant_id) if participant_id else None,
            candidates=list(match.candidates) if match is not None else [],
            cells=cells,
            issues=issues,
        )


# --------------------------------------------------------------------------- 助手


def _ref_from_record(record: ParticipantRecord) -> ParticipantRef:
    return ParticipantRef(
        participant_id=record.participant_id,
        student_id=record.student_id,
        student_no=record.student_no_snapshot,
        name=record.name_snapshot,
        class_id=record.class_id,
        attempt_no=record.attempt_no,
        attendance=record.attendance,
    )


def _collect_absences(
    absences: Sequence[ScoreAbsenceAcknowledgement],
) -> tuple[dict[str, set[str]], bool]:
    provided: dict[str, set[str]] = {}
    duplicates = False
    for item in absences:
        if item.class_id in provided:
            duplicates = True
        provided.setdefault(item.class_id, set()).update(item.participant_ids)
    return provided, duplicates


def build_score_service(
    catalog: TeachingCatalog,
    *,
    asset_store: AssetStore | None,
    file_assets: FileAssetsRepository | None,
    assessment_service: Any | None = None,
    paper_reader: Any | None = None,
    publication_coordinator: Any | None = None,
) -> ScoreService:
    """装配工厂（签名由 B3 任务卡冻结；缺依赖时对应能力 503，不伪造成功）。"""
    return ScoreService(
        catalog,
        asset_store=asset_store,
        file_assets=file_assets,
        assessment_service=assessment_service,
        paper_reader=paper_reader,
        publication_coordinator=publication_coordinator,
    )


__all__ = [
    "CONFIRM_OPERATION",
    "CORRECT_OPERATION",
    "EDITABLE_IMPORT_STATES",
    "ScoreService",
    "build_score_service",
]
