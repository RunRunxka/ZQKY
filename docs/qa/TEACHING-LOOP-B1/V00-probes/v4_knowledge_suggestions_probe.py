"""V4 AI 候选探针（TEACHING-LOOP B1 / V00）。

受控模型替身；覆盖：
  非法 JSON / 未知引用 / 截断 / 配置失效 / 取消迟到（各一例）；
  候选只进 source="ai" 的待确认批次（正式知识点表零新增）；
  publish 注入失败 → 任务 failed 且批次/正式表零残留（同事务）；
  教材证据不可用 → 503 且不建任务。
不联网；模型调用一律替身。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v4_knowledge_suggestions")
root = temp_data_root("v4")
ensure_api_on_path()

from app.contracts.knowledge import KnowledgeSuggestionRequest  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.providers.llm.base import (  # noqa: E402
    FINISH_LENGTH,
    FINISH_STOP,
    LLMConfig,
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from app.repositories.assets.file_assets import FileAssetsRepository  # noqa: E402
from app.repositories.jobs.repository import JobStore  # noqa: E402
from app.repositories.knowledge.catalog import KnowledgeCatalog  # noqa: E402
from app.repositories.teaching.catalog import TeachingCatalog  # noqa: E402
from app.schemas.model_config import ModelProtocol  # noqa: E402
from app.services.assets.store import AssetStore  # noqa: E402
from app.services.jobs.engine import JobEngine  # noqa: E402
from app.services.knowledge.service import build_knowledge_service  # noqa: E402
from app.services.model_runtime import ChatModelHandle  # noqa: E402
from app.services.publication import PublicationCoordinator  # noqa: E402

DATA = root / "data"
kcat = KnowledgeCatalog(DATA / "knowledge" / "knowledge.sqlite3")
kcat.migrate()
tcat = TeachingCatalog(DATA / "teaching" / "teaching.sqlite3")
tcat.migrate()
assets = AssetStore(DATA / "assets")
file_assets = FileAssetsRepository(tcat)

VALID_MATERIAL = "a" * 40


class FakeProvider(LLMProvider):
    """受控替身：按脚本返回文本或抛错；不发任何网络请求。"""

    def __init__(self) -> None:
        self.script: list[tuple[str, str]] = []  # (kind, payload)
        self.calls = 0

    def queue(self, kind: str, payload: str = "") -> None:
        self.script.append((kind, payload))

    async def _complete(self, config: LLMConfig, request: LLMRequest, transport=None) -> LLMResponse:
        self.calls += 1
        kind, payload = self.script.pop(0) if self.script else ("text", "{}")
        if kind == "raise":
            raise AppError(payload, code="UPSTREAM_UNAVAILABLE", status_code=503, retryable=True)
        if kind == "length":
            return LLMResponse(text=payload, finishReason=FINISH_LENGTH)
        return LLMResponse(text=payload, finishReason=FINISH_STOP)

    def _stream(self, config, request, transport=None):  # pragma: no cover - 本批不用流式
        raise NotImplementedError


provider = FakeProvider()


def handle(profile_id: str = "probe-profile") -> ChatModelHandle:
    config = LLMConfig(
        protocol=ModelProtocol.openai_chat,
        baseUrl="http://127.0.0.1:9/probe",
        modelId="probe-model",
        apiKey="probe-not-a-real-key",
        modelProfileId=profile_id,
    )
    return ChatModelHandle(
        profile_id=profile_id, model_id="probe-model", provider=provider, config=config
    )


def make_resolver(fail: bool = False):
    def resolver(profile_id: str, *, purpose: str | None = "chat"):
        if fail:
            raise AppError(
                "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
            )
        return handle(profile_id)

    return resolver


def counts() -> dict[str, int]:
    import sqlite3

    result = {}
    conn = sqlite3.connect(str(kcat.db_path))
    conn.row_factory = sqlite3.Row
    for table in ("knowledge_points", "knowledge_imports", "knowledge_import_rows", "knowledge_jobs"):
        result[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    conn.close()
    conn = sqlite3.connect(str(tcat.db_path))
    conn.row_factory = sqlite3.Row
    result["file_assets"] = conn.execute("SELECT COUNT(*) AS n FROM file_assets").fetchone()["n"]
    conn.close()
    return result


def business() -> dict[str, int]:
    """业务表计数（不含任务表：每次候选都会新增一条任务行，属预期）。"""
    return {k: v for k, v in counts().items() if k != "knowledge_jobs"}


def store_for(engine: JobEngine) -> JobStore:
    return engine.store("knowledge")


async def run_job(service, engine: JobEngine, captured: list, payload):
    engine_schedule = engine.schedule

    def spy(domain, job_id, executor, **kwargs):
        task = engine_schedule(domain, job_id, executor, **kwargs)
        captured.append(task)
        return task

    engine.schedule = spy  # type: ignore[assignment]
    try:
        view = await service.create_suggestion_job(payload)
    finally:
        engine.schedule = engine_schedule  # type: ignore[assignment]
    task = captured[-1]
    record = await asyncio.wait_for(task, timeout=30)
    return view, record


async def main() -> None:
    store = JobStore(
        kcat, domain="knowledge", table="knowledge_jobs", kinds=frozenset({"suggestion"})
    )
    engine = JobEngine({"knowledge": store}, heavy_limit=2, model_limit=1)
    service = build_knowledge_service(
        kcat,
        asset_store=assets,
        file_assets=file_assets,
        evidence=None,
        coordinator=PublicationCoordinator(),
        model_resolver=make_resolver(),
        job_engine=engine,
    )
    base_payload = KnowledgeSuggestionRequest.model_validate(
        {
            "modelProfileId": "probe-profile",
            "subjectId": "math",
            "materials": [{"id": "m-1", "text": VALID_MATERIAL}],
        }
    )

    # ---------------------------------------------------------------- 正常路径
    provider.queue(
        "text",
        json.dumps(
            {
                "candidates": [
                    {
                        "code": "AI-01",
                        "name": "候选一",
                        "description": "说明",
                        "aliases": ["别"],
                        "evidenceIds": ["m-1"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    before = counts()
    view, record = await run_job(service, engine, [], base_payload)
    after = counts()
    p.check(
        "v4.1a 任务 succeeded 且返回 candidateCount",
        record.state == "succeeded" and record.result.get("candidateCount") == 1,
        json.dumps({"state": record.state, "result": record.result}, ensure_ascii=False),
    )
    p.check(
        "v4.1b 候选只进 source=ai 待确认批次（正式知识点表零新增）",
        after["knowledge_points"] == before["knowledge_points"] == 0
        and after["knowledge_imports"] == before["knowledge_imports"] + 1,
        f"before={before} after={after}",
    )
    origin_row = await asyncio.to_thread(
        _import_row, record.result["importId"]
    )
    p.check(
        "v4.1c 批次 source=ai / state=reviewing / candidate 行已落库",
        origin_row["source"] == "ai"
        and origin_row["state"] == "reviewing"
        and origin_row["rows"] == 1,
        json.dumps(origin_row, ensure_ascii=False),
    )
    p.check(
        "v4.1d 模型原始输出登记为教学库 file_assets（§8.3 跨库逻辑引用）",
        after["file_assets"] == before["file_assets"] + 1,
        f"assets {before['file_assets']} -> {after['file_assets']}",
    )
    p.check(
        "v4.1e 任务视图 202 语义字段（jobId/state/attempt）齐全",
        view.job_id == record.job_id and view.state in {"queued", "running", "succeeded"} and view.attempt >= 0,
        json.dumps({"jobId": view.job_id, "state": view.state, "attempt": view.attempt}),
    )

    # ---------------------------------------------------------------- 非法 JSON
    provider.queue("text", "这不是 JSON")
    before = business()
    _, rec_json = await run_job(service, engine, [], base_payload)
    after = business()
    p.check(
        "v4.2a 非法 JSON → 任务 failed + KNOWLEDGE_SUGGESTION_INVALID_JSON",
        rec_json.state == "failed"
        and rec_json.error is not None
        and rec_json.error_code == "KNOWLEDGE_SUGGESTION_INVALID_JSON",
        json.dumps({"state": rec_json.state, "error": rec_json.error_code}, ensure_ascii=False),
    )
    p.check(
        "v4.2b 非法 JSON：批次/正式表/资产零新增",
        after == before,
        f"before={before} after={after}",
    )

    # ---------------------------------------------------------------- 未知引用
    provider.queue(
        "text",
        json.dumps({"candidates": [{"code": "AI-02", "name": "x", "evidenceIds": ["not-an-evidence"]}]}),
    )
    before = business()
    _, rec_ref = await run_job(service, engine, [], base_payload)
    after = business()
    p.check(
        "v4.3a 未知引用 → 任务 failed + KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE",
        rec_ref.state == "failed"
        and rec_ref.error is not None
        and rec_ref.error_code == "KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE",
        json.dumps({"state": rec_ref.state, "error": rec_ref.error_code}, ensure_ascii=False),
    )
    p.check("v4.3b 未知引用零写入", after == before, f"before={before} after={after}")

    # ---------------------------------------------------------------- 截断
    provider.queue("length", json.dumps({"candidates": []}))
    before = business()
    _, rec_len = await run_job(service, engine, [], base_payload)
    after = business()
    p.check(
        "v4.4a 截断（finishReason=length）→ 任务 failed + KNOWLEDGE_SUGGESTION_TRUNCATED",
        rec_len.state == "failed"
        and rec_len.error is not None
        and rec_len.error_code == "KNOWLEDGE_SUGGESTION_TRUNCATED",
        json.dumps({"state": rec_len.state, "error": rec_len.error_code}, ensure_ascii=False),
    )
    p.check("v4.4b 截断零写入", after == before, f"before={before} after={after}")

    # ---------------------------------------------------------------- 配置失效
    provider.queue("text", json.dumps({"candidates": []}))
    failing = build_knowledge_service(
        kcat,
        asset_store=assets,
        file_assets=file_assets,
        evidence=None,
        coordinator=PublicationCoordinator(),
        model_resolver=make_resolver(fail=True),
        job_engine=engine,
    )
    before = business()
    _, rec_cfg = await run_job(failing, engine, [], base_payload)
    after = business()
    p.check(
        "v4.5a 模型配置失效 → 任务 failed + MODEL_PROFILE_NOT_FOUND（不落假候选）",
        rec_cfg.state == "failed"
        and rec_cfg.error is not None
        and rec_cfg.error_code == "MODEL_PROFILE_NOT_FOUND",
        json.dumps({"state": rec_cfg.state, "error": rec_cfg.error_code}, ensure_ascii=False),
    )
    p.check("v4.5b 配置失效零写入", after == before, f"before={before} after={after}")

    # ---------------------------------------------------------------- 取消迟到
    provider.queue(
        "text",
        json.dumps(
            {"candidates": [{"code": "AI-09", "name": "迟到", "evidenceIds": ["m-1"]}]},
            ensure_ascii=False,
        ),
    )
    before = business()
    engine_schedule = engine.schedule
    cancel_tasks: list = []

    def spy_cancel(domain, job_id, executor, **kwargs):
        task = engine_schedule(domain, job_id, executor, **kwargs)
        cancel_tasks.append(task)
        return task

    engine.schedule = spy_cancel  # type: ignore[assignment]
    try:
        # 建任务（已调度但尚未开跑）→ 请求取消 → 再放行执行：
        # 执行器在模型返回后才探测到取消（迟到结果不得发布）
        view_cancel = await service.create_suggestion_job(base_payload)
    finally:
        engine.schedule = engine_schedule  # type: ignore[assignment]
    store.request_cancel(view_cancel.job_id)
    rec_cancel = await asyncio.wait_for(cancel_tasks[-1], timeout=30)
    after = business()
    p.check(
        "v4.6a 取消迟到 → 任务 cancelled（不发布迟到结果）",
        rec_cancel.state == "cancelled",
        json.dumps({"state": rec_cancel.state, "result": rec_cancel.result}, ensure_ascii=False),
    )
    p.check(
        "v4.6b 取消迟到：批次/正式表/资产零新增",
        after == before,
        f"before={before} after={after}",
    )

    # ---------------------------------------------------------------- publish 注入失败
    provider.queue(
        "text",
        json.dumps(
            {"candidates": [{"code": "AI-77", "name": "回滚", "evidenceIds": ["m-1"]}]},
            ensure_ascii=False,
        ),
    )
    broken = build_knowledge_service(
        kcat,
        asset_store=assets,
        file_assets=file_assets,
        evidence=None,
        coordinator=PublicationCoordinator(),
        model_resolver=make_resolver(),
        job_engine=engine,
    )

    original_create = broken.imports.create_import

    def boom(*args, **kwargs):
        raise AppError("探针注入：候选批次写入失败。", code="PROBE_PUBLISH_FAILED", status_code=500)

    broken.imports.create_import = boom  # type: ignore[assignment]
    before = business()
    published_error = None
    job_id_pub = None
    engine_schedule = engine.schedule
    captured_pub: list = []

    def spy_pub(domain, job_id, executor, **kwargs):
        nonlocal job_id_pub
        job_id_pub = job_id
        task = engine_schedule(domain, job_id, executor, **kwargs)
        captured_pub.append(task)
        return task

    engine.schedule = spy_pub  # type: ignore[assignment]
    try:
        view_pub = await broken.create_suggestion_job(base_payload)
        job_id_pub = view_pub.job_id
    finally:
        engine.schedule = engine_schedule  # type: ignore[assignment]
    try:
        await asyncio.wait_for(captured_pub[-1], timeout=30)
    except AppError as exc:
        published_error = exc
    after = business()
    broken.imports.create_import = original_create  # type: ignore[assignment]
    state_pub = await asyncio.to_thread(_job_state, job_id_pub)
    p.check(
        "v4.7a publish 注入失败 → 异常向上抛（B0 引擎文档口径），未写 succeeded",
        published_error is not None and published_error.code == "PROBE_PUBLISH_FAILED",
        f"{type(published_error).__name__}: {getattr(published_error, 'code', None)}",
    )
    p.check(
        "v4.7a2 publish 失败后任务状态（记录实际值；非 succeeded）",
        state_pub != "succeeded",
        f"state={state_pub}",
    )
    p.check(
        "v4.7b 批次/行零残留（同事务回滚）",
        after["knowledge_imports"] == before["knowledge_imports"]
        and after["knowledge_import_rows"] == before["knowledge_import_rows"],
        f"imports {before['knowledge_imports']}->{after['knowledge_imports']} rows {before['knowledge_import_rows']}->{after['knowledge_import_rows']}",
    )
    p.check(
        "v4.7c 已落盘的原始输出资产登记保留（§8.3 预先登记的只增不改）",
        after["file_assets"] == before["file_assets"] + 1,
        f"assets {before['file_assets']} -> {after['file_assets']}",
    )

    # ---------------------------------------------------------------- 教材证据不可用
    evidence_payload = KnowledgeSuggestionRequest.model_validate(
        {
            "modelProfileId": "probe-profile",
            "subjectId": "math",
            "textbookEvidence": [
                {"documentRevisionId": "doc-1", "charStart": 0, "charEnd": 10}
            ],
        }
    )
    before = counts()
    raised = None
    try:
        await service.create_suggestion_job(evidence_payload)
    except AppError as exc:
        raised = exc
    after = counts()
    p.check(
        "v4.8a 教材证据不可用 → 503 TEXTBOOK_EVIDENCE_UNAVAILABLE",
        raised is not None
        and raised.code == "TEXTBOOK_EVIDENCE_UNAVAILABLE"
        and raised.status_code == 503,
        f"{type(raised).__name__}: {getattr(raised, 'code', None)} {raised}",
    )
    p.check(
        "v4.8b 教材证据不可用不建任务（knowledge_jobs 零新增）",
        after["knowledge_jobs"] == before["knowledge_jobs"],
        f"jobs {before['knowledge_jobs']} -> {after['knowledge_jobs']}",
    )

    # ---------------------------------------------------------------- 无证据 / 无引擎
    no_evidence = KnowledgeSuggestionRequest.model_validate(
        {"modelProfileId": "probe-profile", "subjectId": "math"}
    )
    raised2 = None
    try:
        await service.create_suggestion_job(no_evidence)
    except AppError as exc:
        raised2 = exc
    p.check(
        "v4.9a 无任何证据 → 422 KNOWLEDGE_SUGGESTION_NO_EVIDENCE",
        raised2 is not None
        and raised2.code == "KNOWLEDGE_SUGGESTION_NO_EVIDENCE"
        and raised2.status_code == 422,
        f"{getattr(raised2, 'code', None)} {raised2}",
    )
    no_engine = build_knowledge_service(
        kcat,
        asset_store=assets,
        file_assets=file_assets,
        evidence=None,
        coordinator=PublicationCoordinator(),
        model_resolver=make_resolver(),
        job_engine=None,
    )
    raised3 = None
    try:
        await no_engine.create_suggestion_job(base_payload)
    except AppError as exc:
        raised3 = exc
    p.check(
        "v4.9b 未装配任务引擎 → 503 SERVICE_UNAVAILABLE（不假成功）",
        raised3 is not None and raised3.code == "SERVICE_UNAVAILABLE" and raised3.status_code == 503,
        f"{getattr(raised3, 'code', None)} {raised3}",
    )
    await engine.shutdown()


def _job_state(job_id: str) -> str:
    import sqlite3

    conn = sqlite3.connect(str(kcat.db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT state FROM knowledge_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return row["state"] if row else "<missing>"


def _import_row(import_id: str) -> dict:
    import sqlite3

    conn = sqlite3.connect(str(kcat.db_path))
    conn.row_factory = sqlite3.Row
    record = conn.execute(
        "SELECT source, state FROM knowledge_imports WHERE id = ?", (import_id,)
    ).fetchone()
    rows = conn.execute(
        "SELECT COUNT(*) AS n FROM knowledge_import_rows WHERE import_id = ?", (import_id,)
    ).fetchone()["n"]
    conn.close()
    return {"source": record["source"], "state": record["state"], "rows": rows}


try:
    asyncio.run(main())
except Exception as exc:  # noqa: BLE001
    p.crashed = f"{type(exc).__name__}: {exc}"
    p.check("v4 探针整体执行", False, p.crashed)

sys.exit(p.finish())
