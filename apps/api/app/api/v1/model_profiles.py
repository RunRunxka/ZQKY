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
from app.providers.llm.base import LLMRequest, LLMMessage, ProviderError
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import (
    KnownParam,
    ModelProfile,
    ReasoningEffort,
    validate_capability_map,
    now_utc,
)
from app.schemas.model_requests import (
    MetadataPreviewRequest,
    MetadataRefreshRequest,
    ProfileCreate,
    ProfileTestRequest,
    ProfileUpdate,
)
from app.services.model_discovery import discover_connection_models
from app.services.model_metadata import resolve_metadata
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
    default_id = repo.with_document(lambda doc: doc.defaultChatProfileId)
    return [
        profile_view(p, connections.get(p.connectionId), secrets, default_chat_profile_id=default_id)
        for p in repo.list_profiles()
    ]


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
    return profile_view(profile, repo.get_connection(profile.connectionId), secrets,
                        default_chat_profile_id=repo.with_document(lambda doc: doc.defaultChatProfileId))


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
    return profile_view(updated, repo.get_connection(updated.connectionId), secrets,
                        default_chat_profile_id=repo.with_document(lambda doc: doc.defaultChatProfileId))


@router.delete("/model-profiles/{profile_id}", status_code=204)
def delete_profile(request: Request, profile_id: str, expectedRevision: int | None = None) -> None:
    repo, _secrets = _deps(request)
    repo.delete_profile(profile_id, expectedRevision)


def _metadata_changes(profile: ModelProfile, metadata: dict) -> list[dict]:
    """只把有数值变化的上下限列入 changes；来源逐字段给出。"""
    changes: list[dict] = []
    for field_name, label in (("contextTokens", "上下文"), ("maxOutputTokens", "输出上限")):
        new_value = metadata.get(field_name)
        if not isinstance(new_value, int) or isinstance(new_value, bool) or new_value <= 0:
            continue
        old_value = getattr(profile, field_name)
        if old_value == new_value:
            continue
        sources = metadata.get("sources")
        source = (
            sources.get(field_name)
            if isinstance(sources, dict) and sources.get(field_name)
            else metadata.get("source")
        )
        changes.append(
            {
                "field": field_name,
                "label": label,
                "oldValue": old_value,
                "newValue": new_value,
                "source": source or "unknown",
            }
        )
    return changes


def _apply_metadata(profile: ModelProfile, metadata: dict) -> bool:
    """按用户选择自动覆盖上下限；supportedParams 只在档案为空时补。"""
    changed = False
    for field_name in ("contextTokens", "maxOutputTokens"):
        value = metadata.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            if getattr(profile, field_name) != value:
                setattr(profile, field_name, value)
                changed = True
    params = metadata.get("supportedParams")
    if not profile.supportedParams and isinstance(params, list):
        allowed = [item for item in params if item in {"temperature", "top_p"}]
        if allowed:
            profile.supportedParams = list(dict.fromkeys(allowed))
            changed = True
    return changed


def _metadata_message(
    changes: list[dict], metadata: dict, *, params_added: bool = False
) -> str:
    if changes:
        parts = [
            f"{item['label']} "
            f"{format(item['oldValue'], ',') if item['oldValue'] is not None else '—'}"
            f" → {format(item['newValue'], ',')}（{item['source']}）"
            for item in changes
        ]
        return "已更新：" + "；".join(parts) + "。"
    if params_added:
        return "已补充模型支持参数声明。"
    notes = metadata.get("notes") or []
    suffix = f"（{'；'.join(str(note) for note in notes)}）" if notes else ""
    return "未获取到可写回的上下文/输出上限；可在档案手填。" + suffix


async def _refresh_one_metadata(
    request: Request,
    profile: ModelProfile,
    *,
    force: bool = False,
    upstream_rows: list[dict] | None = None,
) -> dict:
    repo, secrets = _deps(request)
    connection = repo.get_connection(profile.connectionId)
    metadata = await resolve_metadata(
        request.app.state.settings,
        connection,
        profile.modelId,
        key=secrets.resolve(connection.id),
        existing_output=profile.maxOutputTokens,
        force_catalog=force,
        upstream_rows=upstream_rows,
    )
    return metadata


@router.post("/model-profiles/{profile_id}/refresh-metadata")
async def refresh_profile_metadata(
    request: Request, profile_id: str, force: bool = False
) -> dict:
    """自动读取并写回上下文容量与输出上限（已有值也覆盖，返回 old→new）。"""
    repo, _secrets = _deps(request)
    profile = repo.get_profile(profile_id)
    metadata = await _refresh_one_metadata(request, profile, force=force)
    changes = _metadata_changes(profile, metadata)
    params_added = not profile.supportedParams and bool(metadata.get("supportedParams"))
    if not changes and not params_added:
        return {
            "updated": False,
            "changes": [],
            "metadata": metadata,
            "message": _metadata_message([], metadata),
        }

    def apply(item: ModelProfile) -> None:
        _apply_metadata(item, metadata)

    repo.update_profile(profile.id, apply)
    return {
        "updated": True,
        "changes": changes,
        "metadata": metadata,
        "message": _metadata_message(changes, metadata, params_added=params_added),
    }


