"""把结构化知识点结果渲染成人类可读正文（text.delta 的正文来源）。

RAG-QUALITY v1.1（PLAN §2.1 / §3.4）：**首答正文只包含知识点**，不追加教材原文摘录。

- 正文形态：编号 + 标题 + 说明 + ``[n]`` 引用编号（``[n]`` 按证据在结果中的顺序编号，
  与前端来源面板的折叠顺序一致；没有对应证据的引用按首次出现顺序补号）；
- 不再输出 ``> `` 原文块、不再输出 ``ev-…`` 长标识、不再输出整段教材原文——
  原文由前端结构化"教材依据"面板按需展开；
- 不输出完整解题推导，不追加任何固定工程尾注；
- ``no_evidence`` / ``partial`` 时正文保持可读：直接给出原因，并说明证据仍可展开核对；
- :func:`body_char_count` 是 ``RagPresentation.bodyCharCount`` 的唯一口径
  （标题 + 说明的 Unicode 码点数，不含引用编号与来源）。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.rag_v2 import RagPoint, RagResultV2, TextbookEvidence

POINTS_HEADING = "### 教材知识点"
FALLBACK_HEADING = "### 教材定位（本地概括未完成）"


def locator_label(locator) -> str:
    if locator.kind == "markdown" and locator.lineStart is not None and locator.lineEnd is not None:
        return f" · 第 {locator.lineStart}–{locator.lineEnd} 行"
    if locator.kind == "pdf" and locator.pageStart is not None and locator.pageEnd is not None:
        return f" · 第 {locator.pageStart}–{locator.pageEnd} 页"
    if locator.kind == "docx" and locator.blockStart is not None and locator.blockEnd is not None:
        return f" · 第 {locator.blockStart}–{locator.blockEnd} 段"
    return ""


def location_of(item: TextbookEvidence) -> str:
    return " → ".join([item.title, *item.chapterPath]) if item.chapterPath else item.title


def body_char_count(points: Sequence[RagPoint]) -> int:
    """知识点正文码点数（标题 + 说明），不含引用编号与来源（PLAN §3.4 的长度口径）。"""
    return sum(len(point.title) + len(point.summary) for point in points)


def reference_labels(result: RagResultV2) -> dict[str, int]:
    """``[n]`` 编号：先按结果里的证据顺序，再按知识点里的首次出现顺序补齐。"""
    labels: dict[str, int] = {}
    for index, item in enumerate(result.evidence, start=1):
        labels.setdefault(item.evidenceId, index)
    next_label = len(labels) + 1
    for point in result.points:
        for evidence_id in point.evidenceIds:
            if evidence_id not in labels:
                labels[evidence_id] = next_label
                next_label += 1
    return labels


def render_result(result: RagResultV2) -> str:
    """只渲染知识点正文（失败状态渲染可读原因）；证据由前端结构化来源面板展示。"""
    if result.status == "no_evidence":
        reason = result.reason or "当前教材范围没有找到足够依据。"
        return f"\n\n{reason}\n\n"
    blocks: list[str] = []
    if result.points:
        blocks.append("\n\n" + POINTS_HEADING + "\n")
    else:
        blocks.append("\n\n" + FALLBACK_HEADING + "\n")
    if result.reason:
        blocks.append(result.reason + "\n")
    labels = reference_labels(result)
    for index, point in enumerate(result.points, start=1):
        refs = "".join(f"[{labels[evidence_id]}]" for evidence_id in point.evidenceIds)
        blocks.append(f"{index}. **{point.title}**\n   {point.summary}{refs}\n")
    if not result.points and result.evidence:
        blocks.append("教材原文已保留，可在「教材依据」中逐条展开核对。\n")
    return "\n".join(blocks)


__all__ = [
    "FALLBACK_HEADING",
    "POINTS_HEADING",
    "body_char_count",
    "locator_label",
    "location_of",
    "reference_labels",
    "render_result",
]
