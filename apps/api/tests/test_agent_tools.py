"""Agent 读工具（A3）正确行为回归：脱敏、分页、截断、服务缺失不注册。

红线断言：
- 名单/施测类工具**不返回**学生姓名/学号（name/studentNo 被剥离），只给匿名计数与业务 ID；
- 工具按服务装配情况注册（缺失服务不注册，Agent 不误报可用）；
- 返回文本超预算截断并标注。

全部用假服务对象，不触网、不读写正式数据目录。
"""

from __future__ import annotations

from typing import Any

from app.services.agent.tools import _clip, _strip_person, build_read_tools


class _Page:
    def __init__(self, items: list[Any], total: int) -> None:
        self.items = items
        self.total = total
        self.offset = 0
        self.limit = 50


class _View:
    """最小 pydantic 替代品：model_dump 返回构造 dict。"""

    def __init__(self, data: dict) -> None:
        self._data = data

    def model_dump(self, by_alias: bool = True, mode: str = "json") -> dict:  # noqa: ARG002
        return dict(self._data)


class _FakeRoster:
    def list_classes(self, *, status=None, offset=0, limit=50):  # noqa: ANN001, ANN201, ARG002
        return _Page(
            [_View({"id": "c1", "name": "三一班", "gradeId": "g3", "studentCount": 12, "status": "active"})],
            total=1,
        )

    def list_class_students(self, class_id: str, *, include_archived: bool = False):  # noqa: ANN001, ANN201, ARG002
        return _Page(
            [
                _View({"id": "s1", "name": "张三", "studentNo": "20240101", "status": "active"}),
                _View({"id": "s2", "name": "李四", "studentNo": "20240102", "status": "active"}),
            ],
            total=2,
        )


class _FakeAnalysis:
    def list_runs(self, *, assessment_id=None, offset=0, limit=50):  # noqa: ANN001, ANN201, ARG002
        return _Page([_View({"runId": "r1", "assessmentId": "a1", "reportReady": True})], total=1)

    def list_report_rows(self, run_id, kind, *, offset=0, limit=50):  # noqa: ANN001, ANN201, ARG002
        return _Page(
            [
                _View({
                    "knowledgePoint": {"knowledgePointId": "kp1", "name": "分数的意义"},
                    "needsCount": 5,
                    "validCount": 12,
                }),
                _View({
                    "knowledgePoint": {"knowledgePointId": "kp2", "name": "分数加法"},
                    "needsCount": 0,
                    "validCount": 12,
                }),
            ],
            total=2,
        )


class _FakeKnowledge:
    def list_points(self, *, subject_id=None, q=None, offset=0, limit=50):  # noqa: ANN001, ANN201, ARG002
        return _Page(
            [_View({"id": "kp1", "code": "F1", "name": "分数的意义", "gradeIds": ["g3"]})],
            total=1,
        )

    def get_point(self, point_id):  # noqa: ANN001, ANN201
        return _View({"id": point_id, "code": "F1", "name": "分数的意义", "description": "认识分数", "gradeIds": ["g3"], "aliases": ["分数"], "subjectId": "math"})


class _State:
    def __init__(self, **services: Any) -> None:
        for key, value in services.items():
            setattr(self, key, value)


def _tools_by_name(state: Any) -> dict[str, Any]:
    return {t.name: t for t in build_read_tools(state)}


class TestToolRegistration:
    def test_list_capabilities_always_registered(self) -> None:
        tools = _tools_by_name(_State())
        assert "list_capabilities" in tools

    def test_missing_service_not_registered(self) -> None:
        """缺 roster 时不注册名单类工具（不误报可用）。"""
        tools = _tools_by_name(_State(analysis_service=_FakeAnalysis()))
        assert "list_classes" not in tools
        assert "get_class_student_count" not in tools
        assert "list_analysis_runs" in tools

    def test_full_assembly(self) -> None:
        state = _State(
            roster_service=_FakeRoster(),
            analysis_service=_FakeAnalysis(),
            knowledge_service=_FakeKnowledge(),
        )
        tools = _tools_by_name(state)
        for name in ("list_classes", "list_analysis_runs", "get_needs_consolidation", "list_knowledge_points"):
            assert name in tools


class TestPrivacyRedaction:
    def test_strip_person_removes_student_id_fields(self) -> None:
        raw = {
            "id": "s1",
            "name": "三一班",  # 班级名：合法业务信息，保留
            "studentNo": "20240101",
            "nested": {"nameSnapshot": "张三", "classId": "c1"},
            "items": [{"studentNoSnapshot": "20240101", "attemptNo": 1}],
        }
        cleaned = _strip_person(raw)
        assert cleaned["name"] == "三一班"  # 班级名保留
        assert "studentNo" not in cleaned
        assert "nameSnapshot" not in cleaned["nested"]
        assert cleaned["nested"]["classId"] == "c1"
        assert "studentNoSnapshot" not in cleaned["items"][0]
        assert cleaned["items"][0]["attemptNo"] == 1

    def test_student_count_tool_returns_count_only(self) -> None:
        state = _State(roster_service=_FakeRoster())
        tool = _tools_by_name(state)["get_class_student_count"]
        out = tool.invoke({"class_id": "c1"})
        assert "2 名学生" in out
        # 不泄漏任何姓名/学号
        assert "张三" not in out and "李四" not in out
        assert "20240101" not in out


class TestReadTools:
    def test_list_classes(self) -> None:
        state = _State(roster_service=_FakeRoster())
        out = _tools_by_name(state)["list_classes"].invoke({})
        assert "共 1 条" in out
        assert "三一班" in out

    def test_needs_consolidation_filters_zero(self) -> None:
        """只报告 needsCount>0 的知识点；为 0 的不列。"""
        state = _State(analysis_service=_FakeAnalysis())
        out = _tools_by_name(state)["get_needs_consolidation"].invoke({"run_id": "r1"})
        assert "分数的意义" in out
        assert "5/12" in out
        assert "分数加法" not in out  # needsCount=0 不列

    def test_needs_consolidation_empty(self) -> None:
        class _Empty:
            def list_report_rows(self, run_id, kind, *, offset=0, limit=50):  # noqa: ANN001, ANN201, ARG002
                return _Page([], total=0)

        state = _State(analysis_service=_Empty())
        out = _tools_by_name(state)["get_needs_consolidation"].invoke({"run_id": "r1"})
        assert "没有需巩固" in out

    def test_get_knowledge_point(self) -> None:
        state = _State(knowledge_service=_FakeKnowledge())
        out = _tools_by_name(state)["get_knowledge_point"].invoke({"knowledge_point_id": "kp1"})
        assert "分数的意义" in out


class TestClip:
    def test_clip_truncates_long_text(self) -> None:
        long_text = "x" * 7000
        clipped = _clip(long_text)
        assert len(clipped) < 7000
        assert "已截断" in clipped

    def test_clip_keeps_short_text(self) -> None:
        assert _clip("short") == "short"
