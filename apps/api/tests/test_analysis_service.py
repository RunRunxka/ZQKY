import sqlite3
import pytest
from app.contracts.b4 import NoteRequest
from app.core.exceptions import AppError
from app.services.analysis.service import AnalysisService
from tests.analysis_support import AnalysisScene


async def test_literal_full_report_and_rich_evidence(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    report = scene.service.read_ready_report(receipt.run_id)
    rows = {(r["participant"]["name"], r["knowledgePoint"]["knowledgePointId"]): r for r in report["students"]}
    expected = {("A", "k1"): ("needs_consolidation", False, 900), ("A", "k2"): ("needs_consolidation", False, 900),
                ("B", "k1"): ("full_credit", False, None), ("B", "k2"): ("incomplete", True, None),
                ("C", "k1"): ("no_evidence", True, None), ("C", "k2"): ("no_evidence", True, None),
                ("D", "k1"): ("needs_consolidation", False, 800), ("D", "k2"): ("full_credit", False, 800)}
    assert {k: (v["observation"], v["informationIncomplete"], v["totalScoreUnits"]) for k, v in rows.items()} == expected
    classes = {r["knowledgePoint"]["knowledgePointId"]: r for r in report["classes"]}
    assert (classes["k1"]["numerator"], classes["k1"]["denominator"], classes["k1"]["ratio"]) == (2, 3, 2 / 3)
    assert (classes["k2"]["numerator"], classes["k2"]["denominator"], classes["k2"]["ratio"]) == (1, 3, 1 / 3)
    assert classes["k1"]["incompleteCount"] == 1 and classes["k2"]["incompleteCount"] == 2
    assert all(p["className"] is None and p["classNameNote"] == "该成绩未记录班名" for p in report["participants"])
    evidence = scene.service.list_report_rows(receipt.run_id, "evidence", limit=200)
    assert evidence.total == len(evidence.items) == 12
    zero = [e for e in evidence.items if e.score_units == 0]
    assert len(zero) == 1 and zero[0].status == "recorded"
    assert len([e for e in evidence.items if e.status == "absent"]) == 3
    assert all(e.content["stemBlocks"] == scene.rich["stemBlocks"] and e.shared_materials == scene.rich["sharedMaterials"] and e.assets == scene.rich["assets"] and e.content["sourceBlocks"][0]["blockId"] == "shared" for e in evidence.items)
    assert all(e.practice_revision_id is None and e.practice_item_id is None for e in evidence.items)
    assert len(report["originalQuestionContents"]) == 3 and report["originalQuestionRevisionIds"] == []
    assert all("type" not in c for c in report["originalQuestionContents"])
    assert "participantId" not in str(report["originalQuestionContents"])
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE classes SET name='后来班名' WHERE id='class'")
        conn.execute("UPDATE students SET name='后来名字' WHERE id='s000'")
        conn.execute("UPDATE papers SET title='后来卷名',status='archived' WHERE id='paper'")
        conn.execute("UPDATE assessments SET active_score_revision_id=NULL WHERE id='assessment'")
    assert scene.service.read_ready_report(receipt.run_id) == report
    # A separately fixed paper that actually recorded its type retains it. Only
    # unknown source types are omitted; no other placeholder or inference.
    known_scene = AnalysisScene(tmp_path / "known-source", known_type="short_answer")
    known = await known_scene.ready()
    assert all(c["type"] == "short_answer" for c in known_scene.service.read_ready_report(known.run_id)["originalQuestionContents"])


@pytest.mark.parametrize("ids,code", [(["p000", "p000"], "DUPLICATE_PARTICIPANT"), (["missing"], "PARTICIPANT_NOT_IN_REVISION")])
async def test_invalid_selection_has_position_and_no_half_accept(tmp_path, ids, code):
    scene = AnalysisScene(tmp_path)
    with pytest.raises(AppError) as failure:
        await scene.accept(ids=ids)
    assert failure.value.status_code == 422 and failure.value.details["issues"][0]["code"] == code
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == scene.count("command_submissions") == 0


async def test_replay_precedes_asset_io_and_same_input_reuses_failed_job(tmp_path, monkeypatch):
    scene = AnalysisScene(tmp_path)
    first = await scene.accept()
    monkeypatch.setattr(scene.service, "_verify_assets", lambda _: (_ for _ in ()).throw(AssertionError("must replay first")))
    replay = await scene.accept(ids=list(reversed(scene.participant_ids)))
    assert replay.replayed and replay.run_id == first.run_id and replay.job == first.job
    with pytest.raises(AppError) as failure:
        await scene.accept(ids=scene.participant_ids[:1])
    assert failure.value.code == "SUBMISSION_CONFLICT"
    monkeypatch.undo()
    lease = scene.store.claim(first.job.job_id)
    scene.store.fail_if_current_lease(first.job.job_id, lease, code="TEST_FAIL", message="故障")
    reused = await scene.accept(submission="s2")
    assert reused.reused and not reused.replayed and reused.run_id == first.run_id and reused.job.state == "failed"
    assert len(scene.engine.accepted) == 1
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == 1


async def test_accept_fault_rolls_back_run_job_and_submission(tmp_path, monkeypatch):
    scene = AnalysisScene(tmp_path)
    original = scene.service.repo.create_in
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected accept failure")
    monkeypatch.setattr(scene.service.repo, "create_in", fail)
    with pytest.raises(RuntimeError):
        await scene.accept()
    assert scene.count("analysis_runs") == scene.count("workflow_jobs") == scene.count("command_submissions") == 0


async def test_notes_ready_append_replay_and_foreign_filters(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError, match="尚未完成"):
        scene.service.list_report_rows(receipt.run_id, "evidence")
    with pytest.raises(AppError) as notready:
        scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n0", note="先备注"))
    assert notready.value.code == "REPORT_NOT_READY"
    await scene.engine.run_job("teaching", receipt.job.job_id, scene.service.execute_job)
    one = scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n1", participantId="p000", knowledgePointId="k1", note="待教师判断具体错因"))
    assert scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n1", participantId="p000", knowledgePointId="k1", note="待教师判断具体错因")).replayed
    scene.service.add_note(receipt.run_id, NoteRequest(submissionId="n2", note="追加记录"))
    assert scene.service.list_notes(receipt.run_id).total == 2
    for kwargs in ({"class_id": "other"}, {"participant_id": "other"}, {"knowledge_point_id": "other"}):
        with pytest.raises(AppError) as failed:
            scene.service.list_report_rows(receipt.run_id, "students", **kwargs)
        assert failed.value.code == "ANALYSIS_FILTER_INVALID"
    with pytest.raises(AppError) as blank:
        scene.service.add_note(receipt.run_id, NoteRequest(submissionId="blank", note="  "))
    assert blank.value.status_code == 422
    with pytest.raises(AppError) as owner:
        scene.service.read_ready_report(receipt.run_id, owner_id="other")
    assert owner.value.status_code == 404
    with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
        with scene.catalog.write_transaction() as conn:
            conn.execute("UPDATE analysis_teacher_notes SET note='rewrite' WHERE id=?", (one.note_id,))


async def test_database_seal_rejects_all_result_dml(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    for sql in ("UPDATE analysis_runs SET input_json='{}'", "UPDATE analysis_runs SET report_ready=0,ready_at=NULL", "DELETE FROM analysis_runs"):
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            with scene.catalog.write_transaction() as conn:
                conn.execute(sql)
    for table in ("analysis_participants", "analysis_item_snapshots", "analysis_student_results", "analysis_class_results", "analysis_evidence"):
        for sql in (f"UPDATE {table} SET run_id=run_id", f"DELETE FROM {table}", f"INSERT INTO {table} SELECT * FROM {table}"):
            with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
                with scene.catalog.write_transaction() as conn:
                    conn.execute(sql)
    assert scene.service.get_run(receipt.run_id).report_ready
