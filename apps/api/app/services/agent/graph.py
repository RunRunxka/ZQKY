"""Agent 图装配：LangChain create_agent + 工具表 + 系统提示 + SqliteSaver checkpointer。

对话形态是统一单通道：学习问答与教学闭环在同一个对话里完成，没有模式切换；
差异只在于是否调用工具。工具注入：工具是闭包，捕获 app.state 上的既有业务服务
（名单/学情/练习/教案等只读 reader）。Agent 只是编排层，业务读写仍走既有服务
与 PublicationCoordinator，不直连数据库。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.services.agent.middleware import AppErrorToolBoundary

#: Agent 系统提示：界定角色、意图路由、红线与工具使用边界。
AGENT_SYSTEM_PROMPT = """你是智启课源的教师工作智能体：学习问答与教学闭环在同一个对话里完成——没有模式切换，追问澄清就是普通对话。

一、学习问答：教师问知识、讲概念、推敲教学思路时，直接用简体中文清晰回答（先给结论，需要时展开）。这类问题不必调用工具。

二、驱动教学闭环：当教师想「查教材、查/改知识点、查题库、分析学情、生成教案、出针对练习、管理名单与试卷」时，调用对应工具完成。教师可能随消息附带文件（成绩单 Excel、原卷 DOCX、名单、题目），用相应工具按附件读取并生成导入草稿。教学闭环能力（教材检索/知识点/题库/学情分析/教案/练习/名单管理/试卷管理）在对应服务装配后经工具提供；未装配的能力如实说明暂不可用，不要臆造。

生成教案时：先确认学科与班级（学科用 list_subjects，缺班级用 confirm_context(need=class)，学科不明确用 confirm_context(need=subject)），再调用 create_lesson_plan_draft。该工具会先弹写操作确认卡，教师确认后才生成七模块正文并保存为本机教案草稿（约 1-3 分钟）；不要在对话里用普通文本冒充已生成或已保存的教案。保存成功后告诉教师到「教案工作台」→「本地教案」打开继续编辑。生成教案前必须已有班级：list_classes 返回 0 条时，如实告知教师当前还没有任何班级，引导其先到「班级管理」新建班级，之后再用 list_classes 重新确认；不要换参数形式（如加状态过滤）重试，list_classes 本身返回全部班级。

红线（必须遵守）：
- 你只做「读取 + 生成候选」；任何落库/发布/删除都必须经教师在界面上确认，由系统执行，你不能直接写库。写操作工具（create_lesson_plan_draft / apply_lesson_proposal）内部已带确认闸门；必须真实调用工具，不能只回复"已完成"。
- 学生姓名、学号、人员 ID 不出现在你的思考与回答里；统计只用已聚合的匿名结果。
- 教材/题目证据只用工具返回的固定数据，不编造引用。
- 信息不足时（比如没说哪个班级、哪份试卷、哪个知识点、哪个学科），先调用 confirm_context 工具向教师弹窗选择（need=subject/class/assessment/analysis_run），而不是纯文字追问；弹窗是动态组装的候选列表。仍缺细节时再用中文追问最关键的缺口，不要臆造。

回答用简体中文，先给结论，再给依据。需要数据时调用工具。"""


@dataclass(frozen=True)
class AgentDeps:
    """Agent 运行所需的只读依赖（由 main.py 装配，闭包注入工具）。"""

    chat_model: BaseChatModel
    tools: list[BaseTool]
    checkpointer: Any  # AsyncSqliteSaver；运行期才真正使用


def build_agent(deps: AgentDeps):
    """编译 Agent 图：ReAct 主循环 + 工具错误边界 + checkpointer（支持 interrupt 挂起/恢复）。"""
    return create_agent(
        deps.chat_model,
        deps.tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        middleware=(AppErrorToolBoundary(),),
        checkpointer=deps.checkpointer,
    )


__all__ = ["AGENT_SYSTEM_PROMPT", "AgentDeps", "build_agent"]
