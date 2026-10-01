"""成绩导入的纯分析层（TEACHING-LOOP B3 / T60）：不碰数据库、不写资产、不调模型。

本模块是"原始表格 → 预览矩阵"的唯一实现，被上传、PATCH 重算、确认复核与只读渲染共用，
保证同一份文件在预览与确认之间得到同一结果：

- **表头自动识别**：按表头文本匹配已确认原卷的计分叶 ``question_no`` 与题号路径
  （``16/16(1)``、``16.16(1)``）。识别不了的一律留给教师 PATCH，不猜；
- **单元格四态**：``0`` 是 recorded(0)、空是 missing、``缺考`` 是 absent、``免考`` 是 exempt；
  分数一律 Decimal 文本 → ×100 整数（禁浮点），拒绝布尔、Excel 错误值、NaN/Infinity、
  负数、超满分与超过两位小数的文本；公式单元格用 data_only **缓存视图**参与解析，
  缺少缓存值明确阻断（不重算公式）；
- **行定位**：优先教师显式 ``participantId``；否则按学号**文本**（前导零保留）匹配，
  再退姓名；同名/多个人次等多义行给出候选并要求人工指定（``SCORE_ROW_UNRESOLVED`` /
  ``SCORE_ROW_DUPLICATE_PARTICIPANT``），绝不自动合并、不自动选最新补考；
- **全矩阵**：冻结参测人次 × 固定计分叶。缺行、缺列、未映射叶显式落 missing，
  **绝不补 0**；缺考/免考与数值同时出现、快照出勤与文件标记互相矛盾时阻断确认。

本模块不修改 ``app/services/tabular.py`` 的读取口径：``RawSheet`` 原样进来，物理行列与
两视图文本原样保留。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any, Mapping, Sequence

from app.contracts.scores import (
    SCORE_CELL_INVALID,
    SCORE_CELL_OVER_MAX,
    SCORE_ITEM_UNKNOWN,
    SCORE_MAPPING_INVALID,
    SCORE_ROW_DUPLICATE_PARTICIPANT,
    SCORE_ROW_UNRESOLVED,
    ScoreColumnMapping,
    ScoreItemColumn,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.services.tabular import RawSheet

#: 单次导入允许存储的单元格上限（含身份列与已映射列；超限明确报错，不静默截断）
MAX_STORED_CELLS = 120_000
#: 表头行搜索范围（首行前的空行/标题行容错）
MAX_HEADER_SEARCH_ROWS = 50
#: 列字母（Excel 列）上限与契约 ``column`` 的 max_length=3 一致
MAX_COLUMN_LETTERS = 3
#: 歧义行的候选人次展示上限（只影响展示，不影响阻断判定）
MAX_ROW_CANDIDATES = 20

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_MARKER_TRAILING = "。．.!！、,，;；"

#: 缺考标记（NFKC + 去空白 + casefold 后比较）
_ABSENT_MARKER_TEXTS = ("缺考", "absent")
#: 免考标记
_EXEMPT_MARKER_TEXTS = ("免考", "exempt")
#: Excel 错误值（不是分数）
_EXCEL_ERROR_TEXTS = (
    "#value!",
    "#ref!",
    "#div/0!",
    "#n/a",
    "#name?",
    "#null!",
    "#num!",
    "#getting_data",
)
_BOOLEAN_TEXTS = ("true", "false")

#: 身份列表头别名（归一化后比较）
STUDENT_NO_HEADERS = frozenset(
    {"学号", "学生学号", "考生号", "考号", "学籍号", "studentno", "studentid"}
)
NAME_HEADERS = frozenset({"姓名", "学生姓名", "考生姓名", "名字", "name"})

#: 阻断确认的问题码（预览可保存，但确认前必须消解）
BLOCKING_ISSUE_CODES: frozenset[str] = frozenset(
    {
        SCORE_ROW_UNRESOLVED,
        SCORE_ROW_DUPLICATE_PARTICIPANT,
        SCORE_CELL_INVALID,
        SCORE_CELL_OVER_MAX,
        SCORE_MAPPING_INVALID,
        SCORE_ITEM_UNKNOWN,
    }
)


def is_blocking_issue(issue: ErrorIssue) -> bool:
    return issue.code in BLOCKING_ISSUE_CODES


def _issue(
    row: int | None,
    *,
    code: str,
    message: str,
    column: str | None = None,
    field: str | None = None,
) -> ErrorIssue:
    return ErrorIssue(row=row, column=column, field=field, code=code, message=message)


def _invalid(
    message: str,
    *,
    code: str = SCORE_MAPPING_INVALID,
    issues: list[ErrorIssue] | None = None,
) -> AppError:
    return AppError(
        message,
        code=code,
        status_code=422,
        details=error_details(issues=issues) if issues else None,
    )


def _mapping_invalid(message: str, *, issues: list[ErrorIssue] | None = None) -> AppError:
    return _invalid(message, code=SCORE_MAPPING_INVALID, issues=issues)


# --------------------------------------------------------------------------- 列与文本


@lru_cache(maxsize=4096)
def column_letter(index: int) -> str:
    """1 基物理列号 → Excel 列字母（1 → A、27 → AA）。"""
    if not isinstance(index, int) or isinstance(index, bool) or index < 1:
        raise ValueError("列号必须是正整数")
    letters: list[str] = []
    value = index
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        letters.append(_ALPHABET[remainder])
    return "".join(reversed(letters))


@lru_cache(maxsize=4096)
def column_index(letter: str) -> int:
    """Excel 列字母 → 1 基物理列号；非法字母抛 ``ValueError``。"""
    if not isinstance(letter, str):
        raise ValueError("列字母必须是字符串")
    text = letter.strip().upper()
    if not text or len(text) > MAX_COLUMN_LETTERS:
        raise ValueError("列字母形状不符")
    value = 0
    for char in text:
        if char not in _ALPHABET:
            raise ValueError("列字母只能是 A-Z")
        value = value * 26 + (_ALPHABET.index(char) + 1)
    return value


def is_column_letter(text: object) -> bool:
    try:
        column_index(text)  # type: ignore[arg-type]
    except ValueError:
        return False
    return True


def normalize_text(text: object) -> str:
    """NFKC（全角→半角）+ 去所有空白 + casefold，用于标记与表头比较。"""
    if not isinstance(text, str):
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = re.sub(r"[\s\u3000\u00a0]+", "", value)
    return value.casefold()


def _marker_key(text: str) -> str:
    return normalize_text(text).rstrip(_MARKER_TRAILING)


ABSENT_MARKERS: frozenset[str] = frozenset(_marker_key(item) for item in _ABSENT_MARKER_TEXTS)
EXEMPT_MARKERS: frozenset[str] = frozenset(_marker_key(item) for item in _EXEMPT_MARKER_TEXTS)


def header_keys(text: str) -> frozenset[str]:
    """表头文本的匹配键集合（去得分/分值后缀、去“第…题”包裹）。"""
    base = normalize_text(text)
    if not base:
        return frozenset()
    keys: set[str] = {base}
    for suffix in ("得分", "分数", "成绩", "分值"):
        if base.endswith(suffix) and len(base) > len(suffix):
            keys.add(base[: -len(suffix)])
    if base.startswith("第") and len(base) > 1:
        keys.add(base[1:])
    for key in tuple(keys):
        for suffix in ("小题", "题"):
            if key.endswith(suffix) and len(key) > len(suffix):
                keys.add(key[: -len(suffix)])
    return frozenset(key for key in keys if key)


# --------------------------------------------------------------------------- 表格形状


@dataclass(frozen=True)
class SheetCell:
    """一个物理单元格（两视图 + 是否公式）。"""

    row: int
    column: int
    text: str
    cached_text: str
    is_formula: bool

    @property
    def is_blank(self) -> bool:
        return self.text.strip() == "" and self.cached_text.strip() == ""

    @property
    def letter(self) -> str:
        return column_letter(self.column)

    def parse_input(self) -> str:
        """解析输入文本：公式单元格用缓存视图（不重算公式），其余用公式视图。"""
        return self.cached_text if self.is_formula else self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "column": self.letter,
            "text": self.text,
            "cachedText": self.cached_text,
            "isFormula": self.is_formula,
        }


@dataclass(frozen=True)
class SheetGrid:
    """保留物理坐标的工作表（只保留有内容的单元格）。"""

    name: str
    max_row: int
    max_column: int
    rows: tuple[tuple[SheetCell, ...], ...]

    def row_cells(self, row_no: int) -> tuple[SheetCell, ...]:
        if row_no < 1 or row_no > len(self.rows):
            return ()
        return self.rows[row_no - 1]

    def cell(self, row_no: int, column: int) -> SheetCell | None:
        target = column_letter(column)
        for item in self.row_cells(row_no):
            if item.letter == target:
                return item
        return None


def sheet_grid(sheet: RawSheet) -> SheetGrid:
    """``RawSheet`` → ``SheetGrid``（两视图原样保留；空行空列不落格）。"""
    if not isinstance(sheet, RawSheet):
        raise _mapping_invalid("读取结果不是 RawSheet。")
    rows: list[tuple[SheetCell, ...]] = []
    for row_cells in sheet.rows:
        kept: list[SheetCell] = []
        for raw in row_cells:
            text = "" if raw.text is None else str(raw.text)
            cached = "" if raw.cached_text is None else str(raw.cached_text)
            if text.strip() == "" and cached.strip() == "":
                continue
            kept.append(
                SheetCell(
                    row=int(raw.row),
                    column=int(raw.column),
                    text=text,
                    cached_text=cached,
                    is_formula=bool(raw.formula),
                )
            )
        rows.append(tuple(kept))
    return SheetGrid(
        name=sheet.name,
        max_row=int(sheet.max_row),
        max_column=int(sheet.max_column),
        rows=tuple(rows),
    )


# --------------------------------------------------------------------------- 计分叶


@dataclass(frozen=True)
class Leaf:
    """已确认原卷的一个计分叶（矩阵列的身份）。"""

    item_id: str
    question_no: str
    item_path: str
    ordinal: int
    max_score_units: int
    keys: frozenset[str]


def question_keys(question_no: str, item_path: str) -> frozenset[str]:
    keys: set[str] = set(header_keys(question_no))
    for value in (item_path, item_path.replace("/", ".")):
        keys |= header_keys(value)
    if "/" in item_path:
        keys |= header_keys(item_path.split("/")[-1])
    return frozenset(key for key in keys if key)


def build_leaf(
    *, item_id: str, question_no: str, item_path: str, ordinal: int, max_score_units: int
) -> Leaf:
    return Leaf(
        item_id=item_id,
        question_no=question_no,
        item_path=item_path,
        ordinal=ordinal,
        max_score_units=max_score_units,
        keys=question_keys(question_no, item_path),
    )


# --------------------------------------------------------------------------- 单元格解析


@dataclass(frozen=True)
class CellParse:
    """单元格解析结果；``code`` 非空表示解析失败（不静默当 missing）。"""

    status: str
    units: int | None = None
    code: str | None = None
    message: str | None = None

    @property
    def is_error(self) -> bool:
        return self.code is not None


def parse_score_text(text: str, *, max_units: int) -> CellParse:
    """四态解析：recorded / missing / absent / exempt（Decimal ×100，禁浮点）。"""
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    stripped = text.strip()
    if stripped == "" or normalize_text(stripped) == "":
        return CellParse(status="missing")
    marker = _marker_key(stripped)
    if marker in ABSENT_MARKERS:
        return CellParse(status="absent")
    if marker in EXEMPT_MARKERS:
        return CellParse(status="exempt")
    normalized = unicodedata.normalize("NFKC", stripped).strip()
    if normalize_text(normalized) in _EXCEL_ERROR_TEXTS:
        return CellParse(
            status="missing",
            code=SCORE_CELL_INVALID,
            message="Excel 错误值不是分数；请修正原表后重新上传。",
        )
    if normalize_text(normalized) in _BOOLEAN_TEXTS:
        return CellParse(
            status="missing",
            code=SCORE_CELL_INVALID,
            message="布尔值不是分数；请填数值、留空或填缺考/免考。",
        )
    try:
        value = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return CellParse(
            status="missing",
            code=SCORE_CELL_INVALID,
            message="单元格不是可解析的数值文本（不接受千分位/百分号/其他字符）。",
        )
    if not value.is_finite():
        return CellParse(
            status="missing", code=SCORE_CELL_INVALID, message="NaN/Infinity 不是分数。"
        )
    if value < 0:
        return CellParse(
            status="missing", code=SCORE_CELL_INVALID, message="分数不能为负数。"
        )
    scaled = value * 100
    if scaled != scaled.to_integral_value():
        return CellParse(
            status="missing",
            code=SCORE_CELL_INVALID,
            message="分数最多两位小数；不四舍五入、不推断。",
        )
    units = int(scaled)
    if units > max_units:
        return CellParse(
            status="missing",
            code=SCORE_CELL_OVER_MAX,
            message=f"分数超过该小题满分（{max_units / 100:g} 分）；请修正原表。",
        )
    return CellParse(status="recorded", units=units)


# --------------------------------------------------------------------------- 表头识别


@dataclass(frozen=True)
class AutoMapping:
    """自动识别结果；``mapping`` 为空表示身份列都没认出来，必须教师 PATCH。"""

    mapping: ScoreColumnMapping | None
    warnings: tuple[str, ...]


def detect_header_row(grid: SheetGrid) -> int | None:
    limit = min(grid.max_row, MAX_HEADER_SEARCH_ROWS)
    for row_no in range(1, limit + 1):
        if grid.row_cells(row_no):
            return row_no
    return None


def auto_map(grid: SheetGrid, leaves: Sequence[Leaf]) -> AutoMapping:
    """按表头文本自动识别身份列与计分叶列；识别不了的留给教师。"""
    warnings: list[str] = []
    header_row = detect_header_row(grid)
    if header_row is None:
        return AutoMapping(
            mapping=None, warnings=(f"工作表「{grid.name}」没有可识别的表头行。",)
        )
    header_cells = grid.row_cells(header_row)

    def _match_column(aliases: frozenset[str], label: str) -> str | None:
        matched = [
            cell.letter for cell in header_cells if header_keys(cell.text) & aliases
        ]
        if len(matched) > 1:
            warnings.append(
                f"表头里出现多个可能的{label}列（{', '.join(matched)}）；"
                "未自动选择，请手动指定。"
            )
            return None
        return matched[0] if matched else None

    student_no_column = _match_column(STUDENT_NO_HEADERS, "学号")
    name_column = _match_column(NAME_HEADERS, "姓名")
    if student_no_column is None and name_column is None:
        warnings.append("未识别到学号列或姓名列；请手动指定后才能定位人次。")

    identity_columns = {
        column for column in (student_no_column, name_column) if column
    }
    leaf_index: dict[str, list[Leaf]] = {}
    for leaf in leaves:
        for key in leaf.keys:
            leaf_index.setdefault(key, []).append(leaf)

    item_columns: list[ScoreItemColumn] = []
    used_leaves: set[str] = set()
    used_columns: set[str] = set(identity_columns)
    ambiguous: list[str] = []
    for cell in header_cells:
        if cell.letter in identity_columns:
            continue
        candidates: dict[str, Leaf] = {}
        for key in header_keys(cell.text):
            for leaf in leaf_index.get(key, ()):
                candidates[leaf.item_id] = leaf
        if not candidates:
            continue
        if len(candidates) > 1:
            ambiguous.append(cell.letter)
            continue
        leaf = next(iter(candidates.values()))
        if leaf.item_id in used_leaves or cell.letter in used_columns:
            warnings.append(
                f"表头「{cell.text}」与已使用的列/小题重复；未自动映射，请手动指定。"
            )
            continue
        used_leaves.add(leaf.item_id)
        used_columns.add(cell.letter)
        item_columns.append(ScoreItemColumn(itemId=leaf.item_id, column=cell.letter))
    if ambiguous:
        warnings.append(
            "以下表头对应多个计分叶（重复题号）未自动映射：" + "、".join(ambiguous) + "。"
        )
    unmapped_warning = unmapped_leaves_warning(
        leaf_count=len(leaves), mapped_count=len(used_leaves)
    )
    if unmapped_warning:
        warnings.append(unmapped_warning)
    if student_no_column is None and name_column is None and not item_columns:
        return AutoMapping(mapping=None, warnings=tuple(warnings))
    mapping = ScoreColumnMapping(
        workSheet=grid.name,
        headerRow=header_row,
        studentNoColumn=student_no_column,
        nameColumn=name_column,
        itemColumns=item_columns,
    )
    return AutoMapping(mapping=mapping, warnings=tuple(warnings))


def unmapped_leaves_warning(*, leaf_count: int, mapped_count: int) -> str | None:
    """未映射计分叶的统一提示（上传自动映射与教师 PATCH 后共用同一文案）。"""
    unmapped = max(0, leaf_count - mapped_count)
    if unmapped == 0:
        return None
    return (
        f"有 {unmapped} 个计分叶没有映射到列；未映射的叶在确认时按 missing 处理。"
    )


def identity_columns_of(mapping: ScoreColumnMapping) -> frozenset[str]:
    return frozenset(
        column
        for column in (mapping.student_no_column, mapping.name_column)
        if column
    )


def validate_mapping(
    mapping: ScoreColumnMapping,
    *,
    sheet_name: str,
    max_row: int,
    max_column: int,
    leaves: Sequence[Leaf],
) -> None:
    """校验教师映射：列存在、计分叶属于本卷、无重复列/重复叶；否则 422 定位。"""
    issues: list[ErrorIssue] = []
    if mapping.work_sheet != sheet_name:
        raise _mapping_invalid(
            f"映射的工作表「{mapping.work_sheet}」与当前工作表「{sheet_name}」不一致。",
            issues=[
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"当前工作表是「{sheet_name}」。",
                    field="workSheet",
                )
            ],
        )
    if mapping.header_row > max_row:
        raise _mapping_invalid(
            "headerRow 超出工作表范围。",
            issues=[
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"工作表最多 {max_row} 行。",
                    field="headerRow",
                )
            ],
        )
    leaf_by_id = {leaf.item_id: leaf for leaf in leaves}
    for field_name, letter in (
        ("studentNoColumn", mapping.student_no_column),
        ("nameColumn", mapping.name_column),
    ):
        if letter is None:
            continue
        try:
            index = column_index(letter)
        except ValueError:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message="列字母只能是 A-Z（最多 3 位）。",
                    field=field_name,
                )
            )
            continue
        if index > max_column:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"列 {letter} 超出工作表范围（最多 {max_column} 列）。",
                    field=field_name,
                )
            )
    if mapping.student_no_column and mapping.student_no_column == mapping.name_column:
        issues.append(
            _issue(
                None,
                code=SCORE_MAPPING_INVALID,
                message="学号列与姓名列不能是同一列。",
                field="nameColumn",
            )
        )
    identity = identity_columns_of(mapping)
    seen_columns: dict[str, str] = {}
    seen_items: dict[str, str] = {}
    for entry in mapping.item_columns:
        leaf = leaf_by_id.get(entry.item_id)
        if leaf is None:
            issues.append(
                _issue(
                    None,
                    code=SCORE_ITEM_UNKNOWN,
                    message="映射到的小题不属于本次施测的已确认原卷计分叶。",
                    field="itemId",
                )
            )
            continue
        try:
            index = column_index(entry.column)
        except ValueError:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message="列字母只能是 A-Z（最多 3 位）。",
                    column=entry.column,
                    field="itemColumns",
                )
            )
            continue
        if index > max_column:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"列 {entry.column} 超出工作表范围（最多 {max_column} 列）。",
                    column=entry.column,
                    field="itemColumns",
                )
            )
        if entry.column in identity:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message="计分列与身份列不能是同一列。",
                    column=entry.column,
                    field="itemColumns",
                )
            )
        if entry.item_id in seen_items:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"计分叶被映射了多次（另一列：{seen_items[entry.item_id]}）。",
                    column=entry.column,
                    field="itemColumns",
                )
            )
        if entry.column in seen_columns:
            issues.append(
                _issue(
                    None,
                    code=SCORE_MAPPING_INVALID,
                    message=f"同一列映射了多个计分叶（另一叶：{seen_columns[entry.column]}）。",
                    column=entry.column,
                    field="itemColumns",
                )
            )
        seen_items[entry.item_id] = entry.column
        seen_columns[entry.column] = entry.item_id
    if issues:
        raise _mapping_invalid("列映射不合法；本次修改未生效，请修正后重试。", issues=issues)


# --------------------------------------------------------------------------- 行提取


@dataclass(frozen=True)
class ExtractedRow:
    """工作表里的一行（只保留有内容的格 + 身份/计分列，物理坐标原样）。"""

    row_no: int
    cells: tuple[SheetCell, ...]

    def cell_map(self) -> dict[str, SheetCell]:
        return {cell.letter: cell for cell in self.cells}

    def text_at(self, column: str | None) -> str:
        if not column:
            return ""
        target = column.upper()
        for cell in self.cells:
            if cell.letter == target:
                return cell.parse_input().strip()
        return ""


def extract_rows(
    grid: SheetGrid, *, header_row: int, mapping: ScoreColumnMapping
) -> tuple[ExtractedRow, ...]:
    """提取表头之后的数据行。

    数据行 = 身份列或已映射计分列至少有一格非空；纯备注/空行跳过（不制造幽灵行）。
    每行保留全部有内容的格 + 身份/计分列的空白占位（保证物理坐标可回溯）。
    """
    interesting = set(identity_columns_of(mapping)) | {
        entry.column.upper() for entry in mapping.item_columns
    }
    rows: list[ExtractedRow] = []
    total_cells = 0
    for row_no in range(header_row + 1, grid.max_row + 1):
        cells: dict[str, SheetCell] = {}
        for cell in grid.row_cells(row_no):
            if cell.letter in interesting or not cell.is_blank:
                cells[cell.letter] = cell
        for letter in sorted(interesting):
            if letter in cells:
                continue
            try:
                index = column_index(letter)
            except ValueError:  # pragma: no cover - 映射已校验
                continue
            if index > grid.max_column:
                continue
            cells[letter] = SheetCell(
                row=row_no, column=index, text="", cached_text="", is_formula=False
            )
        if not any(not cells[letter].is_blank for letter in interesting):
            continue
        total_cells += len(cells)
        if total_cells > MAX_STORED_CELLS:
            raise AppError(
                f"表格有效单元格超过上限 {MAX_STORED_CELLS}；请拆分后重试（不静默截断）。",
                code="TABLE_TOO_LARGE",
                status_code=422,
            )
        rows.append(
            ExtractedRow(
                row_no=row_no,
                cells=tuple(cells[letter] for letter in sorted(cells)),
            )
        )
    return tuple(rows)


def extract_raw_rows(grid: SheetGrid, *, header_row: int) -> tuple[ExtractedRow, ...]:
    """未识别出列映射时的兜底存储：表头后所有非空物理行与非空格原样保留。

    不做任何解释（身份/计分列都未知），教师 PATCH 映射后由服务层重新读取工作表重建行；
    这里存的是"原件证据"，不是解析结论。
    """
    rows: list[ExtractedRow] = []
    total_cells = 0
    for row_no in range(header_row + 1, grid.max_row + 1):
        cells = list(grid.row_cells(row_no))
        if not cells:
            continue
        total_cells += len(cells)
        if total_cells > MAX_STORED_CELLS:
            raise AppError(
                f"表格有效单元格超过上限 {MAX_STORED_CELLS}；请拆分后重试（不静默截断）。",
                code="TABLE_TOO_LARGE",
                status_code=422,
            )
        rows.append(ExtractedRow(row_no=row_no, cells=tuple(cells)))
    return tuple(rows)


# --------------------------------------------------------------------------- 行定位


@dataclass(frozen=True)
class ParticipantRef:
    """参测人次（预览/确认时读取的快照，用于行定位）。"""

    participant_id: str
    student_id: str
    student_no: str | None
    name: str
    class_id: str
    attempt_no: int
    attendance: str


def describe_participant(participant: ParticipantRef) -> str:
    student_no = participant.student_no if participant.student_no else "无学号"
    return (
        f"{participant.name}（学号 {student_no}，第 {participant.attempt_no} 人次，"
        f"班级 {participant.class_id}，参测记录 {participant.participant_id}）"
    )


@dataclass(frozen=True)
class CellInput:
    """行内一格用于解析的输入（校正优先；空白也保留物理坐标）。

    ``is_formula`` 为 True 时 ``text`` 是 data_only 缓存视图文本；缓存缺失（空）
    **不能**当成 missing 放行——Excel 没算过的公式没有权威分数，必须显式阻断。
    """

    row: int
    column: str
    text: str
    blank: bool
    is_formula: bool = False


@dataclass(frozen=True)
class RowInput:
    """一行用于定位与解析的输入（``explicit_participant_id`` 只来自教师 PATCH）。"""

    row_no: int
    explicit_participant_id: str | None
    cells: Mapping[str, CellInput]

    def text_at(self, column: str | None) -> str:
        if not column:
            return ""
        cell = self.cells.get(column.upper())
        if cell is None or cell.blank:
            return ""
        return cell.text.strip()


@dataclass(frozen=True)
class RowMatch:
    """一行的定位结果；``issues`` 非空表示需要人工指定。"""

    row_no: int
    participant_id: str | None
    candidates: tuple[str, ...]
    issues: tuple[ErrorIssue, ...]


def _candidates(participants: Sequence[ParticipantRef]) -> tuple[str, ...]:
    described = [describe_participant(item) for item in participants[:MAX_ROW_CANDIDATES]]
    if len(participants) > MAX_ROW_CANDIDATES:
        described.append(f"…共 {len(participants)} 条候选")
    return tuple(described)


def match_rows(
    rows: Sequence[RowInput],
    *,
    mapping: ScoreColumnMapping,
    participants: Sequence[ParticipantRef],
) -> tuple[RowMatch, ...]:
    """逐行定位人次：显式 id → 学号文本 → 姓名；歧义不猜，给出候选要求人工指定。"""
    by_id = {item.participant_id: item for item in participants}
    matches: list[RowMatch] = []
    for row in rows:
        explicit = row.explicit_participant_id
        if explicit is not None:
            target = by_id.get(explicit)
            if target is None:
                matches.append(
                    RowMatch(
                        row_no=row.row_no,
                        participant_id=None,
                        candidates=(),
                        issues=(
                            _issue(
                                row.row_no,
                                code=SCORE_ROW_UNRESOLVED,
                                message="指定的参测人次不属于本次施测；请重新指定。",
                                field="participantId",
                            ),
                        ),
                    )
                )
                continue
            matches.append(RowMatch(row.row_no, explicit, (), ()))
            continue

        student_no = row.text_at(mapping.student_no_column)
        name = row.text_at(mapping.name_column)
        by_no = (
            [item for item in participants if item.student_no == student_no]
            if student_no
            else []
        )
        if len(by_no) == 1:
            matches.append(RowMatch(row.row_no, by_no[0].participant_id, (), ()))
            continue
        if len(by_no) > 1:
            matches.append(
                RowMatch(
                    row_no=row.row_no,
                    participant_id=None,
                    candidates=_candidates(by_no),
                    issues=(
                        _issue(
                            row.row_no,
                            code=SCORE_ROW_DUPLICATE_PARTICIPANT,
                            message=(
                                f"学号 {student_no} 对应 {len(by_no)} 个参测人次"
                                "（补考/跨班）；请人工指定 participantId。"
                            ),
                            field="participantId",
                        ),
                    ),
                )
            )
            continue
        # 数字学号丢失前导零（"12" vs "0012"）：不猜、不用姓名顶替，给出候选要求人工指定
        near: list[ParticipantRef] = []
        if student_no:
            digits = student_no.strip().lstrip("0") or "0"
            near = [
                item
                for item in participants
                if item.student_no
                and (item.student_no.strip().lstrip("0") or "0") == digits
                and item.student_no != student_no
            ]
        if near:
            matches.append(
                RowMatch(
                    row_no=row.row_no,
                    participant_id=None,
                    candidates=_candidates(near),
                    issues=(
                        _issue(
                            row.row_no,
                            code=SCORE_ROW_UNRESOLVED,
                            message=(
                                f"学号 {student_no} 与库内学号只差格式（前导零/类型）；"
                                "请人工指定 participantId，服务端不猜。"
                            ),
                            field="participantId",
                        ),
                    ),
                )
            )
            continue
        by_name = [item for item in participants if item.name == name] if name else []
        if len(by_name) == 1:
            matches.append(RowMatch(row.row_no, by_name[0].participant_id, (), ()))
            continue
        if len(by_name) > 1:
            matches.append(
                RowMatch(
                    row_no=row.row_no,
                    participant_id=None,
                    candidates=_candidates(by_name),
                    issues=(
                        _issue(
                            row.row_no,
                            code=SCORE_ROW_DUPLICATE_PARTICIPANT,
                            message=(
                                f"姓名「{name}」对应 {len(by_name)} 个参测人次；"
                                "姓名不是主键，请人工指定 participantId。"
                            ),
                            field="participantId",
                        ),
                    ),
                )
            )
            continue
        # 未匹配：给出候选（若有）后要求人工指定
        if not student_no and not name:
            message = "该行没有学号/姓名，无法定位参测人次；请补齐或手动指定。"
        else:
            message = "该行的学号/姓名在本次施测的参测人次中找不到；请人工指定 participantId。"
        matches.append(
            RowMatch(
                row_no=row.row_no,
                participant_id=None,
                candidates=_candidates(near),
                issues=(
                    _issue(
                        row.row_no,
                        code=SCORE_ROW_UNRESOLVED,
                        message=message,
                        field="participantId",
                    ),
                ),
            )
        )
    return tuple(matches)


# --------------------------------------------------------------------------- 全矩阵预览


@dataclass(frozen=True)
class PreviewCell:
    status: str
    units: int | None = None


@dataclass(frozen=True)
class PreviewMatrix:
    """预览/确认共用的完整矩阵与问题清单（missing 口径的唯一来源）。"""

    participant_count: int
    cells: dict[tuple[str, str], PreviewCell]
    row_matches: dict[int, RowMatch]
    row_participant: dict[int, str | None]
    missing_participant_ids: tuple[str, ...]
    missing_cell_count: int
    absent_by_class: dict[str, tuple[str, ...]]
    absent_participant_ids: tuple[str, ...]
    #: 解析错误（非法文本/超满分/公式无缓存）：写入前一律 422，不落预览
    parse_errors: tuple[ErrorIssue, ...]
    #: 语义冲突（缺考与数值同时出现/标记矛盾）：落预览并阻断确认，要求教师修正
    conflicts: tuple[ErrorIssue, ...]
    warnings: tuple[str, ...]

    @property
    def cell_errors(self) -> tuple[ErrorIssue, ...]:
        """行级展示用的全部单元格问题（解析错误 + 语义冲突）。"""
        return self.parse_errors + self.conflicts

    @property
    def blocking_issues(self) -> tuple[ErrorIssue, ...]:
        issues: list[ErrorIssue] = []
        for match in self.row_matches.values():
            issues.extend(match.issues)
        issues.extend(self.conflicts)
        issues.extend(self.parse_errors)
        return tuple(issues)

    @property
    def blocking(self) -> bool:
        return any(is_blocking_issue(issue) for issue in self.blocking_issues)


def _cell_inputs(row: RowInput, mapping: ScoreColumnMapping) -> dict[str, CellInput]:
    inputs: dict[str, CellInput] = {}
    for entry in mapping.item_columns:
        letter = entry.column.upper()
        cell = row.cells.get(letter)
        if cell is None:
            inputs[letter] = CellInput(
                row=row.row_no, column=letter, text="", blank=True
            )
        else:
            inputs[letter] = cell
    return inputs


def parse_cell(cell: CellInput | None, *, max_units: int) -> CellParse:
    """单元格解析入口（含"公式无缓存"阻断）：不静默把不可判定当 missing。"""
    if cell is None or cell.blank:
        if cell is not None and cell.is_formula:
            return CellParse(
                status="missing",
                code=SCORE_CELL_INVALID,
                message=(
                    "公式单元格没有有效缓存值（data_only 读不到结果）；"
                    "请在 Excel 中重算保存，或把该格填成数值后重新上传。"
                ),
            )
        return CellParse(status="missing")
    return parse_score_text(cell.text, max_units=max_units)


def build_preview(
    *,
    participants: Sequence[ParticipantRef],
    leaves: Sequence[Leaf],
    mapping: ScoreColumnMapping,
    rows: Sequence[RowInput],
) -> PreviewMatrix:
    """构建完整矩阵：冻结参测人次 × 固定计分叶；缺行/缺列/未映射叶显式 missing。"""
    matches = match_rows(rows, mapping=mapping, participants=participants)
    row_by_no = {row.row_no: row for row in rows}
    row_matches = {match.row_no: match for match in matches}

    issues_by_row: dict[int, list[ErrorIssue]] = {
        match.row_no: list(match.issues) for match in matches
    }
    # 同一人次出现在多行：全部阻断，要求人工消歧（服务端不猜哪行有效）
    grouped: dict[str, list[int]] = {}
    for match in matches:
        if match.participant_id:
            grouped.setdefault(match.participant_id, []).append(match.row_no)
    for participant_id, row_nos in grouped.items():
        if len(row_nos) < 2:
            continue
        for row_no in row_nos:
            others = "、".join(f"第 {item} 行" for item in row_nos if item != row_no)
            issues_by_row.setdefault(row_no, []).append(
                _issue(
                    row_no,
                    code=SCORE_ROW_DUPLICATE_PARTICIPANT,
                    message=f"与{others}指向同一参测人次；请人工指定后重试。",
                    field="participantId",
                )
            )

    row_for_participant: dict[str, RowInput] = {}
    for match in matches:
        if match.participant_id and match.participant_id not in row_for_participant:
            row_for_participant[match.participant_id] = row_by_no[match.row_no]

    cells: dict[tuple[str, str], PreviewCell] = {}
    parse_errors: list[ErrorIssue] = []
    conflicts: list[ErrorIssue] = []
    warnings: list[str] = []
    missing_participants: set[str] = set()
    missing_cells = 0
    absent_by_class: dict[str, list[str]] = {}

    # 预索引避免 O(叶数^2)：矩阵可能 ≥100 叶 × 200 人次
    leaf_by_item = {leaf.item_id: leaf for leaf in leaves}
    entry_by_item = {entry.item_id: entry for entry in mapping.item_columns}

    for participant in participants:
        row = row_for_participant.get(participant.participant_id)
        inputs = _cell_inputs(row, mapping) if row is not None else {}
        parsed: dict[str, CellParse] = {}
        for entry in mapping.item_columns:
            letter = entry.column.upper()
            leaf = leaf_by_item.get(entry.item_id)
            if leaf is None:  # pragma: no cover - 映射已校验
                continue
            cell = inputs.get(letter)
            result = parse_cell(cell, max_units=leaf.max_score_units)
            parsed[letter] = result
            if result.is_error:
                parse_errors.append(
                    _issue(
                        cell.row if cell is not None else None,
                        code=result.code or SCORE_CELL_INVALID,
                        message=result.message or "单元格解析失败。",
                        column=letter,
                        field="itemColumns",
                    )
                )

        marker_statuses = {
            result.status
            for result in parsed.values()
            if result.status in ("absent", "exempt")
        }
        asserted: str | None = None
        if participant.attendance in ("absent", "exempt"):
            asserted = participant.attendance
        if len(marker_statuses) > 1:
            conflicts.append(
                _issue(
                    row.row_no if row is not None else None,
                    code=SCORE_CELL_INVALID,
                    message="同一行的分数格同时出现缺考与免考标记；请修正原表。",
                    field="itemColumns",
                )
            )
            marker_statuses = set()
        if len(marker_statuses) == 1:
            marker = next(iter(marker_statuses))
            if asserted is not None and asserted != marker:
                conflicts.append(
                    _issue(
                        row.row_no if row is not None else None,
                        code=SCORE_CELL_INVALID,
                        message=(
                            f"文件把该生记为{_status_label(marker)}，但施测快照出勤是"
                            f"{_status_label(asserted)}；请先校正出勤/原表后重建预览。"
                        ),
                        field="itemColumns",
                    )
                )
            elif asserted is None:
                asserted = marker
                if row is not None:
                    warnings.append(
                        f"文件把参测人次 {participant.participant_id} 记为"
                        f"{_status_label(marker)}，施测快照仍是 present；"
                        "成绩版本按文件记录，不改施测快照。"
                    )
        recorded = {letter: result for letter, result in parsed.items() if result.status == "recorded"}
        if asserted is not None and recorded:
            columns = "、".join(sorted(recorded))
            conflicts.append(
                _issue(
                    row.row_no if row is not None else None,
                    code=SCORE_CELL_INVALID,
                    message=(
                        f"该生被记为{_status_label(asserted)}却同时填了分数（列 {columns}）；"
                        "缺考/免考与数值不能同时出现，请修正原表。"
                    ),
                    field="itemColumns",
                )
            )

        for leaf in leaves:
            entry = entry_by_item.get(leaf.item_id)
            if entry is None:
                parsed_result = CellParse(status="missing")
            else:
                parsed_result = parsed.get(
                    entry.column.upper(), CellParse(status="missing")
                )
            if parsed_result.status == "recorded":
                status, units = "recorded", parsed_result.units
            else:
                # 缺考/免考（快照出勤或文件标记）覆盖空白与同向标记；否则 blank → missing
                status = asserted if asserted is not None else parsed_result.status
                units = None
            cells[(participant.participant_id, leaf.item_id)] = PreviewCell(
                status=status, units=units
            )
            if status == "missing":
                missing_participants.add(participant.participant_id)
                missing_cells += 1
            elif status == "absent":
                absent_by_class.setdefault(participant.class_id, [])
                if participant.participant_id not in absent_by_class[participant.class_id]:
                    absent_by_class[participant.class_id].append(participant.participant_id)

    absent_participants = sorted(
        participant_id
        for ids in absent_by_class.values()
        for participant_id in ids
    )
    return PreviewMatrix(
        participant_count=len(participants),
        cells=cells,
        row_matches=row_matches,
        row_participant={row_no: match.participant_id for row_no, match in row_matches.items()},
        missing_participant_ids=tuple(sorted(missing_participants)),
        missing_cell_count=missing_cells,
        absent_by_class={
            class_id: tuple(sorted(ids)) for class_id, ids in sorted(absent_by_class.items())
        },
        absent_participant_ids=tuple(absent_participants),
        parse_errors=tuple(parse_errors),
        conflicts=tuple(conflicts),
        warnings=tuple(warnings),
    )


def _status_label(status: str) -> str:
    return {"absent": "缺考", "exempt": "免考", "present": "参测", "missing": "空白"}.get(
        status, status
    )


__all__ = [
    "ABSENT_MARKERS",
    "AutoMapping",
    "BLOCKING_ISSUE_CODES",
    "CellInput",
    "CellParse",
    "EXEMPT_MARKERS",
    "ExtractedRow",
    "Leaf",
    "MAX_STORED_CELLS",
    "ParticipantRef",
    "PreviewCell",
    "PreviewMatrix",
    "RowInput",
    "RowMatch",
    "SheetCell",
    "SheetGrid",
    "auto_map",
    "build_leaf",
    "build_preview",
    "column_index",
    "column_letter",
    "describe_participant",
    "detect_header_row",
    "extract_raw_rows",
    "extract_rows",
    "header_keys",
    "identity_columns_of",
    "is_blocking_issue",
    "is_column_letter",
    "match_rows",
    "normalize_text",
    "parse_score_text",
    "question_keys",
    "sheet_grid",
    "unmapped_leaves_warning",
    "validate_mapping",
]
