"""模型能力解析层测试：思考档位支持 + 上下文窗口解析。

全部输入用简单假对象或真实 pydantic 模型，不触网、不读凭证。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.providers.llm.registry import ProviderSpec
from app.schemas.model_config import ApiFormat, ModelConnection, ModelProfile, ModelProtocol
from app.services.model_capabilities import (
    resolve_context_window,
    resolve_reasoning_support,
)


def make_profile(**overrides) -> ModelProfile:
    base = dict(
        id="p1",
        connectionId="c1",
        displayName="档案",
        modelId="some-model",
        reasoningEnabled=True,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return ModelProfile(**base)


def make_connection(provider_id: str | None, api_format: ApiFormat = ApiFormat.openai_chat) -> ModelConnection:
    return ModelConnection(
        id="c1",
        displayName="连接",
        protocol=ModelProtocol.openai_chat,
        baseUrl="https://example.invalid",
        providerId=provider_id,
        apiFormat=api_format,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )


# ---------- 布尔样式（deepseek 类：thinking_type） ----------

def test_boolean_style_thinking_type_deepseek():
    profile = make_profile(modelId="deepseek-chat")
    connection = make_connection("deepseek")
    spec = ProviderSpec(providerId="deepseek", label="DeepSeek", thinkingStyle="thinking_type")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["supported"] is True
    assert result["levels"] == [{"value": "high", "label": "高"}]
    assert result["style"] == "thinking_type"
    assert result["source"] == "registry"
    assert result["note"] == "该供应商用布尔开关表达思考（开=高）。"


def test_boolean_style_via_provider_table_enable_thinking():
    # spec 未声明 thinkingStyle，样式按 providerId 从供应商表回退
    profile = make_profile(modelId="qwen3-max")
    connection = make_connection("dashscope")
    spec = ProviderSpec(providerId="dashscope", label="DashScope")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["style"] == "enable_thinking"
    assert result["levels"] == [{"value": "high", "label": "高"}]
    assert result["supported"] is True


# ---------- 档案显式关闭 ----------

def test_reasoning_disabled_by_profile():
    profile = make_profile(modelId="deepseek-chat", reasoningEnabled=False)
    connection = make_connection("deepseek")
    spec = ProviderSpec(providerId="deepseek", label="DeepSeek", thinkingStyle="thinking_type")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result == {
        "supported": False,
        "levels": [],
        "default": None,
        "style": "thinking_type",
        "source": "profile",
        "note": "该档案已关闭思考。",
    }


# ---------- anthropic 六档 ----------

def test_anthropic_budget_six_levels():
    profile = make_profile(modelId="claude-sonnet-4-5")
    connection = make_connection("anthropic", ApiFormat.anthropic)
    spec = ProviderSpec(providerId="anthropic", label="Anthropic", backend="anthropic")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["style"] == "anthropic_budget"
    assert result["supported"] is True
    assert result["source"] == "registry"
    assert [item["value"] for item in result["levels"]] == [
        "minimal", "low", "medium", "high", "xhigh", "max",
    ]
    assert [item["label"] for item in result["levels"]] == ["最低", "低", "中", "高", "很高", "最高"]


def test_anthropic_style_via_api_format_even_if_backend_openai():
    # 连接格式 anthropic 生效即走预算表达，即便 spec 后端写的是别的
    profile = make_profile(modelId="glm-4.6")
    connection = make_connection("zhipu", ApiFormat.anthropic)
    spec = ProviderSpec(providerId="zhipu", label="Zhipu", backend="openai_compat")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["style"] == "anthropic_budget"


# ---------- openai_effort 基础四档 / codex 追加 xhigh ----------

def test_openai_effort_base_four_levels():
    profile = make_profile(modelId="gpt-5.1", reasoningEnabled=None)
    connection = make_connection("openai")
    spec = ProviderSpec(providerId="openai", label="OpenAI", thinkingStyle="reasoning_effort")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["supported"] is True
    assert result["style"] == "openai_effort"
    assert result["source"] == "registry"
    assert [item["value"] for item in result["levels"]] == ["minimal", "low", "medium", "high"]


def test_openai_effort_codex_appends_xhigh_by_model_name():
    # 档案显式开启（source=profile）时，模型名含 codex → 档位追加 xhigh
    profile = make_profile(modelId="gpt-5.1-codex", reasoningEnabled=True)
    connection = make_connection("openai_codex")
    spec = ProviderSpec(providerId="openai_codex", label="Codex")

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["supported"] is True
    assert result["source"] == "profile"
    values = [item["value"] for item in result["levels"]]
    assert values == ["minimal", "low", "medium", "high", "xhigh"]
    assert result["default"] is None


def test_openai_effort_codex_appends_xhigh_by_patterns():
    profile = make_profile(modelId="gpt-5.1-codex-mini", reasoningEnabled=None)
    connection = make_connection("custom")
    spec = ProviderSpec(
        providerId="custom", label="Custom",
        reasoningModelPatterns=("codex",),
    )

    result = resolve_reasoning_support(profile, connection, spec)
    assert "xhigh" in [item["value"] for item in result["levels"]]


def test_default_effort_normalized_and_filtered():
    connection = make_connection("openai")
    spec = ProviderSpec(providerId="openai", label="OpenAI")

    # reasoningEffort="minimum" 无法过 pydantic 枚举（归一发生在解析层），
    # 用 SimpleNamespace 走 normalize_effort 路径：minimum → minimal，在基础四档内
    # 显式开启（source=profile）保证进入 openai_effort 正常分支而非 unsupported 分支
    loose = SimpleNamespace(modelId="gpt-5.1", reasoningEnabled=True, reasoningEffort="minimum")
    assert resolve_reasoning_support(loose, connection, spec)["default"] == "minimal"

    # effort=none 不在任何档位集合里 → default 为 None
    profile_off = make_profile(modelId="gpt-5.1", reasoningEffort="none")
    result_off = resolve_reasoning_support(profile_off, connection, spec)
    assert result_off["default"] is None
    # 未给 effort → default 为 None
    assert resolve_reasoning_support(
        make_profile(modelId="gpt-5.1"), connection, spec
    )["default"] is None


# ---------- 未标注模型 unsupported ----------

def test_unannotated_model_unsupported():
    profile = make_profile(modelId="totally-unknown-model", reasoningEnabled=None)
    connection = make_connection("openai")
    spec = ProviderSpec(providerId="openai", label="OpenAI")  # 无 thinkingStyle、无 patterns

    result = resolve_reasoning_support(profile, connection, spec)
    assert result["supported"] is False
    assert result["levels"] == []
    assert result["source"] == "registry"
    assert result["note"] == "注册表未标注该模型支持思考；可在档案中显式开启。"


# ---------- 上下文窗口 ----------

def test_context_window_profile_overrides():
    profile = make_profile(modelId="claude-sonnet-4-5", contextTokens=123456)
    result = resolve_context_window(profile, None, profile.modelId)
    assert result == {"tokens": 123456, "source": "profile", "note": None}


def test_context_window_model_table_hit():
    profile = make_profile(modelId="claude-sonnet-4-5")
    result = resolve_context_window(profile, None, "claude-sonnet-4-5")
    assert result["tokens"] == 200000
    assert result["source"] == "model-table"
    assert "claude" in result["note"]


def test_context_window_specific_family_before_generic():
    # gpt-5 表 400000，命中 gpt-5 前缀而非任何泛化条目
    result = resolve_context_window(None, None, "gpt-5.1-mini")
    assert result["tokens"] == 400000
    # gpt-4.1 在 gpt-4o 之前定义，避免 4o 条目先命中
    assert resolve_context_window(None, None, "gpt-4.1")["tokens"] == 1_000_000


def test_context_window_unknown_model():
    result = resolve_context_window(None, None, "weird-unknown-9000")
    assert result == {"tokens": None, "source": "unknown", "note": None}


# ---------- None 输入不抛异常 ----------

def test_none_inputs_do_not_raise():
    profile = make_profile(modelId="mystery-model", reasoningEnabled=None)
    result = resolve_reasoning_support(profile, None, None)
    assert result["style"] == "openai_effort"
    assert isinstance(result["supported"], bool)

    # 完全空对象也不抛
    empty = SimpleNamespace()
    assert resolve_context_window(empty, None, None)["source"] == "unknown"
    support = resolve_reasoning_support(empty, None, None)
    assert support["source"] == "registry"


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("o3-mini", 200000),
        ("o4-mini", 200000),
        ("deepseek-v4", 128000),
        ("qwen3-max", 128000),
        ("qwq-32b", 128000),
        ("gemini-2.5-pro", 1000000),
        ("glm-4.6", 128000),
        ("kimi-k2", 128000),
        ("grok-4", 128000),
        ("mistral-large", 128000),
        ("llama-3.1-70b", 128000),
        ("ernie-4.5", 128000),
    ],
)
def test_context_window_full_family_table(model_id, expected):
    result = resolve_context_window(None, None, model_id)
    assert result["tokens"] == expected
    assert result["source"] == "model-table"
