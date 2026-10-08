"""AI 候选验收：非法 JSON/未知引用/截断/配置失效/取消迟到/不自动入库（B1 / A7）。

模型一律受控替身（``FakeProvider`` + ``FakeResolver``，参照 ``tests/test_question_bank.py``）：
不触网、不读写正式 ``.local-data``/``.env``，凭证哨兵值不得出现在冻结输入、任务快照或响应里。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Sequence

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import knowledge as knowledge_route
from app.contracts.knowledge import KnowledgeSuggestionRequest
from app.core.exceptions import AppError
from app.main import create_app
from app.providers.llm.base import (
    DEFAULT_TIMEOUT_SECONDS,
    FINISH_LENGTH,
    FINISH_STOP,
    LLMConfig,
    LLMResponse,
)
from app.repositories.assets.file_assets import FileAssetsRepository
from app.schemas.model_config import ModelProtocol
from app.services.assets.store import AssetStore
from app.services.knowledge.service import build_knowledge_service
from app.services.model_runtime import ChatModelHandle
from app.services.publication import PublicationCoordinator
from tests.conftest import make_settings

LOCAL_PROFILE = "chat-model-local"
#: 写入替身凭证的哨兵值：冻结输入/任务快照/响应里出现它即视为泄漏
FAKE_API_KEY = "sk-test-should-never-be-persisted"
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
_UNSET = object()

MATERIAL_ID = "material-1"
MATERIAL_TEXT = "有理数是能写成分数形式的数；数轴上的点与有理数一一对应。"
EVIDENCE_TEXT = "有理数加法法则：同号两数相加，取相同的符号，并把绝对值相加。"


class FakeEvidenceReader:
    """教材证据替身：区间切片 + 固定标题（不读真教材库）。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def read(self, *, document_revision_id: str, char_start: int, char_end: int):
        from app.services.knowledge.evidence import EvidenceText

        self.calls.append((document_revision_id, char_start, char_end))
        text = EVIDENCE_TEXT[char_start:char_end]
        import hashlib

        return EvidenceText(
            document_revision_id=document_revision_id,
            char_start=char_start,
            char_end=char_end,
            title="人教版数学七年级上册",
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            locator={"charStart": char_start, "charEnd": char_end},
        )


class FailingEvidenceReader:
    """教材读取失败替身：必须 503 TEXTBOOK_EVIDENCE_UNAVAILABLE，不得当"没有依据"。"""

    def read(self, *, document_revision_id: str, char_start: int, char_end: int):
        raise AppError(
            "教材修订不存在。",
            code="TEXTBOOK_EVIDENCE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )


def ensure_knowledge_router(app) -> None:
    paths = {getattr(route, "path", None) for route in app.router.routes}
    if "/api/v1/knowledge-points" not in paths:
        app.include_router(knowledge_route.router, prefix="/api/v1")
    routes = list(app.router.routes)
    catch = [
        route for route in routes if getattr(route, "name", "") == "feature_not_implemented"
    ]
    if catch:
        app.router.routes[:] = [route for route in routes if route not in catch] + catch


def evidence_ids_of(text: str) -> list[str]:
    return [
        line[len("[证据 ") : -1]
        for line in text.split("\n")
        if line.startswith("[证据 ") and line.endswith("]")
    ]


def suggestion_reply(evidence_ids: Sequence[str], **overrides: Any) -> str:
    candidate: dict[str, Any] = {
        "code": "K1",
        "name": "有理数",
        "description": "能写成分数形式的数",
        "parentCode": None,
        "aliases": ["有理数集"],
        "existingKnowledgePointId": None,
        "evidenceIds": list(evidence_ids),
        "confidence": 0.8,
    }
    candidate.update(overrides)
    return json.dumps({"candidates": [candidate]}, ensure_ascii=False)


class FakeProvider:
    """Provider 替身：``handler(request)`` 优先；默认回引输入里的证据 id。"""

    def __init__(
        self,
        replies: Sequence[Any] | None = None,
        handler: Callable[[Any], Any] | None = None,
    ) -> None:
        self.replies = list(replies or [])
        self.handler = handler
        self.calls: list[Any] = []
        self.configs: list[LLMConfig] = []

    async def complete(self, config: LLMConfig, request: Any, *, transport: Any = None) -> LLMResponse:
        self.calls.append(request)
        self.configs.append(config)
        value = (
            self.handler(request)
            if self.handler is not None
            else (self.replies.pop(0) if self.replies else None)
        )
        if value is None:
            return LLMResponse(
                text=suggestion_reply(evidence_ids_of(request.messages[-1].content)),
                finishReason=FINISH_STOP,
            )
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, LLMResponse):
            return value
        return LLMResponse(text=str(value), finishReason=FINISH_STOP)


