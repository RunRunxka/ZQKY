"""V00 · RV01 探针：公共 retry 真装配调度（自建，不复跑实现者测试）。

场景（全部走 HTTP + 真 JobEngine/JobStore/注册表 + 受控模型替身）：

1. 失败任务 → retry → 新 attempt → 终态 succeeded；
2. 失败任务 → 并发两次 retry → 只执行一次（provider 调用只 +1，attempt 只 +1）；
3. 运行中 retry → 409 JOB_NOT_RETRYABLE（不重复执行）；
4. 仓库 retry 后未调度（模拟入队后调度异常/进程退出）→ 再次 POST retry 补调度；
5. 进程重启后 queued 不自动重放；显式 retry 才执行（新 app/新引擎，同一数据目录）。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p01_rv01_retry.py
退出码 0 = 全部断言通过；1 = 存在失败（首败信息在 JSON/日志）。
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402

from _v00 import AppError, FakeProvider, FakeResolver, make_handle, make_settings  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import _build_executor_registry, create_app  # noqa: E402
from app.services.question_bank.service import build_question_bank_service  # noqa: E402

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
GEN_BODY = {
    "modelProfileId": V.LOCAL_PROFILE,
    "subjectId": "math",
    "knowledgePointIds": [],
    "questionTypes": ["short_answer"],
    "difficulty": "medium",
    "count": 1,
    "materials": [],
}
GOOD_REPLY = (
    '{"questions":[{"type":"short_answer","stemMarkdown":"题干：下列说法正确的是（ ）",'
    '"options":[],"answer":{"choiceKeys":[],"accepted":null,"textMarkdown":"示例答案"},'
    '"explanationMarkdown":"示例解析。","knowledgePointIds":[],"evidenceIds":[],"assetIds":[]}]}'
)


class Upstream:
    """一个数据目录 + 一套可重建的 app/服务/替身（模拟进程生命周期）。"""

    def __init__(self, data_dir: Path, provider: FakeProvider) -> None:
        self.settings = make_settings(data_dir)
        self.app = create_app(self.settings)
        self.provider = provider
        self.resolver = FakeResolver(make_handle(provider=provider))
        self.service = build_question_bank_service(
            self.app.state.question_bank,
            self.settings,
            model_resolver=self.resolver,
            knowledge_catalog=self.app.state.knowledge,
            coordinator=self.app.state.publication_coordinator,
            job_engine=self.app.state.job_engine,
        )
        self.app.state.question_bank_service = self.service
        _build_executor_registry(self.app)
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)


def job_view(client: TestClient, job_id: str) -> dict:
    response = client.get(f"/api/v1/workflow-jobs/{job_id}", params={"domain": "question"})
    assert response.status_code == 200, response.text
    return response.json()


def wait_terminal(client: TestClient, job_id: str, *, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    view = job_view(client, job_id)
    while view["state"] not in TERMINAL and time.monotonic() < deadline:
        time.sleep(0.02)
        view = job_view(client, job_id)
    assert view["state"] in TERMINAL, f"未达终态：{view}"
    return view


def retry(client: TestClient, job_id: str):
    return client.post(f"/api/v1/workflow-jobs/{job_id}/retry", json={"domain": "question"})


def main() -> int:
    results: dict[str, object] = {}
    failures: list[str] = []
    provider = FakeProvider(["NOT JSON"])
    upstream = Upstream(V.PROBE_TMP / "rv01", provider)
    try:
        client = upstream.client

        # ---- 场景 1：失败 → retry → 新 attempt → 终态 succeeded
        created = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        assert created.status_code == 202, created.text
        job_id = created.json()["jobId"]
        failed = wait_terminal(client, job_id)
        calls_after_fail = len(provider.calls)
        provider.replies = [GOOD_REPLY]
        receipt = retry(client, job_id)
        receipt_body = receipt.json()
        settled = wait_terminal(client, job_id)
        results["retry_to_terminal"] = {
            "failedState": failed["state"],
            "failedErrorCode": failed.get("errorCode"),
            "retryStatus": receipt.status_code,
            "receiptState": receipt_body.get("state"),
            "receiptAttempt": receipt_body.get("attempt"),
            "terminalState": settled["state"],
            "terminalAttempt": settled["attempt"],
            "providerCallsAfterFail": calls_after_fail,
            "providerCallsAfterRetry": len(provider.calls),
        }
        if not (
            failed["state"] == "failed"
            and receipt.status_code == 200
            and settled["state"] == "succeeded"
            and settled["attempt"] == failed["attempt"] + 1
            and len(provider.calls) == calls_after_fail + 1
        ):
            failures.append("scenario1: retry 未产生新 attempt 的终态成功")

        # ---- 场景 4：仓库 retry 后未调度（模拟入队后调度异常）→ POST retry 补调度
        store = upstream.service.job_engine.store("question")
        provider.replies = ["NOT JSON"]
        created4 = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        job4 = created4.json()["jobId"]
        failed4 = wait_terminal(client, job4)
        assert failed4["state"] == "failed", failed4["state"]
        store.retry(job4)  # 直接仓库重排队：queued 但没有执行器调度
        job_id = job4
        queued_view = job_view(client, job_id)
        provider.replies = [GOOD_REPLY]
        calls_before_recover = len(provider.calls)
        recovered = retry(client, job_id)
        recovered_settled = wait_terminal(client, job_id)
        results["queued_reschedule"] = {
            "stateAfterStoreRetry": queued_view["state"],
            "attemptAfterStoreRetry": queued_view["attempt"],
            "retryStatus": recovered.status_code,
            "terminalState": recovered_settled["state"],
            "terminalAttempt": recovered_settled["attempt"],
            "callsBefore": calls_before_recover,
            "callsAfter": len(provider.calls),
        }
        if not (
            queued_view["state"] == "queued"
            and recovered.status_code == 200
            and recovered_settled["state"] == "succeeded"
            and len(provider.calls) == calls_before_recover + 1
        ):
            failures.append("scenario4: queued 未调度状态再次 retry 未补调度")

        # ---- 场景 3：running → 409
        gate = threading.Event()
        provider.gate = gate
        provider.replies = [GOOD_REPLY, GOOD_REPLY]
        running_created = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        running_id = running_created.json()["jobId"]
        deadline = time.monotonic() + 5
        while len(provider.calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        running_view = job_view(client, running_id)
        during = retry(client, running_id)
        results["running_retry_409"] = {
            "stateWhileGated": running_view["state"],
            "retryStatus": during.status_code,
            "retryCode": during.json().get("code") if during.status_code != 200 else None,
        }
        if not (running_view["state"] == "running" and during.status_code == 409):
            failures.append("scenario3: running 状态 retry 未返回 409")
        gate.set()
        provider.gate = None
        wait_terminal(client, running_id)

        # ---- 场景 2：并发双 retry 只执行一次（两条都落在 queued，最危险的重复点击窗口）
        provider.replies = ["NOT JSON"]
        created2 = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        job2 = created2.json()["jobId"]
        assert wait_terminal(client, job2)["state"] == "failed"
        store.retry(job2)  # 先置 queued（未调度）：两条 retry 都必须看到 queued
        provider.replies = [GOOD_REPLY]
        calls_before_race = len(provider.calls)
        attempts_before = job_view(client, job2)["attempt"]
        codes: list[int] = []

        def _fire() -> None:
            response = retry(client, job2)
            codes.append(response.status_code)

        threads = [threading.Thread(target=_fire) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        settled2 = wait_terminal(client, job2)
        results["concurrent_retry"] = {
            "statusCodes": sorted(codes),
            # 两种合法结果：200+409（第二条到达时已 running，按原契约拒绝）
            # 或 200+200（第二条仍看到 queued，注册表 is_tracking 幂等返回当前视图）
            "secondRequestPath": (
                "rejected-running" if 409 in codes else "idempotent-queued"
            ),
            "attemptBefore": attempts_before,
            "attemptAfter": settled2["attempt"],
            "terminalState": settled2["state"],
            "providerCallsBefore": calls_before_race,
            "providerCallsAfter": len(provider.calls),
        }
        if not (
            200 in codes
            and all(code in (200, 409) for code in codes)
            and settled2["attempt"] == attempts_before + 1
            and settled2["state"] == "succeeded"
            and len(provider.calls) == calls_before_race + 1
        ):
            failures.append("scenario2: 并发 retry 未做到只执行一次")

        # ---- 场景 2c：注册表调度幂等（queued + 已调度窗口内重复 schedule 不重复执行）
        provider.replies = ["NOT JSON"]
        created2c = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        job2c = created2c.json()["jobId"]
        assert wait_terminal(client, job2c)["state"] == "failed"
        store.retry(job2c)  # queued、未调度
        provider.replies = [GOOD_REPLY]
        calls_before_idem = len(provider.calls)
        engine = upstream.service.job_engine
        registry = upstream.app.state.job_executors
        record2c = store.get(job2c)

        def _schedule_twice() -> tuple[bool, bool]:
            # 必须在应用事件循环线程内调用（引擎 tracked 表与 loop 绑定）
            return (
                registry.schedule(engine, record2c),
                registry.schedule(engine, record2c),
            )

        portal = getattr(client, "portal", None)
        assert portal is not None, "TestClient 未暴露 portal（无法在应用循环内调度）"
        first_schedule, second_schedule = portal.call(_schedule_twice)
        settled2c = wait_terminal(client, job2c)
        results["registry_idempotent_schedule"] = {
            "firstSchedule": first_schedule,
            "secondSchedule": second_schedule,
            "terminalState": settled2c["state"],
            "terminalAttempt": settled2c["attempt"],
            "providerCallsDelta": len(provider.calls) - calls_before_idem,
        }
        if not (
            first_schedule is True
            and second_schedule is True
            and settled2c["state"] == "succeeded"
            and len(provider.calls) - calls_before_idem == 1
        ):
            failures.append("scenario2c: 注册表重复 schedule 产生了第二次执行")

        # 场景 2b：重复点击（第一次已开始执行）→ 409，且不再执行第二次
        provider.replies = ["NOT JSON"]
        created2b = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        job2b = created2b.json()["jobId"]
        assert wait_terminal(client, job2b)["state"] == "failed"
        provider.replies = [GOOD_REPLY]
        calls_before_click = len(provider.calls)
        first = retry(client, job2b)
        second = retry(client, job2b)
        settled2b = wait_terminal(client, job2b)
        results["repeat_click"] = {
            "firstStatus": first.status_code,
            "secondStatus": second.status_code,
            "terminalState": settled2b["state"],
            "attemptAfter": settled2b["attempt"],
            "providerCallsDelta": len(provider.calls) - calls_before_click,
        }
        if not (
            first.status_code == 200
            and second.status_code == 409
            and settled2b["state"] == "succeeded"
            and len(provider.calls) - calls_before_click == 1
        ):
            failures.append("scenario2b: 重复点击未按 409 拒绝或发生重复执行")

        # ---- 场景 5：重启后 queued 不自动重放；显式 retry 才执行
        provider.replies = ["NOT JSON"]
        created5 = client.post("/api/v1/question-generation-jobs", json=GEN_BODY)
        job5 = created5.json()["jobId"]
        assert wait_terminal(client, job5)["state"] == "failed"
        store.retry(job5)  # 留下 queued（模拟重启前已入队但未调度）
        upstream.close()
        restarted_provider = FakeProvider([GOOD_REPLY])
        restarted = Upstream(V.PROBE_TMP / "rv01", restarted_provider)
        try:
            after_restart = job_view(restarted.client, job5)
            time.sleep(0.3)  # 给"自动重放"留出窗口：不应发生
            still_queued = job_view(restarted.client, job5)
            explicit = retry(restarted.client, job5)
            final = wait_terminal(restarted.client, job5)
            results["restart_queued"] = {
                "stateAfterRestart": after_restart["state"],
                "stateAfterWait": still_queued["state"],
                "retryStatus": explicit.status_code,
                "terminalState": final["state"],
                "terminalAttempt": final["attempt"],
                "providerCalls": len(restarted_provider.calls),
            }
            if not (
                after_restart["state"] == "queued"
                and still_queued["state"] == "queued"
                and explicit.status_code == 200
                and final["state"] == "succeeded"
                and len(restarted_provider.calls) == 1
            ):
                failures.append("scenario5: 重启后 queued 语义不符（自动重放或显式 retry 未执行）")
        finally:
            restarted.close()
        upstream = None
    finally:
        if upstream is not None:
            upstream.close()

    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p01_rv01_retry", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("retry_to_terminal", "queued_reschedule", "running_retry_409",
                "concurrent_retry", "registry_idempotent_schedule", "repeat_click",
                "restart_queued"):
        print(key, results.get(key))
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
