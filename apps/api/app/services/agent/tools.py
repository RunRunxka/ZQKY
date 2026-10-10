"""Agent 工具表（骨架批）：先挂少量读类工具验证全链路。

写类工具与确认闸门在 A3/A4 接入。工具是闭包，捕获 app.state 上的只读 reader；
工具内部零网络（除既有 RAG/服务自身行为），只做聚合读取并以脱敏文本返回。
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool


def build_read_tools(app_state: Any) -> list[BaseTool]:
    """按 app.state 装配读类工具；服务缺失的工具不注册（Agent 会如实说不可用）。"""
    tools: list[BaseTool] = []

    @tool
    def list_capabilities() -> str:
        """列出本 Agent 当前可用的能力与已装配的教学闭环服务，帮助判断能做什么。"""
        assembled = []
        for key, label in (
            ("rag_service", "教材 RAG"),
            ("knowledge_service", "知识点库"),
            ("roster_service", "名单/班级"),
            ("paper_service", "原卷"),
            ("assessment_service", "施测"),
            ("score_service", "成绩"),
            ("analysis_service", "学情分析"),
            ("practice_service", "针对练习"),
            ("lesson_plan_service", "教案"),
        ):
            if getattr(app_state, key, None) is not None:
                assembled.append(label)
        if not assembled:
            return "当前未装配任何教学闭环服务。"
        return "已装配的教学闭环服务：" + "、".join(assembled) + "。"

    tools.append(list_capabilities)
    return tools


__all__ = ["build_read_tools"]
