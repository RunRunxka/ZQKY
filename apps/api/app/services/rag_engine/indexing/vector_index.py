"""embedding 客户端工厂与向量索引（Phase 4 / P4-LOCAL）。

双 provider（可选模型，D22）：
  - zhipu        智谱 embedding-3 REST（原实现，云端付费）
  - local-ollama 本地 Ollama（/api/embed，零 API 成本，模型维度固定）

三不变量（docs/SCHEMA.md §五）：
  - 单请求条数 ≤ max_batch；单条 ≤3072 tokens（切分层 ≤1000 字符保证，另有守卫）
  - 指数退避重试（限流/过载/网络），不可重试错误快速失败
  - 密钥只从环境变量读取；本地 provider 无需密钥

【模型守卫——本文件最重要的安全设计】
不同 embedding 模型的向量空间互不可比。因此：
  - 索引按 model_id 命名空间隔离（index/<model_ns>/）
  - load_index 校验 index_meta.model_id 与期望一致，不一致拒绝加载
  - 查询向量缓存同样在 model_ns 内
缺少守卫时"换模型继续用旧索引"不会报错、只会静默产出垃圾检索结果。
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import numpy as np

from app.services.rag_engine.contracts import Chunk
from app.services.rag_engine.retrieval.execution_policy import (POLICY_CACHE_ONLY, POLICY_CLOUD_ALLOWED,
                                            POLICY_LOCAL_ONLY, PolicyViolation,
                                            assert_endpoint_allowed,
                                            assert_no_redirect_follow,
                                            assert_provider_allowed,
                                            check_local_model_digest,
                                            normalize_policy)

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CFG = _ROOT / "configs" / "models.yaml"
MAX_TEXT_CHARS = 2400   # 3072 tokens 的保守代理上界（1 字 ≈ 1–1.5 token）；切分层上限 1000

FATAL_CODES_ZHIPU = {"1113"}          # 余额不足——重试无意义

NETWORK_MODES = ("auto", "cache-only")


class NetworkBlockedError(RuntimeError):
    """cache-only 网络策略的客户端层硬闸：在任何 HTTP 请求发出之前抛出。

    两层防线中的第二层（第一层是 run_eval 的查询缓存校验）：即使调用方
    绕过 CLI 直接调用 embed() / _post_one()，也不会发出任何网络请求。
    例外：指向 127.0.0.1 的本地推理同样被拦——cache-only 语义是"本批零
    外呼"，缓存命中时不应有任何 embed 调用。
    """


def load_model_config(path: str | Path | None = None) -> dict:
    import yaml
    return yaml.safe_load(Path(path or _DEFAULT_CFG).read_text(encoding="utf-8"))


def model_ns(model_id: str) -> str:
    """model_id -> 目录安全的命名空间名。"""
    return model_id.replace("/", "_").replace(":", "_")


def _load_dotenv(path: str | Path = _ROOT / ".env") -> None:
    """把 .env 注入环境变量（仅 setdefault）。绝不打印/记录任何值。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


