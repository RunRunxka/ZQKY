"""教材检索服务（R2-BE3）：把 RAG v2 混合检索包装成学习问答的统一入口。

- 每次检索从 ``catalog_state.active_generation_id`` 出发：无活动代 / 代未就绪 /
  代缺少 Embedding 配置 → 409 ``RAG_INDEX_NOT_READY``（不回退、不猜）。
- 允许范围 = 该代内 ``ready`` 修订（``pending`` 尚无向量、``skipped_deleted`` 是已删除
  书册且其封存 blob 可能已清理，都不得进入白名单），再按 ``subject_id`` 过滤；
  过滤后为空返回空列表，绝不放宽成全库。
- ``HybridRetriever`` 文档要求放进有界线程执行；本服务保持同步（供工具经
  ``asyncio.to_thread`` 调用），内部用 ``threading.Lock`` 串行化检索与片段切片——
  retriever 内部有 LRU 词法索引缓存与诊断计数器，保守起见不承诺并发安全。
- 跨线程安全依赖 ``TextbookCatalog`` 每次操作独立开连接的既有约定；本服务不持有连接。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import GenerationRecord
from app.repositories.vector_store.base import VectorStore
from app.services.rag_v2.retrieval import (
    DENSE_LIMIT,
    LEXICAL_LIMIT,
    RRF_K,
    HybridRetriever,
)
from app.services.rag_v2.scope import (
    RevisionScope,
    edition_label as edition_label_of,
    scope_by_revision,
    subject_label as subject_label_of,
)
from app.services.rag_v2.source_text import ImmutableSource, ImmutableTextSource

#: 原文片段展示上限（超出截断并标注）；给模型的上下文按工具层预算再裁一次。
EXCERPT_MAX_CHARS = 400

#: 单次检索返回命中数上限（防止把模型上下文撑爆；工具层可再收紧）。
MAX_LIMIT = 20


def _not_ready(message: str) -> AppError:
    return AppError(message, code="RAG_INDEX_NOT_READY", status_code=409)


@dataclass(frozen=True)
class SearchHit:
    """一次检索命中：几何与身份来自 SQLite 权威，标签来自分类修订与固定字典。"""

    document_revision_id: str
    chunk_set_id: str
    ordinal: int
    region: str
    chapter_path: tuple[str, ...]
    document_title: str
    subject_label: str
    edition_label: str
    grade_ids: tuple[str, ...]
    char_start: int
    char_end: int
    excerpt: str
    fused_score: float
    dense_rank: int | None
    lexical_rank: int | None


class TextbookSearchService:
    """同步教材检索服务：惰性构建并缓存一个 ``HybridRetriever``。"""

    def __init__(
        self,
        catalog: TextbookCatalog,
        vectors: VectorStore,
        embeddings: object,
        *,
        dense_limit: int | None = None,
        lexical_limit: int | None = None,
        rrf_k: int | None = None,
    ) -> None:
        self.catalog = catalog
        self.vectors = vectors
        self.embeddings = embeddings
        self._dense_limit = dense_limit
        self._lexical_limit = lexical_limit
        self._rrf_k = rrf_k
        self._lock = threading.Lock()
        self._retriever: HybridRetriever | None = None

    # ------------------------------------------------------------------ 检索

    def search(
        self,
        query: str,
        *,
        limit: int = 6,
        subject_id: str | None = None,
    ) -> list[SearchHit]:
        """按自然语言问题检索当前索引代内的教材原文；未就绪抛 409，不假成功。"""
        if not isinstance(query, str) or not query.strip():
            raise AppError("检索问题不能为空。", code="INVALID_REQUEST", status_code=422)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise AppError(
                f"limit 必须是 1～{MAX_LIMIT} 的整数。", code="INVALID_REQUEST", status_code=422
            )
        if subject_id is not None and (not isinstance(subject_id, str) or not subject_id.strip()):
            raise AppError("subject_id 必须是非空字符串或 null。", code="INVALID_REQUEST", status_code=422)

        generation = self._active_ready_generation()
        profile = self.catalog.get_embedding_profile(generation.profile_id)
        if profile is None:
            raise _not_ready("教材索引代的 Embedding 配置缺失，教材检索暂不可用。")
        scopes = self._build_scopes(generation, subject_id)
        if not scopes:
            return []

        # 串行化：HybridRetriever 的词法 LRU 缓存与诊断计数器不承诺并发安全；
        # 片段切片复用同一 ImmutableSource 缓存，也一并纳入临界区。
        with self._lock:
            retriever = self._retriever_or_raise()
            candidates = retriever.retrieve(
                question=query.strip(),
                scope=scopes,
                profile=profile,
                generation=generation,
            )
            return self._to_hits(retriever.texts, scopes, candidates)[:limit]

    # -------------------------------------------------------------- 允许范围

    def _active_ready_generation(self) -> GenerationRecord:
        state = self.catalog.catalog_state()
        if not state.active_generation_id:
            raise _not_ready("当前没有已发布的教材索引代，教材检索暂不可用。")
        generation = self.catalog.get_generation(state.active_generation_id)
        if generation is None or generation.state != "ready":
            raise _not_ready("当前教材索引代未就绪，教材检索暂不可用。")
        return generation

    def _build_scopes(
        self, generation: GenerationRecord, subject_id: str | None
    ) -> list[RevisionScope]:
        """该代内 ready 修订 → RevisionScope；已删除书册跳过，不进允许集。"""
        scopes: list[RevisionScope] = []
        for record in self.catalog.list_generation_revisions(generation.generation_id):
            if record.state != "ready":
                continue
            revision = self.catalog.get_revision(record.document_revision_id)
            if revision is None:
                raise AppError(
                    "教材索引代引用的文档修订不存在。",
                    code="REVISION_NOT_FOUND",
                    status_code=404,
                )
            document = self.catalog.get_document(revision.document_id)
            if document is None or document.is_deleted:
                continue
            metadata = self.catalog.get_metadata_revision(document.current_metadata_revision_id)
            if metadata is None or metadata.document_id != document.document_id:
                raise AppError(
                    "教材分类修订缺失或与书册不一致。",
                    code="RAG_SCOPE_CHANGED",
                    status_code=409,
                )
            if subject_id is not None and metadata.subject_id != subject_id:
                continue
            scopes.append(
                RevisionScope(
                    document_id=document.document_id,
                    document_revision_id=revision.revision_id,
                    metadata_revision_id=metadata.metadata_revision_id,
                    chunk_set_id=record.chunk_set_id,
                    owner_id=document.owner_id,
                    title=metadata.title,
                    edition_label=edition_label_of(metadata),
                    subject_label=subject_label_of(metadata.subject_id),
                    grade_ids=tuple(metadata.grade_ids),
                    library_ids=tuple(document.library_ids),
                )
            )
        return scopes

    # ------------------------------------------------------------ 命中映射

    def _to_hits(
        self,
        texts: ImmutableTextSource,
        scopes: list[RevisionScope],
        candidates,
    ) -> list[SearchHit]:
        by_revision = scope_by_revision(scopes)
        hits: list[SearchHit] = []
        for candidate in candidates:
            scope = by_revision.get(candidate.document_revision_id)
            if scope is None:  # pragma: no cover - 融合结果必来自允许范围
                continue
            hits.append(
                SearchHit(
                    document_revision_id=candidate.document_revision_id,
                    chunk_set_id=candidate.chunk_set_id,
                    ordinal=candidate.ordinal,
                    region=candidate.region,
                    chapter_path=tuple(candidate.chapter_path),
                    document_title=scope.title,
                    subject_label=scope.subject_label,
                    edition_label=scope.edition_label,
                    grade_ids=tuple(scope.grade_ids),
                    char_start=candidate.char_start,
                    char_end=candidate.char_end,
                    excerpt=self._excerpt(texts, candidate.document_revision_id, candidate),
                    fused_score=candidate.fused_score,
                    dense_rank=candidate.dense_rank,
                    lexical_rank=candidate.lexical_rank,
                )
            )
        return hits

    def _excerpt(self, texts: ImmutableTextSource, revision_id: str, candidate) -> str:
        revision = self.catalog.get_revision(revision_id)
        if revision is None:  # pragma: no cover - 允许范围构建时已核验存在
            raise AppError("教材修订不存在。", code="REVISION_NOT_FOUND", status_code=404)
        piece = texts.read_normalized_text(revision)[candidate.char_start : candidate.char_end]
        flat = " ".join(piece.split())
        if len(flat) > EXCERPT_MAX_CHARS:
            flat = flat[:EXCERPT_MAX_CHARS] + "…"
        return flat

    # -------------------------------------------------------------- 内部

    def _retriever_or_raise(self) -> HybridRetriever:
        if self._retriever is None:
            kwargs: dict[str, int] = {}
            if self._dense_limit is not None:
                kwargs["dense_limit"] = self._dense_limit
            if self._lexical_limit is not None:
                kwargs["lexical_limit"] = self._lexical_limit
            if self._rrf_k is not None:
                kwargs["rrf_k"] = self._rrf_k
            self._retriever = HybridRetriever(
                self.catalog,
                self.vectors,
                self.embeddings,
                texts=ImmutableSource(catalog=self.catalog),
                **kwargs,
            )
        return self._retriever


__all__ = ["EXCERPT_MAX_CHARS", "MAX_LIMIT", "SearchHit", "TextbookSearchService"]
