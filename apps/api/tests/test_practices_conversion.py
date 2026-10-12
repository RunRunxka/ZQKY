import json
import io
import pytest
from app.contracts import b4
from app.core.exceptions import AppError
from tests.practices_support import PracticesScene


@pytest.fixture
async def scene(tmp_path):
    value=await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def reviewed(scene):
    return scene.review(scene.save(scene.create_set(),[scene.item(scene.question(rich=scene.rich()))]))


async def test_convert_real_same_transaction_paper_source_and_mapping_replay(scene):
    practice=reviewed(scene)
    result=scene.conversion(practice)
    assert scene.conversion(practice).replayed
    detail=scene.assessments.get_assessment(result.assessment_id)
    assert detail.assessment.assessment_type=="practice" and detail.participants[0].name_snapshot=="A"
    with scene.catalog.read_connection() as conn:
        revision=conn.execute("SELECT * FROM paper_revisions WHERE id=?",(result.paper_revision_id,)).fetchone()
        assert revision["state"]=="confirmed" and revision["source_file_id"] is None and revision["source_practice_revision_id"]==practice.current_revision.practice_revision_id
        mapped=conn.execute("SELECT p.content_json AS pc,p.max_score_units AS ps,i.content_json AS ic,i.max_score_units AS isc,i.source_locator_json FROM practice_paper_item_mappings m JOIN practice_items p ON p.id=m.practice_item_id JOIN paper_items i ON i.id=m.paper_item_id WHERE m.conversion_id=?",(result.conversion_id,)).fetchall()
        assert len(mapped)==len(practice.current_revision.items)
        assert all(x["pc"]==x["ic"] and x["ps"]==x["isc"] for x in mapped)
        assert json.loads(mapped[0]["source_locator_json"])["practiceItemId"]==practice.current_revision.items[0].practice_item_id
    scene.questions.archive_question(practice.current_revision.items[0].question_id)
    assert scene.conversion(practice).replayed


@pytest.mark.parametrize("failure",["bad-date","nonmember","duplicate-attempt","after-t30"])
async def test_convert_zero_half_objects_any_error(scene,monkeypatch,failure):
    practice=reviewed(scene)
    baseline={t:scene.count(t) for t in ("papers","paper_revisions","paper_items","assessments","practice_conversions","practice_paper_item_mappings","file_assets","command_submissions")}
    body=dict(submissionId="fail",title="练习施测",heldOn="2026-10-02",classIds=["class"],participants=[dict(studentId="s000",classId="class")])
    if failure=="bad-date":body["heldOn"]="2026-99-99"
    if failure=="nonmember":body["participants"][0]["studentId"]="unknown"
    if failure=="duplicate-attempt":body["participants"]*=2
    if failure=="after-t30":
        original=scene.assessments.create_in
        def fail(conn,payload):
            original(conn,payload)
            raise RuntimeError("injected after T30")
        monkeypatch.setattr(scene.assessments,"create_in",fail)
    with pytest.raises((AppError,RuntimeError)):
        scene.service.convert(practice.practice_set_id,practice.current_revision.practice_revision_id,b4.PracticeConversionRequest(**body))
    assert {t:scene.count(t) for t in baseline}==baseline


async def test_fixed_revision_conversion_archived_kp_blocks_new_but_replays(scene):
    practice=reviewed(scene)
    result=scene.conversion(practice)
    with scene.knowledge.write_transaction() as conn:conn.execute("UPDATE knowledge_points SET status='archived' WHERE id='k1'")
    assert scene.conversion(practice).conversion_id==result.conversion_id
    with pytest.raises(AppError) as error:scene.conversion(practice,submission="new-conversion")
    assert error.value.code=="KNOWLEDGE_ARCHIVED"


