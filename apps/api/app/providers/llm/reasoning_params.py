"""推理/思考参数映射：按供应商与模型把受控 effort 翻译成各家专有字段。

参考：固定 DeepTutor `deeptutor/services/llm/reasoning_params.py:109-173`
（v1.6.5 / 42fab3cf，Apache-2.0）。本实现复刻其映射语义与"模型族回退推断"，
但不引入参考的进程级能力黑名单。

受控输入来自 profile 的 `reasoningEnabled`（三态）与 `reasoningEffort`
（`none|minimal|low|medium|high|xhigh|max`）；本模块不接收任意 JSON。
"""

from __future__ import annotations

from typing import Any

# 供应商 thinking_style → 专有字段构造（参考 _THINKING_STYLE_MAP）
THINKING_STYLE_MAP = {
    "thinking_type": lambda enabled: {"thinking": {"type": "enabled" if enabled else "disabled"}},
    "enable_thinking": lambda enabled: {"enable_thinking": enabled},
    "reasoning_split": lambda enabled: {"reasoning_split": enabled},
}

# providerId → 默认 thinking_style（当 spec 未声明时回退）
PROVIDER_THINKING_STYLES = {
    "deepseek": "thinking_type",
    "volcengine": "thinking_type",
    "volcengine_coding_plan": "thinking_type",
    "byteplus": "thinking_type",
    "byteplus_coding_plan": "thinking_type",
    "dashscope": "enable_thinking",
    "minimax": "reasoning_split",
}

# providerId → 默认推理模型匹配模式
PROVIDER_REASONING_PATTERNS = {
    "deepseek": ("deepseek-v4-pro", "deepseek-reasoner"),
    "dashscope": ("qwen3", "qwen-3", "qwq", "qwen-plus"),
}

# custom 端点（用户自填地址，无法按供应商名识别）按模型族推断 thinking 样式
CUSTOM_MODEL_THINKING_STYLES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("qwen3", "qwen-3", "qwq", "qwen-plus"), "enable_thinking"),
    (("deepseek-v4-pro", "deepseek-reasoner", "deepseek-r1"), "thinking_type"),
)

# effort 归一：参考把 "minimum" 写作 minimal
_EFFORT_ALIASES = {"minimum": "minimal", "off": "none", "disabled": "none", "enabled": "high"}


def _matches(model_name: str, patterns: tuple[str, ...]) -> bool:
    lowered = model_name.lower()
    return any(pattern.lower() in lowered for pattern in patterns)


def _spec_name(spec: Any, provider_id: str | None) -> str:
    return str(getattr(spec, "providerId", None) or provider_id or "").strip().lower()


def _custom_thinking_style(model_name: str) -> tuple[str, tuple[str, ...]]:
    for patterns, style in CUSTOM_MODEL_THINKING_STYLES:
        if _matches(model_name, patterns):
            return style, patterns
    return "", ()


def default_reasoning_effort_for(
    provider_id: str | None,
    model: str | None,
    *,
    default_off_patterns: tuple[str, ...] = (),
    minimal_not_off_patterns: tuple[str, ...] = (),
) -> str | None:
    """供应商默认（未显式声明时）应使用的 effort；None 表示不注入。"""
    model_name = model or ""
    if default_off_patterns and _matches(model_name, default_off_patterns):
        if _matches(model_name, minimal_not_off_patterns):
            return "minimal"
        return "none"
    return None


def normalize_effort(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    return _EFFORT_ALIASES.get(normalized, normalized)


def build_reasoning_kwargs(
    *,
    spec: Any,
    provider_id: str | None,
    model: str | None,
    reasoning_enabled: bool | None,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    """返回应合并进 OpenAI 兼容请求体的推理参数。

    - `reasoningEnabled is False`：强制关闭思考（effort 归为 none），不发送顶层 effort。
    - 显式 effort：优先使用；`reasoningEnabled is True` 且未给 effort 时按模型默认提升。
    - 未声明：按供应商/模型默认（模式命中→high；默认关族→none/minimal）。
    """
    provider_name = _spec_name(spec, provider_id)
    model_name = model or ""
    thinking_style = str(getattr(spec, "thinkingStyle", "") or "")
    patterns = tuple(getattr(spec, "reasoningModelPatterns", ()) or ())
    default_off = tuple(getattr(spec, "defaultOffReasoning", ()) or ())
    minimal_not_off = tuple(getattr(spec, "minimalNotOff", ()) or ())

    if not thinking_style:
        thinking_style = PROVIDER_THINKING_STYLES.get(provider_name, "")
    if not patterns:
        patterns = PROVIDER_REASONING_PATTERNS.get(provider_name, ())
    # custom 端点：无供应商身份时按模型族推断
    if not thinking_style:
        custom_style, custom_patterns = _custom_thinking_style(model_name)
        if custom_style:
            thinking_style = custom_style
            if not patterns:
                patterns = custom_patterns

    explicit = normalize_effort(reasoning_effort)
    if reasoning_enabled is False:
        resolved_effort: str | None = "none"
    elif explicit is not None:
        resolved_effort = explicit
    elif reasoning_enabled is True:
        # 显式开启但未给深度：优先模型默认，其次 high
        resolved_effort = (
            "high"
            if (patterns and _matches(model_name, patterns))
            else (default_reasoning_effort_for(
                provider_name,
                model_name,
                default_off_patterns=default_off,
                minimal_not_off_patterns=minimal_not_off,
            ) or "high")
        )
    elif patterns and _matches(model_name, patterns):
        resolved_effort = "high"
    else:
        resolved_effort = default_reasoning_effort_for(
            provider_name,
            model_name,
            default_off_patterns=default_off,
            minimal_not_off_patterns=minimal_not_off,
        )

    kwargs: dict[str, Any] = {}
    if resolved_effort:
        # 专有字段能表达的语义（minimal/none）与 enable_thinking 样式不再叠加顶层
        # reasoning_effort，避免发送相互矛盾的载荷。
        suppress_top_level = bool(
            thinking_style
            and (resolved_effort in {"minimal", "none"} or thinking_style == "enable_thinking")
        )
        if not suppress_top_level:
            kwargs["reasoning_effort"] = resolved_effort

    if thinking_style and resolved_effort is not None:
        enabled = resolved_effort != "none" and resolved_effort != "minimal"
        extra = THINKING_STYLE_MAP.get(thinking_style, lambda _enabled: None)(enabled)
        if extra:
            kwargs.setdefault("extra_body", {}).update(extra)
    return kwargs


def reasoning_style_for(spec: Any, provider_id: str | None) -> str | None:
    """只读派生给前端展示的推理样式（D6：不落库、不接受写入）。"""
    style = str(getattr(spec, "thinkingStyle", "") or "")
    if not style:
        style = PROVIDER_THINKING_STYLES.get(_spec_name(spec, provider_id), "")
    return style or None


__all__ = [
    "THINKING_STYLE_MAP",
    "build_reasoning_kwargs",
    "default_reasoning_effort_for",
    "normalize_effort",
    "reasoning_style_for",
]
