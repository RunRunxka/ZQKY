"""Read-only B3 score review: all state confined to a temporary data root."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "api"))


def show(label, value):
    print(json.dumps({"probe": label, "result": value}, ensure_ascii=False))


def confirm(h, scene, view, submission="confirm", missing=None):
    request = {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": None,
        "previewVersion": view["previewVersion"],
        "submissionId": submission,
        "absences": [],
        "missing": missing,
    }
    response = h.confirm_import(view["importId"], request)
    return response


with tempfile.TemporaryDirectory(prefix="zqky-b3-score-review-") as temporary:
    temp = Path(temporary)
    # Must precede ALL imports that transitively import app.main.
    os.environ["ZQKY_DATA_DIR"] = str(temp / "import-default")
    from fastapi.testclient import TestClient
    from tests.scores_support import ScoresHarness, write_score_xlsx
    from app.services.tabular import read_csv, read_score_sheet

    with ScoresHarness(temp / "scene") as h:
        scene = h.create_scene(tag="header", students=[("甲", "0001"), ("乙", "0002")])
        # Two-level export: row 1 is the grouping header, row 2 the physical leaf header.
        sheet = write_score_xlsx(temp / "header.xlsx", ["学号", "姓名", "小题得分", "", ""],
                                 [["学号", "姓名", "Q1", "Q2", "Q3"],
                                  ["0001", "甲", 1, 2, 3], ["0002", "乙", 2, 3, 4]])
        upload = h.upload_scores(scene.assessment["assessmentId"], sheet)
        assert upload.status_code == 201, upload.text
        view = upload.json()
        mapping = dict(view["mapping"])
        mapping["headerRow"] = 2
        mapping["itemColumns"] = [{"itemId": f"it-header-{i}", "column": col} for i, col in enumerate(("C", "D", "E"), 1)]
        patch = h.patch_import(view["importId"], {"expectedRevision": view["revision"], "mapping": mapping})
        assert patch.status_code == 200, patch.text
        rows = h.list_import_rows(view["importId"]).json()
        published = confirm(h, scene, patch.json(), submission="header-confirm")
        show("header_row_change", {"patchStatus": patch.status_code, "mappingHeaderRow": patch.json()["mapping"]["headerRow"],
              "dataRowNos": [r["rowNo"] for r in rows["items"]], "confirmStatus": published.status_code,
              "matrix": h.score_matrix(published.json()["revisionId"]).json()["rows"] if published.status_code == 200 else published.json()})

        scene = h.create_scene(tag="case", students=[("丙", "0003")])
        sheet = write_score_xlsx(temp / "case.xlsx", ["学号", "姓名", "Q1", "Q2", "Q3"], [["0003", "丙", 1, 2, 3]])
        view = h.upload_scores(scene.assessment["assessmentId"], sheet).json()
        mapping = dict(view["mapping"])
        mapping["itemColumns"][0]["column"] = "C"
        mapping["itemColumns"][1]["column"] = "c"
        patch = h.patch_import(view["importId"], {"expectedRevision": view["revision"], "mapping": mapping})
        published = confirm(h, scene, patch.json(), submission="case-confirm") if patch.status_code == 200 else None
        show("case_duplicate_column", {"patchStatus": patch.status_code, "patchBody": patch.json(),
              "confirmStatus": published.status_code if published else None,
              "matrix": h.score_matrix(published.json()["revisionId"]).json()["rows"] if published and published.status_code == 200 else None})

        scene = h.create_scene(tag="correction", students=[("丁", "0004")])
        sheet = write_score_xlsx(temp / "correction.xlsx", ["学号", "姓名", "Q1", "Q2", "Q3"], [["0004", "丁", 1, 2, 3]])
        view = h.upload_scores(scene.assessment["assessmentId"], sheet).json()
        published = confirm(h, scene, view, submission="correction-confirm")
        assert published.status_code == 200, published.text
        base = published.json()
        matrix = h.score_matrix(base["revisionId"]).json()
        # Reuse the already-started application, without entering a second lifespan/data lock.
        client = TestClient(h.app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False)
        results = []
        for text in ("", "缺考", "免考"):
            request = {"baseScoreRevisionId": base["revisionId"], "expectedAssessmentRevision": base["assessmentRevision"],
                "submissionId": "correct-" + (text or "blank"), "reason": "review invalid input",
                "corrections": [{"participantId": scene.participant_id("0004"), "itemId": matrix["items"][0]["itemId"],
                                 "status": "recorded", "scoreText": text}]}
            response = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-revisions/correct', json=request)
            results.append({"scoreText": text, "httpStatus": response.status_code, "body": response.text})
        show("recorded_nonnumeric_correction", {"results": results,
            "revisionCountAfter": h.score_revisions(scene.assessment["assessmentId"]).json()["total"]})

        gb = "学号,姓名,Q1,Q2,Q3\r\n0005,戊,缺考,缺考,缺考\r\n".encode("gb18030")
        scene = h.create_scene(tag="gb", students=[("戊", "0005")])
        path = temp / "gb.csv"
        path.write_bytes(gb)
        upload = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
            files={"file": ("gb.csv", gb, "text/csv")})
        show("gb18030_csv", {"sharedTableHeaders": read_csv(gb).headers,
            "scoreReaderFirstRow": [c.text for c in read_score_sheet(gb)[0].rows[0]],
            "uploadStatus": upload.status_code, "uploadBody": upload.text})

        unknown_headers = "身份代号,学生称呼,Q1,Q2,Q3\r\n0005,戊,1,2,3\r\n".encode("utf-8")
        upload = client.post(f'/api/v1/assessments/{scene.assessment["assessmentId"]}/score-imports',
            files={"file": ("unknown-identity.csv", unknown_headers, "text/csv")})
        show("unknown_identity_headers", {"uploadStatus": upload.status_code, "uploadBody": upload.text,
            "headers": [c.text for c in read_score_sheet(unknown_headers)[0].rows[0]]})
