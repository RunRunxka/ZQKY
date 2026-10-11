"""R0-C：LangChain 结构化输出/文本运行器行为回归。

不触网：用假模型（实现 ``with_structured_output`` / ``ainvoke``）验证：

- 成功直接返回解析结果（Pydantic 实例）；
- 解析失败自动重试，且第二次调用携带纠正提示；
- 重试耗尽降级为 outcome（不抛异常——「AI 只进候选」的落点）；
- 传输异常与超时同样降级；
- 提示词登记：指纹稳定、同版本不同内容被拒绝、缺 id 报 PromptNotFound。
"""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.services.llm.prompts import (
    PromptNotFound,
    PromptSpec,
    get_prompt,
    prompt_fingerprint,
    register_prompt,
    registered_prompts,
)
from app.services.llm.runner import run_structured, run_text


class _Draft(BaseModel):
    title: str
    count: int


def _spec(prompt_id: str = "test.runner.draft", version: str = "v1") -> PromptSpec:
    return PromptSpec(
        id=prompt_id,
        version=version,
        system="你是测试助手。",
        human="为 {topic} 生成草稿。",
    )


VARS = {"topic": "二次函数"}


def _joined(messages) -> str:  # noqa: ANN001, ANN202
    return "\n".join(str(getattr(m, "content", m)) for m in messages)


class _StructuredRunnable:
    def __init__(self, model: "_FakeModel") -> None:
        self._model = model

    async def ainvoke(self, messages, config=None):  # noqa: ANN001, ANN202, ARG002
        self._model.calls.append(list(messages))
        item = self._model.results.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, float):  # 约定：float 表示"睡眠这么多秒再返回空结构"
            await asyncio.sleep(item)
            item = {"raw": AIMessage(content=""), "parsed": None, "parsing_error": None}
        return item


class _FakeModel:
    """极简假模型：results 逐次弹出；也支持 run_text 的 ainvoke 路径。"""

    def __init__(self, results: list[object], text_results: list[object] | None = None) -> None:
        self.results = list(results)
        self.text_results = list(text_results or [])
        self.calls: list[list] = []
        self.structured_kwargs: dict | None = None

    def with_structured_output(self, schema, *, include_raw=False, **kwargs):  # noqa: ANN001, ANN202
        self.structured_kwargs = {"schema": schema, "include_raw": include_raw, **kwargs}
        return _StructuredRunnable(self)

    async def ainvoke(self, messages, config=None):  # noqa: ANN001, ANN202, ARG002
        self.calls.append(list(messages))
        item = self.text_results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def test_structured_success_returns_parsed_instance() -> None:
    model = _FakeModel([{"raw": AIMessage(content='{"title":"a","count":1}'), "parsed": None, "parsing_error": None}])
    model.results[0]["parsed"] = _Draft(title="a", count=1)
    outcome = asyncio.run(
        run_structured(model, prompt=_spec(), schema=_Draft, variables={"topic": "二次函数"})
    )
    assert outcome.ok
    assert outcome.parsed == _Draft(title="a", count=1)
    assert outcome.attempts == 1
    assert model.structured_kwargs == {"schema": _Draft, "include_raw": True}
    assert "二次函数" in _joined(model.calls[0])


def test_structured_retries_with_corrective_note() -> None:
    model = _FakeModel(
        [
            {"raw": AIMessage(content="无法解析"), "parsed": None, "parsing_error": ValueError("bad json")},
            {"raw": AIMessage(content='{"title":"b","count":2}'), "parsed": _Draft(title="b", count=2), "parsing_error": None},
        ]
    )
    outcome = asyncio.run(run_structured(model, prompt=_spec(), schema=_Draft, variables=VARS))
    assert outcome.ok
    assert outcome.attempts == 2
    assert len(model.calls) == 2
    # 首次调用不带纠正提示；第二次追加
    assert "不要附加解释" not in _joined(model.calls[0])
    assert "不要附加解释" in _joined(model.calls[1])


def test_structured_exhausted_degrades_without_raising() -> None:
    model = _FakeModel(
        [
            {"raw": AIMessage(content="nope-1"), "parsed": None, "parsing_error": ValueError("bad")},
            {"raw": AIMessage(content="nope-2"), "parsed": None, "parsing_error": ValueError("bad")},
        ]
    )
    outcome = asyncio.run(
        run_structured(model, prompt=_spec(), schema=_Draft, variables=VARS, max_attempts=2)
    )
    assert not outcome.ok
    assert outcome.parsed is None
    assert outcome.attempts == 2
    assert outcome.raw_text == "nope-2"
    assert outcome.error is not None and "结构化解析失败" in outcome.error


def test_structured_transport_error_degrades() -> None:
    model = _FakeModel([RuntimeError("upstream 500"), {"raw": AIMessage(content=""), "parsed": _Draft(title="c", count=3), "parsing_error": None}])
    outcome = asyncio.run(run_structured(model, prompt=_spec(), schema=_Draft, variables=VARS))
    assert outcome.ok
    assert outcome.attempts == 2


def test_structured_timeout_degrades() -> None:
    model = _FakeModel([5.0, 5.0])  # 每次都睡 5 秒，必定超时
    outcome = asyncio.run(
        run_structured(
            model, prompt=_spec(), schema=_Draft, variables=VARS, max_attempts=1, timeout_s=0.01
        )
    )
    assert not outcome.ok
    assert outcome.error is not None and "TimeoutError" in outcome.error


def test_structured_method_passthrough() -> None:
    model = _FakeModel([{"raw": AIMessage(content=""), "parsed": _Draft(title="d", count=4), "parsing_error": None}])
    asyncio.run(run_structured(model, prompt=_spec(), schema=_Draft, variables=VARS, method="json_mode"))
    assert model.structured_kwargs is not None
    assert model.structured_kwargs.get("method") == "json_mode"


def test_run_text_success_and_empty() -> None:
    ok_model = _FakeModel([], text_results=[AIMessage(content="  分析结论  ")])
    outcome = asyncio.run(run_text(ok_model, prompt=_spec(), variables=VARS))
    assert outcome.ok and outcome.text == "分析结论"

    empty_model = _FakeModel([], text_results=[AIMessage(content=""), AIMessage(content="")])
    failed = asyncio.run(run_text(empty_model, prompt=_spec(), variables=VARS, max_attempts=2))
    assert not failed.ok
    assert failed.error == "模型返回空文本"
    assert failed.attempts == 2


def test_prompt_registry_versioning_and_fingerprint() -> None:
    spec = _spec()
    register_prompt(spec)
    assert get_prompt(spec.id) == spec
    assert prompt_fingerprint(spec.id) == spec.fingerprint
    assert spec.id in registered_prompts()

    # 同 id 同版本不同内容 → 拒绝（必须升版）
    with pytest.raises(ValueError):
        register_prompt(PromptSpec(id=spec.id, version=spec.version, human="改过的模板"))

    # 升版允许，且指纹变化
    newer = register_prompt(PromptSpec(id=spec.id, version="v2", human=spec.human))
    assert newer.version == "v2"
    assert newer.fingerprint != spec.fingerprint

    with pytest.raises(PromptNotFound):
        get_prompt("test.runner.missing")
    with pytest.raises(ValueError):
        PromptSpec(id="", version="v1", human="x")
