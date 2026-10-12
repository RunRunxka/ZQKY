"""教材目录 → 知识点树生成（C4-1）：chapter_path 反向建树，幂等。

约定：章节作为**容器节点**（与普通知识点同表，靠目录层级与命名表达；不加列），
教师可在任何节点下继续自定义增删改（走既有 create/update/delete）。
节点 code = ``TB-`` + sha1(subject|docTitle|父路径)[:12]，同一路径重复生成只建一次。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

#: 单次生成的节点上限（防异常教材把库撑爆）。
MAX_NODES = 400


@dataclass(frozen=True)
class TextbookInput:
    """一本教材的目录输入：标题 + 该书全部 chunk 的 chapter_path 集合。"""

    title: str
    document_id: str
    chapter_paths: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class NodePlan:
    """待创建节点：code 全局幂等键；parentCode 为空 = 顶层。"""

    code: str
    name: str
    parent_code: str | None
    sort_order: int
    document_id: str


@dataclass(frozen=True)
class TreePlan:
    nodes: tuple[NodePlan, ...] = field(default_factory=tuple)


def _code_for(subject_id: str, doc_title: str, path: tuple[str, ...]) -> str:
    payload = "|".join((subject_id, doc_title, *path))
    return "TB-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def plan_tree(subject_id: str, books: list[TextbookInput]) -> TreePlan:
    """把各教材的 chapter_path 集合规划成节点列表（文档 → 章 → 节，去重、限上限）。"""
    nodes: dict[str, NodePlan] = {}
    sort_seed = 0
    for book in books:
        title = book.title.strip() or f"教材 {book.document_id}"
        root_code = _code_for(subject_id, title, ())
        if root_code not in nodes:
            nodes[root_code] = NodePlan(code=root_code, name=title, parent_code=None, sort_order=len(nodes), document_id=book.document_id)
        for path in book.chapter_paths:
            cumulative: tuple[str, ...] = ()
            for segment in path:
                name = segment.strip()
                if not name:
                    continue
                cumulative = (*cumulative, name)
                code = _code_for(subject_id, title, cumulative)
                if code not in nodes:
                    if len(nodes) >= MAX_NODES:
                        return TreePlan(nodes=tuple(nodes.values()))
                    nodes[code] = NodePlan(
                        code=code,
                        name=name,
                        parent_code=_code_for(subject_id, title, cumulative[:-1]) if cumulative[:-1] else root_code,
                        sort_order=len(nodes),
                        document_id=book.document_id,
                    )
                sort_seed += 1
    return TreePlan(nodes=tuple(nodes.values()))


__all__ = ["MAX_NODES", "NodePlan", "TextbookInput", "TreePlan", "plan_tree"]
