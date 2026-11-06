"""Embedding 模型接口：本机候选发现、云端百炼连接、真实能力检测与配置保存。

- ``GET /embedding-models`` 使用 ``app.state.embedding_provider``（本机 Ollama）列出本机
  候选；同时返回可用于云端 Embedding 的百炼连接与受控模型清单。本机服务不可达时
  ``available=false`` 并给出可读原因，**不抛错、不返回假列表**；云端连接信息独立返回，
  不会因为本机不可达而消失。
- 检测与保存走 ``app.state.index_service``（先 probe 再落库；指纹冲突返回既有配置）。
  云端请求带 ``source="cloud"`` 与 ``connectionId``；不传时保持旧的本机语义。
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.core.exceptions import AppError
from app.providers.embeddings.dashscope_embedding import (
    DIMENSION_CHOICES,
    SUPPORTED_MODELS,
)
from app.schemas.textbook import (
    EmbeddingModelList,
    EmbeddingProbeRequest,
    EmbeddingProfileCreate,
    EmbeddingProfileList,
    EmbeddingProfileView,
    EmbeddingProbeView,
)
from app.services.textbook_ingest.views import require_state, run_in_thread

router = APIRouter(tags=["embedding-models"])


def _cloud_models() -> list[dict]:
    """受控云端模型清单：只列官方支持 ``dimensions`` 的文本 Embedding 模型。"""
    return [
        {"name": name, "dimensions": list(DIMENSION_CHOICES.get(name, ()))}
        for name in SUPPORTED_MODELS
    ]


def _cloud_connections(request: Request) -> list[dict]:
    resolver = getattr(request.app.state, "embedding_resolver", None)
    if resolver is None:
        return []
    try:
        options = resolver.cloud_connections()
    except AppError:
        return []
    return [
        {
            "connectionId": item.connection_id,
            "displayName": item.display_name,
            "baseUrl": item.base_url,
            "ready": item.ready,
            "reason": item.reason,
        }
        for item in options
    ]


@router.get("/embedding-models")
async def list_embedding_models(request: Request) -> EmbeddingModelList:
    cloud = _cloud_connections(request)
    cloud_models = _cloud_models()
    # 未装配必须是 503（不是"空列表"）；装配了但服务不可达才是 available=False。
    provider = require_state(request.app.state.embedding_provider, label="Embedding 服务")
    base_url = str(getattr(provider, "base_url", request.app.state.settings.embedding_base_url))
    try:
        models = await run_in_thread(provider.list_models)
    except AppError as exc:
        # 本机服务不可达不是"没有模型"：如实报告可用性；云端连接仍照常返回。
        return EmbeddingModelList(
            baseUrl=base_url,
            available=False,
            reason=str(exc),
            models=[],
            cloudConnections=cloud,
            cloudModels=cloud_models,
        )
    return EmbeddingModelList(
        baseUrl=base_url,
        available=True,
        reason=None,
        models=models,
        cloudConnections=cloud,
        cloudModels=cloud_models,
    )


@router.post("/embedding-probes")
async def probe_embedding_model(request: Request, body: EmbeddingProbeRequest) -> EmbeddingProbeView:
    index = require_state(request.app.state.index_service, label="教材索引服务")
    return await run_in_thread(
        index.probe,
        model_name=body.modelName,
        base_url=body.baseUrl,
        query_prefix=body.queryPrefix,
        document_prefix=body.documentPrefix,
        normalization=body.normalization,
        source=body.source,
        connection_id=body.connectionId,
        dimensions=body.dimensions,
    )


@router.get("/embedding-profiles")
async def list_embedding_profiles(request: Request) -> EmbeddingProfileList:
    index = require_state(request.app.state.index_service, label="教材索引服务")
    return await run_in_thread(index.list_profiles)


@router.post("/embedding-profiles", status_code=status.HTTP_201_CREATED)
async def create_embedding_profile(
    request: Request, body: EmbeddingProfileCreate
) -> EmbeddingProfileView:
    index = require_state(request.app.state.index_service, label="教材索引服务")
    return await run_in_thread(
        index.create_profile,
        model_name=body.modelName,
        base_url=body.baseUrl,
        query_prefix=body.queryPrefix,
        document_prefix=body.documentPrefix,
        normalization=body.normalization,
        source=body.source,
        connection_id=body.connectionId,
        dimensions=body.dimensions,
    )


@router.post("/embedding-profiles/{profile_id}/retire")
async def retire_embedding_profile(
    request: Request, profile_id: str
) -> EmbeddingProfileView:
    """停用配置：不再用于新的入库与重建；幂等，已停用再调返回原配置。"""
    index = require_state(request.app.state.index_service, label="教材索引服务")
    return await run_in_thread(index.retire_profile, profile_id)


@router.delete("/embedding-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embedding_profile(request: Request, profile_id: str) -> Response:
    """受守卫删除：仅当没有任何索引代引用该配置才硬删；被引用返回 409 并提示改用停用。"""
    index = require_state(request.app.state.index_service, label="教材索引服务")
    await run_in_thread(index.delete_profile, profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
