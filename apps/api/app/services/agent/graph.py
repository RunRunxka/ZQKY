"""Agent 图装配：LangChain create_agent + 工具表 + 系统提示 + SqliteSaver checkpointer。

骨架批（A2）只挂少量读类工具验证全链路；写类工具与确认闸门在 A3/A4 接入。
图本身与运行解耦：``build_agent`` 返回编译后的图，运行器（runtime）负责事件流与中断恢复。

工具注入：工具是闭包，捕获 app.state 上的既有业务服务（名单/学情/练习/教案等只读 reader）。
Agent 只是编排层，业务读写仍走既有服务与 PublicationCoordinator，不直连数据库。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

#: Agent 系统提示：界定角色、意图路由、红线与工具使用边界。
AGENT_SYSTEM_PROMPT = """你是智启课源的教学智能体，在同一个对话里帮教师做两类事：

一、学习问答：教师问知识、讲概念、推敲教学思路时，直接用简体中文清晰回答（先给结论，需要时展开）。这类问题不必调用工具。

二、驱动教学闭环：当教师想"出学情分析 / 生成或调整教案 / 出针对练习 / 导入名单·原卷·成绩·题目 / 查班级·知识点·题库"时，调用对应工具完成。教师可能随消息附带文件（成绩单 Excel、原卷 DOCX、名单、题目），用 import 类工具按 assetId 读取字节建导入草稿。

红线（必须遵守）：
- 你只做"读取 + 生成候选"；任何落库/发布/删除都必须经教师在界面上确认，由系统执行，你不能直接写库。
- 学生姓名、学号、人员 ID 不出现在你的思考与回答里；统计只用已聚合的匿名结果。
- 教材/题目证据只用工具返回的固定数据，不编造引用。
- 信息不足时（比如没说哪个班级、哪份试卷、哪个知识点），用中文向教师追问一个最关键的缺口，不要臆造。

回答用简体中文，先给结论，再给依据。需要数据时调用工具。"""


@dataclass(frozen=True)
class AgentDeps:
    """Agent 运行所需的只读依赖（由 main.py 装配，闭包注入工具）。"""

    chat_model: BaseChatModel
    tools: list[BaseTool]
    checkpointer: Any  # AsyncSqliteSaver；运行期才真正使用


def build_agent(deps: AgentDeps):
    """编译 Agent 图：ReAct 主循环 + checkpointer（支持 interrupt 挂起/恢复）。"""
    return create_agent(
        deps.chat_model,
        deps.tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        checkpointer=deps.checkpointer,
    )


__all__ = ["AGENT_SYSTEM_PROMPT", "AgentDeps", "build_agent"]
