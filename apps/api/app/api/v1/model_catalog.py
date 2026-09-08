"""统一问答模型目录、默认值和只读模型发现。"""
from __future__ import annotations

import httpx2 as httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.v1.model_views import connection_view, profile_view
from app.core.exceptions import InvalidRequestError
from app.providers.llm.base import ProviderError, raise_for_stream_status

router = APIRouter(tags=["model-settings"])


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


@router.get("/model-connections/{connection_id}/models")
async def discover_models(request: Request, connection_id: str) -> dict:
    connection = request.app.state.model_config_repo.get_connection(connection_id)
    key = request.app.state.secret_store.resolve(connection_id)
    if not key:
        raise ProviderError("MODEL_NOT_CONFIGURED", "请先为该连接保存凭证。", status_code=400)
    base = connection.baseUrl.rstrip("/")
    if connection.protocol == "anthropic-messages":
        base = base if base.endswith("/v1") else base + "/v1"
        headers = {**connection.extraHeaders, "x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        headers = {**connection.extraHeaders, "Authorization": f"Bearer {key}"}
    models: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            params = {}
            for _ in range(20):
                response = await client.get(base + "/models", headers=headers, params=params)
                if response.status_code in (404, 405, 501):
                    raise ProviderError("MODEL_DISCOVERY_UNSUPPORTED", "服务不支持获取模型列表，请手动添加模型。")
                await raise_for_stream_status(response)
                try:
                    data = response.json()
                    rows = data["data"]
                    if not isinstance(rows, list):
                        raise ValueError()
                    for row in rows:
                        if isinstance(row, dict) and isinstance(row.get("id"), str) and 0 < len(row["id"]) <= 128:
                            models.add(row["id"])
                except (ValueError, KeyError, TypeError):
                    raise ProviderError("UPSTREAM_PROTOCOL_ERROR", "模型列表格式不受支持，请手动添加。") from None
                if connection.protocol != "anthropic-messages" or not data.get("has_more"):
                    return {"models": [{"id": value} for value in sorted(models)]}
                cursor = data.get("last_id")
                if not cursor or cursor == params.get("after_id"):
                    break
                params = {"after_id": cursor}
    except httpx.TimeoutException:
        raise ProviderError("UPSTREAM_TIMEOUT", "获取模型列表超时，请重试或手动添加。", retryable=True) from None
    except httpx.HTTPError:
        raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接模型服务。", retryable=True) from None
    raise ProviderError("MODEL_DISCOVERY_INCOMPLETE", "模型列表分页未完成，请手动添加或稍后重试。")
