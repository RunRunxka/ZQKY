"""Implementer HTTP receipts for R04; originals remain in this new evidence folder."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="zqky-g1-score-receipts-"))
os.environ["ZQKY_DATA_DIR"] = str(TEMP_ROOT / "module-import-data")
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["ZQKY_ENV"] = "test"
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "api"))

from tests.test_g1_score_text_boundaries import (  # noqa: E402
    G1ScoresHarness, SCORE_TABLES, STANDARD_ROW, _asset_bytes,
    _cache_formula_string, _confirm, _write_source,
)

SOURCES = OUTPUT / "sources"
SOURCES.mkdir(exist_ok=True)
result = {"temporaryRoot": str(TEMP_ROOT), "scenarios": []}
long_value = "1." + "0" * 19_998 + "1"
for kind, view in (("xlsx", "formula"), ("csv", "csv"), ("xlsx", "cached")):
    tag = f"{kind}-{view}"
    root = TEMP_ROOT / tag
    root.mkdir()
    with G1ScoresHarness(root) as harness:
        scene = harness.create_scene(tag=f"receipt-{tag}")
        row = list(STANDARD_ROW)
        row[2] = "=1" if view == "cached" else long_value
        source = _write_source(root, kind, [row])
        if view == "cached":
            _cache_formula_string(source, "C2", long_value)
        preserved = SOURCES / f"{tag}.{kind}"
        shutil.copyfile(source, preserved)
        original_bytes = preserved.read_bytes()
        raw = {"length": len(long_value), "suffix": long_value[-12:]}
        if kind == "xlsx":
            with zipfile.ZipFile(preserved) as archive:
                xml = archive.read("xl/worksheets/sheet1.xml")
            (SOURCES / f"{tag}-sheet1.xml").write_bytes(xml)
            raw["worksheetXmlSha256"] = hashlib.sha256(xml).hexdigest()
        before = {table: harness.count(table) for table in (*SCORE_TABLES, "file_assets")}
        blobs_before = _asset_bytes(harness)
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        after = {table: harness.count(table) for table in before}
        receipt = {
            "id": tag, "status": response.status_code,
            "contentType": response.headers.get("content-type"),
            "body": response.json(), "before": before, "after": after,
            "noAssetByteChange": _asset_bytes(harness) == blobs_before,
            "sourceByteChange": source.read_bytes() != original_bytes,
            "source": str(preserved), "sourceSha256": hashlib.sha256(original_bytes).hexdigest(),
            "originalCell": raw,
        }
        assert response.status_code == 422 and before == after
        assert receipt["body"]["details"]["actualLength"] == 20_001
        assert receipt["body"]["details"]["view"] == view
        assert receipt["noAssetByteChange"] and not receipt["sourceByteChange"]
        result["scenarios"].append(receipt)

root = TEMP_ROOT / "supported-zero-tail"
root.mkdir()
with G1ScoresHarness(root) as harness:
    scene = harness.create_scene(tag="receipt-exact")
    value = "1." + "0" * 19_998
    row = list(STANDARD_ROW)
    row[2] = value
    source = _write_source(root, "xlsx", [row])
    preserved = SOURCES / "supported-zero-tail.xlsx"
    shutil.copyfile(source, preserved)
    uploaded = harness.upload_scores(scene.assessment["assessmentId"], source)
    assert uploaded.status_code == 201, uploaded.text
    view = uploaded.json()
    cells = harness.list_import_rows(view["importId"]).json()["items"][0]["cells"]
    cell = next(cell for cell in cells if cell["column"] == "C")
    assert cell["originalText"] == cell["originalCachedText"] == value
    confirmed = _confirm(harness, scene, view, "receipt-exact-confirm")
    assert confirmed.status_code == 200, confirmed.text
    matrix = harness.score_matrix(confirmed.json()["revisionId"]).json()
    assert [cell["scoreUnits"] for cell in matrix["rows"][0]["cells"]] == [100, 200, 300]
    blob_bytes = harness.app.state.asset_store.read(view["fileAsset"]["blobKey"])
    result["scenarios"].append({
        "id": "supported-zero-tail", "uploadStatus": uploaded.status_code,
        "confirmStatus": confirmed.status_code, "confirmBody": confirmed.json(),
        "matrix": matrix, "rawTextLength": len(value), "previewOriginalLength": len(cell["originalText"]),
        "source": str(preserved), "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "managedOriginalByteIdentical": blob_bytes == preserved.read_bytes(),
    })

(OUTPUT / "http-receipts.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"scenarios": len(result["scenarios"]), "temporaryRoot": str(TEMP_ROOT),
                  "output": str(OUTPUT / "http-receipts.json")}, ensure_ascii=False))
