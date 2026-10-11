"""表格文件读取（XLSX/CSV）：知识点导入与名单导入共用的唯一实现。

- XLSX 用 ``openpyxl``（**只读**模式，``data_only=True`` 读工作簿已有缓存值，不执行公式）；
- CSV 用标准库（UTF-8 / UTF-8-BOM，尽量少猜编码；解析失败给出可读错误）；
- 读出的是**字符串化单元格**：调用方负责类型判断与错误定位（``issues`` 带行列号）。
- 本模块不做业务校验、不落库、不写资产；只把文件变成 (工作表列表, 行) 的形状，
  便于同一份文件在预览与确认之间保持一致。
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.core.exceptions import AppError

XLSX_MEDIA_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }
)
CSV_MEDIA_TYPES = frozenset({"text/csv", "text/plain", "application/csv"})

MAX_SHEETS = 20
MAX_ROWS = 5000
MAX_COLUMNS = 64
#: 单元格文本上限：超过按截断处理（防止畸形表格把预览撑爆）
MAX_CELL_CHARS = 20000


@dataclass(frozen=True)
class SheetTable:
    """一张工作表（或一个 CSV 文件）的表头与前若干行。``row_no`` 为 1 基表行号。"""

    name: str
    headers: list[str]
    rows: list[list[str]]


def _cell_to_text(value: object) -> str:
    return _full_cell_text(value)[:MAX_CELL_CHARS]


def _full_cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        # 数字学号在 XLSX 里常是数值：整数不写小数尾巴，避免 12.0 这类噪声
        return str(int(value))
    return str(value)


def _normalize_headers(raw: list[str]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(raw):
        base = item.strip() or f"列{index + 1}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        headers.append(base if count == 1 else f"{base}#{count}")
    return headers


def _trim_rows(rows: list[list[str]]) -> list[list[str]]:
    trimmed: list[list[str]] = []
    for row in rows:
        if all(cell.strip() == "" for cell in row):
            continue
        trimmed.append(row)
        if len(trimmed) >= MAX_ROWS:
            break
    return trimmed


def read_xlsx(content: bytes, *, sheet_name: str | None = None) -> list[SheetTable]:
    """读 XLSX 的所有（或指定）工作表；第一行视为表头。"""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        raise AppError(
            "缺少表格解析依赖（openpyxl），无法读取 XLSX。",
            code="TABLE_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl 的异常种类多，统一成可读错误
        raise AppError(
            f"表格文件无法解析：{exc.__class__.__name__}。",
            code="TABLE_PARSE_FAILED",
            status_code=422,
        ) from exc
    sheets: list[SheetTable] = []
    try:
        for name in workbook.sheetnames[:MAX_SHEETS]:
            if sheet_name is not None and name != sheet_name:
                continue
            worksheet = workbook[name]
            rows: list[list[str]] = []
            for raw_row in worksheet.iter_rows(values_only=True):
                row = [_cell_to_text(cell) for cell in list(raw_row)[:MAX_COLUMNS]]
                rows.append(row)
                if len(rows) > MAX_ROWS + 1:
                    break
            if not rows:
                sheets.append(SheetTable(name=name, headers=[], rows=[]))
                continue
            headers = _normalize_headers(rows[0])
            body = _trim_rows(rows[1:])
            sheets.append(SheetTable(name=name, headers=headers, rows=body))
    finally:
        workbook.close()
    if not sheets:
        raise AppError(
            f"找不到工作表：{sheet_name}。",
            code="TABLE_SHEET_MISSING",
            status_code=422,
        )
    return sheets


def _decode_csv_text(content: bytes) -> str:
    """严格解码共享策略；不能替换原字节后把乱码当成绩/身份依据。"""
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise AppError(
            "CSV 文本无法按 UTF-8/GB18030 解码。",
            code="TABLE_PARSE_FAILED",
            status_code=422,
        )
    return text


def read_csv(content: bytes, *, name: str = "csv") -> SheetTable:
    reader = csv.reader(io.StringIO(_decode_csv_text(content)))
    rows: list[list[str]] = []
    for raw_row in reader:
        rows.append([_cell_to_text(cell) for cell in raw_row[:MAX_COLUMNS]])
        if len(rows) > MAX_ROWS + 1:
            break
    if not rows:
        return SheetTable(name=name, headers=[], rows=[])
    headers = _normalize_headers(rows[0])
    return SheetTable(name=name, headers=headers, rows=_trim_rows(rows[1:]))


def read_table(
    content: bytes, *, file_name: str, media_type: str = "", sheet_name: str | None = None
) -> list[SheetTable]:
    """按文件名/媒体类型分派；未知类型明确 422（不猜）。"""
    lowered = file_name.lower()
    if lowered.endswith(".xlsx") or media_type in XLSX_MEDIA_TYPES:
        return read_xlsx(content, sheet_name=sheet_name)
    if lowered.endswith(".csv") or media_type in CSV_MEDIA_TYPES:
        return [read_csv(content, name=file_name or "csv")]
    raise AppError(
        f"不支持的表格格式：{file_name or media_type or '未知'}（只支持 .xlsx / .csv）。",
        code="UNSUPPORTED_DOCUMENT_FORMAT",
        status_code=422,
    )

# --------------------------------------------------------------------------- 成绩原始读取（B3/T60）

MAX_SCORE_ROWS = 2000
MAX_SCORE_COLUMNS = 600
MAX_SCORE_CELL_CHARS = 20000


def _score_cell_text(value: object, *, sheet: str, row: int, column: int, view: str) -> str:
    """成绩原值只保留完整文本或定位拒绝，不能截断后再作为权威输入。"""
    text = _full_cell_text(value)
    if len(text) > MAX_SCORE_CELL_CHARS:
        from openpyxl.utils.cell import get_column_letter

        column_name = get_column_letter(column)
        raise AppError(
            f"工作表「{sheet}」{column_name}{row} 的{view}文本超过{MAX_SCORE_CELL_CHARS}字符；原值未截断，请修正原表。",
            code="TABLE_TOO_LARGE", status_code=422,
            details={"sheet": sheet, "row": row, "column": column_name,
                     "address": f"{column_name}{row}", "view": view,
                     "actualLength": len(text), "maxLength": MAX_SCORE_CELL_CHARS},
        )
    return text


@dataclass(frozen=True)
class RawCell:
    """带物理坐标与公式/缓存双视图的单元格（成绩权威输入，不做去空行/截列）。"""

    row: int                 # 1 基物理行
    column: int              # 1 基物理列
    text: str                # 公式视图的文本（公式单元格为公式文本）
    cached_text: str         # data_only 视图的文本（公式单元格为其缓存值；无缓存为 ""）
    formula: str | None      # 公式文本（以 = 开头）或 None
    data_type: str           # openpyxl cell.data_type：n/s/b/d/f/空
    is_blank: bool           # 两个视图都为空白


@dataclass(frozen=True)
class RawSheet:
    """保留物理空行空列的成绩工作表；``rows`` 的每个元素与物理行一一对应。"""

    name: str
    max_row: int
    max_column: int
    rows: list[list[RawCell]]     # rows[r-1][c-1] 对应物理 (r,c)


def _grid_from_sheet(
    sheet: object, *, max_row: int, max_column: int
) -> list[list[tuple[object, str]]]:
    """一次遍历物化 (value, data_type) 网格；缺位补 (None, "")。

    read-only 工作表上 ``ws.cell(r,c)`` 每次调用都可能重扫整表（实测 51×102 → 211s），
    ``iter_rows`` 才是线性读取路径。
    """
    grid: list[list[tuple[object, str]]] = [
        [(None, "") for _ in range(max_column)] for _ in range(max_row)
    ]
    iterator = sheet.iter_rows(
        min_row=1, max_row=max_row, min_col=1, max_col=max_column
    )
    for row_index, row in enumerate(iterator):
        if row_index >= max_row:
            break
        for column_index, cell in enumerate(row):
            if column_index >= max_column:
                break
            grid[row_index][column_index] = (
                cell.value,
                str(getattr(cell, "data_type", "") or ""),
            )
    return grid


def _materialize_cell_rows(
    formula_sheet: object,
    cached_sheet: object,
    *,
    sheet_name: str,
    max_row: int,
    max_column: int,
) -> list[list[RawCell]]:
    formula_grid = _grid_from_sheet(
        formula_sheet, max_row=max_row, max_column=max_column
    )
    cached_grid = _grid_from_sheet(
        cached_sheet, max_row=max_row, max_column=max_column
    )
    rows: list[list[RawCell]] = []
    for row_index in range(max_row):
        row_cells: list[RawCell] = []
        for column_index in range(max_column):
            formula_value, data_type = formula_grid[row_index][column_index]
            cached_value = cached_grid[row_index][column_index][0]
            text = _score_cell_text(formula_value, sheet=sheet_name, row=row_index + 1,
                                    column=column_index + 1, view="formula")
            cached_text = _score_cell_text(cached_value, sheet=sheet_name, row=row_index + 1,
                                           column=column_index + 1, view="cached")
            formula = (
                text
                if isinstance(formula_value, str) and formula_value.startswith("=")
                else None
            )
            row_cells.append(
                RawCell(
                    row=row_index + 1,
                    column=column_index + 1,
                    text=text,
                    cached_text=cached_text,
                    formula=formula,
                    data_type=data_type,
                    is_blank=(formula_value is None and cached_value is None),
                )
            )
        rows.append(row_cells)
    return rows


def _read_score_csv(
    content: bytes, *, max_rows: int, max_columns: int
) -> list[RawSheet]:
    """CSV 成绩表：物理行号=文件行号（含空行），无公式视图，单表 ``name="CSV"``。"""
    text = _decode_csv_text(content)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        raw_rows = list(reader)
    except csv.Error as exc:
        raise AppError(
            "CSV 字段或记录无法解析；原文未截断，请检查原文件。",
            code="TABLE_PARSE_FAILED", status_code=422,
            details={"sheet": "CSV", "row": max(1, reader.line_num)},
        ) from exc
    if len(raw_rows) > max_rows:
        raise AppError(
            f"CSV 行数 {len(raw_rows)} 超过上限 {max_rows}；请拆分后重试。",
            code="TABLE_TOO_LARGE",
            status_code=422,
        )
    width = max((len(row) for row in raw_rows), default=0)
    if width > max_columns:
        raise AppError(
            f"CSV 列数 {width} 超过上限 {max_columns}；请拆分后重试。",
            code="TABLE_TOO_LARGE",
            status_code=422,
        )
    rows: list[list[RawCell]] = []
    for row_index, record in enumerate(raw_rows, start=1):
        row_cells: list[RawCell] = []
        for column_index in range(1, width + 1):
            value = record[column_index - 1] if column_index - 1 < len(record) else ""
            text_value = _score_cell_text(value, sheet="CSV", row=row_index,
                                          column=column_index, view="csv")
            row_cells.append(
                RawCell(
                    row=row_index,
                    column=column_index,
                    text=text_value,
                    cached_text=text_value,
                    formula=None,
                    data_type="s" if text_value != "" else "",
                    is_blank=text_value == "",
                )
            )
        rows.append(row_cells)
    return [RawSheet(name="CSV", max_row=len(raw_rows), max_column=width, rows=rows)]


def read_score_sheet(
    content: bytes,
    *,
    sheet_name: str | None = None,
    max_rows: int = MAX_SCORE_ROWS,
    max_columns: int = MAX_SCORE_COLUMNS,
) -> list[RawSheet]:
    """按**公式视图 + data_only 缓存视图**读取 XLSX/CSV（成绩导入专用）。

    - 不计算公式、不调用 Excel：``data_only=True`` 读的是工作簿已有缓存值，缓存缺失即为 ""；
    - 保留物理空行空列与真实行列坐标（错误定位必须指向原文件位置）；
    - 行列或文件超限**明确报错**（不静默截断）；
    - CSV（非 ZIP 内容）返回单张 ``name="CSV"`` 的工作表：无公式视图，物理行号即文件行号；
    - 读取用 ``iter_rows`` 一次性物化（read-only 工作表上逐格 ``.cell()`` 会每格重扫整表，
      实测 200×100 不可收敛），内存上限由 ``max_rows×max_columns`` 封顶。
    """
    if not content[:4] == b"PK\x03\x04":
        return _read_score_csv(
            content, max_rows=max_rows, max_columns=max_columns
        )
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise AppError(
            "缺少表格解析依赖（openpyxl），无法读取 XLSX。",
            code="TABLE_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc
    try:
        formula_book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        cached_book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise AppError(
            f"表格文件无法解析：{exc.__class__.__name__}。",
            code="TABLE_PARSE_FAILED",
            status_code=422,
        ) from exc

    sheets: list[RawSheet] = []
    try:
        for name in formula_book.sheetnames[:MAX_SHEETS]:
            if sheet_name is not None and name != sheet_name:
                continue
            formula_sheet = formula_book[name]
            cached_sheet = cached_book[name]
            max_row = max(int(formula_sheet.max_row or 0), int(cached_sheet.max_row or 0))
            max_column = max(
                int(formula_sheet.max_column or 0), int(cached_sheet.max_column or 0)
            )
            if max_row > max_rows:
                raise AppError(
                    f"工作表「{name}」行数 {max_row} 超过上限 {max_rows}；请拆分后重试。",
                    code="TABLE_TOO_LARGE",
                    status_code=422,
                )
            if max_column > max_columns:
                raise AppError(
                    f"工作表「{name}」列数 {max_column} 超过上限 {max_columns}；请拆分后重试。",
                    code="TABLE_TOO_LARGE",
                    status_code=422,
                )
            rows = _materialize_cell_rows(
                formula_sheet, cached_sheet, sheet_name=name, max_row=max_row, max_column=max_column
            )
            sheets.append(
                RawSheet(name=name, max_row=max_row, max_column=max_column, rows=rows)
            )
    finally:
        formula_book.close()
        cached_book.close()
    if not sheets:
        raise AppError(
            f"找不到工作表：{sheet_name}。", code="TABLE_SHEET_MISSING", status_code=422
        )
    return sheets
