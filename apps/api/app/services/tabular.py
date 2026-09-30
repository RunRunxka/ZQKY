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
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        # 数字学号在 XLSX 里常是数值：整数不写小数尾巴，避免 12.0 这类噪声
        return str(int(value))
    text = str(value)
    return text[:MAX_CELL_CHARS]


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


def read_csv(content: bytes, *, name: str = "csv") -> SheetTable:
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
    reader = csv.reader(io.StringIO(text))
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
