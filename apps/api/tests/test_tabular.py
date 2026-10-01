"""共享表格读取测试（TEACHING-LOOP B1 / CTRL）。

覆盖 XLSX（openpyxl 现造）与 CSV（UTF-8-BOM / GB18030）解析、表头规范化、
整数数值不写小数尾巴、空行跳过、工作表选择、坏文件与未知格式的明确错误。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.services.tabular import read_csv, read_table, read_xlsx


def _xlsx(tmp_path: Path, rows: list[list[object]], *, sheet: str = "Sheet1") -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    for row in rows:
        worksheet.append(row)
    target = tmp_path / "table.xlsx"
    workbook.save(target)
    return target.read_bytes()


def test_read_xlsx_headers_rows_and_rows_no(tmp_path: Path) -> None:
    content = _xlsx(
        tmp_path,
        [
            ["学号", "姓名", "", "学号"],
            ["0012", "张三", None, "重复表头"],
            [None, None, None, None],
            [12.0, "李四", "x", 34],
        ],
    )
    sheets = read_xlsx(content)
    assert len(sheets) == 1
    table = sheets[0]
    # 重复/空表头规范化：空列名补「列N」，重名加 #2
    assert table.headers == ["学号", "姓名", "列3", "学号#2"]
    assert table.rows == [["0012", "张三", "", "重复表头"], ["12", "李四", "x", "34"]]
    assert table.name == "Sheet1"


def test_read_xlsx_sheet_selection_and_missing(tmp_path: Path) -> None:
    content = _xlsx(tmp_path, [["a"], ["1"]], sheet="名单")
    assert read_xlsx(content, sheet_name="名单")[0].rows == [["1"]]
    with pytest.raises(AppError) as error:
        read_xlsx(content, sheet_name="不存在")
    assert error.value.code == "TABLE_SHEET_MISSING"


def test_read_xlsx_bad_file_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        read_xlsx(b"not an xlsx at all")
    assert error.value.code == "TABLE_PARSE_FAILED"


def test_read_csv_utf8_bom_and_gb18030() -> None:
    bom = "学号,姓名\n0012,张三\n".encode("utf-8-sig")
    table = read_csv(bom, name="名单.csv")
    assert table.headers == ["学号", "姓名"]
    assert table.rows == [["0012", "张三"]]

    legacy = "学号,姓名\n0007,李四\n".encode("gb18030")
    table = read_csv(legacy, name="名单.csv")
    assert table.rows == [["0007", "李四"]]


def test_read_csv_undecodable_is_explicit() -> None:
    with pytest.raises(AppError) as error:
        read_csv(b"\xff\xfe\x00\x01\x02\x03")
    assert error.value.code == "TABLE_PARSE_FAILED"


def test_read_table_dispatch_by_extension_and_media_type(tmp_path: Path) -> None:
    content = _xlsx(tmp_path, [["a"], ["1"]])
    assert read_table(content, file_name="表.xlsx")[0].rows == [["1"]]
    csv_bytes = b"a\n1\n"
    assert read_table(csv_bytes, file_name="表.csv")[0].rows == [["1"]]
    assert read_table(content, file_name="无后缀", media_type="application/octet-stream")[0].rows == [["1"]]
    with pytest.raises(AppError) as error:
        read_table(b"x", file_name="表.txt", media_type="application/pdf")
    assert error.value.code == "UNSUPPORTED_DOCUMENT_FORMAT"


def test_empty_table_returns_empty_rows(tmp_path: Path) -> None:
    content = _xlsx(tmp_path, [["学号", "姓名"]])
    table = read_xlsx(content)[0]
    assert table.headers == ["学号", "姓名"]
    assert table.rows == []
    empty_csv = read_csv(b"", name="empty.csv")
    assert empty_csv.headers == []
    assert empty_csv.rows == []


# --------------------------------------------------------------------------- 成绩原始读取（B3 / T60）

def _score_xlsx(tmp_path: Path, rows: list[list[object]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    target = tmp_path / "scores.xlsx"
    workbook.save(target)
    return target.read_bytes()


def test_read_score_sheet_keeps_physical_grid_and_views(tmp_path: Path) -> None:
    from app.services.tabular import read_score_sheet

    content = _score_xlsx(
        tmp_path,
        [
            ["学号", "Q1", "Q2"],
            ["0012", 2, 3],
            [],  # 物理空行必须保留（错误定位要能指到原表行号）
            ["0013", "=B2+1", None],
        ],
    )
    sheet = read_score_sheet(content)[0]
    assert (sheet.name, sheet.max_row, sheet.max_column) == ("Sheet", 4, 3)
    # 前导零保持文本；物理坐标一一对应
    assert sheet.rows[1][0].text == "0012"
    assert sheet.rows[1][0].row == 2 and sheet.rows[1][0].column == 1
    assert sheet.rows[1][1].data_type == "n"
    # 空行保留且全空
    assert all(cell.is_blank for cell in sheet.rows[2])
    # 公式视图给公式文本；缓存缺失即空（不执行公式）
    formula_cell = sheet.rows[3][1]
    assert formula_cell.formula == "=B2+1"
    assert formula_cell.text == "=B2+1"
    assert formula_cell.cached_text == ""
    assert sheet.rows[3][2].is_blank is True


def test_read_score_sheet_wide_grid_is_linear(tmp_path: Path) -> None:
    """200×102 规模守卫：旧实现逐格 ``.cell()`` 会重扫整表（该表约 40 分钟），
    线性读取应在秒级完成——本用例不设时间断言，靠套件超时天然兜底。"""
    from app.services.tabular import read_score_sheet

    rows: list[list[object]] = [["学号", *[f"Q{i}" for i in range(1, 101)]]]
    for index in range(1, 201):
        rows.append([f"{index:04d}", *[(index + column) % 7 for column in range(1, 101)]])
    sheet = read_score_sheet(_score_xlsx(tmp_path, rows))[0]
    assert (sheet.max_row, sheet.max_column) == (201, 101)
    assert sheet.rows[200][0].text == "0200"
    assert sheet.rows[200][100].text == str((200 + 100) % 7)
    assert all(cell.is_blank is False for cell in sheet.rows[200][1:])


def test_read_score_sheet_csv_physical_lines_and_limits() -> None:
    from app.services.tabular import read_score_sheet

    content = "姓名,Q1,Q2\n甲,2,3\n\n乙,,\n".encode("utf-8")
    sheet = read_score_sheet(content)[0]
    assert sheet.name == "CSV"
    assert (sheet.max_row, sheet.max_column) == (4, 3)
    # 物理行号 = 文件行号（含空行），CSV 无公式视图
    assert sheet.rows[1][0].text == "甲"
    assert all(cell.is_blank for cell in sheet.rows[2])
    assert sheet.rows[3][1].is_blank is True
    assert sheet.rows[1][1].formula is None
    assert sheet.rows[1][1].text == sheet.rows[1][1].cached_text == "2"

    with pytest.raises(AppError) as error:
        read_score_sheet(b"a,b\n" + b"1,2\n" * 3001, max_rows=2000)
    assert error.value.code == "TABLE_TOO_LARGE"
    with pytest.raises(AppError) as error:
        read_score_sheet(",".join(f"c{i}" for i in range(10)).encode() + b"\n", max_columns=5)
    assert error.value.code == "TABLE_TOO_LARGE"
