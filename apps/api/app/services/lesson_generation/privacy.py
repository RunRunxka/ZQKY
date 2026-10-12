"""Known-source PII blocking, not a claim of universal anonymization."""
from __future__ import annotations

import re
import unicodedata
import json
from .common import dump, invalid, parse_output

# Explicit identity labels remain prohibited even when a person is not in the
# selected report. This deliberately blocks rather than guesses a replacement.
IDENTITY_MARKER = re.compile(
    r"(?:(?:学生|学员)(?:姓名|名字|学号|编号|身份|id)|姓名|学号|学籍号|身份证|手机号|电话号码|"
    r"student\s*[_-]?\s*(?:id|no|number|name)|participant\s*[_-]?\s*id)\s*[:：=]?",
    re.IGNORECASE,
)


def normalized(text: str) -> str:
    # Also catches pasted zero-width separators and Unicode compatibility forms.
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def personal_tokens(report: dict) -> list[str]:
    result = set()
    participants = list(report.get("participants", []))
    participants.extend(row.get("participant", {}) for row in report.get("students", []))
    for participant in participants:
        for key in ("name", "studentNo", "studentId", "participantId"):
            value = participant.get(key)
            if isinstance(value, str) and value.strip():
                result.add(value)
    return sorted(result)


def check_text(text: str, tokens: list[str], field="modelPayload") -> None:
    candidate = normalized(text)
    if IDENTITY_MARKER.search(candidate):
        raise invalid(field, "教学输入含明确个人身份标记，请移除学生个人信息后重试。", "LESSON_PERSONAL_INFO")
    for token in tokens:
        token = normalized(token)
        # Very short ASCII names/IDs require word boundaries, otherwise a name
        # 'A' would block every English teaching word. Longer and Chinese tokens
        # are matched literally, including concatenated identity strings.
        if token.isascii() and token.isdigit():
            found = re.search(r"(?<![0-9])" + re.escape(token) + r"(?![0-9])", candidate)
        elif token.isascii() and len(token) <= 2:
            found = re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", candidate)
        else:
            found = token in candidate
        if found:
            raise invalid(field, "教学输入包含固定报告中的已知个人信息，请移除后重试。", "LESSON_PERSONAL_INFO")


def check_tree(value, tokens: list[str], field="modelPayload") -> None:
    if isinstance(value, str):
        check_text(value, tokens, field)
    elif isinstance(value, dict):
        for key, child in value.items():
            check_text(str(key), tokens, field)
            check_tree(child, tokens, field)
    elif isinstance(value, list):
        for child in value:
            check_tree(child, tokens, field)


COUNT_FIELDS = {"selectedCount", "validCount", "needsCount", "incompleteCount",
                "noEvidenceCount", "fullCreditCount", "numerator", "denominator"}
LESSON_TEXT_FIELDS = {"coreCompetencies", "keyPoints", "teachingDesign", "exercises"}


def _require(condition, field):
    if not condition:
        raise invalid(field, "模型请求含未核准的结构、匿名别名或消息。", "LESSON_PERSONAL_INFO")


def _keys(value, keys, field):
    _require(isinstance(value, dict) and set(value) == set(keys), field)


def _free_text(value, tokens, field):
    _require(isinstance(value, str), field)
    check_text(value, tokens, field)


