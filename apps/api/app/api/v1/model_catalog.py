"""统一问答模型目录、默认值、供应商目录与只读模型发现。"""

from __future__ import annotations

import httpx2 as httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.v1.model_views import connection_view, profile_view, provider_view
from app.core.exceptions import InvalidRequestError
from app.providers.llm.base import ProviderError, raise_for_stream_status
from app.providers.llm.registry import PROVIDERS, effective_backend, find_provider

router = APIRouter(tags=["model-settings"])

# 无发现 API 的供应商：返回有来源的目录或要求手工输入，不伪造成功（D12）
MANUAL_DISCOVERY_PROVIDERS = frozenset({"openai_codex"})
CATALOG_DISCOVERY: dict[str, tuple[list[str], str]] = {
    # providerId: (static ids, source label) —— 仅用于参考已有公开默认的极少场景
    "codebuddy": (["default"], "catalog:codebuddy-fallback"),
}


@router.get("/model-providers")
def providers(request: Request) -> dict:
    """供应商目录：单一 URL/能力真值，前端不再维护第二份表（D14/D15）。"""
    auth = request.app.state.model_auth_service
    entries = [provider_view(spec) for spec in PROVIDERS if not spec.isLegacy]
    legacy = [provider_view(spec) for spec in PROVIDERS if spec.isLegacy]
    auth.augment_providers(entries)
    auth.augment_providers(legacy)
    entries.sort(key=lambda item: item["label"])
    legacy.sort(key=lambda item: item["label"])
    return {"providers": entries, "legacy": legacy}


@router.get("/model-catalog")
def catalog(request: Request) -> dict:
    repo, secrets = request.app.state.model_config_repo, request.app.state.secret_store

    def read(doc):
        connections = {c.id: c for c in doc.connections}
        return {
            "revision": doc.revision,
            "defaultChatProfileId": doc.defaultChatProfileId,
            "connections": [connection_view(c, secrets) for c in doc.connections],
            "profiles": [profile_view(p, connections.get(p.connectionId), secrets) for p in doc.profiles],
        }

    return repo.with_document(read)


class DefaultSelection(BaseModel):
    modelProfileId: str | None
    expectedRevision: int


@router.put("/model-defaults")
def set_default(request: Request, body: DefaultSelection) -> dict:
    repo = request.app.state.model_config_repo

    def apply(doc):
        repo._check_revision(doc, body.expectedRevision)
        if body.modelProfileId:
            profile = repo._require_profile(doc, body.modelProfileId)
            if profile.purpose not in (None, "chat"):
                raise InvalidRequestError("请选择问答模型。")
        doc.defaultChatProfileId = body.modelProfileId

    repo.mutate(apply)
    return catalog(request)


def _discovery_headers(connection, key: str | None, backend: str) -> dict[str, str]:
    """发现请求的认证头风格与聊天一致（参考 utils.build_auth_headers）。"""
    from app.providers.llm.base import merge_headers

    if backend == "anthropic":
        auth = {"anthropic-version": "2023-06-01"}
        if key:
            auth["x-api-key"] = key
    elif connection.providerId == "azure_openai":
        auth = {"api-key": key} if key else {}
    else:
        auth = {"Authorization": f"Bearer {key}"} if key else {}
    return merge_headers(connection.extraHeaders, auth)


@router.get("/model-connections/{connection_id}/models")
async def discover_models(request: Request, connection_id: str) -> dict:
    repo = request.app.state.model_config_repo
    secrets = request.app.state.secret_store
    connection = repo.get_connection(connection_id)
    spec = find_provider(connection.providerId) if connection.providerId else None
    key = secrets.resolve(connection_id)

    # 无发现 API 的供应商：返回 manual 来源，不返回假发现成功
    if connection.providerId in MANUAL_DISCOVERY_PROVIDERS:
        return {"models": [], "source": "manual", "note": "该供应商没有公开模型列表接口，请手工添加模型 ID。"}
    if connection.providerId in CATALOG_DISCOVERY:
        ids, source = CATALOG_DISCOVERY[connection.providerId]
        return {"models": [{"id": value} for value in ids], "source": source, "note": "该目录来自参考内置回退，非上游实时发现。"}

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
                if not is_anthropic or not data.get("has_more"):
                    return {"models": [{"id": value} for value in sorted(models)], "source": "upstream"}
                cursor = data.get("last_id")
                if not cursor or cursor == params.get("after_id"):
                    break
                params = {"after_id": cursor}
    except httpx.TimeoutException:
        raise ProviderError("UPSTREAM_TIMEOUT", "获取模型列表超时，请重试或手动添加。", retryable=True) from None
    except httpx.HTTPError:
        raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接模型服务。", retryable=True) from None
    raise ProviderError("MODEL_DISCOVERY_INCOMPLETE", "模型列表分页未完成，请手动添加或稍后重试。")
