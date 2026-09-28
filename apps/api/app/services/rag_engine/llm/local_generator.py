"""P7 本地讲解生成运行时（docs/SCHEMA.md §十）。

LocalOllamaGenerator —— Ollama 回环 ``/api/chat``：
  - 身份核验：启动时 GET /api/tags，以 :func:`check_local_model_digest`
    与登记的 expected_manifest_digest 比对（复用 execution_policy，不另造），
    不符/不可达即失败；model_id/digest/quantization/license 记入 usage；
  - 策略：local-only 下端点必须回环（:func:`assert_endpoint_allowed`）；
    cache-only 下禁止任何 HTTP（构造即抛错，不静默）；
  - chat(messages, *, schema, num_ctx, ...) -> (text, usage)：schema 非 None 时
    以 ``format=schema`` 传 JSON Schema（结构化输出）；usage 含
    prompt_eval_count/eval_count/total_duration/load_duration/latency_ms/keep_alive；
  - 超时（配置 timeout_seconds，默认 300s）→ 明确异常；取消令牌 → 不发起新请求；
  - release() 以 keep_alive=0 卸载模型；close() 幂等；
  - 记账：每次真实回环调用一行 api_usage.jsonl（provider=local-ollama、
    purpose=explain_chat、est_cost_yuan=0.0、tokens 取实际可得 prompt+eval）。

MockGenerator —— 确定性、无网络；产物带 ``mock: true``；不写 api_usage.jsonl、
不写运行台账；缓存与真实链路物理隔离（model_ns 不同，见 generation_cache）。

运行台账：data/derived/generation_runs/<run_id>.json（SCHEMA §十字段：
尝试数/实际完成数/修复请求数/输入输出 token/缓存命中/采用情况/错误/
cloud_requests: 0/cloud_cost_yuan: 0.0）。**run_id 唯一**（时间戳+进程+随机后缀，
同秒并发请求互不覆盖）、临时文件按写入者独立命名；mock 不写台账。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path

from app.services.rag_engine.retrieval.execution_policy import (POLICY_CACHE_ONLY, POLICY_LOCAL_ONLY,
                                            PolicyViolation, assert_endpoint_allowed,
                                            assert_no_redirect_follow,
                                            check_local_model_digest,
                                            normalize_policy)

ROOT = Path(__file__).resolve().parents[2]

#: /api/chat 返回体的 duration 字段单位为纳秒
_NS_PER_MS = 1e6


class GenerationError(RuntimeError):
    """生成失败基类（HTTP 错误/响应异常）。调用方决定状态映射，本层不吞。"""


class GenerationTimeout(GenerationError):
    """单次生成请求超时（配置 timeout_seconds）。"""


class ModelUnavailable(GenerationError):
    """本地生成模型不可用（服务未运行/模型缺失/身份核验失败）。**不回落云端**。"""


class GenerationCancelled(GenerationError):
    """取消信号：已取消的生成器不再发起新请求。

    `completed` 区分两种取消，**记账必须据此区分**（P8A / R8）：
      - `completed=False`：请求发出前就发现取消 → 没有发生本地调用；
      - `completed=True`：请求已返回、结果不采用 → **这次本地调用确实发生了**，
        必须计入推理次数与台账，不能因为"没采用结果"就漏计。
    """

    def __init__(self, *args, completed: bool = False):
        super().__init__(*args)
        self.completed = bool(completed)


def _is_cancelled(token) -> bool:
    """兼容 threading.Event 与返回布尔的 callable（与 rerank 取消语义一致）。"""
    if token is None:
        return False
    if hasattr(token, "is_set"):
        return bool(token.is_set())
    return bool(token())


# ---------------------------------------------------------------------------
# 生成器接口（鸭子类型约定，service.py 只依赖 chat/release/close/mock 属性）
# ---------------------------------------------------------------------------


class BaseGenerator:
    """生成器公共接口。子类实现 _generate_once(messages, schema, options) -> (text, usage)。"""

    provider: str = "?"
    is_mock: bool = False

    def chat(self, messages: list[dict], *, schema: dict | None = None,
             num_ctx: int, temperature: float = 0.0, seed: int = 0,
             num_predict: int = 1024, purpose: str = "explain_chat",
             cancel_token=None) -> tuple[str, dict]:
        """一次生成。返回 (text, usage)。取消 → GenerationCancelled；失败 → GenerationError。"""
        if _is_cancelled(cancel_token):
            raise GenerationCancelled("取消于生成请求前")
        text, usage = self._generate_once(messages, schema=schema,
                                          num_ctx=int(num_ctx),
                                          temperature=float(temperature),
                                          seed=int(seed),
                                          num_predict=int(num_predict),
                                          purpose=purpose)
        if _is_cancelled(cancel_token):
            raise GenerationCancelled("取消于生成返回后（结果不采用）",
                                      completed=True)
        return text, usage

    def _generate_once(self, messages, *, schema, num_ctx, temperature, seed,
                       num_predict, purpose) -> tuple[str, dict]:
        raise NotImplementedError

    def release(self) -> None:
        """释放模型（真实实现发 keep_alive=0；mock 无操作）。"""

    def close(self) -> None:
        """幂等收尾（含 release）。"""


# ---------------------------------------------------------------------------
# 本地 Ollama 生成器
# ---------------------------------------------------------------------------


class LocalOllamaGenerator(BaseGenerator):
    """Ollama 回环 /api/chat 生成器（真实本地推理）。

    cache-only 策略下构造即抛 PolicyViolation——禁止任何 HTTP，不静默。
    """

    provider = "local-ollama"
    is_mock = False

    def __init__(self, spec: dict, *, policy: str = POLICY_LOCAL_ONLY,
                 usage_log: str | Path | None = None, cancel_token=None):
        self.policy = normalize_policy(policy)
        if self.policy == POLICY_CACHE_ONLY:
            raise PolicyViolation(
                "执行策略 cache-only 禁止任何网络（含本机回环 Ollama 生成）；"
                "如需复用历史结果请走生成缓存（GenerationCache），不得创建真实生成器")
        self.spec = dict(spec)
        self.model = str(spec["model"])
        self.model_id = str(spec["model_id"])
        self.model_ns = self.model_id.replace("/", "_").replace(":", "_")
        self.chat_endpoint = str(spec["chat_endpoint"])
        self.tags_endpoint = str(spec.get("tags_endpoint") or "")
        self.timeout = float(spec.get("timeout_seconds", 300))
        self.keep_alive = spec.get("keep_alive", "10m")
        self.expected_manifest_digest = spec.get("expected_manifest_digest")
        self.quantization = spec.get("quantization")
        self.license = spec.get("license")
        self.usage_log = Path(usage_log) if usage_log else None
        self.cancel_token = cancel_token
        self._client = None            # 惰性 httpx.Client
        self._identity: dict | None = None
        self._closed = False
        # 失败早于任何 I/O：端点必须是显式回环 URL
        assert_endpoint_allowed(self.chat_endpoint, self.policy, name="chat")
        if self.tags_endpoint:
            assert_endpoint_allowed(self.tags_endpoint, self.policy, name="tags")
        assert_no_redirect_follow(False, self.policy)

    # ---- 身份核验 ----

    def verify_identity(self) -> dict:
        """GET /api/tags 核对模型身份（复用 check_local_model_digest）。

        不可达/模型缺失/digest 不符 → ModelUnavailable（绝不静默跳过）。
        返回并缓存 {model, digest, identity_verified}（记入每次 usage）。
        """
        if self._identity is not None:
            return self._identity
        import httpx
        if not self.tags_endpoint:
            raise PolicyViolation("本地生成身份核验要求 spec 登记 tags_endpoint")
        try:
            with httpx.Client(timeout=10.0, follow_redirects=False, trust_env=False) as cli:
                resp = cli.get(self.tags_endpoint)
        except Exception as e:     # noqa: BLE001 —— 回环不可达统一按模型不可用处理
            raise ModelUnavailable(
                f"本地生成模型身份核验不可达：GET {self.tags_endpoint} 失败（{e}）。"
                f"请确认 ollama serve 正在运行；不核验身份不得本地推理") from e
        if resp.status_code != 200:
            raise ModelUnavailable(
                f"本地生成模型身份核验失败：GET {self.tags_endpoint} → HTTP {resp.status_code}")
        try:
            models = resp.json().get("models", [])
        except Exception as e:
            raise ModelUnavailable(f"/api/tags 响应非预期 JSON（{e}）") from e
        entry = next((m for m in models if m.get("model") == self.model), None)
        if entry is None:
            names = [str(m.get("model")) for m in models][:5]
            raise ModelUnavailable(
                f"Ollama 未加载生成模型 {self.model!r}（可用：{names}）。请 ollama pull {self.model}")
        hint = {"model": entry.get("model"),
                "digest": entry.get("digest") or entry.get("model_digest")}
        expected = {"model": self.model}

        def _norm(s: str) -> str:
            return str(s).removeprefix("sha256:")

        matched = False
        got_raw = str(hint.get("digest") or "")
        for anchor in ("expected_manifest_digest", "expected_digest"):
            if self.spec.get(anchor) and got_raw and _norm(got_raw) == _norm(self.spec[anchor]):
                matched = True
        if matched:
            # 锚点已匹配（manifest digest 语义与 /api/tags 回报一致）；
            # 模型名仍交契约函数照常比对。
            pass
        else:
            expected["digest"] = self.expected_manifest_digest or ""
        try:
            check_local_model_digest(hint, expected)
        except PolicyViolation as e:
            raise ModelUnavailable(f"本地生成模型身份不符：{e}") from e
        self._identity = {"model": hint["model"], "digest": hint.get("digest"),
                          "identity_verified": bool(self.expected_manifest_digest)}
        return self._identity

    # ---- HTTP ----

    def _ensure_client(self):
        import httpx
        if self._client is None:
            # local-only 还必须禁用环境代理，回环 URL 本身不足以保证请求不离机。
            self._client = httpx.Client(timeout=self.timeout, follow_redirects=False,
                                        trust_env=False)
        return self._client

    def _generate_once(self, messages, *, schema, num_ctx, temperature, seed,
                       num_predict, purpose) -> tuple[str, dict]:
        if self._closed:
            raise GenerationError("生成器已关闭（close 后不可再生成；release 仍可用）")
        identity = self.verify_identity()
        if _is_cancelled(self.cancel_token):
            raise GenerationCancelled("取消于生成请求前（身份核验后）")
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": int(num_ctx), "temperature": float(temperature),
                        "seed": int(seed), "num_predict": int(num_predict)},
            "keep_alive": self.keep_alive,
        }
        if schema is not None:
            payload["format"] = schema
        client = self._ensure_client()
        t0 = time.monotonic()
        try:
            resp = client.post(self.chat_endpoint, json=payload)
        except Exception as e:  # httpx.TimeoutException 等传输错误统一映射
            latency_ms = int((time.monotonic() - t0) * 1000)
            if isinstance(e, __import__("httpx").TimeoutException):
                self._log_usage(purpose, None, latency_ms, ok=False, error_code="TIMEOUT")
                raise GenerationTimeout(
                    f"本地生成请求超时（>{self.timeout:.0f}s，endpoint={self.chat_endpoint}）") from e
            self._log_usage(purpose, None, latency_ms, ok=False, error_code="TRANSPORT")
            raise ModelUnavailable(
                f"本地生成服务不可达：POST {self.chat_endpoint} 失败（{e}）——不回落云端") from e
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code != 200:
            self._log_usage(purpose, None, latency_ms, ok=False,
                            error_code=f"HTTP{resp.status_code}")
            raise GenerationError(
                f"本地生成失败：HTTP {resp.status_code} body={resp.text[:200]}")
        try:
            body = resp.json()
        except Exception as e:
            self._log_usage(purpose, None, latency_ms, ok=False, error_code="BAD_JSON")
            raise GenerationError(f"/api/chat 响应非 JSON：{e}") from e
        if body.get("error"):
            self._log_usage(purpose, None, latency_ms, ok=False, error_code="API_ERROR")
            raise GenerationError(f"/api/chat 返回错误：{str(body['error'])[:200]}")
        text = str(body.get("message", {}).get("content", ""))
        prompt_eval = body.get("prompt_eval_count")
        eval_count = body.get("eval_count")
        total_tokens = (int(prompt_eval) if isinstance(prompt_eval, int) else 0) \
            + (int(eval_count) if isinstance(eval_count, int) else 0)
        usage = {
            "prompt_eval_count": prompt_eval if isinstance(prompt_eval, int) else None,
            "eval_count": eval_count if isinstance(eval_count, int) else None,
            "total_tokens": total_tokens,
            "total_duration_ms": _ms(body.get("total_duration")),
            "load_duration_ms": _ms(body.get("load_duration")),
            "prompt_eval_duration_ms": _ms(body.get("prompt_eval_duration")),
            "eval_duration_ms": _ms(body.get("eval_duration")),
            "latency_ms": latency_ms,
            "keep_alive": self.keep_alive,
            "done_reason": body.get("done_reason"),
            # 模型身份（每次调用随 usage 记录，供台账与 provenance 汇总）
            "model_id": self.model_id,
            "model": self.model,
            "manifest_digest": identity.get("digest"),
            "identity_verified": identity.get("identity_verified", False),
            "quantization": self.quantization,
            "license": self.license,
            "num_ctx": int(num_ctx), "temperature": float(temperature),
            "seed": int(seed), "num_predict": int(num_predict),
            "billed_unknown": False,
        }
        self._log_usage(purpose, total_tokens, latency_ms, ok=True)
        return text, usage

    # ---- 记账 ----

    def _log_usage(self, purpose: str, total_tokens: int | None, latency_ms: int,
                   ok: bool = True, error_code: str | None = None) -> None:
        """每次真实回环调用一行 api_usage.jsonl（SCHEMA §十：本地照常记账）。

        失败调用的 token 数不可得 → 写 ``null``（"unknown"），**不虚报 0**
        （P8A / R8）：0 与"没测到"是两回事，写成 0 会污染 token 汇总。
        """
        if self.usage_log is None:
            return
        tokens = int(total_tokens) if (ok and total_tokens is not None) else None
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "purpose": purpose,
            "provider": self.provider,
            "model": self.model,
            "model_id": self.model_id,
            "dim": None,
            "n_texts": 1,
            "total_tokens": tokens,
            "est_cost_yuan": 0.0,
            "latency_ms": latency_ms,
            "retries": 0,
            "ok": ok,
            "error_code": error_code,
            "tokens_unknown": tokens is None,     # 失败/不可得：显式标记，不是 0
        }
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.usage_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- 生命周期 ----

    def release(self) -> None:
        """keep_alive=0 卸载模型（评测/运行结束释放显存；幂等安全）。

        注意：close() 之后仍可调用（close 只关常驻 HTTP 客户端；release 用
        一次性短连接发卸载请求）。服务不可达时静默忽略——释放失败不影响结果。
        """
        import httpx
        try:
            with httpx.Client(timeout=30.0, follow_redirects=False, trust_env=False) as cli:
                cli.post(self.chat_endpoint, json={"model": self.model,
                                                   "keep_alive": 0})
        except Exception:
            pass                      # 释放失败不影响结果；服务可能已停止

    def close(self) -> None:
        """幂等收尾：关 HTTP 客户端。**不**隐式卸载模型（release 显式调用）。"""
        self._closed = True
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "LocalOllamaGenerator":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _ms(ns) -> float | None:
    """Ollama duration（纳秒）→ 毫秒；缺失/非法返回 None（不编造）。"""
    if isinstance(ns, (int, float)) and not isinstance(ns, bool):
        return round(float(ns) / _NS_PER_MS, 3)
    return None


# ---------------------------------------------------------------------------
# Mock 生成器
# ---------------------------------------------------------------------------


class MockGenerator(BaseGenerator):
    """确定性伪生成器（无网络、无模型）。产物带 ``mock: true``。

    reply_for 可注入按调用序或关键词的响应（测试用）；缺省输出一个引用了
    ``citation_ids_hint``（构造时给定）的合法 JSON。usage 的 tokens 记 None
    ——mock 无真实 token 数，不得编造。
    """

    provider = "mock"
    is_mock = True

    def __init__(self, *, model_id: str = "mock/generator",
                 replies: list[str] | None = None,
                 citation_ids_hint: list[str] | None = None):
        self.model_id = model_id
        self.model_ns = model_id.replace("/", "_").replace(":", "_")
        self.replies = list(replies or [])
        self.citation_ids_hint = list(citation_ids_hint or [])
        self.calls = 0
        self._closed = False

    def _generate_once(self, messages, *, schema, num_ctx, temperature, seed,
                       num_predict, purpose) -> tuple[str, dict]:
        if self._closed:
            raise GenerationError("生成器已关闭")
        idx = self.calls
        self.calls += 1
        if idx < len(self.replies):
            text = self.replies[idx]
        else:
            import json as _json
            text = _json.dumps({
                "knowledge_points": ["（mock）知识点"],
                "explanations": [{
                    "point": "（mock）知识点",
                    "citation_ids": list(self.citation_ids_hint),
                    "explanation": "（mock 解释）只依据证据作答。",
                    "supplement": None,
                }],
                "uncertain": False,
            }, ensure_ascii=False)
        usage = {
            "prompt_eval_count": None, "eval_count": None, "total_tokens": 0,
            "total_duration_ms": None, "load_duration_ms": None,
            "prompt_eval_duration_ms": None, "eval_duration_ms": None,
            "latency_ms": 0, "keep_alive": None, "done_reason": None,
            "model_id": self.model_id, "model": self.model_id,
            "manifest_digest": None, "identity_verified": False,
            "quantization": None, "license": None,
            "num_ctx": int(num_ctx), "temperature": float(temperature),
            "seed": int(seed), "num_predict": int(num_predict),
            "billed_unknown": False, "mock": True,
        }
        return text, usage

    def release(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True


# ---------------------------------------------------------------------------
# 运行台账（SCHEMA §十：generation_runs/<run_id>.json）
# ---------------------------------------------------------------------------


class GenerationRunLedger:
    """一次讲解服务的运行聚合。mock 运行不写台账（调用方不创建即可）。

    run_id 唯一性（P8A / R8）：过去默认 run_id 只有秒级时间，同一秒的两个请求写同一
    路径，`os.replace` 把前者覆盖掉——调用次数与来源审计直接丢数据。现在 run_id =
    时间戳 + 进程 + 随机后缀，临时文件也按写入者独立命名（并发不再共享 `.tmp`）。

    计数口径（四态分开，不得互相冒充）：
      - `n_attempts`      尝试发出的请求数（含取消前已发出的）；
      - `n_requests`      生成器**正常返回**的请求数（实际完成）；
      - `cache_hits/misses` 缓存重放；
      - `adopted_*`       结果被采用（进入返回的 explanations）；
      - token 不可得时写 null 并注明，**不虚报零**。
    """

    def __init__(self, runs_dir: str | Path, run_id: str | None = None,
                 meta: dict | None = None):
        self.runs_dir = Path(runs_dir)
        # 唯一 run_id：秒级时间戳不足以区分同秒并发请求（R8 复现）
        self.run_id = run_id or (
            time.strftime("generation_%Y%m%d_%H%M%S")
            + f"_{os.getpid()}_{uuid.uuid4().hex[:8]}")
        self.meta = dict(meta or {})
        self.t0 = time.monotonic()
        self.n_attempts = 0
        self.n_requests = 0
        self.n_repair_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.adopted_inference = 0
        self.adopted_cache_replay = 0
        self.explanations_published = 0
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.tokens_known = True          # 任一次调用 token 未知 → 整体 unknown
        self.observed: dict | None = None
        self.latencies_ms: list[int] = []
        self.errors: dict[str, int] = {}
        self.finalized = False

    def note_attempt(self, *, repair: bool = False) -> None:
        """请求已发出但未正常返回（取消/超时/传输错误）——token 不可得，记 unknown。"""
        self.n_attempts += 1
        self.tokens_known = False

    def note_request(self, usage: dict, *, repair: bool = False) -> None:
        self.n_attempts += 1
        self.n_requests += 1
        if repair:
            self.n_repair_requests += 1
        pe, ec = usage.get("prompt_eval_count"), usage.get("eval_count")
        if isinstance(pe, int) and isinstance(ec, int):
            self.prompt_tokens += int(pe)
            self.output_tokens += int(ec)
        else:
            self.tokens_known = False
        lat = usage.get("latency_ms")
        if isinstance(lat, (int, float)) and not isinstance(lat, bool):
            self.latencies_ms.append(int(lat))

    def note_cache(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def note_index_identity(self, identity: dict) -> None:
        """登记本次运行实际绑定的索引身份（spec 名 / chunks 指纹 / index_dir …）。

        P10 契约：结果追溯必须能回答"这次答案用的是哪一份检索空间"。
        空字典不写（mock 或未报告身份的 provider）；台账 meta 已有同名字段时**不覆盖**，
        而是把两次值都留下（`conflict_with_earlier`）——覆盖会掩盖"同一台账进程里换过
        索引身份"这种真实冲突。
        """
        if not identity:
            return
        ident = dict(identity)
        earlier = self.meta.get("index_identity")
        if earlier is not None and earlier != ident:
            ident = {**ident, "conflict_with_earlier": earlier}
        self.meta["index_identity"] = ident

    def note_observed(self, observed: dict) -> None:
        """生成返回后的实测核对（截断疑似、估算偏差）——原样留存，便于再校准。"""
        self.observed = dict(observed)

    def note_result(self, *, n_explanations: int, evidence_published: int,
                    source: str) -> None:
        """结果采用情况（R8：区分'推理结果采用'与'缓存重放采用'）。"""
        self.explanations_published = int(n_explanations)
        if n_explanations <= 0:
            return
        if source == "cache":
            self.adopted_cache_replay += 1
        else:
            self.adopted_inference += 1

    def note_error(self, error_type: str) -> None:
        self.errors[error_type] = self.errors.get(error_type, 0) + 1

    @staticmethod
    def _pctl(sorted_vals: list[int], q: float) -> int:
        if not sorted_vals:
            return 0
        k = max(0, min(len(sorted_vals) - 1, math.ceil(q * len(sorted_vals)) - 1))
        return int(sorted_vals[k])

    def finalize(self) -> dict:
        if self.finalized:
            return self._record
        lat = sorted(self.latencies_ms)
        record = {
            "run_id": self.run_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **self.meta,
            "n_attempts": self.n_attempts,
            "n_requests": self.n_requests,
            "n_repair_requests": self.n_repair_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "adopted_inference": self.adopted_inference,
            "adopted_cache_replay": self.adopted_cache_replay,
            "explanations_published": self.explanations_published,
            "prompt_tokens": self.prompt_tokens if self.tokens_known else None,
            "output_tokens": self.output_tokens if self.tokens_known else None,
            "tokens_note": None if self.tokens_known
            else "存在 token 不可得的调用（缓存命中/失败/取消），未编造数值",
            "observed": self.observed,
            "wall_seconds": round(time.monotonic() - self.t0, 3),
            "latency_ms": {"p50": self._pctl(lat, 0.50), "p95": self._pctl(lat, 0.95)},
            "cloud_requests": 0,
            "cloud_cost_yuan": 0.0,
            "errors": dict(self.errors),
        }
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        p = self.runs_dir / f"{self.run_id}.json"
        # 每个写入者独立临时文件：并发写不再互相覆盖（R8）
        tmp = p.with_name(f".{self.run_id}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1),
                           encoding="utf-8", newline="\n")
            os.replace(tmp, p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        self.finalized = True
        self._record = record
        return record
