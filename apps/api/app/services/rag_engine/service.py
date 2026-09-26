"""P7 本地讲解服务层：locate_and_explain（docs/SCHEMA.md §九/§十/§十一）。

**纯函数式服务层**（为宿主"智启课源"合并预留）：
  - 无全局状态、不读环境变量里的凭证、不绑定 HTTP 框架/端口；
  - 所有 I/O 经 ServiceDeps 注入（检索器、题面向量化、生成器、缓存、语料根）；
  - 输出 = contracts.LocateResult（结构化 JSON 可直接映射前端追问卡）。

流程：检索（searcher_provider 学科路由，subject=None → 全库，**不读 gold/题集
标签**；book/file 约束**下推到检索**，先限定范围再排序）→ 证据层
（evidence_from_question，bounded_window 默认，邻块扩展用同一受约束正文集合）
→ 完整上下文预算（R5：题面+系统提示+约束+模板开销+证据包+输出预留，
首轮与修复轮都在发送前验证）→ 生成（JSON Schema 结构化输出；响应经**严格**
schema 校验；失败最多一次有界修复）→ 引用回填与校验（citation_id ∈ 证据包；
**同一条解释只要含未知/未入包 ID 即整条丢弃**，不剥离坏 ID 后放行）
→ **公开结果统一放行**（R3：所有出口都只返回对当前磁盘源文件复验通过的
evidence/citations，失败者只进诊断）→ 原文/坐标/file/path 全部由程序回填。

状态映射（SCHEMA §九）：
  - 证据为空                        → uncertain（不硬答）
  - 模型 uncertain=true             → uncertain（记 reason）
  - 模型空 explanations 且未标 uncertain → uncertain（无解释可放行）
  - JSON/schema 两次失败（含一次修复）→ partial（保留定位）
  - 生成超时/异常                   → partial
  - 上下文预算不足（发送前判定）    → partial（未调用生成器）
  - 模型/服务不可用（含查询向量化不可用）→ model_unavailable
  - 有解释但全部引用校验失败        → invalid_citation
  - 部分解释被丢弃、部分通过        → partial（保留通过的解释）
  - 正常                            → ok

零云端：cloud_requests 恒 0；本地推理次数如实记录（local_inference_count）。

P11 第二步（**影子候选，默认不注入**）
--------------------------------------
`ServiceDeps.candidate_id` / `evidence_source_filter` / `evidence_sufficiency` /
`region_verifier` 默认全为 None：不注入时本模块行为与现役完全一致（门禁代码块整体
跳过、provenance 不新增字段、生成缓存键载荷逐字节不变）。显式注入时在证据包装配
**之前**插入候选门禁：因素 A（来源过滤：不可核验/非正文区间出局）→ 因素 B
（`p8h-suff-v1` 充分性）。全部区间出局 → `uncertain` 且**不发布任何引用**（结构化降级）。
门禁结果（逐条丢弃原因、版本号、候选 ID）写进 `provenance.evidence_gate`。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.services.rag_engine.config import GenerationConfigError, resolve_generation_config
from app.services.rag_engine.contracts import (EVIDENCE_CONTRACT_VERSION, LOCATE_STATUSES,
                           STATUS_INVALID_CITATION, STATUS_MODEL_UNAVAILABLE,
                           STATUS_OK, STATUS_PARTIAL, STATUS_UNCERTAIN,
                           Citation, EvidenceSpan, ExplanationItem,
                           LocateResult, Supplement, normalize_file,
                           validate_evidence)
from app.services.rag_engine.indexing.index_spec import INDEX_PROVENANCE_KEYS
from app.services.rag_engine.llm.budget import (BudgetPlan, check_usage, input_token_limit,
                            measure_messages_auto, resolve_counter)
from app.services.rag_engine.llm.generation_cache import (CACHE_CONTRACT_VERSION, CACHE_RESULT_POLICY,
                                      GenerationCache)
from app.services.rag_engine.llm.local_generator import (BaseGenerator, GenerationCancelled,
                                     GenerationError, GenerationTimeout,
                                     ModelUnavailable)
from app.services.rag_engine.llm.prompts import (OUTPUT_SCHEMA, PROMPT_VERSION, SCHEMA_VERSION,
                             build_messages, select_evidence, span_text_sha256,
                             validate_output_schema)
from app.services.rag_engine.retrieval.evidence import (EVIDENCE_DEFAULT_MAX_CHARS,
                                    EVIDENCE_DEFAULT_N_SEEDS, SourceCache,
                                    evidence_from_question, load_source)
from app.services.rag_engine.retrieval.hybrid import EmptyScope, HybridSearcher

#: 服务契约版本。P8A 变更了响应校验（严格）、证据放行（统一复验）、
#: 预算（完整上下文）与状态映射（模型不可用含查询向量化），因此升版本。
SERVICE_CONTRACT_VERSION = (f"p8a-v1(evidence:{EVIDENCE_CONTRACT_VERSION},"
                            f"schema:{SCHEMA_VERSION})")

#: 允许从 `searcher_provider` 的 meta 透传进 provenance 的检索侧字段。
#: 索引身份部分由 `src/indexing/index_spec.py::INDEX_PROVENANCE_KEYS` **单一定义**
#: （生产者与消费者共用同一份清单），此处只加"路由/范围"字段。
#: `product_subjects`：未指定学科时实际检索了哪几科（产品范围与"全库"不同，
#: 不能只记 scope 一个值就让人以为搜了整库）。
_SEARCH_META_KEYS = ("scope", "subject_filter", "product_subjects", "n_chunks",
                     "session_snapshot", *INDEX_PROVENANCE_KEYS)


class UnknownSubject(ValueError):
    """请求的学科不在部署方提供的路由表里（由 searcher_provider 抛出/透传）。"""


class _StageTimer:
    """阶段计时（P8C-1）：`with _stage(deps, "embed_query"):` —— 无回调时几乎零开销。"""

    __slots__ = ("_cb", "_name", "_t0")

    def __init__(self, deps: "ServiceDeps", name: str):
        self._cb = deps.stage_timer
        self._name = name
        self._t0 = None

    def __enter__(self):
        if self._cb is not None:
            self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._cb is not None and self._t0 is not None:
            self._cb(self._name, time.perf_counter() - self._t0)
        return False


def _stage(deps: "ServiceDeps", name: str) -> _StageTimer:
    return _StageTimer(deps, name)


@dataclass
class ServiceDeps:
    """服务依赖注入容器（纯函数式的全部 I/O 出入口）。

    searcher_provider
        学科名（或 None=全库）→ (HybridSearcher, meta)。
        meta 至少含 {"scope": "subject"|"all"}；可附 {"subject_filter": …}。
        索引身份字段（`src/indexing/index_spec.py::INDEX_PROVENANCE_KEYS`：
        `index_spec`/`chunks_fingerprint`/`index_dir`/…）会被如实透传进
        `provenance.search.index_identity` 与运行台账——**报了就记，不猜不补**。
        **subject=None 时必须路由到全库检索器**——服务层绝不读取评测集/gold
        去推断学科。
    embed_query
        题面 → 查询向量（真实部署 = 本地 Ollama BGE-M3；测试注入假件）。
    generator
        LocalOllamaGenerator 或 MockGenerator（BaseGenerator 接口）。
    cache_dir
        生成缓存根（None = 不用缓存）。mock 与真实由生成器 is_mock 决定命名空间。
    generation_config
        生成配置（configs/models.yaml 全量 / generation 段 / 扁平覆盖）。
        **解析与默认值只在 src/config.py 一处**（P8A / R10：过去本模块自带一套
        默认值，与 provider 段里的实际配置"恰好相同"，掩盖了配置不生效的缺陷）。
    source_cache / corpus_root
        证据回填校验用源文本缓存（语料只读）。公开结果放行一律**重新读盘**
        （不经快照），以拦住生成期间的源文件变更。
    runs_dir
        运行台账目录（None = 不写台账；mock 恒不写）。
    usage_summary
        可选回调：真实生成调用后收到 usage dict（供外层聚合，不落盘）。
    strict_identity
        为真时，若生成器自报身份与解析出的 provider 身份不一致 → 明确失败
        （默认只记 provenance.identity_mismatch，不阻断历史调用方）。
    """

    searcher_provider: Callable[[str | None], tuple[HybridSearcher, dict]]
    embed_query: Callable[[str], np.ndarray]
    generator: Any
    corpus_root: str | None = None
    source_cache: SourceCache | None = None
    cache_dir: str | None = None
    generation_config: dict = field(default_factory=dict)
    runs_dir: str | None = None
    usage_summary: Callable[[dict], None] | None = None
    # 证据层参数（默认即已采用配置）
    evidence_method: str = "bounded_window"
    evidence_max_chars: int = EVIDENCE_DEFAULT_MAX_CHARS
    evidence_n_seeds: int = EVIDENCE_DEFAULT_N_SEEDS
    strict_identity: bool = False
    #: 可选阶段计时回调 (stage_name, seconds) —— 供性能剖析使用；默认 None（零开销）。
    #: 只在**产品路径的真实边界**打点，不做逻辑分支，不改变任何返回值。
    stage_timer: Callable[[str, float], None] | None = None
    #: 回答策略（P8C-2 A2 候选，默认 "baseline" = 现役提示词）。参与生成缓存键。
    answer_policy: str = "baseline"
    #: 是否记录"题面术语在证据包中的覆盖率"信号（P8C-2；默认关闭以零开销）。
    #: 该信号**只记录、不参与任何拒绝判定**（阈值需人工标注样本校准，本批无金标）。
    record_coverage_signal: bool = False
    # ---- P11 第二步：影子候选（**全部默认关闭；不注入即现役路径不变**）----
    #: 候选 ID（如 `p11-cand-A`）。**非 None 时**才进入生成缓存键（连同 `index_spec`），
    #: 以保证候选与 A0、候选之间物理不串缓存；默认 None → 键载荷逐字节不变。
    candidate_id: str | None = None
    #: 因素 A：证据来源过滤（机械正文归属复核）。None = 不启用。
    evidence_source_filter: Any | None = None
    #: 因素 B：`p8h-suff-v1` 充分性判定配置（`SufficiencyConfig`）。None = 不启用。
    evidence_sufficiency: Any | None = None
    #: 因素 A 的区间判定器（`sufficiency.build_region_verifier(...)` 的返回值）。
    #: **只在 `evidence_source_filter.enabled` 为真时被调用**。
    region_verifier: Callable[[str, int, int], dict] | None = None
    #: 宿主可注入离线词表位置；None 沿用仓库默认路径，模型 digest 守卫不变。
    tokenizer_vocab_path: str | None = None


# ---------------------------------------------------------------------------
# 公开结果的证据放行（R3：唯一实现点，所有出口共用）
# ---------------------------------------------------------------------------


class _SpanRelease:
    """公开 evidence/citations 的放行闸门。

    审查结论（R3）：服务在最终复验前构造全部 citations，复验失败只删解释，
    仍把失效 evidence/citations 交给 `_finish`——依赖 JSON 展示引用的宿主会拿到
    已判定失效的原文和位置。

    本类保证：**只有对当前磁盘源文件逐条复验通过的 span 才会出现在公开结果里**；
    失败项连同原因写进 `provenance.citation_validation.release.failures`。
    每个源文件在一次运行内只读一遍（新鲜读，不经 SourceCache 快照），
    因此"生成期间源文件被改写/删除"能被拦住。
    """

    def __init__(self, corpus_root: str | None):
        self._corpus_root = corpus_root
        self._sources: dict[str, Any] = {}      # file → SourceFile | Exception
        self._problems: dict[str, list[str]] = {}

    def _source(self, file_rel: str):
        key = normalize_file(file_rel)
        if key not in self._sources:
            try:
                self._sources[key] = load_source(key, self._corpus_root)
            except Exception as e:              # noqa: BLE001 —— 读不到也是"不可放行"
                self._sources[key] = e
        return self._sources[key]

    def problems(self, span: EvidenceSpan) -> list[str]:
        """该 span 相对当前源文件的问题列表（空 = 可放行）。按 citation_id 记忆化。"""
        if span.citation_id not in self._problems:
            src = self._source(span.file)
            if isinstance(src, Exception):
                self._problems[span.citation_id] = [
                    f"当前源文件不可读或已删除：{src}"]
            else:
                self._problems[span.citation_id] = validate_evidence(
                    span, src.text, src.sha256, src.line_starts)
        return self._problems[span.citation_id]

    def release(self, spans: list[EvidenceSpan]
                ) -> tuple[list[EvidenceSpan], list[dict]]:
        keep: list[EvidenceSpan] = []
        failures: list[dict] = []
        for s in spans:
            probs = self.problems(s)
            if probs:
                failures.append({"citation_id": s.citation_id, "file": s.file,
                                 "book": s.book, "reasons": list(probs)})
            else:
                keep.append(s)
        return keep, failures


def _coverage_signal(question: str, pack_text: str, used_ids: list[str]) -> dict:
    """题面术语在证据包中的覆盖率（**只记录，不参与判定**；P8C-2）。

    这是"可追溯的原始信号"之一（不是融合分）：用 jieba 切题面取长度 ≥2 的词，
    统计有多少出现在证据包文本里。**不得**直接当拒答阈值——阈值必须在人工标注的
    正负样本上按学科/scope 校准误拒与误答；本批无人工金标，故只记录分布。
    """
    try:
        import jieba
        terms = sorted({t for t in jieba.lcut(question) if len(t.strip()) >= 2})
    except Exception:      # noqa: BLE001
        terms = []
    present = [t for t in terms if t in pack_text]
    return {
        "n_terms": len(terms),
        "n_present": len(present),
        "coverage": (len(present) / len(terms)) if terms else None,
        "missing": [t for t in terms if t not in present][:20],
        "used_span_ids": list(used_ids),
        "note": "只记录信号，不参与拒绝判定；阈值需人工标注样本校准",
    }


# ---------------------------------------------------------------------------
# 响应解析与校验（R6：实时/修复/缓存三条路共用同一实现）
# ---------------------------------------------------------------------------


def _parse_json_object(text: str) -> dict:
    """从模型输出解析 JSON 对象（容忍 ```json 围栏）。失败抛 ValueError。"""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise ValueError("模型输出不是 JSON 对象")
    return obj


def _parse_and_check(text: str, pack_ids: list[str]) -> tuple[dict | None, str | None]:
    """解析 + **严格** schema 校验 + 归一化（不做任何类型修饰）。

    返回 (parsed | None, error)。error 非空即视为"本轮输出不合格"，
    调用方据此进入至多一次有界修复，或降级返回。
    """
    try:
        obj = _parse_json_object(text)
    except ValueError as e:
        return None, f"JSON 解析失败：{e}"
    problems, extra = validate_output_schema(obj)
    if problems:
        return None, "响应不符合 schema：" + "；".join(problems[:6]) + (
            f"（另有 {len(problems) - 6} 项）" if len(problems) > 6 else "")
    parsed = _normalize_output(obj, pack_ids)
    if extra:
        parsed["extra_keys"] = extra
    return parsed, None


def _normalize_output(obj: dict, pack_ids: list[str]) -> dict:
    """整理为受控结构。**保留原始 citation_ids**，未知 ID 只标记不剥离——
    剥离会让"模型依赖 c999 的论断"被重新归给 c1（R2 复现的正是这种错误归因）。
    """
    pack = set(pack_ids)
    explanations = []
    for e in obj["explanations"]:
        cids = list(e["citation_ids"])
        unknown = [c for c in cids if c not in pack]
        seen: set[str] = set()
        dups: list[str] = []
        for c in cids:
            if c in seen and c not in dups:
                dups.append(c)
            seen.add(c)
        explanations.append({
            "point": e["point"].strip(),
            "citation_ids": cids,               # 原样保留（含未知/重复）
            "unknown_citation_ids": unknown,
            "duplicate_citation_ids": dups,
            "explanation": e["explanation"].strip(),
            "supplement": e.get("supplement"),
        })
    return {
        "knowledge_points": [k.strip() for k in obj["knowledge_points"]],
        "explanations": explanations,
        "uncertain": bool(obj["uncertain"]),
    }


def _validate_and_backfill(
    parsed: dict, spans_by_id: dict[str, EvidenceSpan], release: _SpanRelease,
) -> tuple[list[ExplanationItem], list[str], list[str], list[str]]:
    """引用校验 + 程序回填。

    返回 (items, dropped_reasons, unknown_id_total, dedup_notes)。

    规则（SCHEMA §九 / §十，R2 收紧）：
      - **同一条解释**只要出现未知/未入包 citation_id → **整条丢弃**，不剥离坏 ID
        后放行（剥离会改变论断归属）；其他独立有效的解释照常保留 → partial；
      - 引用为空 → 丢弃（无引用的讲解不得放行）；
      - 通过的解释：其每个 citation_id 必须**对当前磁盘源文件复验通过**
        （`_SpanRelease`，与公开结果出口同一实现）；任一失败 → 该条丢弃；
      - 重复 citation_id：去重（引用集合不变，不改变归属）并记录，不判违规；
      - 原文/书册/路径/坐标由程序从 span 回填，模型不得生成。
    """
    items: list[ExplanationItem] = []
    dropped: list[str] = []
    unknown_total = 0
    dedup_notes: list[str] = []
    for e in parsed.get("explanations", []):
        point = e.get("point", "")
        unknown = list(e.get("unknown_citation_ids") or [])
        unknown_total += len(unknown)
        if unknown:
            dropped.append(
                f"解释 {point!r} 引用未知/未入包 citation_id {unknown} → 整条丢弃"
                f"（不放行其余引用：删除坏 ID 会把论断错归给幸存引用）")
            continue
        cids = list(dict.fromkeys(e.get("citation_ids", [])))
        if e.get("duplicate_citation_ids"):
            dedup_notes.append(f"解释 {point!r} 的 citation_ids 含重复项 "
                               f"{e['duplicate_citation_ids']}，已去重（引用集合不变）")
        if not cids:
            dropped.append(f"解释 {point!r} 无引用 → 丢弃（无引用的讲解不得放行）")
            continue
        bad = False
        for cid in cids:
            span = spans_by_id.get(cid)
            if span is None:                    # 防御：未知 ID 已在上面拦下
                bad = True
                dropped.append(f"解释 {point!r} 引用 {cid} 不在证据包内 → 丢弃")
                break
            probs = release.problems(span)
            if probs:
                bad = True
                dropped.append(f"解释 {point!r} 引用 {cid} 复验失败：{probs}")
                break
        if bad:
            continue
        sup_text = e.get("supplement")
        supplement = Supplement(text=str(sup_text), is_external=True) \
            if isinstance(sup_text, str) and sup_text.strip() else None
        items.append(ExplanationItem(
            point=str(point), citation_ids=list(cids),
            explanation=str(e.get("explanation", "")), supplement=supplement))
    return items, dropped, unknown_total, dedup_notes


def locate_and_explain(question: str, *, deps: ServiceDeps,
                       subject: str | None = None, book: str | None = None,
                       file: str | None = None, top_k: int = 50, pool: int = 50,
                       alpha: float = 0.5, rerank: str = "off") -> LocateResult:
    """输入一道题，输出定位（章节 + 行号 + 字符区间 + 原文）与讲解。纯函数式。"""
    if rerank != "off":
        raise ValueError("P7 服务默认无重排（已采用配置）；rerank 只接受 'off'")

    # ---- 0) 配置（唯一定义点 src/config.py；R10）----
    try:
        cfg = resolve_generation_config(deps.generation_config)
    except GenerationConfigError as e:
        raise  # 配置非法是部署错误：明确抛出，不静默取默认（SCHEMA §四）
    budget_cfg = cfg["budget"]
    cpt = budget_cfg["chars_per_token_lower"]

    gen_identity = {
        "provider": str(getattr(deps.generator, "provider", "?")),
        "model_id": str(getattr(deps.generator, "model_id", "?")),
    }
    identity_mismatch = [
        k for k in ("provider", "model_id")
        if cfg.get(k) and gen_identity[k] != "?" and str(cfg[k]) != gen_identity[k]
    ]
    if identity_mismatch and deps.strict_identity:
        raise GenerationConfigError(
            f"生成器身份与选中 provider 不一致（{identity_mismatch}）："
            f"配置={ {k: cfg.get(k) for k in identity_mismatch} } "
            f"生成器={ {k: gen_identity[k] for k in identity_mismatch} }")

    from app.services.rag_engine.llm.prompts import ANSWER_POLICIES, ANSWER_POLICY_PROMPT_VERSIONS
    if deps.answer_policy not in ANSWER_POLICIES:
        raise ValueError(f"未知 answer_policy {deps.answer_policy!r}"
                         f"（可选 {sorted(ANSWER_POLICIES)}）")
    # 策略文本参与提示词身份（进缓存键）：基线策略沿用**配置**里的 prompt_version
    # （配置是单一来源，可被显式覆盖）；候选策略使用其登记的版本号。
    effective_prompt_version = (
        cfg["prompt_version"] if deps.answer_policy == "baseline"
        else ANSWER_POLICY_PROMPT_VERSIONS[deps.answer_policy])

    want_file = normalize_file(file) if file else None
    constraints: dict = {
        "scope": "all" if subject is None else "subject",
        "subject": subject,
        "book": book,
        "file": want_file,
        "top_k": top_k, "pool": pool, "alpha": alpha,
        "evidence_method": deps.evidence_method,
        "evidence_max_chars": deps.evidence_max_chars,
        "evidence_n_seeds": deps.evidence_n_seeds,
        "rewrite": "off",
    }
    provenance: dict = {
        "service": "locate_and_explain",
        "contract_version": SERVICE_CONTRACT_VERSION,
        "failure_stage": None,
        "search": {"method": "hybrid_weighted", "alpha": alpha, "pool": pool,
                   "k": top_k, "rerank": "off", "rewrite": "off",
                   "scope": constraints["scope"]},
        "evidence": {"method": constraints["evidence_method"],
                     "max_chars": deps.evidence_max_chars,
                     "n_seeds": deps.evidence_n_seeds,
                     "all_chunks_wired": False},
        "generation": {"provider": gen_identity["provider"],
                       "model_id": gen_identity["model_id"],
                       "config_provider": cfg.get("provider"),
                       "config_model_id": cfg.get("model_id"),
                       "identity_mismatch": identity_mismatch or None,
                       "active_provider_name": cfg.get("active_provider"),
                       "manifest_digest": None, "num_ctx": cfg["num_ctx"],
                       "temperature": cfg["temperature"], "seed": cfg["seed"],
                       "num_predict": cfg["num_predict"],
                       "prompt_version": effective_prompt_version,
                       "schema_version": cfg["schema_version"],
                       "answer_policy": deps.answer_policy,
                       "observed": None},
        "evidence_pack": {"token_budget": cfg["evidence_pack_max_tokens"],
                          "estimation": (f"字符数/{cpt:g}（保守上界：每字符至少 1 "
                                         f"token；口径与校准见 SCHEMA §十一）"),
                          "used_span_ids": [], "dropped": [],
                          "selection_order": [], "selection_note": None,
                          "budget_drops": []},
        "context_budget": {"first_round": None, "repair_round": None,
                           "refused": False, "refusal_reason": None},
        "cache": {"enabled": bool(deps.cache_dir), "hit": False,
                  "contract_version": cfg["cache_contract_version"],
                  "result_policy": CACHE_RESULT_POLICY},
        "local_inference_count": 0,
        "repair_attempts": 0,
        "repair_skipped_reason": None,
        "cloud_requests": 0,
        "cloud_cost_yuan": 0.0,
        "citation_validation": {"used": [], "failed": [], "dropped_explanations": [],
                                "unknown_citation_ids": [], "deduplicated": [],
                                "release": {"n_evidence_in": 0,
                                            "n_evidence_published": 0,
                                            "failures": []}},
        "uncertain_reason": None,
    }
    release = _SpanRelease(deps.corpus_root)

    ledger = None
    if deps.runs_dir and not getattr(deps.generator, "is_mock", False):
        from app.services.rag_engine.llm.local_generator import GenerationRunLedger
        ledger = GenerationRunLedger(deps.runs_dir, meta={
            "provider": gen_identity["provider"],
            "model_id": gen_identity["model_id"],
            "config_provider": cfg.get("provider"),
            "config_model_id": cfg.get("model_id"),
            "num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"],
            "seed": cfg["seed"], "prompt_version": cfg["prompt_version"],
            "schema_version": cfg["schema_version"]})

    def _finish(status: str, evidence: list[EvidenceSpan],
                citations: list[Citation], explanations: list[ExplanationItem],
                reason: str | None) -> LocateResult:
        """**唯一出口**：公开 evidence/citations 在这里统一放行（R3）。"""
        if status not in LOCATE_STATUSES:
            raise ValueError(f"非法状态 {status!r}（允许：{LOCATE_STATUSES}）")
        pub_ev, failures = release.release(evidence)
        pub_ids = {s.citation_id for s in pub_ev}
        kept = [e for e in explanations
                if e.citation_ids and set(e.citation_ids) <= pub_ids]
        dropped_by_release = len(explanations) - len(kept)
        provenance["citation_validation"]["release"] = {
            "n_evidence_in": len(evidence),
            "n_evidence_published": len(pub_ev),
            "failures": failures,
        }
        if failures:
            provenance["citation_validation"]["dropped_explanations"].extend(
                f"{f['citation_id']}（{f['file']}）：{f['reasons']}" for f in failures)
        if dropped_by_release:
            provenance["citation_validation"]["dropped_explanations"].append(
                f"{dropped_by_release} 条解释的证据复验失败 → 整条丢弃（不放行）")
        if explanations and not kept:
            status = STATUS_INVALID_CITATION
        elif status == STATUS_OK and (failures or dropped_by_release):
            status = STATUS_PARTIAL
            if not reason:
                reason = "部分证据复验失败：失效证据不展示（详见 citation_validation.release）"
        provenance["uncertain_reason"] = reason
        provenance["evidence_pack"]["used_span_ids"] = [
            cid for cid in provenance["evidence_pack"]["used_span_ids"]
            if cid in pub_ids]
        if ledger is not None:
            if not kept and explanations:
                ledger.note_error("INVALID_CITATION")
            ledger.note_result(n_explanations=len(kept),
                               evidence_published=len(pub_ev),
                               source=("cache" if provenance["cache"]["hit"]
                                       else "inference"))
            ledger.finalize()
        return LocateResult(
            contract_version=SERVICE_CONTRACT_VERSION, question=question,
            status=status, subject=subject, constraints=constraints,
            evidence=pub_ev, citations=[Citation.from_span(s) for s in pub_ev],
            explanations=kept, uncertain_reason=reason, provenance=provenance)

    # ---- 1) 检索（subject=None → 全库；绝不读 gold/题集标签推断学科） ----
    try:
        with _stage(deps, "searcher_provider"):
            searcher, search_meta = deps.searcher_provider(subject)
    except UnknownSubject as e:
        return _finish(STATUS_UNCERTAIN, [], [], [], f"学科路由失败：{e}")
    except Exception as e:                      # noqa: BLE001 —— 明确降级，不裸抛
        provenance["failure_stage"] = "retrieval"
        return _finish(STATUS_PARTIAL, [], [], [],
                       f"检索层不可用（{type(e).__name__}）：{e}——未产生证据，不硬答")
    provenance["search"]["searcher_meta"] = {
        k: search_meta.get(k) for k in _SEARCH_META_KEYS
        if k in search_meta}
    # 索引身份（P10 契约）：规格名 + chunks 指纹 + index_dir 等实测值。
    # 只要 searcher_provider 报了身份就必须落到 provenance 与运行台账——
    # "这次答案用的是哪一份检索空间"不能只存在于命令行历史里。
    index_identity = {k: search_meta.get(k) for k in INDEX_PROVENANCE_KEYS
                      if k in search_meta}
    if index_identity:
        provenance["search"]["index_identity"] = index_identity
        if ledger is not None:
            ledger.note_index_identity(index_identity)

    # ---- 1b) 范围约束下推（R4：先限定范围再排序，不在结果侧补漏） ----
    scope_info: dict = {"requested_file": want_file, "requested_book": book,
                        "pushed_down": None, "n_in_scope": None, "note": None,
                        "dropped": []}
    if want_file or book:
        def _in_scope(c) -> bool:
            if want_file and normalize_file(c.file) != want_file:
                return False
            if book and c.book != book:
                return False
            return True

        restrict = getattr(searcher, "restrict", None)
        if callable(restrict):
            try:
                searcher = restrict(_in_scope)
                scope_info.update(pushed_down=True, n_in_scope=len(searcher.body))
            except EmptyScope:
                scope_info.update(pushed_down=True, n_in_scope=0,
                                  note="限定范围内没有可检索的正文")
                provenance["constraint_filter"] = scope_info
                provenance["failure_stage"] = "scope"
                return _finish(STATUS_UNCERTAIN, [], [], [],
                               "限定范围内没有可检索的正文（file/book 约束与当前索引"
                               "不匹配）——不在范围外凑答案")
        else:
            # 检索器不支持范围下推：只能在结果侧过滤 → 明确标记降级（可程序化检测），
            # 不伪装成"已在范围内检索"。生产路径的 HybridSearcher 始终支持 restrict。
            scope_info.update(pushed_down=False, degraded=True,
                              note="searcher 不支持 restrict：只能在结果侧过滤，"
                                   "限定范围外排序靠后的命中可能漏检")
        provenance["constraint_filter"] = scope_info

    # ---- 2) 查询向量 ----
    try:
        with _stage(deps, "embed_query"):
            qv = deps.embed_query(question)
    except Exception as e:                      # noqa: BLE001 —— 明确失败，不裸抛
        provenance["failure_stage"] = "embed_query"
        return _finish(STATUS_MODEL_UNAVAILABLE, [], [], [],
                       f"查询向量化不可用（本地 embedding 服务不可达）：{e}——不回落云端")

    # ---- 3) 证据层（邻块扩展使用同一受约束正文集合；R1） ----
    source_cache = deps.source_cache or SourceCache(deps.corpus_root)
    all_chunks = getattr(searcher, "body", None)
    provenance["evidence"]["all_chunks_wired"] = all_chunks is not None
    provenance["evidence"]["n_scope_chunks"] = len(all_chunks or [])
    try:
        with _stage(deps, "evidence"):
            spans = evidence_from_question(
                searcher, question, qv, method=constraints["evidence_method"],
                pool=pool, k=top_k, alpha=alpha,
                max_chars=deps.evidence_max_chars, n_seeds=deps.evidence_n_seeds,
                subject=subject, source_cache=source_cache,
                corpus_root=deps.corpus_root)
    except Exception as e:  # EvidenceError 等证据层失败：明确状态，不吞
        provenance["failure_stage"] = "evidence"
        return _finish(STATUS_PARTIAL, [], [], [], f"证据重建失败：{e}")
    if not spans:
        return _finish(STATUS_UNCERTAIN, [], [], [],
                       "检索与证据重建后无证据（候选为空或全部失败），不硬答")

    # ---- 3b) 结果侧复核（下推已生效时通常无命中；防注入/防上游未过滤） ----
    if want_file or book:
        kept_spans: list = []
        for s in spans:
            ok = True
            if want_file and normalize_file(s.file) != want_file:
                scope_info["dropped"].append({"citation_id": s.citation_id,
                                              "file": s.file,
                                              "reason": "file_constraint"})
                ok = False
            elif book and s.book != book:
                scope_info["dropped"].append({"citation_id": s.citation_id,
                                              "file": s.file,
                                              "reason": "book_constraint"})
                ok = False
            if ok:
                kept_spans.append(s)
        spans = kept_spans
        if not spans:
            return _finish(STATUS_UNCERTAIN, [], [], [],
                           "全部证据落在 file/book 约束之外（约束未命中），不硬答")

    # ---- 3c) P11 影子候选门禁（**默认不注入 → 本块整体跳过**）----
    # 顺序：因素 A（来源过滤：不可核验/非正文区间出局）→ 因素 B（p8h-suff-v1 充分性）。
    # 在**证据包装配之前**执行：被丢弃的区间不会进提示词、也不可能被引用。
    # 全部被丢弃 → 结构化降级（uncertain），且**不发布任何引用**（evidence 传空）。
    if deps.candidate_id or deps.evidence_source_filter or deps.evidence_sufficiency:
        from app.services.rag_engine.llm.sufficiency import run_candidate_gate
        try:
            with _stage(deps, "evidence_gate"):
                gate = run_candidate_gate(
                    question,
                    [{"citation_id": s.citation_id, "file": s.file,
                      "char_span": list(s.char_span), "text": s.text} for s in spans],
                    deps.region_verifier,
                    source_cfg=deps.evidence_source_filter,
                    suff_cfg=deps.evidence_sufficiency)
        except Exception as e:                  # noqa: BLE001 —— 门禁自身失败不得静默放行
            provenance["failure_stage"] = "evidence_gate"
            return _finish(STATUS_PARTIAL, [], [], [],
                           f"候选门禁执行失败（{type(e).__name__}）：{e}——保守降级，"
                           f"不发布未经判定的引用")
        src_dec = gate.source
        suff_dec = gate.sufficiency
        provenance["evidence_gate"] = {
            "candidate_id": deps.candidate_id,
            "status": gate.status,
            "reason": gate.reason,
            "n_in": len(spans),
            "n_kept": len(gate.keep_ids),
            "n_dropped": len(spans) - len(gate.keep_ids),
            "source_filter": (None if src_dec is None else {
                "version": src_dec.version,
                "status": src_dec.status,
                "n_kept": len(src_dec.keep_ids),
                "n_dropped": len(src_dec.dropped),
                "dropped": src_dec.dropped,
                "reasons": src_dec.reasons,
            }),
            "sufficiency": (None if suff_dec is None else {
                "version": suff_dec.version,
                "status": suff_dec.status,
                "min_overlap": getattr(deps.evidence_sufficiency, "min_overlap", None),
                "keep_citation_ids": list(suff_dec.keep_citation_ids),
                "dropped_citation_ids": list(suff_dec.dropped_citation_ids),
                "reason": suff_dec.reason,
            }),
            "published_citations": bool(gate.status == "pass" and gate.keep_ids),
            "note": ("候选路径（影子）：不改变默认可执行路径；门禁丢弃逐条记台账，"
                     "全部丢弃时不发布任何引用"),
        }
        if not gate.keep_ids:
            return _finish(STATUS_UNCERTAIN, [], [], [],
                           f"[候选 {deps.candidate_id or '（未命名）'}] {gate.reason}")
        keep_set = set(gate.keep_ids)
        spans = [s for s in spans if s.citation_id in keep_set]
        provenance["evidence"]["gate_dropped_citation_ids"] = sorted(
            {str(d.get("citation_id")) for d in (src_dec.dropped if src_dec else [])}
            | set(suff_dec.dropped_citation_ids if suff_dec else []))
    spans_by_id = {s.citation_id: s for s in spans}

    # ---- 4) 证据包装配 + 完整上下文预算（R5） ----
    input_limit = input_token_limit(
        num_ctx=cfg["num_ctx"], num_predict=cfg["num_predict"],
        safety_margin_tokens=budget_cfg["safety_margin_tokens"])
    counter, counter_reason = resolve_counter(
        model_manifest_digest=cfg.get("expected_manifest_digest"),
        vocab_path=deps.tokenizer_vocab_path)
    # 计数口径（P10 运行依赖收口）：`context_budget.counting` **只能来自实际测量**。
    # 旧实现此处按 `counter is not None` 直接写 `method=gguf_bpe/exact=True`：权重词表在、
    # 但 chat template 渲染不可用（典型：缺 jinja2）时，实际测量已退回 estimate，
    # 这一块却仍宣称精确 → 任何读该字段的消费方会把"输入完整性"误读为 PASS（fail-open）。
    # 现在先写"未测量"（exact 恒 False），测量后再按实际结果覆盖。
    provenance["context_budget"]["counting"] = {
        "method": None,                     # 未测量：不得预声明
        "exact": False,
        "reason": counter_reason,
        "vocab_source": (counter.to_dict() if counter is not None else None),
        "measured": False,
    }

    def _record_counting(plan_used: BudgetPlan, *, stage: str) -> None:
        """把**实际生效**的计数口径写进 provenance（fail-closed：只有 exact 才可为真）。"""
        provenance["context_budget"]["counting"] = {
            "method": plan_used.counting_method,        # "gguf_bpe" | "estimate"
            "exact": bool(plan_used.counting_exact),
            "reason": plan_used.counting_reason,
            "vocab_source": plan_used.counting_source or None,
            "measured": True,
            "stage": stage,
        }
    if input_limit <= 0:
        raise GenerationConfigError(
            f"num_ctx={cfg['num_ctx']} 放不下 num_predict={cfg['num_predict']} + "
            f"安全余量 {budget_cfg['safety_margin_tokens']}")
    pack_budget = min(int(cfg["evidence_pack_max_tokens"]), input_limit)
    overhead = budget_cfg["template_overhead_tokens"]

    def _plan(cands: list[EvidenceSpan]) -> tuple[BudgetPlan, Any, list[dict]]:
        sel = select_evidence(cands, pack_budget, chars_per_token_lower=cpt)
        msgs = build_messages(question, sel.pack_text, constraints,
                              answer_policy=deps.answer_policy)
        # 计数口径（P8C-0.3）：优先与已安装权重同词表+同模板的**精确**计数；
        # 不可用时退回估算并如实标注 estimation_only（不声称输入完整）。
        measured = measure_messages_auto(
            msgs, chars_per_token_lower=cpt, template_overhead_tokens=overhead,
            counter=counter, counter_reason=counter_reason)
        plan = BudgetPlan(
            num_ctx=int(cfg["num_ctx"]), num_predict=int(cfg["num_predict"]),
            safety_margin_tokens=budget_cfg["safety_margin_tokens"],
            template_overhead_tokens=overhead, chars_per_token_lower=cpt,
            input_limit=input_limit, est_input_tokens=measured.n_tokens,
            n_messages=len(msgs),
            prompt_chars=sum(len(m["content"]) for m in msgs),
            evidence_span_ids=list(sel.used_ids),
            evidence_chars=sel.chars_used,
            dropped_span_ids=[d["citation_id"] for d in sel.dropped],
            drops_by_budget=list(sel.dropped),
            fits=measured.n_tokens <= input_limit,
            counting_method=measured.method, counting_exact=measured.exact,
            counting_source=measured.source, counting_reason=measured.reason)
        return plan, sel, msgs

    remaining = list(spans)
    with _stage(deps, "plan"):
        plan, sel, messages = _plan(remaining)
    # 计数口径按**实际测量结果**落盘（P10）：精确不可用时即为 estimate + exact=False。
    _record_counting(plan, stage="first_round")
    # 首轮实测钩子（下方修复分支的**任何早退**都必须先调用它，否则首轮 usage 会丢）
    first_plan: BudgetPlan = plan
    observed_first: dict | None = None

    def _flush_first_observation() -> None:
        nonlocal observed_first
        if observed_first is not None or not (usage_first or raw_text is not None):
            return
        observed_first = _observe(first_plan, usage_first)
        provenance["generation"]["observed_first"] = observed_first
        provenance["generation"]["observed"] = observed_first
        if ledger is not None:
            ledger.note_observed(observed_first)

    def _observe(plan_used: BudgetPlan, usage_used: dict) -> dict:
        out = check_usage(usage=usage_used, num_ctx=int(cfg["num_ctx"]),
                          num_predict=int(cfg["num_predict"]),
                          est_input_tokens=plan_used.est_input_tokens,
                          prompt_chars=plan_used.prompt_chars,
                          input_limit=input_limit)
        pe = out.get("prompt_eval_count")
        exact = plan_used.counting_exact
        out["counting_method"] = plan_used.counting_method
        out["input_integrity"] = ("verified_exact_count" if exact
                                 else "not_verified_estimation_only")
        if exact and isinstance(pe, int):
            out["non_truncation_check"] = (
                "exact_count_matches_runtime" if pe == plan_used.est_input_tokens
                else "MISMATCH")
        return out

    if not sel.used_ids:
        return _finish(STATUS_UNCERTAIN, spans, [], [],
                       f"证据存在但均超出证据包预算（budget={pack_budget}），"
                       f"无法生成讲解，不硬答")
    # 预算不足时按相关度从低到高整条剔除证据（不截断原文、不动题面）
    while plan.est_input_tokens > input_limit:
        victims = [cid for cid in reversed(sel.selection_order)
                   if cid in set(sel.used_ids)]
        if not victims:
            provenance["context_budget"]["refused"] = True
            provenance["context_budget"]["refusal_reason"] = (
                f"题面与提示词本身约 {plan.est_input_tokens} tokens > 可用输入 "
                f"{input_limit}（num_ctx={cfg['num_ctx']}, num_predict="
                f"{cfg['num_predict']}, 安全余量="
                f"{budget_cfg['safety_margin_tokens']}）——拒绝发送，未调用生成器")
            provenance["failure_stage"] = "context_budget"
            provenance["context_budget"]["first_round"] = plan.to_dict()
            return _finish(STATUS_PARTIAL, spans, [], [],
                           provenance["context_budget"]["refusal_reason"])
        victim = victims[0]
        provenance["evidence_pack"]["budget_drops"].append({
            "citation_id": victim,
            "reason": "完整上下文预算不足：按相关度从低到高整条剔除（不截断原文）",
        })
        remaining = [s for s in remaining if s.citation_id != victim]
        plan, sel, messages = _plan(remaining)
        if not sel.used_ids:
            provenance["context_budget"]["refused"] = True
            provenance["context_budget"]["refusal_reason"] = (
                "剔除全部证据后仍超出可用输入预算——拒绝发送，未调用生成器")
            provenance["failure_stage"] = "context_budget"
            provenance["context_budget"]["first_round"] = plan.to_dict()
            return _finish(STATUS_PARTIAL, spans, [], [],
                           provenance["context_budget"]["refusal_reason"])
    provenance["context_budget"]["first_round"] = plan.to_dict()
    if deps.record_coverage_signal:
        provenance["evidence_sufficiency"] = _coverage_signal(
            question, sel.pack_text, sel.used_ids)
    provenance["evidence_pack"].update({
        "token_budget": pack_budget,
        "used_span_ids": list(sel.used_ids),
        "dropped": list(sel.dropped),
        "selection_order": list(sel.selection_order),
        "selection_note": sel.selection_note,
    })

    # ---- 5) 生成（缓存 → 真实/mock 调用；坏 JSON/schema 最多一次有界修复） ----
    cache = _cache_for(deps, cfg)
    identity_payload = {
        "question": question, "constraints": constraints,
        # 键覆盖**实际进包**的证据（模型看到的就是这些），顺序参与
        "evidence": [(s.citation_id, span_text_sha256(s)) for s in remaining
                     if s.citation_id in set(sel.used_ids)],
        "prompt_version": effective_prompt_version,
        "schema_version": cfg["schema_version"],
        "answer_policy": deps.answer_policy,
        "result_policy": CACHE_RESULT_POLICY,
        "provider": gen_identity["provider"], "model_id": gen_identity["model_id"],
        "manifest_digest": getattr(deps.generator, "expected_manifest_digest",
                                   None) if not getattr(deps.generator, "is_mock", False)
        else None,
        "num_ctx": cfg["num_ctx"], "temperature": cfg["temperature"],
        "seed": cfg["seed"], "num_predict": cfg["num_predict"],
    }
    # P11 影子候选：键里**额外**带候选 ID 与索引规格（默认路径不传 → 键载荷不变）。
    # 没有它，候选 A 会直接复用 A0 缓存（候选之间也不可分）——登记要求键必须区分候选。
    if deps.candidate_id:
        identity_payload["candidate_id"] = str(deps.candidate_id)
        identity_payload["index_spec"] = (index_identity or {}).get("index_spec")
    raw_text: str | None = None
    usage: dict = {}
    usage_first: dict = {}          # 首轮实测（缓存命中时为缓存记录里的 usage）
    usage_repair: dict | None = None     # 修复轮实测
    repair_plan: BudgetPlan | None = None
    cache_hit = False
    repair_used = 0
    parsed: dict | None = None
    parse_error: str | None = None
    gen = deps.generator
    is_mock = bool(getattr(gen, "is_mock", False))

    def _record_call(usage_dict: dict, *, repair: bool, completed: bool) -> None:
        """记账（R8）：尝试请求 / 实际完成 / 推理采用分开计，失败 token 记 unknown。"""
        if ledger is None:
            return
        if completed:
            ledger.note_request(usage_dict, repair=repair)
        else:
            ledger.note_attempt(repair=repair)

    def _generate(msgs: list[dict], *, repair: bool):
        """一次生成调用；返回 (raw, usage) 或抛出。取消也如实记账（R8）。"""
        try:
            raw, use = gen.chat(msgs, schema=OUTPUT_SCHEMA,
                                num_ctx=cfg["num_ctx"],
                                temperature=cfg["temperature"], seed=cfg["seed"],
                                num_predict=cfg["num_predict"],
                                purpose=("explain_chat_repair" if repair
                                         else "explain_chat"),
                                cancel_token=getattr(gen, "cancel_token", None))
        except GenerationCancelled as e:
            completed = bool(getattr(e, "completed", False))
            if completed:
                # 取消发生在推理返回之后：这次本地调用**已经发生**，不能漏计
                provenance["local_inference_count"] += 1
                _record_call({}, repair=repair, completed=True)
                if ledger is not None:
                    ledger.note_error("CANCELLED_AFTER_INFERENCE")
            else:
                _record_call({}, repair=repair, completed=False)
                if ledger is not None:
                    ledger.note_error("CANCELLED")
            raise
        if not is_mock:
            provenance["local_inference_count"] += 1
            if deps.usage_summary is not None:
                deps.usage_summary(use)
        _record_call(use, repair=repair, completed=True)
        return raw, use

    if cache is not None:
        key = GenerationCache.make_key(GenerationCache.build_key_payload(**identity_payload))
        hit = cache.get(key)
        if hit is not None:
            cache_hit = True
            provenance["cache"]["hit"] = True
            raw_text = str(hit["raw_response"])
            usage = dict(hit.get("usage") or {})
            usage.setdefault("latency_ms", 0)
            # 缓存命中：缓存记录里的 usage 就是**首轮**那一次调用的实测
            # （pack/提示由同一组证据装配，故与首轮计划配对）
            usage_first = dict(usage)
            _flush_first_observation()   # 缓存命中同样要留下配对实测（与首轮计划配对）
            parsed, parse_error = _parse_and_check(raw_text, sel.used_ids)
            if ledger is not None:
                ledger.note_cache(True)
    if parsed is None and raw_text is None:
        try:
            with _stage(deps, "generate"):
                raw_text, usage = _generate(messages, repair=False)
            usage_first = dict(usage)
        except GenerationCancelled:
            provenance["context_budget"]["first_round"] = plan.to_dict()
            return _finish(STATUS_PARTIAL, spans, [], [],
                           "生成被取消（结果不采用；已校验定位与原文保留）")
        except GenerationTimeout as e:
            return _finish(STATUS_PARTIAL, spans, [], [], f"生成超时：{e}")
        except ModelUnavailable as e:
            return _finish(STATUS_MODEL_UNAVAILABLE, spans, [], [],
                           f"本地生成模型不可用（不回落云端）：{e}")
        except GenerationError as e:
            return _finish(STATUS_PARTIAL, spans, [], [], f"生成失败：{e}")
        provenance["generation"]["manifest_digest"] = usage.get("manifest_digest")
        _flush_first_observation()      # 首轮 usage 先落盘：修复分支的任何早退都不得丢它
        parsed, parse_error = _parse_and_check(raw_text, sel.used_ids)
        # ---- 有界修复：JSON/schema 不合格最多一次（错误信息回灌重试） ----
        if parsed is None and int(cfg["max_repair_attempts"]) > 0:
            repair_messages = list(messages) + [
                {"role": "assistant", "content": raw_text or ""},
                {"role": "user", "content":
                    f"上面的输出不合格（错误：{parse_error}）。"
                    "请重新只输出符合 schema 的 JSON，不要输出其他文字。"},
            ]
            repair_measured = measure_messages_auto(
                repair_messages, chars_per_token_lower=cpt,
                template_overhead_tokens=overhead, counter=counter,
                counter_reason=counter_reason)
            repair_est = repair_measured.n_tokens
            repair_plan = BudgetPlan(
                num_ctx=int(cfg["num_ctx"]), num_predict=int(cfg["num_predict"]),
                safety_margin_tokens=budget_cfg["safety_margin_tokens"],
                template_overhead_tokens=overhead, chars_per_token_lower=cpt,
                input_limit=input_limit, est_input_tokens=repair_est,
                n_messages=len(repair_messages),
                prompt_chars=sum(len(m["content"]) for m in repair_messages),
                evidence_span_ids=list(sel.used_ids),
                fits=repair_est <= input_limit,
                counting_method=repair_measured.method,
                counting_exact=repair_measured.exact,
                counting_source=repair_measured.source,
                counting_reason=repair_measured.reason)
            provenance["context_budget"]["repair_round"] = repair_plan.to_dict()
            # 顶部口径跟随**最后一次实际测量**（修复轮）；两轮各自的口径仍分别保留在
            # first_round/repair_round 的 counting 块内（不覆盖历史）。
            _record_counting(repair_plan, stage="repair_round")
            if repair_est > input_limit:
                provenance["repair_skipped_reason"] = (
                    f"修复轮预算不足（估算 {repair_est} > 可用 {input_limit}）"
                    "——不发送修复请求（不截断题面/引用）")
                return _finish(STATUS_PARTIAL, spans, [], [],
                               f"模型输出非合法 JSON（{parse_error}）且修复轮超出上下文"
                               f"预算；保留定位与原文")
            repair_used = 1
            try:
                with _stage(deps, "generate_repair"):
                    raw2, usage2 = _generate(repair_messages, repair=True)
            except GenerationCancelled:
                return _finish(STATUS_PARTIAL, spans, [], [],
                               "修复请求被取消（已校验定位与原文保留）")
            except GenerationTimeout as e:
                return _finish(STATUS_PARTIAL, spans, [], [],
                               f"修复请求超时：{e}")
            except ModelUnavailable as e:
                return _finish(STATUS_MODEL_UNAVAILABLE, spans, [], [],
                               f"修复请求时本地模型不可用（不回落云端）：{e}")
            except GenerationError as e:
                return _finish(STATUS_PARTIAL, spans, [], [],
                               f"修复请求失败：{e}")
            raw_text = raw2
            usage_first = usage_first or {}
            usage_repair = dict(usage2)
            usage = usage2
            provenance["generation"]["manifest_digest"] = usage2.get("manifest_digest")
            provenance["repair_attempts"] = repair_used
            parsed, parse_error = _parse_and_check(raw_text, sel.used_ids)
    elif parsed is None:
        provenance["repair_attempts"] = 0        # 缓存命中但内容不合格：不重写缓存
    if usage_repair is not None:
        observed_repair = _observe(repair_plan, usage_repair)
        provenance["generation"]["observed_repair"] = observed_repair
        provenance["generation"]["observed"] = observed_repair
        if ledger is not None:
            ledger.note_observed(observed_repair)
    if parsed is None:
        return _finish(STATUS_PARTIAL, spans, [], [],
                       f"模型输出两次均非合法 JSON 或不符合 schema（{parse_error}）；"
                       f"保留定位与原文")

    def _finish_generated(status: str, items: list[ExplanationItem],
                          reason: str | None) -> LocateResult:
        """复验后缓存完整语义结果，包括拒答；技术/引用失败不落成功缓存。"""
        result = _finish(status, spans, [], items, reason)
        if (cache is None or cache_hit or parse_error is not None
                or result.status not in (STATUS_OK, STATUS_UNCERTAIN)
                or provenance["citation_validation"]["release"]["failures"]):
            return result
        # uncertain 可以带 explanations（不会公开）；其中有坏引用时同样不得
        # 作为完整有效响应缓存。源复验共用 release，缓存命中仍逐次重读源文件。
        _, rejected, _, _ = _validate_and_backfill(parsed, spans_by_id, release)
        if rejected:
            return result
        key = GenerationCache.make_key(GenerationCache.build_key_payload(**identity_payload))
        try:
            cache.put(key, identity_payload,
                      output={"knowledge_points": parsed.get("knowledge_points", []),
                              "explanations": [
                                  {k: v for k, v in e.items()
                                   if k in ("point", "citation_ids", "explanation",
                                            "supplement")}
                                  for e in parsed.get("explanations", [])],
                              "uncertain": parsed["uncertain"]},
                      raw_response=str(raw_text or ""), usage=usage, mock=is_mock)
        except OSError as e:
            # 缓存不可写不应丢掉已经校验的结果；明确报告未能保证后续复放。
            provenance["cache"]["write_error"] = f"{type(e).__name__}: {e}"
        return result

    # ---- 6) 模型自报 uncertain / 空 explanations 的显式语义 ----
    if parsed["uncertain"]:
        reason = "模型自报证据不足（uncertain=true），不硬答"
        return _finish_generated(STATUS_UNCERTAIN, [], reason)
    if not parsed["explanations"]:
        return _finish_generated(
            STATUS_UNCERTAIN, [],
            "模型输出空 explanations 且未标记 uncertain——无解释可放行，"
            "不硬答（见 SCHEMA_FIELD_MEANINGS）")

    # ---- 7) 引用校验与回填（复验是放行唯一依据；R2 整条拒绝） ----
    items, dropped_reasons, unknown_total, dedup_notes = _validate_and_backfill(
        parsed, spans_by_id, release)
    provenance["citation_validation"]["used"] = sorted(
        {c for it in items for c in it.citation_ids})
    failed_ids = sorted({rid for it in parsed.get("explanations", [])
                         for rid in it.get("citation_ids", [])
                         if rid not in set(provenance["citation_validation"]["used"])})
    provenance["citation_validation"]["failed"] = failed_ids
    provenance["citation_validation"]["dropped_explanations"] = list(dropped_reasons)
    provenance["citation_validation"]["unknown_citation_ids"] = sorted(
        {u for e in parsed.get("explanations", [])
         for u in e.get("unknown_citation_ids", [])})
    provenance["citation_validation"]["deduplicated"] = list(dedup_notes)
    provenance["citation_validation"]["n_unknown_ids_total"] = unknown_total
    if not items:
        return _finish(STATUS_INVALID_CITATION, spans, [], [],
                       "全部解释的引用校验失败（未知/未入包 citation_id 或证据复验不过）"
                       "——错误引用禁止展示")
    if dropped_reasons:
        status = STATUS_PARTIAL
        reason = f"{len(dropped_reasons)} 条解释因引用校验失败被丢弃，保留通过的部分"
    else:
        status = STATUS_OK
        reason = None

    # ---- 8) 完整有效的回答/拒答均缓存；partial/错误/取消不写 ----
    return _finish_generated(status, items, reason)


def _cache_for(deps: ServiceDeps, cfg: dict) -> GenerationCache | None:
    if not deps.cache_dir:
        return None
    gen = deps.generator
    provider = str(getattr(gen, "provider", "unknown"))
    model_id = str(getattr(gen, "model_id", "unknown/model"))
    # mock 与真实物理隔离：命名空间含 provider + model_id（mock 模型的 id 以
    # mock/ 开头），且真实 Ollama 生成器的 model_ns 含具体模型名。
    ns = f"{provider}_{model_id}".replace("/", "_").replace(":", "_")
    return GenerationCache(deps.cache_dir, ns, int(cfg["cache_contract_version"]))
