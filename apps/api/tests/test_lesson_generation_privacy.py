"""R7 教案隐私边界：已知来源 PII 阻断（LangChain 改造后的等价 wire 核对）。

与归档差异：不再有 HTTP transport wires——核对对象改为**入模消息本体**
（LangChain 消息的 openai-chat 等价形状，``build_model_messages`` 产出，
check_wire 逐字复用）。学情报告的匿名聚合（学生代称）与目标班级计数隔离
语义保持归档口径。
"""
import json

import pytest
from app.contracts.lesson_plans import LessonGenerateRequest, LessonView
from app.core.exceptions import AppError
from app.services.lesson_generation.privacy import check_text
from tests.lesson_generation_support import Scene


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    try: yield value
    finally: await value.close()


async def test_model_messages_only_anonymous_target_counts(tmp_path):
    scene = await Scene.create(tmp_path)
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
        # 入模消息：system 逐字 + user 恰等于冻结 modelPayload（无身份泄漏面）
        assert len(scene.model.calls) == 1
        contents = [getattr(message, "content", message) for message in scene.model.calls[0]]
        serialized = json.dumps(contents, ensure_ascii=False, default=str)
        for value in ("s000","p000","00000","other-class","lesson-r",scene.body.analysis_run_id,"98765","998877","old-safe"):
            assert value not in serialized
        assert not any(key in serialized for key in ('"participants"','"students"','"studentId"','"studentNo"','"classId"','"scoreRevisionId"','"scopeSnapshot"'))
        assert scene.count("lesson_plan_revisions") == 1
    finally: await scene.close()


@pytest.mark.parametrize("location,value", [("requirements","为s000单独安排"),("requirements","学号：999999"),
    ("coreCompetencies","针对00000"),("process","为p000讲解"),("textbook","姓名：张某")])
def test_known_identity_blocked_in_all_model_facing_text(scene,location,value):
    body = scene.body.model_dump(by_alias=True)
    lesson = scene.lesson.model_dump(by_alias=True)
    if location == "requirements": body["requirements"] = value
    elif location == "coreCompetencies": lesson["currentRevision"]["data"]["coreCompetencies"] = value
    elif location == "process": lesson["currentRevision"]["data"]["process"][0]["secondary"] = value
    else:
        # Source is freshly parsed/sealed through the production evidence reader.
        harness = scene.textbook_harness
        draft = harness.import_with_metadata("# 教材\n\n" + value + "\n集合是确定对象的整体。")
        job = harness.commit_and_run(draft, submission_id="privacy-evidence")
        assert job.state == "succeeded", job.error
        from app.services.rag_v2.source_text import ImmutableSource
        from app.schemas.textbook import TextbookSelection
        source = ImmutableSource(catalog=harness.catalog)
        doc_ids = harness.catalog.library_document_ids(harness.library.library_id)
        doc = harness.catalog.get_document(doc_ids[-1])
        revision = harness.catalog.get_revision(doc.current_revision_id)
        text = source.read_normalized_text(revision)
        chunk_set_id = harness.catalog.allowed_chunks(
            harness.catalog.catalog_state().active_generation_id, [revision.revision_id]).chunk_set_ids[0]
        chunk = next(c for c in harness.catalog.list_chunks(chunk_set_id) if c.region == "body")
        selection = TextbookSelection(gradeId="senior-1", subjectId="math", editionId="renjiao-a",
                                      documentIds=[doc.document_id])
        result = scene.rag.prepare_selected_evidence(selection, [dict(
            documentRevisionId=revision.revision_id, charStart=chunk.char_start, charEnd=min(chunk.char_end, len(text)))])
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


def test_oversized_output_budget_is_rejected_visibly(scene):
    """LangChain 改造：输出预算由 handle 声明承载；超冻结上限按归档语义显式拒绝。"""
    scene.handle.max_output_tokens = 16385
    with pytest.raises(AppError) as error: scene.prepare()
    assert error.value.code == "LESSON_INPUT_BUDGET"
