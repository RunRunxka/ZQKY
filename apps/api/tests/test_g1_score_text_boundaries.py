"""G1/R04: authoritative score text is preserved or rejected before any write.

The command runner sets a fresh ZQKY_DATA_DIR before pytest imports conftest or
app.main. Each HTTP scene also uses explicit temporary Settings with no
credentials file. No listener, model, formal data, or previous QA fixture is used.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.scores.imports import parse_score_text
from app.services.tabular import read_score_sheet
from tests.scores_support import ScoresHarness, write_score_xlsx


# Keep the supported boundary explicit in the regression rather than importing
# the production limit: an accidental limit change must not weaken the oracle.
SUPPORTED_CHARS = 20_000
HEADER = ("学号", "姓名", "Q1", "Q2", "Q3", "总分", "出勤")
STANDARD_ROW = ("0001", "甲", "1", "2", "3", "6", "出勤")
METADATA_COLUMNS = ((0, "A"), (1, "B"), (2, "C"), (5, "F"), (6, "G"))
SCORE_TABLES = (
    "score_imports", "score_import_rows", "score_revisions",
    "student_item_scores", "score_revision_corrections",
)
_XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class G1ScoresHarness(ScoresHarness):
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = Path(tmp_path)
        self.settings = Settings(
            host="127.0.0.1", port=8001,
            allowed_origins=frozenset({"http://127.0.0.1:5174"}),
            env="test", data_dir=self.tmp_path / "data", credentials_file=None,
        )
        self.app = create_app(self.settings)
        self.db_path = self.settings.teaching_root / "teaching.sqlite3"
        self._client_context = None
        self.client = None  # type: ignore[assignment]


def _write_source(tmp_path: Path, kind: str, rows: list[list[Any]]) -> Path:
    if kind == "xlsx":
        return write_score_xlsx(tmp_path / "scores.xlsx", HEADER, rows)
    target = tmp_path / "scores.csv"
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    writer.writerows(rows)
    target.write_bytes(buffer.getvalue().encode("utf-8-sig"))
    return target


def _cache_formula_string(source: Path, address: str, value: str) -> Path:
    """Inject a string formula cache, as Excel's t='str' cached result.

    openpyxl does not calculate formulas. String caches are important here:
    testing only numeric float caches would not exercise the truncating helper.
    """
    rewritten = source.with_suffix(".cache.xlsx")
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(
        rewritten, "w", zipfile.ZIP_DEFLATED,
    ) as destination:
        for entry in original.infolist():
            content = original.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                tree = ElementTree.fromstring(content)
                cell = tree.find(f".//{{{_XLSX_NS}}}c[@r='{address}']")
                assert cell is not None
                assert cell.find(f"{{{_XLSX_NS}}}f") is not None
                cell.set("t", "str")
                cache = cell.find(f"{{{_XLSX_NS}}}v")
                if cache is None:
                    cache = ElementTree.SubElement(cell, f"{{{_XLSX_NS}}}v")
                cache.text = value
                content = ElementTree.tostring(tree, encoding="utf-8")
            destination.writestr(entry, content)
    source.write_bytes(rewritten.read_bytes())
    rewritten.unlink()
    return source


def _confirm(harness: ScoresHarness, scene, view: dict[str, Any], key: str):
    return harness.confirm_import(view["importId"], {
        "expectedImportRevision": view["revision"],
        "expectedAssessmentRevision": scene.assessment["revision"],
        "baseScoreRevisionId": view["baseScoreRevisionId"],
        "previewVersion": view["previewVersion"], "submissionId": key,
        **view["requiredAcknowledgements"],
    })


def _asset_bytes(harness: ScoresHarness) -> dict[str, bytes]:
    directory = harness.settings.assets_root / "blobs"
    return {path.name: path.read_bytes() for path in directory.glob("*") if path.is_file()}


def _assert_rejected_without_writes(
    harness: ScoresHarness, scene, source: Path, *,
    column: str, view: str, length: int, code: str = "TABLE_TOO_LARGE",
) -> None:
    # A pre-existing managed asset must survive failed uploads byte for byte.
    harness.app.state.asset_store.store_original(
        b"G1 existing original asset\x00\xff", media_type="application/octet-stream",
        original_name="existing-source.bin",
    )
    original = source.read_bytes()
    prior_assets = _asset_bytes(harness)
    prior_counts = {name: harness.count(name) for name in (
        *SCORE_TABLES, "file_assets", "command_submissions",
    )}
    prior_assessment = harness.assessment(scene.assessment["assessmentId"])
    response = harness.upload_scores(scene.assessment["assessmentId"], source)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["code"] == code
    assert body["requestId"] and body["retryable"] is False
    assert body["message"]
    details = body["details"]
    assert details == {
        "sheet": "成绩" if source.suffix == ".xlsx" else "CSV",
        "row": 2, "column": column, "address": f"{column}2",
        "view": view, "actualLength": length, "maxLength": SUPPORTED_CHARS,
    }
    # Rejected parsing must not create a preview, a score asset registration,
    # a successful submission, a revision, an audit, or a partial matrix.
    assert {name: harness.count(name) for name in prior_counts} == prior_counts
    assert all(harness.count(name) == 0 for name in SCORE_TABLES)
    assert harness.assessment(scene.assessment["assessmentId"]) == prior_assessment
    assert _asset_bytes(harness) == prior_assets
    assert source.read_bytes() == original


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
@pytest.mark.parametrize("column_index,column", METADATA_COLUMNS)
def test_all_score_columns_reject_overlong_raw_values_before_writes(
    tmp_path: Path, kind: str, column_index: int, column: str,
) -> None:
    # The original C2 exploit becomes a finite exact 1 if its last 1 is dropped.
    value = "1." + "0" * 19_998 + "1"
    assert len(value) == SUPPORTED_CHARS + 1
    assert parse_score_text(value, max_units=200).code == "SCORE_CELL_INVALID"
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-overlong")
        row = list(STANDARD_ROW)
        row[column_index] = value
        source = _write_source(tmp_path, kind, [row])
        _assert_rejected_without_writes(
            harness, scene, source, column=column,
            view="formula" if kind == "xlsx" else "csv", length=len(value),
        )


@pytest.mark.parametrize("column_index,column", METADATA_COLUMNS)
@pytest.mark.parametrize("view", ["formula", "cached"])
def test_formula_and_cached_views_share_the_authoritative_limit(
    tmp_path: Path, column_index: int, column: str, view: str,
) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-formula-long")
        row = list(STANDARD_ROW)
        long_value = "1." + "0" * 19_998 + "1"
        formula = "=" + "1" * SUPPORTED_CHARS if view == "formula" else "=1"
        row[column_index] = formula
        source = _write_source(tmp_path, "xlsx", [row])
        _cache_formula_string(
            source, f"{column}2", "1" if view == "formula" else long_value,
        )
        _assert_rejected_without_writes(
            harness, scene, source, column=column, view=view,
            length=SUPPORTED_CHARS + 1,
        )


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
@pytest.mark.parametrize("text,units", [
    ("0", 0), ("0.000000000000000000000000000000000000", 0),
    ("1.230000000000000000000000000000000000", 123),
    ("1." + "0" * 19_998, 100),
])
def test_supported_exact_text_is_preserved_and_confirmed_without_rounding(
    tmp_path: Path, kind: str, text: str, units: int,
) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-exact")
        row = list(STANDARD_ROW)
        row[2], row[5] = text, ""  # Total is optional; never derives item scores.
        source = _write_source(tmp_path, kind, [row])
        source_bytes = source.read_bytes()
        raw = read_score_sheet(source_bytes)[0].rows[1][2]
        assert raw.text == text and raw.cached_text == text
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 201, response.text
        view = response.json()
        original_asset = harness.app.state.asset_store.read(view["fileAsset"]["blobKey"])
        assert original_asset == source_bytes
        cell = next(cell for cell in harness.list_import_rows(view["importId"]).json()["items"][0]["cells"]
                    if cell["column"] == "C")
        assert cell["originalText"] == cell["originalCachedText"] == text
        assert cell["effectiveStatus"] == "recorded" and cell["scoreUnits"] == units
        confirmed = _confirm(harness, scene, view, "g1-exact-confirm")
        assert confirmed.status_code == 200, confirmed.text
        matrix_row = harness.score_matrix(confirmed.json()["revisionId"]).json()["rows"][0]
        assert [cell["scoreUnits"] for cell in matrix_row["cells"]] == [units, 200, 300]
        assert matrix_row["participant"]["totalUnits"] == units + 500
        assert harness.app.state.asset_store.read(view["fileAsset"]["blobKey"]) == source_bytes


@pytest.mark.parametrize("column_index,column", METADATA_COLUMNS)
def test_supported_formula_cache_is_preserved_for_identity_and_metadata(
    tmp_path: Path, column_index: int, column: str,
) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-cache")
        row = list(STANDARD_ROW)
        value = row[column_index]
        row[column_index] = "=G1_CACHED_SOURCE()"
        source = _write_source(tmp_path, "xlsx", [row])
        _cache_formula_string(source, f"{column}2", value)
        raw = read_score_sheet(source.read_bytes())[0].rows[1][column_index]
        assert raw.text == "=G1_CACHED_SOURCE()" and raw.cached_text == value
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 201, response.text
        view = response.json()
        # A/B identity cells are retained in original-row storage, while the
        # mapped public row projects only score/total/attendance cells.
        stored_row = harness.raw_rows(
            "SELECT raw_cells_json FROM score_import_rows WHERE import_id=? AND row_no=2",
            (view["importId"],),
        )[0]
        stored = next(cell for cell in json.loads(stored_row["raw_cells_json"])
                      if cell["column"] == column)
        assert stored["text"] == "=G1_CACHED_SOURCE()"
        assert stored["cachedText"] == value
        if column not in {"A", "B"}:
            cell = next(cell for cell in harness.list_import_rows(view["importId"]).json()["items"][0]["cells"]
                        if cell["column"] == column)
            assert cell["originalText"] == "=G1_CACHED_SOURCE()"
            assert cell["originalCachedText"] == value
        confirmed = _confirm(harness, scene, view, "g1-cache-confirm")
        assert confirmed.status_code == 200, confirmed.text
        matrix_row = harness.score_matrix(confirmed.json()["revisionId"]).json()["rows"][0]
        assert [cell["scoreUnits"] for cell in matrix_row["cells"]] == [100, 200, 300]
        assert matrix_row["participant"]["studentNo"] == "0001"
        assert harness.app.state.asset_store.read(view["fileAsset"]["blobKey"]) == source.read_bytes()


def test_exact_formula_cache_at_limit_keeps_all_trailing_zeroes(tmp_path: Path) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-cache-boundary")
        text = "1." + "0" * 19_998
        row = list(STANDARD_ROW)
        row[2] = "=1"
        source = _write_source(tmp_path, "xlsx", [row])
        _cache_formula_string(source, "C2", text)
        raw = read_score_sheet(source.read_bytes())[0].rows[1][2]
        assert raw.text == "=1" and raw.cached_text == text
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 201, response.text
        view = response.json()
        cell = next(cell for cell in harness.list_import_rows(view["importId"]).json()["items"][0]["cells"]
                    if cell["column"] == "C")
        assert cell["originalText"] == "=1" and cell["originalCachedText"] == text
        assert cell["scoreUnits"] == 100
        confirmed = _confirm(harness, scene, view, "g1-cache-boundary-confirm")
        assert confirmed.status_code == 200, confirmed.text
        assert harness.score_matrix(confirmed.json()["revisionId"]).json()["rows"][0]["cells"][0]["scoreUnits"] == 100


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
def test_exact_number_above_supported_length_is_explicitly_rejected(tmp_path: Path, kind: str) -> None:
    # Numerical validity does not bypass the reader's documented support limit.
    value = "1." + "0" * 19_999
    assert parse_score_text(value, max_units=200).units == 100
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-valid-overlong")
        row = list(STANDARD_ROW)
        row[2] = value
        source = _write_source(tmp_path, kind, [row])
        _assert_rejected_without_writes(
            harness, scene, source, column="C",
            view="formula" if kind == "xlsx" else "csv", length=len(value),
        )


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
def test_nonzero_tail_within_supported_boundary_is_invalid_not_rounded(
    tmp_path: Path, kind: str,
) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-nonzero-tail")
        text = "1." + "0" * 19_997 + "1"
        assert len(text) == SUPPORTED_CHARS
        row = list(STANDARD_ROW)
        row[2] = text
        source = _write_source(tmp_path, kind, [row])
        assert read_score_sheet(source.read_bytes())[0].rows[1][2].text == text
        prior_assets = _asset_bytes(harness)
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "SCORE_CELL_INVALID"
        assert any(issue.get("row") == 2 and issue.get("column") == "C"
                   for issue in body["details"]["issues"])
        assert all(harness.count(table) == 0 for table in SCORE_TABLES)
        assert _asset_bytes(harness) == prior_assets


@pytest.mark.parametrize("kind", ["xlsx", "csv"])
def test_four_states_and_complete_total_rule_survive_text_limit_guard(
    tmp_path: Path, kind: str,
) -> None:
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(
            tag="g1-four-states",
            students=(("甲", "0001"), ("乙", "0002"), ("丙", "0003"), ("丁", "0004")),
            attendance={"0003": "absent", "0004": "exempt"},
        )
        source = _write_source(tmp_path, kind, [
            ["0001", "甲", "0", "3", "5", "8.0000", "出勤"],
            ["0002", "乙", "2", "3", "", "", "出勤"],
            ["0003", "丙", "缺考", "", "", "", "缺考"],
            ["0004", "丁", "免考", "", "", "", "免考"],
        ])
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 201, response.text
        view = response.json()
        assert view["missingCellCount"] == 1
        confirmed = _confirm(harness, scene, view, "g1-four-confirm")
        assert confirmed.status_code == 200, confirmed.text
        matrix = harness.score_matrix(confirmed.json()["revisionId"]).json()
        rows = {row["participant"]["studentNo"]: row for row in matrix["rows"]}
        assert [cell["status"] for cell in rows["0001"]["cells"]] == ["recorded"] * 3
        assert [cell["scoreUnits"] for cell in rows["0001"]["cells"]] == [0, 300, 500]
        assert rows["0001"]["participant"]["totalUnits"] == 800
        assert [cell["status"] for cell in rows["0002"]["cells"]] == ["recorded", "recorded", "missing"]
        for number, status in (("0003", "absent"), ("0004", "exempt")):
            assert [cell["status"] for cell in rows[number]["cells"]] == [status] * 3
        assert all(rows[number]["participant"]["totalUnits"] is None
                   for number in ("0002", "0003", "0004"))
        assert harness.count("student_item_scores") == 12


def test_oversized_csv_parser_field_returns_contract_error_without_writes(tmp_path: Path) -> None:
    """O1 was an observation; touched parser now returns a structured rejection."""
    with G1ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="g1-csv-parser")
        source = tmp_path / "parser-limit.csv"
        source.write_bytes(("学号,姓名,Q1,Q2,Q3,备注\r\n0001,甲,1,2,3," + "x" * 131_073 + "\r\n").encode("utf-8"))
        original = source.read_bytes()
        prior_assets = _asset_bytes(harness)
        prior_asset_count = harness.count("file_assets")
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] == "TABLE_PARSE_FAILED"
        assert body["requestId"] and body["retryable"] is False
        assert body["details"]["sheet"] == "CSV" and body["details"]["row"] == 2
        assert "column" not in body["details"]
        assert all(harness.count(table) == 0 for table in SCORE_TABLES)
        assert harness.count("file_assets") == prior_asset_count
        assert _asset_bytes(harness) == prior_assets and source.read_bytes() == original
