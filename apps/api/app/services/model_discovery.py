"""上游模型发现：读取连接 `/models` 并透传可核对的元数据。

路由（model_catalog）与模型元数据服务（model_metadata）共用本模块；
无发现能力的供应商明确返回 manual/catalog，不伪造实时结果。
"""

from __future__ import annotations

from typing import Any

import httpx2 as httpx

from app.providers.llm.base import ProviderError, merge_headers, raise_for_stream_status
from app.providers.llm.registry import effective_backend, find_provider

#: 无发现 API 的供应商：返回有来源的目录或要求手工输入，不伪造成功（D12）
MANUAL_DISCOVERY_PROVIDERS = frozenset({"openai_codex"})
CATALOG_DISCOVERY: dict[str, tuple[list[str], str]] = {
    # providerId: (static ids, source label) —— 仅用于参考已有公开默认的极少场景
    "codebuddy": (["default"], "catalog:codebuddy-fallback"),
}

#: 发现条目透传的 supportedParameters 上限，防止异常上游把响应撑爆
_MAX_PASSTHROUGH_PARAMS = 64
#: 单条元数据的合理上限（防止异常上游返回超大数字）
_MAX_CONTEXT_TOKENS = 100_000_000
_MAX_OUTPUT_TOKENS = 4_000_000


def _positive_int(value: Any, *, maximum: int) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value if 0 < value <= maximum else None


def _first_bool(row: dict, *keys: str) -> bool | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            return value
    return None


def _passthrough_metadata(row: dict) -> dict:
    """从上游模型条目提取上下文、输出上限、能力与受支持参数（有值才附带）。"""
    meta: dict = {}

    raw_context = (
        row.get("context_length")
        or row.get("context_window")
        or row.get("contextWindow")
        or row.get("max_context_length")
        or row.get("max_input_tokens")
    )
    context = _positive_int(raw_context, maximum=_MAX_CONTEXT_TOKENS)
    if context is not None:
        meta["contextLength"] = context

    raw_output = (
        row.get("max_output_tokens")
        or row.get("max_completion_tokens")
        or row.get("output_token_limit")
    )
    top_provider = row.get("top_provider")
    if raw_output is None and isinstance(top_provider, dict):
        raw_output = top_provider.get("max_completion_tokens")
    output = _positive_int(raw_output, maximum=_MAX_OUTPUT_TOKENS)
    if output is not None:
        meta["maxOutputTokens"] = output

    display_name = row.get("name") or row.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        meta["displayName"] = display_name.strip()[:128]

    raw_params = row.get("supported_parameters")
    if isinstance(raw_params, list):
        params = [str(item) for item in raw_params if isinstance(item, str)][:_MAX_PASSTHROUGH_PARAMS]
        if params:
            meta["supportedParameters"] = params

    capabilities: dict[str, Any] = {}
    tool_call = _first_bool(row, "tool_call", "supports_tool_calling", "supports_tools")
    if tool_call is not None:
        capabilities["toolCall"] = tool_call
    reasoning = _first_bool(row, "reasoning", "supports_reasoning")
    if reasoning is not None:
        capabilities["reasoning"] = reasoning
    structured = _first_bool(row, "structured_output", "supports_structured_output")
    if structured is not None:
        capabilities["structuredOutput"] = structured
    temperature = _first_bool(row, "temperature", "supports_temperature")
    if temperature is not None:
        capabilities["temperature"] = temperature
    architecture = row.get("architecture")
    if isinstance(architecture, dict):
        inputs = architecture.get("input_modalities")
        if isinstance(inputs, list):
            modalities = [str(item) for item in inputs if isinstance(item, str)][:8]
            if modalities:
                capabilities["inputModalities"] = modalities
    if capabilities:
        meta["capabilities"] = capabilities
    return meta


def _discovery_headers(connection, key: str | None, backend: str) -> dict[str, str]:
    """发现请求的认证头风格与聊天一致（参考 utils.build_auth_headers）。"""
    if backend == "anthropic":
        auth = {"anthropic-version": "2023-06-01"}
        if key:
            auth["x-api-key"] = key
    elif getattr(connection, "providerId", None) == "azure_openai":
        auth = {"api-key": key} if key else {}
    else:
        auth = {"Authorization": f"Bearer {key}"} if key else {}
    return merge_headers(connection.extraHeaders, auth)


