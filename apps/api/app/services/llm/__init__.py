"""LangChain 运行层（R0-C）：提示词登记 + 结构化输出/文本运行器。

纪律：全部模块 LLM 调用统一经 ``model_runtime`` 解析出 LangChain 模型后使用本层；
禁止绕过本层直连供应商 SDK（门禁：``tests/test_no_raw_sdk_imports.py``）。
"""

from app.services.llm.prompts import (
    PromptNotFound,
    PromptSpec,
    get_prompt,
    prompt_fingerprint,
    register_prompt,
    registered_prompts,
)
from app.services.llm.runner import (
    StructuredMethod,
    StructuredOutcome,
    TextOutcome,
    run_structured,
    run_text,
)

__all__ = [
    "PromptNotFound",
    "PromptSpec",
    "StructuredMethod",
    "StructuredOutcome",
    "TextOutcome",
    "get_prompt",
    "prompt_fingerprint",
    "register_prompt",
    "registered_prompts",
    "run_structured",
    "run_text",
]
