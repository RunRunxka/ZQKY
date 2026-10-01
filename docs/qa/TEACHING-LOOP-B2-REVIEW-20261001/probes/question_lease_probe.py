"""B2 review: organizer batch writes do not check attempt/lease or running state.

Run from apps/api: uv run --no-sync python <absolute path to this script>.
Uses a temporary question database and a fake clock; no app or network server.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

repository_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repository_root / "apps" / "api"))
probe_root = Path(tempfile.mkdtemp(prefix="zqky-b2-review-lease-"))
os.environ["ZQKY_DATA_DIR"] = str(probe_root / "default-isolated")
os.environ.pop("ZQKY_CREDENTIALS_FILE", None)

from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.question_bank.records import DraftInput
from app.repositories.jobs.repository import JobStore
from tests.test_jobs_engine import FakeClock

catalog = QuestionBankCatalog(probe_root / "q.sqlite3")
catalog.migrate()
import_record = catalog.create_import(
    owner_id="local-user", file_sha256="a" * 64, original_blob_id="a" * 64,
    uploaded_file_name="x.md", uploaded_bytes=1, state="needs_review",
)
draft = catalog.create_drafts(import_record.import_id, [DraftInput(
    content={"type": "short_answer", "stemMarkdown": "x", "options": [],
             "answer": None, "explanationMarkdown": None, "assetIds": []},
    metadata={"subjectId": "math"}, source_spans=[], extraction_method="rule",
    review_state="needs_review",
)])[0]
clock = FakeClock()
store = JobStore(
    catalog, domain="question", table="question_jobs",
    kinds=frozenset({"organize"}), lease_seconds=3, now=clock.now,
)
job = store.create(kind="organize", frozen_input={})
first = store.claim(job.job_id)
clock.advance(5)
second = store.claim(job.job_id)
_record, suggestion, _failure = catalog.record_organize_batch(
    job.job_id, batch_index=0, next_batch_index=1,
    draft_id=draft.draft_id, base_draft_revision=draft.revision,
    proposed_content={
        "type": "short_answer", "stemMarkdown": "old attempt output",
        "options": [], "answer": None, "explanationMarkdown": None, "assetIds": [],
    }, source_block_ids=[],
)
live = store.get(job.job_id)
observations = {
    "probeRoot": str(probe_root), "oldAttempt": first.attempt,
    "newAttempt": second.attempt, "staleBatchSuggestionCreated": bool(suggestion),
    "suggestionsAfterStaleBatch": len(catalog.list_suggestions(organization_job_id=job.job_id)),
    "liveAttempt": live.attempt, "checkpointAfterStaleBatch": live.checkpoint,
}
print("stale_attempt_batch_written", first.attempt, second.attempt,
      "suggestion", bool(suggestion), "suggestions_total",
      observations["suggestionsAfterStaleBatch"], "live_attempt", live.attempt,
      "checkpoint", live.checkpoint)
store.reconcile_interrupted()
_record, again, _failure = catalog.record_organize_batch(
    job.job_id, batch_index=1, next_batch_index=2,
    draft_id=draft.draft_id, base_draft_revision=draft.revision,
    proposed_content={
        "type": "short_answer", "stemMarkdown": "interrupted late output",
        "options": [], "answer": None, "explanationMarkdown": None, "assetIds": [],
    }, source_block_ids=[],
)
observations["interruptedBatchSuggestionCreated"] = bool(again)
observations["finalState"] = store.get(job.job_id).state
print("interrupted_batch_written", observations["finalState"], bool(again))
Path(__file__).with_suffix(".json").write_text(
    json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
)
print("probe_root", probe_root)