class BaseEmbeddingClient:
    """双 provider 共用：分批/守卫/台账。子类实现 _post_one。"""

    provider: str = "?"

    def __init__(self, spec: dict, usage_log: str | Path):
        self.spec = spec
        self.model = spec["model"]
        self.model_id = spec["model_id"]
        self.model_ns = model_ns(self.model_id)
        self.endpoint = spec["endpoint"]
        self.dims = [int(d) for d in spec["dims"]]
        self.price = float(spec.get("price_per_million_tokens", 0.0))
        self.max_batch = int(spec["max_batch"])
        self.timeout = float(spec["timeout_seconds"])
        self.retry = spec["retry"]
        self.usage_log = Path(usage_log)
        self.network_mode = "auto"              # "auto" = 历史行为；"cache-only" = 禁止任何网络请求
        self._client = None                     # 惰性创建 httpx.Client

    # ---- 子类实现 ----

    def _post_one(self, batch: list[str], dim: int, purpose: str) -> tuple[list[list[float]], int]:
        """单批请求（含重试）。返回 (embeddings, tokens)。"""
        raise NotImplementedError

    # ---- 共用 ----

    def set_network_mode(self, mode: str) -> None:
        """设置网络策略（P5A-GUARD）。"cache-only" = 任何 embed 调用立即抛错。

        必须在发出任何请求之前设置；对已存在的 client 实例同样生效。
        """
        if mode not in NETWORK_MODES:
            raise ValueError(f"未知网络模式: {mode!r}（可选：{NETWORK_MODES}）")
        self.network_mode = mode

    def _assert_network_allowed(self, dim: int, purpose: str) -> None:
        """网络硬闸：cache-only 下在任何 HTTP 请求发出之前抛 NetworkBlockedError。"""
        if self.network_mode == "cache-only":
            raise NetworkBlockedError(
                f"cache-only 模式禁止任何网络请求：provider={self.provider} "
                f"model_id={self.model_id} dim={dim} purpose={purpose!r}。"
                f"查询向量缓存缺失/指纹或模型不符时应先重建缓存"
                f"（run_eval --embedding-mode auto），或在网络可用环境操作")

    def embed(self, texts: list[str], dim: int, purpose: str) -> np.ndarray:
        """批量向量化，返回 (n, dim) float32。超过 max_batch 自动分批。

        cache-only 模式下第一行即断言网络策略——参数校验之后、任何 HTTP 之前。
        """
        if dim not in self.dims:
            raise ValueError(f"维度 {dim} 不在 {self.provider}:{self.model} 允许列表 {self.dims}")
        for i, t in enumerate(texts):
            if len(t) > MAX_TEXT_CHARS:
                raise ValueError(f"text[{i}] 长 {len(t)} 字符，超保守上界 {MAX_TEXT_CHARS}（3072 tokens 守卫）")
        self._assert_network_allowed(dim, purpose)
        out: list[list[float]] = []
        for start in range(0, len(texts), self.max_batch):
            batch = texts[start:start + self.max_batch]
            embs, _tokens = self._post_one(batch, dim, purpose)
            if len(embs) != len(batch):
                raise RuntimeError(f"返回条数 {len(embs)} != 请求 {len(batch)}")
            out.extend(embs)
        return np.asarray(out, dtype=np.float32)

    def check(self) -> dict:
        """连通性验证：向量化 2 条短文本，返回规格与用量。"""
        dim = 1024 if 1024 in self.dims else self.dims[0]
        t0 = time.monotonic()
        vecs = self.embed(["连通性验证：集合的概念", "连通性验证：曲线运动"], dim=dim,
                          purpose="connectivity_check")
        return {"ok": True, "provider": self.provider, "model": self.model,
                "model_id": self.model_id, "dim": int(vecs.shape[1]),
                "shape": list(vecs.shape),
                "latency_ms": int((time.monotonic() - t0) * 1000)}

    def _log_usage(self, purpose: str, dim: int | None, n_texts: int, tokens: int,
                   latency_ms: int = 0, retries: int = 0, ok: bool = True,
                   error_code: str | None = None) -> None:
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": purpose,
            "provider": self.provider,
            "model": self.model,
            "model_id": self.model_id,
            "dim": dim,
            "n_texts": n_texts,
            "total_tokens": tokens,
            "est_cost_yuan": round(tokens / 1e6 * self.price, 6),
            "latency_ms": latency_ms,
            "retries": retries,
            "ok": ok,
            "error_code": error_code,
        }
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.usage_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _sleep_backoff(self, retries: int) -> None:
        base = float(self.retry["base_sleep_seconds"])
        time.sleep(base * (2 ** retries) * (1 + random.random() * 0.1))


