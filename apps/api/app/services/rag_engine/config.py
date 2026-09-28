"""配置解析的**唯一入口**（P8A / R10）。

问题（2026-09-21 代码审查 R10）：`generation.providers[active]` 里写着 num_ctx、
num_predict、证据预算等运行时参数，而 CLI 把 `generation` **根**传给服务；服务层
`_gen_cfg` 于是退回自己那套默认值。当前两者数值恰好相同，问题被掩盖——用户按配置
调低上下文或显存预算时会发现修改完全不生效。

本模块的规则：

1. **单一默认值来源**：所有缺省值只在本文件出现一次，其它模块不得再维护
   一份"恰好相同"的默认值（这是 R10 的根因，不只是数值不一致）。
2. **优先级**：显式覆盖（函数参数） > 选中 provider 段 > generation 根公共字段 > 本文件默认值。
   provider 段更具体，因此覆盖根字段。
3. **合法性校验**：非法值直接 `ValueError`，不静默取默认（静默默认是同类缺陷的温床）。
4. **身份与运行时同源**：返回值同时含 provider 身份（model / model_id / 端点 / digest）
   与运行时参数，调用方构造生成器与记录 provenance 都从这里取，不得各取一处。

输入容忍三种形态（便于 service / CLI / 测试共用同一函数）：
  - 完整 `configs/models.yaml`：含 `generation` 段；
  - `generation` 段本身：含 `active` + `providers`；
  - 已解析的扁平字典：既无 `generation` 也无 `providers`，按"显式覆盖"叠加在默认值上。

分级职责（本模块只做"解析与校验"，不做 I/O、不建客户端、不读密钥）。
"""
from __future__ import annotations

from typing import Any, Mapping

# 版本常量的**单一定义点**在各模块自身；此处只引用，不复制字面量
from app.services.rag_engine.llm.generation_cache import CACHE_CONTRACT_VERSION as _CACHE_CONTRACT_VERSION
from app.services.rag_engine.llm.prompts import PROMPT_VERSION as _PROMPT_VERSION
from app.services.rag_engine.llm.prompts import SCHEMA_VERSION as _SCHEMA_VERSION

# ---------------------------------------------------------------------------
# 默认值（唯一来源）
# ---------------------------------------------------------------------------

#: 公共字段（与 provider 无关，位于 generation 根）。
GENERATION_COMMON_KEYS = ("active", "cache_dir", "cache_contract_version",
                          "prompt_version", "schema_version")

#: provider 段里属于"运行时/身份"的字段（会被解析进扁平结果）。
_PROVIDER_KEYS = (
    "provider", "model", "model_id", "chat_endpoint", "tags_endpoint",
    "ps_endpoint", "expected_manifest_digest", "expected_digest", "license",
    "quantization", "param_size", "model_context_limit", "num_ctx",
    "temperature", "seed", "num_predict", "keep_alive", "timeout_seconds",
    "json_schema_mode", "price_per_million_tokens", "max_repair_attempts",
    "evidence_pack_max_tokens", "budget",
)

