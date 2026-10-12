"""知识点跨库引用检查（任务①·彻底删除守卫的唯一真实实现）。

删除知识点前必须逐项清点三个库里的引用；任一命中 → 409 ``KNOWLEDGE_POINT_IN_USE``，
``details.counts`` 逐库给出计数，**绝不**静默放行。本模块只做**只读**查询：

- 知识点库（``KnowledgeCatalog``）：``textbook_knowledge_links`` 中该点**任一修订**
  的教材依据行数（同一连接里查，删除事务前先核验）；
- 教学库（``TeachingCatalog``）：``paper_item_knowledge`` 按表 schema 同时带
  ``knowledge_point_id`` 与 ``knowledge_revision_id``，因此按**知识点身份**统计
  （覆盖该点的全部历史修订，名称快照不作为匹配依据）；
- 题库（``QuestionBankCatalog``）：``question_knowledge_links`` 与
  ``question_draft_knowledge_links`` 都以 ``knowledge_point_id`` 为引用键，同样按
  知识点身份统计。

端口（``KnowledgeReferenceChecker`` Protocol）由 ``main.py`` 的知识点运行时装配段
注入真实实现；服务层在端口缺失时返回 503 ``SERVICE_UNAVAILABLE``（可重试），
**不**把"检查不到"当成"没有引用"。

引用计数在 ``PublicationCoordinator.publication(...)`` 内、删除写事务**之前**执行
（与教材依据核验同一纪律）：锁内只做数据库读取，不做网络/解析/推理。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.contracts.knowledge import KNOWLEDGE_POINT_IN_USE
from app.core.exceptions import AppError
from app.core.sqlite import open_readonly

#: 教学库只读打开需要的表（引用计数只碰 paper_item_knowledge）
_TEACHING_REQUIRED = ("paper_item_knowledge", "file_assets")
#: 题库只读打开需要的表（引用计数只碰两张 knowledge link 表）
_QUESTION_BANK_REQUIRED = ("question_revisions", "question_drafts")


@dataclass(frozen=True)
class ReferenceCounts:
    """一次引用清点的逐项计数（0 表示该侧没有引用）。"""

    textbook_links: int
    paper_items: int
    question_links: int
    question_draft_links: int

    @property
    def total(self) -> int:
        return (
            self.textbook_links + self.paper_items + self.question_links
            + self.question_draft_links
        )

    def as_details(self) -> list[dict[str, Any]]:
        """``details.counts`` 的对外形状（camelCase，逐项可展示）。"""
        return [
            {"library": "knowledge", "key": "textbookKnowledgeLinks", "count": self.textbook_links},
            {"library": "teaching", "key": "paperItemKnowledge", "count": self.paper_items},
            {
                "library": "question_bank",
                "key": "questionKnowledgeLinks",
                "count": self.question_links,
            },
            {
                "library": "question_bank",
                "key": "questionDraftKnowledgeLinks",
                "count": self.question_draft_links,
            },
        ]


class KnowledgeReferenceChecker(Protocol):
    """知识点引用检查端口（服务层只依赖本形状；真实实现与测试替身都可注入）。"""

    def count_references(self, point_id: str) -> ReferenceCounts:
        """清点各库对该知识点的引用；实现必须只读、不抛"没有引用"的假结果。"""
        ...


def in_use_error(counts: ReferenceCounts) -> AppError:
    """构造 409 ``KNOWLEDGE_POINT_IN_USE``（details.counts 逐库逐项计数）。"""
    return AppError(
        "知识点仍在使用中：存在教材依据、原卷题目或题库引用，先解除引用或改用归档。",
        code=KNOWLEDGE_POINT_IN_USE,
        status_code=409,
        details={"counts": counts.as_details()},
    )


class CrossLibraryReferenceChecker:
    """跨库引用计数真实实现：三个库路径在装配时注入，每次调用只读打开。"""

    def __init__(
        self,
        *,
        knowledge_catalog: Any,
        teaching_catalog: Any | None = None,
        question_bank_catalog: Any | None = None,
    ) -> None:
        self._knowledge = knowledge_catalog
        self._teaching = teaching_catalog
        self._question_bank = question_bank_catalog

    def count_references(self, point_id: str) -> ReferenceCounts:
        """清点知识点库 / 教学库 / 题库对该点的全部引用（只读，无连接共享）。"""
        point_id = _text(point_id)
        return ReferenceCounts(
            textbook_links=self._count_textbook_links(point_id),
            paper_items=self._count_paper_items(point_id),
            question_links=self._count_question_links(point_id),
            question_draft_links=self._count_question_draft_links(point_id),
        )

    # ------------------------------------------------------------------ 知识点库

    def _count_textbook_links(self, point_id: str) -> int:
        """教材依据行数：该点**任一修订**的 textbook_knowledge_links 行。"""
        with self._knowledge.read_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM textbook_knowledge_links "
                "WHERE knowledge_point_id = ?",
                (point_id,),
            ).fetchone()
        return int(row["total"])

    # ------------------------------------------------------------------ 教学库

    def _count_paper_items(self, point_id: str) -> int:
        """原卷题目关联数：paper_item_knowledge.knowledge_point_id 直接引用本点。

        教学库未装配（隔离部署）时按 0 处理：没有库就没有引用，不伪造"被引用"。
        """
        if self._teaching is None:
            return 0
        conn = open_readonly(self._teaching.db_path, required_tables=_TEACHING_REQUIRED)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM paper_item_knowledge "
                "WHERE knowledge_point_id = ?",
                (point_id,),
            ).fetchone()
        finally:
            conn.close()
        return int(row["total"])

    # ------------------------------------------------------------------ 题库

    def _count_question_links(self, point_id: str) -> int:
        """题库正式关联数：question_knowledge_links 引用本点的行（不可变表）。"""
        if self._question_bank is None:
            return 0
        conn = open_readonly(self._question_bank.db_path, required_tables=_QUESTION_BANK_REQUIRED)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM question_knowledge_links "
                "WHERE knowledge_point_id = ?",
                (point_id,),
            ).fetchone()
        finally:
            conn.close()
        return int(row["total"])

    def _count_question_draft_links(self, point_id: str) -> int:
        """题库草稿关联数：question_draft_knowledge_links 引用本点的行。"""
        if self._question_bank is None:
            return 0
        conn = open_readonly(self._question_bank.db_path, required_tables=_QUESTION_BANK_REQUIRED)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM question_draft_knowledge_links "
                "WHERE knowledge_point_id = ?",
                (point_id,),
            ).fetchone()
        finally:
            conn.close()
        return int(row["total"])


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError("pointId 必须是非空字符串。", code="INVALID_REQUEST", status_code=422)
    return value.strip()


__all__ = [
    "CrossLibraryReferenceChecker",
    "KnowledgeReferenceChecker",
    "ReferenceCounts",
    "in_use_error",
]