class ZhipuEmbeddingClient(BaseEmbeddingClient):
    """智谱 embedding-3 REST（原 EmbeddingClient）。"""

    provider = "zhipu"

    def __init__(self, spec: dict, usage_log: str | Path, network_mode: str = "auto",
                 execution_policy: str | None = None):
        super().__init__(spec, usage_log)
        # 执行策略校验（P5-LOCAL）：在任何 I/O 与密钥读取之前。
        #  - local-only：云端 provider 立即拒绝，错误信息给出逃生口
        #    （--execution-policy cloud-allowed），不做静默降级；
        #  - cache-only：构造放行（P5A 语义——客户端可建、embed 全拦），
        #    provider/端点断言不适用，网络由 network_mode 硬闸兜底；
        #  - cloud-allowed：历史行为。
        self.execution_policy = normalize_policy(execution_policy)
        if self.execution_policy == POLICY_LOCAL_ONLY:
            assert_provider_allowed(self.provider, self.execution_policy,
                                    name=f"embedding:{self.model_id}")
        # 密钥检查服从网络策略（P5A-GUARD）：cache-only 下缓存命中即零请求，
        # 不需要密钥，缺 ZAI_API_KEY 不得阻塞运行；auto 保持历史行为（构造即校验）。
        self.set_network_mode(network_mode)
        if self.network_mode == "cache-only":
            self._api_key = None
            return
        _load_dotenv()
        self._api_key = os.environ.get("ZAI_API_KEY")
        if not self._api_key:
            raise RuntimeError("缺少 ZAI_API_KEY 环境变量（.env 或 shell 注入），无法调用 embedding API")

    def _post_one(self, batch: list[str], dim: int, purpose: str) -> tuple[list[list[float]], int]:
        self._assert_network_allowed(dim, purpose)   # 硬闸兜底：绕过 embed 直调本方法同样拦截
        import httpx
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        max_retries = int(self.retry["max_retries"])
        retries = 0
        payload = {"model": self.model, "input": batch, "dimensions": dim}
        while True:
            t0 = time.monotonic()
            transport_err: Exception | None = None
            try:
                resp = self._client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            except httpx.TransportError as e:      # 网络层错误：可重试
                transport_err = e
            if transport_err is not None:
                if retries >= max_retries:
                    self._log_usage(purpose, dim, len(batch), 0, retries=retries, ok=False,
                                    error_code="TRANSPORT")
                    raise RuntimeError(f"embedding API 网络错误（重试 {retries} 次后放弃）: {transport_err}")
                self._sleep_backoff(retries)
                retries += 1
                continue
            latency_ms = int((time.monotonic() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                rows = sorted(data["data"], key=lambda d: d["index"])
                tokens = int(data.get("usage", {}).get("total_tokens") or 0)
                self._log_usage(purpose, dim, len(batch), tokens, latency_ms, retries)
                return [r["embedding"] for r in rows], tokens
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            code = body.get("error", {}).get("code")
            retryable = (str(code) not in FATAL_CODES_ZHIPU
                         and (resp.status_code in self.retry["retryable_http"]
                              or str(code) in {str(c) for c in self.retry["retryable_codes"]}))
            if not retryable:
                self._log_usage(purpose, dim, len(batch), 0, latency_ms, retries, ok=False,
                                error_code=str(code))
                hint = "（账户余额不足，请充值后重跑；已完成部分不受影响）" if str(code) == "1113" else ""
                raise RuntimeError(f"embedding API 失败: HTTP {resp.status_code} code={code} "
                                   f"body={str(body)[:200]}{hint}")
            if retries >= max_retries:
                self._log_usage(purpose, dim, len(batch), 0, latency_ms, retries, ok=False,
                                error_code=str(code))
                raise RuntimeError(f"embedding API 失败（重试 {retries} 次后放弃）: "
                                   f"HTTP {resp.status_code} code={code} body={str(body)[:200]}")
            self._sleep_backoff(retries)
            retries += 1


class OllamaEmbeddingClient(BaseEmbeddingClient):
    """本地 Ollama（/api/embed）。零 API 成本；模型维度固定。

    执行策略（P5-LOCAL）：构造时校验——local-only 只允许回环端点；
    cache-only 下连本机回环也一并拒绝（"本批零外呼"，语义与 P5A 一致）。
    """

    provider = "local-ollama"

    def __init__(self, spec: dict, usage_log: str | Path, execution_policy: str | None = None):
        super().__init__(spec, usage_log)
        self.execution_policy = normalize_policy(execution_policy)
        if self.execution_policy == POLICY_LOCAL_ONLY:
            # local-ollama 允许；端点必须是显式回环 URL（userinfo/远程主机在此被拒）
            assert_provider_allowed(self.provider, self.execution_policy,
                                    name=f"embedding:{self.model_id}")
            assert_endpoint_allowed(self.endpoint, self.execution_policy,
                                    name=f"embedding:{self.model_id}")
        if self.execution_policy == POLICY_CACHE_ONLY:
            # 与 zhipu 同语义：cache-only 禁止一切网络（含本机回环 Ollama），
            # 构造放行、embed()/_post_one() 的硬闸生效（P5A 语义不变）。
            self.set_network_mode("cache-only")

    def _make_client(self):
        """本地请求不读取环境代理、不跟随重定向，防止回环数据经代理离机。"""
        import httpx
        self._client = httpx.Client(timeout=self.timeout, trust_env=False)
        assert_no_redirect_follow(
            bool(getattr(self._client, "follow_redirects", False)), self.execution_policy)

    def _post_one(self, batch: list[str], dim: int, purpose: str) -> tuple[list[list[float]], int]:
        import httpx
        self._assert_network_allowed(dim, purpose)   # 硬闸兜底：本地端点同样属于外呼
        if self._client is None:
            self._make_client()
        max_retries = int(self.retry["max_retries"])
        retries = 0
        payload = {"model": self.model, "input": batch}
        while True:
            t0 = time.monotonic()
            transport_err: Exception | None = None
            try:
                resp = self._client.post(self.endpoint, json=payload)
            except httpx.TransportError as e:
                # 服务未启动/重启中——可重试
                transport_err = e
            if transport_err is not None:
                if retries >= max_retries:
                    self._log_usage(purpose, dim, len(batch), 0, retries=retries, ok=False,
                                    error_code="TRANSPORT")
                    raise RuntimeError(f"Ollama 连接失败（重试 {retries} 次后放弃，"
                                       f"请确认 ollama serve 正在运行）: {transport_err}")
                self._sleep_backoff(retries)
                retries += 1
                continue
            latency_ms = int((time.monotonic() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                embs = data.get("embeddings")
                if not embs:
                    self._log_usage(purpose, dim, len(batch), 0, latency_ms, retries, ok=False,
                                    error_code="NO_EMBEDDINGS")
                    raise RuntimeError(f"Ollama 响应无 embeddings：{str(data)[:200]}")
                tokens = int(data.get("prompt_eval_count") or 0)
                self._log_usage(purpose, dim, len(batch), tokens, latency_ms, retries)
                return embs, tokens
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            msg = str(body.get("error", body))[:160]
            # 404/400 = 模型不存在或请求非法——重试无意义
            fatal = resp.status_code in (400, 404)
            if fatal or retries >= max_retries:
                self._log_usage(purpose, dim, len(batch), 0, latency_ms, retries, ok=False,
                                error_code=f"HTTP{resp.status_code}")
                raise RuntimeError(f"Ollama 请求失败: HTTP {resp.status_code} {msg}")
            self._sleep_backoff(retries)
            retries += 1


# 兼容别名：既有引用（测试/文档）指的就是智谱实现
EmbeddingClient = ZhipuEmbeddingClient


def create_embedding_client(cfg: dict, name: str | None = None,
                            usage_log: str | Path | None = None,
                            network_mode: str = "auto",
                            execution_policy: str | None = None) -> BaseEmbeddingClient:
    """按配置创建 embedding 客户端。

    name 缺省用 cfg["embedding"]["active"]；usage_log 缺省用 cfg["api_usage_log"]。
    本地 provider 的成本记 0，但 tokens/耗时照常入台账。
    network_mode（P5A-GUARD）："auto"（默认，历史行为）或 "cache-only"
    （任何 embed 调用在发出 HTTP 请求之前即抛 NetworkBlockedError）。
    注意：cache-only 下 ZhipuEmbeddingClient 不做密钥校验（缓存命中即零请求）。
    execution_policy（P5-LOCAL）："local-only"（默认）/ "cache-only" / "cloud-allowed"，
    缺省读 cfg["execution"]["policy"]。校验发生在创建任何 httpx 客户端之前
    （失败早于任何 I/O）：
      - local-only：只允许本地类 provider（local-ollama / local-worker），
        端点必须是显式回环 URL；拒绝 zhipu 并提示 --execution-policy cloud-allowed。
      - cache-only：与 P5A 完全一致——不创建可发网络的对象（zhipu 不读密钥、
        local 客户端置 network_mode="cache-only"），embed() 抛 NetworkBlockedError。
      - cloud-allowed：与历史行为一致（zhipu 可用）。
    """
    emb = cfg["embedding"]
    name = name or emb["active"]
    providers = emb.get("providers", {})
    if name not in providers:
        raise ValueError(f"未知 embedding provider: {name!r}（可选：{sorted(providers)}）")
    spec = providers[name]
    usage = usage_log or cfg["api_usage_log"]
    kind = spec["provider"]
    # 策略解析（P5-LOCAL）：显式参数 > cfg["execution"]["policy"] > 旧式 cfg 回落。
    # 旧式 cfg（无 execution 段，如单测注入的 cfg dict）保持 P5 前历史行为
    # （cloud-allowed），保证既有调用方语义不变；真实 configs/models.yaml
    # 已登记 execution.policy: local-only，生产默认严格。
    cfg_policy = (cfg.get("execution") or {}).get("policy")
    if execution_policy is not None:
        policy = normalize_policy(execution_policy)
    elif cfg_policy:
        policy = normalize_policy(cfg_policy)
    else:
        policy = POLICY_CLOUD_ALLOWED   # 旧式配置 = 历史行为（zhipu 可用）
    if policy == POLICY_CACHE_ONLY:
        # 策略级等价：cache-only（无论来自 --execution-policy 还是配置）即
        # network_mode="cache-only"——不读密钥、任何 embed 全拦（P5A 语义）。
        network_mode = "cache-only"
    if kind == "zhipu":
        client: BaseEmbeddingClient = ZhipuEmbeddingClient(spec, usage, network_mode, policy)
    elif kind in ("local", "local-ollama", "ollama"):
        client = OllamaEmbeddingClient(spec, usage, execution_policy=policy)
        if network_mode != "auto":
            # 显式 CLI network_mode 覆盖构造内的设置（P5A 历史行为保留）
            client.set_network_mode(network_mode)
    else:
        raise ValueError(f"未知 provider 类型: {kind!r}")
    return client


def verify_local_ollama(cfg_spec: dict, policy: str) -> dict:
    """本地端点身份核验（P5-LOCAL）：GET tags_endpoint 比对模型名与 digest。

    用 Ollama /api/tags（回环）取模型列表，找到 spec["model"] 对应条目，
    以 check_local_model_digest 与 spec 的 expected_digest 比对：
      - 端点非回环 / 不可达 / 模型不在列表 / digest 不符 → 抛错（绝不静默跳过）；
      - spec 未登记 expected_digest → 只做存在性检查，返回
        identity_verified=False（调用方须在报告里如实记录，不得伪填）。
    返回 {"model", "digest", "identity_verified": bool}。
    """
    policy = normalize_policy(policy)
    tags_endpoint = cfg_spec.get("tags_endpoint")
    if not tags_endpoint:
        raise PolicyViolation(
            f"local-only 身份核验要求 spec 登记 tags_endpoint"
            f"（provider={cfg_spec.get('model_id')!r}）；缺省端点不被信任")
    assert_endpoint_allowed(tags_endpoint, policy, name="tags")
    import httpx
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False, trust_env=False) as cli:
            assert_no_redirect_follow(False, policy)
            resp = cli.get(tags_endpoint)
    except httpx.TransportError as e:
        raise PolicyViolation(
            f"本地身份核验不可达：GET {tags_endpoint} 失败（{e}）。"
            f"请确认 ollama serve 正在运行；不核验身份不得本地推理") from e
    if resp.status_code != 200:
        raise PolicyViolation(f"本地身份核验失败：GET {tags_endpoint} → HTTP {resp.status_code}")
    try:
        models = resp.json().get("models", [])
    except Exception as e:
        raise PolicyViolation(f"本地身份核验失败：/api/tags 响应非预期 JSON（{e}）") from e
    want = cfg_spec.get("model")
    entry = next((m for m in models if str(m.get("model", "")).split(":")[0] == want
                  or m.get("model") == want), None)
    if entry is None:
        names = [str(m.get("model")) for m in models][:5]
        raise PolicyViolation(
            f"本地身份核验失败：Ollama 未加载模型 {want!r}（可用：{names}）。"
            f"请 ollama pull {want} 或修正配置")
    hint = {"model": entry.get("model"),
            "digest": entry.get("digest") or entry.get("model_digest")}
    expected = {"model": want}

    def _norm_digest(s: str) -> str:
        """digest 比对前的规范化：Ollama 回报无 'sha256:' 前缀，登记值可带可不带。"""
        return str(s).removeprefix("sha256:")

    got_raw = str(hint.get("digest") or "")
    if cfg_spec.get("expected_digest"):
        expected["digest"] = cfg_spec["expected_digest"]
    # 双锚点（实测发现，Ollama 0.34.2）：/api/tags 的 digest 是【manifest 文件哈希】
    # （无 sha256: 前缀），配置的 expected_digest 登记的是【权重 blob（image.model
    # 层）digest】——两者语义不同，同为身份锚但不可互换。任一锚点经规范化后匹配
    # 即通过；全部不匹配 → 保留原值交给 check_local_model_digest 抛错（绝不静默跳过）。
    matched_anchor = False
    for anchor in ("expected_digest", "expected_manifest_digest"):
        if cfg_spec.get(anchor) and got_raw \
                and _norm_digest(got_raw) == _norm_digest(cfg_spec[anchor]):
            matched_anchor = True
    if matched_anchor:
        expected.pop("digest", None)   # 锚点已匹配；模型名仍交契约函数照常比对
    check_local_model_digest(hint, expected)
    verified = bool(cfg_spec.get("expected_digest") or cfg_spec.get("expected_manifest_digest"))
    return {"model": hint["model"], "digest": hint.get("digest"),
            "identity_verified": verified}


# ---------------------------------------------------------------- 索引（按模型命名空间隔离）

def save_index(out_dir: str | Path, dim: int, tag: str, vectors: np.ndarray,
               chunk_ids: list[str], chunks_fingerprint: str, client: BaseEmbeddingClient) -> dict:
    """写 <out_dir>/<model_ns>/ 下的 vectors_<dim>_<tag>.npy / chunk_ids / index_meta。"""
    out = Path(out_dir) / client.model_ns
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / f"vectors_{dim}_{tag}.npy", vectors)
    ids_path = out / f"chunk_ids_{dim}_{tag}.json"
    ids_path.write_text(json.dumps(chunk_ids, ensure_ascii=False), encoding="utf-8", newline="\n")
    meta = {
        "dim": dim,
        "model": client.model,
        "model_id": client.model_id,
        "provider": client.provider,
        "chunk_count": len(chunk_ids),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "chunks_fingerprint": chunks_fingerprint,
        "tag": tag,
    }
    (out / f"index_meta_{dim}_{tag}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return meta


def load_index(index_dir: str | Path, model_ns_name: str, dim: int, tag: str,
               expect_chunks_fingerprint: str | None = None,
               expect_model_id: str | None = None) -> tuple[np.ndarray, list[str], dict]:
    """加载 <index_dir>/<model_ns>/ 下的索引；校验 chunks 指纹与模型一致性。

    expect_model_id 不一致时拒绝加载——防止"换模型继续用旧索引"的静默错误。
    """
    d = Path(index_dir) / model_ns_name
    vectors = np.load(d / f"vectors_{dim}_{tag}.npy")
    ids = json.loads((d / f"chunk_ids_{dim}_{tag}.json").read_text(encoding="utf-8"))
    meta = json.loads((d / f"index_meta_{dim}_{tag}.json").read_text(encoding="utf-8"))
    if expect_chunks_fingerprint and meta["chunks_fingerprint"] != expect_chunks_fingerprint:
        raise RuntimeError(
            f"索引与 chunks.jsonl 版本不一致：index={meta['chunks_fingerprint'][:8]} "
            f"chunks={expect_chunks_fingerprint[:8]} —— 请重建索引")
    if expect_model_id and meta.get("model_id") != expect_model_id:
        raise RuntimeError(
            f"索引模型不匹配：索引由 {meta.get('model_id')!r} 构建，"
            f"当前请求 {expect_model_id!r} —— 不同模型的向量空间不可比，"
            f"请重建索引或切换 embedding provider")
    return vectors, ids, meta


def build_corpus_index(chunks: list[Chunk], dim: int, cch: bool,
                       client: BaseEmbeddingClient, index_dir: str | Path,
                       chunks_fingerprint: str, purpose: str | None = None,
                       resume: bool = True) -> dict:
    """对正文 chunk 建向量索引（调用方保证 chunks 全为 region=="body"）。

    断点续传（resume=True）：每批向量单独落盘到
    <index_dir>/<model_ns>/vector_cache_<dim>_<tag>_<fp8>/batch_%04d.npy。
    缓存目录按 chunks_fingerprint 前 8 位隔离；模型由 model_ns 隔离。
    """
    assert all(c.region == "body" for c in chunks), "只允许为正文 chunk 建索引"
    texts = [c.index_text() if cch else c.text for c in chunks]
    tag = "cch" if cch else "nocch"
    purpose = purpose or f"build_index_dim{dim}_{tag}"
    ns_dir = Path(index_dir) / client.model_ns
    ns_dir.mkdir(parents=True, exist_ok=True)

    step = client.max_batch
    n_batches = (len(texts) + step - 1) // step
    cache_dir = ns_dir / f"vector_cache_{dim}_{tag}_{chunks_fingerprint[:8]}"

    rows: list[list[float]] = []
    reused = 0
    if resume and cache_dir.is_dir():
        for b in range(n_batches):
            f = cache_dir / f"batch_{b:04d}.npy"
            if not f.exists():
                break
            arr = np.load(f, allow_pickle=False)
            if arr.ndim != 2 or arr.shape[0] != min(step, len(texts) - b * step):
                break            # 形状异常：该批及之后不可信，重算
            rows.extend(arr.tolist())
            reused += arr.shape[0]
    if reused:
        print(f"[续传] {client.model_ns} dim={dim} tag={tag} 复用 {reused}/{len(texts)} 条"
              f"（省下约 {reused / len(texts) * 100:.0f}% 本维建库成本）")

    start_batch = len(rows) // step
    if len(rows) < len(texts):
        cache_dir.mkdir(parents=True, exist_ok=True)
        for b in range(start_batch, n_batches):
            batch = texts[b * step:(b + 1) * step]
            embs, _tok = client._post_one(batch, dim, purpose)
            if len(embs) != len(batch):
                raise RuntimeError(f"返回条数 {len(embs)} != 请求 {len(batch)}")
            arr = np.asarray(embs, dtype=np.float32)
            np.save(cache_dir / f"batch_{b:04d}.npy", arr)   # 逐批落盘，中断可复用
            rows.extend(arr.tolist())

    vectors = np.asarray(rows, dtype=np.float32)
    if vectors.shape[0] != len(texts) or vectors.ndim != 2:
        raise RuntimeError(f"向量形状 {vectors.shape} 与正文 chunk 数 {len(texts)} 不符")
    # 完成即清理缓存（索引已独立保存）
    if cache_dir.is_dir():
        for f in cache_dir.glob("batch_*.npy"):
            f.unlink()
        cache_dir.rmdir()
    return save_index(index_dir, dim, tag, vectors, [c.chunk_id for c in chunks],
                      chunks_fingerprint, client)
