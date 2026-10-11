"""模型能力解析层（纯函数、不触网、不读凭证）。

把「思考档位支持」与「上下文窗口」两个只读派生字段集中在这里计算，
供 `model_views.profile_view` 下发；前端按冻结契约消费字段名，
本模块是唯一解析真值，不落库、不接受写入。

任何输入都可能是 None / 缺字段：所有 getattr 带默认值，不得抛异常。
"""

from __future__ import annotations

from typing import Any

from app.providers.llm.reasoning_params import (
    normalize_effort,
    reasoning_style_for,
)

# 布尔开关样式：只有「开/关」，界面收敛为单一「高」档
_BOOLEAN_STYLES = ("thinking_type", "enable_thinking", "reasoning_split")

_ANTHROPIC_LEVELS = (
    ("minimal", "最低"),
    ("low", "低"),
    ("medium", "中"),
    ("high", "高"),
    ("xhigh", "很高"),
    ("max", "最高"),
)

_OPENAI_BASE_LEVELS = (
    ("minimal", "最低"),
    ("low", "低"),
    ("medium", "中"),
    ("high", "高"),
)

#: 模型族 → 上下文窗口粗估（小写子串匹配；具体条目必须排在泛条目之前）
MODEL_CONTEXT_WINDOWS: tuple[tuple[str, int], ...] = (
    ("claude", 200_000),
    ("gpt-5", 400_000),
    ("gpt-4.1", 1_000_000),
    ("gpt-4o", 128_000),
    ("o3", 200_000),
    ("o4", 200_000),
    ("deepseek", 128_000),
    ("qwen", 128_000),
    ("qwq", 128_000),
    ("gemini", 1_000_000),
    ("glm", 128_000),
    ("kimi", 128_000),
    ("grok", 128_000),
    ("mistral", 128_000),
    ("llama", 128_000),
    ("ernie", 128_000),
)


def _levels_dict(levels: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"value": value, "label": label} for value, label in levels]


def _model_name(profile: Any) -> str:
    return str(getattr(profile, "modelId", "") or "").lower()


def _patterns_hit(patterns: Any, model_name: str) -> bool:
    for pattern in tuple(patterns or ()):
        if str(pattern).lower() in model_name:
            return True
    return False


def _resolve_style(profile: Any, connection: Any, spec: Any) -> str:
    """思考档位表达样式：anthropic 连接优先预算表达，否则按注册表，兜底 openai effort。"""
    fmt = getattr(connection, "apiFormat", None)
    fmt_value = getattr(fmt, "value", fmt) if fmt is not None else None
    backend = str(getattr(spec, "backend", "") or "")
    if connection is not None and (fmt_value == "anthropic" or backend == "anthropic"):
        return "anthropic_budget"
    style = reasoning_style_for(spec, getattr(connection, "providerId", None))
    return style or "openai_effort"


def resolve_reasoning_support(profile: Any, connection: Any, spec: Any) -> dict:
    """解析思考档位支持：supported / levels / default / style / source / note。"""
    style = _resolve_style(profile, connection, spec)

    # 档案显式关闭思考：仅提示关闭，不再给出档位
    if getattr(profile, "reasoningEnabled", None) is False:
        return {
            "supported": False,
            "levels": [],
            "default": None,
            "style": style,
            "source": "profile",
            "note": "该档案已关闭思考。",
        }

    model_name = _model_name(profile)

    if style in _BOOLEAN_STYLES:
        return {
            "supported": True,
            "levels": [{"value": "high", "label": "高"}],
            "default": None,
            "style": style,
            "source": "registry",
            "note": "该供应商用布尔开关表达思考（开=高）。",
        }

    if style == "anthropic_budget":
        return {
            "supported": True,
            "levels": _levels_dict(_ANTHROPIC_LEVELS),
            "default": None,
            "style": style,
            "source": "registry",
            "note": "用 thinking 预算量级表达档位。",
        }

    # openai_effort：基础四档；模型名或命中模式含 codex 时追加 xhigh
    patterns = tuple(getattr(spec, "reasoningModelPatterns", ()) or ())
    is_codex = "codex" in model_name
    if not is_codex and patterns and _patterns_hit(patterns, model_name):
        is_codex = any("codex" in str(p).lower() for p in patterns)

    supported: bool
    source: str
    note: str | None = None
    if getattr(profile, "reasoningEnabled", None) is True:
        supported, source = True, "profile"
    elif spec is not None and (
        bool(str(getattr(spec, "thinkingStyle", "") or "").strip())
        or _patterns_hit(patterns, model_name)
    ):
        supported, source = True, "registry"
    else:
        # 契约固定：未标注支持时不下发任何档位
        return {
            "supported": False,
            "levels": [],
            "default": None,
            "style": "openai_effort",
            "source": "registry",
            "note": "注册表未标注该模型支持思考；可在档案中显式开启。",
        }

    levels = _levels_dict(_OPENAI_BASE_LEVELS)
    if is_codex:
        levels.append({"value": "xhigh", "label": "很高"})

    default: str | None = None
    effort = normalize_effort(getattr(profile, "reasoningEffort", None))
    if effort is not None and effort in {item["value"] for item in levels}:
        default = effort

    return {
        "supported": supported,
        "levels": levels,
        "default": default,
        "style": "openai_effort",
        "source": source,
        "note": note,
    }


def resolve_context_window(profile: Any, spec: Any, model_id: str | None) -> dict:
    """解析上下文窗口：档案手填优先，其次按模型族粗估，未知则返回 unknown。"""
    tokens = getattr(profile, "contextTokens", None)
    if tokens:
        return {"tokens": int(tokens), "source": "profile", "note": None}

    name = str(model_id or "").lower()
    for pattern, size in MODEL_CONTEXT_WINDOWS:
        if pattern in name:
            return {
                "tokens": size,
                "source": "model-table",
                "note": f"按模型族粗估（命中 {pattern}），可在该模型档案的手填上下文长度中覆盖。",
            }
    return {"tokens": None, "source": "unknown", "note": None}


__all__ = [
    "MODEL_CONTEXT_WINDOWS",
    "resolve_context_window",
    "resolve_reasoning_support",
]
