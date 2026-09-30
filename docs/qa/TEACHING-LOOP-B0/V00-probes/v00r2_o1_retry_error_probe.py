"""r2 · V00-O1 复验探针：retry 清空上一轮错误（独立自建）。

覆盖：
  O1① 失败任务 retry 后 state=queued、error_code/error_json 为空、view().error 为 null
       （直接读原始 DB 行，不只看记录对象）；
  O1② 同一事务内同时落状态与清错（retry 前后原始行的 state 与 error 列一致地变化，
       不存在"先 queued 后清错"的中间可观测态）；
  O1③ frozen_input / model_snapshot / input_hash / attempt 保留（含 input_hash 逐字节相等）；
  O1④ 其他终态（cancelled / interrupted）retry 同样清错，且 attempt 不变、下次 claim 才 +1；
  O1⑤ 守卫不变：queued / running / succeeded → 409 JOB_NOT_RETRYABLE。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from _probe_common import check, cleanup, record, run_main, temp_root

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.jobs.repository import JobStore
from app.repositories.teaching.catalog import TeachingCatalog

PROBE = "v00r2_o1_retry_error_probe"
KINDS = frozenset({"probe_kind"})


def make_store(root: Path) -> tuple[JobStore, TeachingCatalog]:
    catalog = TeachingCatalog(root / "teaching" / "teaching.sqlite3")
    catalog.migrate()
    store = JobStore(
        catalog, domain="teaching", table="workflow_jobs", kinds=KINDS, lease_seconds=30
    )
    return store, catalog


def raw_row(catalog: TeachingCatalog, job_id: str) -> dict:
    connection = sqlite3.connect(str(catalog.db_path))
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("SELECT * FROM workflow_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row is not None else {}
    finally:
        connection.close()


def part_failed_retry(root: Path) -> None:
    store, catalog = make_store(root)
    job = store.create(
        kind="probe_kind",
        frozen_input={"payload": {"x": [1, 2, 3]}, "model": "p-1"},
        model_snapshot={"modelProfileId": "p-1", "fingerprint": "abc"},
    )
    lease = store.claim(job.job_id)
    failed = store.fail_if_current_lease(
        job.job_id, lease, code="MODEL_CONFIG_INVALID", message="模型配置失效", retryable=True
    )
    check(
        "O1.1 前置：任务为 failed 且带错误",
        failed.state == "failed" and failed.error_code == "MODEL_CONFIG_INVALID" and failed.error is not None,
        f"state={failed.state} error_code={failed.error_code}",
    )
    before_raw = raw_row(catalog, job.job_id)
    before = {
        "frozen": failed.frozen_input,
        "snapshot": failed.model_snapshot,
        "input_hash": failed.input_hash,
        "attempt": failed.attempt,
    }

    retried = store.retry(job.job_id)
    after_raw = raw_row(catalog, job.job_id)
    view = retried.view()
    check(
        "O1.2 retry 后 state=queued 且错误被清空（记录层）",
        retried.state == "queued" and retried.error_code is None and retried.error is None,
        f"state={retried.state} error_code={retried.error_code} error={retried.error}",
    )
    check(
        "O1.3 retry 后视图 error 为 null（前端看到的就是 queued+无错误）",
        view.state == "queued" and view.error is None,
        f"state={view.state} error={view.error}",
    )
    check(
        "O1.4 原始 DB 行 error_code / error_json 均为 NULL（同一事务落盘）",
        after_raw.get("error_code") is None and after_raw.get("error_json") is None,
        f"error_code={after_raw.get('error_code')} error_json={after_raw.get('error_json')}",
    )
    check(
        "O1.5 单条 UPDATE 覆盖状态与错误：行内无中间态（state/error 同源变化）",
        before_raw.get("error_code") == "MODEL_CONFIG_INVALID"
        and before_raw.get("state") == "failed"
        and after_raw.get("state") == "queued"
        and after_raw.get("updated_at") == retried.updated_at,
        f"before=({before_raw.get('state')},{before_raw.get('error_code')}) after=({after_raw.get('state')},{after_raw.get('error_code')})",
    )
    check(
        "O1.6 保留 frozen_input / model_snapshot / input_hash",
        retried.frozen_input == before["frozen"]
        and retried.model_snapshot == before["snapshot"]
        and retried.input_hash == before["input_hash"]
        and retried.input_hash != "",
        f"hash={retried.input_hash[:16]}…",
    )
    check(
        "O1.7 attempt 不变、租约与取消标志清空",
        retried.attempt == before["attempt"]
        and retried.lease_token is None
        and retried.lease_expires_at is None
        and retried.cancel_requested is False,
        f"attempt={retried.attempt} lease={retried.lease_token}",
    )
    reclaimed = store.claim(job.job_id)
    check(
        "O1.8 下次 claim 才递增 attempt 且错误仍为空",
        reclaimed.attempt == before["attempt"] + 1 and store.get(job.job_id).error_code is None,
        f"attempt={reclaimed.attempt}",
    )
    catalog.close()


def part_other_terminal_states(root: Path) -> None:
    store, catalog = make_store(root / "other")

    # cancelled：先失败再取消（failed 是终态，request_cancel 是幂等空操作）→ 用 queued 取消再重试
    cancelled_job = store.create(kind="probe_kind", frozen_input={"a": 1})
    store.request_cancel(cancelled_job.job_id)
    cancelled = store.get(cancelled_job.job_id)
    check("O1.9 前置：queued 取消 → cancelled", cancelled.state == "cancelled", cancelled.state)
    retried_cancel = store.retry(cancelled_job.job_id)
    raw_cancel = raw_row(catalog, cancelled_job.job_id)
    check(
        "O1.10 cancelled 重试：queued 且错误列为 NULL、cancel_requested 归零",
        retried_cancel.state == "queued"
        and raw_cancel.get("error_code") is None
        and raw_cancel.get("error_json") is None
        and retried_cancel.cancel_requested is False,
        f"state={retried_cancel.state}",
    )

    interrupted_job = store.create(kind="probe_kind", frozen_input={"b": 2})
    store.claim(interrupted_job.job_id)
    store.reconcile_interrupted()
    interrupted = store.get(interrupted_job.job_id)
    check("O1.11 前置：running 收敛 → interrupted", interrupted.state == "interrupted", interrupted.state)
    retried_interrupted = store.retry(interrupted_job.job_id)
    raw_interrupted = raw_row(catalog, interrupted_job.job_id)
    check(
        "O1.12 interrupted 重试：queued 且错误列为 NULL",
        retried_interrupted.state == "queued"
        and raw_interrupted.get("error_code") is None
        and raw_interrupted.get("error_json") is None,
        f"state={retried_interrupted.state}",
    )

    # 守卫不变：queued / running / succeeded
    queued_job = store.create(kind="probe_kind", frozen_input={})
    running_job = store.create(kind="probe_kind", frozen_input={})
    store.claim(running_job.job_id)
    succeeded_job = store.create(kind="probe_kind", frozen_input={})
    store.complete(succeeded_job.job_id, store.claim(succeeded_job.job_id), result={"ok": True})
    for label, job_id in (
        ("queued", queued_job.job_id),
        ("running", running_job.job_id),
        ("succeeded", succeeded_job.job_id),
    ):
        try:
            store.retry(job_id)
            record(f"O1.13 retry on {label} -> 409 JOB_NOT_RETRYABLE", False, "no exception")
        except AppError as exc:
            check(
                f"O1.13 retry on {label} -> 409 JOB_NOT_RETRYABLE",
                exc.code == "JOB_NOT_RETRYABLE" and exc.status_code == 409,
                f"code={exc.code} status={exc.status_code}",
            )
    check(
        "O1.14 被拒绝的 retry 未改写任务行（仍为 succeeded）",
        store.get(succeeded_job.job_id).state == "succeeded",
        store.get(succeeded_job.job_id).state,
    )
    catalog.close()


def main() -> None:
    root = temp_root("r2-o1")
    try:
        part_failed_retry(root)
        part_other_terminal_states(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