def check_model_payload(payload: dict, tokens: list[str]) -> None:
    """Only precise generated alias/count paths bypass identity text matching.

    JSON keys, alias suffixes and integer counts are syntax from the service, not
    person-supplied prose. A value moved into a free-text path is checked again.
    """
    _keys(payload, {"lesson", "classSummary", "requirements", "durationMinutes", "evidence",
                    "processAliases", "newProcessAliases"}, "modelPayload")
    _keys(payload["lesson"], LESSON_TEXT_FIELDS | {"process"}, "modelPayload.lesson")
    for key in LESSON_TEXT_FIELDS:
        _free_text(payload["lesson"][key], tokens, "modelPayload.lesson." + key)
    process = payload["lesson"]["process"]
    _require(isinstance(process, list) and len(process) <= 100, "modelPayload.lesson.process")
    aliases = [f"P{n}" for n in range(1, len(process) + 1)]
    _require(payload["processAliases"] == aliases, "modelPayload.processAliases")
    _require(payload["newProcessAliases"] == [f"new:N{n}" for n in range(1, 13)], "modelPayload.newProcessAliases")
    for n, item in enumerate(process):
        field = f"modelPayload.lesson.process[{n}]"
        _keys(item, {"id", "stage", "design", "secondary"}, field)
        _require(item["id"] == aliases[n], field + ".id")
        for key in ("stage", "design", "secondary"):
            _free_text(item[key], tokens, field + "." + key)
    _keys(payload["classSummary"], {"knowledgePoints"}, "modelPayload.classSummary")
    points = payload["classSummary"]["knowledgePoints"]
    _require(isinstance(points, list) and 1 <= len(points) <= 50, "modelPayload.classSummary.knowledgePoints")
    for n, item in enumerate(points, 1):
        field = f"modelPayload.classSummary.knowledgePoints[{n-1}]"
        _keys(item, {"alias", "name", "counts"}, field)
        _require(item["alias"] == f"K{n}", field + ".alias")
        _free_text(item["name"], tokens, field + ".name")
        _keys(item["counts"], COUNT_FIELDS, field + ".counts")
        _require(all(type(value) is int and value >= 0 for value in item["counts"].values()), field + ".counts")
    _require(type(payload["durationMinutes"]) is int and 5 <= payload["durationMinutes"] <= 180, "modelPayload.durationMinutes")
    _free_text(payload["requirements"], tokens, "modelPayload.requirements")
    evidence = payload["evidence"]
    _require(isinstance(evidence, list) and 1 <= len(evidence) <= 31, "modelPayload.evidence")
    limits, prefixes, counts = {"textbook": 6, "question": 20, "practice": 5}, {"textbook": "E", "question": "Q", "practice": "R"}, {}
    for n, item in enumerate(evidence):
        field = f"modelPayload.evidence[{n}]"
        _keys(item, {"alias", "kind", "title", "text"}, field)
        kind = item["kind"]
        _require(kind in limits, field + ".kind")
        counts[kind] = counts.get(kind, 0) + 1
        _require(counts[kind] <= limits[kind] and item["alias"] == prefixes[kind] + str(counts[kind]), field + ".alias")
        _free_text(item["title"], tokens, field + ".title")
        _free_text(item["text"], tokens, field + ".text")
    _require(counts.get("textbook", 0) >= 1, "modelPayload.evidence")


def check_candidate_text(patch, budget, tokens, *, allowed_ids, knowledge_aliases, evidence_aliases):
    """Called after the strict candidate validator; verify every exempt path."""
    _require(isinstance(patch, dict) and set(patch) <= LESSON_TEXT_FIELDS | {"process"} and "process" in patch, "candidate.patch")
    for key in LESSON_TEXT_FIELDS:
        if patch.get(key) is not None:
            _free_text(patch[key], tokens, "candidate.patch." + key)
    for n, item in enumerate(patch["process"]):
        field = f"candidate.patch.process[{n}]"
        _keys(item, {"id", "stage", "design", "secondary"}, field)
        _require(item["id"] in allowed_ids, field + ".id")
        for key in ("stage", "design", "secondary"):
            _free_text(item[key], tokens, field + "." + key)
    _keys(budget, {"durationMinutes", "stages"}, "candidate.budget")
    _require(type(budget["durationMinutes"]) is int, "candidate.budget.durationMinutes")
    for n, item in enumerate(budget["stages"]):
        field = f"candidate.budget.stages[{n}]"
        _keys(item, {"processId", "phase", "minutes", "knowledgeAliases", "activity", "check", "evidenceAliases"}, field)
        _require(item["processId"] in allowed_ids, field + ".processId")
        _require(item["phase"] in {"introduction", "exploration", "practice", "conclusion"} and type(item["minutes"]) is int, field)
        _require(set(item["knowledgeAliases"]) <= knowledge_aliases and set(item["evidenceAliases"]) <= evidence_aliases, field)
        for key in ("activity", "check"):
            _free_text(item[key], tokens, field + "." + key)


