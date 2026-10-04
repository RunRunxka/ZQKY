"""Independent B5 generation review: fixed data oracle and source boundaries.

Runs only under the review runner's fresh OS TEMP environment. Does not import
app.main, connect a listener or real model, or access formal data/credentials.
"""
from dataclasses import replace
import json
import pytest
from app.contracts.lesson_plans import LessonGenerateRequest
from app.core.exceptions import AppError
from tests.lesson_generation_support import Scene


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


async def test_wire_uses_explicit_hand_computed_four_student_counts(scene):
    # Actual score fixture: A loses in the joint leaf, B is full on K1 but
    # missing a K2 leaf, C is absent, D loses only K1. No production merge/rule
    # helper is used to build this oracle.
    done = await scene.run()
    assert done.state == "succeeded", done.error
    payload = json.loads(scene.wires[0]["body"]["messages"][1]["content"])
    expected = [
        dict(selectedCount=4, validCount=3, needsCount=2, incompleteCount=1,
             noEvidenceCount=1, fullCreditCount=1, numerator=2, denominator=3),
        dict(selectedCount=4, validCount=3, needsCount=1, incompleteCount=2,
             noEvidenceCount=1, fullCreditCount=1, numerator=1, denominator=3),
    ]
    assert [row["counts"] for row in payload["classSummary"]["knowledgePoints"]] == expected
    assert set(payload["classSummary"]) == {"knowledgePoints"}
    assert [row["alias"] for row in payload["classSummary"]["knowledgePoints"]] == ["K1", "K2"]
    assert scene.count("lesson_plan_revisions") == 1


def test_known_identity_compatibility_letters_with_word_joiner_is_blocked(scene):
    body = scene.body.model_dump(by_alias=True)
    body["requirements"] = "为Ｓ\u2060０００单独调整"
    with pytest.raises(AppError) as caught:
        scene.prepare(LessonGenerateRequest.model_validate(body))
    assert caught.value.code == "LESSON_PERSONAL_INFO"
    assert scene.calls == 0 and scene.count("lesson_ai_proposals") == 0
    assert "Ｓ" not in str(caught.value)


async def test_textbook_scope_becoming_unavailable_blocks_before_provider(scene):
    job = scene.job()
    scene.rag_env.catalog.set_active_generation(None)
    done = await scene.run(job)
    assert done.state == "failed" and done.error_code == "RAG_SCOPE_CHANGED"
    assert scene.calls == 0 and scene.count("lesson_ai_proposals") == 0


async def test_reference_question_archived_after_acceptance_blocks_before_provider(scene):
    question = scene.question()
    body = LessonGenerateRequest.model_validate({**scene.body.model_dump(by_alias=True),
        "questionRevisionIds": [question.current_revision_id]})
    job = scene.job(scene.prepare(body))
    with scene.practice_scene.questions.write_transaction() as conn:
        conn.execute("UPDATE questions SET status='archived' WHERE id=?", (question.question_id,))
    done = await scene.run(job)
    assert done.state == "failed"
    assert scene.calls == 0 and scene.count("lesson_ai_proposals") == 0


async def test_provider_alias_identity_conflict_blocks_before_network(scene):
    # Restore fingerprint as a fresh accepted task with the explicit unsafe
    # model name to check the final wire's free-text model path, not model drift.
    scene.handle = replace(scene.handle, model_id="s000-model",
                           config=replace(scene.handle.config, modelId="s000-model"))
    with pytest.raises(AppError) as caught:
        scene.prepare()
    assert caught.value.code == "LESSON_PERSONAL_INFO" and scene.calls == 0
