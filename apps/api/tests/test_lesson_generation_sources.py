import copy
import json
import pytest
from app.contracts.lesson_plans import LessonGenerateRequest
from app.core.exceptions import AppError
from tests.lesson_generation_support import Scene


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try: yield value
    finally: await value.close()


def with_body(scene, **fields):
    return LessonGenerateRequest.model_validate({**scene.body.model_dump(by_alias=True), **fields})


def test_actual_question_owner_is_explicit_and_fixed_revision_read(scene):
    question = scene.question()
    prepared = scene.prepare(with_body(scene, questionRevisionIds=[question.current_revision_id]))
    frozen = prepared.frozen_input
    actual = frozen["source"]["questions"][0]
    assert actual["owner_id"] == "local-user" and actual["question_revision_id"] == question.current_revision_id
    assert frozen["source"]["evidence"][-1]["kind"] == "question"
    assert frozen["source"]["evidence"][-1]["text"] == "固定课堂问题\n"
    assert "local-user" not in json.dumps(frozen["modelPayload"])
    scene.service.revalidate_prepared_refs(frozen)
    other = scene.question(owner="local")
    with pytest.raises(AppError) as error:
        scene.prepare(with_body(scene, questionRevisionIds=[other.current_revision_id]))
    assert error.value.code == "QUESTION_NOT_FOUND"


async def test_reviewed_practice_is_exact_fixed_reader_no_current_substitution(scene):
    question = scene.question()
    practice_service = scene.practice_scene.service
    practice_service.question_owner_id = "local-user"
    created = scene.practice_scene.create_set()
    # item() is a legacy helper with local owner; construct exact reviewed content
    # through real practice service using its explicitly injected question owner.
    item = dict(itemKey="item-1",questionRevisionId=question.current_revision_id,ordinal=1,maxScore="1",
        selectedKnowledgePointIds=["k1","k2"],itemStructure={"nodes":[dict(nodeKey="leaf",parentNodeKey=None,
            questionNo="1",ordinal=1,isScored=True,maxScore="1",knowledgePointIds=["k1","k2"],sourceBlockIds=["stem:0"])]})
    saved = scene.practice_scene.save(created,[item])
    reviewed = scene.practice_scene.review(saved)
    rid = reviewed.current_revision.practice_revision_id
    prepared = scene.prepare(with_body(scene,practiceRevisionIds=[rid]))
    fixed = prepared.frozen_input["source"]["practices"][0]
    assert fixed["practiceRevisionId"] == rid and fixed["state"] == "reviewed"
    evidence = prepared.frozen_input["source"]["evidence"][-1]
    assert evidence["kind"] == "practice" and evidence["referenceId"] == rid
    assert "固定课堂问题" in evidence["text"]
    # A later draft must not replace the selected immutable review.
    from app.contracts.b4 import PracticeRevisionRequest
    new = practice_service.new_revision(reviewed.practice_set_id,PracticeRevisionRequest(
        submissionId="new-draft",sourceRevisionId=rid))
    assert new.current_revision.practice_revision_id != rid
    scene.service.revalidate_prepared_refs(prepared.frozen_input)
    done = await scene.run(scene.job(prepared))
    assert done.state == "succeeded", done.error
    assert rid not in json.dumps(scene.wires[0]["body"])
    with pytest.raises(AppError) as error:
        scene.prepare(with_body(scene,practiceRevisionIds=[new.current_revision.practice_revision_id]))
    assert error.value.code == "LESSON_INVALID" and error.value.details["issues"][0]["code"] == "PRACTICE_NOT_REVIEWED"


@pytest.mark.parametrize("field,value", [("classId","other-class"),("selectedKnowledgePointIds",["other-kp"]),
    ("baseRevisionId","history-r"),("baseServerRevision",2)])
def test_explicit_class_report_points_and_base_are_required(scene,field,value):
    with pytest.raises(AppError): scene.prepare(with_body(scene,**{field:value}))
    assert scene.calls == 0


async def test_later_active_score_does_not_replace_fixed_ready_report(scene):
    prepared = scene.prepare()
    new_id = scene.analysis.new_score(changes={("p000","i000"):("recorded",0)})
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE assessments SET active_score_revision_id=? WHERE id='assessment'",(new_id,))
    fresh_prepared = scene.prepare()
    assert fresh_prepared.frozen_input == prepared.frozen_input
    done = await scene.run(scene.job(prepared))
    assert done.state == "succeeded"
    with scene.catalog.read_connection() as conn:
        payload = json.loads(conn.execute("SELECT payload_json FROM lesson_ai_proposals").fetchone()[0])
    assert payload["generationSource"]["analysis"]["scoreRevisionId"] == "score-r"


def test_every_distinct_historical_kp_revision_is_rechecked(scene):
    frozen = scene.prepare().frozen_input
    frozen["source"]["referenceKnowledge"].append(dict(knowledgePointId="k1",knowledgeRevisionId="fake-revision",name="name",role="primary"))
    with pytest.raises(AppError) as error: scene.service.revalidate_prepared_refs(frozen)
    assert error.value.code == "KNOWLEDGE_REFERENCE_INVALID"


def test_question_archive_blocks_new_reference_even_fixed_revision(scene):
    question = scene.question()
    prepared = scene.prepare(with_body(scene,questionRevisionIds=[question.current_revision_id]))
    with scene.practice_scene.questions.write_transaction() as conn:
        conn.execute("UPDATE questions SET status='archived' WHERE id=?",(question.question_id,))
    with pytest.raises(AppError): scene.service.revalidate_prepared_refs(prepared.frozen_input)
    with pytest.raises(AppError): scene.prepare(with_body(scene,questionRevisionIds=[question.current_revision_id]))


def test_references_hash_or_scope_tamper_is_not_hand_typed_evidence(scene):
    refs = [x.model_dump() for x in scene.body.evidence_refs]
    refs[0]["normalizedTextSha256"] = "ab"*32
    with pytest.raises(AppError): scene.prepare(with_body(scene,evidenceRefs=refs))
    scope = scene.body.scope_snapshot.model_dump()
    scope["scopeHash"] = "cd"*32
    with pytest.raises(AppError): scene.prepare(with_body(scene,scopeSnapshot=scope))


def test_wrong_subject_and_unreviewed_sources_not_accepted(scene):
    question = scene.question(subject="english")
    with pytest.raises(AppError) as error: scene.prepare(with_body(scene,questionRevisionIds=[question.current_revision_id]))
    assert error.value.code == "LESSON_INVALID"
    practice = scene.practice_scene.create_set()
    with pytest.raises(AppError) as error: scene.prepare(with_body(scene,practiceRevisionIds=[practice.current_revision.practice_revision_id]))
    assert error.value.code == "LESSON_INVALID" and error.value.details["issues"][0]["code"] == "PRACTICE_NOT_REVIEWED"
