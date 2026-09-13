"""模型配置接口：CRUD 与真实连接测试（一次小额上游请求）。"""

from __future__ import annotations

import time
import uuid
import math
from contextlib import aclosing
from typing import Any

from fastapi import APIRouter, Request

from app.api.v1.model_views import profile_view
from app.core.exceptions import InvalidRequestError, NotFoundError, RevisionConflictError
from app.core.secrets import SecretStore
from app.providers.llm.base import LLMRequest, LLMMessage
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import (
    KnownParam,
    ModelProfile,
    ReasoningEffort,
    validate_capability_map,
    now_utc,
)
from app.schemas.model_requests import ProfileCreate, ProfileTestRequest, ProfileUpdate
from app.services.model_runtime import build_llm_config, build_provider

router = APIRouter(tags=["model-settings"])

TEST_PROMPT = "请用一句中文回复：连接正常。"
TEST_MAX_OUTPUT_TOKENS = 256


def validate_supported_params(params: list[str] | None) -> list[str]:
    if not params:
        return []
    allowed = {item.value for item in KnownParam}
    for name in params:
        if name not in allowed:
            raise InvalidRequestError(f"不支持的生成参数：{name}")
    return list(dict.fromkeys(params))


def validate_params(params: dict, supported: list[str]) -> dict:
    for key, value in params.items():
        if key not in supported or key not in {"temperature", "top_p"}:
            raise InvalidRequestError("生成参数未声明支持。", code="UNSUPPORTED_PARAMETER")
        if not math.isfinite(value) or not 0 <= value <= (2 if key == "temperature" else 1):
            raise InvalidRequestError("生成参数超出允许范围。")
    return dict(params)


def _deps(request: Request) -> tuple[ModelConfigRepository, SecretStore]:
    return request.app.state.model_config_repo, request.app.state.secret_store


@router.get("/model-profiles")
def list_profiles(request: Request) -> list[dict]:
    repo, secrets = _deps(request)
    connections = {c.id: c for c in repo.list_connections()}
    return [profile_view(p, connections.get(p.connectionId), secrets) for p in repo.list_profiles()]


@router.post("/model-profiles", status_code=201)
def create_profile(request: Request, body: ProfileCreate) -> dict:
    repo, secrets = _deps(request)
    now = now_utc()
    _validate_reasoning(body.reasoningEnabled, body.reasoningEffort)
    profile = ModelProfile(
        id=uuid.uuid4().hex,
        connectionId=body.connectionId,
        displayName=body.displayName.strip(),
        modelId=body.modelId.strip(),
        purpose=body.purpose,
        contextTokens=body.contextTokens,
        maxOutputTokens=body.maxOutputTokens,
        supportedParams=validate_supported_params(body.supportedParams),
        params=validate_params(body.params, body.supportedParams or []),
        capabilities=validate_capability_map(body.capabilities),
        reasoningEnabled=body.reasoningEnabled,
        reasoningEffort=body.reasoningEffort,
        createdAt=now,
        updatedAt=now,
    )
    repo.create_profile(profile)
    return profile_view(profile, repo.get_connection(profile.connectionId), secrets)


def _validate_reasoning(enabled: bool | None, effort: ReasoningEffort | None) -> None:
    """D6：明确关闭与非关闭 effort 冲突应校验。"""
    if enabled is False and effort not in (None, ReasoningEffort.none):
        raise InvalidRequestError("已关闭推理时不能再指定推理深度。")


