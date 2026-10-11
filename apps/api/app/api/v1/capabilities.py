"""能力状态：按实际实现如实报告；未实现能力一律 planned，不返回假成功。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import API_VERSION, SERVICE_NAME
from app.schemas.capabilities import (
    Capability,
    CapabilityStatus,
    CapabilitiesResponse,
    now_utc,
)

router = APIRouter(tags=["capabilities"])

# 与 IMPLEMENTATION_PLAN.md 的任务阶段保持一致；能力实现后更新对应条目
CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        feature="model_settings",
        label="模型设置",
        status=CapabilityStatus.ready,
        detail=(
            "模型连接、模型配置、供应商目录与真实连接测试已实现；"
            "凭证存入服务端 SecretStore（正式服务为忽略的 apps/api/.env，测试为内存），"
            "响应只返回凭证状态，不回显明文。"
        ),
    ),
    Capability(
        feature="chat",
        label="对话",
        status=CapabilityStatus.ready,
        detail="流式对话已实现（三协议 SSE）；对话记录保存在浏览器本地。",
    ),
    Capability(
        feature="agent",
        label="教学 Agent",
        status=CapabilityStatus.ready,
        detail=(
            "LangGraph 内嵌编排已实现（会话/中断确认/上传机制在位）；"
            "工具表当前为空骨架，随业务重建逐项扩展。"
        ),
    ),
)


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(request: Request) -> CapabilitiesResponse:
    """骨架能力清单：只报告当前实际装配的三项（对话 / Agent / 模型设置）。

    业务能力随重建在 CAPABILITIES 中逐项回归；未实现的能力不得在此伪装 ready。
    """
    return CapabilitiesResponse(
        service=SERVICE_NAME,
        apiVersion=API_VERSION,
        generatedAt=now_utc(),
        capabilities=list(CAPABILITIES),
    )
