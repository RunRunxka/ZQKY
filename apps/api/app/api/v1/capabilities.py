"""能力状态：按实际实现如实报告；未实现能力一律 planned，不返回假成功。"""

from __future__ import annotations

from fastapi import APIRouter

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
            "模型连接、模型配置、供应商目录（38 条）与真实连接测试已实现；"
            "凭证存入服务端 SecretStore（正式服务为忽略的 apps/api/.env，测试为内存），"
            "响应只返回凭证状态，不回显明文。"
        ),
    ),
    Capability(
        feature="chat",
        label="学习问答对话",
        status=CapabilityStatus.ready,
        detail="流式对话已实现（D04）；对话记录保存在浏览器本地。教材检索（RAG）仍规划中。",
    ),
    Capability(
        feature="lesson_plan_ai_fill",
        label="教案真实AI填充",
        status=CapabilityStatus.planned,
        detail="当前教案使用浏览器本地规则填充，不调用模型。",
    ),
    Capability(
        feature="paper_compose",
        label="智能组卷",
        status=CapabilityStatus.planned,
        detail="本地组卷与排版在 D05/D06 实施；题库自动选题保持规划。",
    ),
    Capability(
        feature="templates",
        label="模板中心与正式导出",
        status=CapabilityStatus.planned,
        detail="DOCX 模板上传、字段映射与渲染任务在 D05–D07 实施。",
    ),
    Capability(
        feature="textbook_repository",
        label="教材资料库",
        status=CapabilityStatus.planned,
        detail="仅契约规划，没有存储与检索实现。",
    ),
    Capability(
        feature="question_bank",
        label="题库",
        status=CapabilityStatus.planned,
        detail="仅契约规划，没有存储与检索实现。",
    ),
    Capability(
        feature="rag",
        label="教材检索（RAG）",
        status=CapabilityStatus.planned,
        detail="没有索引与向量存储，不返回检索结果。",
    ),
    Capability(
        feature="agent_tasks",
        label="Agent 任务",
        status=CapabilityStatus.planned,
        detail="任务运行器与业务工具调用未实现。",
    ),
    Capability(
        feature="mcp",
        label="MCP",
        status=CapabilityStatus.planned,
        detail=(
            "外部 MCP 连接与工具调用未实现：设置中的 MCP 条目只是本地登记，"
            "不会被连接、检测或执行，也不会进入问答请求。"
        ),
    ),
    Capability(
        feature="skills",
        label="Skills",
        status=CapabilityStatus.ready,
        detail=(
            "已启用的技能说明由服务端拼装为本轮系统上下文（设置 → Skills 唯一管理）。"
            "范围只到提示词级：技能不执行工具、不访问外部数据、不产生工具调用事件。"
        ),
    ),
)


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        service=SERVICE_NAME,
        apiVersion=API_VERSION,
        generatedAt=now_utc(),
        capabilities=list(CAPABILITIES),
    )
