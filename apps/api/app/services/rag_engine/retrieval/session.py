"""会话级、**身份绑定**的索引快照（P8C-1）。

问题（2026-09-22 profile）：CLI 的 `searcher_provider` 在**每次调用**都做
`load_index`（重新读 48 MB `.npy`）+ 构造 `HybridSearcher`（对整矩阵做 L2 归一化）
+ 首次检索时重建 BM25（对 ~12k chunk 重新分词）。同一进程内逐题问同一个索引，
这些工作被重复了 N 次，是"全库约 20 s / 子库约 2 s"里的主要固定开销。

本模块的做法：
  - **验证一次**：chunks 指纹、索引登记 ids 与 body 顺序逐项一致、矩阵形状/维度、
    模型身份——四项核对（R7 的同一套检查，**单一定义点**在此）通过后，
    得到不可变快照；
  - **按身份缓存**：键 = (chunks 路径解析值, 索引目录解析值, model_ns, dim, tag)
    + 实测 chunks 指纹。指纹变了（切分产物更新）或索引目录换了 → 键变 → 自动重载；
    不允许"跳过校验换速度"；
  - **子库与 BM25 只建一次**：按选择器（学科文件过滤）缓存受限 searcher，并把
    BM25 预热交给调用方显式触发（`warm_bm25=True`），便于把建 BM25 的时间单独计时；
  - **不引入全局服务**：这是进程内只读缓存，注入式使用，不绑定 HTTP、不管理端口；
    `threading.RLock` 保护构建，构建完成后对象只读（可并发读）。

边界（不得含糊）：快照绑定的是**文件指纹**，不是时间；语料/切分/索引变更必须表现为
指纹变化（或显式 `clear_snapshots()`），否则会继续复用旧快照。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.services.rag_engine.contracts import REGION_BODY, Chunk, read_jsonl, sha256_file
from app.services.rag_engine.retrieval.hybrid import HybridSearcher

#: 选择器：None = 全库；否则为"文件名须含全部子串"的元组（学科过滤用）
Selector = tuple[str, ...] | None

#: 并集缓存的键标记（与"子串元组"型选择器不可能混同）
_UNION_KEY = object()


class IndexIdentityError(RuntimeError):
    """索引与当前切分产物身份不符（指纹/行序/形状/注册字段）。

    调用方必须**明确失败**：不自动重建、不回落云端、不静默错绑。
    """


@dataclass
class IndexSnapshot:
    """一次验证通过的不可变索引视图（body 顺序与向量行序严格对齐）。"""

    chunks_path: str
    chunks_fingerprint: str
    model_ns: str
    dim: int
    tag: str
    model_id: str
    body: list[Chunk]
    vectors: np.ndarray                 # 已归一化（HybridSearcher 构造时统一处理）
    ids: list[str]
    meta: dict
    verified_checks: dict = field(default_factory=dict)
    _searchers: dict = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ---- 选器与缓存 ----

    def rows_for(self, selector: Selector) -> list[int]:
        if selector is None:
            return list(range(len(self.body)))
        return [i for i, c in enumerate(self.body)
                if all(sub in c.file for sub in selector)]

    def files_in(self, selector: Selector) -> list[str]:
        return sorted({self.body[i].file for i in self.rows_for(selector)})

    def searcher_for(self, selector: Selector = None, *,
                     warm_bm25: bool = False) -> HybridSearcher:
        """按选择器返回（缓存的）检索器；`warm_bm25` 触发 BM25 构建并计时用。"""
        key = selector
        with self._lock:
            s = self._searchers.get(key)
            if s is None:
                rows = self.rows_for(selector)
                if not rows:
                    raise IndexIdentityError(
                        f"选择器 {selector!r} 在快照内没有任何 body chunk")
                body = [self.body[i] for i in rows]
                # 传入索引侧真实 ids 的子序列（与 rows 同源同序）；构造器仍会核对顺序
                s = HybridSearcher(body, self.vectors[rows],
                                   [self.ids[i] for i in rows], use_cch=True)
                self._searchers[key] = s
        if warm_bm25:
            s.ensure_bm25()
        return s

    def searcher_for_selectors(self, selectors: tuple[Selector, ...], *,
                               warm_bm25: bool = False) -> HybridSearcher:
        """多个选择器的**并集**检索器（产品四科默认范围；行序仍与索引一致）。

        `searcher_for` 的语义是"全部子串都要命中"，无法表达"四科任一"；
        产品入口用本方法把可检索空间限在已声明的学科册内，避免未声明册
        （语文/英语/历史/地理…）被当成"教材原文"发布。空并集**明确失败**，
        不回退全库（沿用 R4：不回退后过滤，制造假漏检）。
        """
        key = (_UNION_KEY, tuple(selectors))
        with self._lock:
            s = self._searchers.get(key)
            if s is None:
                rows = sorted({i for selector in selectors for i in self.rows_for(selector)})
                if not rows:
                    raise IndexIdentityError(
                        f"选择器并集 {selectors!r} 在快照内没有任何 body chunk")
                body = [self.body[i] for i in rows]
                s = HybridSearcher(body, self.vectors[rows],
                                   [self.ids[i] for i in rows], use_cch=True)
                self._searchers[key] = s
        if warm_bm25:
            s.ensure_bm25()
        return s


def load_verified_snapshot(*, chunks_path: str | Path, index_dir: str | Path,
                           model_ns: str, dim: int, tag: str,
                           model_id: str) -> IndexSnapshot:
    """读取 chunks + 索引并做四项身份核对；任一不符抛 `IndexIdentityError`。

    这是 R7 校验的**唯一实现点**（CLI 与性能工具共用）；核对项与错误文案由
    `tests/test_p8a_index_config.py` 锁定，避免"为省指纹开销移除校验"。
    """
    from app.services.rag_engine.indexing.vector_index import load_index

    cp = Path(chunks_path)
    if not cp.exists():
        raise IndexIdentityError(f"chunks 文件不存在：{cp}")
    chunks = [Chunk.from_dict(d) for d in read_jsonl(cp)]
    body_all = [c for c in chunks if c.region == REGION_BODY]
    if not body_all:
        raise IndexIdentityError(f"chunks 中没有 body chunk：{cp}")
    chunks_fp = sha256_file(cp)
    try:
        vectors_full, ids, meta = load_index(
            index_dir, model_ns, dim, tag,
            expect_chunks_fingerprint=chunks_fp, expect_model_id=model_id)
    except (RuntimeError, FileNotFoundError, KeyError) as e:
        raise IndexIdentityError(
            f"索引身份校验失败（不自动重建、不回落云端）：{type(e).__name__}: {e}") from e
    if not meta.get("chunks_fingerprint"):
        raise IndexIdentityError("索引 meta 未登记 chunks_fingerprint——无法核对，拒绝使用")
    expected_ids = [c.chunk_id for c in body_all]
    if list(ids) != expected_ids:
        first = next((i for i, (a, b) in enumerate(zip(ids, expected_ids)) if a != b),
                     min(len(ids), len(expected_ids)))
        raise IndexIdentityError(
            f"索引行序与 chunks.jsonl 的 body 顺序不一致（首个不符位置 {first}："
            f"索引 {list(ids)[first:first + 2]} vs chunks "
            f"{expected_ids[first:first + 2]}）——切分/索引版本不匹配，"
            f"拒绝静默错绑（不自动重建）")
    if vectors_full.ndim != 2 or vectors_full.shape != (len(body_all), dim):
        raise IndexIdentityError(
            f"向量矩阵形状 {vectors_full.shape} != 期望 {(len(body_all), dim)}"
            f"（缺行/多行/维度不符）——拒绝使用")
    return IndexSnapshot(
        chunks_path=str(cp), chunks_fingerprint=chunks_fp, model_ns=model_ns,
        dim=dim, tag=tag, model_id=model_id, body=body_all,
        vectors=vectors_full, ids=list(ids), meta=dict(meta),
        verified_checks={
            "chunks_fingerprint": chunks_fp,
            "index_chunks_fingerprint": meta.get("chunks_fingerprint"),
            "index_model_id": meta.get("model_id"),
            "ids_order_matches_body": True,
            "matrix_shape": list(vectors_full.shape),
            "dim": dim, "tag": tag, "model_ns": model_ns,
        })


_SNAPSHOTS: dict[tuple, IndexSnapshot] = {}
_SNAP_LOCK = threading.RLock()


def snapshot_key(chunks_path: str | Path, index_dir: str | Path, model_ns: str,
                 dim: int, tag: str) -> tuple:
    """快照键 = (chunks 路径, **索引目录**, model_ns, dim, tag)。

    `index_dir` 必须进键（P10 修复批）：过去键里没有它，于是"同一份 chunks + 换一个
    索引目录"会命中旧快照——成对身份核对被缓存悄悄绕过（实测：v3 chunks 配 legacy
    索引时不报错，直接复用先前验过的 v3 快照）。键变了才不会出现这种"核对被跳过"。
    """
    return (str(Path(chunks_path).resolve()), str(Path(index_dir).resolve()),
            model_ns, int(dim), str(tag))


def get_snapshot(*, chunks_path: str | Path, index_dir: str | Path, model_ns: str,
                 dim: int, tag: str, model_id: str) -> IndexSnapshot:
    """进程内按身份缓存的快照。**首次调用做四项核对**，其后复用。

    指纹变化（切分/索引更新）或**索引目录变化** → 本次调用重新验证并替换缓存；
    因此不会出现"语料换了还用旧快照"，也不会出现"换了索引目录却复用旧快照"
    （后者是 P10 修复批实测到的缺陷：键里缺 index_dir）。
    """
    key = snapshot_key(chunks_path, index_dir, model_ns, dim, tag)
    with _SNAP_LOCK:
        cached = _SNAPSHOTS.get(key)
        if cached is not None:
            try:
                fp = sha256_file(chunks_path)
            except OSError:
                fp = None
            if fp is not None and fp == cached.chunks_fingerprint:
                return cached
        snap = load_verified_snapshot(chunks_path=chunks_path, index_dir=index_dir,
                                      model_ns=model_ns, dim=dim, tag=tag,
                                      model_id=model_id)
        _SNAPSHOTS[key] = snap
        return snap


def clear_snapshots() -> int:
    """清空进程内快照（测试与显式失效用）；返回清除数量。"""
    with _SNAP_LOCK:
        n = len(_SNAPSHOTS)
        _SNAPSHOTS.clear()
    return n


def snapshot_stats() -> dict:
    with _SNAP_LOCK:
        return {"n_snapshots": len(_SNAPSHOTS),
                "keys": [[str(k[0]), str(k[1]), k[2], k[3], k[4]]
                         for k in _SNAPSHOTS],
                "searchers_per_snapshot": [len(s._searchers)
                                           for s in _SNAPSHOTS.values()]}
