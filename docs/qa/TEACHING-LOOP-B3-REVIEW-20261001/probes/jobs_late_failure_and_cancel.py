"""Independent B3 review probes; temporary data only, no network calls.

Run from apps/api with `uv run --no-sync python <absolute-path>`.
All product code is unchanged. Controlled scheduling interleavings expose two
normal service paths that lack cancellation/lease checks.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
RUN_ROOT = Path(tempfile.mkdtemp(prefix="zqky-b3-review-jobs-"))
os.environ["ZQKY_DATA_DIR"] = str(RUN_ROOT / "default-import-root")
sys.path.insert(0, str(WORKSPACE / "apps" / "api"))

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.services.model_runtime import fingerprint_of_handle
from app.services.question_bank import generation
from tests.test_model_drift_guards import _organize_contract
from tests.test_question_bank import LOCAL_PROFILE, FakeLLMProvider
from tests.test_question_generation import GenerationHarness, _generation_request, generation_reply


async def wait_terminal(store, job_id):
    deadline = asyncio.get_running_loop().time() + 5
    while asyncio.get_running_loop().time() < deadline:
        record = store.get(job_id)
        if record.state in {"succeeded", "failed", "cancelled", "interrupted"}:
            return record
        await asyncio.sleep(0.01)
    raise AssertionError("job did not settle")


async def cancelled_while_waiting_for_model_slot():
    provider = FakeLLMProvider(replies=[generation_reply()])
    harness = GenerationHarness(RUN_ROOT / "cancel", provider=provider, with_client=False)
    engine = harness.service.job_engine
    engine._ensure_primitives()
    await engine._model.acquire()
    try:
        job = await harness.service.create_generation_job(_generation_request([]))
        store = engine.store("question")
        for _ in range(100):
            if store.get(job.jobId).state == "running":
                break
            await asyncio.sleep(0.01)
        before = store.request_cancel(job.jobId)
        assert before.cancel_requested and provider.calls == []
        engine._model.release()
        result = await wait_terminal(store, job.jobId)
        assert result.state == "cancelled"
        assert len(provider.calls) == 1, "probe expected unnecessary provider call"
        assert harness.row_count("question_imports") == 0
        return {
            "case": "cancel_requested_before_model_slot_acquired",
            "cancelBeforeProvider": True,
            "finalState": result.state,
            "providerCallsAfterCancel": len(provider.calls),
            "publishedImports": harness.row_count("question_imports"),
        }
    finally:
        await engine.shutdown()
        harness.close()


def late_failure_overwrites_new_holder_checkpoint():
    harness = GenerationHarness(RUN_ROOT / "late-failure")
    try:
        detail = harness.sample_detail()
        draft = harness.catalog.get_draft(detail["drafts"][0]["draftId"])
        provider = FakeLLMProvider(replies=[AppError(
            "old worker upstream failure", code="UPSTREAM_UNAVAILABLE", status_code=503
        )])
        handle = harness.handle(LOCAL_PROFILE, provider=provider)
        store = harness.service.job_engine.store("question")
        job = store.create(
            kind="organize",
            frozen_input=_organize_contract(draft, fingerprint=fingerprint_of_handle(handle)),
            model_snapshot={"profileId": LOCAL_PROFILE, "fingerprint": fingerprint_of_handle(handle)},
        )
        real_update = harness.catalog.update_job
        takeover = {}

        def race_before_old_checkpoint_write(job_id, **kwargs):
            checkpoint = kwargs.get("checkpoint") or {}
            if "jobError" in checkpoint and not takeover:
                # Interleave another worker's expired-lease claim after the old
                # worker reads the checkpoint and before it writes jobError.
                connection = connect(harness.catalog.db_path)
                try:
                    connection.execute(
                        "UPDATE question_jobs SET lease_expires_at='2000-01-01T00:00:00Z' WHERE id=?",
                        (job_id,),
                    )
                finally:
                    connection.close()
                fresh = store.claim(job_id)
                takeover.update(attempt=fresh.attempt, token=fresh.token)
                _current, created, failure = harness.catalog.record_organize_batch(
                    job_id, batch_index=0, next_batch_index=1,
                    draft_id=draft.draft_id, base_draft_revision=draft.revision,
                    proposed_content=dict(draft.content),
                    lease_attempt=fresh.attempt, lease_token=fresh.token,
                )
                assert created is not None and failure is None
                takeover["suggestionId"] = created.suggestion_id
            return real_update(job_id, **kwargs)

        harness.catalog.update_job = race_before_old_checkpoint_write
        outcome = asyncio.run(harness.service.job_engine.run_job(
            "question", job.job_id,
            harness.service._organize_executor_factory(model=handle), uses_model=True,
        ))
        live = store.get(job.job_id)
        assert live.state == "running" and live.attempt == 2
        assert live.lease_token == takeover["token"]
        assert live.checkpoint.get("nextBatchIndex", 0) == 0
        assert live.checkpoint.get("suggestionIds", []) == []
        assert len(harness.catalog.list_suggestions(organization_job_id=job.job_id)) == 1
        assert live.checkpoint["jobError"]["code"] == "UPSTREAM_UNAVAILABLE"
        return {
            "case": "old_failure_after_checkpoint_read_new_lease_claim",
            "newAttempt": live.attempt,
            "newLeasePreserved": True,
            "newHolderPublishedSuggestion": takeover["suggestionId"],
            "newCheckpointSuggestionLost": True,
            "newCheckpointProgress": 1,
            "actualCheckpointProgress": live.checkpoint.get("nextBatchIndex", 0),
            "actualCheckpoint": live.checkpoint,
            "finalState": outcome.state,
        }
    finally:
        harness.close()


if __name__ == "__main__":
    observations = [asyncio.run(cancelled_while_waiting_for_model_slot()),
                    late_failure_overwrites_new_holder_checkpoint()]
    print(json.dumps({"isolated": True, "tempRoot": str(RUN_ROOT),
                      "observations": observations}, ensure_ascii=False, indent=2))