async def discover_connection_models(connection, key: str | None) -> dict:
    """按连接读取上游模型列表；返回 `{"models", "source", "note"?}`。

    不读取进程环境、不记录凭证；认证只来自调用方传入的 SecretStore key。
    """
    spec = find_provider(connection.providerId) if connection.providerId else None

    if connection.providerId in MANUAL_DISCOVERY_PROVIDERS:
        return {"models": [], "source": "manual", "note": "该供应商没有公开模型列表接口，请手工添加模型 ID。"}
    if connection.providerId in CATALOG_DISCOVERY:
        ids, source = CATALOG_DISCOVERY[connection.providerId]
        return {
            "models": [{"id": value} for value in ids],
            "source": source,
            "note": "该目录来自参考内置回退，非上游实时发现。",
        }

    requires_key = bool(spec and spec.authMode == "api_key" and spec.requires_key)
    if requires_key and not key:
        raise ProviderError("MODEL_NOT_CONFIGURED", "请先为该连接保存凭证。", status_code=400)

    backend = effective_backend(spec, connection.apiFormat.value)
    base = (connection.baseUrl or (spec.defaultApiBaseFor(connection.apiFormat.value) if spec else "")).rstrip("/")
    if not base:
        raise ProviderError("MODEL_NOT_CONFIGURED", "该连接缺少 Base URL。", status_code=400)
    if backend == "anthropic":
        base = base if base.endswith("/v1") else base + "/v1"
    headers = _discovery_headers(connection, key, backend)
    is_anthropic = backend == "anthropic"

    models: set[str] = set()
    row_metadata: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            params: dict[str, str] = {}
            for _ in range(20):
                response = await client.get(base + "/models", headers=headers, params=params)
                if response.status_code in (404, 405, 501):
                    # 不支持发现的端点明确报告；认证失败已由 raise_for_stream_status 处理
                    raise ProviderError("MODEL_DISCOVERY_UNSUPPORTED", "服务不支持获取模型列表，请手动添加模型。")
                await raise_for_stream_status(response)
                try:
                    data = response.json()
                except ValueError:
                    raise ProviderError("UPSTREAM_PROTOCOL_ERROR", "模型列表格式不受支持，请手动添加。") from None
                # Anthropic / 部分服务返回 {"models":[...]}，OpenAI 返回 {"data":[...]}
                rows = data.get("data")
                if rows is None:
                    rows = data.get("models")
                if not isinstance(rows, list):
                    raise ProviderError("UPSTREAM_PROTOCOL_ERROR", "模型列表格式不受支持，请手动添加。")
                for row in rows:
                    if isinstance(row, str) and 0 < len(row) <= 128:
                        models.add(row)
                    elif isinstance(row, dict) and isinstance(row.get("id"), str) and 0 < len(row["id"]) <= 128:
                        models.add(row["id"])
                        meta = _passthrough_metadata(row)
                        if meta:
                            row_metadata[row["id"]] = meta
                if not is_anthropic or not data.get("has_more"):
                    entries = [
                        {"id": value, **row_metadata[value]} if value in row_metadata else {"id": value}
                        for value in sorted(models)
                    ]
                    return {"models": entries, "source": "upstream"}
                cursor = data.get("last_id")
                if not cursor or cursor == params.get("after_id"):
                    break
                params = {"after_id": cursor}
    except httpx.TimeoutException:
        raise ProviderError("UPSTREAM_TIMEOUT", "获取模型列表超时，请重试或手动添加。", retryable=True) from None
    except httpx.HTTPError:
        raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接模型服务。", retryable=True) from None
    raise ProviderError("MODEL_DISCOVERY_INCOMPLETE", "模型列表分页未完成，请手动添加或稍后重试。")


__all__ = [
    "CATALOG_DISCOVERY",
    "MANUAL_DISCOVERY_PROVIDERS",
    "discover_connection_models",
]