#: 缺省运行时参数。**唯一来源**——历史 `service._gen_cfg` 的默认值已删除。
GENERATION_DEFAULTS: dict[str, Any] = {
    "provider": "local-ollama",
    "model": "qwen2.5:7b",
    "model_id": "ollama/qwen2.5:7b",
    "num_ctx": 8192,
    "temperature": 0.0,
    "seed": 0,
    "num_predict": 1024,
    "keep_alive": "10m",
    "timeout_seconds": 300.0,
    "max_repair_attempts": 1,
    "evidence_pack_max_tokens": 6000,
    # ---- 完整上下文预算（P8A / R5）----
    # 证据包预算只约束"证据"部分；题面、系统提示、约束行、chat 模板开销、
    # 输出预留与修复轮追加消息都不在 evidence_pack_max_tokens 之内。
    # 下面三个参数构成完整预算契约（口径见 docs/SCHEMA.md §十一）。
    "budget": {
        #: 保守 token 上界系数：est_tokens = ceil(chars / chars_per_token_lower)。
        #: 1.0 = 折成"每字符至少 1 token"（中文约 0.7–1.2 token/字符，取 1.0 偏保守）。
        #: 该值必须由 `budget.calibration` 记录的真实测量支撑，不得凭空声明。
        "chars_per_token_lower": 1.0,
        #: chat 模板（system/user 包装、角色标记）的固定 token 开销。
        "template_overhead_tokens": 64,
        #: 额外安全余量（估算误差、模板微调、服务端附加字段）。
        "safety_margin_tokens": 128,
    },
    #: 缓存契约版本（键的一部分；不接受时须由调用方显式给值）。
    #: **由唯一定义点推导**，不写死字面量——否则会与 `src/llm/*` 的常量悄悄漂移，
    #: 表现为"缓存总是未命中/查到旧命名空间"（P8C 实测过：默认 1 与部署配置 2 不一致）。
    "cache_contract_version": _CACHE_CONTRACT_VERSION,
    "prompt_version": _PROMPT_VERSION,
    "schema_version": _SCHEMA_VERSION,
    "cache_dir": None,
}

#: 运行时参数的合法区间（含端点）；越界即拒绝。
_RANGES: dict[str, tuple[float, float]] = {
    "num_ctx": (512, 1 << 20),
    "num_predict": (1, 1 << 20),
    "temperature": (0.0, 2.0),
    "max_repair_attempts": (0, 1),      # 有界：最多一次
    "evidence_pack_max_tokens": (1, 1 << 20),
    "timeout_seconds": (1.0, 3600.0),
}


class GenerationConfigError(ValueError):
    """配置非法（缺 provider、类型错、越界、预算自相矛盾）。不静默取默认。"""


def _as_section(cfg: Mapping[str, Any] | None) -> tuple[dict, bool]:
    """返回 (generation 段, 是否为结构化段)。扁平字典按"显式覆盖"处理。"""
    if not isinstance(cfg, Mapping):
        return {}, False
    inner = cfg.get("generation")
    if isinstance(inner, Mapping):
        return dict(inner), True
    if "providers" in cfg or "active" in cfg:
        return dict(cfg), True
    return dict(cfg), False


def _merge_budget(resolved: dict, value: Any) -> None:
    """budget 是**部分覆盖**：只给一个子键时其余子键必须保留默认值。

    若整块替换，`budget: {safety_margin_tokens: 0}` 这类配置会把
    chars_per_token_lower 变成缺失 → 估算口径丢失（P8A 自测发现的真实缺陷）。
    """
    if not isinstance(value, Mapping):
        raise GenerationConfigError(f"budget 必须是字典，得到 {type(value).__name__}")
    merged = dict(resolved.get("budget") or {})
    merged.update(value)
    resolved["budget"] = merged


