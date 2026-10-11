"""Agent 接口的请求模型（骨架批）。

与 /chat、/rag 请求风格一致：显式 requestId + 会话/轮次标识；未知字段由路由层拒绝。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentAttachment(BaseModel):
    """随消息附带的上传文件引用（先经 /agent/upload 落 blob）。

    Agent 据此调 import_* 工具读取字节建导入草稿（产候选）；字节本体不进模型上下文。
    """

    assetId: str = Field(min_length=1, max_length=128)
    fileName: str = Field(min_length=1, max_length=512)
    mediaType: str = Field(default="", max_length=128)
    kind: str = Field(
        default="auto",
        pattern="^(auto|textbook|paper|roster|score|question)$",
        description="导入目标类型；auto 由 Agent 按文件名/上下文判断",
    )


class AgentStreamRequest(BaseModel):
    """发起一轮 Agent 对话。

    - ``threadId``：Agent 会话线程（checkpointer 按它隔离/恢复 interrupt 状态）；
    - ``message``：教师的一句话；
    - ``modelProfileId``：本论使用的模型配置（走 SecretStore 显式注入，不读进程环境）；
    - ``attachments``：可选的上传文件引用（一句话 + 附件驱动导入）。
    """

    requestId: str = Field(min_length=1, max_length=128)
    threadId: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=32000)
    modelProfileId: str = Field(min_length=1, max_length=128)
    attachments: list[AgentAttachment] = Field(default_factory=list, max_length=8)
    #: 本轮思考强度（D6）：覆盖 profile 默认值；none/minimal/low/medium/high/xhigh/max。
    #: 省略用 profile 声明的 reasoningEffort。模型不支持推理由构造层忽略，不报错。
    reasoningEffort: str | None = Field(default=None, max_length=16)


class AgentConfirmRequest(BaseModel):
    """教师对中断卡（写操作确认 / 参数选择）的决定，用于 Command(resume=...) 续跑。

    - ``decision``：approve（确认执行/选定）/ reject（放弃）；
    - ``value``：选择卡的选定值（select 类卡片；confirm 类省略）；
    - ``submissionId``：幂等键，同一确认重复提交不产生第二次写操作。
    """

    submissionId: str = Field(min_length=8, max_length=128)
    requestId: str = Field(min_length=1, max_length=128)
    threadId: str = Field(min_length=1, max_length=128)
    modelProfileId: str = Field(min_length=1, max_length=128)
    confirmId: str = Field(min_length=1, max_length=128)
    decision: str = Field(pattern="^(approve|reject)$")
    value: str | None = Field(default=None, max_length=2000)


class AgentUploadResponse(BaseModel):
    """上传落 blob 后的引用（/agent/upload 返回）。"""

    assetId: str
    fileName: str
    mediaType: str
    byteSize: int
    sha256: str


__all__ = [
    "AgentAttachment",
    "AgentConfirmRequest",
    "AgentStreamRequest",
    "AgentUploadResponse",
]
