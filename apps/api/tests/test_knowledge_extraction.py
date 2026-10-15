"""知识点提取验收（任务③）：预览清单 / 任务受理 / 候选只进批次 / 确认后自动建依据。

书册用**真实教材目录临时库**（小规模替身正文 + 分块 + 当前索引代），模型用
``FakeProvider`` + ``FakeResolver``（与 ``test_knowledge_suggestions.py`` 同一套替身，
不触网）：验证"与生产同一条调用路径"下的受理校验、证据冻结、候选批次与确认后的
教材依据自动登记。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Sequence

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import knowledge as knowledge_route
from app.main import create_app
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.assets.store import AssetStore
from app.services.knowledge.service import build_knowledge_service
from app.services.publication import PublicationCoordinator
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from tests.conftest import make_settings
from app.providers.llm.base import DEFAULT_TIMEOUT_SECONDS

LOCAL_PROFILE = "chat-model-local"
SUBJECT = "math"
DOCUMENT_TITLE = "人教版数学七年级上册"
#: 替身书册正文（两段正文，够分块）
DOC_TEXT = (
    "第一章 有理数。有理数加法法则：同号两数相加，取相同的符号，并把绝对值相加。\n"
    "有理数减法法则：减去一个数，等于加上这个数的相反数。"
)
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


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


def suggestion_reply(evidence_ids: Sequence[str]) -> dict[str, Any]:
    """固定替身回复：一个新建候选，回引输入里的全部证据 id。"""
    return {
        "candidates": [
            {
                "code": "K1",
                "name": "有理数加法",
                "description": "同号相加取同号并把绝对值相加",
                "parentCode": None,
                "aliases": [],
                "existingKnowledgePointId": None,
                "evidenceIds": list(evidence_ids),
                "confidence": 0.9,
            }
        ]
    }


def evidence_ids_of(text: str) -> list[str]:
    return [
        line[len("[证据 ") : -1]
        for line in text.split("\n")
        if line.startswith("[证据 ") and line.endswith("]")
    ]


class FakeLangChainModel:
    """LangChain 形状替身：``with_structured_output`` 与 runner 同一路径（不触网）。"""

    def __init__(self, handler: Callable[[Any], Any] | None = None) -> None:
        self.handler = handler
        self.calls: list[list[Any]] = []

    def with_structured_output(self, schema, *, include_raw=False, **kwargs):
        model = self

        class _Runnable:
            async def ainvoke(self, messages, config=None):
                model.calls.append(list(messages))
                if model.handler is not None:
                    value = model.handler(messages[-1].content)
                    payload = value if isinstance(value, dict) else None
                else:
                    payload = None
                if payload is None:
                    # 默认回引输入里的证据 id（与归档 FakeProvider 默认行为一致）
                    payload = {
                        "candidates": [
                            {
                                "code": "K1",
                                "name": "有理数加法",
                                "evidenceIds": evidence_ids_of(str(messages[-1].content)),
                            }
                        ]
                    }
                return {
                    "raw": _FakeAIMessage(content=json.dumps(payload, ensure_ascii=False)),
                    "parsed": schema.model_validate(payload),
                    "parsing_error": None,
                }

        return _Runnable()


class _FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def make_handle(profile_id: str = LOCAL_PROFILE, *, model: Any) -> Any:
    """R3：替身句柄（AgentModelHandle 同形状）。"""
    from app.services.agent.model import AgentModelHandle

    return AgentModelHandle(
        profile_id=profile_id,
        model_id="qwen2.5:7b",
        chat_model=model,
        max_output_tokens=2048,
    )


class FakeResolver:
    """``(profileId) -> AgentModelHandle`` 替身。"""

    def __init__(self, handle: Any) -> None:
        self.handle = handle
        self.calls: list[str] = []

    def __call__(self, profile_id: str) -> Any:
        self.calls.append(profile_id)
        if profile_id not in (LOCAL_PROFILE,):
            raise AssertionError(f"替身只认 {LOCAL_PROFILE}，收到 {profile_id}")
        return self.handle


def _chunk_input(ordinal: int, char_start: int, char_end: int):
    from app.repositories.textbook_catalog.records import ChunkInput

    text = DOC_TEXT[char_start:char_end]
    return ChunkInput(
        ordinal=ordinal,
        char_start=char_start,
        char_end=char_end,
        region="body",
        chapter_path=["第一章 有理数"],
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


class ExtractionHarness:
    """提取测试台：真实教材目录临时库 + 真实知识点服务（生产装配路径）+ 替身模型。"""

    def __init__(self, tmp_path: Path, *, model: Any | None = None) -> None:
        self.settings = make_settings(tmp_path / "data")
        self.app = create_app(self.settings)
        self.catalog = self.app.state.catalog
        self.knowledge = self.app.state.knowledge
        # R3 适配：教学库（R5-BE 批次）不在 main 装配范围，本台自建临时 TeachingCatalog
        from app.repositories.teaching.catalog import TeachingCatalog

        self.teaching = TeachingCatalog(tmp_path / "teaching" / "teaching.sqlite3")
        self.teaching.migrate()
        self.model = model if model is not None else FakeLangChainModel()
        handle = make_handle(model=self.model)
        self.model_resolver = FakeResolver(handle)
        # 服务与生产 main.py 同形参（含 reference_checker / scope_reader 真实实现）
        self.service = build_knowledge_service(
            self.knowledge,
            asset_store=AssetStore(self.settings.assets_root),
            file_assets=FileAssetsRepository(self.teaching),
            evidence=self.app.state.textbook_evidence,
            coordinator=PublicationCoordinator(),
            model_resolver=self.model_resolver,
            job_engine=self.app.state.job_engine,
            reference_checker=self.app.state.knowledge_service.reference_checker
            if self.app.state.knowledge_service is not None
            else None,
            scope_reader=self.app.state.knowledge_service.scope_reader
            if self.app.state.knowledge_service is not None
            else None,
        )
        self.app.state.knowledge_service = self.service
        ensure_knowledge_router(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()
        self._blob_store = BlobStore(self.settings.textbooks_root)
        # 与任教设置一致的逻辑库（g7/math/rj）：书册挂进它才能进入任教范围
        library = self.catalog.create_library(
            kind="base",
            owner_id="local-user",
            display_name="任教教材库",
            grade_id="g7",
            subject_id=SUBJECT,
            edition_id="rj",
        )
        self._base_library_id = library.library_id

    def _library_id(self) -> str:
        return self._base_library_id

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 教材替身书册

    def add_document(
        self,
        *,
        title: str = DOCUMENT_TITLE,
        grade_ids: tuple[str, ...] = ("g7",),
        with_revision: bool = True,
        with_chunks: bool = True,
        publish: bool = True,
        text: str | None = None,
    ) -> dict[str, Any]:
        """建立替身书册：文档 + 规范化文本修订 + 分块集 + 当前索引代（可选逐项省略）。

        ``text`` 缺省用台账正文 ``DOC_TEXT``；需要不同目录/标题形状的用例可显式传入
        （修订哈希与块长都按传入文本计算）。
        """
        book_text = DOC_TEXT if text is None else text
        document = self.catalog.create_document(
            owner_id="local-user",
            title=title,
            stage_id="stage-1",
            grade_ids=grade_ids,
            subject_id=SUBJECT,
            edition_id="rj",
            library_ids=[self._library_id()],
        )
        result: dict[str, Any] = {"document": document}
        if not with_revision:
            return result
        blob_id = self._blob_store.write_staged_text(book_text)
        self._blob_store.seal(area="normalized", blob_id=blob_id)
        revision = self.catalog.create_document_revision(
            document.document_id,
            original_file_sha256=hashlib.sha256(book_text.encode("utf-8")).hexdigest(),
            normalized_text_sha256=sha256_text(book_text),
            parser_version="test-parser-1",
            original_blob_id=blob_id,
            normalized_blob_id=blob_id,
            source_map_blob_id=blob_id,
            char_count=len(book_text),
        )
        result["revision"] = revision
        if with_chunks and len(book_text) > 37:
            chunk_set = self.catalog.create_chunk_set(
                revision.revision_id,
                policy_fingerprint="policy-test-1",
                manifest_sha256="m" * 64,
                chunks=[_chunk_input(0, 0, 36), _chunk_input(1, 37, len(book_text))],
            )
            result["chunk_set"] = chunk_set
        if publish:
            self.catalog.publish_document_revision(
                document.document_id, revision_id=revision.revision_id,
                metadata_revision_id=document.current_metadata_revision_id,
            )
        return result

    def publish_index(self, documents: list[dict[str, Any]]) -> str:
        """发布当前索引代并把替身书册的修订标为 ready。"""
        profile = self.catalog.create_embedding_profile(
            fingerprint=f"fp-{uuid_hex()}",
            adapter="ollama",
            native_base_url="http://127.0.0.1:11434",
            model_name="bge-m3",
            model_manifest_digest="digest-1",
            dimensions=8,
            distance="cosine",
            query_prefix="",
            document_prefix="",
            normalization="none",
        )
        generation = self.catalog.create_generation(
            profile_id=profile.profile_id,
            collection_name=f"zqky_test_{uuid_hex()}",
            chunk_policy_json={"target": 800, "overlap": 120},
            state="building",
        )
        for item in documents:
            self.catalog.upsert_generation_revision(
                generation.generation_id,
                item["revision"].revision_id,
                item["chunk_set"].chunk_set_id,
                state="ready",
                expected_chunk_count=item["chunk_set"].chunk_count,
                manifest_sha256="m" * 64,
            )
        self.catalog.publish_generation(generation.generation_id)
        self.catalog.set_active_generation(generation.generation_id)
        return generation.generation_id

    # -------------------------------------------------------------- 便捷方法

    def payload(self, **overrides: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "submissionId": "sub-extract-1",
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": SUBJECT,
        }
        body.update(overrides)
        return body

    def preview(self, subject_id: str = SUBJECT) -> dict:
        response = self.client.get(
            "/api/v1/knowledge-extraction/preview", params={"subjectId": subject_id}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def start_jobs(self, body: dict):
        response = self.client.post("/api/v1/knowledge-extraction-jobs", json=body)
        return response, response.json() if response.content else {}

    def wait_job(self, job_id: str, *, timeout: float = 8.0) -> dict:
        deadline = time.monotonic() + timeout
        view = self.job_view(job_id)
        while view["state"] not in TERMINAL_STATES and time.monotonic() < deadline:
            time.sleep(0.02)
            view = self.job_view(job_id)
        assert view["state"] in TERMINAL_STATES, view
        return view

    def job_view(self, job_id: str) -> dict:
        response = self.client.get(
            f"/api/v1/workflow-jobs/{job_id}", params={"domain": "knowledge"}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def run_all(self, body: dict) -> list[dict]:
        response, accepted = self.start_jobs(body)
        assert response.status_code == 202, response.text
        return [self.wait_job(item["jobId"]) for item in accepted]

    def import_view(self, import_id: str) -> dict:
        response = self.client.get(f"/api/v1/knowledge-imports/{import_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def confirm(self, import_id: str, *, revision: int = 0) -> dict:
        rows = self.import_view(import_id)["rows"]
        actions = [
            {"rowNo": row["rowNo"], "decision": row["decision"] or "create"}
            for row in rows
        ]
        response = self.client.post(
            f"/api/v1/knowledge-imports/{import_id}/confirm",
            json={"expectedRevision": revision, "submissionId": f"confirm-{import_id}", "actions": actions},
        )
        return response

    def link_count(self) -> int:
        import sqlite3

        connection = sqlite3.connect(self.knowledge.db_path)
        try:
            return int(
                connection.execute("SELECT COUNT(*) FROM textbook_knowledge_links").fetchone()[0]
            )
        finally:
            connection.close()


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


@pytest.fixture()
def harness(tmp_path: Path):
    instance = ExtractionHarness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- 预览


def test_preview_lists_all_subject_documents_with_readiness(harness: ExtractionHarness) -> None:
    ready_doc = harness.add_document()
    harness.publish_index([ready_doc])
    # 未就绪书册：有修订、有分块，但不在当前索引代
    harness.add_document(title="另一本未入库书")
    preview = harness.preview()
    assert preview["subjectId"] == SUBJECT
    assert preview["totalDocuments"] == 2
    assert preview["readyDocuments"] == 1
    assert preview["totalChunks"] == 2
    assert preview["approxChars"] == len(DOC_TEXT)
    by_title = {item["title"]: item for item in preview["documents"]}
    ready = by_title[DOCUMENT_TITLE]
    assert ready["indexReady"] is True
    assert ready["reason"] is None
    assert ready["gradeIds"] == ["g7"]
    assert ready["revisionId"] == ready_doc["revision"].revision_id
    assert ready["chunkCount"] == 2
    not_ready = by_title["另一本未入库书"]
    assert not_ready["indexReady"] is False
    assert not_ready["reason"]


def test_preview_without_revision_marks_reason(harness: ExtractionHarness) -> None:
    harness.add_document(with_revision=False, with_chunks=False, publish=False)
    preview = harness.preview()
    assert preview["totalDocuments"] == 1
    entry = preview["documents"][0]
    assert entry["indexReady"] is False
    assert entry["revisionId"] is None
    assert "修订" in entry["reason"]


def test_preview_other_subject_is_empty(harness: ExtractionHarness) -> None:
    harness.add_document()
    preview = harness.preview(subject_id="physics")
    assert preview["totalDocuments"] == 0


# --------------------------------------------------------------------------- 受理


def test_accept_requires_all_documents_ready(harness: ExtractionHarness) -> None:
    ready_doc = harness.add_document()
    harness.publish_index([ready_doc])
    unready = harness.add_document(title="未就绪的书")
    response, _ = harness.start_jobs(
        harness.payload(documentIds=[ready_doc["document"].document_id, unready["document"].document_id])
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "KNOWLEDGE_EXTRACTION_NOT_READY"
    assert body["details"]["documents"][0]["documentId"] == unready["document"].document_id
    # 未受理任何任务
    assert harness.client.get("/api/v1/knowledge-imports").json()["total"] == 0


def test_accept_unknown_document_is_conflict(harness: ExtractionHarness) -> None:
    response, _ = harness.start_jobs(harness.payload(documentIds=["no-such-doc"]))
    assert response.status_code == 409
    assert response.json()["code"] == "KNOWLEDGE_EXTRACTION_NOT_READY"


def test_accept_defaults_to_all_ready_documents(harness: ExtractionHarness) -> None:
    first = harness.add_document()
    second = harness.add_document(title="第二本就绪书", grade_ids=("g8",))
    harness.publish_index([first, second])
    unready = harness.add_document(title="第三本未就绪")
    jobs = harness.run_all(harness.payload())
    # 缺省只受理就绪书册：两本 → 两个任务；未就绪不静默跳过也不受理
    assert len(jobs) == 2
    assert all(job["state"] == "succeeded" for job in jobs)


# --------------------------------------------------------------------------- 候选只进批次


def test_extraction_candidates_only_enter_reviewing_batch(harness: ExtractionHarness) -> None:
    doc = harness.add_document()
    harness.publish_index([doc])
    jobs = harness.run_all(harness.payload())
    assert len(jobs) == 1
    job = jobs[0]
    assert job["kind"] == "suggestion"
    assert job["result"]["candidateCount"] == 1
    batch = harness.import_view(job["result"]["importId"])
    assert batch["source"] == "ai"
    assert batch["state"] == "reviewing"
    # 候选绝不直接写正式表
    import sqlite3

    connection = sqlite3.connect(harness.knowledge.db_path)
    try:
        assert int(connection.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]) == 0
    finally:
        connection.close()
    # 冻结输入里的证据：正文 chunk 区间（documentRevisionId + char 坐标）
    record = harness.app.state.job_engine.store("knowledge").get(job["jobId"])
    frozen = record.frozen_input
    assert frozen["extraction"]["documentId"] == doc["document"].document_id
    assert frozen["extraction"]["gradeIds"] == ["g7"]
    assert all(item["documentRevisionId"] == doc["revision"].revision_id for item in frozen["textbookEvidence"])
    assert all(item["charEnd"] > item["charStart"] for item in frozen["textbookEvidence"])


def test_extraction_job_widens_provider_call_timeout(harness: ExtractionHarness) -> None:
    """整册提取按调用放宽非流式等待：默认 30 秒对 6 万码点证据不够（真机 UPSTREAM_TIMEOUT）。"""
    from app.services.knowledge import suggestions as suggestion_rules

    doc = harness.add_document()
    harness.publish_index([doc])
    jobs = harness.run_all(harness.payload())
    assert jobs[0]["state"] == "succeeded", jobs[0]
    assert harness.model.calls, "提取任务必须真实调用模型"
    # R3：放宽落在 runner 的 timeout_s（提取任务专属）；模型替身不感知时间，这里只断言
    # 常量口径保持"放宽"（超时降级路径由 runner 回归与 run_job 行为覆盖）。
    assert suggestion_rules.EXTRACTION_TIMEOUT_SECONDS > DEFAULT_TIMEOUT_SECONDS


def test_extraction_no_ready_documents_is_422(harness: ExtractionHarness) -> None:
    # 有书册但索引代未就绪 → 缺省（全部就绪书册）为空集 → 422
    harness.add_document()
    response, _ = harness.start_jobs(harness.payload())
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


# --------------------------------------------------------------------------- 确认后自动建依据


def test_confirm_creates_textbook_links_from_extraction_evidence(
    harness: ExtractionHarness,
) -> None:
    doc = harness.add_document()
    harness.publish_index([doc])
    jobs = harness.run_all(harness.payload())
    batch = harness.import_view(jobs[0]["result"]["importId"])
    # AI 候选行冻结了提取证据（确认后建依据的来源）
    row = batch["rows"][0]
    raw_cells = row  # 行视图不回显 raw_cells；证据在确认时由服务端从行记录恢复
    confirmed = harness.confirm(batch["importId"])
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert len(result["created"]) == 1
    point_id = result["created"][0]["knowledgePointId"]
    # 自动建教材依据：正文有 2 个 body chunk → 2 条依据，source=ai_confirmed，
    # 坐标来自正文 chunk，标题快照 = 教材标题
    assert harness.link_count() == 2
    links = harness.client.get(f"/api/v1/knowledge-points/{point_id}/textbook-links").json()
    assert len(links["items"]) == 2
    for link in links["items"]:
        assert link["source"] == "ai_confirmed"
        assert link["documentRevisionId"] == doc["revision"].revision_id
        assert link["titleSnapshot"] == DOCUMENT_TITLE
        assert link["charEnd"] > link["charStart"]
    # scope=taught 现在能看到该知识点（真实 scope reader + 该书册在任教范围）
    from app.schemas.textbook import TextbookSelection

    selection = TextbookSelection(
        gradeId="g7", subjectId=SUBJECT, editionId="rj",
        documentIds=[doc["document"].document_id],
    )
    harness.catalog.set_teaching_settings(
        selection_json=selection.model_dump(by_alias=True), expected_revision=0
    )
    listing = harness.client.get(
        "/api/v1/knowledge-points", params={"scope": "taught", "subjectId": SUBJECT}
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    item = listing.json()["items"][0]
    assert item["id"] == point_id
    assert item["gradeIds"] == ["g7"]


def test_confirm_update_rows_do_not_create_links(harness: ExtractionHarness) -> None:
    """update 行不自动建依据（只对新建知识点补教材依据）。"""
    doc = harness.add_document()
    harness.publish_index([doc])
    # 预置同名编码的既有知识点：替身候选 code=K1 → update 目标
    existing = harness.client.post(
        "/api/v1/knowledge-points",
        json={"subjectId": SUBJECT, "code": "K1", "name": "既有知识点"},
    )
    assert existing.status_code == 201, existing.text
    jobs = harness.run_all(harness.payload())
    batch = harness.import_view(jobs[0]["result"]["importId"])
    assert batch["rows"][0]["decision"] == "update"
    confirmed = harness.confirm(batch["importId"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["created"] == []
    assert len(confirmed.json()["updated"]) == 1
    assert harness.link_count() == 0


def test_job_handler_reply_is_frozen_input_safe(harness: ExtractionHarness) -> None:
    """冻结输入不含凭证（与既有候选同一安全边界）。"""
    doc = harness.add_document()
    harness.publish_index([doc])
    jobs = harness.run_all(harness.payload())
    record = harness.app.state.job_engine.store("knowledge").get(jobs[0]["jobId"])
    blob = json.dumps(record.frozen_input, ensure_ascii=False)
    assert "sk-test-should-never-be-persisted" not in blob
    assert record.model_snapshot["profileId"] == LOCAL_PROFILE