@router.post("/model-profiles/{profile_id}/refresh-context")
async def refresh_profile_context(request: Request, profile_id: str) -> dict:
    """兼容旧前端的上下文刷新别名：内部转调 refresh-metadata，只返回上下文部分。"""
    result = await refresh_profile_metadata(request, profile_id, force=False)
    metadata = result["metadata"]
    context_change = next(
        (change for change in result["changes"] if change["field"] == "contextTokens"),
        None,
    )
    return {
        "contextTokens": metadata.get("contextTokens"),
        "source": metadata.get("source") or "unavailable",
        "updated": bool(context_change),
        "message": result["message"],
    }


@router.post("/model-metadata/preview")
async def preview_model_metadata(request: Request, body: MetadataPreviewRequest) -> dict:
    """读取单个模型的元数据但不写库；供新建档案表单自动填充。"""
    repo, secrets = _deps(request)
    connection = repo.get_connection(body.connectionId)
    metadata = await resolve_metadata(
        request.app.state.settings,
        connection,
        body.modelId,
        key=secrets.resolve(connection.id),
        force_catalog=body.force,
    )
    return {
        "connectionId": body.connectionId,
        "modelId": body.modelId,
        "metadata": metadata,
    }


@router.post("/model-metadata/refresh")
async def refresh_model_metadata(request: Request, body: MetadataRefreshRequest) -> dict:
    """批量自动获取模型信息：目录只拉一次、每个连接只发现一次。"""
    repo, secrets = _deps(request)
    settings = request.app.state.settings
    profiles, connections = repo.with_document(
        lambda doc: (list(doc.profiles), {connection.id: connection for connection in doc.connections})
    )
    selected_ids = set(body.profileIds or [])
    targets = [
        profile
        for profile in profiles
        if (not selected_ids or profile.id in selected_ids)
        and (body.connectionId is None or profile.connectionId == body.connectionId)
    ]

    upstream_by_connection: dict[str, list[dict]] = {}
    discovery_notes: dict[str, str] = {}
    results: list[dict] = []
    updates: dict[str, dict] = {}
    for index, profile in enumerate(targets):
        connection = connections.get(profile.connectionId)
        if connection is None:
            results.append(
                {
                    "profileId": profile.id,
                    "modelId": profile.modelId,
                    "updated": False,
                    "changes": [],
                    "metadata": {"source": "unavailable", "notes": ["模型连接不存在。"]},
                    "message": "模型连接不存在。",
                }
            )
            continue
        key = secrets.resolve(connection.id)
        if profile.connectionId not in upstream_by_connection:
            try:
                discovery = await discover_connection_models(connection, key)
                upstream_by_connection[profile.connectionId] = [
                    entry for entry in (discovery.get("models") or []) if isinstance(entry, dict)
                ]
            except ProviderError as exc:
                upstream_by_connection[profile.connectionId] = []
                discovery_notes[profile.connectionId] = f"供应商模型列表读取失败：{exc}"
            except Exception as exc:  # pragma: no cover - 防御异常上游
                upstream_by_connection[profile.connectionId] = []
                discovery_notes[profile.connectionId] = (
                    f"供应商模型列表读取失败（{type(exc).__name__}）。"
                )

        metadata = await resolve_metadata(
            settings,
            connection,
            profile.modelId,
            key=key,
            existing_output=profile.maxOutputTokens,
            # force 只对第一个模型生效；后续使用刚更新的进程内缓存，避免重复拉目录
            force_catalog=body.force and index == 0,
            upstream_rows=upstream_by_connection[profile.connectionId],
        )
        note = discovery_notes.get(profile.connectionId)
        if note:
            metadata["notes"] = [note, *list(metadata.get("notes") or [])]
        changes = _metadata_changes(profile, metadata)
        params_added = not profile.supportedParams and bool(metadata.get("supportedParams"))
        updated = bool(changes or params_added)
        if updated:
            updates[profile.id] = metadata
        results.append(
            {
                "profileId": profile.id,
                "modelId": profile.modelId,
                "updated": updated,
                "changes": changes,
                "metadata": metadata,
                "message": _metadata_message(changes, metadata, params_added=params_added),
            }
        )

    if updates:

        def apply(document) -> None:  # noqa: ANN001
            by_id = {profile.id: profile for profile in document.profiles}
            for profile_id, metadata in updates.items():
                profile = by_id.get(profile_id)
                if profile is None:
                    continue
                _apply_metadata(profile, metadata)
                profile.updatedAt = now_utc()

        repo.mutate(apply)

    unchanged = len(results) - len(updates)
    return {
        "updatedCount": len(updates),
        "unchangedCount": unchanged,
        "results": results,
        "message": f"已检查 {len(results)} 个模型，更新 {len(updates)} 个。",
    }


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
