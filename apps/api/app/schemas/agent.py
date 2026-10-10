"""Agent 接口的请求模型（骨架批）。

与 /chat、/rag 请求风格一致：显式 requestId + 会话/轮次标识；未知字段由路由层拒绝。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentStreamRequest(BaseModel):
    """发起一轮 Agent 对话。

    - ``threadId``：Agent 会话线程（checkpointer 按它隔离/恢复 interrupt 状态）；
    - ``message``：教师的一句话；
    - ``modelProfileId``：本论使用的模型配置（走 SecretStore 显式注入，不读进程环境）。
    """

    requestId: str = Field(min_length=1, max_length=128)
    threadId: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=32000)
    modelProfileId: str = Field(min_length=1, max_length=128)


class AgentConfirmRequest(BaseModel):
    """写操作确认（A4 全面启用；骨架批先占位，保证协议稳定）。"""

    submissionId: str = Field(min_length=1, max_length=128)
    threadId: str = Field(min_length=1, max_length=128)
    confirmId: str = Field(min_length=1, max_length=128)
    decision: str = Field(pattern="^(approve|reject)$")


__all__ = ["AgentConfirmRequest", "AgentStreamRequest"]
