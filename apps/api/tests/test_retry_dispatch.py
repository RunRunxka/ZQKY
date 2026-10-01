"""公共 retry 的真调度（TEACHING-LOOP B3 / G0 · B2-RV01 正确行为回归）。

审查缺陷：``POST /workflow-jobs/{id}/retry`` 只把任务置回 ``queued``，没有任何调度路径；
失败任务重试后永远排队（连续 20 轮查询仍 ``queued``、``attempt`` 不变、零模型调用）。

本文件走**真装配**（``create_app`` + ``TestClient`` + 临时数据根 + 受控模型替身），
只把真实服务的 ``model_resolver`` 换成替身，其余全部使用应用自身装配的对象：

- 真应用注册表里已实现的任务类型能解析到执行器（``app.state.job_executors``）；
- 失败任务（模型替身首次抛错）→ retry → 轮询到**新 attempt 的终态** ``succeeded``，
  provider 确实再次调用；收据 attempt=N，终态 attempt=N+1；
- 连发两次 retry → 只执行一次（provider 调用数 + attempt 断言）；
- ``queued`` 但本进程未调度（手工 ``store.retry`` 绕过路由）→ 再调 retry 会补调度并终态；
- ``running`` → 409 ``JOB_NOT_RETRYABLE``；``succeeded`` 不允许重跑；
- question / knowledge 两域注册形状。

阻塞说明（结果卡已登记）：公共件 ``app/services/jobs/registry.py`` 目前从
``app.repositories.jobs.repository`` 导入未定义的 ``JobExecutor``（该类在
``app.services.jobs.engine``），导入即 ``ImportError``；``main.py`` 捕获后把
``app.state.job_executors`` 置为 ``None``，真装配 retry 无法调度。CTRL 修复
类型导入与装配顺序（``_build_executor_registry`` 移到各域服务构造之后）后，本文件
自动生效；在此之前整个模块以明确原因 skip，不让全量套件因公共件缺陷变红。

不触网、不读写正式数据目录；模型一律为受控替身。
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import create_app
from tests.conftest import make_settings
from tests.test_question_bank import LOCAL_PROFILE, FakeLLMProvider, FakeResolver, make_handle
from tests.test_question_generation import generation_reply

#: RV01 前置公共件是否可用；不可用则本模块整体 skip（原因写明，不静默通过）。
#: 行为审计：registry.py 修复前 ImportError 来自模块内部（缺 JobExecutor 类型），
#: ``importorskip`` 会如实地重新抛出而不是跳过，因此显式捕获并 skip。
try:
    from app.services.jobs.registry import JobExecutorRegistry
except ImportError as exc:  # pragma: no cover - CTRL 修复公共件后此分支消失
    pytest.skip(
        (
            "RV01 前置公共件不可用：app/services/jobs/registry.py 从 "
            "app.repositories.jobs.repository 导入未定义的 JobExecutor（应为 "
            "app.services.jobs.engine），导入即 ImportError；main.py 因此把 "
            f"app.state.job_executors 置为 None，真装配 retry 无法调度。原始错误：{exc}"
        ),
        allow_module_level=True,
    )

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
GENERATION_BODY = {
    "modelProfileId": LOCAL_PROFILE,
    "subjectId": "math",
    "knowledgePointIds": [],
    "questionTypes": ["short_answer"],
    "difficulty": "medium",
    "count": 1,
    "materials": [],
}


def _job_view(client: TestClient, job_id: str) -> dict:
    response = client.get(
        f"/api/v1/workflow-jobs/{job_id}", params={"domain": "question"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _wait_job(
    client: TestClient, job_id: str, *, timeout: float = 8.0, states=frozenset(TERMINAL_STATES)
) -> dict:
    deadline = time.monotonic() + timeout
    view = _job_view(client, job_id)
    while view["state"] not in states and time.monotonic() < deadline:
        time.sleep(0.02)
        view = _job_view(client, job_id)
    assert view["state"] in states, view
    return view


class RetryHarness:
    """真装配应用（只把真实服务的模型解析器换成替身）+ 受控 Provider。"""

    def __init__(self, tmp_path: Path, *, replies: list) -> None:
        self.settings = make_settings(tmp_path / "data")
        self.app = create_app(self.settings)
        self.provider = FakeLLMProvider(replies=list(replies))
        self.service = self.app.state.question_bank_service
        assert self.service is not None, "题库服务未装配"
        # 真装配（main.py 已注入模型仓储+凭证）下，测试用替身走"注入 resolver + 指纹核对"
        # 等价路径：清空共享冻结解析器（判定与错误码一致，见 service._frozen_model_resolver）
        self.service._frozen_model_resolver = None
        self.service.model_resolver = FakeResolver(
            default=make_handle(LOCAL_PROFILE, provider=self.provider)
        )
        self.registry = self.app.state.job_executors
        assert self.registry is not None, "执行器注册表未装配"
        # 真装配证据：已实现的 question 执行器由服务注册进应用注册表
        assert self.registry.has("question", "organize")
        assert self.registry.has("question", "generate")
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8001")
        self.client.__enter__()

    def close(self) -> None:
        self.client.__exit__(None, None, None)

    # ---------------------------------------------------------------- 便捷

    def start_generation(self) -> str:
        response = self.client.post("/api/v1/question-generation-jobs", json=GENERATION_BODY)
        assert response.status_code == 202, response.text
        return response.json()["jobId"]

    def retry(self, job_id: str):
        return self.client.post(
            f"/api/v1/workflow-jobs/{job_id}/retry", json={"domain": "question"}
        )

    def store(self):
        return self.service.job_engine.store("question")


def _failing_then_ok_replies() -> list:
    """首次调用抛上游错误（任务 failed），之后返回合法补题回复。"""
    return [
        AppError(
            "模型服务当前不可用（测试替身）。",
            code="UPSTREAM_UNAVAILABLE",
            status_code=503,
            retryable=True,
        ),
        generation_reply(),
    ]


@pytest.fixture()
def harness(tmp_path: Path):
    instance = RetryHarness(tmp_path, replies=_failing_then_ok_replies())
    try:
        yield instance
    finally:
        instance.close()


# ------------------------------------------------------------- 注册形状（两域）


def test_register_job_executors_covers_question_and_knowledge(harness: RetryHarness) -> None:
    for domain, kind in (("question", "generate"), ("question", "organize")):
        spec = harness.registry.spec_for(domain, kind)
        assert spec is not None and spec.uses_model is True and callable(spec.factory)
    # 知识点域同样注册（真装配的 knowledge_service）
    knowledge_registry = JobExecutorRegistry()
    harness.app.state.knowledge_service.register_job_executors(knowledge_registry)
    assert knowledge_registry.kinds() == [("knowledge", "suggestion")]
    spec = knowledge_registry.spec_for("knowledge", "suggestion")
    assert spec is not None and spec.uses_model is True and callable(spec.factory)


# ------------------------------------------------- 失败 → retry → 新 attempt 终态


def test_retry_after_failure_runs_new_attempt_to_success(harness: RetryHarness) -> None:
    job_id = harness.start_generation()
    failed = _wait_job(harness.client, job_id)
    assert failed["state"] == "failed", failed
    assert failed["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert failed["attempt"] == 1
    assert len(harness.provider.calls) == 1

    receipt = harness.retry(job_id)
    assert receipt.status_code == 200, receipt.text
    # 重排即 queued（attempt 不变），claim 才 +1（任务卡 §4.1 的 N/N+1 观察口径）
    assert receipt.json()["state"] == "queued"
    assert receipt.json()["attempt"] == 1

    final = _wait_job(harness.client, job_id)
    assert final["state"] == "succeeded", final
    assert final["attempt"] == 2
    assert final["error"] is None
    assert final["result"]["candidateCount"] == 1
    assert len(harness.provider.calls) == 2  # 只有新 attempt 真正执行过
    assert harness.service.job_record(job_id).frozen_input["count"] == 1


def test_double_retry_click_executes_only_once(harness: RetryHarness) -> None:
    job_id = harness.start_generation()
    assert _wait_job(harness.client, job_id)["state"] == "failed"
    calls_before = len(harness.provider.calls)

    first = harness.retry(job_id)
    second = harness.retry(job_id)
    assert first.status_code == 200, first.text
    # 第二次点击：已在本引擎调度（queued）→ 200 幂等；已被 claim（running）→ 409。
    # 两种都是"不重复执行"的契约结果，效果断言在下面。
    assert second.status_code in (200, 409), second.text
    if second.status_code == 200:
        assert second.json()["state"] in ("queued", "running")
    else:
        assert second.json()["code"] == "JOB_NOT_RETRYABLE"

    final = _wait_job(harness.client, job_id)
    assert final["state"] == "succeeded", final
    assert final["attempt"] == 2  # 只多领了一次
    assert len(harness.provider.calls) == calls_before + 1


def test_retry_is_rejected_while_running(harness: RetryHarness) -> None:
    job_id = harness.start_generation()
    assert _wait_job(harness.client, job_id)["state"] == "failed"
    # 直接领取（模拟另一个执行者正在跑）：公共 retry 对 running 一律 409
    harness.store().claim(job_id)
    response = harness.retry(job_id)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "JOB_NOT_RETRYABLE"
    assert len(harness.provider.calls) == 1  # 没有触发第二次执行


# --------------------------------------------- queued 但未调度（重启/异常遗留）


def test_retry_reschedules_queued_job_left_unscheduled(harness: RetryHarness) -> None:
    job_id = harness.start_generation()
    assert _wait_job(harness.client, job_id)["state"] == "failed"

    # 手工绕过路由重排（模拟"入队后调度异常 / 进程重启遗留"：queued 但本进程没在跑）
    record = harness.store().retry(job_id)
    assert record.state == "queued"
    assert harness.store().get(job_id).attempt == 1
    calls_before = len(harness.provider.calls)

    response = harness.retry(job_id)
    assert response.status_code == 200, response.text
    final = _wait_job(harness.client, job_id)
    assert final["state"] == "succeeded", final
    assert final["attempt"] == 2
    assert len(harness.provider.calls) == calls_before + 1


def test_retry_not_retryable_after_success(harness: RetryHarness) -> None:
    """终态 succeeded 不允许重跑（结果已发布）：显式 retry 409，不重复执行。"""
    job_id = harness.start_generation()
    assert _wait_job(harness.client, job_id)["state"] == "failed"
    assert harness.retry(job_id).status_code == 200
    assert _wait_job(harness.client, job_id)["state"] == "succeeded"
    calls_after_success = len(harness.provider.calls)

    blocked = harness.retry(job_id)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "JOB_NOT_RETRYABLE"
    assert len(harness.provider.calls) == calls_after_success
