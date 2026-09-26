"""混合检索：BM25 词法路 + 向量语义路 → 融合（RRF / 加权归一化）。

口径与防线（docs/EVAL.md v1）：
  - 检索目标仅 region=="body" 的 chunk（由调用方传入的 body 列表保证）
  - 候选池：BM25 top-pool ∪ 向量 top-pool，融合后取最终 top-k
  - rerank 不在本层（Phase 5）
"""
from __future__ import annotations

import numpy as np

from app.services.rag_engine.contracts import Chunk
from app.services.rag_engine.indexing.bm25_index import BM25Index

METHODS = ("bm25", "vector", "hybrid_rrf", "hybrid_weighted")


class EmptyScope(ValueError):
    """限定范围内没有可检索 chunk（file/book 约束与当前索引不匹配）。

    由 `HybridSearcher.restrict` 抛出；调用方必须**明确失败**，不得回退全库检索后
    再在结果侧过滤——那会制造假漏检（2026-09-21 审查 R4）。
    """


def l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def cosine_topk(qv: np.ndarray, vectors: np.ndarray, k: int) -> list[tuple[int, float]]:
    """qv: (dim,) 已归一化；vectors: (n, dim) 已归一化。返回 [(行号, 余弦相似度)]。"""
    sims = vectors @ qv
    order = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in order]


def _rrf_score(ranks_per_list: list[dict[int, int]], rrf_k: float) -> dict[int, float]:
    fused: dict[int, float] = {}
    for ranks in ranks_per_list:
        for idx, rank in ranks.items():          # rank 从 1 开始
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank)
    return fused


def _minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-12:
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def fuse(bm25_hits: list[tuple[int, float]], vec_hits: list[tuple[int, float]],
         method: str, rrf_k: float = 60.0, alpha: float = 0.5) -> list[tuple[int, float]]:
    """融合两路候选（元素为 (行号, 原始分)），返回按融合分降序的 [(行号, 融合分)]。

    并列分按 (bm25 名次, 向量名次, 行号) 稳定排序，保证确定性。
    """
    if method == "hybrid_rrf":
        bm25_ranks = {idx: r for r, (idx, _s) in enumerate(bm25_hits, 1)}
        vec_ranks = {idx: r for r, (idx, _s) in enumerate(vec_hits, 1)}
        fused = _rrf_score([bm25_ranks, vec_ranks], rrf_k)
        order = sorted(fused, key=lambda i: (-fused[i],
                                             bm25_ranks.get(i, 10**9),
                                             vec_ranks.get(i, 10**9), i))
        return [(i, fused[i]) for i in order]
    if method == "hybrid_weighted":
        bm25_ranks = {idx: r for r, (idx, _s) in enumerate(bm25_hits, 1)}
        vec_ranks = {idx: r for r, (idx, _s) in enumerate(vec_hits, 1)}
        bn = dict(zip((i for i, _ in bm25_hits), _minmax([s for _, s in bm25_hits])))
        vn = dict(zip((i for i, _ in vec_hits), _minmax([s for _, s in vec_hits])))
        union = set(bm25_ranks) | set(vec_ranks)
        fused = {i: alpha * bn.get(i, 0.0) + (1.0 - alpha) * vn.get(i, 0.0)
                 for i in union}
        order = sorted(union, key=lambda i: (-fused[i],
                                             bm25_ranks.get(i, 10**9),
                                             vec_ranks.get(i, 10**9), i))
        return [(i, fused[i]) for i in order]
    raise ValueError(f"未知融合方法: {method}")


class HybridSearcher:
    """一个学科组的检索器：body chunks + BM25 + 向量矩阵（三者行序严格对齐）。"""

    def __init__(self, body: list[Chunk], vectors: np.ndarray,
                 index_chunk_ids: list[str], use_cch: bool = True,
                 *, _normalized: bool = False):
        if index_chunk_ids != [c.chunk_id for c in body]:
            raise RuntimeError("向量索引与 body chunk 顺序不一致——索引与切分产物版本不匹配")
        if vectors.shape[0] != len(body):
            raise RuntimeError(
                f"向量行数 {vectors.shape[0]} != body 条数 {len(body)}——索引与切分产物不匹配")
        self.body = body
        arr = vectors.astype(np.float32)
        #: 已归一化的余弦矩阵；`_normalized=True` 供 restrict() 复用（避免二次归一化的舍入）
        self.vectors = arr if _normalized else l2_normalize(arr)
        self.use_cch = use_cch
        self._pos = {(c.file, c.chunk_id): i for i, c in enumerate(body)}
        self._bm25: BM25Index | None = None

    def restrict(self, predicate) -> "HybridSearcher":
        """按谓词限定范围，返回新的检索器（R4：先限定范围再排序）。

        `body / vectors / index_chunk_ids` 三者用**同一行号列表**同步切片，构造函数
        的顺序守卫照常生效——因此不可能出现"向量绑定到别的正文"。范围内无 chunk
        时抛 `EmptyScope`（明确失败，不返回空检索器让调用方误以为还能搜）。
        """
        rows = [i for i, c in enumerate(self.body) if predicate(c)]
        if not rows:
            raise EmptyScope("限定范围内没有 body chunk（约束与当前索引不匹配）")
        return HybridSearcher([self.body[i] for i in rows],
                              self.vectors[rows],
                              [self.body[i].chunk_id for i in rows],
                              self.use_cch, _normalized=True)

    def ensure_bm25(self) -> BM25Index:
        if self._bm25 is None:
            self._bm25 = BM25Index(self.body, use_header=self.use_cch)
        return self._bm25

    def search(self, query: str, qv: np.ndarray | None, method: str,
               k: int = 50, pool: int = 50,
               rrf_k: float = 60.0, alpha: float = 0.5) -> list[tuple[Chunk, float]]:
        if method == "bm25":
            return self.ensure_bm25().search(query, k)
        if method == "vector":
            if qv is None:
                raise ValueError("vector 方法需要查询向量")
            hits = cosine_topk(qv.astype(np.float32), self.vectors, k)
            return [(self.body[i], s) for i, s in hits]
        if method in ("hybrid_rrf", "hybrid_weighted"):
            if qv is None:
                raise ValueError(f"{method} 需要查询向量")
            bm25_hits = self.ensure_bm25().search(query, pool)
            bm25_idx = [(self._pos[(c.file, c.chunk_id)], s) for c, s in bm25_hits]
            vec = cosine_topk(qv.astype(np.float32), self.vectors, pool)
            fused = fuse(bm25_idx, vec, method, rrf_k=rrf_k, alpha=alpha)[:k]
            return [(self.body[i], s) for i, s in fused]
        raise ValueError(f"未知方法: {method}")

    def search_scored(self, query: str, qv: np.ndarray | None, method: str,
                      k: int = 50, pool: int = 50, rrf_k: float = 60.0,
                      alpha: float = 0.5) -> list[tuple[Chunk, float, int]]:
        """带分与名次的检索结果——产品证据层/单题入口用，**不改变** search() 的行为。

        返回 [(chunk, score, rank)]，rank 为 1-based：
          - bm25：score = BM25 分
          - vector：score = 余弦相似度（已归一化向量的内积）
          - hybrid_rrf / hybrid_weighted：score = 融合分（各段分**不可比**，只用于该次排序）
        与 search() 用同一套 fuse/cosine_topk/BM25，保证两条路径排序一致（有测试对拍）。
        """
        scored = self.search(query, qv, method, k=k, pool=pool, rrf_k=rrf_k, alpha=alpha)
        return [(c, float(s), i) for i, (c, s) in enumerate(scored, 1)]
