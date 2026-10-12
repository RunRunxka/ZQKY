import pytest
from app.core.exceptions import AppError
from tests.analysis_support import AnalysisScene


async def test_loss_precedes_incomplete_and_four_score_states(tmp_path):
    scene = AnalysisScene(tmp_path)
    changes = {("p000", "i001"): ("missing", None), ("p001", "i000"): ("exempt", None),
               ("p001", "i001"): ("exempt", None), ("p001", "i002"): ("exempt", None),
               ("p003", "i001"): ("missing", None)}
    rid = scene.new_score(changes=changes)
    payload = scene.request().model_copy(update={"score_revision_id": rid})
    receipt = await scene.service.create_run("assessment", payload)
    await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    report = scene.service.read_ready_report(receipt.run_id)
    rows = {(r["participant"]["name"], r["knowledgePoint"]["knowledgePointId"]): r for r in report["students"]}
    assert (rows[("D", "k1")]["observation"], rows[("D", "k1")]["informationIncomplete"]) == ("needs_consolidation", True)
    assert rows[("A", "k1")]["observation"] == "incomplete"
    assert rows[("B", "k1")]["observation"] == "no_evidence" and rows[("B", "k1")]["stateCounts"] == {"recorded": 0, "missing": 0, "absent": 0, "exempt": 2}
    counts = report["selectionSnapshot"]["stateCounts"]
    assert counts == {"recorded": 4, "missing": 2, "absent": 3, "exempt": 3}
    k1 = next(r for r in report["classes"] if r["knowledgePoint"]["knowledgePointId"] == "k1")
    assert (k1["validCount"], k1["needsCount"], k1["incompleteCount"], k1["noEvidenceCount"]) == (2, 1, 4, 2)
    assert scene.service.list_report_rows(receipt.run_id, "evidence").total == 12


async def test_all_nonrecorded_has_null_ratio_and_no_full_credit(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept(ids=["p002"])
    await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    rows = scene.service.list_report_rows(receipt.run_id, "classes").items
    assert len(rows) == 2
    assert all(r.denominator == 0 and r.numerator == 0 and r.ratio is None and r.full_credit_count == 0 for r in rows)


async def test_explicit_one_attempt_per_student_no_auto_selection(tmp_path):
    scene = AnalysisScene(tmp_path)
    rid = scene.new_score(extra_attempt=True)
    invalid = scene.request().model_copy(update={"score_revision_id": rid, "selected_participant_ids": ["p000", "p-repeat"]})
    with pytest.raises(AppError) as fail:
        await scene.service.create_run("assessment", invalid)
    assert fail.value.details["issues"][0] == {"field": "selectedParticipantIds[1]", "row": 1, "code": "DUPLICATE_STUDENT_ATTEMPT", "message": "同学生只能选择一个人次。"}
    assert scene.count("analysis_runs") == 0
    chosen = invalid.model_copy(update={"selected_participant_ids": ["p-repeat", "p001"]})
    receipt = await scene.service.create_run("assessment", chosen)
    await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    report = scene.service.read_ready_report(receipt.run_id)
    assert {(p["participantId"], p["attemptNo"]) for p in report["participants"]} == {("p-repeat", 2), ("p001", 1)}
    assert report["selectionSnapshot"]["uniqueStudentCount"] == 2
    assert scene.service.list_report_rows(receipt.run_id, "evidence").total == 6


@pytest.mark.parametrize("bad", ["missing_cell", "over_max"])
async def test_corrupt_confirmed_matrix_never_becomes_empty_report(tmp_path, bad):
    scene = AnalysisScene(tmp_path)
    rid = scene.new_score(direct_bad=bad == "missing_cell", changes={("p000", "i000"): ("recorded", 201)} if bad == "over_max" else None)
    with pytest.raises(AppError) as failed:
        await scene.service.create_run("assessment", scene.request().model_copy(update={"score_revision_id": rid}))
    assert failed.value.status_code == 500 and failed.value.code == "ANALYSIS_SOURCE_CORRUPT"
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == 0


async def test_missing_asset_before_accept_is_error(tmp_path):
    scene = AnalysisScene(tmp_path)
    scene.assets.path_of(scene.image.blob_key).unlink()  # Only this new owned fixture's blob.
    with pytest.raises(AppError) as failure:
        await scene.accept()
    assert failure.value.status_code >= 400
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == 0
