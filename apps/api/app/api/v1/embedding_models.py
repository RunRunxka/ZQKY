"""Embedding 模型接口：本地候选发现、真实能力检测与配置保存。

- ``GET /embedding-models`` 使用 ``app.state.embedding_provider``（本机 Ollama 适配器）；
  本地服务不可达时返回 ``available=false`` 与可读原因，**不抛错、不返回假列表**。
- 检测与保存走 ``app.state.index_service``（先 probe 再落库；指纹冲突返回既有配置）。
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.core.exceptions import AppError
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


@router.get("/embedding-models")
async def list_embedding_models(request: Request) -> EmbeddingModelList:
    provider = require_state(request.app.state.embedding_provider, label="Embedding 服务")
    base_url = str(getattr(provider, "base_url", request.app.state.settings.embedding_base_url))
    try:
        models = await run_in_thread(provider.list_models)
    except AppError as exc:
        # 服务不可达不是"没有模型"：如实报告可用性
        return EmbeddingModelList(
            baseUrl=base_url, available=False, reason=str(exc), models=[]
        )
    return EmbeddingModelList(baseUrl=base_url, available=True, reason=None, models=models)


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
