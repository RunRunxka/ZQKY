"""供应商注册表（contract-v1）：38 条元数据、别名、格式钳制与 backend 派生。"""

from __future__ import annotations

import pytest

from app.providers.llm.registry import (
    BACKEND_ANTHROPIC,
    BACKEND_AZURE_OPENAI,
    BACKEND_CODEBUDDY,
    BACKEND_GITHUB_COPILOT,
    BACKEND_OPENAI_CODEX,
    BACKEND_OPENAI_COMPAT,
    FORMAT_ANTHROPIC,
    PROVIDERS,
    api_format_for_provider,
    canonical_provider_id,
    effective_backend,
    find_by_model,
    find_provider,
    model_overrides_for,
    strip_provider_prefix,
)

# STATUS 第6节列出的 38 条（36 现行 + 2 legacy）
EXPECTED_PROVIDER_IDS = {
    "custom",
    "custom_anthropic",
    "azure_openai",
    "openrouter",
    "orcarouter",
    "edenai",
    "aihubmix",
    "siliconflow",
    "novita",
    "atlascloud",
    "volcengine",
    "volcengine_coding_plan",
    "byteplus",
    "byteplus_coding_plan",
    "anthropic",
    "openai",
    "openai_codex",
    "github_copilot",
    "codebuddy",
    "deepseek",
    "gemini",
    "zhipu",
    "dashscope",
    "moonshot",
    "minimax",
    "minimax_anthropic",
    "mistral",
    "stepfun",
    "xiaomi_mimo",
    "vllm",
    "ollama",
    "lm_studio",
    "llama_cpp",
    "lemonade",
    "ovms",
    "nvidia_nim",
    "groq",
    "qianfan",
}


def test_registry_has_exactly_38_entries():
    ids = {spec.providerId for spec in PROVIDERS}
    assert len(PROVIDERS) == 38
    assert ids == EXPECTED_PROVIDER_IDS


def test_backend_distribution_matches_reference():
    counts: dict[str, int] = {}
    for spec in PROVIDERS:
        counts[spec.backend] = counts.get(spec.backend, 0) + 1
    assert counts[BACKEND_OPENAI_COMPAT] == 31
    assert counts[BACKEND_ANTHROPIC] == 3
    assert counts[BACKEND_AZURE_OPENAI] == 1
    assert counts[BACKEND_OPENAI_CODEX] == 1
    assert counts[BACKEND_GITHUB_COPILOT] == 1
    assert counts[BACKEND_CODEBUDDY] == 1


def test_only_two_legacy_entries():
    legacy = {spec.providerId for spec in PROVIDERS if spec.isLegacy}
    assert legacy == {"custom_anthropic", "minimax_anthropic"}
    assert find_provider("custom_anthropic").legacyOf == ("custom", FORMAT_ANTHROPIC)


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("azure", "azure_openai"),
        ("azure-openai", "azure_openai"),
        ("AzureOpenAI", "azure_openai"),
        ("claude", "anthropic"),
        ("google", "gemini"),
        ("google_genai", "gemini"),
        ("openai-compatible", "custom"),
        ("workbuddy", "codebuddy"),
        ("github-copilot", "github_copilot"),
        ("lm-studio", "lm_studio"),
        ("orca_router", "orcarouter"),
        ("atlas-cloud", "atlascloud"),
        ("volcengineCodingPlan", "volcengine_coding_plan"),
    ],
)
def test_aliases_resolve_to_canonical_ids(alias, expected):
    assert canonical_provider_id(alias) == expected
    assert find_provider(alias) is not None


def test_unknown_provider_has_no_spec():
    assert find_provider("not-a-real-provider") is None
    assert canonical_provider_id(None) is None


def test_api_formats_follow_reference_rules():
    # OAuth / Azure / Codex / Copilot 无可选格式
    assert find_provider("azure_openai").apiFormats == ()
    assert find_provider("openai_codex").apiFormats == ()
    assert find_provider("github_copilot").apiFormats == ()
    # 原生 Anthropic 只有 anthropic
    assert find_provider("anthropic").apiFormats == (FORMAT_ANTHROPIC,)
    assert find_provider("anthropic").defaultApiFormat == FORMAT_ANTHROPIC
    # OpenAI 兼容默认三值
    assert find_provider("openai").apiFormats == ("auto", "openai_chat", "openai_responses")
    # custom 与声明了 anthropic base 的 minimax 追加 anthropic
    assert FORMAT_ANTHROPIC in find_provider("custom").apiFormats
    assert FORMAT_ANTHROPIC in find_provider("minimax").apiFormats
    assert FORMAT_ANTHROPIC not in find_provider("mistral").apiFormats


def test_api_format_is_clamped_to_provider_choices():
    assert api_format_for_provider("responses", find_provider("minimax")) == "auto"
    assert api_format_for_provider("openai_responses", find_provider("minimax")) == "openai_responses"
    # anthropic 格式在 openai 兼容供应商上切换 backend
    assert effective_backend(find_provider("minimax"), "anthropic") == BACKEND_ANTHROPIC
    assert effective_backend(find_provider("minimax"), "openai_chat") == BACKEND_OPENAI_COMPAT
    # 无选择权的供应商被钳到默认
    assert api_format_for_provider("openai_chat", find_provider("azure_openai")) == "auto"


def test_minimax_anthropic_format_has_distinct_base_url():
    spec = find_provider("minimax")
    assert spec.defaultApiBaseFor("anthropic") == "https://api.minimax.io/anthropic"
    assert spec.defaultApiBaseFor("auto") == "https://api.minimax.io/v1"


def test_model_prefix_stripping_only_when_declared():
    assert strip_provider_prefix("openai/gpt-4o", find_provider("aihubmix")) == "gpt-4o"
    assert strip_provider_prefix("deepseek-chat", find_provider("deepseek")) == "deepseek-chat"


def test_model_overrides_delete_parameter_for_kimi():
    # None 表示"发送时删除该参数"
    assert model_overrides_for("kimi-k3", find_provider("openai")) == {"temperature": None}
    assert model_overrides_for("k3", find_provider("openai")) == {"temperature": None}
    # 精确匹配：k30 不应命中 =k3
    assert model_overrides_for("k30", find_provider("openai")) == {}
    assert model_overrides_for("moonshot-v1-8k", find_provider("moonshot")) == {}


def test_find_by_model_matches_standard_vendors():
    assert find_by_model("deepseek-chat").providerId == "deepseek"
    assert find_by_model("claude-sonnet-4").providerId == "anthropic"
    assert find_by_model("qwen-max").providerId == "dashscope"


def test_default_api_bases_match_reference():
    assert find_provider("deepseek").defaultApiBase == "https://api.deepseek.com"
    assert find_provider("ollama").defaultApiBase == "http://localhost:11434/v1"
    assert find_provider("qianfan").defaultApiBase == "https://qianfan.baidubce.com/v2"


def test_local_and_oauth_providers_do_not_require_key():
    assert find_provider("ollama").authMode == "none"
    assert find_provider("openai_codex").authMode == "oauth"
    assert find_provider("deepseek").authMode == "api_key"
    assert find_provider("deepseek").requires_key is True
