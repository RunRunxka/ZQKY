"""知识点列表的教材范围解析（任务②·scope=taught / gradeId 的唯一真实实现）。

``scope=taught`` 的"任教范围内有教材依据"语义：

- 任教范围真值 = 教材库 ``teaching_settings`` 经 ``TextbookCatalog.resolve_selection``
  解析（与 ``services.rag_v2.scope`` 同一权威）；未保存/未就绪 → 409 带可读原因，
  **绝不**静默回退成"全部知识点"；
- 解析出的 document_ids → 这些教材的**当前**修订集合（任教范围按当前修订生效，
  与 RAG 检索范围同一口径）→ 知识点命中 = 该点任一 ``textbook_knowledge_links``
  的 ``document_revision_id`` 落在该集合；
- ``gradeId`` 过滤落在知识点侧：命中的教材依据文档的年级集合里包含该年级才保留；
  视图 ``gradeIds`` = 该点教材依据文档的年级去重并集（分页批量取，不做 N+1）。

端口（``TextbookScopeReader`` Protocol）由 ``main.py`` 知识点运行时装配段注入；
端口缺失时带 ``scope=taught`` 的调用 503，**不带 scope 的旧调用不受影响**。
本模块只读：不写任何库，不在事务里做网络/解析。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.exceptions import AppError
from app.schemas.textbook import TextbookSelection


@dataclass(frozen=True)
class TextbookScopeSnapshot:
    """一次解析成功的任教范围：documentId → documentRevisionId / grade_ids。"""

    document_ids: tuple[str, ...]
    revision_ids: tuple[str, ...]
    grade_ids_by_document: dict[str, tuple[str, ...]]

    @property
    def revision_set(self) -> frozenset[str]:
        return frozenset(self.revision_ids)


class TextbookScopeReader(Protocol):
    """教材范围查询端口（服务层只依赖本形状；装配缺失时带 scope 的调用 503）。"""

    def resolve_taught_scope(self) -> TextbookScopeSnapshot:
        """解析当前任教范围；未保存/未就绪抛 409（带原因），不回退全部。"""
        ...

    def grade_ids_of_revisions(self, revision_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        """按教材修订 id 批量读年级集合（该修订所属文档当前元数据的年级）。"""
        ...


class CatalogTextbookScopeReader:
    """教材范围查询真实实现：教材目录 +任教设置（``teaching_settings``）。"""

    def __init__(self, catalog: Any) -> None:
        self._catalog = catalog

    def resolve_taught_scope(self) -> TextbookScopeSnapshot:
        """任教设置 → ``resolve_selection`` 逐条核验；任一不满足 409 带原因。"""
        record = self._catalog.get_teaching_settings()
        raw = record.selection
        if raw is None:
            raise _scope_unavailable("尚未保存任教范围，无法按任教范围筛选知识点。")
        try:
            selection = TextbookSelection.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 - 损坏设置不伪装成可用范围
            raise _scope_unavailable("任教范围设置已损坏，请重新保存任教范围。") from exc
        try:
            resolved = self._catalog.resolve_selection(selection)
        except AppError as exc:
            # B0 的范围核验错误原样透出（409，含 INDEX_NOT_READY/RAG_SCOPE_CHANGED 与原因），
            # 绝不静默回退成"全部知识点"。
            raise _scope_unavailable(f"任教范围当前不可用：{exc}") from exc
        grade_ids_by_document = {item.document_id: tuple(item.grade_ids) for item in resolved}
        return TextbookScopeSnapshot(
            document_ids=tuple(item.document_id for item in resolved),
            revision_ids=tuple(item.document_revision_id for item in resolved),
            grade_ids_by_document=grade_ids_by_document,
        )

    def grade_ids_of_revisions(self, revision_ids: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
        """按修订 id 批量读年级：修订 → document → 当前元数据 → grade_ids。

        未知/已删除的修订不进结果表（调用方按"无年级依据"处理，不伪造年级）。
        """
        result: dict[str, tuple[str, ...]] = {}
        for revision_id in revision_ids:
            revision = self._catalog.get_revision(revision_id)
            if revision is None:
                continue
            try:
                metadata = self._catalog.current_metadata_revision(revision.document_id)
            except AppError:
                continue
            result[revision_id] = tuple(metadata.grade_ids)
        return result


def _scope_unavailable(message: str) -> AppError:
    from app.contracts.knowledge import KNOWLEDGE_SCOPE_UNAVAILABLE

    return AppError(message, code=KNOWLEDGE_SCOPE_UNAVAILABLE, status_code=409)


__all__ = [
    "CatalogTextbookScopeReader",
    "TextbookScopeReader",
    "TextbookScopeSnapshot",
]
