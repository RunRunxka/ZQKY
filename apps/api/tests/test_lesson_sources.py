"""教案来源：教师上传学情材料（2026-10-13 补齐 ``POST /lesson-plans/source-uploads``）。

此前该端点只有前端调用、后端未实现（501 ``FEATURE_NOT_IMPLEMENTED``），且生成流声明不消费
``sourceAssetRef``。本套件钉住补齐后的口径：

- 上传：文档类（.docx/.pdf/.txt/.md）落受管资产并返回 ``assetRef``；成绩表类
  （.xlsx/.xls/.csv）422 且给出「去学情分析生成报告、用『分析报告』来源」的指引
  （不把含学号/姓名的原始表格送进模型）；空文件 422、超限 413；
- 读回：材料文本按上限截断并标注；缺资产 404；无可提取文本 422；不静默忽略来源；
- 生成流：``sourceAssetRef`` 真正进固定数据上下文（HTTP 级验证），坏引用直接失败。
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.core.config import Settings
from app.main import create_app
from app.services.lesson_sources import (
    MAX_MATERIAL_CHARS,
    MAX_SOURCE_BYTES,
    TRUNCATION_NOTE,
    LessonSourceMaterial,
)
from app.services.lesson_streaming.service import build_context

ALLOWED = frozenset({"http://127.0.0.1:5173"})


def _client(data_dir: Path) -> TestClient:
    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=data_dir)
    app = create_app(settings, bootstrap_textbooks=False)
    return TestClient(app, base_url="http://127.0.0.1:8001")


def _service(client: TestClient):
    return client.app.state.lesson_source_service


def _docx_bytes(text: str) -> bytes:
    """最小 docx（python-docx 内存构建），用于验证 docx 文本提取。"""
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


class TestUpload:
    def test_txt_upload_registers_asset_and_returns_ref(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("学情说明.txt", "本次单元测班级整体偏弱在导数应用。".encode("utf-8"), "text/plain")},
            )
            assert resp.status_code == 201, resp.text
            body = resp.json()
            assert body["fileName"] == "学情说明.txt"
            assert len(body["sha256"]) == 64
            assert body["byteSize"] > 0
            # assetRef 即受管资产 id：按它可以读回材料正文
            material = _service(client).read_material(body["assetRef"])
            assert material.file_name == "学情说明.txt"
            assert "导数应用" in material.text
            assert material.truncated is False

    def test_docx_upload_extracts_text(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={
                    "file": (
                        "学情.docx",
                        _docx_bytes("本班在函数单调性上失分较多。"),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert resp.status_code == 201, resp.text
            material = _service(client).read_material(resp.json()["assetRef"])
            assert "函数单调性" in material.text

    def test_spreadsheet_is_rejected_with_analysis_guidance(self, tmp_path: Path) -> None:
        """成绩表类不直接接收：422 + 明确指引（红线：不把含姓名的原始表格送模型）。"""
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("小题分.xlsx", b"PK fake xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert resp.status_code == 422, resp.text
            body = resp.json()
            assert body["code"] == "LESSON_SOURCE_UNSUPPORTED"
            assert "学情分析" in body["message"] and "分析报告" in body["message"]

    def test_unknown_suffix_is_rejected(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("病毒.exe", b"MZ", "application/octet-stream")},
            )
            assert resp.status_code == 422
            assert resp.json()["code"] == "LESSON_SOURCE_UNSUPPORTED"

    def test_empty_upload_is_rejected(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("空说明.txt", b"", "text/plain")},
            )
            assert resp.status_code == 422
            assert resp.json()["code"] == "INVALID_REQUEST"

    def test_oversize_upload_is_413(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            payload = b"a" * (MAX_SOURCE_BYTES + 1)
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("大文件.txt", payload, "text/plain")},
            )
            assert resp.status_code == 413
            assert resp.json()["code"] == "UPLOAD_TOO_LARGE"

    def test_missing_file_part_is_422(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"other": ("x.txt", b"abc", "text/plain")},
            )
            assert resp.status_code == 422
            assert resp.json()["code"] == "INVALID_REQUEST"


class TestReadMaterial:
    def test_truncates_with_explicit_note(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            long_text = "学" * (MAX_MATERIAL_CHARS + 500)
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("长说明.md", long_text.encode("utf-8"), "text/markdown")},
            )
            assert resp.status_code == 201, resp.text
            material = _service(client).read_material(resp.json()["assetRef"])
            assert material.truncated is True
            assert material.text.endswith(TRUNCATION_NOTE)
            assert len(material.text) == MAX_MATERIAL_CHARS + len(TRUNCATION_NOTE)

    def test_unknown_asset_is_404_not_silent_ignore(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            with pytest.raises(Exception) as excinfo:
                _service(client).read_material("no-such-asset")
            error = excinfo.value
            assert getattr(error, "code", None) == "LESSON_SOURCE_NOT_FOUND"
            assert getattr(error, "status_code", None) == 404

    def test_whitespace_only_text_is_422(self, tmp_path: Path) -> None:
        """提取为空（如无文本层）：如实 422，不把空材料当有效来源。"""
        with _client(tmp_path) as client:
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("空内容.txt", b"   \n  \n", "text/plain")},
            )
            assert resp.status_code == 201, resp.text
            with pytest.raises(Exception) as excinfo:
                _service(client).read_material(resp.json()["assetRef"])
            assert getattr(excinfo.value, "code", None) == "LESSON_SOURCE_EMPTY"


class TestContextInjection:
    def test_build_context_includes_material_section(self) -> None:
        material = LessonSourceMaterial(file_name="学情说明.md", text="班级薄弱点：导数应用。", truncated=False)
        context = build_context(None, [], "函数与导数", "", material)
        assert "【教师上传的学情材料（学情说明.md，原文摘录）】" in context
        assert "导数应用" in context

    def test_build_context_omits_section_without_material(self) -> None:
        assert "教师上传的学情材料" not in build_context(None, [], "函数与导数", "")


class TestAssemblyBoundary:
    def test_missing_service_is_503_not_501(self, tmp_path: Path) -> None:
        """服务未装配时路由 503（缺依赖如实失败），不是 501 占位、也不是假成功。"""
        with _client(tmp_path) as client:
            client.app.state.lesson_source_service = None
            resp = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("学情.txt", b"abc", "text/plain")},
            )
            assert resp.status_code == 503
            assert resp.json()["code"] == "SERVICE_UNAVAILABLE"


class _StreamChatModel:
    def __init__(self) -> None:
        self.prompts: list[list] = []

    async def astream(self, messages):  # noqa: ANN001, ANN201
        self.prompts.append(list(messages))
        yield AIMessage(content="正文")


class TestGenerationStreamConsumesSource:
    def test_uploaded_material_reaches_prompt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP 级：``sourceAssetRef`` 真正进固定数据（坏引用直接失败，不静默忽略）。"""
        model = _StreamChatModel()

        class _Handle:
            chat_model = model

        monkeypatch.setattr(
            "app.services.agent.model.resolve_agent_chat_model",
            lambda repo, secrets, profile_id: _Handle(),
        )

        with _client(tmp_path) as client:
            upload = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("学情.txt", "本班在导数应用上失分较多。".encode("utf-8"), "text/plain")},
            ).json()
            with client.stream(
                "POST",
                "/api/v1/lesson-plans/generation-stream",
                json={
                    "requestId": "r1",
                    "modelProfileId": "p",
                    "courseName": "函数与导数",
                    "sourceAssetRef": upload["assetRef"],
                    "modules": ["analysis"],
                },
            ) as resp:
                assert resp.status_code == 200, "".join(chunk for chunk in resp.iter_text())
                body = "".join(chunk for chunk in resp.iter_text())
            assert "module.delta" in body
            assert model.prompts, "模型未被调用"
            prompt = model.prompts[0][1].content
            assert "【教师上传的学情材料（学情.txt，原文摘录）】" in prompt
            assert "导数应用" in prompt

            # 坏引用：直接 404（证明该字段真的被消费，而不是被忽略）
            bad = client.post(
                "/api/v1/lesson-plans/generation-stream",
                json={
                    "requestId": "r2",
                    "modelProfileId": "p",
                    "sourceAssetRef": "no-such-asset",
                    "modules": ["analysis"],
                },
            )
            assert bad.status_code == 404
            assert bad.json()["code"] == "LESSON_SOURCE_NOT_FOUND"

    def test_material_does_not_break_event_sequence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _StreamChatModel()

        class _Handle:
            chat_model = model

        monkeypatch.setattr(
            "app.services.agent.model.resolve_agent_chat_model",
            lambda repo, secrets, profile_id: _Handle(),
        )
        with _client(tmp_path) as client:
            upload = client.post(
                "/api/v1/lesson-plans/source-uploads",
                files={"file": ("学情.txt", b"material", "text/plain")},
            ).json()
            with client.stream(
                "POST",
                "/api/v1/lesson-plans/generation-stream",
                json={
                    "requestId": "r3",
                    "modelProfileId": "p",
                    "sourceAssetRef": upload["assetRef"],
                    "modules": ["analysis", "objectives"],
                },
            ) as resp:
                body = "".join(chunk for chunk in resp.iter_text())
            events = [
                frame.split("event: ", 1)[1].split("\n", 1)[0]
                for frame in body.split("\n\n")
                if frame.startswith("event: ")
            ]
            assert events[0] == "message.start"
            assert events.count("module.done") == 2
            assert events[-1] == "message.end"
            for frame in body.split("\n\n"):
                if frame.startswith("data: "):
                    json.loads(frame.split("data: ", 1)[1])
