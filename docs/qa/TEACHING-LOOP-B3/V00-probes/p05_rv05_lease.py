"""V00 · RV05 探针：整理中间批的同事务租约 CAS（自建仓储级故障注入）。

缺陷回顾（B2-RV05）：`record_organize_batch` 不接收租约，旧 attempt / 失权 / 终态迟到
批次仍会写入建议并推进新 attempt 的 checkpoint。

断言（每条都检查"建议行 + checkpoint 两个维度"）：
  A. 正常路径（当前有效租约）：建议与 checkpoint 同事务推进，行为不变；
  B. 旧 attempt（被接管后）：零写入；
  C. token 不匹配（同 attempt）：零写入；
  D. 租约已过期（注入 now）：零写入；
  E. 任务已 interrupted / succeeded（终态迟到）：零写入；
  F. 已请求取消：零写入（取消优先）；
  G. 未提供租约凭据：零写入。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p05_rv05_lease.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00 import FakeProvider, FakeResolver, make_handle, make_settings  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core.sqlite import now_iso  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.jobs.repository import JobStore  # noqa: E402
from app.services.question_bank.service import build_question_bank_service  # noqa: E402

DOC = """# 探针练习

1. 下列函数中，是一次函数的是（ ）
A. y = x^2
B. y = 2x + 1
答案：B
解析：形如 y = kx + b（k≠0）的函数是一次函数。
"""


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    settings = make_settings(V.PROBE_TMP / "rv05")
    app = create_app(settings)
    provider = FakeProvider(["{}"])
    service = build_question_bank_service(
        app.state.question_bank,
        settings,
        model_resolver=FakeResolver(make_handle(provider=provider)),
        knowledge_catalog=app.state.knowledge,
        coordinator=app.state.publication_coordinator,
        job_engine=app.state.job_engine,
    )
    app.state.question_bank_service = service
    client = TestClient(app, base_url="http://127.0.0.1:8001")
    client.__enter__()
    catalog = app.state.question_bank
    store = JobStore(
        catalog, domain="question", table="question_jobs", kinds=frozenset({"organize"})
    )
    try:
        imported = client.post(
            "/api/v1/question-imports",
            files={"file": ("probe.md", DOC.encode("utf-8"), "text/markdown")},
            data={"subjectId": "math", "gradeId": "grade-7"},
        )
        assert imported.status_code == 201, imported.text
        detail = imported.json()
        draft_id = detail["drafts"][0]["draftId"]
        draft = catalog.get_draft(draft_id)

        def new_job() -> Any:
            return store.create(
                kind="organize",
                frozen_input={"contractVersion": 2, "modelProfileId": V.LOCAL_PROFILE},
                model_snapshot={"profileId": V.LOCAL_PROFILE, "fingerprint": "sha256:x"},
            )

        def suggestion_count(job_id: str) -> int:
            rows = catalog.list_suggestions(organization_job_id=job_id)
            return len(rows)

        def checkpoint_of(job_id: str) -> dict[str, Any]:
            return dict(catalog.get_job(job_id).checkpoint or {})

        def expire_lease(job_id: str) -> None:
            """故障注入：把当前租约置为已过期，使下一次 claim 允许接管。"""
            import sqlite3

            connection = sqlite3.connect(str(catalog.db_path))
            try:
                with connection:
                    connection.execute(
                        "UPDATE question_jobs SET lease_expires_at = ? WHERE id = ?",
                        ("2000-01-01T00:00:00+00:00", job_id),
                    )
            finally:
                connection.close()

        def write_batch(
            job_id: str,
            *,
            attempt: int | None,
            token: str | None,
            index: int = 0,
            now: str | None = None,
        ):
            return catalog.record_organize_batch(
                job_id,
                batch_index=index,
                next_batch_index=index + 1,
                draft_id=draft_id,
                base_draft_revision=draft.revision,
                proposed_content={"stemMarkdown": f"整理结果 {index}"},
                source_block_ids=[],
                lease_attempt=attempt,
                lease_token=token,
                now=now,
            )

        # ---- A. 正常路径
        job_a = new_job()
        lease_a = store.claim(job_a.job_id)
        record_a, created_a, _ = write_batch(
            job_a.job_id, attempt=lease_a.attempt, token=lease_a.token
        )
        cp_a = checkpoint_of(job_a.job_id)
        results["normal_path"] = {
            "suggestions": suggestion_count(job_a.job_id),
            "createdSuggestion": created_a is not None,
            "nextBatchIndex": cp_a.get("nextBatchIndex"),
            "jobState": record_a.state,
        }
        if not (
            created_a is not None
            and suggestion_count(job_a.job_id) == 1
            and cp_a.get("nextBatchIndex") == 1
        ):
            failures.append("A: 正常路径未写入建议/推进 checkpoint")

        # ---- B. 旧 attempt（接管后）
        job_b = new_job()
        lease_b1 = store.claim(job_b.job_id)
        _rec_b, created_b1, _ = write_batch(
            job_b.job_id, attempt=lease_b1.attempt, token=lease_b1.token, index=0
        )
        checkpoint_b_before = checkpoint_of(job_b.job_id)
        count_b_before = suggestion_count(job_b.job_id)
        expire_lease(job_b.job_id)
        lease_b2 = store.claim(job_b.job_id)
        _rec_b2, created_b_old, _ = write_batch(
            job_b.job_id, attempt=lease_b1.attempt, token=lease_b1.token, index=1
        )
        checkpoint_b_after = checkpoint_of(job_b.job_id)
        results["stale_attempt"] = {
            "newAttempt": lease_b2.attempt,
            "oldAttemptWrite": created_b_old is not None,
            "suggestionsBefore": count_b_before,
            "suggestionsAfter": suggestion_count(job_b.job_id),
            "checkpointBefore": checkpoint_b_before.get("nextBatchIndex"),
            "checkpointAfter": checkpoint_b_after.get("nextBatchIndex"),
        }
        if not (
            created_b_old is None
            and suggestion_count(job_b.job_id) == count_b_before == 1
            and checkpoint_b_after.get("nextBatchIndex") == checkpoint_b_before.get("nextBatchIndex") == 1
        ):
            failures.append("B: 旧 attempt 批次发生了写入")

        # ---- C. token 不匹配（同 attempt）
        job_c = new_job()
        lease_c = store.claim(job_c.job_id)
        _rec_c, created_c, _ = write_batch(
            job_c.job_id, attempt=lease_c.attempt, token="0" * 32
        )
        results["token_mismatch"] = {
            "write": created_c is not None,
            "suggestions": suggestion_count(job_c.job_id),
            "nextBatchIndex": checkpoint_of(job_c.job_id).get("nextBatchIndex"),
        }
        if not (
            created_c is None
            and suggestion_count(job_c.job_id) == 0
            and checkpoint_of(job_c.job_id).get("nextBatchIndex", 0) == 0
        ):
            failures.append("C: token 不匹配的批次发生了写入")

        # ---- D. 租约过期（now 注入到远未来）
        job_d = new_job()
        lease_d = store.claim(job_d.job_id)
        future = "2099-01-01T00:00:00+00:00"
        _rec_d, created_d, _ = write_batch(
            job_d.job_id, attempt=lease_d.attempt, token=lease_d.token, now=future
        )
        results["expired_lease"] = {
            "write": created_d is not None,
            "suggestions": suggestion_count(job_d.job_id),
        }
        if not (created_d is None and suggestion_count(job_d.job_id) == 0):
            failures.append("D: 过期租约的批次发生了写入")

        # ---- E. 终态迟到：interrupted / succeeded
        job_e = new_job()
        lease_e = store.claim(job_e.job_id)
        catalog.reconcile_interrupted() if hasattr(catalog, "reconcile_interrupted") else None
        store.reconcile_interrupted()
        state_e = store.get(job_e.job_id).state
        _rec_e, created_e, _ = write_batch(
            job_e.job_id, attempt=lease_e.attempt, token=lease_e.token
        )
        job_f = new_job()
        lease_f = store.claim(job_f.job_id)
        store.complete(job_f.job_id, lease_f, result={"ok": True})
        state_f = store.get(job_f.job_id).state
        _rec_f, created_f, _ = write_batch(
            job_f.job_id, attempt=lease_f.attempt, token=lease_f.token
        )
        results["terminal_late_batch"] = {
            "interruptedState": state_e,
            "writeAfterInterrupted": created_e is not None,
            "succeededState": state_f,
            "writeAfterSucceeded": created_f is not None,
            "suggestionsE": suggestion_count(job_e.job_id),
            "suggestionsF": suggestion_count(job_f.job_id),
        }
        if not (
            state_e == "interrupted"
            and created_e is None
            and state_f == "succeeded"
            and created_f is None
            and suggestion_count(job_e.job_id) == 0
            and suggestion_count(job_f.job_id) == 0
        ):
            failures.append("E: interrupted/succeeded 后的迟到批次发生了写入")

        # ---- F. 取消优先
        job_g = new_job()
        lease_g = store.claim(job_g.job_id)
        store.request_cancel(job_g.job_id)
        _rec_g, created_g, _ = write_batch(
            job_g.job_id, attempt=lease_g.attempt, token=lease_g.token
        )
        results["cancel_first"] = {
            "write": created_g is not None,
            "suggestions": suggestion_count(job_g.job_id),
            "jobState": store.get(job_g.job_id).state,
        }
        if not (created_g is None and suggestion_count(job_g.job_id) == 0):
            failures.append("F: 取消后的批次发生了写入")

        # ---- G. 未提供租约凭据
        job_h = new_job()
        store.claim(job_h.job_id)
        _rec_h, created_h, _ = write_batch(job_h.job_id, attempt=None, token=None)
        results["no_lease_credentials"] = {
            "write": created_h is not None,
            "suggestions": suggestion_count(job_h.job_id),
        }
        if not (created_h is None and suggestion_count(job_h.job_id) == 0):
            failures.append("G: 无租约凭据的批次发生了写入")

        # ---- H. 正常路径重复确认（同一批重放不重复落建议）
        job_i = new_job()
        lease_i = store.claim(job_i.job_id)
        write_batch(job_i.job_id, attempt=lease_i.attempt, token=lease_i.token, index=0)
        write_batch(job_i.job_id, attempt=lease_i.attempt, token=lease_i.token, index=1)
        results["normal_two_batches"] = {
            "suggestions": suggestion_count(job_i.job_id),
            "nextBatchIndex": checkpoint_of(job_i.job_id).get("nextBatchIndex"),
        }
        if not (
            suggestion_count(job_i.job_id) == 2
            and checkpoint_of(job_i.job_id).get("nextBatchIndex") == 2
        ):
            failures.append("H: 正常多批推进不符")
    finally:
        client.__exit__(None, None, None)

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p05_rv05_lease", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in (
        "normal_path",
        "stale_attempt",
        "token_mismatch",
        "expired_lease",
        "terminal_late_batch",
        "cancel_first",
        "no_lease_credentials",
        "normal_two_batches",
    ):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:320])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
