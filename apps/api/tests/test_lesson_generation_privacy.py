import copy
import json
from dataclasses import replace
import pytest
from app.core.exceptions import AppError
from app.contracts.lesson_plans import LessonGenerateRequest, LessonView
from app.services.lesson_generation.privacy import check_text
from tests.lesson_generation_support import Scene


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try: yield value
    finally: await value.close()


@pytest.mark.parametrize("protocol", ["openai_chat","openai_responses","anthropic_messages"])
async def test_real_provider_serialized_wire_only_anonymous_target_counts(tmp_path,protocol):
    scene = await Scene.create(tmp_path,protocol)
    try:
        # Inject a second class into the PUBLIC READER test response, with unique
        # sentinel counts; target selection must ignore it and global totals.
        reader = scene.service.analysis
        original = reader.read_ready_report
        def report(run_id,owner_id="local"):
            value = original(run_id,owner_id)
            value["selectionSnapshot"]["uniqueStudentCount"] = 98765
            value["classes"].extend([{**row,"classId":"other-class","needsCount":998877} for row in value["classes"]])
            return value
        reader.read_ready_report = report
        prepared = scene.prepare()
        model = prepared.frozen_input["modelPayload"]
        assert set(model["classSummary"]) == {"knowledgePoints"}
        assert all(set(x) == {"alias","name","counts"} for x in model["classSummary"]["knowledgePoints"])
        assert "98765" not in json.dumps(model) and "998877" not in json.dumps(model)
        # Protected frozen facts retain identities for the exact lineage audit.
        assert prepared.frozen_input["source"]["report"]["participants"][0]["studentId"] == "s000"
        done = await scene.run(scene.job(prepared))
        assert done.state == "succeeded", done.error
        assert len(scene.wires) == 1
        wire = scene.wires[0]["body"]
        serialized = json.dumps(wire,ensure_ascii=False)
        for value in ("s000","p000","00000","other-class","lesson-r",scene.body.analysis_run_id,"98765","998877","old-safe"):
            assert value not in serialized
        assert not any(key in serialized for key in ('"participants"','"students"','"studentId"','"studentNo"','"classId"','"scoreRevisionId"','"scopeSnapshot"'))
        token_key = {"openai_chat":"max_tokens","openai_responses":"max_output_tokens","anthropic_messages":"max_tokens"}[protocol]
        assert wire[token_key] == 16384
        assert scene.count("lesson_plan_revisions") == 1
    finally: await scene.close()


@pytest.mark.parametrize("location,value", [("requirements","为s000单独安排"),("requirements","学号：999999"),
    ("coreCompetencies","针对00000"),("process","为p000讲解"),("textbook","姓名：张某"),("question","为s000设计题")])
def test_known_identity_blocked_in_all_model_facing_text(scene,location,value):
    body = scene.body.model_dump(by_alias=True)
    lesson = scene.lesson.model_dump(by_alias=True)
    if location == "requirements": body["requirements"] = value
    elif location == "coreCompetencies": lesson["currentRevision"]["data"]["coreCompetencies"] = value
    elif location == "process": lesson["currentRevision"]["data"]["process"][0]["secondary"] = value
    elif location == "question":
        question = scene.question(value)
        body["questionRevisionIds"] = [question.current_revision_id]
    else:
        # Source is freshly parsed/sealed through the production evidence reader.
        doc = scene.rag_env.add_document(title="教材证据",text="# 教材\n\n"+value+"\n集合是确定对象的整体。")
        chunk = doc.first_body_chunk()
        result = scene.rag.prepare_selected_evidence(scene.rag_env.selection(doc),[dict(
            documentRevisionId=doc.revision_id,charStart=chunk.char_start,charEnd=chunk.char_end)])
        body["scopeSnapshot"],body["evidenceRefs"] = result.scope_snapshot,result.evidence_refs
    with pytest.raises(AppError) as error:
        scene.prepare(LessonGenerateRequest.model_validate(body),LessonView.model_validate(lesson))
    assert error.value.code == "LESSON_PERSONAL_INFO"
    assert value not in str(error.value) and scene.calls == 0


def test_unsafe_old_process_id_is_never_forwarded(scene):
    lesson = scene.lesson.model_dump(by_alias=True)
    lesson["currentRevision"]["data"]["process"][0]["id"] = "p000"
    prepared = scene.prepare(lesson=LessonView.model_validate(lesson))
    assert prepared.frozen_input["source"]["processAliases"]["P1"].startswith("lp_")
    assert "p000" not in json.dumps(prepared.frozen_input["modelPayload"])


@pytest.mark.parametrize("value", ["s\u200b000","Ｓ０００","Student ID: unknown-person","participant_id=unknown","姓名 张某"])
def test_normalized_known_and_explicit_identity_markers(value):
    with pytest.raises(AppError): check_text(value,["s000"])


def test_input_budget_is_visible_and_not_truncated(scene):
    lesson = scene.lesson.model_dump(by_alias=True)
    lesson["currentRevision"]["data"]["coreCompetencies"] = "长"*100000
    lesson["currentRevision"]["data"]["keyPoints"] = "文"*100000
    with pytest.raises(AppError) as error: scene.prepare(lesson=LessonView.model_validate(lesson))
    assert error.value.code == "LESSON_INPUT_BUDGET" and scene.calls == 0


def test_anthropic_reasoning_expansion_cannot_exceed_selected_cap(scene):
    scene.handle = replace(scene.handle,config=replace(scene.handle.config,protocol="anthropic-messages",reasoningEffort="max",reasoningEnabled=True))
    with pytest.raises(AppError) as error: scene.prepare()
    assert error.value.code == "LESSON_INPUT_BUDGET"
