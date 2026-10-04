import copy
import pytest
from app.core.exceptions import AppError
from app.services.lesson_generation.validation import normalize_model_output, stable_ids
from tests.lesson_generation_support import Scene, reply


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


def test_process_aliases_and_fixed_sources(scene):
    prepared = scene.prepare()
    result = normalize_model_output(reply(), prepared.frozen_input)
    ids = stable_ids(prepared.frozen_input)
    assert [x["id"] for x in result["patch"]["process"]] == [ids[f"new:N{n}"] for n in range(1,5)]
    assert result["budget"]["durationMinutes"] == 40
    assert result["generationSource"]["analysis"]["scoreRevisionId"] == "score-r"
    assert result["generationSource"]["analysis"]["paperRevisionId"] == "paper-r"
    assert result["generationSource"]["analysis"]["className"] is None
    assert result["generationSource"]["analysis"]["classNameNote"] == "该成绩未记录班名"
    assert result["evidence"][0]["text"] == scene.verified.evidence[0].text
    assert scene.service.validate_for_apply(result, prepared.frozen_input) == result


@pytest.mark.parametrize("mutation", ["teacher", "path", "unknown", "null", "fake_process", "duplicate_process", "missing_phase",
    "decimal_minutes", "bool_minutes", "zero_minutes", "sum", "duration", "fake_kp", "duplicate_kp", "uncovered_kp",
    "fake_evidence", "empty_check", "empty_stage", "extra_process", "few_process", "long_stage", "long_activity", "surrogate"])
def test_rejects_illegal_model_candidate(scene, mutation):
    prepared, value = scene.prepare(), reply()
    patch, budget = value["patch"], value["budget"]
    if mutation == "teacher": patch["reflection"] = "overwrite"
    elif mutation == "path": patch["process[0].design"] = "overwrite"
    elif mutation == "unknown": value["extra"] = True
    elif mutation == "null": patch["exercises"] = None
    elif mutation == "fake_process": patch["process"][0]["id"] = "secret-old-id"
    elif mutation == "duplicate_process": patch["process"][1]["id"] = patch["process"][0]["id"]
    elif mutation == "missing_phase": budget["stages"][0]["phase"] = "exploration"
    elif mutation == "decimal_minutes": budget["stages"][0]["minutes"] = 10.0
    elif mutation == "bool_minutes": budget["stages"][0]["minutes"] = True
    elif mutation == "zero_minutes": budget["stages"][0]["minutes"] = 0
    elif mutation == "sum": budget["stages"][0]["minutes"] = 11
    elif mutation == "duration": budget["durationMinutes"] = 41
    elif mutation == "fake_kp": budget["stages"][0]["knowledgeAliases"] = ["private-kp"]
    elif mutation == "duplicate_kp": budget["stages"][0]["knowledgeAliases"] = ["K1","K1"]
    elif mutation == "uncovered_kp":
        for stage in budget["stages"]: stage["knowledgeAliases"] = ["K1"]
    elif mutation == "fake_evidence": budget["stages"][0]["evidenceAliases"] = ["fake-ref"]
    elif mutation == "empty_check": budget["stages"][0]["check"] = " "
    elif mutation == "empty_stage": patch["process"][0]["stage"] = " "
    elif mutation == "extra_process": patch["process"][0]["minutes"] = 10
    elif mutation == "few_process": patch["process"] = patch["process"][:3]
    elif mutation == "long_stage": patch["process"][0]["stage"] = "😀"*61
    elif mutation == "long_activity": budget["stages"][0]["activity"] = "😀"*2001
    elif mutation == "surrogate": patch["exercises"] = "\ud800"
    with pytest.raises(AppError) as error:
        normalize_model_output(value, prepared.frozen_input)
    assert error.value.code == "LESSON_PROPOSAL_INVALID"


@pytest.mark.parametrize("mutation", ["fake_ref", "changed_source", "bad_budget", "teacher", "unrecognized_id", "duplicate_stage"])
def test_apply_validator_rechecks_full_stored_candidate(scene, mutation):
    frozen = scene.prepare().frozen_input
    value = normalize_model_output(reply(), frozen)
    if mutation == "fake_ref": value["evidence"][0]["referenceId"] = "fake"
    elif mutation == "changed_source": value["generationSource"]["analysis"]["inputHash"] = "changed"
    elif mutation == "bad_budget": value["budget"]["stages"][0]["minutes"] = 9
    elif mutation == "teacher": value["patch"]["title"] = "forbidden"
    elif mutation == "unrecognized_id": value["patch"]["process"][0]["id"] = "random"
    else: value["budget"]["stages"][1]["processId"] = value["budget"]["stages"][0]["processId"]
    with pytest.raises(AppError):
        scene.service.validate_for_apply(value, frozen)


def test_omitted_string_suggestion_allowed_and_old_safe_id_preserved(scene):
    frozen, value = scene.prepare().frozen_input, reply()
    del value["patch"]["exercises"]
    value["patch"]["process"][0]["id"] = "P1"
    value["budget"]["stages"][0]["processId"] = "P1"
    normalized = normalize_model_output(value,frozen)
    assert normalized["patch"]["exercises"] is None
    assert normalized["patch"]["process"][0]["id"] == "old-safe"
