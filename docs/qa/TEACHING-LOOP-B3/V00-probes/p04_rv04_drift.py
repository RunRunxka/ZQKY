"""V00 · RV04 探针：模型配置漂移守卫（四条路径，自建故障注入）。

缺陷回顾（B2-RV04）：原卷建议 / 题库生成 / 整理恢复 / 知识点候选在排队期间同 profile
改为 model-B 后仍按 model-A 的旧指纹记录来源（执行与来源不一致）。

本探针：
  A. 共享实现 `resolve_frozen_model` 单元级：缺指纹 422 / 漂移 409 / 一致通过 /
     快照与错误消息不含凭证；
  B. 四条真实执行路径：占住共享模型名额 → 目标任务 queued → 同 profile 换模型 →
     放行 → 终态 failed + MODEL_CONFIG_DRIFT + 该路径零上游调用、零发布；
  C. 旧行缺指纹：直接建任务行（model_snapshot 无 fingerprint）→ 经公共 retry 调度 →
     failed + MODEL_FINGERPRINT_MISSING，零调用；
  D. 凭证边界：落库快照 / 任务视图 / 错误消息中都不出现替身 API Key。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p04_rv04_drift.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00_papers import PapersProbe  # noqa: E402

from _v00 import (  # noqa: E402
    AppError,
    FakeProvider,
    FakeResolver,
    FAKE_API_KEY,
    LOCAL_PROFILE,
    make_handle,
    make_settings,
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _build_executor_registry, create_app  # noqa: E402
from app.schemas.model_config import ApiFormat, ModelConnection, ModelProfile, ModelProtocol  # noqa: E402
from app.services.knowledge.service import build_knowledge_service  # noqa: E402
from app.services.model_runtime import (  # noqa: E402
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    fingerprint_of_handle,
    model_fingerprint,
    resolve_frozen_model,
)
from app.services.question_bank.service import build_question_bank_service  # noqa: E402

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
IMPORT_DOC = """# 探针练习

