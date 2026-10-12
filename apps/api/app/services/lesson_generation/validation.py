"""Strict whole-field candidate validation, also rerun before apply."""
from __future__ import annotations

import hashlib
from pydantic import ValidationError
from app.contracts.lesson_plans import ALLOWED_FIELDS, LessonPatch, LessonBudget, ProposalEvidenceView, GenerationSourceView, utf16_length
from app.contracts.teaching_loop import canonical_hash
from .common import dump, exact_keys, invalid, snapshot
from .privacy import check_candidate_text

MAX_OUTPUT_BYTES = 256 * 1024
PHASES = {"introduction", "exploration", "practice", "conclusion"}


def stable_ids(frozen: dict) -> dict[str, str]:
    result = dict(frozen["source"]["processAliases"])
    digest = canonical_hash(frozen)
    for n in range(1, 13):
        alias = f"new:N{n}"
        result[alias] = "lp_" + hashlib.sha256((digest + "\0" + alias).encode("utf-8")).hexdigest()[:32]
    return result


def generation_source(frozen):
    return dict(analysis=frozen["contextSnapshot"]["analysis"], classId=frozen["classId"],
                selectedKnowledgePoints=frozen["source"]["selectedKnowledgePoints"],
                modelProfileId=frozen["modelProfileId"], scopeSnapshot=frozen["scopeSnapshot"],
                evidenceRefs=frozen["evidenceRefs"], requirements=frozen["requirements"])


