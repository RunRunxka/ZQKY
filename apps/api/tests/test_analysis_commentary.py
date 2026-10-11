"""AI 学情评价（C2-3）：脱敏构造 + 生成流程回归。

- build_prompt：学生姓名/学号/人员 ID 不进提示词（代称学生A/B…），班级名与知识点名保留；
- generate_from_report：假 handle 返回文本；空文本 → EMPTY_RESPONSE；
- 解析失败（run 未就绪）→ read_ready_report 原样抛（409 REPORT_NOT_READY 由 service 层给）。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import AppError
from app.services.analysis.commentary import build_prompt, generate_from_report
from tests.analysis_support import AnalysisScene


def _report() -> dict:
    return {
        "paperTitle": "期中数学卷",
        "selectionSnapshot": {"participantCount": 2, "uniqueStudentCount": 2},
        "participants": [
            {"participantId": "p-full-uuid-001"},
            {"participantId": "p-full-uuid-002"},
        ],
        "classes": [
            {"className": "三一班", "knowledgePoint": {"knowledgePointId": "kp1", "name": "分数的意义"},
             "needsCount": 1, "validCount": 2, "ratio": 0.5},
        ],
        "students": [
            {"participant": {"participantId": "p-full-uuid-001", "name": "张三", "studentNo": "20240101"},
             "knowledgePoint": {"knowledgePointId": "kp1", "name": "分数的意义"},
             "observation": "needs_consolidation", "informationIncomplete": False,
             "expectedCount": 2, "validCount": 2, "totalScoreUnits": 30, "totalMaxScoreUnits": 100},
            {"participant": {"participantId": "p-full-uuid-002", "name": "李四", "studentNo": "20240102"},
             "knowledgePoint": {"knowledgePointId": "kp1", "name": "分数的意义"},
             "observation": "full_credit", "informationIncomplete": True,
             "expectedCount": 2, "validCount": 1, "totalScoreUnits": None, "totalMaxScoreUnits": 100},
        ],
    }


class TestBuildPrompt:
    def test_students_are_anonymized(self) -> None:
        prompt = build_prompt(_report())
        # 姓名/学号绝不出现；代称出现
        assert "张三" not in prompt
        assert "李四" not in prompt
        assert "20240101" not in prompt
        assert "学生A" in prompt and "学生B" in prompt
        # 班级名与知识点名保留
        assert "三一班" in prompt and "分数的意义" in prompt
        # 观察与信息不全标注
        assert "信息不全" in prompt

    def test_more_than_26_participants_fall_back(self) -> None:
        report = _report()
        report["participants"] = [{"participantId": f"p{i}"} for i in range(30)]
        report["students"] = [
            {"participant": {"participantId": f"p{i}"}, "knowledgePoint": {"knowledgePointId": "kp1", "name": "kp"},
             "observation": "needs_consolidation", "informationIncomplete": False,
             "expectedCount": 1, "validCount": 1, "totalScoreUnits": 1, "totalMaxScoreUnits": 1}
            for i in range(30)
        ]
        prompt = build_prompt(report)
        assert "学生A" in prompt and "学生27" in prompt


class _FakeHandle:
    def __init__(self, text: str) -> None:
        self._text = text
        from app.providers.llm.base import LLMConfig
        from app.schemas.model_config import ModelProtocol

        self.config = LLMConfig(protocol=ModelProtocol.openai_chat, baseUrl="http://127.0.0.1:9/v1", modelId="m")
        self.captured: Any = None
        self.provider = self  # ChatModelHandle.provider 的最小替身

    async def complete(self, config, request):  # noqa: ANN001, ANN201
        self.captured = request
        from app.providers.llm.base import LLMResponse

        return LLMResponse(text=self._text, finishReason="stop")


class TestGenerate:
    async def test_returns_model_text(self) -> None:
        handle = _FakeHandle("## 评价\n整体良好。")
        text = await generate_from_report(_report(), lambda _pid: handle, "p1")
        assert "评价" in text
        # 系统提示含脱敏规则，用户消息含匿名数据
        assert "学生A" in handle.captured.messages[1].content
        assert "张三" not in handle.captured.messages[1].content

    async def test_empty_text_rejected(self) -> None:
        handle = _FakeHandle("  ")
        with pytest.raises(AppError) as excinfo:
            await generate_from_report(_report(), lambda _pid: handle, "p1")
        assert excinfo.value.code == "EMPTY_RESPONSE"


@pytest.mark.asyncio
async def test_unready_run_raises(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError) as excinfo:
        scene.service.read_ready_report(receipt.run_id)
    assert excinfo.value.code == "REPORT_NOT_READY"
