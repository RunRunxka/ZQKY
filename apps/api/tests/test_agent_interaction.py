"""Agent 交互工具（C1-4 弹窗选择）：confirm_context 组装候选 + interrupt/resume 映射。

- 候选组装：班级/施测/学情运行 → 选择卡选项（label=名称，description 含 id=xxx）；
- resume 映射：approve + value=label → 反查 ID 返回；reject → "未选择"；
- 无候选：直接返回提示（不弹卡）；服务缺失：返回不可用提示。

用 monkeypatch 控制 interrupt 返回值（无需真实图上下文），不触网。
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

import app.services.agent.tools_write as tw
from app.services.agent.tools_write import build_interaction_tools


class _Page:
    def __init__(self, items: list[Any]) -> None:
        self.items = items


class _View:
    def __init__(self, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _FakeRoster:
    def list_classes(self, *, limit: int = 50):  # noqa: ANN001, ANN201, ARG002
        return _Page([
            _View(id="c1", name="三一班", student_count=12),
            _View(id="c2", name=None, student_count=0),
        ])


class _FakeAssessments:
    def list_assessments(self, *, limit: int = 50):  # noqa: ANN001, ANN201, ARG002
        return _Page([
            _View(assessment_id="a1", title="期中数学", paper_title="期中卷"),
        ])


class _FakeAnalysis:
    def list_runs(self, *, limit: int = 50):  # noqa: ANN001, ANN201, ARG002
        return _Page([
            _View(run_id="r1234567890", assessment_id="a1", report_ready=True),
        ])


class _EmptyRoster:
    def list_classes(self, *, limit: int = 50):  # noqa: ANN001, ANN201, ARG002
        return _Page([])


def _state(**services: Any) -> Any:
    class _S:
        pass

    s = _S()
    for key, value in services.items():
        setattr(s, key, value)
    return s


def _tool(state: Any) -> Any:
    return {t.name: t for t in build_interaction_tools(state)}["confirm_context"]


class TestCandidates:
    def test_class_options(self) -> None:
        state = _state(roster_service=_FakeRoster())
        # interrupt 无图上下文会抛 KeyError('__pregel_scratchpad')：先只验证候选组装前置逻辑
        with pytest.raises(BaseException) as excinfo:
            _tool(state).invoke({"need": "class"})
        assert isinstance(excinfo.value, KeyError)

    def test_empty_candidates_no_interrupt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tw, "interrupt", lambda payload: (_ for _ in ()).throw(AssertionError("不应弹卡")))
        state = _state(roster_service=_EmptyRoster())
        out = _tool(state).invoke({"need": "class"})
        assert "没有任何可选" in out

    def test_unknown_need(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tw, "interrupt", lambda payload: (_ for _ in ()).throw(AssertionError("不应弹卡")))
        state = _state()
        out = _tool(state).invoke({"need": "nonsense"})
        assert "无法" in out


class TestSubjectSelection:
    def test_subject_options_use_taxonomy_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """学科选择卡来自固定字典（id=math 等），供 create_lesson_plan_draft 直接使用。"""
        captured: dict = {}
        monkeypatch.setattr(tw, "interrupt", lambda payload: captured.update(payload) or (_ for _ in ()).throw(SystemExit))
        with pytest.raises(SystemExit):
            _tool(_state()).invoke({"need": "subject"})
        assert captured.get("kind") == "select"
        assert captured.get("prompt") == "选择学科"
        assert {"label": "数学", "description": "id=math"} in captured.get("options", [])
        assert {"label": "语文", "description": "id=chinese"} in captured.get("options", [])


class TestResume:
    def test_resume_label_maps_to_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """approve + value=班级名 → 反查 id= 返回。"""
        monkeypatch.setattr(tw, "interrupt", lambda payload: {"decision": "approve", "value": "三一班"})
        state = _state(roster_service=_FakeRoster())
        out = _tool(state).invoke({"need": "class"})
        assert "c1" in out

    def test_resume_label_without_name_uses_item_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """name 为 None 的班级 label=id 本身。"""
        monkeypatch.setattr(tw, "interrupt", lambda payload: {"decision": "approve", "value": "c2"})
        state = _state(roster_service=_FakeRoster())
        out = _tool(state).invoke({"need": "class"})
        assert "c2" in out

    def test_reject_returns_not_selected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tw, "interrupt", lambda payload: {"decision": "reject"})
        state = _state(roster_service=_FakeRoster())
        out = _tool(state).invoke({"need": "class"})
        assert "未选择" in out

    def test_select_interrupt_payload_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """弹卡载荷必须是 kind=select + prompt + options（前端按此渲染选择卡）。"""
        captured: dict = {}
        monkeypatch.setattr(tw, "interrupt", lambda payload: captured.update(payload) or (_ for _ in ()).throw(SystemExit))
        state = _state(assessment_service=_FakeAssessments())
        with pytest.raises(SystemExit):
            _tool(state).invoke({"need": "assessment"})
        assert captured.get("kind") == "select"
        assert captured.get("prompt") == "选择施测（出学情的来源）"
        assert captured.get("options") == [
            {"label": "期中数学", "description": "id=a1，期中卷"},
        ]
