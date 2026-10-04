"""B5 author boundaries: immutable history, original envelopes and true FKs."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from pydantic import ValidationError

from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from app.services.lesson_plans import LessonPlanService
from tests.lesson_plans_support import LessonScene, changed


@pytest.fixture
async def scene(tmp_path):
    value = await LessonScene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


def test_create_blank_v1_summary_and_history(scene):
    body = scene.create_request(content=dict(title="", totalLessons="", currentLessonNo="", lessonTypes=["new","new","review"],
        otherTypeText="", coreCompetencies="", keyPoints="", teachingDesign="", process=[], exercises="", reflection=""))
    lesson = scene.be.create_lesson(body)
    assert lesson["revision"] == 1 and lesson["currentRevision"]["data"]["lessonTypes"] == ["new","new","review"]
    assert lesson["currentRevision"]["reviewState"] == "unreviewed"
    assert scene.be.get_lesson(lesson["lessonPlanId"]) == lesson
    listing = scene.be.list_lessons(subject_id="math", class_id="class", limit=1)
    assert listing["total"] == 2 and len(listing["items"]) == 1
    assert "data" not in listing["items"][0] and "currentRevision" not in listing["items"][0]
    history = scene.be.list_revisions(lesson["lessonPlanId"])
    assert history["total"] == 1 and "data" not in history["items"][0]
    assert scene.be.get_revision(lesson["lessonPlanId"], lesson["currentRevisionId"]) == lesson["currentRevision"]
    assert scene.be.list_lessons(subject_id="unknown")["items"] == []
    assert scene.be.list_lessons(offset=100)["items"] == []


def test_import_preserves_exact_envelope_timestamp_excluded_from_replay(scene):
    local = dict(schemaVersion=1, revision=47, updatedAt="2026-10-03T10:11:12.123+08:00", data=scene.create_request().data.model_dump(by_alias=True))
    local["data"]["process"][0]["id"] = "旧稳定身份"
    body = lp.LessonImportRequest(submissionId="import", subjectId="math", classId="class", draft=local, context=scene.context())
    result = scene.be.import_local(body)
    assert result["currentRevision"]["importEnvelope"] == local
    assert result["revision"] == 1 and result["currentRevision"]["source"] == "import_local"
    second = lp.LessonImportRequest.model_validate({**body.model_dump(by_alias=True), "draft": {**local,"updatedAt":"2026-10-04T10:11:12Z"}})
    replay = scene.be.import_local(second)
    assert replay == {**result, "replayed":True}
    assert scene.count("lesson_plans") == 2 and scene.count("lesson_plan_revisions") == 2
    assert replay["currentRevision"]["contextSnapshot"]["analysis"]["className"] is None
    assert "未记录" in replay["currentRevision"]["contextSnapshot"]["analysis"]["classNameNote"]
    assert local["revision"] == 47 and local["updatedAt"] == "2026-10-03T10:11:12.123+08:00"


@pytest.mark.parametrize("field,value", [("schemaVersion",True),("schemaVersion",1.0),("revision",True),("revision",9007199254740992),
                                          ("updatedAt","2026-10-03T01:02:03"),("updatedAt","broken")])
def test_import_strict_envelope_invalid(field, value):
    from tests.lesson_generation_support import data
    envelope = dict(schemaVersion=1, revision=0, updatedAt="2026-10-03T01:02:03Z", data=data())
    envelope[field] = value
    with pytest.raises(ValidationError):
        lp.DraftEnvelope.model_validate(envelope)


def test_save_semantic_dedup_aba_and_source_context_hash(scene):
    initial = scene.be.create_lesson(scene.create_request())
    lid = initial["lessonPlanId"]
    no_op = scene.be.save_draft(lid, scene.save_request(initial, submission="same"))
    assert no_op["revision"] == 1 and no_op["currentRevisionId"] == initial["currentRevisionId"]
    middle = scene.be.save_draft(lid, scene.save_request(no_op, submission="B", content=changed(initial["currentRevision"]["data"], keyPoints="B")))
    final = scene.be.save_draft(lid, scene.save_request(middle, submission="A", content=initial["currentRevision"]["data"]))
    assert [x["version"] for x in scene.be.list_revisions(lid)["items"]] == [3,2,1]
    assert final["currentRevision"]["contentHash"] == initial["currentRevision"]["contentHash"]
    assert final["currentRevisionId"] != initial["currentRevisionId"]
    with_context = scene.be.save_draft(lid, scene.save_request(final, submission="context", context=scene.context(("k2","k1"))))
    assert with_context["revision"] == 4
    assert [p["knowledgePointId"] for p in with_context["currentRevision"]["contextSnapshot"]["analysis"]["knowledgePoints"]] == ["k2","k1"]
    rule = scene.be.save_draft(lid, scene.save_request(with_context, submission="rule", context=scene.context(("k2","k1")),source="rule"))
    assert rule["revision"] == 5 and rule["currentRevision"]["source"] == "rule"


def test_original_save_receipt_wins_later_cas_context_archive(scene):
    initial = scene.be.create_lesson(scene.create_request(context=scene.context()))
    lid = initial["lessonPlanId"]
    request = scene.save_request(initial, context=scene.context(), content=changed(initial["currentRevision"]["data"], exercises="第一次"))
    saved = scene.be.save_draft(lid, request)
    later = scene.be.save_draft(lid, scene.save_request(saved, submission="later", content=changed(saved["currentRevision"]["data"],exercises="后来")))
    with scene.ai.practice_scene.knowledge.write_transaction() as conn:
        conn.execute("UPDATE knowledge_points SET status='archived' WHERE id='k1'")
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE lesson_plans SET archived_at='2026-10-03' WHERE id=?",(lid,))
    assert scene.be.save_draft(lid, request) == {**saved,"replayed":True}
    assert scene.be.get_lesson(lid)["revision"] == later["revision"]
    with pytest.raises(AppError) as changed_request:
        scene.be.save_draft(lid, request.model_copy(update={"source":"rule"}))
    assert changed_request.value.code == "SUBMISSION_CONFLICT"


def test_new_submission_old_cas_is_conflict_and_owner_is_uniform404(scene):
    initial = scene.be.create_lesson(scene.create_request())
    scene.be.save_draft(initial["lessonPlanId"],scene.save_request(initial,content=changed(initial["currentRevision"]["data"],title="new")))
    with pytest.raises(AppError) as old:
        scene.be.save_draft(initial["lessonPlanId"],scene.save_request(initial,submission="new-op"))
    assert old.value.code == "REVISION_CONFLICT" and old.value.details == {"currentRevision":2,"fields":["expectedRevision"]}
    other = LessonPlanService(scene.catalog,analysis_reader=scene.ai.analysis.service,knowledge_catalog=scene.ai.practice_scene.knowledge,
        coordinator=scene.be.coordinator,job_engine=scene.engine,generation_service=scene.ai.service,evidence_reader=scene.ai.rag,owner_id="other")
    for action in [lambda: other.get_lesson(initial["lessonPlanId"]),lambda: other.get_revision(initial["lessonPlanId"], initial["currentRevisionId"]),
                   lambda: other.save_draft(initial["lessonPlanId"],scene.save_request(initial)),lambda: other.list_revisions(initial["lessonPlanId"])]:
        with pytest.raises(AppError) as absent:
            action()
        assert absent.value.code == "NOT_FOUND" and absent.value.status_code == 404
    assert other.list_lessons()["items"] == []


def test_context_must_match_fixed_ready_report_class_and_subject(scene):
    for context in [scene.context(("not-in-report",)),dict(analysisRunId="missing",selectedKnowledgePointIds=["k1"])]:
        with pytest.raises(AppError):
            scene.be.create_lesson(scene.create_request(context=context))
    with scene.catalog.write_transaction() as conn:
        conn.execute("INSERT INTO classes(id,code,name,school_year,grade_id) VALUES('other-class','other','其他班','2026','g')")
    for changes in [dict(subjectId="other"),dict(classId="other-class")]:
        value = scene.create_request(context=scene.context()).model_dump(by_alias=True)
        value.update(changes)
        with pytest.raises(AppError) as invalid:
            scene.be.create_lesson(lp.LessonCreateRequest.model_validate(value))
        assert invalid.value.code == "LESSON_INVALID"
    assert scene.count("lesson_plans") == 1


def test_same_package_concurrent_save_one_revision_and_receipt(scene, monkeypatch):
    initial = scene.be.create_lesson(scene.create_request())
    request = scene.save_request(initial,content=changed(initial["currentRevision"]["data"],keyPoints="并发同包"))
    barrier = Barrier(2)
    from app.services.lesson_plans import service as module
    original = module.freeze_context
    def paused(*args):
        result = original(*args)
        barrier.wait(timeout=10)
        return result
    monkeypatch.setattr(module,"freeze_context",paused)
    before = scene.count("command_submissions")
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(scene.be.save_draft,initial["lessonPlanId"],request) for _ in range(2)]
        values = [future.result(timeout=15) for future in futures]
    assert sorted(x["replayed"] for x in values) == [False,True]
    assert values[0]["currentRevisionId"] == values[1]["currentRevisionId"]
    assert scene.be.get_lesson(initial["lessonPlanId"])["revision"] == 2
    assert scene.count("command_submissions") == before+1


def test_receipt_and_preflight_share_snapshot_even_when_commit_between_reads(scene, monkeypatch):
    initial = scene.be.create_lesson(scene.create_request())
    request = scene.save_request(initial,content=changed(initial["currentRevision"]["data"],keyPoints="snapshot"))
    entered, finished = Event(), Event()
    original = scene.be._replay_in
    fired = False
    def window(conn, command):
        nonlocal fired
        prior = original(conn,command)
        if prior is None and not fired:
            fired = True
            entered.set()
            assert finished.wait(10)
        return prior
    monkeypatch.setattr(scene.be,"_replay_in",window)
    def competitor():
        assert entered.wait(10)
        try:
            return scene.be.save_draft(initial["lessonPlanId"],request)
        finally:
            finished.set()
    with ThreadPoolExecutor(1) as pool:
        other = pool.submit(competitor)
        replay = scene.be.save_draft(initial["lessonPlanId"],request)
        committed = other.result(timeout=10)
    assert replay == {**committed,"replayed":True}
    assert scene.be.get_lesson(initial["lessonPlanId"])["revision"] == 2


@pytest.mark.parametrize("operation",["create","save"])
def test_preparation_failure_returns_already_committed_same_package_receipt(scene,monkeypatch,operation):
    from app.services.lesson_plans import service as module
    original = module.freeze_context
    initial = scene.be.create_lesson(scene.create_request())
    request = scene.create_request(submission="prepare-create") if operation=="create" else scene.save_request(initial,content=changed(initial["currentRevision"]["data"],exercises="竞态"))
    action = lambda: scene.be.create_lesson(request) if operation=="create" else scene.be.save_draft(initial["lessonPlanId"],request)
    committed = []
    def window(*args):
        monkeypatch.setattr(module,"freeze_context",original)
        committed.append(action())
        raise AppError("原文准备失效",code="TEST_PREPARE_FAILURE",status_code=422)
    monkeypatch.setattr(module,"freeze_context",window)
    replay = action()
    assert replay == {**committed[0],"replayed":True}


def test_missing_receipt_preserves_preparation_error(scene,monkeypatch):
    from app.services.lesson_plans import service as module
    failure = AppError("原始准备错误",code="ORIGINAL_FAILURE",status_code=422)
    def broken(*args):
        raise failure
    monkeypatch.setattr(module,"freeze_context",broken)
    with pytest.raises(AppError) as caught:
        scene.be.create_lesson(scene.create_request())
    assert caught.value is failure
    assert scene.count("lesson_plans") == 1


def test_new_revision_and_receipt_fault_roll_back_everything(scene):
    initial = scene.be.create_lesson(scene.create_request())
    before = (scene.count("lesson_plan_revisions"),scene.count("lesson_revision_reviews"),scene.count("command_submissions"))
    with scene.catalog.write_transaction() as conn:
        conn.execute("""CREATE TRIGGER be_receipt_fault BEFORE INSERT ON command_submissions
            WHEN NEW.operation LIKE 'lesson.draft:%' BEGIN SELECT RAISE(ABORT,'author receipt failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        scene.be.save_draft(initial["lessonPlanId"],scene.save_request(initial,content=changed(initial["currentRevision"]["data"],title="rollback")))
    assert scene.be.get_lesson(initial["lessonPlanId"]) == initial
    assert before == (scene.count("lesson_plan_revisions"),scene.count("lesson_revision_reviews"),scene.count("command_submissions"))


def test_true_pointer_owner_version_fks_and_immutable_content(scene):
    initial = scene.be.create_lesson(scene.create_request())
    for sql,args in [
        ("UPDATE lesson_plan_revisions SET data_json='{}' WHERE id=?",(initial["currentRevisionId"],)),
        ("DELETE FROM lesson_plan_revisions WHERE id=?",(initial["currentRevisionId"],)),
        ("UPDATE lesson_plans SET subject_id='other' WHERE id=?",(initial["lessonPlanId"],)),
        ("UPDATE lesson_plans SET current_revision_id='lesson-r',revision=revision+1 WHERE id=?",(initial["lessonPlanId"],)),
        ("INSERT INTO lesson_plans VALUES('bad-owner','other','math','class','lesson-r',1,NULL,'now','now')",()),
        ("INSERT INTO lesson_plans VALUES('bad-version','local','math','class','lesson-r',2,NULL,'now','now')",()),
    ]:
        with pytest.raises(sqlite3.IntegrityError):
            with scene.catalog.write_transaction() as conn:
                conn.execute(sql,args)
    assert scene.be.get_lesson(initial["lessonPlanId"]) == initial
    with scene.catalog.read_connection() as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall()==[]
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
