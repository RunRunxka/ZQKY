"""把结构化知识点结果渲染成人类可读正文（text.delta 的正文来源）。

渲染只使用已核验证据与已校验知识点，不添加任何未出现在证据中的讲解：
没有证据时只说明"证据不足"，概括未完成时明确标注并原样给出教材原文。
"""

from __future__ import annotations

from app.schemas.rag_v2 import RagResultV2, TextbookEvidence

FOOTER = "以上为教材原文摘录与知识点概括，供核对题目；本轮未提供独立解题推导，人工教学质量验收尚未完成。"


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


def render_result(result: RagResultV2) -> str:
    if result.status == "no_evidence":
        reason = result.reason or "当前教材范围没有找到足够依据。"
        return f"\n\n{reason}\n\n"
    blocks: list[str] = []
    if result.points:
        blocks.append("\n\n### 教材知识点（本地概括）\n")
    else:
        blocks.append("\n\n### 教材定位（本地概括未完成）\n")
    if result.reason:
        blocks.append(result.reason + "\n")
    for point in result.points:
        refs = "、".join(point.evidenceIds)
        blocks.append(f"**{point.title}**（{refs}）\n\n{point.summary}\n")
    if result.evidence:
        blocks.append("\n### 教材原文摘录\n")
        for item in result.evidence:
            blocks.append(f"**[{item.evidenceId}] {location_of(item)}{locator_label(item.locator)}**\n")
            blocks.append("\n".join("> " + line for line in item.text.split("\n")) + "\n")
    blocks.append(FOOTER + "\n")
    return "\n".join(blocks)


__all__ = ["FOOTER", "locator_label", "location_of", "render_result"]
