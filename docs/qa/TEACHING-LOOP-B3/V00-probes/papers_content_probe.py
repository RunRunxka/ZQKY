"""Reproduce B2 confirmation despite missing diagram / empty question content.

Run from apps/api: uv run --no-sync python <absolute path to this script>.
All application data is temporary; only review evidence is written beside this file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

# Must precede any import of app.main, including indirect test harness imports.
root = Path(tempfile.mkdtemp(prefix="zqky-b2-review-paper-content-"))
os.environ["ZQKY_DATA_DIR"] = str(root / "startup-data")
api_root = Path(__file__).resolve().parents[4] / "apps" / "api"
sys.path.insert(0, str(api_root))
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document
from docx.oxml import parse_xml
from tests.papers_support import PapersHarness, items_payload
from app.contracts.papers import PaperDraftPatchRequest, PaperConfirmRequest

results = []


def emit(result):
    results.append(result)
    print(json.dumps(result, ensure_ascii=False))


harness = PapersHarness(root)
service = harness.service()
point = harness.add_point("AREA", "Area")
document = Document()
paragraph = document.add_paragraph("1.（5 分）Use the diagram to compute the shaded area.")
paragraph._p.append(parse_xml(
    '<w:object xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">'
    '<v:shape id="critical-diagram"><v:imagedata o:title="required diagram"/></v:shape>'
    '<o:OLEObject Type="Embed" ProgID="Package" ShapeID="critical-diagram"/>'
    '</w:object>'
))
path = root / "critical-diagram.docx"
document.save(path)

imported = harness.import_docx(service, path)
payload = items_payload(imported.revision.items, knowledge={"1": [point.point_id]})
blocking = [issue for issue in imported.revision.issues if issue.severity == "blocking"]
service.patch_draft(imported.paper.paper_id, PaperDraftPatchRequest.model_validate({
    "expectedRevision": 0,
    "items": payload,
    "issues": [{"issueId": issue.issue_id, "status": "resolved", "resolution": {"anything": 1}}
               for issue in blocking],
}))
confirmed = service.confirm(imported.paper.paper_id, PaperConfirmRequest(
    expectedRevision=1, submissionId="without-replacement",
))
snapshot = service.confirmed_reader().read(confirmed.paper_revision_id)
emit({
    "probe": "required-diagram-unreplaced",
    "blocking": [issue.code for issue in blocking],
    "confirmedState": confirmed.state,
    "stemContent": snapshot.items[0].content,
    "originalMissingCriticalObjectHasNoReplacement": (
        snapshot.items[0].content == imported.revision.items[0].content
    ),
})

# Separate original revision: discard all item rich content but keep source ownership.
imported = harness.import_docx(service, path)
payload = items_payload(imported.revision.items, knowledge={"1": [point.point_id]})
for item in payload:
    item["content"] = {}
service.patch_draft(imported.paper.paper_id, PaperDraftPatchRequest.model_validate({
    "expectedRevision": 0,
    "items": payload,
    "issues": [{"issueId": issue.issue_id, "status": "excluded",
                "resolution": {"note": "excluded"}}
               for issue in imported.revision.issues if issue.severity == "blocking"],
}))
confirmed = service.confirm(imported.paper.paper_id, PaperConfirmRequest(
    expectedRevision=1, submissionId="empty-content",
))
emit({
    "probe": "empty-content-confirm", "state": confirmed.state,
    "readerContent": service.confirmed_reader().read(confirmed.paper_revision_id).items[0].content,
})
emit({"evidenceDirectory": str(root)})
Path(__file__).with_suffix(".json").write_text(
    json.dumps({"results": results, "exitMeaning": "0 means reproduction completed"},
               ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