async def test_new_analysis_return_lineage_real_keys_not_strings(scene):
    practice=reviewed(scene)
    result=scene.conversion(practice)
    detail=scene.assessments.get_assessment(result.assessment_id)
    participant=detail.participants[0]
    item=practice.current_revision.items[0]
    with scene.catalog.read_connection() as conn:
        leaf=conn.execute("SELECT * FROM paper_items WHERE paper_revision_id=? AND is_scored=1",(result.paper_revision_id,)).fetchone()
    from openpyxl import Workbook
    from app.services.scores.service import build_score_service
    from app.services.papers.reader import ConfirmedPaperReaderAdapter
    from app.contracts.scores import ScoreImportConfirmRequest
    scores=build_score_service(scene.catalog,asset_store=scene.assets,file_assets=scene.service.file_assets,assessment_service=scene.assessments,
        paper_reader=ConfirmedPaperReaderAdapter(scene.catalog),publication_coordinator=scene.coordinator)
    workbook=Workbook();sheet=workbook.active
    sheet.append(["学号","姓名",leaf["question_no"]]);sheet.append([participant.student_no_snapshot,participant.name_snapshot,0])
    data=io.BytesIO();workbook.save(data)
    imported=scores.create_score_import(result.assessment_id,file_name="return.xlsx",content=data.getvalue())
    confirmed=scores.confirm_score_import(imported.import_id,ScoreImportConfirmRequest(submissionId="return-score",expectedImportRevision=imported.revision,
        expectedAssessmentRevision=detail.assessment.revision,previewVersion=imported.preview_version,baseScoreRevisionId=None))
    reader=scene.analysis_scene.service
    receipt=await reader.create_run(result.assessment_id,b4.AnalysisCreateRequest(submissionId="return-analysis",scoreRevisionId=confirmed.revision_id,selectedParticipantIds=[participant.participant_id],ruleCode="any_loss_v1"))
    assert (await reader.engine.run_job("teaching",receipt.job.job_id,reader.execute_job)).state=="succeeded"
    report=reader.read_ready_report(receipt.run_id)
    assert report["originalQuestionRevisionIds"]==[item.question_revision_id]
    evidence=reader.list_report_rows(receipt.run_id,"evidence",participant_id=participant.participant_id)
    assert evidence.items[0].practice_item_id==item.practice_item_id
    assert evidence.items[0].practice_revision_id==practice.current_revision.practice_revision_id


@pytest.mark.parametrize("tamper",["duplicate-source-leaf","wrong-kp","wrong-qno","wrong-qrev","wrong-ordinal","wrong-content"])
async def test_conversion_database_source_gate_rejects_tamper_without_half_objects(scene,monkeypatch,tamper):
    import sqlite3
    from app.repositories.teaching.papers import PaperRepository
    q1=scene.question("第一题");q2=scene.question("第二题")
    practice=scene.review(scene.save(scene.create_set(count=2),[scene.item(q1),scene.item(q2,ordinal=2)]))
    original=PaperRepository.confirm_revision_in
    def changed(repository,conn,revision_id):
        rows=conn.execute("SELECT * FROM paper_items WHERE paper_revision_id=? ORDER BY ordinal",(revision_id,)).fetchall()
        first=rows[0]
        if tamper=="duplicate-source-leaf":
            locator=json.loads(rows[1]["source_locator_json"]);locator["practiceItemId"]=json.loads(first["source_locator_json"])["practiceItemId"]
            conn.execute("UPDATE paper_items SET source_locator_json=? WHERE id=?",(json.dumps(locator),rows[1]["id"]))
        elif tamper=="wrong-kp":
            conn.execute("UPDATE paper_item_knowledge SET knowledge_name_snapshot='tampered' WHERE item_id=?",(first["id"],))
        elif tamper=="wrong-qno":conn.execute("UPDATE paper_items SET question_no='wrong-no' WHERE id=?",(first["id"],))
        elif tamper=="wrong-qrev":conn.execute("UPDATE paper_items SET question_revision_id='wrong-revision' WHERE id=?",(first["id"],))
        elif tamper=="wrong-ordinal":conn.execute("UPDATE paper_items SET ordinal=99 WHERE id=?",(first["id"],))
        else:
            content=json.loads(first["content_json"]);content["stemBlocks"][0]["text"]="different question content"
            conn.execute("UPDATE paper_items SET content_json=? WHERE id=?",(json.dumps(content),first["id"]))
        original(repository,conn,revision_id)
    monkeypatch.setattr(PaperRepository,"confirm_revision_in",changed)
    baseline={t:scene.count(t) for t in ("papers","paper_revisions","paper_items","assessments","practice_conversions","file_assets","command_submissions")}
    with pytest.raises(sqlite3.IntegrityError):scene.conversion(practice)
    assert {t:scene.count(t) for t in baseline}==baseline


async def test_mapping_insert_failure_rolls_source_assessment_assets_and_submission(scene,monkeypatch):
    import sqlite3
    from contextlib import contextmanager
    practice=reviewed(scene)
    original=scene.catalog.write_transaction
    @contextmanager
    def guarded():
        with original() as conn:
            conn.set_authorizer(lambda action,table,*args:sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_INSERT and table=="practice_paper_item_mappings" else sqlite3.SQLITE_OK)
            yield conn
    monkeypatch.setattr(scene.catalog,"write_transaction",guarded)
    baseline={t:scene.count(t) for t in ("papers","paper_revisions","paper_items","assessments","practice_conversions","practice_paper_item_mappings","file_assets","command_submissions")}
    with pytest.raises(sqlite3.DatabaseError):scene.conversion(practice)
    assert {t:scene.count(t) for t in baseline}==baseline
