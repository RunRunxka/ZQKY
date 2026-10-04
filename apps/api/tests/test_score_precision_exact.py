"""Exact score units must not depend on Decimal's ambient arithmetic context."""

from decimal import localcontext
from pathlib import Path

import pytest

from app.services.scores.imports import parse_score_text
from tests.scores_support import SAMPLE_HEADER, ScoresHarness, write_score_xlsx


@pytest.mark.parametrize("precision", [2, 28])
@pytest.mark.parametrize("text,units", [
    ("0", 0), ("0e-9999999", 0), ("1e-2", 1),
    ("1.23000000000000000000000000000", 123), ("5.00", 500),
])
def test_exact_units_ignore_context_precision(text: str, units: int, precision: int) -> None:
    with localcontext() as context:
        context.prec = precision
        parsed = parse_score_text(text, max_units=500)
    assert (parsed.status, parsed.units, parsed.code) == ("recorded", units, None)


@pytest.mark.parametrize("text,code", [
    ("1e9999999", "SCORE_CELL_OVER_MAX"),
    ("1e-9999999", "SCORE_CELL_INVALID"),
    ("1.000000000000000000000000000001", "SCORE_CELL_INVALID"),
    ("1.23000000000000000000000000001", "SCORE_CELL_INVALID"),
    ("5.000000000000000000000000000001", "SCORE_CELL_OVER_MAX"),
])
def test_extreme_exponents_and_coefficients_reject_exactly(text: str, code: str) -> None:
    parsed = parse_score_text(text, max_units=500)
    assert parsed.code == code
    assert parsed.units is None


@pytest.mark.parametrize("text", [
    "1e9999999", "1e-9999999", "1.000000000000000000000000000001",
    "1.23000000000000000000000000001",
])
def test_upload_rejects_at_real_coordinate_without_business_writes(
    tmp_path: Path, text: str,
) -> None:
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag="precision", students=[("甲", "0001")])
        source = write_score_xlsx(tmp_path / "precision.xlsx", SAMPLE_HEADER,
                                  [["0001", "甲", text, 2, 3]])
        response = harness.upload_scores(scene.assessment["assessmentId"], source)
        assert response.status_code == 422, response.text
        body = response.json()
        assert body["code"] in {"SCORE_CELL_INVALID", "SCORE_CELL_OVER_MAX"}
        assert any(issue.get("row") == 2 and issue.get("column") == "C"
                   for issue in body["details"]["issues"])
        assert harness.count("score_imports") == 0
        assert harness.count("score_revisions") == 0
        assert harness.count("student_item_scores") == 0