def check_wire(body: dict, tokens: list[str], *, protocol: str, model_payload: dict, system_prompt: str) -> None:
    """Inspect serialized provider JSON, strict-parse user JSON and check paths.

    Never scan an entire encoded JSON string as person-supplied prose: doing so
    confuses anonymous aliases, structural literals and aggregate integers with
    short student numbers. Unknown fields/messages/tool data are still rejected.
    """
    wire = json.loads(dump(body))
    _require(isinstance(wire, dict), "providerRequest")
    optional = {"temperature", "top_p", "reasoning_effort", "thinking", "enable_thinking", "reasoning_split"}
    if protocol == "openai-chat":
        required = {"model", "messages"}
        _require(set(wire) <= required | optional | {"max_tokens", "max_completion_tokens"} and required <= set(wire), "providerRequest")
        messages = wire["messages"]
        _require(isinstance(messages, list) and len(messages) == 2, "providerRequest.messages")
        for item in messages: _keys(item, {"role", "content"}, "providerRequest.messages")
        _require(messages[0]["role"] == "system" and messages[0]["content"] == system_prompt and messages[1]["role"] == "user", "providerRequest.messages")
        user_text = messages[1]["content"]
    elif protocol == "openai-responses":
        _require(set(wire) <= {"model", "input", "max_output_tokens", "reasoning"} and {"model", "input"} <= set(wire), "providerRequest")
        messages = wire["input"]
        _require(isinstance(messages, list) and len(messages) == 2, "providerRequest.input")
        parts = []
        for n, item in enumerate(messages):
            _keys(item, {"role", "content"}, "providerRequest.input")
            _require(item["role"] == ("system" if n == 0 else "user") and isinstance(item["content"], list) and len(item["content"]) == 1, "providerRequest.input")
            part = item["content"][0]
            _keys(part, {"type", "text"}, "providerRequest.input.content")
            _require(part["type"] == "input_text", "providerRequest.input.content.type")
            parts.append(part["text"])
        _require(parts[0] == system_prompt, "providerRequest.input.system")
        user_text = parts[1]
        if "reasoning" in wire:
            _keys(wire["reasoning"], {"effort", "summary"}, "providerRequest.reasoning")
            _require(wire["reasoning"]["summary"] == "auto", "providerRequest.reasoning.summary")
            _free_text(wire["reasoning"]["effort"], tokens, "providerRequest.reasoning.effort")
    elif protocol == "anthropic-messages":
        _require(set(wire) <= {"model", "messages", "max_tokens", "system", "thinking", "temperature"} and {"model", "messages", "max_tokens", "system"} <= set(wire), "providerRequest")
        _require(wire["system"] == system_prompt, "providerRequest.system")
        messages = wire["messages"]
        _require(isinstance(messages, list) and len(messages) == 1, "providerRequest.messages")
        _keys(messages[0], {"role", "content"}, "providerRequest.messages")
        _require(messages[0]["role"] == "user", "providerRequest.messages.role")
        user_text = messages[0]["content"]
    else:
        _require(False, "providerRequest.protocol")
    _free_text(wire["model"], tokens, "providerRequest.model")
    for key in ("reasoning_effort",):
        if key in wire: _free_text(wire[key], tokens, "providerRequest." + key)
    if "thinking" in wire:
        thinking = wire["thinking"]
        _require(isinstance(thinking, dict) and set(thinking) <= {"type", "budget_tokens"} and "type" in thinking, "providerRequest.thinking")
        _free_text(thinking["type"], tokens, "providerRequest.thinking.type")
        _require(thinking["type"] in {"enabled", "disabled"} and ("budget_tokens" not in thinking or type(thinking["budget_tokens"]) is int), "providerRequest.thinking")
    for key in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if key in wire: _require(type(wire[key]) is int and wire[key] > 0, "providerRequest." + key)
    for key in ("temperature", "top_p"):
        if key in wire: _require(type(wire[key]) in (int, float), "providerRequest." + key)
    for key in ("enable_thinking", "reasoning_split"):
        if key in wire: _require(type(wire[key]) is bool, "providerRequest." + key)
    _require(isinstance(user_text, str), "providerRequest.user")
    parsed = parse_output(user_text)
    _require(parsed == model_payload, "providerRequest.user")
    check_model_payload(parsed, tokens)
