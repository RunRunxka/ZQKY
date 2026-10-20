"""Agent 流事件的跨层标签。

工具内部再调用 LLM（例如对话生成教案时按模块并行结构化生成）时，LangChain 的事件
会冒泡到外层 ``astream_events``。这些 token 是工具的中间产物，不应作为聊天正文推给
教师；调用方给内部模型加本标签，Agent 运行器按标签过滤。
"""

INTERNAL_TOOL_LLM_TAG = "zqky-internal-tool-llm"

__all__ = ["INTERNAL_TOOL_LLM_TAG"]
