"""Independent read-only review probes; all application state is temporary."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="zqky-b3-review-scores-"))
os.environ["ZQKY_DATA_DIR"] = str(TEMP_ROOT / "module-import-data")
os.environ["PYTHONUTF8"] = "1"
os.environ["ZQKY_ENV"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "api"))

from fastapi.testclient import TestClient
from app.services.scores.imports import parse_score_text
from app.services.tabular import read_score_sheet
from tests.scores_support import SAMPLE_HEADER, ScoresHarness, write_score_xlsx


def confirmation(scene, view, key):
    return {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
        "previewVersion": view["previewVersion"],
        "submissionId": key,
        **view["requiredAcknowledgements"],
    }


result = {"temporaryRoot": str(TEMP_ROOT), "scenarios": []}

with ScoresHarness(TEMP_ROOT / "long-xlsx") as harness:
    scene = harness.create_scene(tag="long-xlsx")
    text = "1." + "0" * 19998 + "1"
    original = parse_score_text(text, max_units=200)
    source = write_score_xlsx(TEMP_ROOT / "long-score.xlsx", SAMPLE_HEADER,
                              [["0001", "甲", text, 2, 3]])
    grid = read_score_sheet(source.read_bytes())[0]
    parsed_cell = grid.rows[1][2]
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], source)
    entry = {
        "id": "xlsx-text-truncation",
        "originalLength": len(text),
        "originalSuffix": text[-12:],
        "directParseCode": original.code,
        "readLength": len(parsed_cell.text),
        "readSuffix": parsed_cell.text[-12:],
        "uploadStatus": uploaded.status_code,
        "originalFileSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    if uploaded.status_code == 201:
        view = uploaded.json()
        entry["previewIssues"] = view["issues"]
        entry["requiredAcknowledgements"] = view["requiredAcknowledgements"]
        rows = harness.list_import_rows(view["importId"]).json()["items"]
        cell = next(cell for cell in rows[0]["cells"] if cell["column"] == "C")
        entry["previewCell"] = {
            "row": cell["row"], "column": cell["column"],
            "originalTextLength": len(cell["originalText"]),
            "effectiveStatus": cell["effectiveStatus"], "scoreUnits": cell["scoreUnits"],
        }
        confirmed = harness.confirm_import(view["importId"], confirmation(scene, view, "long-confirm"))
        entry["confirmStatus"] = confirmed.status_code
        if confirmed.status_code == 200:
            page = harness.score_matrix(confirmed.json()["revisionId"]).json()
            entry["matrixCells"] = page["rows"][0]["cells"]
            entry["totalUnits"] = page["rows"][0]["participant"]["totalUnits"]
    result["scenarios"].append(entry)

with ScoresHarness(TEMP_ROOT / "csv-large-field") as harness:
    scene = harness.create_scene(tag="csv-large-field")
    client = TestClient(harness.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
    content = ("学号,姓名,Q1,Q2,Q3,备注\r\n0001,甲,1,2,3," + "x" * 131073 + "\r\n").encode("utf-8")
    response = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
                           files={"file": ("large-field.csv", content, "text/csv")})
    result["scenarios"].append({
        "id": "csv-reader-large-field", "fileBytes": len(content),
        "status": response.status_code, "contentType": response.headers.get("content-type"),
        "response": response.text[:500], "importCount": harness.count("score_imports"),
        "revisionCount": harness.count("score_revisions"),
    })

with ScoresHarness(TEMP_ROOT / "xlsx-short-dimension") as harness:
    scene = harness.create_scene(tag="xlsx-short-dimension", students=(("甲", "0001"), ("乙", "0002")))
    source = write_score_xlsx(TEMP_ROOT / "dimensions.xlsx", SAMPLE_HEADER,
                              [["0001", "甲", 1, 2, 3], ["0002", "乙", 2, 3, 4]])
    altered = TEMP_ROOT / "short-dimensions.xlsx"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(altered, "w", zipfile.ZIP_DEFLATED) as target:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b'<dimension ref="A1:E3"/>', b'<dimension ref="A1:E2"/>')
            target.writestr(info, data)
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], altered)
    entry = {"id": "xlsx-metadata-dimension", "uploadStatus": uploaded.status_code,
             "actualDataRows": 2}
    if uploaded.status_code == 201:
        view = uploaded.json()
        entry["readRowCount"] = view["rowCount"]
        entry["previewIssues"] = view["issues"]
        entry["missingCellCount"] = view["missingCellCount"]
        entry["storedPhysicalRows"] = [row["rowNo"] for row in harness.list_import_rows(view["importId"]).json()["items"]]
    result["scenarios"].append(entry)

(OUTPUT / "probe-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