def _strings(value, field):
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise invalid(field, "字符串包含非法 Unicode。") from exc
        if utf16_length(value) > 100000:
            raise invalid(field, "字符串超出 UTF-16 长度限制。")
    elif isinstance(value, dict):
        for key, item in value.items():
            _strings(item, field + "." + key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _strings(item, f"{field}[{i}]")


def _validate(patch, budget, frozen):
    if not isinstance(patch, dict) or not set(patch) <= set(ALLOWED_FIELDS) or "process" not in patch:
        raise invalid("patch", "候选仅允许五个完整字段，且 process 必需。")
    exact_keys(budget, ("durationMinutes", "stages"), "budget")
    if type(budget["durationMinutes"]) is not int or budget["durationMinutes"] != frozen["durationMinutes"]:
        raise invalid("budget.durationMinutes", "候选必须遵守教师明确的总分钟预算。")
    for field in ("coreCompetencies", "keyPoints", "teachingDesign", "exercises"):
        value = patch.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise invalid("patch." + field, "已建议的字段必须为非空字符串。")
    _strings(patch, "patch")
    try:
        typed_patch = LessonPatch.model_validate(patch)
        typed_budget = LessonBudget.model_validate(budget)
    except (ValidationError, UnicodeError) as exc:
        raise invalid("candidate", "候选字段、过程或分钟结构不符合契约。") from exc
    process = typed_patch.process
    stages = typed_budget.stages
    if not 4 <= len(process) <= 12:
        raise invalid("patch.process", "教学过程必须包含 4..12 个完整环节。")
    ids = [item.id for item in process]
    stage_ids = [stage.process_id for stage in stages]
    allowed_ids = set(stable_ids(frozen).values())
    if len(set(ids)) != len(ids) or len(set(stage_ids)) != len(stage_ids) or set(ids) != set(stage_ids) or not set(ids) <= allowed_ids:
        raise invalid("budget.stages", "环节稳定身份与元数据必须一一对应冻结允许集。")
    if set(stage.phase for stage in stages) != PHASES:
        raise invalid("budget.stages", "教学过程必须包含导入、探究、练习和总结四阶段。")
    if sum(stage.minutes for stage in stages) != frozen["durationMinutes"]:
        raise invalid("budget.stages", "各环节整数分钟之和必须精确等于教师预算。")
    knowledge = set(frozen["source"]["knowledgeAliases"])
    evidence = {item["alias"] for item in frozen["source"]["evidence"]}
    covered = set()
    for i, stage in enumerate(stages):
        aliases, refs = stage.knowledge_aliases, stage.evidence_aliases
        if len(set(aliases)) != len(aliases) or not set(aliases) <= knowledge:
            raise invalid(f"budget.stages[{i}].knowledgeAliases", "知识点别名必须唯一且来自冻结输入。")
        if len(set(refs)) != len(refs) or not set(refs) <= evidence:
            raise invalid(f"budget.stages[{i}].evidenceAliases", "依据别名必须唯一且来自冻结输入。")
        if not stage.activity.strip() or not stage.check.strip() or utf16_length(stage.activity) > 4000 or utf16_length(stage.check) > 4000:
            raise invalid(f"budget.stages[{i}]", "活动和课堂检测必须为预算内非空文本。")
        covered.update(aliases)
    if covered != knowledge:
        raise invalid("budget.stages", "候选过程必须覆盖每个选定知识点。")
    if any(not item.stage.strip() or not item.design.strip() for item in process):
        raise invalid("patch.process", "每个教学环节的标题与设计必须非空。")
    check_candidate_text(patch, budget, frozen["source"]["personalTokens"], allowed_ids=allowed_ids,
                         knowledge_aliases=knowledge, evidence_aliases=evidence)
    return snapshot(typed_patch), snapshot(typed_budget)


def normalize_model_output(reply: dict, frozen: dict) -> dict:
    exact_keys(reply, ("patch", "budget"), "response")
    patch, budget = snapshot(reply["patch"]), snapshot(reply["budget"])
    if not isinstance(patch, dict) or any(value is None for value in patch.values()):
        raise invalid("patch", "模型不得用 null 代替已建议字符串；未建议字段应省略。")
    mapping = stable_ids(frozen)
    if not isinstance(patch.get("process"), list):
        raise invalid("patch.process", "必须提供完整教学过程数组。")
    for item in patch["process"]:
        if not isinstance(item, dict) or item.get("id") not in mapping:
            raise invalid("patch.process.id", "模型环节只能使用已提供的匿名别名或 new:N1..N12。")
        item["id"] = mapping[item["id"]]
    if not isinstance(budget, dict) or not isinstance(budget.get("stages"), list):
        raise invalid("budget", "必须提供完整预算元数据。")
    for stage in budget["stages"]:
        if not isinstance(stage, dict) or stage.get("processId") not in mapping:
            raise invalid("budget.stages.processId", "预算元数据环节只能引用冻结匿名别名。")
        stage["processId"] = mapping[stage["processId"]]
    patch, budget = _validate(patch, budget, frozen)
    payload = dict(patch=patch, budget=budget, evidence=frozen["source"]["evidence"], generationSource=generation_source(frozen))
    return validate_for_apply(payload, frozen)


def validate_for_apply(payload: dict, frozen_input: dict) -> dict:
    exact_keys(payload, ("patch", "budget", "evidence", "generationSource"), "proposal")
    try:
        raw = dump(payload).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise invalid("proposal", "候选不能安全序列化。") from exc
    if len(raw) > MAX_OUTPUT_BYTES:
        raise invalid("proposal", "候选超过 256 KiB 输出上限。")
    patch, budget = _validate(payload["patch"], payload["budget"], frozen_input)
    if payload["evidence"] != frozen_input["source"]["evidence"] or payload["generationSource"] != generation_source(frozen_input):
        raise invalid("proposal.evidence", "候选依据及生成来源必须与固定输入完全一致。")
    try:
        evidence = [snapshot(ProposalEvidenceView.model_validate(item)) for item in payload["evidence"]]
        source = snapshot(GenerationSourceView.model_validate(payload["generationSource"]))
    except ValidationError as exc:
        raise invalid("proposal.evidence", "固定来源结构不符合契约。") from exc
    return dict(patch=patch, budget=budget, evidence=evidence, generationSource=source)
