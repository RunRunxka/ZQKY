"""教材 HTTP 接口：错误信封、真实状态、multipart 上传、任务与索引端点。

全部用 ``TestClient`` + 注入替身（内存向量库、假 Embedding、MockTransport Ollama），
只写 pytest ``tmp_path``；服务未装配时必须是 503 而不是空列表。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.embeddings.fingerprint import embedding_fingerprint
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider
from app.repositories.vector_store import InMemoryVectorStore
from app.services.document_parsing import chunk_document, parse_document
from app.services.textbook_ingest import IngestService
from app.services.textbook_index import IndexService
from tests.test_textbook_ingest import FakeEmbeddings, METADATA, sample_text

ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173"})
LIBRARY_BODY = {
    "kind": "base",
    "displayName": "基础库·数学",
    "gradeId": "senior-1",
    "subjectId": "math",
    "editionId": "renjiao-a",
}


def _parser(*, path, file_name, parser_version, allow_empty_text=False):
    return parse_document(
        path=path,
        file_name=file_name,
        parser_version=parser_version,
        allow_empty_text=allow_empty_text,
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=tmp_path / "data",
    )


class ApiHarness:
    def __init__(self, tmp_path: Path, *, embeddings=None, vectors=None) -> None:
        self.settings = _settings(tmp_path)
        self.app = create_app(self.settings)
        self.catalog = self.app.state.catalog
        self.vectors = vectors if vectors is not None else InMemoryVectorStore()
        self.embeddings = embeddings if embeddings is not None else FakeEmbeddings()
        self.ingest = IngestService(
            self.catalog,
            _parser,
            chunk_document,
            self.embeddings,
            self.vectors,
            self.settings,
            batch_size=8,
            sleep=lambda _seconds: None,
        )
        self.index = IndexService(
            self.catalog, self.embeddings, self.vectors, self.settings, sleep=lambda _seconds: None
        )
        self.app.state.ingest_service = self.ingest
        self.app.state.index_service = self.index
        self.app.state.vector_store = self.vectors
        self.app.state.embedding_provider = _ollama_provider()
        # 空库首启：登记默认配置并发布空索引代（与总控装配生产服务时的顺序一致）
        self.profile = self.catalog.create_embedding_profile(
            fingerprint=embedding_fingerprint(
                model_manifest_digest="digest-1",
                dimensions=4,
                query_prefix="",
                document_prefix="",
                normalization="none",
            ),
            adapter="ollama",
            native_base_url="http://127.0.0.1:11434",
            model_name="bge-m3",
            model_manifest_digest="digest-1",
            dimensions=4,
            distance="cosine",
            query_prefix="",
            document_prefix="",
            normalization="none",
        )
        self.index.ensure_empty_generation(self.profile.profile_id)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")

    def __enter__(self) -> "ApiHarness":
        self.client.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self.client.__exit__(*exc)

    # ---------------------------------------------------------------- 便捷方法

    def create_library(self) -> dict:
        response = self.client.post("/api/v1/textbook-libraries", json=LIBRARY_BODY)
        assert response.status_code == 201, response.text
        return response.json()

    def upload(self, text: str, *, file_name: str = "chapter.md", metadata: dict | None = METADATA):
        files = {"file": (file_name, text.encode("utf-8"), "text/markdown")}
        data = {}
        if metadata is not None:
            data["metadataJson"] = json.dumps(metadata, ensure_ascii=False)
        response = self.client.post("/api/v1/textbook-imports", files=files, data=data)
        return response

    def publish_document(self) -> tuple[dict, dict, dict]:
        library = self.create_library()
        draft = self.upload(sample_text()).json()["draft"]
        response = self.client.post(
            f"/api/v1/textbook-imports/{draft['importId']}/commit",
            json={
                "expectedRevision": draft["revision"],
                "submissionId": "submission-api-1",
                "libraryIds": [library["libraryId"]],
            },
        )
        assert response.status_code == 200, response.text
        return library, draft, response.json()


def _ollama_provider() -> OllamaEmbeddingProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "bge-m3:latest", "size": 12, "digest": "sha256:abc"}]},
            )
        if request.url.path == "/api/show":
            return httpx.Response(
                200,
                json={"details": {"family": "bert", "parameter_size": "567M"}, "capabilities": ["embedding"]},
            )
        if request.url.path == "/api/embed":
            body = json.loads(request.content)
            return httpx.Response(
                200, json={"embeddings": [[0.5, 0.25] for _ in body["input"]]}
            )
        return httpx.Response(404, json={"error": "nope"})

    return OllamaEmbeddingProvider("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))


@pytest.fixture()
def api(tmp_path: Path):
    with ApiHarness(tmp_path) as harness:
        yield harness


# ------------------------------------------------------------------- 服务未装配


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/textbook-libraries"),
        ("GET", "/api/v1/textbook-imports"),
        ("GET", "/api/v1/textbook-jobs"),
        ("GET", "/api/v1/textbooks"),
        ("GET", "/api/v1/textbook-index/status"),
        ("GET", "/api/v1/embedding-models"),
        ("GET", "/api/v1/embedding-profiles"),
        ("GET", "/api/v1/teaching-settings"),
    ],
)
def test_missing_services_return_503_not_empty_list(tmp_path: Path, method: str, path: str) -> None:
    app = create_app(_settings(tmp_path), bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.request(method, path)
    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["retryable"] is True
    assert "未装配" in body["message"]


def test_taxonomy_is_available_without_services(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path), bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.get("/api/v1/textbook-taxonomy")
    assert response.status_code == 200
    body = response.json()
    assert {stage["id"] for stage in body["stages"]} == {"senior"}
    assert {"math", "physics"} <= {subject["id"] for subject in body["subjects"]}
    assert {grade["stageId"] for grade in body["grades"]} == {"senior"}


# --------------------------------------------------------------------- 逻辑库


def test_library_crud_and_revision_conflict(api: ApiHarness) -> None:
    library = api.create_library()
    assert library["documentCount"] == 0
    assert library["ownerId"] == "system"

    listed = api.client.get("/api/v1/textbook-libraries").json()["libraries"]
    assert [item["libraryId"] for item in listed] == [library["libraryId"]]

    detail = api.client.get(f"/api/v1/textbook-libraries/{library['libraryId']}")
    assert detail.status_code == 200
    assert detail.json()["documents"] == []

    patched = api.client.patch(
        f"/api/v1/textbook-libraries/{library['libraryId']}",
        json={"expectedRevision": library["revision"], "displayName": "基础库·数学（改名）"},
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == library["revision"] + 1

    conflict = api.client.patch(
        f"/api/v1/textbook-libraries/{library['libraryId']}",
        json={"expectedRevision": library["revision"], "displayName": "过期写入"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "REVISION_CONFLICT"

    missing = api.client.get("/api/v1/textbook-libraries/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "LIBRARY_NOT_FOUND"

    deleted = api.client.request(
        "DELETE",
        f"/api/v1/textbook-libraries/{library['libraryId']}",
        json={"expectedRevision": patched.json()["revision"]},
    )
    assert deleted.status_code == 204
    assert api.client.get("/api/v1/textbook-libraries").json()["libraries"] == []


# ----------------------------------------------------------------------- 导入


def test_upload_commit_publish_and_source(api: ApiHarness) -> None:
    library, draft, job = api.publish_document()
    # 后台线程在 TestClient 中随响应完成：任务已终态
    assert job["jobId"]
    fetched = api.client.get(f"/api/v1/textbook-jobs/{job['jobId']}").json()
    assert fetched["state"] == "succeeded", fetched
    assert fetched["progress"]["chunksTotal"] > 0

    documents = api.client.get("/api/v1/textbooks").json()["documents"]
    assert len(documents) == 1
    document = documents[0]
    assert document["libraryIds"] == [library["libraryId"]]
    assert document["currentRevision"]["revisionId"] == job["inputRevisionId"]

    draft_view = api.client.get(f"/api/v1/textbook-imports/{draft['importId']}").json()
    assert draft_view["state"] == "ready"
    assert draft_view["canCommit"] is False  # 已提交

    source = api.client.get(
        f"/api/v1/textbook-revisions/{job['inputRevisionId']}/source",
        params={"charStart": 0, "charEnd": 5},
    )
    assert source.status_code == 200
    body = source.json()
    assert body["text"] == "# 第一章"
    assert body["locator"]["kind"] == "markdown"
    assert body["locator"]["lineStart"] == 1

    out_of_range = api.client.get(
        f"/api/v1/textbook-revisions/{job['inputRevisionId']}/source",
        params={"charStart": 0, "charEnd": 10**6},
    )
    assert out_of_range.status_code == 422
    assert out_of_range.json()["code"] == "INVALID_REQUEST"

    # 任教范围：已发布教材 + 匹配逻辑库 → scopeReady
    selection = {
        "gradeId": "senior-1",
        "subjectId": "math",
        "editionId": "renjiao-a",
        "documentIds": [document["documentId"]],
    }
    settings = api.client.get("/api/v1/teaching-settings").json()
    assert settings["scopeReady"] is False and settings["scopeReason"]
    updated = api.client.put(
        "/api/v1/teaching-settings",
        json={"expectedRevision": settings["revision"], "selection": selection},
    )
    assert updated.status_code == 200
    assert updated.json()["scopeReady"] is True
    check = api.client.post(
        "/api/v1/teaching-settings/scope-check", json={"selection": selection}
    ).json()
    assert check["scopeReady"] is True
    assert [item["documentId"] for item in check["documents"]] == [document["documentId"]]
    assert check["missingDocumentIds"] == []

    bad_scope = api.client.post(
        "/api/v1/teaching-settings/scope-check",
        json={"selection": {**selection, "documentIds": [document["documentId"], "ghost"]}},
    ).json()
    assert bad_scope["scopeReady"] is False
    assert bad_scope["missingDocumentIds"] == ["ghost"]


def test_upload_accepts_multipart_with_chinese_filename(api: ApiHarness) -> None:
    response = api.upload(sample_text(), file_name="第一章 集合.md")
    assert response.status_code == 201
    draft = response.json()["draft"]
    assert draft["uploadedFileName"] == "第一章 集合.md"
    assert draft["parsed"]["sourceKind"] == "markdown"


def test_upload_requires_file_part(api: ApiHarness) -> None:
    response = api.client.post(
        "/api/v1/textbook-imports",
        files={"other": ("x.md", b"hello", "text/markdown")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


def test_upload_rejects_unsupported_suffix(api: ApiHarness) -> None:
    response = api.upload("hello", file_name="book.epub")
    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_DOCUMENT_FORMAT"


def test_upload_rejects_oversize(api: ApiHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.v1.textbooks.MAX_UPLOAD_BYTES", 128)
    response = api.upload("x" * 4096)
    assert response.status_code == 413
    assert response.json()["code"] == "DOCUMENT_TOO_LARGE"


def test_needs_ocr_draft_and_commit_error_envelope(api: ApiHarness) -> None:
    from tests.test_document_parsing import _build_pdf

    files = {"file": ("scan.pdf", _build_pdf([""], with_text_stream=False), "application/pdf")}
    response = api.client.post(
        "/api/v1/textbook-imports",
        files=files,
        data={"metadataJson": json.dumps(METADATA, ensure_ascii=False)},
    )
    assert response.status_code == 201
    draft = response.json()["draft"]
    assert draft["state"] == "needs_review"
    assert draft["parsed"]["needsOcr"] is True
    assert draft["canCommit"] is False
    assert draft["warnings"]

    library = api.create_library()
    commit = api.client.post(
        f"/api/v1/textbook-imports/{draft['importId']}/commit",
        json={
            "expectedRevision": draft["revision"],
            "submissionId": "submission-ocr-api",
            "libraryIds": [library["libraryId"]],
        },
    )
    assert commit.status_code == 422
    assert commit.json()["code"] == "DOCUMENT_NEEDS_OCR"
    # 不产生任何任务，也没有发布任何修订
    assert api.client.get("/api/v1/textbook-jobs").json()["jobs"] == []
    assert api.client.get("/api/v1/textbooks").json()["documents"] == []


def test_import_patch_conflict_and_missing_import(api: ApiHarness) -> None:
    draft = api.upload(sample_text(), metadata=None).json()["draft"]
    assert draft["canCommit"] is False
    patched = api.client.patch(
        f"/api/v1/textbook-imports/{draft['importId']}",
        json={"expectedRevision": draft["revision"], "metadata": METADATA},
    )
    assert patched.status_code == 200
    assert patched.json()["canCommit"] is True

    stale = api.client.patch(
        f"/api/v1/textbook-imports/{draft['importId']}",
        json={"expectedRevision": draft["revision"], "metadata": METADATA},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"

    missing = api.client.get("/api/v1/textbook-imports/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "IMPORT_NOT_FOUND"

    unknown_field = api.client.patch(
        f"/api/v1/textbook-imports/{draft['importId']}",
        json={"expectedRevision": patched.json()["revision"], "metadata": METADATA, "oops": 1},
    )
    assert unknown_field.status_code == 422
    assert unknown_field.json()["code"] == "INVALID_REQUEST"


def test_commit_with_stale_revision_is_conflict(api: ApiHarness) -> None:
    library = api.create_library()
    draft = api.upload(sample_text()).json()["draft"]
    commit = api.client.post(
        f"/api/v1/textbook-imports/{draft['importId']}/commit",
        json={
            "expectedRevision": draft["revision"] + 5,
            "submissionId": "submission-stale-api",
            "libraryIds": [library["libraryId"]],
        },
    )
    assert commit.status_code == 409
    assert commit.json()["code"] == "REVISION_CONFLICT"


def test_job_cancel_and_missing_job(api: ApiHarness) -> None:
    library = api.create_library()
    draft = api.upload(sample_text()).json()["draft"]
    # 手工建一个 queued 任务（不触发后台执行）后取消
    job = api.ingest.commit_import(
        draft["importId"],
        expected_revision=draft["revision"],
        submission_id="submission-cancel-api",
        library_ids=[library["libraryId"]],
    )
    assert job.state == "queued"
    cancelled = api.client.post(f"/api/v1/textbook-jobs/{job.jobId}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"

    retried = api.client.post(f"/api/v1/textbook-jobs/{job.jobId}/retry")
    assert retried.status_code == 200
    retried_job = retried.json()
    assert retried_job["state"] == "queued"  # 响应先返回排队状态
    assert retried_job["jobId"] != job.jobId
    # 响应后台任务已执行：重试任务完成并发布
    finished = api.client.get(f"/api/v1/textbook-jobs/{retried_job['jobId']}").json()
    assert finished["state"] == "succeeded", finished
    assert api.client.get("/api/v1/textbooks").json()["documents"][0]["currentRevision"]

    missing = api.client.get("/api/v1/textbook-jobs/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "JOB_NOT_FOUND"


def test_retry_of_rebuild_job_is_rejected(api: ApiHarness) -> None:
    api.publish_document()
    profile_id = api.catalog.list_embedding_profiles()[0].profile_id
    rebuild = api.client.post(
        "/api/v1/textbook-index/rebuilds",
        json={"submissionId": "submission-rebuild-api", "profileId": profile_id},
    )
    assert rebuild.status_code == 201
    job_id = rebuild.json()["jobId"]
    retry = api.client.post(f"/api/v1/textbook-jobs/{job_id}/retry")
    assert retry.status_code == 409
    assert retry.json()["code"] == "RETRY_NOT_SUPPORTED"


# ------------------------------------------------------------------ 教材与删除


def test_document_patch_and_delete(api: ApiHarness) -> None:
    _library, _draft, job = api.publish_document()
    document_id = api.client.get("/api/v1/textbooks").json()["documents"][0]["documentId"]
    detail = api.client.get(f"/api/v1/textbooks/{document_id}").json()
    assert detail["metadata"]["title"] == METADATA["title"]

    patched = api.client.patch(
        f"/api/v1/textbooks/{document_id}",
        json={
            "expectedRevision": detail["revision"],
            "metadata": {**METADATA, "title": "高中数学必修第一册（改）"},
            "libraryIds": detail["libraryIds"],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "高中数学必修第一册（改）"

    empty_libraries = api.client.patch(
        f"/api/v1/textbooks/{document_id}",
        json={
            "expectedRevision": patched.json()["revision"],
            "metadata": METADATA,
            "libraryIds": [],
        },
    )
    assert empty_libraries.status_code == 422

    deleted = api.client.request(
        "DELETE", f"/api/v1/textbooks/{document_id}", json={"expectedRevision": patched.json()["revision"]}
    )
    assert deleted.status_code == 204
    assert api.client.get("/api/v1/textbooks").json()["documents"] == []
    included = api.client.get("/api/v1/textbooks", params={"includeDeleted": True}).json()
    assert len(included["documents"]) == 1
    assert included["documents"][0]["deletedAt"] is not None
    # 删除后原文仍可读（历史引用），但不在任何范围内
    source = api.client.get(
        f"/api/v1/textbook-revisions/{job['inputRevisionId']}/source",
        params={"charStart": 0, "charEnd": 3},
    )
    assert source.status_code == 200


# ----------------------------------------------------------------- Embedding


def test_embedding_models_available_and_unavailable(api: ApiHarness) -> None:
    available = api.client.get("/api/v1/embedding-models")
    assert available.status_code == 200
    body = available.json()
    assert body["available"] is True
    assert body["baseUrl"] == "http://127.0.0.1:11434"
    assert body["models"][0]["name"] == "bge-m3:latest"
    assert body["models"][0]["isEmbeddingCapable"] is True

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    api.app.state.embedding_provider = OllamaEmbeddingProvider(
        "http://127.0.0.1:11434", transport=httpx.MockTransport(boom)
    )
    unavailable = api.client.get("/api/v1/embedding-models")
    assert unavailable.status_code == 200
    assert unavailable.json()["available"] is False
    assert unavailable.json()["reason"]
    assert unavailable.json()["models"] == []


def test_embedding_probe_and_profile_creation(api: ApiHarness) -> None:
    probe = api.client.post("/api/v1/embedding-probes", json={"modelName": "bge-m3"})
    assert probe.status_code == 200
    assert probe.json()["dimensions"] == 4
    assert probe.json()["alreadyConfigured"] is True

    created = api.client.post(
        "/api/v1/embedding-profiles", json={"modelName": "bge-m3", "queryPrefix": "q:"}
    )
    assert created.status_code == 201
    profile = created.json()
    assert profile["modelName"] == "bge-m3"
    assert profile["queryPrefix"] == "q:"

    same = api.client.post(
        "/api/v1/embedding-profiles", json={"modelName": "bge-m3", "queryPrefix": "q:"}
    )
    assert same.status_code == 201
    assert same.json()["profileId"] == profile["profileId"]  # 指纹冲突返回既有配置

    listed = api.client.get("/api/v1/embedding-profiles").json()
    profile_ids = {item["profileId"] for item in listed["profiles"]}
    assert profile["profileId"] in profile_ids
    assert len(profile_ids) == 2  # 空库默认配置 + 新建配置并存
    assert all(isinstance(item["installed"], bool) for item in listed["profiles"])

    unknown = api.client.post("/api/v1/embedding-probes", json={"modelName": "nope"})
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "EMBEDDING_MODEL_MISSING"


# --------------------------------------------------------------------- 索引代


def test_index_status_and_rebuild_endpoint(api: ApiHarness) -> None:
    _library, _draft, job = api.publish_document()
    status = api.client.get("/api/v1/textbook-index/status").json()
    assert status["qdrantAvailable"] is True
    assert status["scopeReady"] is True
    assert status["generation"]["state"] == "ready"
    assert status["generationCount"] == 1

    profile_id = status["activeProfileId"]
    rebuild = api.client.post(
        "/api/v1/textbook-index/rebuilds",
        json={"submissionId": "submission-rebuild-api-2", "profileId": profile_id},
    )
    assert rebuild.status_code == 201
    rebuild_job = rebuild.json()
    assert rebuild_job["kind"] == "rebuild"
    assert rebuild_job["baseGenerationId"] == status["activeGenerationId"]

    # 后台执行完成：当前索引代已切换、闸门释放
    after = api.client.get("/api/v1/textbook-index/status").json()
    assert after["activeGenerationId"] == rebuild_job["targetGenerationId"]
    assert after["rebuildJob"] is None
    assert after["generationCount"] == 2
    assert api.client.get(f"/api/v1/textbook-jobs/{rebuild_job['jobId']}").json()["state"] == "succeeded"
    assert api.client.get("/api/v1/textbooks").json()["documents"][0]["currentRevision"] is not None
    assert api.catalog.get_revision(job["inputRevisionId"]) is not None


# --------------------------------------------------------- v1.1 同一内容重复导入


def test_same_content_reimport_reuses_document_via_api(api: ApiHarness) -> None:
    library = api.create_library()
    payload = sample_text("集合")
    first = api.upload(payload).json()["draft"]
    first_job = api.client.post(
        f"/api/v1/textbook-imports/{first['importId']}/commit",
        json={
            "expectedRevision": first["revision"],
            "submissionId": "submission-api-reuse-1",
            "libraryIds": [library["libraryId"]],
        },
    )
    assert first_job.status_code == 200, first_job.text

    second = api.upload(payload).json()["draft"]
    second_job = api.client.post(
        f"/api/v1/textbook-imports/{second['importId']}/commit",
        json={
            "expectedRevision": second["revision"],
            "submissionId": "submission-api-reuse-2",
            "libraryIds": [library["libraryId"]],
        },
    )
    assert second_job.status_code == 200, second_job.text
    assert api.client.get(f"/api/v1/textbook-jobs/{second_job.json()['jobId']}").json()["state"] == "succeeded"

    documents = api.client.get("/api/v1/textbooks").json()["documents"]
    assert len(documents) == 1  # 相同内容不产生第二册
    assert len(api.catalog.list_document_revisions(documents[0]["documentId"])) == 2  # 追加为第二个修订
    assert documents[0]["currentRevision"]["revisionId"] == second_job.json()["inputRevisionId"]
    assert documents[0]["currentRevision"]["chunkCount"] > 0

    draft_view = api.client.get(f"/api/v1/textbook-imports/{second['importId']}").json()
    assert any("相同内容" in warning for warning in draft_view["warnings"])
    assert draft_view["state"] == "ready"