@router.put("/model-profiles/{profile_id}")
def update_profile(request: Request, profile_id: str, body: ProfileUpdate) -> dict:
    repo, secrets = _deps(request)

    def apply(profile: ModelProfile) -> None:
        if body.connectionId is not None:
            profile.connectionId = body.connectionId
        if body.displayName is not None:
            profile.displayName = body.displayName.strip()
        if body.modelId is not None:
            profile.modelId = body.modelId.strip()
        if "purpose" in body.model_fields_set:
            profile.purpose = body.purpose
        if "contextTokens" in body.model_fields_set:
            profile.contextTokens = body.contextTokens
        if "maxOutputTokens" in body.model_fields_set:
            profile.maxOutputTokens = body.maxOutputTokens
        if body.supportedParams is not None:
            profile.supportedParams = validate_supported_params(body.supportedParams)
        if body.params is not None:
            profile.params = validate_params(body.params, profile.supportedParams)
        else:
            profile.params = {k: v for k, v in profile.params.items() if k in profile.supportedParams}
        if body.capabilities is not None:
            profile.capabilities = validate_capability_map(body.capabilities)
        if "reasoningEnabled" in body.model_fields_set:
            profile.reasoningEnabled = body.reasoningEnabled
        if "reasoningEffort" in body.model_fields_set:
            profile.reasoningEffort = body.reasoningEffort
        _validate_reasoning(profile.reasoningEnabled, profile.reasoningEffort)

    updated = repo.update_profile(profile_id, apply, body.expectedRevision)
    return profile_view(updated, repo.get_connection(updated.connectionId), secrets)


@router.delete("/model-profiles/{profile_id}", status_code=204)
def delete_profile(request: Request, profile_id: str, expectedRevision: int | None = None) -> None:
    repo, _secrets = _deps(request)
    repo.delete_profile(profile_id, expectedRevision)


@router.post("/model-profiles/{profile_id}/test")
async def test_profile(request: Request, profile_id: str, body: ProfileTestRequest) -> dict:
    """对上游发送一次小请求；无论上游成败都以 200 返回测试结果，不伪造成功。"""
    repo, secrets = _deps(request)
    tested_revision = repo.revision()
    profile = repo.get_profile(profile_id)
    connection = repo.get_connection(profile.connectionId)

    requested_params = {**profile.params, **(body.params or {})}
    unsupported = sorted(set(requested_params) - set(profile.supportedParams))
    if unsupported:
        raise InvalidRequestError(
            f"该模型配置未声明支持参数：{', '.join(unsupported)}。",
            code="UNSUPPORTED_PARAMETER",
        )

    config = build_llm_config(connection, profile, secrets)
    provider = build_provider(connection, config, auth_service=request.app.state.model_auth_service)
    llm_request = LLMRequest(
        messages=[LLMMessage(role="user", content=body.prompt or TEST_PROMPT)],
        maxOutputTokens=min(body.maxOutputTokens or TEST_MAX_OUTPUT_TOKENS, TEST_MAX_OUTPUT_TOKENS),
        params=requested_params,
    )
    started = time.perf_counter()
    try:
        if body.stream:
            from app.providers.llm.base import LLMResponse
            text, times, reason, usage = [], [], "unknown", None
            async with aclosing(provider.stream(config, llm_request)) as events:
                async for event in events:
                    if event.type == "text":
                        text.append(event.text or "")
                        times.append(round((time.perf_counter() - started) * 1000))
                    elif event.type == "end":
                        reason = event.finishReason
                    elif event.type == "usage":
                        usage = event.usage
            response = LLMResponse(text="".join(text), finishReason=reason, usage=usage)
        else:
            response = await provider.complete(config, llm_request)
    except Exception as exc:  # noqa: BLE001 - 上游任何失败都是“测试结果”，不作为接口错误
        return {"ok": False, "error": _error_payload(exc)}
    latency_ms = round((time.perf_counter() - started) * 1000)
    try:
        repo.update_profile(profile_id, lambda p: p.capabilities.update({"stream" if body.stream else "chat": "verified"}), tested_revision)
    except (RevisionConflictError, NotFoundError):
        pass  # The result belongs to the tested snapshot, not the newly edited configuration.
    return {
        "ok": True,
        "text": response.text,
        "finishReason": response.finishReason,
        "usage": None
        if response.usage is None
        else {
            "inputTokens": response.usage.inputTokens,
            "outputTokens": response.usage.outputTokens,
        },
        "latencyMs": latency_ms,
        **({"stream": {"chunks": len(times), "firstTextMs": times[0] if times else None, "lastTextMs": times[-1] if times else None}} if body.stream else {}),
    }


def _error_payload(exc: Exception) -> dict[str, Any]:
    code = getattr(exc, "code", "UPSTREAM_ERROR")
    retryable = bool(getattr(exc, "retryable", False))
    return {"code": code, "message": str(exc) if hasattr(exc, "code") else "连接测试失败，请检查服务与配置。", "retryable": retryable}