def resolve_generation_config(cfg: Mapping[str, Any] | None = None, *,
                              provider: str | None = None,
                              overrides: Mapping[str, Any] | None = None) -> dict:
    """把任意形态的配置解析成**一份**扁平运行时配置。

    参数
      cfg        完整 models.yaml / generation 段 / 扁平覆盖字典（见模块 docstring）。
      provider   显式选中 provider（覆盖 `active`；用于 `--provider` 类开关或测试）。
      overrides  最高优先级的显式覆盖（如单次运行的 CLI 参数）。

    返回扁平 dict：公共字段 + 选中 provider 的运行时与身份字段 + `active_provider`
    （实际选中的 provider 名）。所有值已通过类型与区间校验。
    """
    section, structured = _as_section(cfg)
    resolved: dict[str, Any] = dict(GENERATION_DEFAULTS)
    resolved["budget"] = dict(GENERATION_DEFAULTS["budget"])

    active_name: str | None = None
    if structured:
        providers = section.get("providers")
        if not isinstance(providers, Mapping) or not providers:
            raise GenerationConfigError(
                "generation 段缺少 providers（无法确定运行时参数与模型身份）")
        active_name = str(provider or section.get("active") or "")
        if not active_name:
            raise GenerationConfigError(
                "generation 段缺少 active，且未显式指定 provider")
        if active_name not in providers:
            raise GenerationConfigError(
                f"未知 generation provider {active_name!r}（可选："
                f"{sorted(providers)}）——拒绝回退默认值")
        spec = providers[active_name]
        if not isinstance(spec, Mapping):
            raise GenerationConfigError(f"generation.providers[{active_name}] 不是字典")
        # ① generation 根公共字段（比内置默认更具体 → 覆盖默认）
        for k, v in section.items():
            if k in ("providers", "active"):
                continue
            if k == "budget":
                _merge_budget(resolved, v)
            else:
                resolved[k] = v
        # ② 选中 provider 段（最具体 → 覆盖根字段）
        for k, v in dict(spec).items():
            if k == "budget":
                _merge_budget(resolved, v)
            elif k in _PROVIDER_KEYS:
                resolved[k] = v
        resolved["active_provider"] = active_name
    else:
        # 扁平字典：全部按显式覆盖处理（不参与 provider 选择）
        for k, v in section.items():
            if k == "budget":
                _merge_budget(resolved, v)
            else:
                resolved[k] = v
        resolved.setdefault("active_provider", None)

    if overrides:
        for k, v in dict(overrides).items():
            if k == "budget":
                _merge_budget(resolved, v)
            else:
                resolved[k] = v

    _validate(resolved)
    return resolved


def _validate(cfg: dict) -> None:
    """类型 + 区间 + 预算自洽性校验。任何问题抛 GenerationConfigError。"""
    for key, (lo, hi) in _RANGES.items():
        if key not in cfg or cfg[key] is None:
            continue
        val = cfg[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise GenerationConfigError(f"{key} 必须是数字，得到 {type(val).__name__}")
        if not (lo <= float(val) <= hi):
            raise GenerationConfigError(f"{key}={val} 超出允许区间 [{lo}, {hi}]")
    for key in ("max_repair_attempts", "num_ctx", "num_predict",
                "evidence_pack_max_tokens"):
        val = cfg.get(key)
        if isinstance(val, float) and not float(val).is_integer():
            raise GenerationConfigError(f"{key} 必须是整数，得到 {val}")
        if val is not None:
            cfg[key] = int(val)

    budget = cfg.get("budget")
    if not isinstance(budget, Mapping):
        raise GenerationConfigError("budget 必须是字典（chars_per_token_lower/"
                                    "template_overhead_tokens/safety_margin_tokens）")
    for key in ("chars_per_token_lower", "template_overhead_tokens",
                "safety_margin_tokens"):
        val = budget.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or float(val) <= 0:
            raise GenerationConfigError(f"budget.{key} 必须为正数，得到 {val!r}")
    cfg["budget"] = {k: float(budget[k]) for k in
                     ("chars_per_token_lower", "template_overhead_tokens",
                      "safety_margin_tokens")}
    # 证据包预算只是完整预算的一部分：它不能大于等于 num_ctx（否则必然越界）。
    if int(cfg["evidence_pack_max_tokens"]) >= int(cfg["num_ctx"]):
        raise GenerationConfigError(
            f"evidence_pack_max_tokens={cfg['evidence_pack_max_tokens']} 必须小于 "
            f"num_ctx={cfg['num_ctx']}（证据包只是输入的一部分，还要留题面与输出空间）")
    if int(cfg["num_predict"]) >= int(cfg["num_ctx"]):
        raise GenerationConfigError(
            f"num_predict={cfg['num_predict']} 必须小于 num_ctx={cfg['num_ctx']}")
