"""供应商注册表：38 条参考条目的单一真值（contract-v1）。

参考：固定 DeepTutor `deeptutor/services/provider_registry.py:175-567`
（v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202，Apache-2.0）。本文件为
本项目自有实现，按参考语义复刻元数据；**不启用**参考的进程级环境变量注入、
`detect_by_*` 指纹自动识别与 `env_key`/`env_extras` 写入。

38 条 = 36 现行 + 2 legacy（`custom_anthropic`、`minimax_anthropic`）。
顺序与参考一致：direct → gateway → standard → local → auxiliary。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# backend 取值：与参考 provider_factory.py 的六种分派一一对应
BACKEND_OPENAI_COMPAT = "openai_compat"
BACKEND_ANTHROPIC = "anthropic"
BACKEND_AZURE_OPENAI = "azure_openai"
BACKEND_OPENAI_CODEX = "openai_codex"
BACKEND_GITHUB_COPILOT = "github_copilot"
BACKEND_CODEBUDDY = "codebuddy"

BACKENDS = frozenset(
    {
        BACKEND_OPENAI_COMPAT,
        BACKEND_ANTHROPIC,
        BACKEND_AZURE_OPENAI,
        BACKEND_OPENAI_CODEX,
        BACKEND_GITHUB_COPILOT,
        BACKEND_CODEBUDDY,
    }
)

# API 格式常量（对参考 api_formats / default_api_format 的等价物）
FORMAT_AUTO = "auto"
FORMAT_OPENAI_CHAT = "openai_chat"
FORMAT_OPENAI_RESPONSES = "openai_responses"
FORMAT_ANTHROPIC = "anthropic"
API_FORMAT_VALUES = frozenset({FORMAT_AUTO, FORMAT_OPENAI_CHAT, FORMAT_OPENAI_RESPONSES, FORMAT_ANTHROPIC})
OPENAI_API_FORMATS: tuple[str, ...] = (FORMAT_AUTO, FORMAT_OPENAI_CHAT, FORMAT_OPENAI_RESPONSES)

# provider_mode（参考 ProviderSpec.mode）
MODE_STANDARD = "standard"
MODE_GATEWAY = "gateway"
MODE_LOCAL = "local"
MODE_DIRECT = "direct"
MODE_OAUTH = "oauth"

# 认证方式（参考 auth_mode 的扩展：本机免 Key 与专用认证分开表达）
AUTH_API_KEY = "api_key"
AUTH_OAUTH = "oauth"
AUTH_NONE = "none"


@dataclass(frozen=True)
class ProviderSpec:
    """单条供应商元数据。字段语义对齐参考 ProviderSpec，但剔除进程全局项。"""

    providerId: str
    label: str
    backend: str = BACKEND_OPENAI_COMPAT
    keywords: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    is_gateway: bool = False
    is_local: bool = False
    is_direct: bool = False
    is_oauth: bool = False
    requires_key: bool = True
    defaultApiBase: str = ""
    apiBaseByFormat: tuple[tuple[str, str], ...] = ()
    legacyOf: tuple[str, ...] = ()
    stripModelPrefix: bool = False
    supportsMaxCompletionTokens: bool = False
    supportsPromptCaching: bool = False
    supportsStreamOptions: bool = True
    thinkingStyle: str = ""
    reasoningModelPatterns: tuple[str, ...] = ()
    nativeWebSearchModels: tuple[str, ...] = ()
    modelOverrides: tuple[tuple[str, dict[str, Any]], ...] = ()
    exactModelIds: tuple[str, ...] = ()
    # gemini 族默认关闭思考；其中一部分最低只能 minimal（参考 reasoning_params.py:29-38）
    defaultOffReasoning: tuple[str, ...] = ()
    minimalNotOff: tuple[str, ...] = ()
    # 参考 env_extras 仅用于文档说明；本实现不写进程环境变量
    legacyEnvKey: str = ""

    @property
    def mode(self) -> str:
        if self.is_oauth:
            return MODE_OAUTH
        if self.is_direct:
            return MODE_DIRECT
        if self.is_gateway:
            return MODE_GATEWAY
        if self.is_local:
            return MODE_LOCAL
        return MODE_STANDARD

    @property
    def authMode(self) -> str:
        if self.is_oauth:
            return AUTH_OAUTH
        if not self.requires_key:
            return AUTH_NONE
        return AUTH_API_KEY

    @property
    def supportsWireApiSelection(self) -> bool:
        return self.backend == BACKEND_OPENAI_COMPAT and not self.is_oauth

    @property
    def isLegacy(self) -> bool:
        return bool(self.legacyOf)

    @property
    def apiFormats(self) -> tuple[str, ...]:
        """该供应商可选 API 格式；空元组表示格式固定、UI 不提供选择（D2）。"""
        if self.is_oauth or self.backend in {BACKEND_AZURE_OPENAI, BACKEND_OPENAI_CODEX, BACKEND_GITHUB_COPILOT}:
            return ()
        if self.backend == BACKEND_ANTHROPIC:
            return (FORMAT_ANTHROPIC,)
        if self.backend != BACKEND_OPENAI_COMPAT:
            return ()
        formats: tuple[str, ...] = OPENAI_API_FORMATS
        if self.providerId == "custom" or FORMAT_ANTHROPIC in dict(self.apiBaseByFormat):
            formats = (*formats, FORMAT_ANTHROPIC)
        return formats

    @property
    def defaultApiFormat(self) -> str:
        return FORMAT_ANTHROPIC if self.backend == BACKEND_ANTHROPIC else FORMAT_AUTO

    def defaultApiBaseFor(self, api_format: str | None) -> str:
        return dict(self.apiBaseByFormat).get(api_format or "", self.defaultApiBase)


# ---------------------------------------------------------------------------
# 显式别名表（D1：别名只来自此表，keywords 是匹配词，二者分开）
# ---------------------------------------------------------------------------

PROVIDER_ALIASES: dict[str, str] = {
    "azure": "azure_openai",
    "azure-openai": "azure_openai",
    "azureopenai": "azure_openai",
    "google": "gemini",
    "google_genai": "gemini",
    "claude": "anthropic",
    "openai_compatible": "custom",
    "openai-compatible": "custom",
    "anthropic_compatible": "custom_anthropic",
    "anthropic-compatible": "custom_anthropic",
    "volcenginecodingplan": "volcengine_coding_plan",
    "bytepluscodingplan": "byteplus_coding_plan",
    "github-copilot": "github_copilot",
    "openai-codex": "openai_codex",
    "codebuddy-code": "codebuddy",
    "codebuddy_code": "codebuddy",
    "workbuddy": "codebuddy",
    "lm-studio": "lm_studio",
    "atlas": "atlascloud",
    "atlas_cloud": "atlascloud",
    "atlas-cloud": "atlascloud",
    "eden_ai": "edenai",
    "novita_ai": "novita",
    "orca_router": "orcarouter",
    "orca-router": "orcarouter",
    "openai_compat": "custom",
}


def _snake(value: str) -> str:
    """参考 hashlib 无关的 to_snake 等价：连字符/空格归一为下划线。"""
    return re.sub(r"[\s\-]+", "_", value.strip()).lower()


def canonical_provider_id(name: str | None) -> str | None:
    """归一 incoming providerId 与 legacy 别名（参考 canonical_provider_name）。"""
    if not name:
        return None
    key = name.strip()
    if not key:
        return None
    key = _snake(key)
    return PROVIDER_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# PROVIDERS —— 注册表本体
# ---------------------------------------------------------------------------

PROVIDERS: tuple[ProviderSpec, ...] = (
    # === Direct：用户提供全部信息，不自动识别 ===============================
    ProviderSpec(
        providerId="custom",
        label="自定义（OpenAI 兼容）",
        backend=BACKEND_OPENAI_COMPAT,
        is_direct=True,
        keywords=(),
    ),
    ProviderSpec(
        providerId="custom_anthropic",
        label="自定义（Anthropic API）",
        backend=BACKEND_ANTHROPIC,
        is_direct=True,
        keywords=(),
        legacyOf=("custom", FORMAT_ANTHROPIC),
    ),
    ProviderSpec(
        providerId="azure_openai",
        label="Azure OpenAI",
        backend=BACKEND_AZURE_OPENAI,
        is_direct=True,
        keywords=("azure", "azure_openai"),
    ),
    # === Gateway：聚合/网关 ================================================
    ProviderSpec(
        providerId="openrouter",
        label="OpenRouter",
        is_gateway=True,
        keywords=("openrouter",),
        defaultApiBase="https://openrouter.ai/api/v1",
        supportsPromptCaching=True,
    ),
    ProviderSpec(
        providerId="orcarouter",
        label="OrcaRouter",
        is_gateway=True,
        keywords=("orcarouter", "orca_router", "orca router"),
        defaultApiBase="https://api.orcarouter.ai/v1",
    ),
    ProviderSpec(
        providerId="edenai",
        label="Eden AI",
        is_gateway=True,
        keywords=("edenai",),
        defaultApiBase="https://api.edenai.run/v3",
    ),
    ProviderSpec(
        providerId="aihubmix",
        label="AiHubMix",
        is_gateway=True,
        keywords=("aihubmix",),
        defaultApiBase="https://aihubmix.com/v1",
        stripModelPrefix=True,
    ),
    ProviderSpec(
        providerId="siliconflow",
        label="SiliconFlow",
        is_gateway=True,
        keywords=("siliconflow",),
        defaultApiBase="https://api.siliconflow.cn/v1",
    ),
    ProviderSpec(
        providerId="novita",
        label="Novita AI",
        is_gateway=True,
        keywords=("novita", "novita-ai", "novita ai"),
        defaultApiBase="https://api.novita.ai/openai",
    ),
    ProviderSpec(
        providerId="atlascloud",
        label="Atlas Cloud",
        is_gateway=True,
        keywords=("atlascloud", "atlas-cloud", "atlas cloud"),
        defaultApiBase="https://api.atlascloud.ai/v1",
    ),
    ProviderSpec(
        providerId="volcengine",
        label="VolcEngine（火山方舟）",
        is_gateway=True,
        keywords=("volcengine", "volces", "ark"),
        defaultApiBase="https://ark.cn-beijing.volces.com/api/v3",
        thinkingStyle="thinking_type",
    ),
    ProviderSpec(
        providerId="volcengine_coding_plan",
        label="VolcEngine Coding Plan",
        is_gateway=True,
        keywords=("volcengine-plan",),
        defaultApiBase="https://ark.cn-beijing.volces.com/api/coding/v3",
        stripModelPrefix=True,
        thinkingStyle="thinking_type",
    ),
    ProviderSpec(
        providerId="byteplus",
        label="BytePlus",
        is_gateway=True,
        keywords=("byteplus",),
        defaultApiBase="https://ark.ap-southeast.bytepluses.com/api/v3",
        stripModelPrefix=True,
        thinkingStyle="thinking_type",
    ),
    ProviderSpec(
        providerId="byteplus_coding_plan",
        label="BytePlus Coding Plan",
        is_gateway=True,
        keywords=("byteplus-plan",),
        defaultApiBase="https://ark.ap-southeast.bytepluses.com/api/coding/v3",
        stripModelPrefix=True,
        thinkingStyle="thinking_type",
    ),
    ProviderSpec(
        providerId="nvidia_nim",
        label="NVIDIA NIM",
        is_gateway=True,
        keywords=("nvidia_nim", "nvidia-nim", "nim"),
        defaultApiBase="https://integrate.api.nvidia.com/v1",
        supportsStreamOptions=False,
    ),
    # === Standard：按模型名匹配 ============================================
    ProviderSpec(
        providerId="anthropic",
        label="Anthropic",
        backend=BACKEND_ANTHROPIC,
        keywords=("anthropic", "claude"),
        defaultApiBase="https://api.anthropic.com/v1",
        supportsPromptCaching=True,
    ),
    ProviderSpec(
        providerId="openai",
        label="OpenAI",
        keywords=("openai", "gpt"),
        defaultApiBase="https://api.openai.com/v1",
        supportsMaxCompletionTokens=True,
    ),
    ProviderSpec(
        providerId="openai_codex",
        label="OpenAI Codex",
        backend=BACKEND_OPENAI_CODEX,
        is_oauth=True,
        keywords=("openai-codex",),
        defaultApiBase="https://chatgpt.com/backend-api",
        requires_key=False,
    ),
    ProviderSpec(
        providerId="github_copilot",
        label="GitHub Copilot",
        backend=BACKEND_GITHUB_COPILOT,
        is_oauth=True,
        keywords=("github_copilot", "copilot"),
        defaultApiBase="https://api.githubcopilot.com",
        stripModelPrefix=True,
        supportsMaxCompletionTokens=True,
        requires_key=False,
    ),
    ProviderSpec(
        providerId="codebuddy",
        label="CodeBuddy / WorkBuddy",
        backend=BACKEND_CODEBUDDY,
        is_oauth=True,
        keywords=("codebuddy", "workbuddy"),
        defaultApiBase="https://www.codebuddy.ai/v2",
        stripModelPrefix=True,
        supportsStreamOptions=False,
    ),
    ProviderSpec(
        providerId="deepseek",
        label="DeepSeek",
        keywords=("deepseek",),
        defaultApiBase="https://api.deepseek.com",
        thinkingStyle="thinking_type",
        reasoningModelPatterns=("deepseek-v4-pro", "deepseek-reasoner"),
        nativeWebSearchModels=("deepseek-v4-flash", "deepseek-v4-pro"),
    ),
    ProviderSpec(
        providerId="gemini",
        label="Gemini",
        keywords=("gemini",),
        defaultApiBase="https://generativelanguage.googleapis.com/v1beta/openai/",
        defaultOffReasoning=("gemini-2.5", "gemini-3"),
        minimalNotOff=("gemini-3", "gemini-2.5-pro"),
    ),
    ProviderSpec(
        providerId="zhipu",
        label="智谱 AI",
        keywords=("zhipu", "glm", "zai"),
        defaultApiBase="https://open.bigmodel.cn/api/paas/v4",
        legacyEnvKey="ZAI_API_KEY",
    ),
    ProviderSpec(
        providerId="dashscope",
        label="阿里云百炼（DashScope）",
        keywords=("qwen", "dashscope"),
        defaultApiBase="https://dashscope.aliyuncs.com/compatible-mode/v1",
        thinkingStyle="enable_thinking",
        reasoningModelPatterns=("qwen3", "qwen-3", "qwq", "qwen-plus"),
    ),
    ProviderSpec(
        providerId="moonshot",
        label="Moonshot（Kimi）",
        keywords=("moonshot", "kimi"),
        defaultApiBase="https://api.moonshot.cn/v1",
        modelOverrides=(
            ("kimi", {"temperature": None}),
            ("=k3", {"temperature": None}),
        ),
        exactModelIds=("k3",),
    ),
    ProviderSpec(
        providerId="minimax",
        label="MiniMax",
        keywords=("minimax",),
        defaultApiBase="https://api.minimax.io/v1",
        apiBaseByFormat=((FORMAT_ANTHROPIC, "https://api.minimax.io/anthropic"),),
        thinkingStyle="reasoning_split",
    ),
    ProviderSpec(
        providerId="minimax_anthropic",
        label="MiniMax（Anthropic）",
        backend=BACKEND_ANTHROPIC,
        keywords=("minimax_anthropic",),
        defaultApiBase="https://api.minimax.io/anthropic",
        legacyOf=("minimax", FORMAT_ANTHROPIC),
    ),
    ProviderSpec(
        providerId="mistral",
        label="Mistral",
        keywords=("mistral",),
        defaultApiBase="https://api.mistral.ai/v1",
    ),
    ProviderSpec(
        providerId="stepfun",
        label="阶跃星辰（StepFun）",
        keywords=("stepfun", "step"),
        defaultApiBase="https://api.stepfun.com/v1",
    ),
    ProviderSpec(
        providerId="xiaomi_mimo",
        label="Xiaomi MIMO",
        keywords=("xiaomi_mimo", "mimo"),
        defaultApiBase="https://api.xiaomimimo.com/v1",
    ),
    ProviderSpec(
        providerId="groq",
        label="Groq",
        keywords=("groq",),
        defaultApiBase="https://api.groq.com/openai/v1",
    ),
    ProviderSpec(
        providerId="qianfan",
        label="百度千帆（Qianfan）",
        keywords=("qianfan", "ernie"),
        defaultApiBase="https://qianfan.baidubce.com/v2",
    ),
    # === Local：本机部署 ==================================================
    ProviderSpec(
        providerId="vllm",
        label="vLLM",
        is_local=True,
        keywords=("vllm",),
        requires_key=False,
        legacyEnvKey="HOSTED_VLLM_API_KEY",
    ),
    ProviderSpec(
        providerId="ollama",
        label="Ollama",
        is_local=True,
        keywords=("ollama", "nemotron"),
        requires_key=False,
        defaultApiBase="http://localhost:11434/v1",
        legacyEnvKey="OLLAMA_API_KEY",
    ),
    ProviderSpec(
        providerId="lm_studio",
        label="LM Studio",
        is_local=True,
        keywords=("lm-studio", "lmstudio", "lm_studio"),
        requires_key=False,
        defaultApiBase="http://localhost:1234/v1",
        legacyEnvKey="LM_STUDIO_API_KEY",
    ),
    ProviderSpec(
        providerId="llama_cpp",
        label="llama.cpp",
        is_local=True,
        keywords=("llama_cpp", "llama.cpp"),
        requires_key=False,
        defaultApiBase="http://localhost:8080/v1",
    ),
    ProviderSpec(
        providerId="lemonade",
        label="Lemonade",
        is_local=True,
        keywords=("lemonade",),
        requires_key=False,
        defaultApiBase="http://localhost:13305/api/v1",
        legacyEnvKey="LEMONADE_API_KEY",
    ),
    ProviderSpec(
        providerId="ovms",
        label="OpenVINO Model Server",
        is_direct=True,
        is_local=True,
        keywords=("openvino", "ovms"),
        requires_key=False,
        defaultApiBase="http://localhost:8000/v3",
    ),
)

PROVIDER_BY_ID: dict[str, ProviderSpec] = {spec.providerId: spec for spec in PROVIDERS}


def find_provider(provider_id: str | None) -> ProviderSpec | None:
    canonical = canonical_provider_id(provider_id)
    if not canonical:
        return None
    return PROVIDER_BY_ID.get(canonical)


def normalize_api_format(value: Any) -> str:
    normalized = str(value or FORMAT_AUTO).strip().lower()
    return normalized if normalized in API_FORMAT_VALUES else FORMAT_AUTO


def api_format_for_provider(value: Any, spec: ProviderSpec | None) -> str:
    """把请求的格式钳制到该供应商能说的集合（参考 api_format_for_provider）。"""
    requested = normalize_api_format(value)
    if spec is None:
        return requested
    choices = spec.apiFormats
    if not choices:
        return spec.defaultApiFormat
    return requested if requested in choices else spec.defaultApiFormat


def effective_backend(spec: ProviderSpec | None, api_format: Any = FORMAT_AUTO) -> str:
    """按格式派生实际后端；唯一会切换后端的是 OpenAI 兼容供应商上的 anthropic 格式。"""
    if spec is None:
        return BACKEND_OPENAI_COMPAT
    if api_format_for_provider(api_format, spec) == FORMAT_ANTHROPIC and spec.backend == BACKEND_OPENAI_COMPAT:
        return BACKEND_ANTHROPIC
    return spec.backend


def api_format_from_legacy(provider_id: str | None, wire_api: Any) -> str:
    """旧配置只写 wire_api 时还原它当时的格式（参考 api_format_from_legacy）。"""
    spec = find_provider(provider_id)
    if spec is not None and spec.backend == BACKEND_ANTHROPIC:
        return FORMAT_ANTHROPIC
    mapping = {"responses": FORMAT_OPENAI_RESPONSES, "chat_completions": FORMAT_OPENAI_CHAT}
    return mapping.get(str(wire_api or "").strip().lower(), FORMAT_AUTO)


def find_by_model(model: str | None) -> ProviderSpec | None:
    """按模型名前缀/精确 ID/关键字匹配标准供应商（参考 find_by_model）。"""
    if not model:
        return None
    model_lower = model.lower()
    model_normalized = model_lower.replace("-", "_")
    model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
    normalized_prefix = model_prefix.replace("-", "_")
    standard = [s for s in PROVIDERS if not s.is_gateway and not s.is_local]

    for spec in standard:
        if model_prefix and normalized_prefix == spec.providerId:
            return spec
    for spec in standard:
        if model_lower in spec.exactModelIds:
            return spec
    for spec in standard:
        if any(kw in model_lower or kw.replace("-", "_") in model_normalized for kw in spec.keywords):
            return spec
    return None


def _matching_overrides(spec: ProviderSpec, model_lower: str) -> dict[str, Any]:
    for pattern, overrides in spec.modelOverrides:
        if (pattern.startswith("=") and model_lower == pattern[1:]) or (
            not pattern.startswith("=") and pattern in model_lower
        ):
            return dict(overrides)
    return {}


def model_overrides_for(model: str | None, spec: ProviderSpec | None) -> dict[str, Any]:
    """模型自带的请求参数覆盖（None 表示删除该参数）。配置的 spec 优先，其次模型厂商。"""
    model_lower = (model or "").strip().lower()
    if not model_lower:
        return {}
    if spec is not None:
        configured = _matching_overrides(spec, model_lower)
        if configured:
            return configured
    vendor = find_by_model(model_lower)
    if vendor is None or vendor is spec:
        return {}
    return _matching_overrides(vendor, model_lower)


def strip_provider_prefix(model: str, spec: ProviderSpec | None) -> str:
    if not model or not spec or not spec.stripModelPrefix:
        return model
    return model.split("/", 1)[1] if "/" in model else model


def is_anthropic_family(model: str | None) -> bool:
    """缓存控制等 Anthropic 专有行为只在 Anthropic 模型上前提成立。"""
    lowered = (model or "").lower()
    return lowered.startswith("anthropic/") or "claude" in lowered


__all__ = [
    "API_FORMAT_VALUES",
    "AUTH_API_KEY",
    "AUTH_NONE",
    "AUTH_OAUTH",
    "BACKENDS",
    "BACKEND_ANTHROPIC",
    "BACKEND_AZURE_OPENAI",
    "BACKEND_CODEBUDDY",
    "BACKEND_GITHUB_COPILOT",
    "BACKEND_OPENAI_CODEX",
    "BACKEND_OPENAI_COMPAT",
    "FORMAT_ANTHROPIC",
    "FORMAT_AUTO",
    "FORMAT_OPENAI_CHAT",
    "FORMAT_OPENAI_RESPONSES",
    "MODE_STANDARD",
    "MODE_DIRECT",
    "MODE_GATEWAY",
    "MODE_LOCAL",
    "MODE_OAUTH",
    "OPENAI_API_FORMATS",
    "PROVIDERS",
    "PROVIDER_ALIASES",
    "PROVIDER_BY_ID",
    "ProviderSpec",
    "api_format_for_provider",
    "api_format_from_legacy",
    "canonical_provider_id",
    "effective_backend",
    "find_by_model",
    "find_provider",
    "is_anthropic_family",
    "model_overrides_for",
    "normalize_api_format",
    "strip_provider_prefix",
]
