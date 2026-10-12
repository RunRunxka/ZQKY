"""B5R-R01: short identities in free text versus exact trusted JSON paths（R7 适配）。

与归档差异：无 HTTP transport wires；核对对象是入模消息本体与 check_wire 的
openai-chat 等价形状（``build_model_messages`` + ``check_wire``）。教材证据用
真实教材目录（Harness），固定题/练习引用路径由 sources 测试覆盖。
"""
import copy
import json
from dataclasses import replace

import pytest
from app.contracts.lesson_plans import LessonGenerateRequest
from app.core.exceptions import AppError
from app.services.lesson_generation.privacy import check_model_payload, check_wire, check_text
from app.services.lesson_generation.service import SYSTEM_PROMPT_TEXT
from app.services.lesson_generation.validation import normalize_model_output
from tests.lesson_generation_support import Scene, reply


def short_identity_reader(scene, student_no):
    """Consistent public fixed-reader projection for the identity-boundary probe."""
    original = scene.service.analysis.read_ready_report
    def read(run_id, owner_id="local"):
        report = original(run_id, owner_id)
        report["participants"][0]["studentNo"] = student_no
        for row in report["students"]:
            if row["participant"]["participantId"] == report["participants"][0]["participantId"]:
                row["participant"]["studentNo"] = student_no
        names = {"k1":"集合概念", "k2":"关系判断"}
        for point in report["knowledgePoints"]: point["name"] = names[point["knowledgePointId"]]
        for row in report["classes"]: row["knowledgePoint"]["name"] = names[row["knowledgePoint"]["knowledgePointId"]]
        return report
    scene.service.analysis.read_ready_report = read
    scene.reply = safe_reply()
    scene.model.default_reply = safe_reply()
    # 教材证据换成无数字自由文本的干净文档（归档口径：短身份探针不得被既有
    # 编号段落文本误伤）；用真实管线导入 + 首个正文块构造已核实引用。
    harness = scene.textbook_harness
    draft = harness.import_with_metadata(
        "# 集合教材\n\n集合是确定对象组成的整体。元素与集合之间有属于或不属于的关系。用固定课堂题验证概念。",
        file_name="identity-free.md")
    job = harness.commit_and_run(draft, submission_id="identity-free-ingest")
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
    scene.verified = scene.rag.prepare_selected_evidence(selection, [dict(
        documentRevisionId=revision.revision_id, charStart=chunk.char_start, charEnd=min(chunk.char_end, len(text)))])
    scene.body = LessonGenerateRequest.model_validate({**scene.body.model_dump(by_alias=True),
        "scopeSnapshot": scene.verified.scope_snapshot, "evidenceRefs": scene.verified.evidence_refs})


def safe_reply():
    value = reply()
    for item, title in zip(value["patch"]["process"], ("导入", "探究", "练习", "总结")):
        item["stage"] = title
    # Trusted numeric minute metadata deliberately includes both 1 and 12.
    for stage, minutes in zip(value["budget"]["stages"], (1,12,12,15)):
        stage["minutes"] = minutes
    return value


@pytest.fixture
async def scene(tmp_path):
    value = await Scene.create(tmp_path)
    short_identity_reader(value, "1")
    try: yield value
    finally: await value.close()


async def test_wire_rejects_unknown_or_modified_user_json(tmp_path):
    scene = await Scene.create(tmp_path)
    short_identity_reader(scene, "1")
    try:
        prepared = scene.prepare()
        done = await scene.run(scene.job(prepared))
        assert done.state == "succeeded"
        # 入模消息（openai-chat 等价形状）再次过 check_wire：成功路径的 wire 合法
        wire = {"model": scene.handle.model_id, "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_TEXT},
            {"role": "user", "content": scene.service.build_request(prepared.frozen_input, scene.handle)[1]["content"]},
        ]}
        check_wire(wire, prepared.frozen_input["source"]["personalTokens"], protocol="openai-chat",
                   model_payload=prepared.frozen_input["modelPayload"], system_prompt=SYSTEM_PROMPT_TEXT)
        assert scene.calls == 1 and scene.count("lesson_ai_proposals") == 1
        # 变体（未知字段 / 改过的 user JSON / 改过的 system）必须被 check_wire 拒绝
        for mutation in ("extra_top", "changed_system", "changed_user", "duplicate_user_key"):
            body = copy.deepcopy(wire)
            if mutation == "extra_top": body["tools"] = [{"studentNo":"1"}]
            elif mutation == "changed_system": body["messages"][0]["content"] = SYSTEM_PROMPT_TEXT + "学号:1"
            elif mutation == "changed_user": body["messages"][1]["content"] = '{"unknown":"1"}'
            else: body["messages"][1]["content"] = '{"requirements":"safe","requirements":"学号:1"}'
            with pytest.raises(AppError):
                check_wire(body, prepared.frozen_input["source"]["personalTokens"], protocol="openai-chat",
                           model_payload=prepared.frozen_input["modelPayload"], system_prompt=SYSTEM_PROMPT_TEXT)
    finally: await scene.close()


@pytest.mark.parametrize("field", ["coreCompetencies", "process_design", "activity", "check"])
def test_candidate_free_text_short_identity_blocked_but_aliases_and_minutes_allowed(scene,field):
    frozen, value = scene.prepare().frozen_input, safe_reply()
    assert normalize_model_output(value,frozen)["budget"]["stages"][0]["minutes"] == 1
    if field == "coreCompetencies": value["patch"][field] = "为1设计"
    elif field == "process_design": value["patch"]["process"][0]["design"] = "P1"
    else: value["budget"]["stages"][0][field] = "学号:1"
    with pytest.raises(AppError) as error: normalize_model_output(value,frozen)
    assert error.value.code == "LESSON_PERSONAL_INFO"


def test_model_configuration_free_strings_still_checked(scene):
    scene.handle.model_id = "model-1"
    with pytest.raises(AppError) as error: scene.prepare()
    assert error.value.code == "LESSON_PERSONAL_INFO" and scene.calls == 0


@pytest.mark.parametrize("text", ["学员ID:unknown-person", "学籍号:unknown-person"])
def test_explicit_identity_markers_block_even_when_value_is_not_in_known_report(text):
    with pytest.raises(AppError) as error: check_text(text,["1"])
    assert error.value.code == "LESSON_PERSONAL_INFO"


def test_short_person_identifiers_can_collide_only_in_trusted_alias_paths(scene):
    payload = scene.prepare().frozen_input["modelPayload"]
    # Exact service-generated aliases remain anonymous labels even if one is
    # coincidentally equal to a short ID. Any free path with it is rejected.
    check_model_payload(payload,["P1", "K1", "E1", "new:N1"])
    for token in ("P1", "K1", "E1", "new:N1"):
        changed = copy.deepcopy(payload)
        changed["requirements"] = "单独关注" + token
        with pytest.raises(AppError): check_model_payload(changed,[token])
