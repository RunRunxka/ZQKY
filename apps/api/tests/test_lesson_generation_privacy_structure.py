"""B5R-R01: short identities in free text versus exact trusted JSON paths."""
import copy
import json
from dataclasses import replace
import pytest
from app.core.exceptions import AppError
from app.contracts.lesson_plans import LessonGenerateRequest
from app.services.lesson_generation.privacy import check_model_payload, check_wire, check_text
from app.services.lesson_generation.service import SYSTEM_PROMPT
from app.services.lesson_generation.validation import normalize_model_output
from tests.lesson_generation_support import Scene, reply


def short_identity_reader(scene, student_no):
    """Consistent public fixed-reader projection for the identity-boundary probe.

    The real catalogs/RAG/provider/job publication are retained. Safe teaching
    names avoid incidental digits in the original fixture's names '固定k1'.
    This projection changes no SQL row and is not claimed as a new report API run.
    """
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
    # The original RAG test fixture intentionally has numbered paragraph text.
    # Short identity probes must use actual sealed evidence with no such free
    # numbers; free source text containing the known number remains blocked.
    document = scene.rag_env.add_document(title="集合教材", text="# 集合概念\n\n集合是确定对象组成的整体。元素与集合之间有属于或不属于的关系。用固定课堂题验证概念。")
    chunk = document.first_body_chunk()
    scene.verified = scene.rag.prepare_selected_evidence(scene.rag_env.selection(document),[dict(
        documentRevisionId=document.revision_id,charStart=chunk.char_start,charEnd=chunk.char_end)])
    scene.body = LessonGenerateRequest.model_validate({**scene.body.model_dump(by_alias=True),
        "scopeSnapshot":scene.verified.scope_snapshot,"evidenceRefs":scene.verified.evidence_refs})


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
    scene = await Scene.create(tmp_path)
    short_identity_reader(scene,"1")
    try: yield scene
    finally: await scene.close()


@pytest.mark.parametrize("protocol", ["openai_chat", "openai_responses", "anthropic_messages"])
@pytest.mark.parametrize("student_no", ["1", "2", "12"])
async def test_short_student_numbers_generate_with_real_final_serialization(tmp_path,protocol,student_no):
    scene = await Scene.create(tmp_path,protocol)
    short_identity_reader(scene,student_no)
    try:
        prepared = scene.prepare()
        assert student_no in prepared.frozen_input["source"]["personalTokens"]
        payload = prepared.frozen_input["modelPayload"]
        assert payload["newProcessAliases"] == [f"new:N{n}" for n in range(1,13)]
        assert payload["processAliases"] == ["P1"]
        assert any(1 in point["counts"].values() for point in payload["classSummary"]["knowledgePoints"])
        done = await scene.run(scene.job(prepared))
        assert done.state == "succeeded", done.error
        actual = scene.wires[0]["body"]
        check_wire(actual,prepared.frozen_input["source"]["personalTokens"],protocol=protocol.replace("_","-"),
                   model_payload=payload,system_prompt=SYSTEM_PROMPT)
        assert scene.calls == 1 and scene.count("lesson_ai_proposals") == 1
    finally: await scene.close()


@pytest.mark.parametrize("text", ["为1另行辅导", "学号:1", "学员ID=1", "student_id:1", "new:N1", "P1", "K1", "E1"])
def test_short_identity_is_still_blocked_in_free_natural_text_and_alias_literal(text):
    with pytest.raises(AppError) as error: check_text(text,["1"])
    assert error.value.code == "LESSON_PERSONAL_INFO"


@pytest.mark.parametrize("path", ["requirements", "competencies", "stage", "design", "secondary", "kp_name", "evidence_title", "evidence_text"])
def test_no_free_payload_path_can_borrow_an_alias_or_scalar_exemption(scene,path):
    payload = scene.prepare().frozen_input["modelPayload"]
    if path == "requirements": payload["requirements"] = "学号:1"
    elif path == "competencies": payload["lesson"]["coreCompetencies"] = "为1安排"
    elif path in ("stage","design","secondary"): payload["lesson"]["process"][0][path] = "new:N1"
    elif path == "kp_name": payload["classSummary"]["knowledgePoints"][0]["name"] = "1"
    elif path == "evidence_title": payload["evidence"][0]["title"] = "P1"
    else: payload["evidence"][0]["text"] = "E1"
    with pytest.raises(AppError) as error: check_model_payload(payload,["1"])
    assert error.value.code == "LESSON_PERSONAL_INFO"


