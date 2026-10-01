"""B2 review: queued question generation uses a changed profile configuration.

Run from apps/api: uv run --no-sync python <absolute path to this script>.
Uses an isolated temporary data root and fake provider; no real model is called.
The held model slot represents an earlier long-running model task.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

repository_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repository_root / "apps" / "api"))
probe_root = Path(tempfile.mkdtemp(prefix="zqky-b2-review-model-"))
os.environ["ZQKY_DATA_DIR"] = str(probe_root / "module-default-isolated")
os.environ.pop("ZQKY_CREDENTIALS_FILE", None)

from tests.test_question_generation import GenerationHarness, generation_reply
from tests.test_question_bank import FakeLLMProvider, make_handle, LOCAL_PROFILE
from app.schemas.question_bank import QuestionGenerationRequest
from app.services.question_bank.generation import build_model_snapshot

async def scenario() -> dict:
    provider = FakeLLMProvider(replies=[generation_reply()])
    harness = GenerationHarness(probe_root / "h", provider=provider, with_client=False)
    engine = harness.service.job_engine
    engine._ensure_primitives()
    await engine._model.acquire()
    try:
        harness.resolver.default = make_handle(
            LOCAL_PROFILE, model_id="model-A", provider=provider,
        )
        job = await harness.service.create_generation_job(
            QuestionGenerationRequest(
                modelProfileId=LOCAL_PROFILE, subjectId="math", count=1,
            ),
        )
        await asyncio.sleep(0.03)
        harness.resolver.default = make_handle(
            LOCAL_PROFILE, model_id="model-B", provider=provider,
        )
        engine._model.release()
        for _ in range(200):
            record = harness.service.job_record(job.jobId)
            if record.state in {"succeeded", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert record.state == "succeeded", record.state
        result = {
            "probeRoot": str(probe_root),
            "state": record.state,
            "calledModel": provider.calls[0].model_id,
            "storedFingerprint": record.model_snapshot["fingerprint"],
            "actualFingerprint": build_model_snapshot(harness.resolver.default)["fingerprint"],
        }
        print("queued_model_changed", record.state,
              "called_model", result["calledModel"],
              "stored_fp", result["storedFingerprint"],
              "actual_fp", result["actualFingerprint"])
        return result
    finally:
        await engine.shutdown()
        harness.close()

observations = asyncio.run(scenario())
Path(__file__).with_suffix(".json").write_text(
    json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
)
print("probe_root", probe_root)
