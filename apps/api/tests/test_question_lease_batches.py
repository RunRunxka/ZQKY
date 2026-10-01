"""题库整理中间批的租约 CAS（TEACHING-LOOP B3 / G0 · B2-RV05 正确行为回归）。

审查缺陷：``record_organize_batch`` 不接收租约、不要求任务 ``running``，旧 attempt 在
失权后仍能写入建议并推进**新持有者**的 checkpoint；任务收敛为 ``interrupted``/``cancelled``
后迟到批次也能写入。

回归断言（反向对照见 ``docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/probes/question_lease_probe.py``）：

- 旧 attempt / 过期租约 / interrupted / cancelled / 未提供租约 → 零写入
  （不落建议、不推进 checkpoint、不覆盖新持有者）；
- 正常路径（当前有效租约）照常写入建议与进度；
- 服务层执行器把本执行轮的租约身份带进每一批（端到端 organise 仍成功）。

全部用 ``tmp_path`` 临时题库 + 假时钟：不触网、不读写正式数据目录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from app.repositories.jobs.repository import JobLease, JobStore
from app.repositories.question_bank.catalog import (
    JobLeaseIdentity,
    QuestionBankCatalog,
)
from app.repositories.question_bank.records import DraftInput
from tests.test_jobs_engine import FakeClock
from tests.test_question_bank import LOCAL_PROFILE, make_handle
from tests.test_question_generation import GenerationHarness

TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})


def _proposed(stem: str = "整理后的题干（ ）") -> dict[str, Any]:
    return {
        "type": "short_answer",
        "stemMarkdown": stem,
        "options": [],
        "answer": {"choiceKeys": [], "accepted": None, "textMarkdown": "答案"},
        "explanationMarkdown": None,
        "assetIds": [],
    }


class LeaseFixture:
    """题库存量目录 + 假时钟任务仓储 + 一只可提交的草稿。"""

    def __init__(self, tmp_path: Path) -> None:
        self.catalog = QuestionBankCatalog(tmp_path / "question-bank.sqlite3")
        self.catalog.migrate()
        self.clock = FakeClock()
        self.store = JobStore(
            self.catalog,
            domain="question",
            table="question_jobs",
            kinds=frozenset({"organize", "generate"}),
            lease_seconds=30,
            now=self.clock.now,
        )
        import_id = self.catalog.create_import(
            owner_id="local-user",
            file_sha256="a" * 64,
            original_blob_id="a" * 64,
            uploaded_file_name="x.md",
            uploaded_bytes=1,
            state="needs_review",
        ).import_id
        self.draft = self.catalog.create_drafts(
            import_id,
            [
                DraftInput(
                    content=_proposed("原文题干（ ）"),
                    metadata={"subjectId": "math"},
                    source_spans=[],
                    extraction_method="rule",
                    review_state="needs_review",
                )
            ],
        )[0]

    # ------------------------------------------------------------------ 便捷

    def job(self, **kwargs: Any) -> Any:
        return self.store.create(kind="organize", frozen_input={}, **kwargs)

    def lease_of(self, lease: JobLease) -> JobLeaseIdentity:
        return JobLeaseIdentity(attempt=lease.attempt, token=lease.token)

    def batch(
        self,
        job_id: str,
        *,
        lease: JobLeaseIdentity | None = None,
        index: int = 0,
        stem: str = "迟到批次（ ）",
        now: str | None = None,
    ):
        # 时钟一致：仓储与 CAS 都用同一只假时钟（生产两者都是统一 ``now_iso``）
        return self.catalog.record_organize_batch(
            job_id,
            batch_index=index,
            next_batch_index=index + 1,
            draft_id=self.draft.draft_id,
            base_draft_revision=self.draft.revision,
            proposed_content=_proposed(stem),
            source_block_ids=(),
            lease_attempt=None if lease is None else lease.attempt,
            lease_token=None if lease is None else lease.token,
            now=self.clock.now() if now is None else now,
        )

    def suggestions(self, job_id: str) -> Sequence[Any]:
        return self.catalog.list_suggestions(organization_job_id=job_id)

    def assert_zero_write(self, job_id: str) -> None:
        assert self.suggestions(job_id) == []
        checkpoint = self.store.get(job_id).checkpoint
        assert checkpoint.get("suggestionIds") in (None, [])
        assert checkpoint.get("nextBatchIndex", 0) == 0


# --------------------------------------------------------------------- 正常路径


def test_current_lease_writes_suggestion_and_progress(tmp_path: Path) -> None:
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    lease = fixture.store.claim(job.job_id)
    assert fixture.catalog.job_lease_identity(job.job_id, now=fixture.clock.now()) == (
        fixture.lease_of(lease)
    )

    _job, created, failure = fixture.batch(job.job_id, lease=fixture.lease_of(lease))
    assert created is not None and failure is None
    assert len(fixture.suggestions(job.job_id)) == 1
    live = fixture.store.get(job.job_id)
    assert live.state == "running"
    assert live.checkpoint["nextBatchIndex"] == 1
    assert live.checkpoint["suggestionIds"] == [created.suggestion_id]


# ----------------------------------------------------------------- 旧 attempt


def test_stale_attempt_batch_writes_nothing_and_keeps_new_holder_checkpoint(
    tmp_path: Path,
) -> None:
    """旧 attempt 租约过期、新 claim 接管后，旧批次零写入且不推进新持有者进度。"""
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    first = fixture.store.claim(job.job_id)
    assert first.attempt == 1

    fixture.clock.advance(60)  # 租约过期（lease_seconds=30）
    second = fixture.store.claim(job.job_id)
    assert second.attempt == 2

    now = fixture.clock.now()
    job_now, created, failure = fixture.batch(
        job.job_id, lease=fixture.lease_of(first), now=now
    )
    assert created is None and failure is None
    assert job_now.state == "running"
    fixture.assert_zero_write(job.job_id)
    # 新持有者的租约仍有效，且没有被旧批次的写入/收敛影响
    live = fixture.store.get(job.job_id)
    assert (live.attempt, live.lease_token) == (second.attempt, second.token)
    assert fixture.catalog.job_lease_identity(job.job_id, now=now) == fixture.lease_of(second)

    # 新持有者用同一批号提交：正常写入（旧批次没占掉进度）
    _job, created_new, _failure = fixture.batch(
        job.job_id, lease=fixture.lease_of(second), now=now
    )
    assert created_new is not None
    assert fixture.store.get(job.job_id).checkpoint["nextBatchIndex"] == 1


def test_expired_lease_batch_writes_nothing_until_reclaimed(tmp_path: Path) -> None:
    """租约过期但尚未被接管：迟到批次零写入；重新 claim 后可正常继续。"""
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    lease = fixture.store.claim(job.job_id)

    fixture.clock.advance(120)
    now = fixture.clock.now()
    assert fixture.catalog.job_lease_identity(job.job_id, now=now) is None
    _job, created, failure = fixture.batch(
        job.job_id, lease=fixture.lease_of(lease), now=now
    )
    assert created is None and failure is None
    fixture.assert_zero_write(job.job_id)

    fresh = fixture.store.claim(job.job_id)  # 过期后可接管（attempt+1）
    assert fresh.attempt == 2
    _job, created_again, _failure = fixture.batch(
        job.job_id, lease=fixture.lease_of(fresh), now=now
    )
    assert created_again is not None


# ----------------------------------------------------- interrupted / cancelled


def test_interrupted_job_batch_writes_nothing(tmp_path: Path) -> None:
    """任务被重启收敛为 interrupted 后，迟到批次零写入（不复活、不推进进度）。"""
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    lease = fixture.store.claim(job.job_id)
    assert fixture.store.reconcile_interrupted() == [job.job_id]
    assert fixture.store.get(job.job_id).state == "interrupted"

    _job, created, failure = fixture.batch(
        job.job_id, lease=fixture.lease_of(lease), now=fixture.clock.now()
    )
    assert created is None and failure is None
    fixture.assert_zero_write(job.job_id)
    assert fixture.store.get(job.job_id).state == "interrupted"


def test_cancelled_job_batch_writes_nothing(tmp_path: Path) -> None:
    """取消优先：running 中置取消标志后，迟到批次零写入（终态由引擎收敛）。"""
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    lease = fixture.store.claim(job.job_id)
    fixture.store.request_cancel(job.job_id)

    job_now, created, failure = fixture.batch(job.job_id, lease=fixture.lease_of(lease))
    assert created is None and failure is None
    assert job_now.state == "running"
    live = fixture.store.get(job.job_id)
    assert live.state == "running" and live.cancel_requested is True
    fixture.assert_zero_write(job.job_id)


def test_batch_without_lease_writes_nothing(tmp_path: Path) -> None:
    """没有租约身份（调用方 bug / 审查探针形状）一律零写入，不冒充当前持有者。"""
    fixture = LeaseFixture(tmp_path)
    job = fixture.job()
    fixture.store.claim(job.job_id)

    job_now, created, failure = fixture.batch(job.job_id)
    assert created is None and failure is None
    assert job_now.state == "running"
    fixture.assert_zero_write(job.job_id)


# ----------------------------------------------------------------- 服务层接线


def test_service_organize_path_still_succeeds_with_lease_cas(tmp_path: Path) -> None:
    """正常路径不受影响：真实服务执行器带租约提交每一批，组织任务照常 succeeded。"""
    harness = GenerationHarness(tmp_path)
    try:
        detail = harness.sample_detail()
        draft = detail["drafts"][0]
        response = harness.client.post(
            f"/api/v1/question-imports/{detail['importId']}/organize",
            json={
                "draftIds": [draft["draftId"]],
                "includeUnassigned": False,
                "modelProfileId": LOCAL_PROFILE,
            },
        )
        assert response.status_code == 200, response.text
        view = response.json()
        assert view["state"] == "succeeded"
        assert view["suggestionCount"] == 1
        record = harness.service.job_record(view["jobId"])
        assert record.attempt == 1
        assert record.checkpoint["nextBatchIndex"] == 1
        assert len(harness.catalog.list_suggestions(organization_job_id=view["jobId"])) == 1
    finally:
        harness.close()