@pytest.mark.parametrize("mutation", ["extra_root", "extra_lesson", "extra_count", "count_string", "count_bool", "fake_process",
    "fake_process_list", "fake_new_alias", "fake_knowledge", "fake_evidence", "extra_evidence", "numeric_text"])
def test_only_exact_structural_paths_aliases_and_integer_counts_are_whitelisted(scene,mutation):
    payload = scene.prepare().frozen_input["modelPayload"]
    if mutation == "extra_root": payload["students"] = [{"studentNo":"1"}]
    elif mutation == "extra_lesson": payload["lesson"]["studentNo"] = "1"
    elif mutation == "extra_count": payload["classSummary"]["knowledgePoints"][0]["counts"]["studentNo"] = 1
    elif mutation == "count_string": payload["classSummary"]["knowledgePoints"][0]["counts"]["needsCount"] = "1"
    elif mutation == "count_bool": payload["classSummary"]["knowledgePoints"][0]["counts"]["needsCount"] = True
    elif mutation == "fake_process": payload["lesson"]["process"][0]["id"] = "1"
    elif mutation == "fake_process_list": payload["processAliases"] = ["new:N1"]
    elif mutation == "fake_new_alias": payload["newProcessAliases"][0] = "N1"
    elif mutation == "fake_knowledge": payload["classSummary"]["knowledgePoints"][0]["alias"] = "E1"
    elif mutation == "fake_evidence": payload["evidence"][0]["alias"] = "Q1"
    elif mutation == "extra_evidence": payload["evidence"][0]["studentNo"] = "1"
    else: payload["requirements"] = 1
    with pytest.raises(AppError): check_model_payload(payload,["1"])


@pytest.mark.parametrize("protocol", ["openai_chat", "openai_responses", "anthropic_messages"])
@pytest.mark.parametrize("mutation", ["extra_top", "extra_message", "extra_message_key", "changed_system", "changed_user", "duplicate_user_key"])
async def test_final_actual_wire_rejects_unknown_tool_messages_or_modified_user_json(tmp_path,protocol,mutation):
    scene = await Scene.create(tmp_path,protocol)
    short_identity_reader(scene,"1")
    try:
        prepared = scene.prepare()
        done = await scene.run(scene.job(prepared))
        assert done.state == "succeeded"
        body = copy.deepcopy(scene.wires[0]["body"])
        messages = body["input" if protocol == "openai_responses" else "messages"]
        index = 0 if protocol == "anthropic_messages" else 1
        if mutation == "extra_top": body["tools"] = [{"studentNo":"1"}]
        elif mutation == "extra_message": messages.append(copy.deepcopy(messages[index]))
        elif mutation == "extra_message_key": messages[index]["tool_calls"] = [{"studentNo":"1"}]
        elif mutation == "changed_system":
            if protocol == "anthropic_messages": body["system"] = SYSTEM_PROMPT + "学号:1"
            elif protocol == "openai_responses": messages[0]["content"][0]["text"] = "altered"
            else: messages[0]["content"] = "altered"
        else:
            text = '{"requirements":"safe","requirements":"学号:1"}' if mutation == "duplicate_user_key" else '{"unknown":"1"}'
            if protocol == "openai_responses": messages[index]["content"][0]["text"] = text
            else: messages[index]["content"] = text
        with pytest.raises(AppError):
            check_wire(body,prepared.frozen_input["source"]["personalTokens"],protocol=protocol.replace("_","-"),
                       model_payload=prepared.frozen_input["modelPayload"],system_prompt=SYSTEM_PROMPT)
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
    scene.handle = replace(scene.handle,model_id="model-1",config=replace(scene.handle.config,modelId="model-1"))
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
