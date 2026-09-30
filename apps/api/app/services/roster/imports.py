"""名单表格分析（纯函数层，TEACHING-LOOP B1 / T30-a）。

只做"单元格 → 预览行"的确定性转换：表头同义词、映射解析、行抽取、问题检测与建议分类；
**不读文件、不写库、不调用模型**。文件读取统一走 ``app/services/tabular.py``，
持久化统一走 ``app/repositories/teaching/roster.py``。

口径（与任务卡一致）：

- **学号是文本**：``0012`` 原样保留，绝不数值化、不补零、不去零；空字符串视为"无学号"。
- 行号 ``rowNo`` 是**数据行序号（1 基，不含表头）**，预览、PATCH、确认与错误定位都用它。
- 建议（``suggestion``）不构成写入决定，只提示人工动作：
  - 有学号且按 ``(owner, studentNo)`` 命中 → ``link``；命中但姓名不符 → 追加
    ``ROSTER_ROW_INVALID``（field=name）且建议 ``name_mismatch``（**绝不自动改姓名**）；
  - 有学号未命中 → ``create``；无学号 → ``no_student_no``（必须人工 link 或 create）；
  - 同批重复（同学号，或同名且都无学号）→ ``duplicate`` + 两侧都标 issue；
  - 同名多命中（无学号）→ ``conflict`` + issue（**不静默选第一人**）。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Protocol, Sequence

from app.contracts.roster import (
    ROSTER_IMPORT_FIELDS,
    ROSTER_MAPPING_INVALID,
    ROSTER_ROW_INVALID,
    RosterRowSuggestion,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.repositories.teaching.roster import ROSTER_NAME_CONFLICT, ROSTER_ROW_DUPLICATE

MAX_NAME_CHARS = 120
MAX_STUDENT_NO_CHARS = 64

#: 自动映射同义词（比较时忽略大小写与空白；显式 mapping 优先于自动结果）
HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "studentNo": (
        "学号",
        "学生学号",
        "学籍号",
        "学籍辅号",
        "考号",
        "编号",
        "studentno",
        "student_no",
        "student number",
        "number",
        "no",
    ),
    "name": (
        "姓名",
        "学生姓名",
        "名字",
        "name",
        "student name",
        "studentname",
        "student_name",
    ),
}


class _StudentLike(Protocol):
    """分析层只依赖学生的稳定身份与姓名，不关心仓储实现。"""

    id: str
    name: str


def mapping_invalid(message: str) -> AppError:
    return AppError(
        message,
        code=ROSTER_MAPPING_INVALID,
        status_code=422,
        details=error_details(fields=["mapping"]),
    )


def _header_key(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("\u3000", "")


def auto_mapping(headers: Sequence[str]) -> dict[str, str]:
    """按同义词给出 ``{字段: 表头}``；每个字段取第一个命中的表头。"""
    by_key: dict[str, str] = {}
    for header in headers:
        key = _header_key(header)
        by_key.setdefault(key, header)
    mapping: dict[str, str] = {}
    for field_name in ROSTER_IMPORT_FIELDS:
        for synonym in HEADER_SYNONYMS[field_name]:
            found = by_key.get(_header_key(synonym))
            if found is not None:
                mapping[field_name] = found
                break
    return mapping


def resolve_mapping(
    headers: Sequence[str], mapping: dict[str, str] | None = None
) -> dict[str, str]:
    """解析/校验映射：``{字段: 表头}``；缺 name 列、未知字段、未知表头都 422。

    ``mapping is None`` 时按同义词自动映射；显式给出 ``mapping`` 时**完全按它执行**
    （不自动补全）——这样"不映射学号列"是可用显式请求表达的意图。
    """
    if not headers:
        raise mapping_invalid("表格没有表头行，无法识别「学号/姓名」列。")
    available = set(headers)
    resolved: dict[str, str] = {}
    if mapping is not None:
        if not isinstance(mapping, dict):
            raise mapping_invalid("mapping 必须是 JSON 对象。")
        for key, value in mapping.items():
            if key not in ROSTER_IMPORT_FIELDS:
                raise mapping_invalid(
                    f"未知映射字段 {key!r}；只允许 {list(ROSTER_IMPORT_FIELDS)}。"
                )
            if not isinstance(value, str) or value.strip() not in available:
                raise mapping_invalid(f"映射列 {value!r} 不在表头中。")
            resolved[key] = value.strip()
    else:
        resolved = auto_mapping(headers)
    if "name" not in resolved:
        raise mapping_invalid("未能识别姓名列；请在 mapping 里指定 name 对应的表头。")
    if len(set(resolved.values())) != len(resolved):
        raise mapping_invalid("mapping 的不同字段不能指向同一列。")
    return resolved


@dataclass(frozen=True)
class ExtractedRow:
    """按映射抽取的一行（尚未与库内学生匹配）。"""

    row_no: int
    name: str
    student_no: str | None
    raw_cells: dict[str, str]


@dataclass(frozen=True)
class AnalyzedRow:
    """预览行：抽取结果 + 匹配 + 问题（建议由 ``suggestion_of`` 派生）。"""

    row_no: int
    name: str
    student_no: str | None
    matched_student_id: str | None
    issues: tuple[ErrorIssue, ...]
    raw_cells: dict[str, str]


def extract_rows(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    mapping: dict[str, str],
) -> list[ExtractedRow]:
    """逐行按映射取「姓名/学号」；``studentNo`` 单元格为空 → ``None``（文本保持不变）。"""
    name_header = mapping["name"]
    no_header = mapping.get("studentNo")
    name_index = list(headers).index(name_header)
    no_index = list(headers).index(no_header) if no_header is not None else None

    extracted: list[ExtractedRow] = []
    for offset, cells in enumerate(rows):
        values = list(cells)
        raw_cells = {
            header: (values[index] if index < len(values) else "")
            for index, header in enumerate(headers)
        }
        name = raw_cells.get(name_header, "").strip()
        raw_no = raw_cells.get(no_header, "") if no_header is not None else ""
        student_no = raw_no.strip() or None
        extracted.append(
            ExtractedRow(
                row_no=offset + 1,
                name=name,
                student_no=student_no,
                raw_cells=raw_cells,
            )
        )
    return extracted


def extract_rows_from_raw(
    raw_rows: Sequence[tuple[int, dict[str, str]]],
    mapping: dict[str, str],
) -> list[ExtractedRow]:
    """按新映射从已持久化的审计原文重算行（改映射时使用，行号原样保留）。"""
    name_header = mapping["name"]
    no_header = mapping.get("studentNo")
    extracted: list[ExtractedRow] = []
    for row_no, raw_cells in raw_rows:
        name = raw_cells.get(name_header, "").strip()
        raw_no = raw_cells.get(no_header, "") if no_header is not None else ""
        extracted.append(
            ExtractedRow(
                row_no=row_no,
                name=name,
                student_no=raw_no.strip() or None,
                raw_cells=dict(raw_cells),
            )
        )
    return extracted


def analyze_rows(
    extracted: Sequence[ExtractedRow],
    *,
    by_student_no: dict[str, _StudentLike],
    by_name: dict[str, list[_StudentLike]],
) -> list[AnalyzedRow]:
    """逐行匹配与问题检测；批量重复行在最后统一标记（两侧都标）。"""
    rows: list[AnalyzedRow] = []
    for row in extracted:
        issues: list[ErrorIssue] = []
        matched_student_id: str | None = None
        if not row.name:
            issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column="name",
                    field="name",
                    code=ROSTER_ROW_INVALID,
                    message="姓名为空，只能 link 到既有学生或 ignore。",
                )
            )
        elif len(row.name) > MAX_NAME_CHARS:
            issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column="name",
                    field="name",
                    code=ROSTER_ROW_INVALID,
                    message=f"姓名超过 {MAX_NAME_CHARS} 字上限。",
                )
            )
        if row.student_no is not None:
            if len(row.student_no) > MAX_STUDENT_NO_CHARS:
                issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        column="studentNo",
                        field="studentNo",
                        code=ROSTER_ROW_INVALID,
                        message=f"学号超过 {MAX_STUDENT_NO_CHARS} 字上限。",
                    )
                )
            matched = by_student_no.get(row.student_no)
            if matched is not None:
                matched_student_id = matched.id
                if row.name and matched.name != row.name:
                    issues.append(
                        ErrorIssue(
                            row=row.row_no,
                            column="name",
                            field="name",
                            code=ROSTER_ROW_INVALID,
                            message="学号命中的学生姓名与表格不一致，请人工确认（不自动改名）。",
                        )
                    )
        else:
            candidates = by_name.get(row.name, []) if row.name else []
            if len(candidates) >= 2:
                issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        column="name",
                        field="name",
                        code=ROSTER_NAME_CONFLICT,
                        message=f"同名学生在库中有 {len(candidates)} 人，请人工指定 link 目标（不自动选第一人）。",
                    )
                )
        rows.append(
            AnalyzedRow(
                row_no=row.row_no,
                name=row.name,
                student_no=row.student_no,
                matched_student_id=matched_student_id,
                issues=tuple(issues),
                raw_cells=row.raw_cells,
            )
        )
    return _mark_duplicates(rows)


def duplicate_groups(rows: Sequence[tuple[int, str, str | None]]) -> list[list[int]]:
    """同批重复分组（``row_no`` 列表）：同学号，或同名且都无学号。

    预览标记与确认消歧共用同一口径，避免"预览说重复、确认却不拦"。
    """
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row_no, name, student_no in rows:
        if student_no:
            groups[("studentNo", student_no)].append(row_no)
        elif name:
            groups[("name", name)].append(row_no)
    return [sorted(indexes) for indexes in groups.values() if len(indexes) >= 2]


def _mark_duplicates(rows: list[AnalyzedRow]) -> list[AnalyzedRow]:
    groups = duplicate_groups(
        [(row.row_no, row.name, row.student_no) for row in rows]
    )
    if not groups:
        return rows
    by_no = {row.row_no: index for index, row in enumerate(rows)}
    extra: dict[int, list[ErrorIssue]] = defaultdict(list)
    for indexes in groups:
        for row_no in indexes:
            others = [item for item in indexes if item != row_no]
            joined = "、".join(f"第 {item} 行" for item in others)
            column = "studentNo" if rows[by_no[row_no]].student_no else "name"
            extra[row_no].append(
                ErrorIssue(
                    row=row_no,
                    column=column,
                    field=column,
                    code=ROSTER_ROW_DUPLICATE,
                    message=f"与{joined}重复（同学号或同名同特征），需人工消歧。",
                )
            )
    return [
        replace(row, issues=row.issues + tuple(extra.get(row.row_no, ())))
        for row in rows
    ]


def suggestion_of(
    *,
    name: str,
    student_no: str | None,
    matched_student_id: str | None,
    issues: Sequence[ErrorIssue],
) -> RosterRowSuggestion:
    """由持久化的匹配结果与问题派生行建议（优先级见模块 docstring）。"""
    codes = {issue.code for issue in issues}
    if ROSTER_ROW_DUPLICATE in codes:
        return "duplicate"
    if ROSTER_NAME_CONFLICT in codes:
        return "conflict"
    if matched_student_id is not None and student_no is not None:
        mismatch = any(
            issue.code == ROSTER_ROW_INVALID and issue.field == "name"
            for issue in issues
        )
        return "name_mismatch" if mismatch else "link"
    if student_no is None:
        return "no_student_no"
    return "create"


def is_blocking_issue(issue: ErrorIssue) -> bool:
    return issue.code in (ROSTER_ROW_DUPLICATE, ROSTER_NAME_CONFLICT)


__all__ = [
    "AnalyzedRow",
    "ExtractedRow",
    "HEADER_SYNONYMS",
    "MAX_NAME_CHARS",
    "MAX_STUDENT_NO_CHARS",
    "analyze_rows",
    "auto_mapping",
    "duplicate_groups",
    "extract_rows",
    "extract_rows_from_raw",
    "is_blocking_issue",
    "mapping_invalid",
    "resolve_mapping",
    "suggestion_of",
]
