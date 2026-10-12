"""混合检索：范围预过滤的稠密（Qdrant）+ 词法（SQLite BM25）+ RRF 融合。

对应 docs/PLAN.md §6.4：

1. 查询向量与教材向量必须同一 Embedding 配置指纹（``generation.profile_id`` 对应的
   ``ProfileRecord``），前缀取自该配置，``truncate=False`` 由 provider 保证。
   **查询前与算完向量后各核一次清单 digest**：本机实际 digest 必须等于登记 digest，
   否则 409 ``EMBEDDING_MODEL_CHANGED`` 并停止检索（同名 tag 换了权重时不得继续用错误向量空间）；
   名字与 digest 归一一律复用 B1 provider 的 ``manifest_digest``（tag 语义在 provider 内）。
2. 稠密检索把允许集合（修订 / 分块集 / 归属 / 正文区）作为 Qdrant filter **下推**，
   绝不"从全库取结果再过滤"。
3. BM25 只从 ``catalog.list_chunks`` 读允许范围内的块（正文区），用 ``rank_bm25``
   建内存索引；**文档文本用该索引代登记的清洗版本投影后的索引输入文本**（历史代
   ``raw-v0`` 为恒等投影，新旧代绝不混用词法文本）。缓存键含索引代 + 排序后的
   修订/分块集集合 + **清洗版本** + 分词版本，容量有界。
   词法命中判定用"与查询有词元交集"，不按分数正负判定（小语料上 IDF 可能为负，
   负分块仍是真命中）；块文本按块指纹核验后才进入索引（核验的是**原文切片**）。
4. RRF：``score = Σ 1/(k + rank)``，``k=60``，rank 从 1 起；并列时按稳定块身份
   （``chunk_set_id`` + ``ordinal``）排序，保证同输入同顺序。

查询向量不需要投影（用户问题是原文），查询前缀与身份核验逻辑保持不变
（含 ``EMBEDDING_MODEL_CHANGED``）。

不使用 pickle/.npy 作为正式索引存储，不加载用户上传的索引文件。
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import ChunkRecord, GenerationRecord, ProfileRecord
from app.repositories.vector_store.base import (
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_ORDINAL,
    VectorStore,
)
from app.services.document_parsing.chunking import chunk_projection
from app.services.rag_v2.scope import BODY_REGION, RevisionScope, allowed_filter
from app.services.rag_v2.source_text import ImmutableSource, ImmutableTextSource
from app.services.textbook_ingest.blobs import sha256_text
from app.services.textbook_ingest.generation_doc import generation_policy

DENSE_LIMIT = 50
LEXICAL_LIMIT = 50
RRF_K = 60
#: 分词版本：进入 BM25 缓存键；改动分词必须改版本，避免复用旧索引。
TOKENIZER_VERSION = "zqky-ragv2-lexical-v1"
LEXICAL_CACHE_ENTRIES = 4


@dataclass(frozen=True)
class Candidate:
    """融合后的候选块：几何信息来自 SQLite 权威块表，不信任向量 payload 的坐标。"""

    chunk_set_id: str
    ordinal: int
    char_start: int
    char_end: int
    region: str
    chapter_path: tuple[str, ...]
    dense_rank: int | None
    lexical_rank: int | None
    fused_score: float
    document_revision_id: str

    @property
    def identity(self) -> tuple[str, int]:
        return (self.chunk_set_id, self.ordinal)


@dataclass(frozen=True)
class _LexicalEntry:
    chunk_set_id: str
    ordinal: int
    document_revision_id: str
    text: str
    tokens: frozenset[str]


class _LexicalIndex:
    """一个允许集合内的 BM25 索引：条目顺序固定（分块集 id、ordinal 升序）。

    ``entries`` 只含**可被命中**的块（分词非空的块）：分词为空的块（纯符号、纯公式）与任何
    查询都不可能有词元交集，且全空语料会让 ``BM25Okapi`` 构造期除零崩溃。过滤后
    ``bm25`` 语料与 ``entries`` 按同一顺序一一对应，不会错位。
    """

    def __init__(self, entries: list[_LexicalEntry], bm25) -> None:
        self.entries = entries
        self.bm25 = bm25


def tokenize(text: str) -> list[str]:
    """与既有词法基线一致：jieba 精确分词并丢弃纯符号/空白。"""
    import jieba

    return [
        word
        for word in jieba.lcut(text)
        if word.strip() and not re.fullmatch(r"[\W_]+", word)
    ]


class HybridRetriever:
    """同步检索器：由调用方放进有界线程执行（FastAPI 线程池 / anyio.to_thread）。"""

    def __init__(
        self,
        catalog: TextbookCatalog,
        vectors: VectorStore,
        embeddings: object,
        *,
        texts: ImmutableTextSource | None = None,
        dense_limit: int = DENSE_LIMIT,
        lexical_limit: int = LEXICAL_LIMIT,
        rrf_k: int = RRF_K,
        cache_entries: int = LEXICAL_CACHE_ENTRIES,
    ) -> None:
        self.catalog = catalog
        self.vectors = vectors
        self.embeddings = embeddings
        self.texts = texts if texts is not None else ImmutableSource(catalog=catalog)
        self.dense_limit = int(dense_limit)
        self.lexical_limit = int(lexical_limit)
        self.rrf_k = int(rrf_k)
        self.cache_entries = max(1, int(cache_entries))
        self._cache: OrderedDict[tuple, _LexicalIndex] = OrderedDict()
        #: 诊断计数：Qdrant 返回了白名单内但 SQLite 块表不存在的陈旧 point
        self.inconsistent_hits = 0
        self.cache_hits = 0
        self.cache_misses = 0

    # ------------------------------------------------------------------ 状态

    def status(self) -> dict:
        return {
            "available": self.vectors is not None and self.embeddings is not None,
            "denseLimit": self.dense_limit,
            "lexicalLimit": self.lexical_limit,
            "rrfK": self.rrf_k,
            "tokenizerVersion": TOKENIZER_VERSION,
            "lexicalCacheEntries": self.cache_entries,
        }

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------ 检索

    def retrieve(
        self,
        *,
        question: str,
        scope: Sequence[RevisionScope],
        profile: ProfileRecord,
        generation: GenerationRecord,
    ) -> list[Candidate]:
        """按给定允许范围检索并融合；空范围返回空列表（不回退全库）。"""
        if not scope:
            return []
        allowed = allowed_filter(scope)
        chunk_maps = self._chunk_maps(scope)
        revision_by_chunk_set = {item.chunk_set_id: item.document_revision_id for item in scope}
        query_vector = self._embed_query(profile, question)
        dense = self._dense(generation, query_vector, allowed, chunk_maps)
        lexical = self._lexical(generation, scope, question)
        return self._fuse(dense, lexical, chunk_maps, revision_by_chunk_set)

    # ------------------------------------------------------------ 查询向量

    def _verify_model_identity(self, profile: ProfileRecord) -> str:
        """核验查询向量空间的身份：本机实际 digest 必须等于该配置登记的 digest。

        - 名字与 digest 归一复用 B1 provider 的 ``manifest_digest``（tag 归一在 provider 内完成，
          本模块不另写名字比较）。
        - 不一致、模型不在本机、或适配器没有清单核对能力 → 409 ``EMBEDDING_MODEL_CHANGED``：
          不能证明身份就不得检索（绝不静默使用可能错误的向量空间）。
        - 服务本身不可达（``EMBEDDING_UNAVAILABLE`` 等）原样抛出：那是"服务不可用"，
          与"同名换了权重"是两类失败，错误码必须可区分。
        """
        embeddings = self.embeddings
        reader = getattr(embeddings, "manifest_digest", None)
        if not callable(reader):
            raise AppError(
                "Embedding 适配器不提供清单核对能力，无法确认查询向量空间，已停止检索。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        try:
            installed = reader(profile.model_name)
        except AppError as exc:
            if exc.code == "EMBEDDING_MODEL_MISSING":
                raise AppError(
                    f"登记模型 {profile.model_name} 不在本机（{exc}），无法确认查询向量空间，已停止检索。",
                    code="EMBEDDING_MODEL_CHANGED",
                    status_code=409,
                ) from exc
            raise
        if installed != profile.model_manifest_digest:
            raise AppError(
                f"Embedding 模型 {profile.model_name} 的清单与登记不一致"
                f"（本机 {installed[:12]}…，登记 {profile.model_manifest_digest[:12]}…），已停止检索。",
                code="EMBEDDING_MODEL_CHANGED",
                status_code=409,
            )
        return installed

    def _embed_query(self, profile: ProfileRecord, question: str) -> list[float]:
        if self.embeddings is None:
            raise AppError(
                "本地 Embedding 适配器未装配，无法检索教材。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        # ① 先核身份再算向量：身份不符时一次嵌入调用都不发生
        self._verify_model_identity(profile)
        prefix = profile.query_prefix or ""
        vectors = self.embeddings.embed(model=profile.model_name, texts=[prefix + question])
        if not isinstance(vectors, list) or len(vectors) != 1:
            raise AppError(
                "Embedding 返回条数与查询输入不一致，已停止检索。",
                code="EMBEDDING_INVALID_OUTPUT",
                status_code=502,
            )
        vector = vectors[0]
        if not isinstance(vector, list) or not vector:
            raise AppError(
                "Embedding 查询向量为空，已停止检索。",
                code="EMBEDDING_INVALID_OUTPUT",
                status_code=502,
            )
        if len(vector) != profile.dimensions:
            raise AppError(
                f"查询向量维度 {len(vector)} 与配置 {profile.dimensions} 不一致，已停止检索。",
                code="EMBEDDING_DIMENSION_MISMATCH",
                status_code=409,
            )
        # ② 算完再核一次：嵌入调用期间模型被换（同名 tag 换权重）→ 丢弃该向量，不得用于检索
        self._verify_model_identity(profile)
        return [float(value) for value in vector]

    # ---------------------------------------------------------------- 稠密

    def _dense(
        self,
        generation: GenerationRecord,
        query_vector: list[float],
        allowed,
        chunk_maps: dict[str, dict[int, ChunkRecord]],
    ) -> list[tuple[str, int]]:
        if self.vectors is None:
            raise AppError(
                "向量库未装配，无法检索教材。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        hits = self.vectors.search(
            name=generation.collection_name,
            vector=query_vector,
            limit=self.dense_limit,
            allowed=allowed,
        )
        ordered: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for hit in hits:
            payload = hit.payload if isinstance(hit.payload, dict) else {}
            chunk_set_id = payload.get(PAYLOAD_CHUNK_SET_ID)
            ordinal = payload.get(PAYLOAD_ORDINAL)
            if not isinstance(chunk_set_id, str) or isinstance(ordinal, bool) or not isinstance(ordinal, int):
                raise AppError(
                    "向量库返回的 point 缺少教材块身份，已停止检索。",
                    code="QDRANT_INVALID_RESPONSE",
                    status_code=502,
                )
            # 零/负相似度不构成命中：既不冒充相关，也不伪造 RRF 名次
            if float(hit.score) <= 0.0:
                continue
            if ordinal not in chunk_maps.get(chunk_set_id, {}):
                # 白名单内却不在封存块表：陈旧 point，记诊断并跳过，不参与融合
                self.inconsistent_hits += 1
                continue
            identity = (chunk_set_id, ordinal)
            if identity in seen:
                continue
            seen.add(identity)
            ordered.append(identity)
        return ordered

    # ---------------------------------------------------------------- 词法

    def _lexical(
        self,
        generation: GenerationRecord,
        scope: Sequence[RevisionScope],
        question: str,
    ) -> list[tuple[str, int]]:
        if self.lexical_limit <= 0:
            return []
        index = self._lexical_index(generation, scope)
        if not index.entries or index.bm25 is None:
            # 该范围内没有可被词法命中的块（含"全部块分词为空"）：词法侧为空，
            # 不构造 BM25，也不把整个检索判定为不可用；稠密与 RRF 照常进行。
            return []
        query_tokens = set(tokenize(question))
        if not query_tokens:
            return []
        scores = index.bm25.get_scores(tokenize(question))
        # 命中判定用"与查询有词元交集"，不用分数正负：BM25 的 IDF 在小语料上可能为负，
        # 但负分块仍然是真的词法命中，不能因此丢掉或伪造名次。
        rows = [
            (entry, float(score))
            for entry, score in zip(index.entries, scores)
            if entry.tokens & query_tokens
        ]
        rows.sort(key=lambda row: (-row[1], row[0].chunk_set_id, row[0].ordinal))
        return [(entry.chunk_set_id, entry.ordinal) for entry, _score in rows[: self.lexical_limit]]

    def _lexical_index(self, generation: GenerationRecord, scope: Sequence[RevisionScope]) -> _LexicalIndex:
        policy = generation_policy(generation)
        projection_version = policy.text_projection_version
        key = (
            generation.generation_id,
            tuple(sorted(item.document_revision_id for item in scope)),
            tuple(sorted(item.chunk_set_id for item in scope)),
            projection_version,
            TOKENIZER_VERSION,
        )
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            self._cache.move_to_end(key)
            return cached
        self.cache_misses += 1
        entries: list[_LexicalEntry] = []
        for item in sorted(scope, key=lambda entry: entry.chunk_set_id):
            revision = self.catalog.get_revision(item.document_revision_id)
            if revision is None:
                raise AppError(
                    "教材修订不存在，无法构建词法索引。",
                    code="REVISION_NOT_FOUND",
                    status_code=404,
                )
            text = self.texts.read_normalized_text(revision)
            for chunk in self.catalog.list_chunks(item.chunk_set_id):
                if chunk.region != BODY_REGION:
                    continue
                piece = text[chunk.char_start:chunk.char_end]
                if sha256_text(piece) != chunk.text_sha256:
                    raise AppError(
                        "分块文本与块指纹不一致，已停止使用该教材块。",
                        code="RAG_EVIDENCE_UNAVAILABLE",
                        status_code=409,
                    )
                # 词法文本与向量输入同一口径：按该代登记的清洗版本投影（旧代 raw-v0 恒等）
                index_text = chunk_projection(chunk, text, policy).text
                entries.append(
                    _LexicalEntry(
                        chunk_set_id=chunk.chunk_set_id,
                        ordinal=chunk.ordinal,
                        document_revision_id=item.document_revision_id,
                        text=index_text,
                        tokens=frozenset(tokenize(index_text)),
                    )
                )
        from rank_bm25 import BM25Okapi

        # BM25 语料只收分词非空的块：空词元块永远不可能与查询有词元交集（不可能成为命中），
        # 但会让 BM25Okapi 在全空语料上构造期除零崩溃（合法语料的崩溃，不是坏数据）。
        # 过滤后按同一顺序重建语料与 entries，保证 get_scores 的序号与条目一一对应。
        indexable = [entry for entry in entries if entry.tokens]
        bm25 = BM25Okapi([tokenize(entry.text) for entry in indexable]) if indexable else None
        index = _LexicalIndex(entries=indexable, bm25=bm25)
        self._cache[key] = index
        while len(self._cache) > self.cache_entries:
            self._cache.popitem(last=False)
        return index

    def _chunk_maps(self, scope: Sequence[RevisionScope]) -> dict[str, dict[int, ChunkRecord]]:
        maps: dict[str, dict[int, ChunkRecord]] = {}
        for item in scope:
            maps[item.chunk_set_id] = {
                chunk.ordinal: chunk for chunk in self.catalog.list_chunks(item.chunk_set_id)
            }
        return maps

    # ----------------------------------------------------------------- RRF

    def _fuse(
        self,
        dense: Sequence[tuple[str, int]],
        lexical: Sequence[tuple[str, int]],
        chunk_maps: dict[str, dict[int, ChunkRecord]],
        revision_by_chunk_set: dict[str, str],
    ) -> list[Candidate]:
        fused: dict[tuple[str, int], float] = {}
        dense_ranks: dict[tuple[str, int], int] = {}
        lexical_ranks: dict[tuple[str, int], int] = {}
        for rank, identity in enumerate(dense, start=1):
            dense_ranks[identity] = rank
            fused[identity] = fused.get(identity, 0.0) + 1.0 / (self.rrf_k + rank)
        for rank, identity in enumerate(lexical, start=1):
            lexical_ranks[identity] = rank
            fused[identity] = fused.get(identity, 0.0) + 1.0 / (self.rrf_k + rank)
        order = sorted(fused, key=lambda identity: (-fused[identity], identity[0], identity[1]))
        candidates: list[Candidate] = []
        for identity in order:
            chunk = chunk_maps.get(identity[0], {}).get(identity[1])
            if chunk is None:
                continue
            candidates.append(
                Candidate(
                    chunk_set_id=identity[0],
                    ordinal=identity[1],
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    region=chunk.region,
                    chapter_path=tuple(chunk.chapter_path),
                    dense_rank=dense_ranks.get(identity),
                    lexical_rank=lexical_ranks.get(identity),
                    fused_score=fused[identity],
                    document_revision_id=revision_by_chunk_set.get(identity[0], ""),
                )
            )
        return candidates


__all__ = [
    "Candidate",
    "DENSE_LIMIT",
    "HybridRetriever",
    "LEXICAL_LIMIT",
    "RRF_K",
    "TOKENIZER_VERSION",
    "tokenize",
]
