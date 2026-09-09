"""模型连接接口：列表/创建/更新/删除；凭证只写入，响应不回显明文。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.v1.model_views import connection_view
from app.core.exceptions import NotFoundError
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ModelConnection, validate_base_url, now_utc
from app.schemas.model_requests import (
    ConnectionCreate,
    ConnectionUpdate,
    validate_extra_headers,
)

router = APIRouter(tags=["model-settings"])


def _deps(request: Request) -> tuple[ModelConfigRepository, SecretStore]:
    return request.app.state.model_config_repo, request.app.state.secret_store


@router.get("/model-connections")
def list_connections(request: Request) -> list[dict]:
    repo, secrets = _deps(request)
    return [connection_view(connection, secrets) for connection in repo.list_connections()]


@router.post("/model-connections", status_code=201)
def create_connection(request: Request, body: ConnectionCreate) -> dict:
    repo, secrets = _deps(request)
    now = now_utc()
    connection = ModelConnection(
        id=uuid.uuid4().hex,
        displayName=body.displayName.strip(),
        protocol=body.protocol,
        baseUrl=validate_base_url(body.baseUrl),
        extraHeaders=validate_extra_headers(body.extraHeaders),
        createdAt=now,
        updatedAt=now,
    )
    if body.apiKey:
        secrets.put(connection.id, body.apiKey)
    try:
        repo.create_connection(connection)
    except Exception:
        secrets.delete(connection.id)
        raise
    return connection_view(connection, secrets)


@router.put("/model-connections/{connection_id}")
def update_connection(request: Request, connection_id: str, body: ConnectionUpdate) -> dict:
    repo, secrets = _deps(request)

    def apply(connection: ModelConnection) -> None:
        if body.displayName is not None:
            connection.displayName = body.displayName.strip()
        if body.protocol is not None:
            connection.protocol = body.protocol
        if body.baseUrl is not None:
            connection.baseUrl = validate_base_url(body.baseUrl)
        if body.extraHeaders is not None:
            connection.extraHeaders = validate_extra_headers(body.extraHeaders)
        # revision 与字段先验证；凭证文件写入失败时不保存本次配置变更。
        if body.apiKey:
            secrets.put(connection_id, body.apiKey)

    updated = repo.update_connection(connection_id, apply, body.expectedRevision)
    return connection_view(updated, secrets)


@router.delete("/model-connections/{connection_id}", status_code=204)
def delete_connection(request: Request, connection_id: str, expectedRevision: int | None = None) -> None:
    repo, secrets = _deps(request)
    if not any(c.id == connection_id for c in repo.list_connections()):
        raise NotFoundError("模型连接不存在。")
    repo.delete_connection(connection_id, expectedRevision)
    secrets.delete(connection_id)
