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
    reasoning_patterns_for,
    reasoning_style_for,
)

# 布尔开关样式：只有「开/关」；档位收敛为单一「高」
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

_EFFORT_LABELS = {
    "minimal": "最低",
    "low": "低",
    "medium": "中",
    "high": "高",
    "xhigh": "很高",
    "max": "最高",
}

#: 精确模型 ID → 已知上下文窗口（不是族匹配；仅收确实可核对的模型）。
#: 解析顺序：档案手填 > 本表 > 模型族暂估 > unknown。
MODEL_CONTEXT_OVERRIDES: dict[str, int] = {
    "deepseek-flash": 1_000_000,
    "deepseek-v4-flash": 1_000_000,
    "deepseek-v4.1-flash": 1_000_000,
    "deepseek-v4-pro": 1_000_000,
}

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


def _level_values(levels: list[dict[str, str]]) -> set[str]:
    return {item["value"] for item in levels}


def _append_profile_effort(levels: list[dict[str, str]], effort: str | None) -> None:
    """把档案声明的档位补进可选表（如 flash 的 max），保证「默认（最高）」可见可选。"""
    if not effort or effort == "none" or effort in _level_values(levels):
        return
    label = _EFFORT_LABELS.get(effort)
    if label:
        levels.append({"value": effort, "label": label})


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
    """解析思考档位支持：supported / selectable / levels / default / style / source / note。

    语义（2026-10-22 起）：

    - ``selectable``：是否在对话页展示思考强度控件。除档案显式关闭思考外恒为 true，
      避免切换到未声明支持的模型时控件直接消失；未验证模型仍可强制本轮档位。
    - ``supported``：是否**已知**支持思考（档案开启 / 注册表声明 / 模型族命中）。
    - ``levels``：selectable 时始终非空；档案声明的超集档位（如 max）会补进表内。
    """
    style = _resolve_style(profile, connection, spec)
    effort = normalize_effort(getattr(profile, "reasoningEffort", None))
    if effort == "none":
        effort = None

    # 档案显式关闭思考：唯一不展示控件的分支
    if getattr(profile, "reasoningEnabled", None) is False:
        return {
            "supported": False,
            "selectable": False,
            "levels": [],
            "default": None,
            "style": style,
            "source": "profile",
            "note": "该档案已关闭思考。",
        }

    if style in _BOOLEAN_STYLES:
        levels = [{"value": "high", "label": "高"}]
        _append_profile_effort(levels, effort)
        return {
            "supported": True,
            "selectable": True,
            "levels": levels,
            "default": effort if effort in _level_values(levels) else None,
            "style": style,
            "source": "registry",
            "note": "该供应商用布尔开关表达思考（开=高）。",
        }

    if style == "anthropic_budget":
        levels = _levels_dict(_ANTHROPIC_LEVELS)
        return {
            "supported": True,
            "selectable": True,
            "levels": levels,
            "default": effort if effort in _level_values(levels) else None,
            "style": style,
            "source": "registry",
            "note": "用 thinking 预算量级表达档位。",
        }

    # openai_effort：基础四档；codex 追加 xhigh；档案声明的 max 等也补进表内
    model_name = _model_name(profile)
    patterns = reasoning_patterns_for(spec, getattr(connection, "providerId", None))
    is_codex = "codex" in model_name
    levels = _levels_dict(_OPENAI_BASE_LEVELS)
    if is_codex:
        levels.append({"value": "xhigh", "label": "很高"})
    _append_profile_effort(levels, effort)
    default = effort if effort in _level_values(levels) else None

    supported: bool
    source: str
    note: str | None = None
    if getattr(profile, "reasoningEnabled", None) is True:
        supported, source = True, "profile"
    elif _patterns_hit(patterns, model_name):
        supported, source = True, "model-family"
        note = "按模型族推断该模型支持思考；可在档案中显式关闭。"
    else:
        # 契约固定：未标注支持也保留控件（selectable=true），由教师决定是否强制档位
        return {
            "supported": False,
            "selectable": True,
            "levels": levels,
            "default": default,
            "style": "openai_effort",
            "source": "fallback",
            "note": "未在注册表标注该模型支持思考；档位作为本轮覆盖发送，上游可能忽略或报错。",
        }

    return {
        "supported": supported,
        "selectable": True,
        "levels": levels,
        "default": default,
        "style": "openai_effort",
        "source": source,
        "note": note,
    }


def _exact_model_name(model_id: str | None) -> str:
    """模型 ID 归一：小写、去空白、取网关前缀后的最后一段（deepseek/deepseek-flash → deepseek-flash）。"""
    name = str(model_id or "").strip().lower()
    return name.rsplit("/", 1)[-1]


def resolve_context_window(profile: Any, spec: Any, model_id: str | None) -> dict:
    """解析上下文窗口：档案手填 > 精确模型 ID 已知值 > 模型族暂估 > unknown。

    2026-10-22 起不再只依赖模型族表：`deepseek-flash` 等可核对模型直接返回 1M，
    避免档案为空时被 `deepseek` 泛条目的 128k 粗估覆盖。
    """
    tokens = getattr(profile, "contextTokens", None)
    if tokens:
        return {"tokens": int(tokens), "source": "profile", "note": None}

    name = _exact_model_name(model_id or getattr(profile, "modelId", None))
    override = MODEL_CONTEXT_OVERRIDES.get(name)
    if override:
        return {
            "tokens": override,
            "source": "model",
            "note": f"按模型 ID 精确匹配的已知上下文长度（{name}）；可在档案手填覆盖。",
        }

    for pattern, size in MODEL_CONTEXT_WINDOWS:
        if pattern in name:
            return {
                "tokens": size,
                "source": "model-table",
                "note": f"按模型族粗估（命中 {pattern}），可在该模型档案的手填上下文长度中覆盖。",
            }
    return {"tokens": None, "source": "unknown", "note": None}


__all__ = [
    "MODEL_CONTEXT_OVERRIDES",
    "MODEL_CONTEXT_WINDOWS",
    "resolve_context_window",
    "resolve_reasoning_support",
]
