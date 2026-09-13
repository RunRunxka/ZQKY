"""模型连接接口：CRUD、凭证语义（R-08）、专用认证生命周期（D9/D10）。

凭证只写入，响应不回显明文。跨 `.env` 与 JSON 的补偿由 ModelConfigService 承担（R-01）。
认证端点按供应商能力返回四态状态机；不支持的操作返回明确错误。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.v1.model_views import connection_view
from app.core.exceptions import AppError, NotFoundError
from app.core.secrets import SecretStore
from app.providers.llm.registry import find_provider
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ApiFormat, ModelConnection, ModelProtocol, now_utc, protocol_for
from app.schemas.model_requests import (
    ConnectionCreate,
    ConnectionUpdate,
    validate_extra_headers,
    validate_base_url,
)
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import (
    CREDENTIAL_KEEP,
    CREDENTIAL_REPLACE,
    ModelConfigService,
)

router = APIRouter(tags=["model-settings"])


def _deps(
    request: Request,
) -> tuple[ModelConfigRepository, SecretStore, ModelConfigService, ModelAuthService]:
    repo = request.app.state.model_config_repo
    secrets = request.app.state.secret_store
    service = request.app.state.model_config_service
    auth = request.app.state.model_auth_service
    return repo, secrets, service, auth


def _resolve_identity(
    provider_id: str | None,
    api_format: ApiFormat | str | None,
    protocol: ModelProtocol | str | None,
) -> tuple[str | None, ApiFormat, ModelProtocol]:
    """解析并校验 providerId + apiFormat；非法组合明确报错（D2）。"""
    canonical = provider_id
    spec = find_provider(canonical) if canonical else None
    if canonical and spec is None:
        raise AppError(
            f"未知的供应商：{canonical}。请从供应商目录中选择。",
            code="UNSUPPORTED_PROVIDER",
            status_code=422,
        )
    requested_format = api_format.value if isinstance(api_format, ApiFormat) else (api_format or "auto")
    if spec is not None:
        choices = spec.apiFormats
        if choices:
            if requested_format not in choices:
                raise AppError(
                    f"供应商 {spec.label} 不支持 API 格式 {requested_format}。",
                    code="UNSUPPORTED_API_FORMAT",
                    status_code=422,
                )
            resolved_format = requested_format
        else:
            # D2：格式固定的供应商（Azure/Codex/Copilot/OAuth）不接受显式改格式；
            # auto 视为使用默认，其他显式值明确拒绝，不静默换协议。
            if requested_format not in ("auto", spec.defaultApiFormat):
                raise AppError(
                    f"供应商 {spec.label} 的 API 格式固定为 {spec.defaultApiFormat}，不能指定 {requested_format}。",
                    code="UNSUPPORTED_API_FORMAT",
                    status_code=422,
                )
            resolved_format = spec.defaultApiFormat
    else:
        resolved_format = requested_format

    derived_protocol = protocol_for(canonical, resolved_format)
    if protocol is not None:
        # 旧调用方显式传 protocol：以显式值为准（无 providerId 时完全兼容）
        try:
            derived_protocol = ModelProtocol(protocol)
        except ValueError as exc:
            raise AppError(
                f"不支持的模型协议：{protocol}。",
                code="UNSUPPORTED_PROTOCOL",
                status_code=400,
            ) from exc
    return canonical, ApiFormat(resolved_format), derived_protocol


@router.get("/model-connections")
def list_connections(request: Request) -> list[dict]:
    repo, secrets, _service, _auth = _deps(request)
    return [connection_view(connection, secrets) for connection in repo.list_connections()]


@router.post("/model-connections", status_code=201)
def create_connection(request: Request, body: ConnectionCreate) -> dict:
    repo, secrets, service, _auth = _deps(request)
    provider_id, api_format, protocol = _resolve_identity(body.providerId, body.apiFormat, body.protocol)
    spec = find_provider(provider_id) if provider_id else None
    base_url = body.baseUrl.strip()
    if base_url:
        base_url = validate_base_url(base_url)
    elif spec is None or not spec.defaultApiBaseFor(api_format.value):
        raise AppError(
            "该供应商需要填写 Base URL。",
            code="INVALID_REQUEST",
            status_code=422,
        )

    now = now_utc()
    connection = ModelConnection(
        id=uuid.uuid4().hex,
        displayName=body.displayName.strip(),
        providerId=provider_id,
        protocol=protocol,
        apiFormat=api_format,
        apiVersion=body.apiVersion,
        baseUrl=base_url,
        extraHeaders=validate_extra_headers(body.extraHeaders),
        createdAt=now,
        updatedAt=now,
    )
    service.create_connection(connection, body.apiKey)
    return connection_view(connection, secrets)


@router.put("/model-connections/{connection_id}")
def update_connection(request: Request, connection_id: str, body: ConnectionUpdate) -> dict:
    repo, secrets, service, _auth = _deps(request)
    existing = repo.get_connection(connection_id)

    provider_id = body.providerId if body.providerId is not None else existing.providerId
    api_format = body.apiFormat if body.apiFormat is not None else existing.apiFormat
    provider_id, api_format, derived_protocol = _resolve_identity(
        provider_id, api_format, body.protocol
    )
    spec = find_provider(provider_id) if provider_id else None

    def apply(connection: ModelConnection) -> None:
        if body.displayName is not None:
            connection.displayName = body.displayName.strip()
        connection.providerId = provider_id
        connection.protocol = derived_protocol
        connection.apiFormat = api_format
        if "apiVersion" in body.model_fields_set:
            connection.apiVersion = body.apiVersion
        if body.baseUrl is not None:
            # 显式提交空字符串表示"使用供应商默认地址"；非空则保留用户原值
            connection.baseUrl = validate_base_url(body.baseUrl) if body.baseUrl.strip() else ""
        if body.extraHeaders is not None:
            connection.extraHeaders = validate_extra_headers(body.extraHeaders)
        elif spec is not None:
            connection.extraHeaders = connection.extraHeaders

    action = body.credentialAction
    if action is None:
        action = CREDENTIAL_REPLACE if body.apiKey else CREDENTIAL_KEEP

    updated = service.update_connection(
        connection_id,
        apply,
        api_key=body.apiKey,
        credential_action=action,
        expected_revision=body.expectedRevision,
    )
    return connection_view(updated, secrets)


@router.delete("/model-connections/{connection_id}", status_code=204)
def delete_connection(request: Request, connection_id: str, expectedRevision: int | None = None) -> None:
    repo, _secrets, service, _auth = _deps(request)
    if not any(c.id == connection_id for c in repo.list_connections()):
        raise NotFoundError("模型连接不存在。")
    # 托管凭证（Codex/Copilot）随连接一起清理，避免孤儿
    service.delete_connection(connection_id, expectedRevision)


# --- 专用认证生命周期（D9/D10）--------------------------------------------


@router.get("/model-connections/{connection_id}/auth")
def auth_status(request: Request, connection_id: str) -> dict:
    repo, _secrets, _service, auth = _deps(request)
    if not any(c.id == connection_id for c in repo.list_connections()):
        raise NotFoundError("模型连接不存在。")
    return auth.status(connection_id)


@router.post("/model-connections/{connection_id}/auth/start")
async def auth_start(request: Request, connection_id: str) -> dict:
    _repo, _secrets, _service, auth = _deps(request)
    result = await auth.start(connection_id)
    if not result.get("ok"):
        # start 不是上游调用；用 200 + ok:false 让前端展示具体原因，不伪造授权地址
        return result
    return result


@router.post("/model-connections/{connection_id}/auth/cancel")
async def auth_cancel(request: Request, connection_id: str) -> dict:
    _repo, _secrets, _service, auth = _deps(request)
    return await auth.cancel(connection_id)


@router.post("/model-connections/{connection_id}/auth/logout")
async def auth_logout(request: Request, connection_id: str) -> dict:
    _repo, _secrets, _service, auth = _deps(request)
    return await auth.logout(connection_id)
