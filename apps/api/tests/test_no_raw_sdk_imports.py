"""门禁：业务代码不得直连供应商 SDK（必须统一经 LangChain + LangGraph）。

用户裁定：全部教学闭环 LLM 能力用 langchain + langgraph 实现。本测试扫描
``app/**/*.py``（排除 providers 协议适配层之外的任何位置也一样禁止）中出现：

- ``import openai`` / ``from openai ...`` / ``import anthropic`` / ``from anthropic ...``
- 供应商 SDK 客户端构造 ``OpenAI(`` / ``AsyncOpenAI(`` / ``Anthropic(`` / ``AsyncAnthropic(``

LangChain 的 ``ChatOpenAI(`` / ``ChatAnthropic(`` 不受影响（其前缀为单词字符，
不会命中词边界规则）。
"""

from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

_SDK_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(?:openai|anthropic)(?:\b|\.)",
    re.MULTILINE,
)
_SDK_CONSTRUCTOR = re.compile(
    r"(?:(?<![\w.])(?:Async)?OpenAI\(|(?<![\w.])(?:Async)?Anthropic\()",
)


def _scan() -> list[str]:
    offenders: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _SDK_IMPORT.search(line) or _SDK_CONSTRUCTOR.search(line):
                offenders.append(f"{path.relative_to(APP_ROOT)}:{lineno}: {stripped}")
    return offenders


def test_no_raw_vendor_sdk_usage() -> None:
    offenders = _scan()
    assert offenders == [], (
        "发现绕过 LangChain 的供应商 SDK 直连（必须统一经 model_runtime + "
        "app.services.llm 运行层）：\n" + "\n".join(offenders)
    )
