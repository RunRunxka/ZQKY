"""Read-only B2 paper review reproductions, with isolated temporary databases.

Run from apps/api: uv run --no-sync python <absolute path to this script>.
Product files and formal data are not changed. JSON evidence is written beside
this script; this is a bug reproduction probe, so exit 0 means it ran to completion.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile

# Must precede imports of tests.papers_support / app.main.
root = Path(tempfile.mkdtemp(prefix="zqky-b2-review-papers-"))
os.environ["ZQKY_DATA_DIR"] = str(root / "startup-data")
api_root = Path(__file__).resolve().parents[4] / "apps" / "api"
sys.path.insert(0, str(api_root))
sys.stdout.reconfigure(encoding="utf-8")

from tests.papers_support import (
    FakeProvider, PapersHarness, build_no_question_docx, build_paper_docx,
    items_payload, make_handle,
)
from app.contracts.papers import PaperConfirmRequest, PaperDraftPatchRequest
from app.services.jobs.engine import FrozenJob
from app.services.papers.proposals import ProposalRunner, model_fingerprint

results = []


def emit(result):
    results.append(result)
    print(json.dumps(result, ensure_ascii=False))


def prepare(subdir, *, unknown=False):
    path = root / subdir
    path.mkdir()
    harness = PapersHarness(path)
    service = harness.service()
    imported = harness.import_docx(
        service, build_paper_docx(path / "paper.docx", with_unknown_object=unknown),
        title="Original Title",
    )
    point = harness.add_point("K1", "Knowledge")
    service.patch_draft(
        imported.paper.paper_id,
        PaperDraftPatchRequest.model_validate({
            "expectedRevision": 0,
            "items": items_payload(imported.revision.items, knowledge={
                item.question_no: [point.point_id]
                for item in imported.revision.items if item.is_scored
            }),
        }),
    )
    return harness, service, imported, point


# 1. Unassigned source blocks are stored but their content is omitted from the API DTO.
no = root / "no-question"
no.mkdir()
harness = PapersHarness(no)
service = harness.service()
imported = harness.import_docx(service, build_no_question_docx(no / "no.docx"))
response = service.get_revision_content(
    imported.paper.paper_id, imported.revision.paper_revision_id,
).model_dump(mode="json", by_alias=True)
raw = harness.raw_rows("SELECT block_json FROM paper_source_blocks")[0]["block_json"]
needle = "这是一份没有题号的文档"
emit({
    "probe": "unassigned-block-content",
    "items": len(response["items"]),
    "blockKeys": list(response["blocks"][0]),
    "responseContainsOriginalText": needle in json.dumps(response, ensure_ascii=False),
    "dbContainsOriginalText": needle in raw,
})

# 2. Any nonempty resolution object closes a blocking issue without replacement content.
harness, service, imported, point = prepare("issue-bypass", unknown=True)
before = harness.raw_rows("SELECT content_json FROM paper_items ORDER BY id")
blocking = [issue for issue in imported.revision.issues if issue.severity == "blocking"]
service.patch_draft(imported.paper.paper_id, PaperDraftPatchRequest.model_validate({
    "expectedRevision": 1,
    "issues": [{"issueId": issue.issue_id, "status": "resolved", "resolution": {"anything": 1}}
               for issue in blocking],
}))
confirmed = service.confirm(imported.paper.paper_id, PaperConfirmRequest(
    expectedRevision=2, submissionId="resolve-without-content",
))
after = harness.raw_rows("SELECT content_json FROM paper_items ORDER BY id")
emit({
    "probe": "blocking-bypass",
    "blockingIssueCodes": [issue.code for issue in blocking],
    "itemContentUnchanged": before == after,
    "resultState": confirmed.state,
    "resolvedPayload": harness.raw_rows(
        "SELECT resolution_json FROM paper_issues WHERE severity='blocking'",
    ),
})

# 3. Archive a linked point after draft validation, then publish a confirmed revision.
harness, service, imported, point = prepare("archive-and-title")
harness.archive_point(point.point_id)
confirmed = service.confirm(imported.paper.paper_id, PaperConfirmRequest(
    expectedRevision=1, submissionId="after-archive",
))
old = service.get_revision_content(imported.paper.paper_id, confirmed.paper_revision_id)
reader_before = service.confirmed_reader().read(confirmed.paper_revision_id)
emit({
    "probe": "archive-then-confirm",
    "confirmedState": confirmed.state,
    "archivedKnowledgeWasConfirmed": all(
        item.knowledge[0].knowledge_point_id == point.point_id
        for item in old.items if item.is_scored
    ),
})

# 4. Rename a new draft and re-read the old, unchanged confirmed revision ID.
service.patch_draft(imported.paper.paper_id, PaperDraftPatchRequest(
    expectedRevision=2, title="NEW DRAFT Title",
))
old_after = service.get_revision_content(imported.paper.paper_id, confirmed.paper_revision_id)
reader_after = service.confirmed_reader().read(confirmed.paper_revision_id)
emit({
    "probe": "old-revision-title-drift",
    "confirmedRevisionSame": old.paper_revision_id == old_after.paper_revision_id,
    "viewBefore": old.title, "viewAfter": old_after.title,
    "readerBefore": reader_before.title, "readerAfter": reader_after.title,
})


async def model_drift():
    provider = FakeProvider()
    old_handle = make_handle(provider=provider)
    new_handle = replace(
        old_handle, model_id="DIFFERENT-MODEL",
        config=replace(old_handle.config, modelId="DIFFERENT-MODEL"),
    )

    def fingerprint(handle):
        return model_fingerprint(
            model_id=handle.model_id, protocol=handle.config.protocol.value,
            base_url=handle.config.baseUrl, api_format=handle.config.apiFormat or "",
        )

    async def resolve(_profile):
        return new_handle

    class Context:
        async def cancellation_requested(self):
            return False

    published = []
    runner = ProposalRunner(
        resolve_model=resolve, publish_proposal=lambda _conn, draft: published.append(draft),
    )
    frozen = FrozenJob(
        job_id="j", domain="teaching", kind="paper_mapping", attempt=2,
        input={"paperId": "p", "paperRevisionId": "r", "baseRevision": 1,
               "subjectId": "math", "modelProfileId": "same-profile",
               "allowedItemIds": [], "allowedKnowledgePointIds": [], "items": []},
        model_snapshot={"profileId": "same-profile", "fingerprint": fingerprint(old_handle)},
        input_hash="x",
    )
    outcome = await runner(frozen, Context())
    outcome.publish(None)
    emit({
        "probe": "model-fingerprint-drift",
        "frozenFingerprint": fingerprint(old_handle),
        "actualFingerprint": fingerprint(new_handle),
        "providerCalls": len(provider.calls),
        "actualProviderModelId": new_handle.config.modelId,
        "publishedFingerprint": published[0].model["fingerprint"],
        "outcome": "accepted despite changed model",
    })


asyncio.run(model_drift())
emit({"evidenceDirectory": str(root)})
Path(__file__).with_suffix(".json").write_text(
    json.dumps({"results": results, "exitMeaning": "0 means reproduction completed"},
               ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
