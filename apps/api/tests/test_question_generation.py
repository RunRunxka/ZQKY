"""题库 B2 增量验收：AI 补题生成链 + 知识点关联 + 派生指纹（A6/A7）。

全部使用 pytest ``tmp_path`` 临时四库与受控模型替身，不触网、不读写正式
``.local-data``/``.env``；生成任务后台调度按 ``workflow-jobs?domain=question`` 轮询，
与前端观察路径一致。

生成链覆盖点（任务卡 §6.4 / §9 A7）：
- 合法生成：202 只代表任务被接受；候选落 ``needs_review`` 草稿 + ``source='ai'`` 草稿关联 +
  ``question_import_provenance(source='ai')``，**确认前 questions 一行不涨**；
- 发布失败注入：批次/候选/来源/任务终态同事务，失败零可发布半批；
- 非法 JSON、截断、未知知识点、虚构依据、URL/路径、非法 assetId、候选数不符各一例；
- 取消（执行器返回后取消）：不发布、任务 ``cancelled``；
- 知识点关联：草稿整表替换/清空、同学科未归档校验、确认冻结、按知识点检索、
  改题复制/替换关联、拆/合口径（不继承 + 明确提示 + 旧行可追溯）；
- 派生指纹：``derived-v1`` 版本化、补算不改旧列、富内容权威与资产真实字节散列。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Sequence

import pytest

from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMConfig, LLMResponse
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.knowledge.points import KnowledgePointRepository, SubjectRepository
from app.schemas.question_bank import QuestionGenerationRequest, QuestionPatchRequest
from app.services.question_bank import fingerprint as fp
from app.services.question_bank import generation
from app.services.question_bank.blobs import QuestionBlobStore
from tests.test_question_bank import (
    LOCAL_PROFILE,
    FakeLLMProvider,
)
from tests.test_question_bank_confirm import (
    ONE_QUESTION_DOC,
    confirm,
    questions,
    reviewed_draft,
)

_UNSET = object()
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


# --------------------------------------------------------------------------- 夹具


class GenerationHarness:
    """题库 B2 测试夹具：真实临时库 + 注入替身，并按 ``main.py`` 的目标装配接线。

    - ``knowledge_catalog`` = 题解库只读入口、``coordinator`` = 跨库发布协调器、
      ``job_engine`` = 共享统一任务引擎（``create_app`` 已装配 question 域）；
    - ``wire_knowledge=False`` 用于验证"知识点库未装配 → 503 而不是假成功"；
    - ``with_client=False`` 用于纯 asyncio 场景（取消/并发）：不进入 TestClient 生命周期，
      应用目录保持打开，任务全部跑在测试自己的事件循环上。
    """

    def __init__(
        self,
        tmp_path: Path,
        *,
        provider: FakeLLMProvider | None = None,
        resolver: Any = _UNSET,
        model_resolver: Any = _UNSET,
        with_client: bool = True,
        wire_knowledge: bool = True,
        job_engine: Any = _UNSET,
    ) -> None:
        from app.main import create_app
        from app.services.question_bank.service import build_question_bank_service
        from tests.test_question_bank import FakeResolver, make_handle, make_settings

        self.settings = make_settings(tmp_path)
        self.app = create_app(self.settings)
        self.catalog = self.app.state.question_bank
        assert self.catalog is not None, "题库目录未装配"
        self.provider = provider if provider is not None else FakeLLMProvider()
        self.resolver = (
            FakeResolver(default=make_handle(LOCAL_PROFILE, provider=self.provider))
            if resolver is _UNSET
            else resolver
        )
        self.service = build_question_bank_service(
            self.catalog,
            self.settings,
            # 显式传 None（未装配）与不传是两种测试意图，用哨兵区分
            model_resolver=(self.resolver if model_resolver is _UNSET else model_resolver),
            knowledge_catalog=(self.app.state.knowledge if wire_knowledge else None),
            coordinator=self.app.state.publication_coordinator,
            job_engine=(self.app.state.job_engine if job_engine is _UNSET else job_engine),
        )
        self.app.state.question_bank_service = self.service
        self.client: Any = None
        if with_client:
            from fastapi.testclient import TestClient

            self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
            self.client.__enter__()

    def close(self) -> None:
        if self.client is not None:
            self.client.__exit__(None, None, None)

    # -------------------------------------------------------------- 便捷方法

    def handle(self, profile_id: str = LOCAL_PROFILE, **overrides: Any):
        from tests.test_question_bank import make_handle

        overrides.setdefault("provider", self.provider)
        return make_handle(profile_id, **overrides)

    def upload(self, data: bytes | str, *, name: str = "第三章练习.md", **fields: str):
        assert self.client is not None
        payload = data.encode("utf-8") if isinstance(data, str) else data
        return self.client.post(
            "/api/v1/question-imports",
            files={"file": (name, payload, "text/markdown")},
            data=fields or None,
        )

    def import_detail(self, import_id: str) -> dict:
        assert self.client is not None
        response = self.client.get(f"/api/v1/question-imports/{import_id}")
        assert response.status_code == 200, response.text
        return response.json()

    def sample_detail(self, **fields: str) -> dict:
        from tests.test_question_bank import SAMPLE_DOC

        response = self.upload(SAMPLE_DOC, **fields)
        assert response.status_code == 201, response.text
        return response.json()

    def patch_draft(self, draft: dict, **overrides: Any):
        from tests.test_question_bank import review_payload

        assert self.client is not None
        payload = review_payload(draft, **overrides)
        return self.client.patch(f"/api/v1/question-drafts/{draft['draftId']}", json=payload)

    def knowledge(self) -> KnowledgeCatalog:
        return self.app.state.knowledge

    def create_point(
        self, *, subject_id: str = "math", code: str = "kp-1", name: str = "一次函数"
    ) -> dict:
        with self.knowledge().write_transaction() as conn:
            SubjectRepository().ensure_subject(conn, subject_id=subject_id, name=subject_id)
            record = KnowledgePointRepository().create_point(
                conn, subject_id=subject_id, code=code, name=name
            )
        return {
            "pointId": record.point_id,
            "revisionId": record.revision_id,
            "name": record.name,
            "subjectId": record.subject_id,
            "code": record.code,
        }

    def archive_point(self, point_id: str) -> None:
        repository = KnowledgePointRepository()
        with self.knowledge().write_transaction() as conn:
            record = repository.require_point(conn, point_id)
            repository.set_status(
                conn, point_id, expected_revision=record.revision, archived=True
            )

    def generation_body(self, **overrides: Any) -> dict:
        body: dict[str, Any] = {
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": "math",
            "knowledgePointIds": [],
            "questionTypes": ["short_answer"],
            "difficulty": "medium",
            "count": 1,
            "materials": [],
        }
        body.update(overrides)
        return body

    def start_generation(self, **overrides: Any):
        assert self.client is not None
        return self.client.post(
            "/api/v1/question-generation-jobs", json=self.generation_body(**overrides)
        )

    def job_view(self, job_id: str) -> dict:
        """公共任务视图（六态 + attempt + result/error）。"""
        if self.client is None:
            return (
                self.service.job_engine.store("question")
                .get(job_id)
                .view()
                .model_dump(mode="json")
            )
        response = self.client.get(
            f"/api/v1/workflow-jobs/{job_id}", params={"domain": "question"}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def wait_job(self, job_id: str, *, timeout: float = 8.0) -> dict:
        deadline = time.monotonic() + timeout
        view = self.job_view(job_id)
        while view["state"] not in TERMINAL_STATES and time.monotonic() < deadline:
            time.sleep(0.02)
            view = self.job_view(job_id)
        assert view["state"] in TERMINAL_STATES, view
        return view

    def generation_view(self, job_id: str) -> dict:
        """生成任务视图（importId / candidateCount / errorCode）。"""
        return self.service.generation_job_view(job_id).model_dump(mode="json")

    def run_generation(self, **overrides: Any) -> dict:
        response = self.start_generation(**overrides)
        assert response.status_code == 202, response.text
        return self.wait_job(response.json()["jobId"])

    def row_count(self, table: str) -> int:
        connection = sqlite3.connect(self.catalog.db_path)
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            connection.close()

    def revision_links(self, revision_id: str) -> list[tuple[str, str]]:
        connection = sqlite3.connect(self.catalog.db_path)
        try:
            return [
                (row[0], row[1])
                for row in connection.execute(
                    "SELECT knowledge_point_id, role FROM question_knowledge_links "
                    "WHERE question_revision_id = ? ORDER BY rowid",
                    (revision_id,),
                ).fetchall()
            ]
        finally:
            connection.close()

    def revision_link_rows(self, revision_id: str) -> list[tuple[str, ...]]:
        """正式关联的完整快照行（除 created_at），用于断言旧修订逐字节未变。"""
        connection = sqlite3.connect(self.catalog.db_path)
        try:
            return [
                tuple(row)
                for row in connection.execute(
                    "SELECT knowledge_point_id, knowledge_revision_id, subject_id_snapshot, "
                    "knowledge_name_snapshot, role FROM question_knowledge_links "
                    "WHERE question_revision_id = ? ORDER BY rowid",
                    (revision_id,),
                ).fetchall()
            ]
        finally:
            connection.close()

    def provenance(self, import_id: str):
        return self.catalog.get_import_provenance(import_id)

    def upload_sample(self, doc: str = ONE_QUESTION_DOC, **fields: str) -> dict:
        response = self.upload(doc, **fields)
        assert response.status_code == 201, response.text
        return response.json()

    def patch_links(self, draft_id: str, revision: int, links: list[dict], **extra: Any):
        """只改关联的 PATCH：内容/分类取当前值，显式给 knowledgeLinks（整表替换）。"""
        assert self.client is not None
        current = self.catalog.get_draft(draft_id)
        payload: dict[str, Any] = {
            "expectedRevision": revision,
            "content": current.content,
            "metadata": current.metadata,
            "knowledgeLinks": links,
        }
        payload.update(extra)
        return self.client.patch(f"/api/v1/question-drafts/{draft_id}", json=payload)


@pytest.fixture()
def harness(tmp_path: Path):
    instance = GenerationHarness(tmp_path)
    try:
        yield instance
    finally:
        instance.close()


def generation_reply(
    *,
    count: int = 1,
    knowledge_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    stem: str = "生成题干：下列说法正确的是（ ）",
    options: Sequence[dict[str, str]] | None = None,
    asset_ids: Sequence[str] = (),
) -> str:
    questions_payload = []
    for index in range(count):
        questions_payload.append(
            {
                "type": "single_choice" if options else "short_answer",
                "stemMarkdown": stem if count == 1 else f"{stem}（第 {index + 1} 题）",
                "options": list(options or []),
                "answer": (
                    {"choiceKeys": ["A"], "accepted": None, "textMarkdown": None}
                    if options
                    else {"choiceKeys": [], "accepted": None, "textMarkdown": "示例答案"}
                ),
                "explanationMarkdown": "示例解析。",
                "knowledgePointIds": list(knowledge_ids),
                "evidenceIds": list(evidence_ids),
                "assetIds": list(asset_ids),
            }
        )
    return json.dumps({"questions": questions_payload}, ensure_ascii=False)


def failure_code(harness: GenerationHarness, job_id: str) -> str | None:
    """失败补题后：零批次/零来源/零正式题，返回任务级错误码。"""
    view = harness.wait_job(job_id)
    assert view["state"] == "failed", view
    final = harness.generation_view(job_id)
    assert final["importId"] is None
    assert harness.row_count("question_imports") == 0
    assert harness.row_count("question_drafts") == 0
    assert harness.row_count("question_draft_knowledge_links") == 0
    assert harness.row_count("question_import_provenance") == 0
    assert harness.row_count("questions") == 0
    return final["errorCode"]


# ------------------------------------------------------------------ 1 合法生成


def test_generate_publishes_needs_review_batch_with_links_and_provenance(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point(code="kp-linear", name="一次函数")
    harness.provider.replies = [
        generation_reply(
            knowledge_ids=[point["pointId"]],
            evidence_ids=["m0"],
            options=[{"key": "A", "textMarkdown": "y=2x+1"}],
        )
    ]
    response = harness.start_generation(
        knowledgePointIds=[point["pointId"]],
        questionTypes=["single_choice"],
        difficulty="easy",
        count=1,
        instructions="结合证据命题",
        materials=["一次函数形如 y=kx+b（k≠0）。"],
    )
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["state"] in ("queued", "running")
    assert accepted["attempt"] == 0
    assert accepted["importId"] is None and accepted["candidateCount"] == 0

    view = harness.wait_job(accepted["jobId"])
    assert view["state"] == "succeeded", view
    assert view["attempt"] == 1  # 经 JobEngine claim 执行
    assert view["error"] is None
    assert view["result"]["candidateCount"] == 1
    import_id = view["result"]["importId"]
    assert import_id
    final = harness.generation_view(accepted["jobId"])
    assert (final["state"], final["importId"], final["candidateCount"]) == (
        "succeeded",
        import_id,
        1,
    )
    assert final["errorCode"] is None

    # 候选只落 needs_review 草稿：确认前正式题一行不涨
    detail = harness.import_detail(import_id)
    assert detail["state"] == "needs_review"
    assert len(detail["drafts"]) == 1
    draft = detail["drafts"][0]
    assert draft["extractionMethod"] == "ai"
    assert draft["reviewState"] == "needs_review"
    assert draft["sourceSpans"] == []  # 补题没有上传原文块，来源不冒充教材
    assert draft["warnings"]  # 明确提示尚未入库
    assert draft["content"]["stemMarkdown"].startswith("生成题干")
    assert draft["metadata"]["subjectId"] == "math"
    assert draft["metadata"]["difficulty"] == "easy"
    assert draft["metadata"]["knowledgeTags"] == []  # 旧标签不得自动变成正式知识点
    assert draft["knowledgeLinks"] == [
        {
            "knowledgePointId": point["pointId"],
            "knowledgeRevisionId": point["revisionId"],
            "knowledgeNameSnapshot": point["name"],
            "subjectIdSnapshot": "math",
            "role": "primary",
            "source": "ai",
        }
    ]
    assert harness.row_count("questions") == 0

    # 生成来源 + 非敏感模型快照
    provenance = harness.provenance(import_id)
    assert provenance is not None
    assert provenance.source == "ai"
    assert provenance.job_id == accepted["jobId"]
    assert provenance.model_snapshot["profileId"] == LOCAL_PROFILE
    assert provenance.model_snapshot["fingerprint"].startswith("sha256:")
    serialized = json.dumps(provenance.model_snapshot, ensure_ascii=False)
    assert "qwen2.5:7b" not in serialized and "apiKey" not in serialized

    # 冻结输入：允许知识点/证据/题型/数量 + 模型指纹，且不含凭证
    record = harness.service.job_record(accepted["jobId"])
    assert generation.is_current_frozen_input(record.frozen_input)
    frozen = record.frozen_input
    assert frozen["knowledgePoints"][0]["pointId"] == point["pointId"]
    assert frozen["knowledgePoints"][0]["revisionId"] == point["revisionId"]
    assert frozen["materials"][0]["id"] == "m0"
    assert frozen["count"] == 1
    assert "sk-test" not in json.dumps(frozen, ensure_ascii=False)
    assert record.model_snapshot["profileId"] == LOCAL_PROFILE

    # 生成原件（模型原始回复）作为内容寻址 blob 落盘，读取时重算 sha256
    import_record = harness.catalog.get_import(import_id)
    blobs = QuestionBlobStore(harness.settings.question_bank_root)
    original = blobs.read(import_record.original_blob_id)
    assert b"rawReply" in original and point["pointId"].encode() in original

    # 模型只调一次；提示词带冻结的 count / 知识点 id / 证据 id
    assert len(harness.provider.calls) == 1
    call = harness.provider.calls[0]
    assert "命制 1 道题" in call.messages[0].content
    assert point["pointId"] in call.messages[1].content
    assert "[m0]" in call.messages[1].content
    assert "结合证据命题" in call.messages[1].content


def test_generate_publish_failure_leaves_zero_publishable_batch(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point()
    harness.provider.replies = [generation_reply(knowledge_ids=[point["pointId"]])]

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("注入发布失败")

    harness.catalog.create_drafts_in = boom  # type: ignore[method-assign]
    view = harness.run_generation(knowledgePointIds=[point["pointId"]])
    final = harness.generation_view(view["jobId"])

    assert view["state"] == "failed", view
    assert view["error"]["code"] == "JOB_FAILED"
    assert final["errorCode"] == "JOB_FAILED"
    assert final["importId"] is None and final["candidateCount"] == 0
    # 批次、候选、关联、来源、正式题零残留（同一事务整体回滚）
    assert harness.row_count("question_imports") == 0
    assert harness.row_count("question_drafts") == 0
    assert harness.row_count("question_draft_knowledge_links") == 0
    assert harness.row_count("question_import_provenance") == 0
    assert harness.row_count("questions") == 0


def test_generate_candidates_enter_formal_table_only_after_confirm(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point()
    harness.provider.replies = [generation_reply(knowledge_ids=[point["pointId"]])]
    view = harness.run_generation(knowledgePointIds=[point["pointId"]])
    import_id = harness.generation_view(view["jobId"])["importId"]
    assert import_id
    assert questions(harness)["total"] == 0

    draft = reviewed_draft(harness, import_id, 0)
    result = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-ai-0001",
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["failures"] == []
    assert len(body["confirmedQuestionIds"]) == 1

    question_id = body["confirmedQuestionIds"][0]
    response = harness.client.get(f"/api/v1/questions/{question_id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["knowledgeLinks"] == [
        {
            "knowledgePointId": point["pointId"],
            "knowledgeRevisionId": point["revisionId"],
            "knowledgeNameSnapshot": point["name"],
            "subjectIdSnapshot": "math",
            "role": "primary",
        }
    ]
    assert questions(harness, knowledgePointId=point["pointId"])["total"] == 1
    assert questions(harness, knowledgePointId="kp-not-exist")["total"] == 0


# ------------------------------------------------------- 2 生成校验（每类一例）


@pytest.mark.parametrize(
    ("label", "reply"),
    [
        ("invalid_json", "{不是 JSON"),
        ("not_object", "[1, 2, 3]"),
        ("missing_questions", json.dumps({"items": []}, ensure_ascii=False)),
    ],
)
def test_generate_rejects_invalid_json(
    harness: GenerationHarness, label: str, reply: str
) -> None:
    harness.provider.replies = [reply]
    response = harness.start_generation()
    assert response.status_code == 202, response.text
    assert failure_code(harness, response.json()["jobId"]) == generation.INVALID_JSON, label


def test_generate_rejects_truncated_output(harness: GenerationHarness) -> None:
    harness.provider.replies = [
        LLMResponse(text='{"questions":[{"stemMarkdown":"写', finishReason=FINISH_LENGTH)
    ]
    response = harness.start_generation()
    assert response.status_code == 202, response.text
    assert failure_code(harness, response.json()["jobId"]) == generation.OUTPUT_TRUNCATED
    assert harness.provider.calls  # 调用确实发生过，只是输出不可用


def test_generate_rejects_unknown_knowledge_point(harness: GenerationHarness) -> None:
    point = harness.create_point()
    harness.provider.replies = [generation_reply(knowledge_ids=["kp-outside"])]
    response = harness.start_generation(knowledgePointIds=[point["pointId"]])
    assert response.status_code == 202, response.text
    assert failure_code(harness, response.json()["jobId"]) == generation.UNKNOWN_KNOWLEDGE


def test_generate_rejects_fabricated_evidence(harness: GenerationHarness) -> None:
    point = harness.create_point()
    harness.provider.replies = [
        generation_reply(knowledge_ids=[point["pointId"]], evidence_ids=["m9"])
    ]
    response = harness.start_generation(
        knowledgePointIds=[point["pointId"]], materials=["唯一一份证据"]
    )
    assert response.status_code == 202, response.text
    assert failure_code(harness, response.json()["jobId"]) == generation.UNKNOWN_EVIDENCE


@pytest.mark.parametrize(
    "stem",
    [
        "请参考 https://example.com/lesson 的内容作答",
        "题目来自 file:///tmp/paper.docx",
        r"请打开 C:\Users\teacher\题库.docx 查看原题",
        "原文见 /etc/passwd 或 /usr/local/share/questions",
        r"附件在 \\fileserver\share\paper.docx",
    ],
)
def test_generate_rejects_urls_and_paths(harness: GenerationHarness, stem: str) -> None:
    harness.provider.replies = [generation_reply(stem=stem)]
    response = harness.start_generation()
    assert response.status_code == 202, response.text
    assert (
        failure_code(harness, response.json()["jobId"]) == generation.FORBIDDEN_REFERENCE
    )


@pytest.mark.parametrize(
    ("asset_id", "expected_code"),
    [
        ("blobs/not-a-hash", generation.ASSET_INVALID),
        ("assets/abc", generation.ASSET_INVALID),
        ("blobs/" + "0" * 64, generation.ASSET_NOT_REGISTERED),
    ],
)
def test_generate_rejects_illegal_assets(
    harness: GenerationHarness, asset_id: str, expected_code: str
) -> None:
    harness.provider.replies = [generation_reply(asset_ids=[asset_id])]
    response = harness.start_generation()
    assert response.status_code == 202, response.text
    assert failure_code(harness, response.json()["jobId"]) == expected_code


def test_generate_rejects_candidate_count_mismatch(harness: GenerationHarness) -> None:
    harness.provider.replies = [generation_reply(count=2)]
    response = harness.start_generation(count=1)
    assert response.status_code == 202, response.text
    assert (
        failure_code(harness, response.json()["jobId"])
        == generation.CANDIDATE_COUNT_MISMATCH
    )


def test_generate_accepts_registered_asset_bytes(harness: GenerationHarness) -> None:
    """已登记的 blobs/<64hex> 原件可被引用：真实字节散列一致才算已登记。"""
    payload = b"PNG-BYTES"
    blob_id, _size = harness.service.blobs.write(payload)
    harness.provider.replies = [generation_reply(asset_ids=[f"blobs/{blob_id}"])]
    view = harness.run_generation()
    assert view["state"] == "succeeded", view
    import_id = harness.generation_view(view["jobId"])["importId"]
    draft = harness.import_detail(import_id)["drafts"][0]
    assert draft["content"]["assetIds"] == [f"blobs/{blob_id}"]


def test_generate_rejects_material_with_url(harness: GenerationHarness) -> None:
    response = harness.start_generation(materials=["见 http://example.com/a"])
    assert response.status_code == 422, response.text
    assert response.json()["code"] == generation.MATERIAL_INVALID
    assert harness.provider.calls == []
    assert harness.row_count("question_imports") == 0


def test_generate_requires_knowledge_catalog_for_points(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path, wire_knowledge=False)
    try:
        response = harness.start_generation(knowledgePointIds=["kp-1"])
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "KNOWLEDGE_CATALOG_UNAVAILABLE"
        assert harness.provider.calls == []
        assert harness.row_count("question_imports") == 0
        # 不选知识点时仍可补题（知识点库不是硬依赖）
        harness.provider.replies = [generation_reply()]
        view = harness.run_generation()
        assert view["state"] == "succeeded"
    finally:
        harness.close()


def test_generate_rejects_cross_subject_points(harness: GenerationHarness) -> None:
    math = harness.create_point(subject_id="math", code="kp-m")
    physics = harness.create_point(subject_id="physics", code="kp-p")
    response = harness.start_generation(
        subjectId="math", knowledgePointIds=[math["pointId"], physics["pointId"]]
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "KNOWLEDGE_SUBJECT_MISMATCH"
    assert harness.provider.calls == []


def test_generate_unresolved_model_profile_fails_before_job(harness: GenerationHarness) -> None:
    harness.resolver.error = AppError(
        "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
    )
    response = harness.start_generation()
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "MODEL_PROFILE_NOT_FOUND"
    assert harness.provider.calls == []
    assert harness.service.job_engine.store("question").list_recent(limit=10) == []


# ------------------------------------------------------------------------ 3 取消


class GatedProvider(FakeLLMProvider):
    """闸门替身：进入模型调用即置事件并记账，等放行后才返回（取消迟到/并发名额用）。"""

    def __init__(self, started: asyncio.Event, release: asyncio.Event) -> None:
        super().__init__()
        self.started = started
        self.release = release
        #: 已进入 complete 的调用（含尚未返回者），用于断言"名额已满、第二个不进"
        self.entered: list[int] = []

    async def complete(self, config: LLMConfig, request: Any, *, transport: Any = None):
        self.entered.append(len(self.entered))
        self.started.set()
        await self.release.wait()
        return await super().complete(config, request, transport=transport)


def _generation_request(point_ids: Sequence[str], *, count: int = 1) -> QuestionGenerationRequest:
    return QuestionGenerationRequest.model_validate(
        {
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": "math",
            "knowledgePointIds": list(point_ids),
            "questionTypes": ["short_answer"],
            "difficulty": "medium",
            "count": count,
            "materials": [],
        }
    )


def test_cancel_after_executor_returns_does_not_publish(tmp_path: Path) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        provider = GatedProvider(started, release)
        harness = GenerationHarness(tmp_path, with_client=False, provider=provider)
        try:
            point = harness.create_point()
            provider.replies = [generation_reply(knowledge_ids=[point["pointId"]])]
            view = await harness.service.create_generation_job(
                _generation_request([point["pointId"]])
            )
            assert view.state in ("queued", "running"), view
            await asyncio.wait_for(started.wait(), timeout=5)
            # 执行器已拿到结果、尚未发布：先请求取消，再放行（取消优先于迟到结果）
            store = harness.service.job_engine.store("question")
            store.request_cancel(view.jobId)
            release.set()
            deadline = time.monotonic() + 5
            record = store.get(view.jobId)
            while record.state not in TERMINAL_STATES and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
                record = store.get(view.jobId)
            assert record.state == "cancelled", record.state
            assert record.result is None
            assert harness.row_count("question_imports") == 0
            assert harness.row_count("question_drafts") == 0
            assert harness.row_count("question_import_provenance") == 0
        finally:
            await harness.service.job_engine.shutdown()
            harness.close()

    asyncio.run(scenario())


# ------------------------------------------------------------------ 4 草稿关联


def test_draft_links_replace_clear_and_force_review(harness: GenerationHarness) -> None:
    first = harness.create_point(code="kp-a", name="知识点 A")
    second = harness.create_point(code="kp-b", name="知识点 B")
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]

    reviewed = harness.patch_draft(draft)  # 先标 reviewed（内容不变）
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewState"] == "reviewed"

    linked = harness.patch_links(
        draft["draftId"],
        reviewed.json()["revision"],
        [{"knowledgePointId": first["pointId"], "role": "primary"}],
        reviewState="reviewed",
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    # 关联变化把草稿拉回 needs_review，并递增 revision
    assert body["revision"] == reviewed.json()["revision"] + 1
    assert body["reviewState"] == "needs_review"
    assert [item["knowledgePointId"] for item in body["knowledgeLinks"]] == [first["pointId"]]
    assert body["knowledgeLinks"][0]["source"] == "human"
    assert body["knowledgeLinks"][0]["knowledgeNameSnapshot"] == "知识点 A"

    # 提供即整表替换
    replaced = harness.patch_links(
        draft["draftId"],
        body["revision"],
        [
            {"knowledgePointId": first["pointId"], "role": "secondary"},
            {"knowledgePointId": second["pointId"], "role": "primary"},
        ],
    )
    assert replaced.status_code == 200, replaced.text
    links = replaced.json()["knowledgeLinks"]
    assert [(item["knowledgePointId"], item["role"]) for item in links] == [
        (first["pointId"], "secondary"),
        (second["pointId"], "primary"),
    ]

    # 空数组 = 清空
    cleared = harness.patch_links(draft["draftId"], replaced.json()["revision"], [])
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["knowledgeLinks"] == []
    assert cleared.json()["revision"] == replaced.json()["revision"] + 1
    assert cleared.json()["reviewState"] == "needs_review"

    # 乐观锁：过期 revision 409
    stale = harness.patch_links(draft["draftId"], body["revision"], [])
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVISION_CONFLICT"


def test_draft_patch_without_links_keeps_existing_links(harness: GenerationHarness) -> None:
    """缺省 knowledgeLinks 不动关联（仅显式提供才整表替换）。"""
    point = harness.create_point()
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"], draft["revision"], [{"knowledgePointId": point["pointId"]}]
    )
    assert linked.status_code == 200, linked.text
    content = dict(linked.json()["content"])
    content["stemMarkdown"] = "只改题干（ ）"
    patched = harness.patch_draft(linked.json() | {"draftId": draft["draftId"]}, content=content)
    assert patched.status_code == 200, patched.text
    assert [item["knowledgePointId"] for item in patched.json()["knowledgeLinks"]] == [
        point["pointId"]
    ]


@pytest.mark.parametrize(
    ("case", "expected_status", "expected_code"),
    [
        ("unknown", 404, "KNOWLEDGE_POINT_NOT_FOUND"),
        ("archived", 422, "KNOWLEDGE_POINT_ARCHIVED"),
        ("other_subject", 422, "KNOWLEDGE_SUBJECT_MISMATCH"),
        ("duplicate", 422, "KNOWLEDGE_LINK_DUPLICATE"),
    ],
)
def test_draft_links_validation(
    harness: GenerationHarness, case: str, expected_status: int, expected_code: str
) -> None:
    point = harness.create_point(subject_id="math")
    other = harness.create_point(subject_id="physics", code="kp-p", name="物理点")
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]

    if case == "unknown":
        links = [{"knowledgePointId": "kp-missing"}]
    elif case == "archived":
        harness.archive_point(point["pointId"])
        links = [{"knowledgePointId": point["pointId"]}]
    elif case == "other_subject":
        links = [{"knowledgePointId": other["pointId"]}]
    else:
        links = [
            {"knowledgePointId": point["pointId"]},
            {"knowledgePointId": point["pointId"], "role": "secondary"},
        ]

    response = harness.patch_links(draft["draftId"], draft["revision"], links)
    assert response.status_code == expected_status, response.text
    assert response.json()["code"] == expected_code
    # 校验失败不落任何关联、不改草稿
    assert harness.catalog.draft_knowledge_links(draft["draftId"]) == []
    assert harness.catalog.get_draft(draft["draftId"]).revision == draft["revision"]


def test_draft_links_require_knowledge_catalog(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path, wire_knowledge=False)
    try:
        detail = harness.upload_sample(subjectId="math")
        draft = detail["drafts"][0]
        response = harness.patch_links(
            draft["draftId"], draft["revision"], [{"knowledgePointId": "kp-1"}]
        )
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "KNOWLEDGE_CATALOG_UNAVAILABLE"
        assert harness.catalog.get_draft(draft["draftId"]).revision == draft["revision"]
        # 清空（空数组）不需要知识点库，仍可执行
        cleared = harness.patch_links(draft["draftId"], draft["revision"], [])
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["knowledgeLinks"] == []
    finally:
        harness.close()


# ------------------------------------------------- 5 正式关联：确认 / 检索 / 改题


def _confirmed_question(harness: GenerationHarness, point: dict) -> tuple[str, dict]:
    """上传 → 关联 → reviewed → 确认，返回 (questionId, QuestionDetail)。"""
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"],
        draft["revision"],
        [{"knowledgePointId": point["pointId"], "role": "primary"}],
    )
    assert linked.status_code == 200, linked.text
    reviewed = harness.patch_draft(
        {"draftId": draft["draftId"], "revision": linked.json()["revision"],
         "content": linked.json()["content"], "metadata": linked.json()["metadata"]}
    )
    assert reviewed.status_code == 200, reviewed.text
    result = confirm(
        harness,
        detail["importId"],
        [
            {
                "draftId": draft["draftId"],
                "expectedDraftRevision": reviewed.json()["revision"],
            }
        ],
        submission_id=f"submission-{draft['draftId'][:12]}",
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["failures"] == [], body
    question_id = body["confirmedQuestionIds"][0]
    response = harness.client.get(f"/api/v1/questions/{question_id}")
    assert response.status_code == 200, response.text
    return question_id, response.json()


def test_confirm_freezes_draft_links_into_immutable_revision(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point(code="kp-freeze", name="冻结关联点")
    question_id, detail = _confirmed_question(harness, point)
    assert detail["knowledgeLinks"] == [
        {
            "knowledgePointId": point["pointId"],
            "knowledgeRevisionId": point["revisionId"],
            "knowledgeNameSnapshot": "冻结关联点",
            "subjectIdSnapshot": "math",
            "role": "primary",
        }
    ]
    record = harness.catalog.get_question(question_id)
    assert harness.revision_links(record.current_revision_id) == [(point["pointId"], "primary")]
    # 不可变：触发器拒绝 UPDATE / DELETE 正式关联
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE question_knowledge_links SET role = 'secondary' "
                "WHERE question_revision_id = ?",
                (record.current_revision_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM question_knowledge_links WHERE question_revision_id = ?",
                (record.current_revision_id,),
            )
    finally:
        connection.close()


def test_confirm_freezes_ai_draft_without_links_as_empty(
    harness: GenerationHarness,
) -> None:
    """无关联也可确认（历史未分类题可读）：明确显示未正式关联，不伪造。"""
    harness.provider.replies = [generation_reply()]
    view = harness.run_generation()
    import_id = harness.generation_view(view["jobId"])["importId"]
    draft = reviewed_draft(harness, import_id, 0)
    result = confirm(
        harness,
        import_id,
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-nolink-0001",
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["failures"] == []
    question_id = body["confirmedQuestionIds"][0]
    detail = harness.client.get(f"/api/v1/questions/{question_id}").json()
    assert detail["knowledgeLinks"] == []


def test_http_patch_question_knowledge_links_contract(harness: GenerationHarness) -> None:
    """HTTP 契约（B2 字段补齐）：提供即整表替换（`[]` 清空）、缺省复制旧正式关联。

    ① 带 ``knowledgeLinks`` → 新修订 + 关联被替换，**旧修订关联逐字节未变**；
    ② 不带该字段 → 与既有行为一致（复制旧正式关联）；
    ③ ``knowledgeLinks: []`` → 新修订 + 零关联（检索不再命中）。
    """
    point = harness.create_point(code="kp-http", name="HTTP 关联点")
    replacement = harness.create_point(code="kp-http-2", name="HTTP 新关联点")
    question_id, detail = _confirmed_question(harness, point)
    old_revision_id = harness.catalog.get_question(question_id).current_revision_id
    old_rows = harness.revision_link_rows(old_revision_id)
    assert [(row[0], row[4]) for row in old_rows] == [(point["pointId"], "primary")]

    # ① 显式改关联：新修订 + 替换；旧修订旧关联逐字节未变
    content = dict(detail["content"])
    content["stemMarkdown"] = "HTTP 改关联（ ）"
    replaced = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": detail["revision"],
            "content": content,
            "metadata": detail["metadata"],
            "knowledgeLinks": [
                {"knowledgePointId": replacement["pointId"], "role": "secondary"}
            ],
        },
    )
    assert replaced.status_code == 200, replaced.text
    body = replaced.json()
    assert body["revision"] == detail["revision"] + 1
    assert [
        (item["knowledgePointId"], item["role"]) for item in body["knowledgeLinks"]
    ] == [(replacement["pointId"], "secondary")]
    new_revision_id = harness.catalog.get_question(question_id).current_revision_id
    assert new_revision_id != old_revision_id
    assert harness.revision_link_rows(old_revision_id) == old_rows
    assert questions(harness, knowledgePointId=point["pointId"])["total"] == 0
    assert questions(harness, knowledgePointId=replacement["pointId"])["total"] == 1

    # ② 缺省字段：复制旧正式关联（此时旧关联 = replacement）
    content = dict(body["content"])
    content["stemMarkdown"] = "HTTP 缺省复制（ ）"
    copied = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": body["revision"],
            "content": content,
            "metadata": detail["metadata"],
        },
    )
    assert copied.status_code == 200, copied.text
    copied_body = copied.json()
    assert copied_body["revision"] == body["revision"] + 1
    assert [
        (item["knowledgePointId"], item["role"]) for item in copied_body["knowledgeLinks"]
    ] == [(replacement["pointId"], "secondary")]
    assert harness.revision_link_rows(new_revision_id) == [
        (replacement["pointId"], replacement["revisionId"], "math", "HTTP 新关联点", "secondary")
    ]

    # ③ 空数组 = 清空（新修订 + 零关联；旧修订仍然可查）
    cleared = harness.client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "expectedRevision": copied_body["revision"],
            "content": content,
            "metadata": detail["metadata"],
            "knowledgeLinks": [],
        },
    )
    assert cleared.status_code == 200, cleared.text
    cleared_body = cleared.json()
    assert cleared_body["revision"] == copied_body["revision"] + 1
    assert cleared_body["knowledgeLinks"] == []
    assert questions(harness, knowledgePointId=replacement["pointId"])["total"] == 0
    assert harness.revision_link_rows(new_revision_id) == [
        (replacement["pointId"], replacement["revisionId"], "math", "HTTP 新关联点", "secondary")
    ]


def test_patch_question_copies_links_and_replaces_only_when_asked(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point(code="kp-copy", name="原关联点")
    replacement = harness.create_point(code="kp-new", name="新关联点")
    question_id, detail = _confirmed_question(harness, point)
    old_revision_id = harness.catalog.get_question(question_id).current_revision_id

    # 内容修改：新修订 + 复制旧正式关联
    content = dict(detail["content"])
    content["stemMarkdown"] = "改过的题干（ ）"
    patched = harness.service.patch_question(
        question_id,
        QuestionPatchRequest(
            expectedRevision=detail["revision"],
            content=content,
            metadata=detail["metadata"],
        ),
    )
    assert patched.revision == detail["revision"] + 1
    assert [item.knowledgePointId for item in patched.knowledgeLinks] == [point["pointId"]]
    new_revision_id = harness.catalog.get_question(question_id).current_revision_id
    assert new_revision_id != old_revision_id
    # 旧修订的关联仍在（复制而非搬移）
    assert harness.revision_links(old_revision_id) == [(point["pointId"], "primary")]

    # 明确改关联：新修订 + 替换关联，旧修订旧关联不动
    replaced = harness.service.patch_question(
        question_id,
        QuestionPatchRequest(
            expectedRevision=patched.revision,
            content=content,
            metadata=detail["metadata"],
        ),
        knowledge_links=[{"knowledgePointId": replacement["pointId"], "role": "primary"}],
    )
    assert [item.knowledgePointId for item in replaced.knowledgeLinks] == [
        replacement["pointId"]
    ]
    assert harness.revision_links(old_revision_id) == [(point["pointId"], "primary")]
    assert len(harness.catalog.question_knowledge_links(question_id)) == 1

    # 检索按最新修订：老知识点不再命中，新知识点命中
    assert questions(harness, knowledgePointId=point["pointId"])["total"] == 0
    assert questions(harness, knowledgePointId=replacement["pointId"])["total"] == 1
    # 明确清空关联
    cleared = harness.service.patch_question(
        question_id,
        QuestionPatchRequest(
            expectedRevision=replaced.revision,
            content=content,
            metadata=detail["metadata"],
        ),
        knowledge_links=[],
    )
    assert cleared.knowledgeLinks == []
    assert questions(harness, knowledgePointId=replacement["pointId"])["total"] == 0


# ------------------------------------------------------- 6 拆分/合并关联口径


def test_split_and_merge_do_not_inherit_links_but_keep_source_traceable(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point(code="kp-split", name="拆合点")
    detail = harness.upload_sample(subjectId="math")
    draft = detail["drafts"][0]
    linked = harness.patch_links(
        draft["draftId"], draft["revision"], [{"knowledgePointId": point["pointId"]}]
    )
    assert linked.status_code == 200, linked.text
    span = linked.json()["sourceSpans"][0]
    offset = (span["charStart"] + span["charEnd"]) // 2

    split = harness.client.post(
        f"/api/v1/question-imports/{detail['importId']}/split",
        params={"draftId": draft["draftId"]},
        json={"expectedRevision": linked.json()["revision"], "charOffset": offset},
    )
    assert split.status_code == 200, split.text
    after = harness.import_detail(detail["importId"])
    new_drafts = [item for item in after["drafts"] if item["draftId"] != draft["draftId"]]
    assert len(new_drafts) == 2
    for item in new_drafts:
        assert item["knowledgeLinks"] == []  # 不继承
        assert any("重新校对关联" in warning for warning in item["warnings"])
    # 被替代的旧草稿行保留并继续携带原关联，供追溯（不静默宣称关联仍有效）
    old_links = harness.catalog.draft_knowledge_links(draft["draftId"])
    assert [item.knowledge_point_id for item in old_links] == [point["pointId"]]
    assert after["drafts"][0]["reviewState"] == "excluded"

    # 合并：同样不继承，且明确提示
    merged = harness.client.post(
        f"/api/v1/question-imports/{detail['importId']}/merge",
        json={"expectedRevisions": {item["draftId"]: item["revision"] for item in new_drafts}},
    )
    assert merged.status_code == 200, merged.text
    merged_detail = harness.import_detail(detail["importId"])
    merged_drafts = [
        item
        for item in merged_detail["drafts"]
        if item["extractionMethod"] == "manual" and item["reviewState"] != "excluded"
    ]
    assert merged_drafts
    assert merged_drafts[-1]["knowledgeLinks"] == []
    assert any("重新校对关联" in warning for warning in merged_drafts[-1]["warnings"])


# ------------------------------------------------------------ 7 派生指纹版本化


def test_derived_fingerprint_is_versioned_and_does_not_rewrite_legacy_column(
    harness: GenerationHarness,
) -> None:
    point = harness.create_point(code="kp-fp", name="指纹点")
    question_id, _detail = _confirmed_question(harness, point)
    record = harness.catalog.get_question(question_id)
    legacy = record.content_fingerprint
    assert legacy == fp.content_fingerprint(record.content)

    derived = harness.catalog.derived_fingerprint(
        record.current_revision_id, algorithm_version=fp.DERIVED_ALGORITHM_VERSION
    )
    assert derived == fp.derived_content_fingerprint(record.content)
    assert harness.row_count("question_content_fingerprints") == 1

    # 派生指纹幂等；旧指纹列一字不动
    assert harness.catalog.derived_fingerprint(
        record.current_revision_id, algorithm_version=fp.DERIVED_ALGORITHM_VERSION
    ) == derived
    assert harness.catalog.get_question(question_id).content_fingerprint == legacy

    # 模拟历史数据（缺派生行）：显式补算，仍不改旧列
    connection = sqlite3.connect(harness.catalog.db_path)
    try:
        connection.execute(
            "DELETE FROM question_content_fingerprints WHERE question_revision_id = ?",
            (record.current_revision_id,),
        )
        connection.commit()
    finally:
        connection.close()
    assert (
        harness.catalog.derived_fingerprint(
            record.current_revision_id, algorithm_version=fp.DERIVED_ALGORITHM_VERSION
        )
        is None
    )
    assert harness.service.backfill_derived_fingerprints() == 1
    assert (
        harness.catalog.derived_fingerprint(
            record.current_revision_id, algorithm_version=fp.DERIVED_ALGORITHM_VERSION
        )
        == derived
    )
    assert harness.catalog.get_question(question_id).content_fingerprint == legacy
    assert harness.service.backfill_derived_fingerprints() == 0


def test_derived_fingerprint_covers_materials_rich_content_and_asset_bytes() -> None:
    content = {
        "type": "short_answer",
        "stemMarkdown": "题干",
        "options": [],
        "answer": None,
        "explanationMarkdown": None,
        "assetIds": [],
    }
    base = fp.derived_content_fingerprint(content)
    assert base == fp.derived_content_fingerprint(content)  # 同输入可复算
    assert fp.DERIVED_ALGORITHM_VERSION == "derived-v1"

    # 共享材料进入派生指纹（顺序敏感）
    assert fp.derived_content_fingerprint(content, materials=["证据 A"]) != base
    assert fp.derived_content_fingerprint(
        content, materials=["证据 A", "证据 B"]
    ) != fp.derived_content_fingerprint(content, materials=["证据 B", "证据 A"])

    # 富内容权威：富内容变化即便 Markdown 不变也改变派生值
    rich = {"kind": "rich_content_v2", "blocks": [{"type": "paragraph", "text": "权威"}]}
    with_rich = fp.derived_content_fingerprint(content, rich_content=rich)
    assert with_rich != base
    assert (
        fp.derived_content_fingerprint(
            content, rich_content={"kind": "rich_content_v2", "blocks": []}
        )
        != with_rich
    )

    # 资产真实字节散列：blobs/<hex> 键即内容寻址散列
    digest = "a" * 64
    with_asset = fp.derived_content_fingerprint(
        {**content, "assetIds": [f"blobs/{digest}"]}
    )
    assert with_asset != base
    assert fp.asset_byte_hash(f"blobs/{digest}") == digest
    assert fp.asset_byte_hash("legacy-asset-id") == fp.asset_content_hash("legacy-asset-id")


def test_legacy_markdown_question_still_readable_and_confirmable(
    harness: GenerationHarness,
) -> None:
    """B2 保持旧 Markdown 题可读：无关联、无资产的老题照常确认、检索与改题。"""
    detail = harness.upload_sample(subjectId="math")
    draft = reviewed_draft(harness, detail["importId"], 0)
    result = confirm(
        harness,
        detail["importId"],
        [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
        submission_id="submission-legacy-0001",
    )
    assert result.status_code == 200, result.text
    question_id = result.json()["confirmedQuestionIds"][0]
    response = harness.client.get(f"/api/v1/questions/{question_id}")
    assert response.status_code == 200, response.text
    detail_view = response.json()
    assert detail_view["knowledgeLinks"] == []  # 未正式关联：明确显示为空
    assert questions(harness)["total"] == 1

    # 老题改题：复制（空）关联 + 写派生指纹，仍可读
    content = dict(detail_view["content"])
    content["stemMarkdown"] = "旧题改题干（ ）"
    patched = harness.service.patch_question(
        question_id,
        QuestionPatchRequest(
            expectedRevision=detail_view["revision"],
            content=content,
            metadata=detail_view["metadata"],
        ),
    )
    assert patched.knowledgeLinks == []
    assert patched.revision == detail_view["revision"] + 1
    assert (
        harness.catalog.derived_fingerprint(
            harness.catalog.get_question(question_id).current_revision_id,
            algorithm_version=fp.DERIVED_ALGORITHM_VERSION,
        )
        is not None
    )


def test_question_links_error_when_knowledge_catalog_missing(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path, wire_knowledge=False)
    try:
        detail = harness.upload_sample(subjectId="math")
        draft = reviewed_draft(harness, detail["importId"], 0)
        result = confirm(
            harness,
            detail["importId"],
            [{"draftId": draft["draftId"], "expectedDraftRevision": draft["revision"]}],
            submission_id="submission-nokp-0001",
        )
        assert result.status_code == 200, result.text
        question_id = result.json()["confirmedQuestionIds"][0]
        view = harness.client.get(f"/api/v1/questions/{question_id}").json()
        with pytest.raises(AppError) as excinfo:
            harness.service.patch_question(
                question_id,
                QuestionPatchRequest(
                    expectedRevision=view["revision"],
                    content=view["content"],
                    metadata=view["metadata"],
                ),
                knowledge_links=[{"knowledgePointId": "kp-1"}],
            )
        assert excinfo.value.code == "KNOWLEDGE_CATALOG_UNAVAILABLE"
        # 未装配知识点库时"改内容"仍可复制旧关联（无需跨库读取）
        content = dict(view["content"])
        content["stemMarkdown"] = "不需要知识点库的改题（ ）"
        patched = harness.service.patch_question(
            question_id,
            QuestionPatchRequest(
                expectedRevision=view["revision"],
                content=content,
                metadata=view["metadata"],
            ),
        )
        assert patched.knowledgeLinks == []
    finally:
        harness.close()