1. 下列函数中，是一次函数的是（ ）
A. y = x^2
B. y = 2x + 1
C. y = 1/x
D. y = x^3
答案：B
解析：形如 y = kx + b（k≠0）的函数是一次函数。
"""
GEN_BODY = {
    "modelProfileId": LOCAL_PROFILE,
    "subjectId": "math",
    "knowledgePointIds": [],
    "questionTypes": ["short_answer"],
    "difficulty": "medium",
    "count": 1,
    "materials": [],
}
GEN_REPLY = (
    '{"questions":[{"type":"short_answer","stemMarkdown":"题干（ ）","options":[],'
    '"answer":{"choiceKeys":[],"accepted":null,"textMarkdown":"答案"},'
    '"explanationMarkdown":"解析","knowledgePointIds":[],"evidenceIds":[],"assetIds":[]}]}'
)


# --------------------------------------------------------------------------- 单元级替身


class _FakeSecrets:
    def has(self, connection_id: str) -> bool:
        return True

    def resolve(self, connection_id: str) -> str:
        return FAKE_API_KEY


class _FakeModelRepo:
    def __init__(self, model_id: str) -> None:
        now = datetime.now(UTC)
        self.profile = ModelProfile(
            id="p1", connectionId="c1", displayName="探针", modelId=model_id,
            purpose="chat", createdAt=now, updatedAt=now,
        )
        self.connection = ModelConnection(
            id="c1", displayName="探针", protocol=ModelProtocol.openai_chat,
            baseUrl="http://127.0.0.1:11434/v1", apiFormat=ApiFormat.openai_chat,
            createdAt=now, updatedAt=now,
        )

    def get_profile(self, profile_id: str):
        return self.profile if profile_id == self.profile.id else None

    def get_connection(self, connection_id: str):
        return self.connection if connection_id == self.connection.id else None


def unit_checks(results: dict[str, Any], failures: list[str]) -> None:
    repo = _FakeModelRepo("model-A")
    secrets = _FakeSecrets()
    # 冻结值必须来自**创建时**的同一实现（fingerprint_of_handle），与执行期核对对称
    from app.services.model_runtime import resolve_chat_model

    created_handle = resolve_chat_model(repo, secrets, "p1")
    good = {"profileId": "p1", "fingerprint": fingerprint_of_handle(created_handle)}
    handle = resolve_frozen_model(repo, secrets, good)
    ok_fingerprint = fingerprint_of_handle(handle) == good["fingerprint"]

    def code_of(snapshot: dict[str, Any]) -> list[Any]:
        try:
            resolve_frozen_model(repo, secrets, snapshot)
        except AppError as exc:
            return [exc.code, exc.status_code, str(exc)]
        return ["NO_ERROR", None, ""]

    missing = code_of({"profileId": "p1"})
    missing_profile = code_of({"fingerprint": good["fingerprint"]})
    drift = code_of({"profileId": "p1", "fingerprint": "sha256:" + "d" * 64})
    results["unit_resolve_frozen_model"] = {
        "matchOk": ok_fingerprint,
        "missingFingerprint": missing[:2],
        "missingProfileId": missing_profile[:2],
        "drift": drift[:2],
        "credentialsInFingerprint": FAKE_API_KEY in good["fingerprint"],
        "credentialsInErrors": any(
            FAKE_API_KEY in row[2] for row in (missing, missing_profile, drift)
        ),
    }
    if not (
        ok_fingerprint
        and missing[0] == MODEL_FINGERPRINT_MISSING and missing[1] == 422
        and missing_profile[0] == MODEL_FINGERPRINT_MISSING
        and drift[0] == MODEL_CONFIG_DRIFT and drift[1] == 409
        and FAKE_API_KEY not in good["fingerprint"]
        and not results["unit_resolve_frozen_model"]["credentialsInErrors"]
    ):
        failures.append("A: resolve_frozen_model 判定/错误码/凭证边界不符")


# --------------------------------------------------------------------------- 真实装配


class Domains:
    """真 app + 四个域的受控替身服务 + 共享任务引擎/注册表。"""

    def __init__(self, data_dir: Path) -> None:
        self.settings = make_settings(data_dir)
        self.app = create_app(self.settings)
        # 知识点候选（也用作占住模型名额的 holder）
        self.kn_provider = FakeProvider(["{}"])
        self.kn_resolver = FakeResolver(make_handle(provider=self.kn_provider))
        self.knowledge = build_knowledge_service(
            self.app.state.knowledge,
            asset_store=self.app.state.asset_store,
            file_assets=self.app.state.file_assets,
            evidence=None,
            coordinator=self.app.state.publication_coordinator,
            model_resolver=self.kn_resolver,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.knowledge_service = self.knowledge
        # 题库
        self.qb_provider = FakeProvider([GEN_REPLY])
        self.qb_resolver = FakeResolver(make_handle(provider=self.qb_provider))
        self.qb = build_question_bank_service(
            self.app.state.question_bank,
            self.settings,
            model_resolver=self.qb_resolver,
            knowledge_catalog=self.app.state.knowledge,
            coordinator=self.app.state.publication_coordinator,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.question_bank_service = self.qb
        # 原卷
        self.paper_provider = FakeProvider(['{"items":[]}'])
        self.paper_resolver = FakeResolver(make_handle(provider=self.paper_provider))
        probe = PapersProbe.__new__(PapersProbe)  # 复用其装配，改用同一个 app
        from app.services.papers.service import build_paper_service

        probe.settings = self.settings
        probe.app = self.app
        probe.catalog = self.app.state.teaching
        probe.assets = self.app.state.asset_store
        probe.file_assets = self.app.state.file_assets
        probe.knowledge = self.app.state.knowledge
        from app.repositories.knowledge.points import KnowledgePointRepository, SubjectRepository

        probe.points = KnowledgePointRepository()
        probe.subjects = SubjectRepository()
        probe.resolver = self.paper_resolver
        probe.service = build_paper_service(
            self.app.state.teaching,
            asset_store=self.app.state.asset_store,
            file_assets=self.app.state.file_assets,
            knowledge_catalog=self.app.state.knowledge,
            coordinator=self.app.state.publication_coordinator,
            model_resolver=self.paper_resolver,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.paper_service = probe.service
        self.papers = probe
        _build_executor_registry(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    # ------------------------------------------------------------------ 工具

    def job_view(self, domain: str, job_id: str) -> dict[str, Any]:
        response = self.client.get(
            f"/api/v1/workflow-jobs/{job_id}", params={"domain": domain}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def wait_terminal(self, domain: str, job_id: str, *, timeout: float = 12.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        view = self.job_view(domain, job_id)
        while view["state"] not in TERMINAL and time.monotonic() < deadline:
            time.sleep(0.02)
            view = self.job_view(domain, job_id)
        return view

    def hold_model_slot(self) -> tuple[str, threading.Event]:
        """用知识点候选任务（gated provider）占住共享模型名额。"""
        gate = threading.Event()
        started = threading.Event()
        self.kn_provider.gate = gate
        self.kn_provider.before_call = started.set
        response = self.client.post(
            "/api/v1/knowledge-suggestion-jobs",
            json={
                "modelProfileId": LOCAL_PROFILE,
                "subjectId": "math",
                "materials": [{"id": "m1", "text": "一次函数 y=kx+b 的图象是一条直线。"}],
            },
        )
        assert response.status_code in (200, 201, 202), response.text
        job_id = response.json()["jobId"]
        assert started.wait(10), "holder 未在 10 秒内开始模型调用"
        return job_id, gate

    def db_rows(self, db_path: Path, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in connection.execute(sql, list(params)).fetchall()]
        finally:
            connection.close()

    def count(self, db_path: Path, table: str, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        if where:
            sql += f" WHERE {where}"
        rows = self.db_rows(db_path, sql, params)
        return int(rows[0]["n"]) if rows else -1

    def close(self) -> None:
        self.client.__exit__(None, None, None)


def scenario_paths(results: dict[str, Any], failures: list[str], domains: Domains) -> None:
    client = domains.client

    # ---- 路径 1：question:generate
    print("path1 generate: hold slot", flush=True)
    holder, gate = domains.hold_model_slot()
    try:
        created = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        assert created.status_code == 202, created.text
        job_id = created.json()["jobId"]
        time.sleep(0.2)
        queued = domains.job_view("question", job_id)
        observed_calls_before = len(domains.qb_provider.starts)
        # 同 profile 换成 model-B（真实配置漂移）
        domains.qb_resolver.default = make_handle(
            LOCAL_PROFILE, model_id="model-B", provider=domains.qb_provider
        )
    finally:
        gate.set()
        domains.kn_provider.gate = None
        domains.kn_provider.before_call = None
    final = domains.wait_terminal("question", job_id)
    domains.wait_terminal("knowledge", holder)
    qb_db = domains.settings.question_bank_root / "question-bank.sqlite3"
    results["path_generate"] = {
        "stateWhileWaitingSlot": queued["state"],
        "terminalState": final["state"],
        "errorCode": (final.get("error") or {}).get("code"),
        "providerCalls": len(domains.qb_provider.starts) - observed_calls_before,
        "imports": domains.count(qb_db, "question_imports"),
        "provenance": domains.count(qb_db, "question_import_provenance"),
    }
    if not (
        queued["state"] in ("queued", "running")
        and final["state"] == "failed"
        and (final.get("error") or {}).get("code") == MODEL_CONFIG_DRIFT
        and len(domains.qb_provider.starts) == observed_calls_before
        and results["path_generate"]["imports"] == 0
        and results["path_generate"]["provenance"] == 0
    ):
        failures.append("B1: question:generate 漂移未被拒或发生了调用/发布")

    # ---- 路径 2：question:organize（整理恢复路径：先失败落库，再 retry 时配置已漂移）
    print("path2 organize: fail then retry after drift", flush=True)
    import_response = client.post(
        "/api/v1/question-imports",
        files={"file": ("probe.md", IMPORT_DOC.encode("utf-8"), "text/markdown")},
        data={"subjectId": "math", "gradeId": "grade-7"},
    )
    assert import_response.status_code == 201, import_response.text
    detail = import_response.json()
    draft_id = detail["drafts"][0]["draftId"]
    domains.qb_resolver.default = make_handle(provider=domains.qb_provider)
    domains.qb_provider.replies = ["NOT JSON"]
    organized = client.post(
        f"/api/v1/question-imports/{detail['importId']}/organize",
        json={"draftIds": [draft_id], "includeUnassigned": False,
              "modelProfileId": LOCAL_PROFILE},
    )
    assert organized.status_code == 200, organized.text
    organize_job = organized.json()["jobId"]
    assert organized.json()["state"] == "failed", organized.text
    # 恢复前：同 profile 已换成 model-B（真实配置漂移），用新的观察 provider 计数
    observed = FakeProvider([GEN_REPLY])
    domains.qb_resolver.default = make_handle(
        LOCAL_PROFILE, model_id="model-B", provider=observed
    )
    observed_calls_before = len(observed.starts)
    checkpoint_before = dict((domains.qb.job_record(organize_job).checkpoint or {}))
    dispatched = client.post(
        f"/api/v1/workflow-jobs/{organize_job}/retry", json={"domain": "question"}
    )
    assert dispatched.status_code == 200, dispatched.text
    not_yet = domains.job_view("question", organize_job)
    final = domains.wait_terminal("question", organize_job)
    record = domains.qb.job_record(organize_job)
    suggestion_count = domains.count(
        qb_db, "question_suggestions", "organization_job_id = ?", (organize_job,)
    )
    results["path_organize"] = {
        "stateBeforeRetry": not_yet["state"],
        "terminalState": final["state"],
        "errorCode": (final.get("error") or {}).get("code"),
        "providerCalls": len(observed.calls) - observed_calls_before,
        "suggestions": suggestion_count,
        "checkpointNextBatchBefore": checkpoint_before.get("nextBatchIndex", "n/a"),
        "checkpointNextBatchAfter": (record.checkpoint or {}).get("nextBatchIndex", "n/a"),
        "frozenFingerprintKept": bool((record.model_snapshot or {}).get("fingerprint")),
    }
    if not (
        final["state"] == "failed"
        and (final.get("error") or {}).get("code") == MODEL_CONFIG_DRIFT
        and len(observed.starts) == observed_calls_before
        and suggestion_count == 0
    ):
        failures.append("B2: question:organize 恢复漂移未被拒或发生了调用/建议写入")

    # ---- 路径 3：teaching:paper_mapping
    print("path3 paper_mapping: hold slot", flush=True)
    from tests.papers_support import build_paper_docx

    domains.paper_resolver.default = make_handle(provider=domains.paper_provider)
    imported = client.post(
        "/api/v1/paper-imports",
        files={
            "file": (
                "rv04.docx",
                Path(build_paper_docx(V.PROBE_TMP / "rv04.docx")).read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"subjectId": "math", "title": "RV04 探针卷"},
    )
    assert imported.status_code == 201, imported.text
    paper_id = imported.json()["paper"]["paperId"]
    revision = client.get(f"/api/v1/papers/{paper_id}").json()["revision"]
    holder, gate = domains.hold_model_slot()
    try:
        proposal = client.post(
            f"/api/v1/papers/{paper_id}/knowledge-proposals",
            json={"modelProfileId": LOCAL_PROFILE, "expectedRevision": revision},
        )
        assert proposal.status_code in (200, 202), proposal.text
        proposal_job = proposal.json()["jobId"]
        time.sleep(0.2)
        queued = domains.job_view("teaching", proposal_job)
        observed_calls_before = len(domains.paper_provider.starts)
        domains.paper_resolver.default = make_handle(
            LOCAL_PROFILE, model_id="model-B", provider=domains.paper_provider
        )
    finally:
        gate.set()
        domains.kn_provider.gate = None
        domains.kn_provider.before_call = None
    final = domains.wait_terminal("teaching", proposal_job)
    domains.wait_terminal("knowledge", holder)
    proposal_count = domains.count(
        domains.settings.teaching_root / "teaching.sqlite3", "ai_proposals"
    )
    results["path_paper_mapping"] = {
        "stateWhileWaitingSlot": queued["state"],
        "terminalState": final["state"],
        "errorCode": (final.get("error") or {}).get("code"),
        "providerCalls": len(domains.paper_provider.starts) - observed_calls_before,
        "proposals": proposal_count,
    }
    if not (
        queued["state"] in ("queued", "running")
        and final["state"] == "failed"
        and (final.get("error") or {}).get("code") == MODEL_CONFIG_DRIFT
        and len(domains.paper_provider.starts) == observed_calls_before
        and proposal_count == 0
    ):
        failures.append("B3: teaching:paper_mapping 漂移未被拒或发生了调用/建议写入")

    # ---- 路径 4：knowledge:suggestion（漂移版本；holder 用同一模块的冻结行）
    print("path4 knowledge: hold slot", flush=True)
    domains.kn_resolver.default = make_handle(provider=domains.kn_provider)
    domestic_gate = threading.Event()
    domains.kn_provider.gate = domestic_gate
    holder2_response = client.post(
        "/api/v1/knowledge-suggestion-jobs",
        json={
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": "physics",
            "materials": [{"id": "m2", "text": "牛顿第一定律：物体在不受外力时保持静止或匀速直线运动。"}],
        },
    )
    holder2 = holder2_response.json()["jobId"]
    deadline = time.monotonic() + 8
    while len(domains.kn_provider.calls) < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    # 目标：第二条候选任务（排队），排队期间换 model-B
    target_response = client.post(
        "/api/v1/knowledge-suggestion-jobs",
        json={
            "modelProfileId": LOCAL_PROFILE,
            "subjectId": "chemistry",
            "materials": [{"id": "m3", "text": "水的化学式是 H2O。"}],
        },
    )
    target_job = target_response.json()["jobId"]
    time.sleep(0.2)
    queued = domains.job_view("knowledge", target_job)
    calls_before = len(domains.kn_provider.starts)
    domains.kn_resolver.default = make_handle(
        LOCAL_PROFILE, model_id="model-B", provider=domains.kn_provider
    )
    domestic_gate.set()
    domains.kn_provider.gate = None
    final = domains.wait_terminal("knowledge", target_job)
    domains.wait_terminal("knowledge", holder2)
    kn_db = domains.settings.knowledge_root / "knowledge.sqlite3"
    results["path_knowledge_suggestion"] = {
        "stateWhileWaitingSlot": queued["state"],
        "terminalState": final["state"],
        "errorCode": (final.get("error") or {}).get("code"),
        "providerCallsForTarget": len(domains.kn_provider.starts) - calls_before,
        "imports": domains.count(kn_db, "knowledge_imports"),
    }
    if not (
        queued["state"] in ("queued", "running")
        and final["state"] == "failed"
        and (final.get("error") or {}).get("code") == MODEL_CONFIG_DRIFT
        and len(domains.kn_provider.starts) - calls_before == 0
    ):
        failures.append("B4: knowledge:suggestion 漂移未被拒或发生了调用")

    print("path C legacy missing fingerprint", flush=True)
    # ---- C：旧行缺指纹 → MODEL_FINGERPRINT_MISSING（经公共 retry 调度）
    store = domains.qb.job_engine.store("question")
    from app.services.question_bank import generation as generation_module

    legacy = store.create(
        kind="generate",
        frozen_input=generation_module.build_frozen_input(
            model_profile_id=LOCAL_PROFILE,
            subject_id="math",
            knowledge=[],
            question_types=["short_answer"],
            difficulty="medium",
            count=1,
            instructions="",
            materials=[],
            owner_id=domains.qb.owner_id,
        ),
        model_snapshot={"profileId": LOCAL_PROFILE},
    )
    calls_before_legacy = len(domains.qb_provider.starts)
    dispatched = client.post(
        f"/api/v1/workflow-jobs/{legacy.job_id}/retry", json={"domain": "question"}
    )
    assert dispatched.status_code == 200, dispatched.text
    legacy_final = domains.wait_terminal("question", legacy.job_id)
    results["legacy_missing_fingerprint"] = {
        "dispatchStatus": dispatched.status_code,
        "terminalState": legacy_final["state"],
        "errorCode": (legacy_final.get("error") or {}).get("code"),
        "providerCallsDelta": len(domains.qb_provider.starts) - calls_before_legacy,
    }
    if not (
        legacy_final["state"] == "failed"
        and (legacy_final.get("error") or {}).get("code") == MODEL_FINGERPRINT_MISSING
        and len(domains.qb_provider.starts) == calls_before_legacy
    ):
        failures.append("C: 旧行缺指纹未被拒或发生了调用")

    # ---- D：凭证不落库/不出现在视图
    leaked: list[dict[str, Any]] = []
    for db, table_sql in (
        (qb_db, "SELECT model_snapshot_json FROM question_jobs"),
        (domains.settings.teaching_root / "teaching.sqlite3",
         "SELECT model_snapshot_json FROM workflow_jobs"),
        (kn_db, "SELECT model_snapshot_json FROM knowledge_jobs"),
    ):
        for row in domains.db_rows(db, table_sql):
            blob = row.get("model_snapshot_json") or ""
            if FAKE_API_KEY in blob:
                leaked.append({"db": str(db), "row": blob[:200]})
    views = [
        domains.job_view("question", job_id),
        domains.job_view("teaching", proposal_job),
        domains.job_view("knowledge", target_job),
    ]
    results["credentials_boundary"] = {
        "leakedRows": leaked,
        "viewBlobHasKey": any(FAKE_API_KEY in json.dumps(view) for view in views),
        "fingerprintNotKey": FAKE_API_KEY
        not in json.dumps([view.get("jobId") for view in views]),
    }
    if leaked or results["credentials_boundary"]["viewBlobHasKey"]:
        failures.append("D: 凭证出现在快照或任务视图")


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    unit_checks(results, failures)
    domains = Domains(V.PROBE_TMP / "rv04")
    try:
        scenario_paths(results, failures, domains)
    finally:
        domains.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p04_rv04_drift", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in (
        "unit_resolve_frozen_model",
        "path_generate",
        "path_organize",
        "path_paper_mapping",
        "path_knowledge_suggestion",
        "legacy_missing_fingerprint",
        "credentials_boundary",
    ):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:420])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
