"""知识点导入：表头映射、行规范化、父树校验与确认计划（TEACHING-LOOP B1 / T20）。

本模块是导入流程的**纯规则层**：只做字符串/结构处理与**只读** SQL 校验（经注入的
``KnowledgePointRepository``），不写库、不解析文件、不调用模型。服务层负责在
``coordinator.publication(...)`` 内、单事务里应用这里产出的计划。

固定行为（B1 任务卡 §2.4）：

- 表头映射六个字段 ``subjectCode/code/name/description/parentCode/aliases``；
  自动映射支持大小写与中文同义词（``学科/编码/名称/说明/父级/别名``）；
- 别名按 ``、,;；/``（含换行）拆分，去空白、按规范化值去重；
- 逐行校验：缺 ``code``/``name``、批内 ``code`` 重复、父 ``code`` 批内/既有都不存在、
  环、目标或父已归档、``create`` 撞既有 ``code`` 都会生成**可定位**的 ``ErrorIssue``；
- 阻断问题（``BLOCKING_ISSUE_CODES``）只在**确认时**拒绝（预览不阻断）；
- 更新行空白可选字段默认"不修改"，清空需要知识点级 ``clearFields``；
- 环与父树由 DB 触发器/K 兜底，本模块先给可定位错误。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.contracts.knowledge import (
    KNOWLEDGE_IMPORT_FIELDS,
    KNOWLEDGE_ROW_ACTIONS,
    KnowledgeSuggestionCandidate,
)
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.repositories.knowledge.imports import ImportRowInput, ImportRowRecord
from app.repositories.knowledge.points import (
    KnowledgePointRepository,
    invalid,
    normalize_alias,
    revision_conflict,
)
from app.services.tabular import SheetTable

#: 每个字段可接受的表头（大小写折叠 + NFKC 后比较；`#2` 之类的去重后缀会被剥掉）
HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "subjectCode": ("subjectcode", "subject_code", "subject", "学科", "学科编码"),
    "code": ("code", "编码", "知识点编码", "编号"),
    "name": ("name", "名称", "知识点名称", "标题"),
    "description": ("description", "desc", "说明", "描述", "定义"),
    "parentCode": ("parentcode", "parent_code", "父级", "父级编码", "父编码", "上级"),
    "aliases": ("aliases", "alias", "别名", "同义词"),
}
#: 缺失会让整批无意义的列
REQUIRED_FIELDS: tuple[str, ...] = ("code", "name")

#: 阻断确认的问题码：确认时必须为零（预览只展示，不阻断）
BLOCKING_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "KNOWLEDGE_ROW_INVALID",
        "KNOWLEDGE_ROW_MISSING_CODE",
        "KNOWLEDGE_ROW_MISSING_NAME",
        "KNOWLEDGE_ROW_DUPLICATE_CODE",
        "KNOWLEDGE_PARENT_INVALID",
        "KNOWLEDGE_CROSS_SUBJECT_PARENT",
        "KNOWLEDGE_CYCLE",
        "KNOWLEDGE_ARCHIVED",
        "KNOWLEDGE_CODE_CONFLICT",
    }
)

#: 括号级问题码（非阻断）：缺列/未知列/学科不一致
MISSING_COLUMN_CODE = "KNOWLEDGE_IMPORT_MISSING_COLUMN"
UNKNOWN_COLUMN_CODE = "KNOWLEDGE_IMPORT_UNKNOWN_COLUMN"
SUBJECT_MISMATCH_CODE = "KNOWLEDGE_IMPORT_SUBJECT_MISMATCH"

_ALIAS_SPLIT = re.compile(r"[、,;；/\n\r]+")
_DUPLICATE_SUFFIX = re.compile(r"#\d+$")
_WHITESPACE = re.compile(r"\s+")

MAX_ALIAS_WARNINGS = 10


# --------------------------------------------------------------------------- 行草稿


@dataclass
class RowDraft:
    """派生中的一行（校验会就地补 ``target``/``base``/``issues``）。"""

    row_no: int
    name: str
    code: str
    parent_code: str | None
    description: str
    aliases: tuple[str, ...]
    raw_cells: dict[str, Any]
    target_knowledge_point_id: str | None = None
    base_revision: int | None = None
    base_revision_id: str | None = None
    decision: str | None = None
    issues: list[ErrorIssue] = field(default_factory=list)

    def to_input(self) -> ImportRowInput:
        return ImportRowInput(
            row_no=self.row_no,
            name=self.name,
            code=self.code,
            parent_code=self.parent_code,
            description=self.description,
            aliases=self.aliases,
            target_knowledge_point_id=self.target_knowledge_point_id,
            base_revision=self.base_revision,
            base_revision_id=self.base_revision_id,
            decision=self.decision,
            raw_cells=self.raw_cells,
            issues=[item.model_dump(exclude_none=True) for item in self.issues],
        )


@dataclass(frozen=True)
class DerivedImport:
    """一次派生结果：可直接落库的行 + 批次级 issues/warnings。"""

    rows: list[ImportRowInput]
    batch_issues: list[ErrorIssue]
    warnings: list[str]


@dataclass(frozen=True)
class AiRowSource:
    """AI 候选行来源：已校验候选 + 模型原始对象 + 证据/置信度提示。"""

    candidate: KnowledgeSuggestionCandidate
    raw: dict[str, Any]
    issues: tuple[ErrorIssue, ...] = ()


@dataclass(frozen=True)
class PlanEntry:
    """确认计划的一行：动作 + 本次写入所需的一切字段。"""

    row_no: int
    action: str
    code: str
    name: str
    description: str
    aliases: tuple[str, ...]
    parent_code: str | None
    parent_point_id: str | None
    target_point_id: str | None
    expected_revision: int | None


# --------------------------------------------------------------------------- 表头映射


def normalize_header(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).strip()
    text = _DUPLICATE_SUFFIX.sub("", text)
    return _WHITESPACE.sub(" ", text).casefold()


def auto_map(headers: Sequence[str]) -> dict[str, str]:
    """按同义词表自动映射（同名字段取第一个命中的表头）。"""
    lookup: dict[str, str] = {}
    for header in headers:
        key = normalize_header(header)
        if key and key not in lookup:
            lookup[key] = header
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for field_name in KNOWLEDGE_IMPORT_FIELDS:
        for synonym in HEADER_SYNONYMS[field_name]:
            header = lookup.get(synonym)
            if header is not None and header not in used:
                mapping[field_name] = header
                used.add(header)
                break
    return mapping


def validate_mapping(mapping: dict[str, str] | None, headers: Sequence[str]) -> dict[str, str]:
    """手工映射校验：字段名必须在六字段内、表头必须存在（大小写折叠后比较）。"""
    if mapping is None:
        return {}
    if not isinstance(mapping, dict):
        raise invalid("mapping 必须是 JSON 对象。")
    normalized_headers = {normalize_header(header): header for header in headers}
    resolved: dict[str, str] = {}
    fields: list[str] = []
    for key, value in mapping.items():
        if key not in KNOWLEDGE_IMPORT_FIELDS:
            raise AppError(
                f"映射字段必须是 {list(KNOWLEDGE_IMPORT_FIELDS)} 之一：{key!r}。",
                code="INVALID_REQUEST",
                status_code=422,
                details=error_details(fields=[str(key)]),
            )
        if not isinstance(value, str) or not value.strip():
            raise AppError(
                f"映射 {key} 的表头必须是非空字符串。",
                code="INVALID_REQUEST",
                status_code=422,
                details=error_details(fields=[key]),
            )
        header = normalized_headers.get(normalize_header(value))
        if header is None:
            fields.append(value)
            continue
        resolved[key] = header
    if fields:
        raise AppError(
            f"映射指向了不存在的列：{', '.join(fields)}。",
            code="INVALID_REQUEST",
            status_code=422,
            details=error_details(fields=fields),
        )
    return resolved


def batch_issues_for(
    mapping: dict[str, str], headers: Sequence[str], *, ai: bool = False
) -> list[ErrorIssue]:
    """批次级（非阻断）问题：缺必需列、存在未映射的多余列。"""
    issues: list[ErrorIssue] = []
    if ai:
        return issues
    for field_name in REQUIRED_FIELDS:
        if field_name not in mapping:
            issues.append(
                ErrorIssue(
                    field=field_name,
                    code=MISSING_COLUMN_CODE,
                    message=(
                        f"缺少必需列 {field_name}：未映射到任何表头，"
                        "该列缺失时相关行会在确认时被拒绝。"
                    ),
                )
            )
    mapped_headers = set(mapping.values())
    for header in headers:
        if header not in mapped_headers:
            issues.append(
                ErrorIssue(
                    column=header,
                    code=UNKNOWN_COLUMN_CODE,
                    message=f"列「{header}」未被映射，已忽略。",
                )
            )
    return issues


# --------------------------------------------------------------------------- 行派生


def _cell(cells: dict[str, Any], mapping: dict[str, str], field_name: str) -> str:
    """按映射取单元格文本（字段未映射或缺列 → 空字符串）。"""
    header = mapping.get(field_name)
    if not header:
        return ""
    value = cells.get(header)
    if value is None:
        return ""
    return str(value).strip()


def split_aliases(value: str) -> tuple[str, ...]:
    """按 ``、,;；/``（含换行）拆分别名，去空白并按规范化值去重。"""
    if not isinstance(value, str) or not value.strip():
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for part in _ALIAS_SPLIT.split(value):
        text = part.strip()
        if not text:
            continue
        key = normalize_alias(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return tuple(result)


def derive_file_rows(
    conn: Any,
    *,
    subject_id: str,
    table: SheetTable,
    mapping: dict[str, str],
    points: KnowledgePointRepository,
) -> DerivedImport:
    """把工作表按映射派生为可落库的行（含逐行校验），不做任何写入。"""
    headers = list(table.headers)
    rows: list[RowDraft] = []
    for index, raw in enumerate(table.rows, start=1):
        cells: dict[str, Any] = {}
        for position, header in enumerate(headers):
            if position < len(raw):
                cells[header] = raw[position]
        row = RowDraft(
            row_no=index,
            name=_cell(cells, mapping, "name"),
            code=_cell(cells, mapping, "code"),
            parent_code=_cell(cells, mapping, "parentCode") or None,
            description=_cell(cells, mapping, "description"),
            aliases=split_aliases(_cell(cells, mapping, "aliases")),
            raw_cells=cells,
        )
        subject_cell = _cell(cells, mapping, "subjectCode")
        if subject_cell and subject_cell != subject_id:
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column=mapping.get("subjectCode"),
                    field="subjectCode",
                    code=SUBJECT_MISMATCH_CODE,
                    message=(
                        f"该行学科编码为「{subject_cell}」，与批次学科「{subject_id}」不一致；"
                        "已按批次学科处理。"
                    ),
                )
            )
        rows.append(row)
    warnings = validate_rows(conn, subject_id=subject_id, rows=rows, points=points, mapping=mapping)
    return DerivedImport(
        rows=[row.to_input() for row in rows],
        batch_issues=batch_issues_for(mapping, headers),
        warnings=warnings,
    )


def derive_ai_rows(
    conn: Any,
    *,
    subject_id: str,
    sources: Sequence[AiRowSource],
    points: KnowledgePointRepository,
) -> DerivedImport:
    """把模型候选派生为待确认行（同一套父树/重复校验，不写正式表）。"""
    rows: list[RowDraft] = []
    for index, source in enumerate(sources, start=1):
        candidate = source.candidate
        row = RowDraft(
            row_no=index,
            name=candidate.name,
            code=candidate.code,
            parent_code=candidate.parent_code,
            description=candidate.description,
            aliases=tuple(candidate.aliases),
            raw_cells=dict(source.raw),
            issues=list(source.issues),
        )
        if candidate.existing_knowledge_point_id is not None:
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    field="existingKnowledgePointId",
                    code="KNOWLEDGE_SUGGESTION_EXISTING_REFERENCE",
                    message=(
                        "模型认为该候选对应既有知识点 "
                        f"{candidate.existing_knowledge_point_id}；请在确认前人工核对。"
                    ),
                )
            )
        rows.append(row)
    warnings = validate_rows(conn, subject_id=subject_id, rows=rows, points=points, mapping=None)
    return DerivedImport(
        rows=[row.to_input() for row in rows], batch_issues=[], warnings=warnings
    )


def validate_rows(
    conn: Any,
    *,
    subject_id: str,
    rows: list[RowDraft],
    points: KnowledgePointRepository,
    mapping: dict[str, str] | None = None,
) -> list[str]:
    """就地补全目标/基线/建议动作与问题；返回跨知识点别名提示（只提示，不合并）。"""
    mapping = mapping or {}

    def column(field_name: str | None) -> str | None:
        return mapping.get(field_name) if field_name else None

    by_code: dict[str, list[RowDraft]] = {}
    for row in rows:
        if row.code:
            by_code.setdefault(row.code, []).append(row)

    for row in rows:
        if not row.code:
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column=column("code"),
                    field="code",
                    code="KNOWLEDGE_ROW_MISSING_CODE",
                    message="缺少知识点编码（code）。",
                )
            )
        if not row.name:
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column=column("name"),
                    field="name",
                    code="KNOWLEDGE_ROW_MISSING_NAME",
                    message="缺少知识点名称（name）。",
                )
            )

    for code, group in by_code.items():
        if len(group) > 1:
            numbers = "、".join(str(item.row_no) for item in group)
            for row in group:
                row.issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        column=column("code"),
                        field="code",
                        code="KNOWLEDGE_ROW_DUPLICATE_CODE",
                        message=f"批内编码重复：{code}（第 {numbers} 行）；请先改成唯一编码。",
                    )
                )

    # 既有知识点：同 (学科, code) → update 目标 + 基线（归档目标阻断）
    for row in rows:
        if not row.code:
            continue
        existing = points.get_by_code(conn, subject_id=subject_id, code=row.code)
        if existing is None:
            continue
        row.target_knowledge_point_id = existing.point_id
        row.base_revision = existing.revision
        row.base_revision_id = existing.revision_id
        if row.decision is None:
            row.decision = "update"
        if existing.status == "archived":
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column=column("code"),
                    field="code",
                    code="KNOWLEDGE_ARCHIVED",
                    message="该编码对应已归档知识点：归档保留历史，但新引用/更新必须先恢复。",
                )
            )

    # 父节点：既有（同科）→ 直接引用；批内 → 拓扑序创建；否则阻断
    for row in rows:
        if not row.parent_code:
            continue
        if row.parent_code == row.code:
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    column=column("parentCode"),
                    field="parentCode",
                    code="KNOWLEDGE_PARENT_INVALID",
                    message="父级编码不能是本行自身的编码。",
                )
            )
            continue
        parent = points.get_by_code(conn, subject_id=subject_id, code=row.parent_code)
        if parent is not None:
            if parent.status == "archived":
                row.issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        column=column("parentCode"),
                        field="parentCode",
                        code="KNOWLEDGE_ARCHIVED",
                        message=f"父级「{row.parent_code}」已归档，不能作为新引用的父节点。",
                    )
                )
            elif parent.point_id == row.target_knowledge_point_id:
                row.issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        column=column("parentCode"),
                        field="parentCode",
                        code="KNOWLEDGE_PARENT_INVALID",
                        message="父级不能是本行自身的知识点。",
                    )
                )
            continue
        if row.parent_code in by_code:
            continue  # 批内父节点：确认时按拓扑序先建
        row.issues.append(
            ErrorIssue(
                row=row.row_no,
                column=column("parentCode"),
                field="parentCode",
                code="KNOWLEDGE_PARENT_INVALID",
                message=(
                    f"父级编码「{row.parent_code}」在本批与既有知识点中都不存在；"
                    "请先建立父节点或修正编码。"
                ),
            )
        )

    _mark_cycles(rows, by_code)

    # 别名歧义：同学科其他知识点已用同别名 → 只提示，绝不自动合并
    warnings: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for alias in row.aliases:
            key = normalize_alias(alias)
            if key in seen:
                continue
            others = points.points_with_alias(
                conn,
                subject_id=subject_id,
                normalized_alias=key,
                exclude_point_id=row.target_knowledge_point_id,
            )
            if not others:
                continue
            seen.add(key)
            if len(warnings) >= MAX_ALIAS_WARNINGS:
                continue
            warnings.append(
                f"别名「{alias}」在学科内已指向其他知识点（{', '.join(others[:3])}）："
                "只提示，不自动合并。"
            )
    return warnings


def _mark_cycles(rows: list[RowDraft], by_code: dict[str, list[RowDraft]]) -> None:
    """批内父链成环（或依赖成环节点）的行标 ``KNOWLEDGE_CYCLE``（阻断）。

    Kahn 消元：反复移除"父节点不是批内待创建编码"的节点，剩下的节点就是成环或
    依赖环的节点。
    """
    edges: dict[str, str] = {}
    for code, group in by_code.items():
        row = group[0]
        if row.parent_code and row.parent_code in by_code and row.target_knowledge_point_id is None:
            edges[code] = row.parent_code
    remaining = dict(edges)
    changed = True
    while changed:
        changed = False
        for code in list(remaining):
            if remaining[code] not in remaining:
                del remaining[code]
                changed = True
    if not remaining:
        return
    for code in remaining:
        for row in by_code.get(code, []):
            row.issues.append(
                ErrorIssue(
                    row=row.row_no,
                    field="parentCode",
                    code="KNOWLEDGE_CYCLE",
                    message=f"批内父链形成环（编码 {code}）；请修正父级编码。",
                )
            )


# --------------------------------------------------------------------------- 确认计划


def plan_confirm(
    conn: Any,
    *,
    subject_id: str,
    rows: Sequence[ImportRowRecord],
    actions: dict[int, tuple[str, int | None]],
    points: KnowledgePointRepository,
) -> tuple[list[PlanEntry], list[ErrorIssue], list[ErrorIssue]]:
    """确认时以**当前**库状态重新校验并生成计划。

    返回 ``(计划, 阻断问题, 请求级问题)``：

    - 阻断问题（父树/重复/归档/`create` 撞 code 等）→ 422 ``KNOWLEDGE_IMPORT_BLOCKING_ISSUES``；
    - 请求级问题（某行没有最终动作）→ 422 ``KNOWLEDGE_ROW_INVALID``，逐行定位；
    - ``actions``：``{row_no: (action, expected_revision)}``；缺省回落到行内 ``decision``；
    - ``update`` 行核 ``expectedRevision``（缺省用预览冻结的 ``baseRevision``），
      不符抛 409 ``REVISION_CONFLICT`` + ``details.currentRevision``；
    - 计划顺序：``create`` 行按批内拓扑序（父先子后），其余按行号。
    """
    fresh: list[RowDraft] = []
    for record in rows:
        fresh.append(
            RowDraft(
                row_no=record.row_no,
                name=record.name,
                code=record.code,
                parent_code=record.parent_code,
                description=record.description,
                aliases=tuple(record.aliases),
                raw_cells={},
                target_knowledge_point_id=None,
                decision=record.decision,
            )
        )
    validate_rows(conn, subject_id=subject_id, rows=fresh, points=points, mapping=None)

    stored = {record.row_no: record for record in rows}
    issues: list[ErrorIssue] = []
    for row in fresh:
        for item in row.issues:
            if item.code in BLOCKING_ISSUE_CODES:
                issues.append(item)

    create_entries: dict[str, PlanEntry] = {}
    other_entries: list[PlanEntry] = []
    update_targets: dict[str, int] = {}
    request_issues: list[ErrorIssue] = []
    for row in fresh:
        action, expected = actions.get(row.row_no, (row.decision, None))
        row_issues: list[ErrorIssue] = []
        if action is None:
            request_issues.append(
                ErrorIssue(
                    row=row.row_no,
                    field="decision",
                    code="KNOWLEDGE_ROW_INVALID",
                    message="该行没有最终动作：请在 actions 或行 decision 里给出 create/update/ignore。",
                )
            )
        elif action not in KNOWLEDGE_ROW_ACTIONS:
            request_issues.append(
                ErrorIssue(
                    row=row.row_no,
                    field="decision",
                    code="KNOWLEDGE_ROW_INVALID",
                    message=f"未知动作：{action!r}。",
                )
            )
        elif action == "update":
            target_id = row.target_knowledge_point_id
            if target_id is None:
                row_issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        field="code",
                        code="KNOWLEDGE_ROW_INVALID",
                        message="update 行没有匹配的既有知识点；请改成 create 或忽略该行。",
                    )
                )
            else:
                expected_revision = expected if expected is not None else row.base_revision
                current = points.get_point(conn, target_id)
                if current is None:
                    row_issues.append(
                        ErrorIssue(
                            row=row.row_no,
                            field="code",
                            code="KNOWLEDGE_ROW_INVALID",
                            message="update 目标知识点已不存在。",
                        )
                    )
                else:
                    if current.status == "archived":
                        row_issues.append(
                            ErrorIssue(
                                row=row.row_no,
                                field="code",
                                code="KNOWLEDGE_ARCHIVED",
                                message="update 目标已归档；请先恢复该知识点。",
                            )
                        )
                    if expected_revision is None:
                        row_issues.append(
                            ErrorIssue(
                                row=row.row_no,
                                field="expectedRevision",
                                code="KNOWLEDGE_ROW_INVALID",
                                message="update 行缺少 expectedRevision（且没有预览基线）。",
                            )
                        )
                    elif current.revision != expected_revision:
                        raise revision_conflict(current.revision)
                    if target_id in update_targets:
                        row_issues.append(
                            ErrorIssue(
                                row=row.row_no,
                                field="code",
                                code="KNOWLEDGE_ROW_INVALID",
                                message=(
                                    f"同一知识点（{target_id}）在本批出现多次 update"
                                    f"（第 {update_targets[target_id]} 行已占用）。"
                                ),
                            )
                        )
                    else:
                        update_targets[target_id] = row.row_no
        elif action == "create":
            if row.target_knowledge_point_id is not None:
                row_issues.append(
                    ErrorIssue(
                        row=row.row_no,
                        field="code",
                        code="KNOWLEDGE_CODE_CONFLICT",
                        message=(
                            f"编码「{row.code}」已存在知识点 "
                            f"{row.target_knowledge_point_id}，不能 create；请改用 update。"
                        ),
                    )
                )
        issues.extend(row_issues)
        if row_issues:
            continue
        entry = PlanEntry(
            row_no=row.row_no,
            action=action,
            code=row.code,
            name=row.name,
            description=row.description,
            aliases=tuple(row.aliases),
            parent_code=row.parent_code,
            parent_point_id=_existing_parent_id(
                conn, subject_id=subject_id, parent_code=row.parent_code, points=points
            )
            if row.parent_code
            else None,
            target_point_id=row.target_knowledge_point_id,
            expected_revision=expected if expected is not None else row.base_revision,
        )
        if action == "create":
            create_entries[row.code] = entry
        else:
            other_entries.append(entry)

    if issues or request_issues:
        return [], issues, request_issues
    ordered = _topological(create_entries, issues)
    if issues:
        return [], issues, request_issues
    ordered.extend(sorted(other_entries, key=lambda item: item.row_no))
    return ordered, [], []


def _existing_parent_id(
    conn: Any, *, subject_id: str, parent_code: str | None, points: KnowledgePointRepository
) -> str | None:
    if not parent_code:
        return None
    parent = points.get_by_code(conn, subject_id=subject_id, code=parent_code)
    return parent.point_id if parent is not None else None


def _topological(
    create_entries: dict[str, PlanEntry], issues: list[ErrorIssue]
) -> list[PlanEntry]:
    """批内父先子后的拓扑序；成环则记 ``KNOWLEDGE_CYCLE``（防御性兜底）。"""
    remaining = dict(create_entries)
    ordered: list[PlanEntry] = []
    while remaining:
        ready = [
            entry
            for code, entry in remaining.items()
            if entry.parent_code not in remaining
        ]
        if not ready:
            for code, entry in sorted(remaining.items()):
                issues.append(
                    ErrorIssue(
                        row=entry.row_no,
                        field="parentCode",
                        code="KNOWLEDGE_CYCLE",
                        message=f"批内父链形成环（编码 {code}），无法确定写入顺序。",
                    )
                )
            return ordered
        for entry in sorted(ready, key=lambda item: item.row_no):
            ordered.append(entry)
            del remaining[entry.code]
    return ordered


__all__ = [
    "BLOCKING_ISSUE_CODES",
    "MISSING_COLUMN_CODE",
    "REQUIRED_FIELDS",
    "SUBJECT_MISMATCH_CODE",
    "UNKNOWN_COLUMN_CODE",
    "AiRowSource",
    "DerivedImport",
    "PlanEntry",
    "RowDraft",
    "auto_map",
    "batch_issues_for",
    "derive_ai_rows",
    "derive_file_rows",
    "normalize_header",
    "plan_confirm",
    "split_aliases",
    "validate_mapping",
    "validate_rows",
]
