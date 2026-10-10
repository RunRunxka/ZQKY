"""Agent 确认闸门（A4）：上传端点 + 导入工具（读 assetRef 建草稿）+ confirm 工具 interrupt。

- 上传：空文件 422、超限 413、asset_store 未装配 503、正常落 blob 返回 sha256/assetId；
- 导入工具：按 assetRef 读字节调 create_import（产候选），返回草稿 ID；
- confirm 工具：内部 interrupt 挂起为 wait-confirm，decision!=approve 不写库。

全部用假服务 + tmp_path 资产目录，不触网、不读写正式数据目录。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.agent.tools_write import _blob_key, build_confirm_tools, build_import_tools
from app.services.assets.store import AssetStore


def _state(**services: Any) -> Any:
    class _S:
        pass

    s = _S()
    for key, value in services.items():
        setattr(s, key, value)
    return s


class TestBlobKey:
    def test_blob_key_format(self) -> None:
        assert _blob_key("abc123") == "blobs/abc123"


class TestImportTools:
    def test_import_paper_reads_blob_and_creates_draft(self, tmp_path: Path) -> None:
        """import_paper 按 assetRef 从 AssetStore 读字节，调 create_import 建草稿。"""
        assets = AssetStore(tmp_path / "assets")
        data = b"PK fake docx"
        stored = assets.store_original(data, media_type="application/octet-stream", original_name="t.docx")

        captured: dict = {}

        class _PaperView:
            def model_dump(self, by_alias: bool = True, mode: str = "json") -> dict:  # noqa: ARG002
                return {"paperId": "p1", "itemCount": 16, "status": "draft"}

        class _View:
            paper = _PaperView()
            warnings: list = []

        class _Papers:
            def create_import(self, *, file_name, content, media_type, subject_id, title=None):  # noqa: ANN001, ANN202
                captured["content"] = content
                captured["subject_id"] = subject_id
                return _View()

        state = _state(asset_store=assets, paper_service=_Papers())
        tool = {t.name: t for t in build_import_tools(state)}["import_paper"]
        out = tool.invoke({"asset_id": stored.sha256, "file_name": "t.docx", "subject_id": "math"})
        assert captured["content"] == data
        assert captured["subject_id"] == "math"
        assert "paperId=p1" in out
        assert "草稿" in out

    def test_import_tools_missing_service_not_registered(self, tmp_path: Path) -> None:
        state = _state(asset_store=AssetStore(tmp_path / "assets"))
        names = [t.name for t in build_import_tools(state)]
        assert names == []  # 无业务服务时不注册任何导入工具


class TestConfirmTool:
    def test_apply_lesson_proposal_interrupts(self, tmp_path: Path) -> None:
        """confirm 工具内部 interrupt：未恢复时不执行写操作。"""
        called: list = []

        class _Lessons:
            def apply_proposal(self, lesson_id, proposal_id, payload):  # noqa: ANN001, ANN202
                called.append((lesson_id, proposal_id))

        state = _state(lesson_plan_service=_Lessons())
        tool = {t.name: t for t in build_confirm_tools(state)}["apply_lesson_proposal"]
        # 工具内有 interrupt：无图上下文时 interrupt() 抛 KeyError('__pregel_scratchpad')
        # （它在图的 scratchpad 里找中断点），这正是 interrupt 被调用的证据。
        # 关键断言：在 interrupt 之前不调用写服务。
        try:
            tool.invoke({"lesson_id": "L1", "proposal_id": "P1", "summary": "改 3 处"})
        except BaseException as exc:
            name = type(exc).__name__
            is_interrupt = (
                "interrupt" in name.lower()
                or (isinstance(exc, KeyError) and "__pregel_scratchpad" in str(exc))
            )
            assert is_interrupt, f"预期 interrupt 信号，实际 {name}: {exc}"
        assert called == [], "interrupt 未恢复前不得执行写操作"

    def test_confirm_tools_missing_service_not_registered(self) -> None:
        state = _state()
        assert build_confirm_tools(state) == []


ALLOWED = frozenset({"http://127.0.0.1:5173"})


def _client(data_dir: Path, *, bootstrap: bool) -> TestClient:
    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=data_dir)
    app = create_app(settings, bootstrap_textbooks=bootstrap)
    return TestClient(app, base_url="http://127.0.0.1:8001")


class TestUploadEndpoint:
    def test_empty_file_422(self, tmp_path: Path) -> None:
        with _client(tmp_path, bootstrap=True) as client:
            resp = client.post(
                "/api/v1/agent/upload",
                files={"file": ("t.docx", b"", "application/octet-stream")},
            )
            assert resp.status_code == 422

    def test_upload_stores_blob(self, tmp_path: Path) -> None:
        with _client(tmp_path, bootstrap=True) as client:
            resp = client.post(
                "/api/v1/agent/upload",
                files={"file": ("t.docx", b"PK fake bytes", "application/octet-stream")},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["assetId"] == body["sha256"]
            assert body["byteSize"] == len(b"PK fake bytes")
            assert (tmp_path / "assets" / "blobs" / body["assetId"]).exists()

    def test_upload_service_unavailable_when_not_bootstrapped(self, tmp_path: Path) -> None:
        with _client(tmp_path, bootstrap=False) as client:
            resp = client.post(
                "/api/v1/agent/upload",
                files={"file": ("t.docx", b"PK fake", "application/octet-stream")},
            )
            assert resp.status_code == 503


class TestConfirmEndpoint:
    def test_confirm_model_not_found(self, tmp_path: Path) -> None:
        with _client(tmp_path, bootstrap=False) as client:
            resp = client.post(
                "/api/v1/agent/confirm",
                json={
                    "submissionId": "sub-12345678",
                    "requestId": "r1",
                    "threadId": "t1",
                    "modelProfileId": "no-such",
                    "confirmId": "k1",
                    "decision": "approve",
                },
            )
            assert resp.status_code == 404
            assert resp.json()["code"] == "MODEL_PROFILE_NOT_FOUND"

    def test_confirm_rejects_bad_decision(self, tmp_path: Path) -> None:
        with _client(tmp_path, bootstrap=False) as client:
            resp = client.post(
                "/api/v1/agent/confirm",
                json={
                    "submissionId": "sub-12345678",
                    "requestId": "r1",
                    "threadId": "t1",
                    "modelProfileId": "p",
                    "confirmId": "k1",
                    "decision": "maybe",
                },
            )
            assert resp.status_code == 422

    def test_confirm_rejects_short_submission_id(self, tmp_path: Path) -> None:
        """submissionId 幂等键至少 8 字符（与既有提交幂等纪律一致）。"""
        with _client(tmp_path, bootstrap=False) as client:
            resp = client.post(
                "/api/v1/agent/confirm",
                json={
                    "submissionId": "short",
                    "requestId": "r1",
                    "threadId": "t1",
                    "modelProfileId": "p",
                    "confirmId": "k1",
                    "decision": "approve",
                },
            )
            assert resp.status_code == 422