class GatedProvider:
    """在 ``complete`` 里等待事件：用于"executor 拿到结果后取消"的确定性时序。"""

    def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
        self.started = started
        self.release = release
        self.calls = 0

    async def complete(self, config: LLMConfig, request: Any, *, transport: Any = None) -> LLMResponse:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return LLMResponse(
            text=suggestion_reply(evidence_ids_of(request.messages[-1].content)),
            finishReason=FINISH_STOP,
        )


def make_handle(
    profile_id: str = LOCAL_PROFILE,
    *,
    provider: Any | None = None,
    api_key: str | None = FAKE_API_KEY,
) -> ChatModelHandle:
    config = LLMConfig(
        protocol=ModelProtocol.openai_chat,
        baseUrl="http://127.0.0.1:11434/v1",
        modelId="qwen2.5:7b",
        apiKey=api_key,
        apiFormat="openai_chat",
        connectionId="conn-1",
        modelProfileId=profile_id,
    )
    return ChatModelHandle(
        profile_id=profile_id,
        model_id="qwen2.5:7b",
        provider=provider if provider is not None else FakeProvider(),
        config=config,
        max_output_tokens=2048,
    )


class FakeResolver:
    """``(profileId) -> ChatModelHandle`` 替身：可换映射、可抛错、记录调用。"""

    def __init__(
        self,
        profiles: dict[str, ChatModelHandle] | None = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.profiles = dict(profiles or {})
        self.error = error
        self.calls: list[str] = []

    def __call__(self, profile_id: str) -> ChatModelHandle:
        self.calls.append(profile_id)
        if self.error is not None:
            raise self.error
        handle = self.profiles.get(profile_id)
        if handle is None:
            raise AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
        return handle


class SuggestionHarness:
    """AI 候选测试台：四库临时目录 + 替身模型解析器 + 真实任务引擎。"""

    def __init__(
        self,
        tmp_path: Path,
        *,
        model_resolver: Any = _UNSET,
        job_engine: Any = _UNSET,
        evidence: Any = None,
        with_client: bool = True,
    ) -> None:
        self.settings = make_settings(tmp_path / "data")
        self.app = create_app(self.settings)
        self.catalog = self.app.state.knowledge
        self.teaching = self.app.state.teaching
        self.assets = AssetStore(self.settings.assets_root)
        self.file_assets = FileAssetsRepository(self.teaching)
        self.coordinator = PublicationCoordinator()
        self.model_resolver = None if model_resolver is _UNSET else model_resolver
        self.job_engine = (
            self.app.state.job_engine if job_engine is _UNSET else job_engine
        )
        self.service = build_knowledge_service(
            self.catalog,
            asset_store=self.assets,
            file_assets=self.file_assets,
            evidence=evidence,
            coordinator=self.coordinator,
            model_resolver=self.model_resolver,
            job_engine=self.job_engine,
        )
        self.app.state.knowledge_service = self.service
        ensure_knowledge_router(self.app)
        self.client = None
        if with_client:
            self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
            self.client.__enter__()

    def close(self) -> None:
        if self.client is not None:
            self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 便捷方法

    def payload(self, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": "math",
            "materials": [{"id": MATERIAL_ID, "text": MATERIAL_TEXT}],
        }
        body.update(overrides)
        return body

    def create_point(self, code: str, **overrides: Any) -> dict:
        assert self.client is not None
        body = {"subjectId": "math", "code": code, "name": f"知识点 {code}"}
        body.update(overrides)
        response = self.client.post("/api/v1/knowledge-points", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def start_job(self, body: dict) -> tuple[Any, dict]:
        assert self.client is not None
        response = self.client.post("/api/v1/knowledge-suggestion-jobs", json=body)
        return response, response.json() if response.content else {}

    def wait_job(self, job_id: str, *, timeout: float = 8.0) -> dict:
        assert self.client is not None
        deadline = time.monotonic() + timeout
        view = self.job_view(job_id)
        while view["state"] not in TERMINAL_STATES and time.monotonic() < deadline:
            time.sleep(0.02)
            view = self.job_view(job_id)
        assert view["state"] in TERMINAL_STATES, view
        return view

    def job_view(self, job_id: str) -> dict:
        assert self.client is not None
        response = self.client.get(
            f"/api/v1/workflow-jobs/{job_id}", params={"domain": "knowledge"}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def run_job(self, body: dict) -> dict:
        response, view = self.start_job(body)
        assert response.status_code == 202, response.text
        return self.wait_job(view["jobId"])

    def count(self, db_path: Path, table: str) -> int:
        import sqlite3

        connection = sqlite3.connect(db_path)
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            connection.close()

    def knowledge_count(self, table: str) -> int:
        return self.count(self.catalog.db_path, table)

    def teaching_count(self, table: str) -> int:
        return self.count(self.teaching.db_path, table)

    def import_view(self, import_id: str) -> dict:
        assert self.client is not None
        response = self.client.get(f"/api/v1/knowledge-imports/{import_id}")
        assert response.status_code == 200, response.text
        return response.json()


def make_harness(
    tmp_path: Path,
    *,
    provider: Any | None = None,
    handler: Callable[[Any], Any] | None = None,
    resolver_error: BaseException | None = None,
    model_resolver: Any = _UNSET,
    job_engine: Any = _UNSET,
    evidence: Any = None,
    with_client: bool = True,
) -> SuggestionHarness:
    """按测试意图装配：替身 Provider / 抛错的解析器 / 未装配的解析器。"""
    if model_resolver is _UNSET:
        if resolver_error is not None:
            model_resolver = FakeResolver(error=resolver_error)
        else:
            model_resolver = FakeResolver(
                {LOCAL_PROFILE: make_handle(provider=provider or FakeProvider(handler=handler))}
            )
    return SuggestionHarness(
        tmp_path,
        model_resolver=model_resolver,
        job_engine=job_engine,
        evidence=evidence,
        with_client=with_client,
    )


@pytest.fixture()
def harness(tmp_path: Path):
    instance = make_harness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- 成功路径


def test_success_creates_reviewing_batch_and_not_formal_table(tmp_path: Path) -> None:
    harness = make_harness(
        tmp_path,
        handler=lambda request: json.dumps(
            {
                "candidates": [
                    {
                        "code": "K1",
                        "name": "有理数",
                        "description": "能写成分数形式的数",
                        "aliases": ["有理数集"],
                        "evidenceIds": [MATERIAL_ID],
                        "confidence": 0.9,
                    },
                    {
                        "code": "K2",
                        "name": "已有说法的候选",
                        "existingKnowledgePointId": existing["id"],
                        "evidenceIds": [MATERIAL_ID],
                    },
                ]
            },
            ensure_ascii=False,
        ),
    )
    try:
        existing = harness.create_point("E1", name="既有知识点")
        response, accepted = harness.start_job(harness.payload())
        assert response.status_code == 202, response.text
        assert accepted["jobId"] and accepted["state"] == "queued"
        assert accepted["domain"] == "knowledge" and accepted["kind"] == "suggestion"
        assert accepted["attempt"] == 0
        assert accepted["result"] is None and accepted["error"] is None

        job = harness.wait_job(accepted["jobId"])
        assert job["state"] == "succeeded", job
        assert job["result"]["candidateCount"] == 2
        import_id = job["result"]["importId"]

        batch = harness.import_view(import_id)
        assert batch["source"] == "ai"
        assert batch["state"] == "reviewing"
        assert batch["revision"] == 0
        assert [row["code"] for row in batch["rows"]] == ["K1", "K2"]
        assert batch["rows"][0]["issues"][0]["code"] == "KNOWLEDGE_SUGGESTION_REVIEW"
        assert "置信度 0.90" in batch["rows"][0]["issues"][0]["message"]
        assert (
            "KNOWLEDGE_SUGGESTION_EXISTING_REFERENCE"
            in {issue["code"] for issue in batch["rows"][1]["issues"]}
        )
        assert batch["warnings"] and "AI 候选批次" in batch["warnings"][0]

        # 候选绝不写正式表；原始模型输出登记为教学库受管资产
        assert harness.knowledge_count("knowledge_points") == 1  # 只有 E1
        assert harness.teaching_count("file_assets") == 1
        asset = harness.file_assets.get(batch["fileAsset"]["assetId"])
        assert asset is not None and asset.kind == "attachment"

        # 冻结输入/模型快照不含凭证
        record = harness.job_engine.store("knowledge").get(accepted["jobId"])
        blob = json.dumps(
            {"frozen": record.frozen_input, "snapshot": record.model_snapshot},
            ensure_ascii=False,
        )
        assert FAKE_API_KEY not in blob
        assert record.model_snapshot["profileId"] == LOCAL_PROFILE
        assert record.model_snapshot["fingerprint"].startswith("sha256:")
        assert record.frozen_input["evidenceIds"] == [MATERIAL_ID]
        assert record.frozen_input["allowedKnowledgePointIds"] == [existing["id"]]

        # 同一确认接口可入库
        body = {
            "expectedRevision": 0,
            "submissionId": "sub-ai",
            "actions": [
                {"rowNo": 1, "decision": "create"},
                {"rowNo": 2, "decision": "create"},
            ],
        }
        confirmed = harness.client.post(
            f"/api/v1/knowledge-imports/{import_id}/confirm", json=body
        )
        assert confirmed.status_code == 200, confirmed.text
        assert len(confirmed.json()["created"]) == 2
        assert harness.knowledge_count("knowledge_points") == 3
        assert harness.import_view(import_id)["state"] == "confirmed"
    finally:
        harness.close()


# --------------------------------------------------------------------------- 失败路径


def test_invalid_json_fails_job_without_batch(tmp_path: Path) -> None:
    harness = make_harness(tmp_path, provider=FakeProvider(replies=["不是 JSON"]))
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "KNOWLEDGE_SUGGESTION_INVALID_JSON"
        assert harness.knowledge_count("knowledge_imports") == 0
        assert harness.teaching_count("file_assets") == 0
    finally:
        harness.close()


@pytest.mark.parametrize(
    "overrides",
    [
        {"existingKnowledgePointId": "not-an-allowed-id"},
        {"evidenceIds": ["material-outside-input"]},
    ],
)
def test_unknown_reference_fails_job(tmp_path: Path, overrides: dict) -> None:
    harness = make_harness(
        tmp_path, handler=lambda request: suggestion_reply([MATERIAL_ID], **overrides)
    )
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE"
        assert harness.knowledge_count("knowledge_imports") == 0
    finally:
        harness.close()


def test_truncated_output_fails_job(tmp_path: Path) -> None:
    truncated = LLMResponse(text='{"candidates":[{"code":"K1"', finishReason=FINISH_LENGTH)
    harness = make_harness(tmp_path, provider=FakeProvider(replies=[truncated]))
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "KNOWLEDGE_SUGGESTION_TRUNCATED"
        assert harness.knowledge_count("knowledge_imports") == 0
    finally:
        harness.close()


def test_plain_suggestion_job_keeps_default_provider_timeout(tmp_path: Path) -> None:
    """放宽只覆盖教材提取；手输材料候选任务保持默认非流式等待。"""
    provider = FakeProvider()
    harness = make_harness(tmp_path, provider=provider)
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "succeeded", job
        assert provider.configs, "候选任务必须真实调用模型"
        assert provider.configs[-1].timeoutSeconds == DEFAULT_TIMEOUT_SECONDS
    finally:
        harness.close()


def test_model_profile_missing_fails_job(tmp_path: Path) -> None:
    harness = make_harness(
        tmp_path,
        resolver_error=AppError(
            "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
        ),
    )
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "MODEL_PROFILE_NOT_FOUND"
        assert harness.knowledge_count("knowledge_imports") == 0
        assert harness.knowledge_count("knowledge_points") == 0
    finally:
        harness.close()


def test_model_not_configured_fails_job(tmp_path: Path) -> None:
    harness = make_harness(
        tmp_path,
        resolver_error=AppError(
            "该模型连接当前不可调用。", code="MODEL_NOT_CONFIGURED", status_code=400
        ),
    )
    try:
        job = harness.run_job(harness.payload())
        assert job["state"] == "failed"
        assert job["error"]["code"] == "MODEL_NOT_CONFIGURED"
    finally:
        harness.close()


# --------------------------------------------------------------------------- 闸门与取消


def test_no_evidence_is_422_and_no_job(harness: SuggestionHarness) -> None:
    response = harness.client.post(
        "/api/v1/knowledge-suggestion-jobs",
        json={"modelProfileId": LOCAL_PROFILE, "subjectId": "math"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "KNOWLEDGE_SUGGESTION_NO_EVIDENCE"
    assert harness.knowledge_count("knowledge_jobs") == 0


def test_textbook_evidence_without_reader_is_503_and_no_job(
    harness: SuggestionHarness,
) -> None:
    body = harness.payload(
        materials=[],
        textbookEvidence=[
            {"documentRevisionId": "rev-1", "charStart": 0, "charEnd": 5}
        ],
    )
    response = harness.client.post("/api/v1/knowledge-suggestion-jobs", json=body)
    assert response.status_code == 503
    assert response.json()["code"] == "TEXTBOOK_EVIDENCE_UNAVAILABLE"
    assert response.json()["retryable"] is True
    assert harness.knowledge_count("knowledge_jobs") == 0


def test_new_subject_is_registered_on_demand(tmp_path: Path) -> None:
    """学科尚未建档也能发起候选：学科按需 INSERT OR IGNORE（与人工建立一致）。"""
    harness = make_harness(tmp_path)
    try:
        job = harness.run_job(harness.payload(subjectId="brand-new-subject"))
        assert job["state"] == "succeeded", job
        assert harness.knowledge_count("subjects") == 1
        batch = harness.import_view(job["result"]["importId"])
        assert batch["subjectId"] == "brand-new-subject"
        assert batch["rows"][0]["targetKnowledgePointId"] is None
    finally:
        harness.close()


def test_missing_model_resolver_is_503(tmp_path: Path) -> None:
    instance = make_harness(tmp_path, model_resolver=None)
    try:
        response = instance.client.post(
            "/api/v1/knowledge-suggestion-jobs", json=instance.payload()
        )
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
        assert instance.knowledge_count("knowledge_jobs") == 0
    finally:
        instance.close()


def test_missing_job_engine_is_503(tmp_path: Path) -> None:
    instance = make_harness(tmp_path, job_engine=None)
    try:
        response = instance.client.post(
            "/api/v1/knowledge-suggestion-jobs", json=instance.payload()
        )
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    finally:
        instance.close()


def test_textbook_evidence_is_frozen_with_stable_ids(tmp_path: Path) -> None:
    reader = FakeEvidenceReader()
    harness = make_harness(tmp_path, evidence=reader)
    try:
        body = harness.payload(
            materials=[],
            textbookEvidence=[{"documentRevisionId": "rev-1", "charStart": 0, "charEnd": 6}],
        )
        job = harness.run_job(body)
        assert job["state"] == "succeeded", job
        record = harness.job_engine.store("knowledge").get(job["jobId"])
        evidence_id = "textbook:rev-1:0:6"
        assert record.frozen_input["evidenceIds"] == [evidence_id]
        frozen = record.frozen_input["textbookEvidence"][0]
        assert frozen["title"] == "人教版数学七年级上册"
        assert frozen["text"] == EVIDENCE_TEXT[0:6]
        assert frozen["sha256"]
        # 默认替身回引输入里的证据 id → 候选行带上同一条教材证据提示
        batch = harness.import_view(job["result"]["importId"])
        assert batch["rows"][0]["code"] == "K1"
        assert evidence_id in batch["rows"][0]["issues"][0]["message"]
    finally:
        harness.close()


def test_textbook_evidence_unavailable_is_503_and_no_job(tmp_path: Path) -> None:
    harness = make_harness(tmp_path, evidence=FailingEvidenceReader())
    try:
        body = harness.payload(
            materials=[],
            textbookEvidence=[{"documentRevisionId": "rev-1", "charStart": 0, "charEnd": 6}],
        )
        response = harness.client.post("/api/v1/knowledge-suggestion-jobs", json=body)
        assert response.status_code == 503
        assert response.json()["code"] == "TEXTBOOK_EVIDENCE_UNAVAILABLE"
        assert harness.knowledge_count("knowledge_jobs") == 0
    finally:
        harness.close()


def test_cancel_after_executor_returns_does_not_publish(tmp_path: Path) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        provider = GatedProvider(started, release)
        instance = make_harness(tmp_path, provider=provider, with_client=False)
        try:
            view = await instance.service.create_suggestion_job(
                KnowledgeSuggestionRequest.model_validate(instance.payload())
            )
            assert view.state == "queued"
            await asyncio.wait_for(started.wait(), timeout=5)
            # executor 仍在等模型：先请求取消，再放行（取消迟到）
            instance.job_engine.store("knowledge").request_cancel(view.job_id)
            release.set()
            deadline = time.monotonic() + 5
            record = instance.job_engine.store("knowledge").get(view.job_id)
            while record.state not in TERMINAL_STATES and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
                record = instance.job_engine.store("knowledge").get(view.job_id)
            assert record.state == "cancelled", record.state
            assert record.result is None
            assert instance.knowledge_count("knowledge_imports") == 0
            assert instance.teaching_count("file_assets") == 0
        finally:
            await instance.job_engine.shutdown()
            instance.close()

    asyncio.run(scenario())


def test_extraction_instruction_bounds_candidates_and_raises_output_budget() -> None:
    """教材提取必须有界输出（2026-10-08 真机：整册候选超出 2048 触发截断拒绝）。"""
    from app.services.knowledge import suggestions

    plain = suggestions.system_instruction({"allowedKnowledgePointIds": []})
    assert suggestions.EXTRACTION_INSTRUCTION_SUFFIX.strip() not in plain

    extraction = suggestions.system_instruction(
        {"allowedKnowledgePointIds": [], "extraction": {"documentRevisionId": "rev-1"}}
    )
    assert f"最多提炼 {suggestions.EXTRACTION_MAX_CANDIDATES} 条" in extraction
    assert suggestions.EXTRACTION_MAX_OUTPUT_TOKENS > suggestions.MAX_OUTPUT_TOKENS
    assert extraction.index(suggestions.EXTRACTION_INSTRUCTION_SUFFIX.strip()) > 0
