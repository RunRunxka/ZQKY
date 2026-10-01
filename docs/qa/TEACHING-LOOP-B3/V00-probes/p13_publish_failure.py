"""V00 · 已披露项探针：发布事务失败后的终态收敛（自建故障注入，三域一致）。

背景（B2 已披露）：原卷 publish 抛错后任务停在 `running`。G0 修复要求在公共引擎里用
**本次执行开始时的原 JobLease** 在新短事务收敛终态：AppError → `failed`（保留错误码/文案）、
非 AppError → `failed` + `JOB_FAILED` 固定文案、取消优先 → `cancelled`、失权 → 零写入；
业务写入随发布事务整体回滚（无半批），不留下永久 running。

断言（三个域各跑一遍 teaching/question/knowledge 的 JobStore 实现）：
  A. publish 抛 AppError：state=failed + error_code 保留；publish 内的业务写入被回滚；
  B. publish 抛非 AppError：state=failed + JOB_FAILED + 固定文案；业务写入回滚；
  C. 正常 publish：succeeded + 业务写入保留（控制组）；
  D. 取消优先：cancel_requested=1 且租约仍归本次执行者 → fail_if_current_lease 收敛
     `cancelled`（而不是 failed）；
  E. 失权零写入：用过期/被接管的旧租约调 fail_if_current_lease → 不改状态、
     不覆盖新持有者；
  F. 收敛后无永久 running：finished_at 非空、lease 清空。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p13_publish_failure.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.repositories.jobs.repository import JobLease, JobStore  # noqa: E402
from app.repositories.knowledge.catalog import KnowledgeCatalog  # noqa: E402
from app.repositories.question_bank.catalog import QuestionBankCatalog  # noqa: E402
from app.repositories.teaching.catalog import TeachingCatalog  # noqa: E402
from app.services.jobs.engine import (  # noqa: E402
    JOB_FAILED,
    PUBLISH_FAILURE_MESSAGE,
    FrozenJob,
    JobContext,
    JobEngine,
    JobOutcome,
)

PROBE_TABLE = "v00_publish_probe"


def catalogs_for(data_dir: Path) -> list[tuple[str, Any, str]]:
    settings = Settings(
        host="127.0.0.1", port=8001, allowed_origins=frozenset(), env="test", data_dir=data_dir
    )
    teaching = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
    teaching.migrate()
    question = QuestionBankCatalog(settings.question_bank_root / "question-bank.sqlite3")
    question.migrate()
    knowledge = KnowledgeCatalog(settings.knowledge_root / "knowledge.sqlite3")
    knowledge.migrate()
    return [
        ("teaching", teaching, "workflow_jobs"),
        ("question", question, "question_jobs"),
        ("knowledge", knowledge, "knowledge_jobs"),
    ]


def prepare_table(catalog: Any) -> None:
    with catalog.write_transaction() as conn:
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE} (id TEXT PRIMARY KEY NOT NULL, note TEXT)"
        )


def probe_rows(catalog: Any) -> list[dict[str, Any]]:
    connection = sqlite3.connect(str(catalog.db_path))
    connection.row_factory = sqlite3.Row
    try:
        try:
            return [
                dict(row)
                for row in connection.execute(f"SELECT * FROM {PROBE_TABLE}").fetchall()
            ]
        except sqlite3.OperationalError:
            return []
    finally:
        connection.close()


async def run_domain(domain: str, catalog: Any, table: str) -> dict[str, Any]:
    store = JobStore(catalog, domain=domain, table=table, kinds=frozenset({"v00_probe"}))
    engine = JobEngine({domain: store}, heavy_limit=2, model_limit=1)
    prepare_table(catalog)
    out: dict[str, Any] = {}

    def make_executor(publish):
        async def executor(frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
            return JobOutcome(result={"job": frozen.job_id}, publish=publish)

        return executor

    async def run_with(publish):
        record = store.create(kind="v00_probe", frozen_input={}, model_snapshot={})
        return await engine.run_job(domain, record.job_id, make_executor(publish))

    # A. AppError 发布失败
    def publish_app_error(conn):
        conn.execute(f"INSERT INTO {PROBE_TABLE} (id, note) VALUES ('a', '半批')")
        raise AppError("业务写入失败（探针）", code="V00_PUBLISH_FAIL", status_code=422)

    record = await run_with(publish_app_error)
    out["app_error_publish"] = {
        "state": record.state,
        "errorCode": record.error_code,
        "finishedAt": record.finished_at,
        "leaseCleared": record.lease_token is None,
        "probeRows": probe_rows(catalog),
    }

    # B. 非 AppError 发布失败
    def publish_internal_error(conn):
        conn.execute(f"INSERT INTO {PROBE_TABLE} (id, note) VALUES ('b', '半批')")
        raise RuntimeError("internal boom")

    record_b = await run_with(publish_internal_error)
    out["internal_publish"] = {
        "state": record_b.state,
        "errorCode": record_b.error_code,
        "errorMessage": (record_b.error or {}).get("message"),
        "fixedMessage": PUBLISH_FAILURE_MESSAGE,
        "probeRows": probe_rows(catalog),
    }

    # C. 正常发布（控制组）
    def publish_ok(conn):
        conn.execute(f"INSERT INTO {PROBE_TABLE} (id, note) VALUES ('c', '正常')")

    record_c = await run_with(publish_ok)
    out["normal_publish"] = {
        "state": record_c.state,
        "result": record_c.result,
        "probeRows": probe_rows(catalog),
    }

    # D. 取消优先（仓储级：原租约 + cancel_requested=1）
    record_d = store.create(kind="v00_probe", frozen_input={}, model_snapshot={})
    lease_d = store.claim(record_d.job_id)
    store.request_cancel(record_d.job_id)
    try:
        store.complete(record_d.job_id, lease_d, result={"ok": True})
        complete_raised = None
    except AppError as exc:  # complete 的取消分支不会抛错；这里仅兜底记录
        complete_raised = exc.code
    after_complete = store.get(record_d.job_id)
    record_d2 = store.create(kind="v00_probe", frozen_input={}, model_snapshot={})
    lease_d2 = store.claim(record_d2.job_id)
    store.request_cancel(record_d2.job_id)
    cancelled = store.fail_if_current_lease(
        record_d2.job_id, lease_d2, code="V00_SHOULD_NOT_APPEAR", message="x"
    )
    out["cancel_priority"] = {
        "completeCancelRaised": complete_raised,
        "stateAfterComplete": after_complete.state,
        "stateAfterFailIfCurrentLease": cancelled.state,
        "errorCode": cancelled.error_code,
    }

    # E. 失权零写入（过期旧租约）
    record_e = store.create(kind="v00_probe", frozen_input={}, model_snapshot={})
    lease_e = store.claim(record_e.job_id)
    connection = sqlite3.connect(str(catalog.db_path))
    try:
        with connection:
            connection.execute(
                f"UPDATE {table} SET lease_expires_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00+00:00", record_e.job_id),
            )
    finally:
        connection.close()
    lease_e2 = store.claim(record_e.job_id)  # 接管：attempt+1、新 token
    stale_result = store.fail_if_current_lease(
        record_e.job_id, lease_e, code="V00_STALE", message="旧租约迟到"
    )
    current = store.get(record_e.job_id)
    out["lost_lease_zero_write"] = {
        "newAttempt": lease_e2.attempt,
        "staleCallState": stale_result.state,
        "currentState": current.state,
        "errorCode": current.error_code,
        "attemptKept": current.attempt == lease_e2.attempt,
    }

    await engine.shutdown()
    out["no_running_left"] = store.get(record.job_id).state != "running"
    return out


def check(out: dict[str, Any], failures: list[str], domain: str) -> None:
    a = out["app_error_publish"]
    if not (
        a["state"] == "failed"
        and a["errorCode"] == "V00_PUBLISH_FAIL"
        and a["finishedAt"]
        and a["leaseCleared"]
        and a["probeRows"] == []
    ):
        failures.append(f"{domain}: A publish(AppError) 未收敛或半批未回滚")
    b = out["internal_publish"]
    if not (
        b["state"] == "failed"
        and b["errorCode"] == JOB_FAILED
        and b["fixedMessage"] in (b["errorMessage"] or "")
        and b["probeRows"] == []
    ):
        failures.append(f"{domain}: B publish(内部错误) 未收敛或半批未回滚")
    c = out["normal_publish"]
    if not (c["state"] == "succeeded" and [row["id"] for row in c["probeRows"]] == ["c"]):
        failures.append(f"{domain}: C 正常发布被误伤")
    d = out["cancel_priority"]
    if not (
        d["stateAfterComplete"] == "cancelled"
        and d["stateAfterFailIfCurrentLease"] == "cancelled"
        and d["errorCode"] is None
    ):
        failures.append(f"{domain}: D 取消优先语义不符")
    e = out["lost_lease_zero_write"]
    if not (
        e["newAttempt"] == 2
        and e["currentState"] == "running"
        and e["errorCode"] is None
        and e["attemptKept"]
    ):
        failures.append(f"{domain}: E 失权旧租约发生了写入")
    if not out["no_running_left"]:
        failures.append(f"{domain}: F 存在永久 running")


async def main_async() -> tuple[dict[str, Any], list[str]]:
    results: dict[str, Any] = {}
    failures: list[str] = []
    for domain, catalog, table in catalogs_for(V.PROBE_TMP / "publish_failure"):
        out = await run_domain(domain, catalog, table)
        results[domain] = out
        check(out, failures, domain)
    return results, failures


def main() -> int:
    results, failures = asyncio.run(main_async())
    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p13_publish_failure", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for domain in ("teaching", "question", "knowledge"):
        print(domain, json.dumps(results.get(domain), ensure_ascii=False)[:700])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
