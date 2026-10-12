"""已确认原卷读取适配器（TEACHING-LOOP B2 / T40）。

T30-b（施测）与后续批次**只能**通过本适配器读取原卷：它只放行 ``state='confirmed'``
的修订，并在返回前验证业务闸门（``total_score_units > 0`` 且至少一个计分叶子），
否则抛 422 ``ASSESSMENT_PAPER_INVALID``；返回的是**数据库里的真实**标题（B3/G0 ·
B2-RV11：修订级快照 ``paper_revisions.title_snapshot``，不随后续草稿改名而变）、学科与计数，
绝不接受调用方传入的标题/学科/总分快照（B1 视图的 ``ge=0`` 只是形状校验，不能代替
业务闸门）。

读取口径：

- 端口方法名与冻结契约 ``app.contracts.roster.ConfirmedPaperReader`` 一致：
  ``read_confirmed_paper_revision(paper_revision_id) -> ConfirmedPaperRevisionView``
  （返回类型来自契约，不复制第二份）；``read()`` 是它的**等价别名**（同一读法与同一
  闸门，返回字段更全的内部快照 ``ConfirmedPaperSnapshot``）；
- ``read_current(paper_id)``：读该卷当前修订（``papers.current_revision_id``），
  供本模块测试与人工核对；施测端口只需要按修订 id 读取；
- 修订不存在 → 404 ``PAPER_NOT_FOUND``（不区分"卷不存在"与"修订不存在"，避免探测）；
- 未确认 / 总分不大于 0 / 没有计分叶子 / 计分题目却带子题 → 422
  ``ASSESSMENT_PAPER_INVALID``（错误码来自 ``app.contracts.assessments``，不复制定义）；
- 计分叶子 = ``is_scored=1`` 且没有子题的题目；适配器按此口径校验并给出
  ``scored_leaves``，T30-b 的录入模板与逐题单元格都从这里取题号/满分。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import sqlite3

from app.contracts.assessments import ASSESSMENT_PAPER_INVALID
from app.contracts.papers import PAPER_NOT_FOUND
from app.contracts.roster import ConfirmedPaperRevisionView
from app.core.exceptions import AppError
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.teaching.papers import (
    ItemKnowledgeRecord,
    ItemRecord,
    PaperRepository,
    PaperSummary,
)


@dataclass(frozen=True)
class ConfirmedPaperItem:
    """已确认修订里的一道题（含知识关联快照；draft 内容不进本适配器）。"""

    item_id: str
    parent_item_id: str | None
    question_no: str
    ordinal: int
    is_scored: bool
    max_score_units: int | None
    content: dict[str, Any]
    knowledge: tuple[ItemKnowledgeRecord, ...] = ()
    child_count: int = 0

    @property
    def is_leaf(self) -> bool:
        return self.child_count == 0


@dataclass(frozen=True)
class ConfirmedPaperSnapshot:
    """已确认原卷的只读快照：真实标题/学科/计数 + 全部题目（含计分叶子）。"""

    paper_id: str
    paper_revision_id: str
    version: int
    subject_id: str
    title: str
    total_score_units: int
    items: tuple[ConfirmedPaperItem, ...]
    source_practice_revision_id: str | None = None

    @property
    def scored_leaves(self) -> tuple[ConfirmedPaperItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.is_scored and item.is_leaf and item.max_score_units is not None
        )

    @property
    def scored_leaf_count(self) -> int:
        return len(self.scored_leaves)

    @property
    def item_count(self) -> int:
        return len(self.items)


class ConfirmedPaperReaderAdapter:
    """按修订读取已确认原卷的唯一入口；调用方注入已迁移的 ``TeachingCatalog``。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog
        self._papers = PaperRepository(catalog)

    # ------------------------------------------------------------ 公开读取

    def read_confirmed_paper_revision(
        self, paper_revision_id: str
    ) -> ConfirmedPaperRevisionView:
        """冻结端口方法（``app.contracts.roster.ConfirmedPaperReader``）。

        与 ``read()`` **同义**（同一份校验与同一份数据），只是返回端口定义的
        ``ConfirmedPaperRevisionView``：施测（T30-b）只能引用已确认修订，未确认 /
        总分不大于 0 / 没有计分叶子一律 422 ``ASSESSMENT_PAPER_INVALID``。
        """
        snapshot = self.read(paper_revision_id)
        return ConfirmedPaperRevisionView(
            paperId=snapshot.paper_id,
            paperRevisionId=snapshot.paper_revision_id,
            title=snapshot.title,
            subjectId=snapshot.subject_id,
            totalScoreUnits=snapshot.total_score_units,
            scoredLeafCount=snapshot.scored_leaf_count,
        )

    def read(self, paper_revision_id: str) -> ConfirmedPaperSnapshot:
        """按修订 id 读取；未确认或闸门不满足一律失败（不返回半成品）。

        ``read_confirmed_paper_revision()`` 的等价别名：同一读法与同一闸门，
        返回的是字段更全的内部快照（``items``/``scored_leaves`` 等），其
        ``paper_id``/``paper_revision_id``/``title``/``subject_id``/
        ``total_score_units``/``scored_leaf_count`` 与端口视图逐项一致。
        """
        revision_id = _require_text(paper_revision_id, field="paperRevisionId")
        with self._catalog.read_connection() as conn:
            return self.read_in(conn, revision_id)

    def read_in(self, conn: sqlite3.Connection, paper_revision_id: str) -> ConfirmedPaperSnapshot:
        """同教学事务读新确认卷；复用全部确认/计分叶闸门。"""
        revision_id = _require_text(paper_revision_id, field="paperRevisionId")
        revision = self._papers.get_revision_in(conn, revision_id)
        if revision is None:
            raise AppError(f"原卷修订不存在：{revision_id}。", code=PAPER_NOT_FOUND, status_code=404)
        paper = self._papers.get_paper_in(conn, revision.paper_id)
        items = self._papers.list_items_in(conn, revision_id)
        if paper is None:  # pragma: no cover - 外键保证存在
            raise AppError(
                "原卷修订关联的原卷缺失。", code=PAPER_NOT_FOUND, status_code=404
            )
        return self._snapshot(
            paper_id=paper.paper_id,
            subject_id=paper.subject_id,
            # B3/G0 · B2-RV11：标题取**修订级快照**，不读可变 papers.title
            title=revision.title_snapshot,
            revision_id=revision_id,
            version=revision.version,
            state=revision.state,
            total_score_units=revision.total_score_units,
            items=items,
            source_practice_revision_id=revision.source_practice_revision_id,
        )

    def read_current(self, paper_id: str) -> ConfirmedPaperSnapshot:
        """读取该卷**当前**修订；当前修订不是已确认卷时按 422 拒绝。"""
        paper_id = _require_text(paper_id, field="paperId")
        with self._catalog.read_connection() as conn:
            summary: PaperSummary = self._papers.summary_in(conn, paper_id)
            if summary.current_revision_id is None:
                raise AppError(
                    "该原卷还没有修订。", code=PAPER_NOT_FOUND, status_code=404
                )
            revision = self._papers.require_revision_in(conn, summary.current_revision_id)
            items = self._papers.list_items_in(conn, summary.current_revision_id)
        return self._snapshot(
            paper_id=summary.paper_id,
            subject_id=summary.subject_id,
            title=revision.title_snapshot,
            revision_id=summary.current_revision_id,
            version=summary.version,
            state=summary.current_state or "draft",
            total_score_units=summary.total_score_units,
            items=items,
            source_practice_revision_id=revision.source_practice_revision_id,
        )

    # ------------------------------------------------------------ 内部

    def _snapshot(
        self,
        *,
        paper_id: str,
        subject_id: str,
        title: str,
        revision_id: str,
        version: int,
        state: str,
        total_score_units: int,
        items: list[ItemRecord],
        source_practice_revision_id: str | None = None,
    ) -> ConfirmedPaperSnapshot:
        if state != "confirmed":
            raise _paper_invalid(
                "只允许使用已确认的原卷修订；当前修订仍是草稿，请先完成确认。"
            )
        if total_score_units <= 0:
            raise _paper_invalid("已确认原卷的总分必须大于 0。")
        child_counts: dict[str, int] = {}
        for item in items:
            if item.parent_item_id is not None:
                child_counts[item.parent_item_id] = (
                    child_counts.get(item.parent_item_id, 0) + 1
                )
        snapshot_items = tuple(
            ConfirmedPaperItem(
                item_id=item.item_id,
                parent_item_id=item.parent_item_id,
                question_no=item.question_no,
                ordinal=item.ordinal,
                is_scored=item.is_scored,
                max_score_units=item.max_score_units,
                content=dict(item.content),
                knowledge=tuple(item.knowledge),
                child_count=child_counts.get(item.item_id, 0),
            )
            for item in items
        )
        scored_leaf_count = sum(
            1
            for item in snapshot_items
            if item.is_scored and item.is_leaf and item.max_score_units is not None
        )
        if scored_leaf_count < 1:
            raise _paper_invalid("已确认原卷必须至少有一个计分叶子（小题）。")
        return ConfirmedPaperSnapshot(
            paper_id=paper_id,
            paper_revision_id=revision_id,
            version=version,
            subject_id=subject_id,
            title=title,
            total_score_units=total_score_units,
            items=snapshot_items,
            source_practice_revision_id=source_practice_revision_id,
        )


def _paper_invalid(message: str) -> AppError:
    return AppError(message, code=ASSESSMENT_PAPER_INVALID, status_code=422)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"{field} 必须是非空字符串。", code="INVALID_REQUEST", status_code=422
        )
    return value.strip()


__all__ = [
    "ConfirmedPaperItem",
    "ConfirmedPaperReaderAdapter",
    "ConfirmedPaperSnapshot",
]
