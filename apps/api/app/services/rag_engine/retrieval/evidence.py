"""P6 证据层：原文区间重建（evidence reconstruction）。

输入 = 检索种子（`HybridSearcher.search_scored()` 的输出 `[(Chunk, score, rank)]`，
rank 1-based 融合序）与源文本缓存（`SourceCache` / `{file: SourceFile}`，可注入），
输出 = 校验过的 `list[EvidenceSpan]`。契约单一定义点 `src/contracts.py`（SCHEMA §九），
本模块只消费、不重复定义。

三种方法（`method` 与 `expansions` 如实记录；`selection_score/score_kind` 直接来自种子，
不做跨来源比较、不设绝对阈值）：
  - `single_chunk`    种子各自成段（基线，`char_span=[c.start, c.end)`，不受预算影响）；
  - `bounded_window`  以最强种子（rank=1）为中心，向同 file、同节（path[:2] 全等）的
                      左右邻块扩展至字符预算（默认 max_chars=1200），产出**一个** span；
  - `rse`             取融合序前 n_seeds 个种子（按 (file, path[:2]) 去重），重建各种子
                      所在的**安全连续区间**（节内相邻 body 块 + 纯空白 gap 可并入），
                      超预算按块粒度拆分为多个 span（单块仍超预算则按字符拆分）。

合并/扩展硬规则（全部按**原文字符位置**判定，绝不信任 chunk_id 连号）：
  1. 只在同 file 内扩展；不跨节（分组键 = file + path[:2] 全等）；
  2. 相邻判定：`next.start == prev.end`（紧邻）或 gap 内只有空白
     （`source_text[prev.end:next.start].strip() == ""`）才可并入；gap 内有任何非空白 →
     不合并，拆成两个 span；习题区（region=="exercise"）块不参与并入——它若落在两个
     body 块之间，其文本构成非空白 gap，同样断链；目录区/被丢弃的短块同理（空洞文本
     非空白 → 断链），因此「ID 连号但字符不连续」不可能被误合并；
  3. 种子之间的**全部**相邻对逐对检查（不只是两端）：任一对不同节/习题区/非空白 gap →
     该处断链；
  4. 同一结果内重叠区间确定性去重（同 file 内按 start 排序、左闭右开、并列按 chunk_id；
     重叠时保留覆盖 chunk 更多/更长的一方）；**跨文件绝不合并**；
  5. 字符预算：预算不足时按块（必要时按字符）拆分并**重算坐标**——每个产出 span 的
     `text` 都是 `source_text[start:end]` 直接切片，绝不静默截断文本却沿用旧坐标；
     `expansions` 记录合并的 chunk_id、种子 id、跳过的 gap（长度+原因）、是否因预算拆分、
     因预算排除的同节块。
  6. **切分坐标 vs 当前语料**（P8A 加固）：每个并入单元的 `Chunk.text` 必须与当前
     源文件的 `source_text[start:end)` 逐字符一致，否则抛 `EvidenceError`。仅靠
     `validate_evidence` 无法发现"坐标整体陈旧"——从新文件切片再自证切片正确是同义
     反复；以 chunk 记录的正文为对照才能发现语料与切分产物版本不一致。

邻块来源：`reconstruct(all_chunks=...)` 由调用方给出；`evidence_from_question()`
缺省取 `searcher.body`（该检索器受约束的正文集合），因此学科/书册/文件范围同时
约束检索、邻块扩展与结果复核（P8A / R1：过去服务层没传，`bounded_window`
实际退化成单 chunk）。

`text` 一律 `source_text[start:end]` 直接切片；每个 span 构建后立即调 `validate_evidence()`，
任一问题抛 `EvidenceValidationError`（不允许产出可疑 span）。源文件读不到、坐标越界、
校验失败 → 抛 `EvidenceError` / `EvidenceValidationError`，由调用方决定状态，本层不吞。

纯函数式服务层（为宿主合并预留）：不绑 HTTP、不管理端口与凭证；不依赖 reranker；
不 import 任何 `src.evaluation.*`。本层不加载任何模型（种子与查询向量由调用方给）。
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from app.services.rag_engine.contracts import (EVIDENCE_METHODS, REGION_BODY, Chunk, EvidenceSpan,
                           line_starts_of, to_line, validate_evidence)
from app.services.rag_engine.parsing.reader import read_book

EVIDENCE_DEFAULT_MAX_CHARS = 1200
EVIDENCE_DEFAULT_N_SEEDS = 3
#: 已采用检索配置（P5-LOCAL 结论）：全科 hybrid_weighted@0.5、pool=50，无重排。
DEFAULT_SEARCH_METHOD = "hybrid_weighted"
DEFAULT_ALPHA = 0.5
DEFAULT_POOL = 50
DEFAULT_K = 50
DEFAULT_RRF_K = 60.0
#: 种子分数种类：search_scored 的 score 即融合分（各方法分不可比，仅用于该次排序）。
DEFAULT_SCORE_KIND = "fusion_score"


class EvidenceError(RuntimeError):
    """证据层失败（源文件缺失、坐标越界等）。调用方决定状态，本层不吞。"""


class EvidenceValidationError(EvidenceError):
    """span 构建后 `validate_evidence` 不通过——可疑证据绝不出本层。"""


# ---------------------------------------------------------------------------
# 源文本缓存
# ---------------------------------------------------------------------------

@dataclass
class SourceFile:
    """一个源文件的只读快照：read_book 文本、原始字节 sha256、每行起始偏移。"""

    file: str                       # 相对语料根路径（正斜杠规范形）
    text: str                       # read_book() 返回值（UTF-8 + 通用换行归一化）
    sha256: str                     # 原始文件**字节**的 sha256
    line_starts: list[int]

    def line_of(self, off: int) -> int:
        return to_line(self.line_starts, off)


def default_corpus_root() -> str:
    """语料根：取 configs/heading_rules.yaml 的 corpus_root（只读配置）。"""
    from app.services.rag_engine.parsing.heading_rules import load_rules
    return load_rules().corpus_root


def load_source(file_rel_path: str, corpus_root: str | None = None) -> SourceFile:
    """读取一个源文件并计算指纹。文件不存在 → EvidenceError（明确失败）。

    `file` 相对语料根；语料根缺省取 `configs/heading_rules.yaml` 的 `corpus_root`。
    text 用 `read_book()`（与 chunk 坐标同一实现：UTF-8 解码 + 通用换行归一化）；
    sha256 按**原始文件字节**计算（两套语义，见 SCHEMA §九 9.1）。
    """
    if corpus_root is None:
        corpus_root = default_corpus_root()
    rel = file_rel_path.replace("\\", "/")
    path = os.path.join(corpus_root, *rel.split("/"))
    if not os.path.isfile(path):
        raise EvidenceError(
            f"源文件不存在：{path}（语料根 {corpus_root}，file={file_rel_path!r}）")
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    text = read_book(path)
    return SourceFile(file=rel, text=text, sha256=sha, line_starts=line_starts_of(text))


class SourceCache:
    """按 file 记忆化的 `load_source`（一次运行每文件只读一遍）。语料全程只读。"""

    def __init__(self, corpus_root: str | None = None):
        self._corpus_root = corpus_root
        self._cache: dict[str, SourceFile] = {}

    @property
    def corpus_root(self) -> str:
        if self._corpus_root is None:
            self._corpus_root = default_corpus_root()
        return self._corpus_root

    def get(self, file_rel_path: str) -> SourceFile:
        key = file_rel_path.replace("\\", "/")
        if key not in self._cache:
            self._cache[key] = load_source(key, self.corpus_root)
        return self._cache[key]

    def __contains__(self, file_rel_path: str) -> bool:
        return file_rel_path.replace("\\", "/") in self._cache


# ---------------------------------------------------------------------------
# 候选单元与合并规则（全部按原文字符位置判定）
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    """一个并入单元（检索种子或同节 body 邻块），由原文字符位置刻画。

    `text` 是该 chunk 记录的正文（`Chunk.text`）。重建时会与**当前源文件**的
    `source_text[start:end]` 逐字符核对：不一致说明切分产物与语料版本不一致，
    此时只从新文件切片再自证"切片正确"是没有意义的——必须明确失败。
    """

    chunk_id: str
    start: int
    end: int
    region: str
    is_seed: bool
    text: str
    score: float | None = None


def _assert_node_text(src: SourceFile, nodes: list[_Node]) -> None:
    """核对每个并入单元的 chunk 文本与当前源文件 `[start,end)` 逐字符一致。

    这是"语料版本 vs 切分坐标"的真实交叉检查：`validate_evidence` 校验的是
    span.text == source_text[start:end]（由构造保证），单靠它无法发现坐标整体
    陈旧（从新文件切出来当然自洽）。以 `Chunk.text` 为对照即可发现漂移。
    """
    for n in nodes:
        if n.start < 0 or n.end > len(src.text) or n.start >= n.end:
            raise EvidenceError(
                f"chunk {n.chunk_id} 坐标 [{n.start},{n.end}) 越界（file={src.file}，"
                f"源文本长 {len(src.text)}）——切分产物与当前语料版本不一致，拒绝产出证据")
        piece = src.text[n.start:n.end]
        if piece != n.text:
            raise EvidenceError(
                f"chunk {n.chunk_id} 记录的正文与当前源文件 [{n.start},{n.end}) 不一致"
                f"（file={src.file}）——切分产物与语料版本不一致；不接受'从新文件切片"
                f"再自证切片正确'，请重建切分/索引")


def _node_sort_key(n: _Node) -> tuple[int, int, str]:
    """确定性排序：按 (start, end, chunk_id)，并列按 chunk_id。"""
    return (n.start, n.end, n.chunk_id)


def _gap_safe(text: str, prev: _Node, nxt: _Node) -> bool:
    """gap [prev.end, nxt.start) 内只有空白（或紧邻/重叠）才可并入。"""
    if nxt.start <= prev.end:
        return True                      # 紧邻或重叠：重叠交给结果内去重
    return text[prev.end:nxt.start].strip() == ""


def _attach_ok(text: str, prev: _Node, nxt: _Node) -> bool:
    """并入条件：双方都是 body（习题区不并入）且 gap 安全。同节由分组保证。"""
    return prev.region == REGION_BODY and nxt.region == REGION_BODY and _gap_safe(text, prev, nxt)


def _break_reason(text: str, prev: _Node, nxt: _Node) -> str:
    if prev.region != REGION_BODY or nxt.region != REGION_BODY:
        return "相邻块含习题区（exercise 不并入）"
    gap = text[prev.end:nxt.start] if nxt.start > prev.end else ""
    if gap.strip():
        return "gap 含非空白文本（被丢弃的标题/栏目/目录内容，不合并）"
    return "不可并入（未知原因）"


def _build_runs(text: str, nodes: list[_Node]) -> tuple[list[list[_Node]], list[dict]]:
    """把同 file 同节的有序 node 序列按并入规则切成若干「连续 run」。

    返回 (runs, dropped_gaps)。runs 内 node 两两可并入（紧邻或纯空白 gap）；
    dropped_gaps 记录每处断链（前后 chunk_id、gap 字符数、原因）。
    """
    runs: list[list[_Node]] = [[nodes[0]]]
    dropped: list[dict] = []
    for prev, nxt in zip(nodes, nodes[1:]):
        if _attach_ok(text, prev, nxt):
            runs[-1].append(nxt)
        else:
            dropped.append({
                "after_chunk_id": prev.chunk_id,
                "before_chunk_id": nxt.chunk_id,
                "gap_chars": max(0, nxt.start - prev.end),
                "reason": _break_reason(text, prev, nxt),
            })
            runs.append([nxt])
    return runs, dropped


def _split_run_by_budget(run: list[_Node], budget: int) -> list[list[_Node]]:
    """把一个 run 按块粒度贪心切成若干段，每段 [first.start, last.end] ≤ budget。

    段内含纯空白 gap（其字符计入预算）；段间不共享字符。
    """
    parts: list[list[_Node]] = []
    cur = [run[0]]
    for nxt in run[1:]:
        if nxt.end - cur[0].start > budget:
            parts.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)
    parts.append(cur)
    return parts


def _split_node_chars(node: _Node, budget: int) -> list[tuple[int, int]]:
    """单块仍超预算：按字符切成若干 ≤ budget 的片段（坐标随后重算）。"""
    pieces: list[tuple[int, int]] = []
    s = node.start
    while node.end - s > budget:
        pieces.append((s, s + budget))
        s += budget
    pieces.append((s, node.end))
    return pieces


# ---------------------------------------------------------------------------
# span 构建（切片 → 校验，任一问题抛错）
# ---------------------------------------------------------------------------

def _make_span(*, method: str, src: SourceFile, start: int, end: int,
               nodes: list[_Node], path: list[str], book: str,
               score: float | None, score_kind: str | None,
               seed_ids: list[str], expansions: dict) -> EvidenceSpan:
    if start < 0 or end > len(src.text):
        raise EvidenceError(
            f"坐标越界：[{start},{end}) 超出源文本长度 {len(src.text)}"
            f"（file={src.file}）——chunk 坐标与当前源文件版本不一致，拒绝产出证据")
    if start >= end:
        raise EvidenceError(f"非法区间 [{start},{end})（file={src.file}）")
    _assert_node_text(src, nodes)              # 切分坐标 vs 当前语料的交叉核对
    text = src.text[start:end]
    merged_ids = [n.chunk_id for n in nodes]
    exp = {"merged_chunk_ids": merged_ids, "seed_chunk_ids": list(seed_ids),
           "skipped_gaps": [], "budget_split": False, "n_nodes": len(nodes)}
    exp.update(expansions)
    span = EvidenceSpan(
        citation_id="pending",               # 去重排序后统一编号
        file=src.file, book=book, path=[str(p) for p in path],
        source_sha256=src.sha256, char_span=[start, end],
        line_span=[src.line_of(start), src.line_of(end)],
        text=text, chunk_ids=merged_ids, method=method,
        selection_score=score, score_kind=score_kind, expansions=exp,
    )
    problems = validate_evidence(span, src.text, src.sha256, src.line_starts)
    if problems:
        raise EvidenceValidationError(
            f"证据校验失败（file={src.file} span=[{start},{end})）：{problems}")
    return span


def _dedupe_and_sort(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """同结果内重叠区间确定性去重；跨文件绝不比较。

    同 file 内按 (start, end, 首 chunk_id) 排序后线性扫描：与前一保留项重叠时，
    保留 (覆盖 chunk 数, 长度) 更大者（并列保持先出现者）。最后按
    (file, start, end) 全序编号 citation_id = c1..cN（确定性）。
    """
    by_file: dict[str, list[EvidenceSpan]] = {}
    for s in spans:
        by_file.setdefault(s.file, []).append(s)
    kept_all: list[EvidenceSpan] = []
    for file_id in sorted(by_file):
        group = sorted(by_file[file_id],
                       key=lambda s: (s.char_span[0], s.char_span[1],
                                      s.chunk_ids[0] if s.chunk_ids else ""))
        kept: list[EvidenceSpan] = []
        for s in group:
            if kept and s.char_span[0] < kept[-1].char_span[1]:
                prev = kept[-1]
                prev_key = (len(prev.chunk_ids),
                            prev.char_span[1] - prev.char_span[0])
                cur_key = (len(s.chunk_ids), s.char_span[1] - s.char_span[0])
                if cur_key > prev_key:
                    kept[-1] = s
            else:
                kept.append(s)
        kept_all.extend(kept)
    kept_all.sort(key=lambda s: (s.file, s.char_span[0], s.char_span[1]))
    for i, s in enumerate(kept_all, 1):
        s.citation_id = f"c{i}"
    return kept_all


# ---------------------------------------------------------------------------
# 三种方法
# ---------------------------------------------------------------------------

def _single_chunk_spans(seeds: list[tuple[Chunk, float, int]], resolve,
                        score_kind: str) -> list[EvidenceSpan]:
    """基线：种子各自成段，char_span=[c.start, c.end)，不扩展、不受预算影响。"""
    spans: list[EvidenceSpan] = []
    for chunk, score, rank in seeds:
        src = resolve(chunk.file)
        node = _Node(chunk.chunk_id, chunk.start, chunk.end, chunk.region, True,
                     chunk.text, float(score))
        spans.append(_make_span(
            method="single_chunk", src=src, start=chunk.start, end=chunk.end,
            nodes=[node], path=chunk.path, book=chunk.book,
            score=float(score), score_kind=score_kind,
            seed_ids=[chunk.chunk_id],
            expansions={"skipped_gaps": [], "budget_split": False, "seed_rank": rank}))
    return spans


def _group_nodes(seed_entries: list[tuple[Chunk, float, int]],
                 all_chunks: list[Chunk] | None, file_id: str,
                 sec: tuple[str, ...]) -> list[_Node]:
    """一个 (file, path[:2]) 组的并入单元：组内种子 + 同 file 同节 body 块（可选用）。"""
    by_id: dict[str, _Node] = {}
    for chunk, score, _rank in seed_entries:
        if chunk.file == file_id and tuple(chunk.path[:2]) == sec:
            by_id[chunk.chunk_id] = _Node(chunk.chunk_id, chunk.start, chunk.end,
                                          chunk.region, True, chunk.text,
                                          float(score))
    if all_chunks is not None:
        for c in all_chunks:
            if c.file == file_id and tuple(c.path[:2]) == sec \
                    and c.region == REGION_BODY and c.chunk_id not in by_id:
                by_id[c.chunk_id] = _Node(c.chunk_id, c.start, c.end, c.region,
                                          False, c.text)
    return sorted(by_id.values(), key=_node_sort_key)


def _adjacent_drops(dropped: list[dict], run: list[_Node]) -> list[dict]:
    """与本 run 相邻的断链记录（run 首块之前 / 末块之后）。"""
    first_id, last_id = run[0].chunk_id, run[-1].chunk_id
    out = []
    for g in dropped:
        if g["before_chunk_id"] == first_id or g["after_chunk_id"] == last_id:
            out.append(g)
    return out


def _rse_spans(groups: dict[tuple[str, tuple[str, ...]], list[tuple[Chunk, float, int]]],
               all_chunks: list[Chunk] | None, resolve, *,
               max_chars: int, score_kind: str) -> list[EvidenceSpan]:
    """RSE：重建各选中组内**含种子的**安全连续区间，超预算按块/字符拆分。"""
    spans: list[EvidenceSpan] = []
    for key in sorted(groups):
        file_id, sec = key
        entries = groups[key]
        src = resolve(file_id)
        head_chunk, head_score, head_rank = entries[0]
        nodes = _group_nodes(entries, all_chunks, file_id, sec)
        if not nodes:
            continue
        runs, dropped = _build_runs(src.text, nodes)
        seed_ids_all = [c.chunk_id for c, _s, _r in entries]
        for run in runs:
            if not any(n.is_seed for n in run):
                continue                      # 不含种子的连续段不产出证据
            adj = _adjacent_drops(dropped, run)
            parts = _split_run_by_budget(run, max_chars)
            multi = len(parts) > 1
            for part in parts:
                if len(part) == 1 and part[0].end - part[0].start > max_chars:
                    for s, e in _split_node_chars(part[0], max_chars):
                        spans.append(_make_span(
                            method="rse", src=src, start=s, end=e, nodes=part,
                            path=head_chunk.path, book=head_chunk.book,
                            score=head_score, score_kind=score_kind,
                            seed_ids=[i for i in seed_ids_all
                                      if i in {n.chunk_id for n in part}],
                            expansions={"skipped_gaps": adj, "budget_split": True,
                                        "run_chunk_ids": [n.chunk_id for n in run],
                                        "seed_rank": head_rank}))
                else:
                    spans.append(_make_span(
                        method="rse", src=src, start=part[0].start,
                        end=part[-1].end, nodes=part, path=head_chunk.path,
                        book=head_chunk.book, score=head_score,
                        score_kind=score_kind,
                        seed_ids=[i for i in seed_ids_all
                                  if i in {n.chunk_id for n in part}],
                        expansions={"skipped_gaps": adj,
                                    "budget_split": multi,
                                    "run_chunk_ids": [n.chunk_id for n in run],
                                    "seed_rank": head_rank}))
    return spans


def _bounded_window_spans(anchor: tuple[Chunk, float, int],
                          all_chunks: list[Chunk] | None, resolve, *,
                          max_chars: int, score_kind: str) -> list[EvidenceSpan]:
    """以最强种子为中心的同节窗口：先扩成安全连续 run，再围绕种子收进预算。"""
    chunk, score, rank = anchor
    src = resolve(chunk.file)
    sec = tuple(chunk.path[:2])
    nodes = _group_nodes([anchor], all_chunks, chunk.file, sec)
    runs, dropped = _build_runs(src.text, nodes)
    run = next((r for r in runs if any(n.chunk_id == chunk.chunk_id for n in r)), None)
    if run is None:                            # 理论不可达（锚点必在某个 run 里）
        raise EvidenceError(f"锚点 chunk 未落入任何连续 run：{chunk.chunk_id}")
    idx = next(i for i, n in enumerate(run) if n.chunk_id == chunk.chunk_id)
    seed_ids = [chunk.chunk_id]

    if chunk.end - chunk.start > max_chars:
        # 锚点自身超预算：按字符拆分并重算坐标（绝不沿用旧坐标截断）
        out = []
        for s, e in _split_node_chars(_Node(chunk.chunk_id, chunk.start, chunk.end,
                                            chunk.region, True, chunk.text,
                                            float(score)),
                                      max_chars):
            out.append(_make_span(
                method="bounded_window", src=src, start=s, end=e, nodes=run[:1],
                path=chunk.path, book=chunk.book, score=float(score),
                score_kind=score_kind, seed_ids=seed_ids,
                expansions={"skipped_gaps": _adjacent_drops(dropped, run),
                            "budget_split": True,
                            "anchor_chunk_id": chunk.chunk_id, "seed_rank": rank}))
        return out

    lo = hi = idx
    while True:
        grew = False
        if lo > 0 and run[hi].end - run[lo - 1].start <= max_chars:
            lo -= 1
            grew = True
        if hi + 1 < len(run) and run[hi + 1].end - run[lo].start <= max_chars:
            hi += 1
            grew = True
        if not grew:
            break
    window = run[lo:hi + 1]
    excluded = [n.chunk_id for n in run[:lo]] + [n.chunk_id for n in run[hi + 1:]]
    spans = [_make_span(
        method="bounded_window", src=src, start=window[0].start,
        end=window[-1].end, nodes=window, path=chunk.path, book=chunk.book,
        score=float(score), score_kind=score_kind, seed_ids=seed_ids,
        expansions={"skipped_gaps": _adjacent_drops(dropped, run),
                    "budget_split": bool(excluded),
                    "excluded_chunk_ids": excluded,
                    "anchor_chunk_id": chunk.chunk_id, "seed_rank": rank})]
    return spans


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _resolve_source(sources, file_id: str) -> SourceFile:
    getter = getattr(sources, "get", None)
    if getter is None:
        raise EvidenceError(
            f"sources 必须提供 .get(file)（SourceCache 或 dict），得到 {type(sources)!r}")
    src = getter(file_id)
    if src is None:
        raise EvidenceError(f"种子 chunk 的源文件未加载：{file_id}（sources 中无该文件）")
    return src


def reconstruct(seeds: list[tuple[Chunk, float, int]],
                sources, method: str, *,
                max_chars: int = EVIDENCE_DEFAULT_MAX_CHARS,
                n_seeds: int = EVIDENCE_DEFAULT_N_SEEDS,
                all_chunks: list[Chunk] | None = None,
                score_kind: str = DEFAULT_SCORE_KIND) -> list[EvidenceSpan]:
    """证据区间重建主入口（供 P6-EVAL / P7 复用）。

    参数：
      seeds      `HybridSearcher.search_scored()` 的输出 `[(Chunk, score, rank)]`
                 （rank 1-based，按融合分降序；本函数内部再按 rank 升序排序以防御）。
      sources    源文本缓存：`SourceCache` 或 `{file_rel_path: SourceFile}`（可注入替身）。
      method     "single_chunk" | "bounded_window" | "rse"。
      max_chars  bounded_window / rse 的合并字符预算（超过则拆分并重算坐标）。
      n_seeds    rse 取融合序前 N 个种子（按 (file, path[:2]) 去重）。
      all_chunks 可选：全量 chunk 列表（同 file 同节 body 块参与扩展/重建；
                 缺省时 rse 只合并种子本身、bounded_window 退化为种子本身）。
      score_kind 种子分数种类（search_scored 输出即 "fusion_score"）。

    返回校验过的 `list[EvidenceSpan]`（citation_id 按 (file, start, end) 确定性编号）。
    空种子 → 空列表（不抛错、不产假证据）；失败（源缺失/越界/校验不过）→ 抛 EvidenceError。
    """
    if not seeds:
        return []
    if method not in EVIDENCE_METHODS:
        raise ValueError(f"未知证据方法: {method!r}（应为 {EVIDENCE_METHODS}）")
    if max_chars <= 0:
        raise ValueError(f"max_chars 必须为正，得到 {max_chars}")
    if n_seeds <= 0:
        raise ValueError(f"n_seeds 必须为正，得到 {n_seeds}")
    ordered = sorted(seeds, key=lambda t: t[2])          # rank 升序 = 融合序

    if method == "single_chunk":
        return _dedupe_and_sort(
            _single_chunk_spans(ordered, lambda f: _resolve_source(sources, f),
                                score_kind))

    if method == "bounded_window":
        return _dedupe_and_sort(
            _bounded_window_spans(ordered[0], all_chunks,
                                  lambda f: _resolve_source(sources, f),
                                  max_chars=max_chars, score_kind=score_kind))

    # rse：融合序前 n_seeds 个种子，按 (file, path[:2]) 去重——即至多 n_seeds 个
    # 「出发点组」；选中组内的**全部**种子都参与合并（种子之间的区间逐对检查），
    # 未选中组的种子不出现。
    picked_keys: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for chunk, _s, _r in ordered:
        key = (chunk.file, tuple(chunk.path[:2]))
        if key in seen:
            continue
        seen.add(key)
        picked_keys.append(key)
        if len(picked_keys) >= n_seeds:
            break
    groups: dict[tuple[str, tuple[str, ...]], list[tuple[Chunk, float, int]]] = {}
    for entry in ordered:
        key = (entry[0].file, tuple(entry[0].path[:2]))
        if key in seen:
            groups.setdefault(key, []).append(entry)
    return _dedupe_and_sort(
        _rse_spans(groups, all_chunks, lambda f: _resolve_source(sources, f),
                   max_chars=max_chars, score_kind=score_kind))


def evidence_from_question(searcher, query: str, qv, *, method: str,
                           pool: int = DEFAULT_POOL, k: int = DEFAULT_K,
                           alpha: float = DEFAULT_ALPHA,
                           rrf_k: float = DEFAULT_RRF_K,
                           max_chars: int = EVIDENCE_DEFAULT_MAX_CHARS,
                           n_seeds: int = EVIDENCE_DEFAULT_N_SEEDS,
                           subject: str | None = None,
                           all_chunks: list[Chunk] | None = None,
                           source_cache: SourceCache | None = None,
                           corpus_root: str | None = None) -> list[EvidenceSpan]:
    """便捷入口（P7 服务 / CLI / 段级标注候选共用）：已采用配置检索 + 证据重建。

    检索固定走 `searcher.search_scored(query, qv, "hybrid_weighted", k, pool,
    rrf_k, alpha)`（P5-LOCAL 已采用配置：全科 hybrid_weighted@0.5、pool=50、
    本地 BGE-M3 1024、无重排；不依赖 reranker）。`method` 是**证据方法**
    ∈ {single_chunk, bounded_window, rse}。`source_cache` 缺省时从
    `configs/heading_rules.yaml` 的 `corpus_root` 构建（语料只读）。
    `subject` 仅作调用方上下文记录，不参与重建逻辑。

    **邻块来源（P8A / R1）**：`all_chunks` 缺省时取 `searcher.body`——那正是该
    检索器**受约束的正文集合**（学科/书册/文件范围已在构造 searcher 时限定）。
    这样产品入口与评测入口用的是同一个集合与同一份实现：过去服务层没传
    `all_chunks`，`bounded_window` 退化成单 chunk，"默认窗口服务"名不副实。
    显式传入 `all_chunks` 可覆盖（例如外部给定语料子集）。
    """
    scored = searcher.search_scored(query, qv, DEFAULT_SEARCH_METHOD, k=k,
                                    pool=pool, rrf_k=rrf_k, alpha=alpha)
    if source_cache is None:
        source_cache = SourceCache(corpus_root)
    if all_chunks is None:
        all_chunks = getattr(searcher, "body", None)
    return reconstruct(scored, source_cache, method, max_chars=max_chars,
                       n_seeds=n_seeds, all_chunks=all_chunks)
