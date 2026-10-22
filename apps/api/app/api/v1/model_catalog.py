"""统一问答模型目录、默认值、供应商目录与只读模型发现。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.v1.model_views import connection_view, profile_view, provider_view
from app.core.exceptions import InvalidRequestError
from app.providers.llm.registry import PROVIDERS
from app.services.model_discovery import discover_connection_models

router = APIRouter(tags=["model-settings"])


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
            "profiles": [profile_view(p, connections.get(p.connectionId), secrets,
                                     default_chat_profile_id=doc.defaultChatProfileId) for p in doc.profiles],
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
    repo = request.app.state.model_config_repo
    secrets = request.app.state.secret_store
    connection = repo.get_connection(connection_id)
    key = secrets.resolve(connection_id)
    return await discover_connection_models(connection, key)


@router.get("/model-connections/{connection_id}/models")
async def discover_models(request: Request, connection_id: str) -> dict:
    repo = request.app.state.model_config_repo
    secrets = request.app.state.secret_store
    connection = repo.get_connection(connection_id)
    spec = find_provider(connection.providerId) if connection.providerId else None
    key = secrets.resolve(connection_id)
    return await discover_connection_models(connection, spec, key)
