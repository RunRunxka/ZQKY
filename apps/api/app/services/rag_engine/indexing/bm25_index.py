"""BM25 词法索引基线（评测体系的最小检索基建；向量路属 Phase 4）。

tokenize / index_text 与 prototype/section_index.py 完全一致——
冻结基线的复现依赖这一点，不得改动分词与过滤行为。
"""
from __future__ import annotations

import re

import numpy as np

from app.services.rag_engine.contracts import Chunk


def tokenize(s: str) -> list[str]:
    import jieba
    return [w for w in jieba.lcut(s)
            if w.strip() and not re.fullmatch(r"[\W_]+", w)]


class BM25Index:
    def __init__(self, chunks: list[Chunk], use_header: bool = True):
        from rank_bm25 import BM25Okapi
        self.chunks = chunks
        fn = (lambda c: c.index_text()) if use_header else (lambda c: c.text)
        self.bm25 = BM25Okapi([tokenize(fn(c)) for c in chunks])

    def search(self, query: str, k: int,
               mask: int | None = None) -> list[tuple[Chunk, float]]:
        """返回前 k 个 (chunk, score)。

        mask 用于数据泄漏防护（ablation）：屏蔽来源 chunk。
        排序与原型一致：np.argsort(scores)[::-1][:k]（并列分时较大索引在前）。
        """
        scores = self.bm25.get_scores(tokenize(query))
        if mask is not None:
            scores[mask] = -1e9
        order = np.argsort(scores)[::-1][:k]
        return [(self.chunks[i], float(scores[i])) for i in order]

    def save(self, path, chunks_fingerprint: str) -> dict:
        import pickle
        meta = {"chunks_fingerprint": chunks_fingerprint,
                "use_header": self.chunks[0].index_text() != self.chunks[0].text
                if self.chunks else True,
                "chunk_count": len(self.chunks)}
        with open(path, "wb") as f:
            pickle.dump({"meta": meta, "chunks": self.chunks, "bm25": self.bm25}, f)
        return meta

    @classmethod
    def load(cls, path, expect_chunks_fingerprint: str | None = None) -> "BM25Index":
        import pickle
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if expect_chunks_fingerprint and \
                obj["meta"]["chunks_fingerprint"] != expect_chunks_fingerprint:
            raise RuntimeError("bm25.pkl 与 chunks.jsonl 版本不一致——请重建索引")
        idx = cls.__new__(cls)
        idx.chunks = obj["chunks"]
        idx.bm25 = obj["bm25"]
        return idx
