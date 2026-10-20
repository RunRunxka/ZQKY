"""Agent 读工具（A3）正确行为回归：脱敏、分页、截断、服务缺失不注册。

红线断言：
- 名单/施测类工具**不返回**学生姓名/学号（name/studentNo 被剥离），只给匿名计数与业务 ID；
- 工具按服务装配情况注册（缺失服务不注册，Agent 不误报可用）；
- 返回文本超预算截断并标注。

全部用假服务对象，不触网、不读写正式数据目录。
"""

from __future__ import annotations

import asyncio
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
    def __init__(self) -> None:
        self.class_calls: list[dict] = []

    def list_classes(self, *, offset=0, limit=50):  # noqa: ANN001, ANN201
        self.class_calls.append({"offset": offset, "limit": limit})
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

    def test_list_classes_schema_has_no_status(self) -> None:
        """工具 schema 不含 status 参数（归档全局移除后不再有状态过滤入口）。"""
        tool = _tools_by_name(_State(roster_service=_FakeRoster()))["list_classes"]
        assert "status" not in tool.args
        assert "limit" in tool.args

    def test_list_classes_never_passes_status_to_service(self) -> None:
        """工具固定按「全部班级」调用服务，不透传任何状态过滤。"""
        roster = _FakeRoster()
        state = _State(roster_service=roster)
        tool = _tools_by_name(state)["list_classes"]
        tool.invoke({})
        tool.invoke({"status": "null"})  # 模型残留的历史入参：被 schema 忽略，不透传
        assert roster.class_calls
        for call in roster.class_calls:
            assert set(call) == {"offset", "limit"}
        assert roster.class_calls[0]["limit"] == 30

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


class _FakeSearchHit:
    """SearchHit 的最小替身（工具只读这些属性）。"""

    def __init__(self, title: str, chapter_path: tuple[str, ...], excerpt: str) -> None:
        self.document_title = title
        self.edition_label = "人教A版"
        self.subject_label = "数学"
        self.chapter_path = chapter_path
        self.excerpt = excerpt


class _FakeTextbookSearch:
    def __init__(self, hits: list[_FakeSearchHit] | None = None, error: Exception | None = None) -> None:
        self.hits = hits if hits is not None else [
            _FakeSearchHit("高中数学必修第一册", ("第一章 集合与函数", "1.1 集合的概念"), "集合元素具有确定性。")
        ]
        self.error = error
        self.calls: list[dict] = []

    def search(self, query, *, limit=6, subject_id=None):  # noqa: ANN001, ANN201
        self.calls.append({"query": query, "limit": limit, "subject_id": subject_id})
        if self.error is not None:
            raise self.error
        return self.hits


class TestSearchTextbooksTool:
    def test_missing_service_not_registered(self) -> None:
        tools = _tools_by_name(_State())
        assert "search_textbooks" not in tools

    def test_registered_when_service_present_and_lists_capability(self) -> None:
        state = _State(textbook_search=_FakeTextbookSearch())
        tools = _tools_by_name(state)
        assert "search_textbooks" in tools
        assert "教材检索" in tools["list_capabilities"].invoke({})

    def test_search_reports_title_and_chapter_path(self) -> None:
        state = _State(textbook_search=_FakeTextbookSearch())
        out = asyncio.run(_tools_by_name(state)["search_textbooks"].ainvoke({"query": "集合的概念"}))
        assert "高中数学必修第一册" in out
        assert "第一章 集合与函数" in out
        assert "集合元素具有确定性。" in out
        assert "共 1 条" in out

    def test_search_passes_args_to_service(self) -> None:
        fake = _FakeTextbookSearch()
        state = _State(textbook_search=fake)
        asyncio.run(
            _tools_by_name(state)["search_textbooks"].ainvoke(
                {"query": "函数的单调性", "limit": 2, "subject_id": "math"}
            )
        )
        assert fake.calls == [{"query": "函数的单调性", "limit": 2, "subject_id": "math"}]

    def test_search_empty_result_is_honest(self) -> None:
        state = _State(textbook_search=_FakeTextbookSearch(hits=[]))
        out = asyncio.run(_tools_by_name(state)["search_textbooks"].ainvoke({"query": "微积分"}))
        assert "没有检索到" in out

    def test_search_service_error_is_reported_not_faked(self) -> None:
        """服务报错（如索引未就绪）：工具如实返回错误，不返回空结果冒充成功。"""
        fake = _FakeTextbookSearch(error=Exception("当前没有已发布的教材索引代"))
        state = _State(textbook_search=fake)
        out = asyncio.run(_tools_by_name(state)["search_textbooks"].ainvoke({"query": "函数"}))
        assert "教材检索当前不可用" in out
        assert "当前没有已发布的教材索引代" in out

    def test_search_long_output_clipped(self) -> None:
        """多命中超长输出按工具预算截断并标注。"""
        hits = [
            _FakeSearchHit(f"教材第{i}册", (f"第{i}章",), "原文片段。" * 500)
            for i in range(1, 11)
        ]
        state = _State(textbook_search=_FakeTextbookSearch(hits=hits))
        out = asyncio.run(_tools_by_name(state)["search_textbooks"].ainvoke({"query": "函数"}))
        assert len(out) < 7000
        assert "已截断" in out


class TestClip:
    def test_list_subjects_always_registered(self) -> None:
        tools = _tools_by_name(_State())
        assert "list_subjects" in tools
        out = tools["list_subjects"].invoke({})
        assert "math=数学" in out and "chinese=语文" in out

    def test_clip_truncates_long_text(self) -> None:
        long_text = "x" * 7000
        clipped = _clip(long_text)
        assert len(clipped) < 7000
        assert "已截断" in clipped

    def test_clip_keeps_short_text(self) -> None:
        assert _clip("short") == "short"
