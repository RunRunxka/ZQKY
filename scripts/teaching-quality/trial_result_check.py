"""New-label B7-B result integrity; never grades teaching or native layout."""
from __future__ import annotations

import argparse
import ast
import builtins
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import zipfile

from PIL import Image, ImageFile, UnidentifiedImageError

from common import (CheckError, canonical, checked_json, create_output, exact_object,
                    known_case_ids, positive_int, require, sha_file, strict_json,
                    trimmed_string, write_json, live_scope)

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("coreCompetencies", "keyPoints", "teachingDesign", "process", "exercises")
TEACHER_FIELDS = ("title", "totalLessons", "currentLessonNo", "lessonTypes", "otherTypeText", "reflection")
DIMENSIONS = ("facts", "material", "coverage", "activity", "time", "control", "accuracy", "feedback")
NATIVE_CHECKS = ("secondary", "chineseSymbols", "mergedCells", "crossPage", "clipping")
ARTIFACTS = {"frozenInput", "raw", "wire", "usage", "attempt", "job", "candidate", "selectedFields", "applied", "docx"}
# Registered live provenance: only this proof kind / tokenizer revision may carry a live result.
LIVE_PROOF_KIND = "deepseek-v4-flash-openai-chat-reasoning-probe-v1"
LIVE_TOKENIZER_SHA256 = "89085f12ef79460ac5f66d1119325ddfc694b4ab209d80bbd81d35f081dc9614"
LIVE_MODEL_ID = "deepseek-flash"
LIVE_PROFILE_ID = "63b3ffdc87fb4c8f8b278c3b58923296"
LIVE_PROOF_FIELDS = {"schemaVersion", "proofKind", "evidenceKind", "modelProfileId", "modelId", "wireSHA", "inputUpper", "outputUpper", "reasoningUpper", "otherUpper", "tokenizerSHA256", "tokenizerSourceURL", "officialFacts", "probeFacts", "proofSHA"}
LIVE_USAGE_ALLOWED = {"prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "prompt_tokens_details", "completion_tokens_details"}
ORIGINAL_SPECS = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json"
ORIGINAL_SPEC_SHA = "353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55"
PRODUCTION_REQUIRED = {"apps/api/app/services/lesson_generation/validation.py", "apps/api/app/services/lesson_generation/privacy.py", "apps/api/app/services/lesson_generation/common.py", "apps/api/app/services/lesson_generation/service.py", "apps/api/app/services/lesson_generation/preparation.py", "apps/api/app/services/model_runtime.py", "apps/api/app/providers/llm/base.py", "apps/api/app/providers/llm/openai_chat.py", "apps/api/app/providers/llm/openai_responses.py", "apps/api/app/providers/llm/anthropic_messages.py", "apps/api/app/services/jobs/engine.py", "apps/api/app/contracts/lesson_plans.py"}
EXECUTOR_REQUIRED = {"scripts/teaching-quality/controlled_trial.py", "scripts/teaching-quality/controlled_scope.py", "scripts/teaching-quality/controlled_provider.py", "scripts/teaching-quality/controlled_ledger.py", "scripts/teaching-quality/controlled_guard.py", "scripts/teaching-quality/controlled_fixtures.py", "scripts/teaching-quality/common.py"}
MANIFEST_FIELDS = {"schemaVersion", "mode", "evidenceKind", "reviewLabel", "scopeSHA", "authorizationSHA",
                   "selectedCaseIds", "unrunCaseIds", "productionSourceSHA", "executorSourceSHA", "cases",
                   "stopReason", "realModelCalls", "fixtureWireSends", "ledgerRef", "technicalGate"}
CASE_FIELDS = {"caseId", "caseSpecSHA", "inputHash", "modelFingerprint", "jobId", "jobAttempt", "caseAttempt",
               "providerSendCount", "status", "technicalStatus", "teacherStatus", "nativeStatus", "artifacts"}
ATTEMPT_FIELDS = {"schemaVersion", "ticketId", "caseId", "scopeSHA", "jobId", "jobAttempt", "caseAttempt", "modelFingerprint", "inputHash", "wireSHA", "rawSHA", "usageSHA", "reservedTokens", "settledTokens", "providerSendCount", "state", "boundProofSHA", "runLabel"}
SECRET = re.compile(r"(?i)(?:bearer\s+[a-z0-9._-]+|(?:api[_-]?key|authorization|x-api-key)\s*[\"']?\s*[:=]|sk-[a-z0-9_-]{8,})")
# Declared native page-image bounds; the real decoder below must fit inside them.
NATIVE_IMAGE_EXTENSIONS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
MAX_NATIVE_PAGE_IMAGE_BYTES = 32 * 1024 * 1024
MAX_NATIVE_PAGE_IMAGE_PIXELS = 40_000_000
MAX_NATIVE_PAGE_IMAGE_DIMENSION = 20_000
MAX_NATIVE_PAGE_IMAGE_FRAMES = 64
ImageFile.LOAD_TRUNCATED_IMAGES = False  # strict mode: truncated pixel data must raise, never decode leniently


def same(actual, expected, field):
    require(canonical(actual) == canonical(expected), field, "frozen identity or fact differs", "IDENTITY_MISMATCH")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(value, field):
    require(type(value) is str and bool(re.fullmatch(r"[0-9a-f]{64}", value)), field, "lowercase SHA-256 required")
    return value


def nonnegative(value, field):
    require(type(value) is int and value >= 0, field, "exact nonnegative integer required")
    return value


def stamp(value, field):
    trimmed_string(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckError(field, "ISO timestamp with timezone required") from exc
    require("T" in value and parsed.tzinfo is not None, field, "ISO timestamp with timezone required")


def safe_text(value, field):
    trimmed_string(value, field)
    require(not SECRET.search(value), field, "credential material is prohibited", "SECRET_MATERIAL")
    return value


def no_secret_tree(value, field):
    if isinstance(value, str):
        require(not SECRET.search(value), field, "credential material is prohibited", "SECRET_MATERIAL")
    elif isinstance(value, dict):
        for key, child in value.items():
            require(not SECRET.search(str(key)), field, "credential material is prohibited", "SECRET_MATERIAL")
            require(str(key).lower().replace("_", "-") not in {"authorization", "api-key", "apikey", "x-api-key", "headers", "credential", "credentials"}, field, "credential/header fields are prohibited", "SECRET_MATERIAL")
            no_secret_tree(child, field)
    elif isinstance(value, list):
        for child in value:
            no_secret_tree(child, field)


def ref_path(ref, root, field):
    exact_object(ref, field, {"file", "sha256"}, {"file", "sha256"})
    value = trimmed_string(ref["file"], field + ".file")
    sha(ref["sha256"], field + ".sha256")
    relative = Path(value)
    require(not relative.is_absolute() and ".." not in relative.parts, field, "artifact must be within its new label")
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), field, "artifact escapes new label")
    same(sha_file(path), ref["sha256"], field + ".sha256")
    return path


def artifact(record, name, root, *, optional=False, text=False):
    ref = record["artifacts"][name]
    if ref is None:
        require(optional, "artifacts." + name, "required evidence is missing", "MISSING_EVIDENCE")
        return None
    path = ref_path(ref, root, "artifacts." + name)
    return path.read_text(encoding="utf-8") if text else strict_json(path)


def production():
    # No app.main; package initialization also imports preparation/service.
    # CLI establishes isolation first and records every actual app module.
    sys.path.insert(0, str(ROOT / "apps/api"))
    from app.services.lesson_generation.common import parse_output
    from app.services.lesson_generation.validation import normalize_model_output, validate_for_apply
    from app.services.lesson_generation.privacy import check_model_payload, check_wire
    service = ROOT / "apps/api/app/services/lesson_generation/service.py"
    tree = ast.parse(service.read_text(encoding="utf-8"))
    prompt = next(ast.literal_eval(node.value) for node in tree.body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SYSTEM_PROMPT" for t in node.targets))
    return parse_output, normalize_model_output, validate_for_apply, check_model_payload, check_wire, prompt


def fixed_facts(frozen, spec):
    same(frozen["durationMinutes"], spec["durationMinutes"], "durationMinutes")
    same(frozen["requirements"], spec["requirements"], "requirements")
    same(frozen["modelPayload"]["durationMinutes"], spec["durationMinutes"], "modelPayload.durationMinutes")
    same(frozen["modelPayload"]["requirements"], spec["requirements"], "modelPayload.requirements")
    points = frozen["source"]["selectedKnowledgePoints"]
    same(len(points), len(spec["selectedKnowledgeIndexes"]), "selectedKnowledgePoints.length")
    same(frozen["contextSnapshot"]["analysis"]["knowledgePoints"], points, "context.knowledgePoints")
    same(list(frozen["source"]["knowledgeAliases"].values()), points, "knowledgeAliases")
    report = frozen["source"]["report"]
    same(report["reportReady"], True, "reportReady")
    same(report["ruleCode"], "any_loss_v1", "ruleCode")
    same(report["runId"], frozen["analysisRunId"], "analysisRunId")
    for key in ("scoreRevisionId", "paperRevisionId", "inputHash"):
        same(report[key], frozen["contextSnapshot"]["analysis"][key], "report." + key)
    counts = frozen["modelPayload"]["classSummary"]["knowledgePoints"]
    same(len(counts), len(points), "classSummary.length")
    for i, (point, expected) in enumerate(zip(points, spec["expectedTargetCounts"])):
        same(counts[i]["alias"], f"K{i+1}", "classSummary.alias")
        same(counts[i]["counts"], {key: value for key, value in expected.items() if key != "ratio"}, "classSummary.counts")
        rows = [row for row in report["classes"] if row["classId"] == frozen["classId"] and row["knowledgePoint"] == point]
        require(len(rows) == 1, "report.classes", "exactly one frozen target class/KP required")
        same({key: rows[0][key] for key in expected}, expected, "report.classCounts")
        if expected["denominator"] == 0:
            same(rows[0]["ratio"], None, "report.zeroDenominator")
        if spec["caseId"] == "C08":
            same(rows[0]["className"], None, "historicalClassName")
    selected = [spec["participants"][i] for i in spec["selectedParticipantIndexes"]]
    actual = report["participants"]
    same(len(actual), len(selected), "selectedParticipants.length")
    # Production report participants are sorted by generated participantId, not
    # handwritten source order. Match explicit attempt/attendance/target-class
    # facts as a multiset; generated IDs never become a fixture quality oracle.
    expected_participants = sorted((p["attemptNo"], p["attendance"], p["classIndex"] == spec["selectedClassIndex"]) for p in selected)
    actual_participants = sorted((p["attemptNo"], p["attendance"], p["classId"] == frozen["classId"]) for p in actual)
    same(actual_participants, expected_participants, "participants.explicitAttemptAttendanceClass")
    if actual and all("studentId" in p for p in actual):
        same(len({p["studentId"] for p in actual}), len({p["alias"] for p in selected}), "participants.uniqueStudentIdentity")
    state_counts = {status: 0 for status in ("recorded", "missing", "absent", "exempt")}
    for participant in selected:
        for cell in participant["cells"]:
            state_counts[cell[0]] += 1
    selection = report["selectionSnapshot"]
    same(selection["stateCounts"], state_counts, "selection.fourStates")
    same(selection["uniqueStudentCount"], len({p["alias"] for p in selected}), "selection.uniqueStudents")
    same(selection["participantCount"], len(selected), "selection.participantCount")
    questions = frozen["source"].get("questions", [])
    if spec["questionSource"] == "confirmed":
        require(type(questions) is list and bool(questions) and all(q.get("question_status") == "confirmed" for q in questions), "source.questions", "fixed case requires confirmed question sources")
    elif spec["questionSource"] == "gap":
        same(questions, [], "source.questionCoverageGap")
    require(all(p.get("state", "reviewed") == "reviewed" for p in frozen["source"].get("practices", [])), "source.practices", "only reviewed fixed practice sources permitted")


def applied_check(value, candidate, selected):
    exact_object(value, "applied", {"beforeData", "afterData", "selectionActor", "revisionId"}, {"beforeData", "afterData", "selectionActor", "revisionId"})
    require(value["selectionActor"] in {"qa", "human"}, "selectionActor", "qa or human required")
    trimmed_string(value["revisionId"], "revisionId")
    before, after = value["beforeData"], value["afterData"]
    exact_object(before, "beforeData", set(FIELDS + TEACHER_FIELDS), set(FIELDS + TEACHER_FIELDS))
    exact_object(after, "afterData", set(FIELDS + TEACHER_FIELDS), set(FIELDS + TEACHER_FIELDS))
    require(type(selected) is list and bool(selected) and len(selected) == len(set(selected)), "selectedFields", "nonempty unique list required")
    require(set(selected) <= set(FIELDS), "selectedFields", "only five AI fields selectable")
    for key in TEACHER_FIELDS + tuple(field for field in FIELDS if field not in selected):
        same(after[key], before[key], "applied.preserved." + key)
    for key in selected:
        require(candidate["patch"].get(key) is not None, "selectedFields", "selected candidate field is absent")
        same(after[key], candidate["patch"][key], "applied.selected." + key)
    return "pass_qa_selection" if value["selectionActor"] == "qa" else "pass_human_selection_integrity"


def docx_bound(ref, root):
    path = ref_path(ref, root, "docx")
    require(path.suffix.lower() == ".docx", "docx", "new working copy must be DOCX")
    try:
        with zipfile.ZipFile(path) as archive:
            require(archive.testzip() is None and {"[Content_Types].xml", "word/document.xml"} <= set(archive.namelist()), "docx", "DOCX package or CRC invalid")
    except (zipfile.BadZipFile, OSError) as exc:
        raise CheckError("docx", "DOCX package invalid") from exc


def manifest_check(path, expected_sha, case_path, case_sha):
    manifest = checked_json(path, expected_sha)
    no_secret_tree(manifest, "manifest")
    exact_object(manifest, "manifest", MANIFEST_FIELDS, MANIFEST_FIELDS)
    same(manifest["schemaVersion"], 1, "schemaVersion")
    require(manifest["mode"] in {"dry-run", "live"}, "mode", "dry-run or live required")
    same(manifest["evidenceKind"], "fixture" if manifest["mode"] == "dry-run" else "live", "evidenceKind")
    trimmed_string(manifest["reviewLabel"], "reviewLabel")
    sha(manifest["scopeSHA"], "scopeSHA")
    safe_text(manifest["technicalGate"], "technicalGate")
    if manifest["stopReason"] is not None:
        safe_text(manifest["stopReason"], "stopReason")
    if manifest["mode"] == "live":
        sha(manifest["authorizationSHA"], "authorizationSHA")
        # Live results are accepted only through the registered model proof: every case
        # that actually sent must carry a billingProof artifact of the registered kind
        # (validated per case below). A fixture snapshot relabelled live still fails,
        # because it has no live proof artifact bound to its wire/model/profile.
    else:
        require(manifest["authorizationSHA"] is None, "authorizationSHA", "dry-run does not create human authorization")
    specs = checked_json(case_path, case_sha)
    original_specs = checked_json(ORIGINAL_SPECS, ORIGINAL_SPEC_SHA)
    same(specs, original_specs, "caseSpecs.originalHandwrittenFacts")
    known = known_case_ids(specs)
    ids = manifest["selectedCaseIds"]
    require(type(ids) is list and ids and len(ids) == len(set(ids)) and set(ids) <= set(known), "selectedCaseIds", "explicit unique known set required")
    same(manifest["unrunCaseIds"], [case for case in known if case not in ids], "unrunCaseIds")
    require(type(manifest["cases"]) is list, "cases", "list required")
    same([case.get("caseId") for case in manifest["cases"]], ids, "cases.order")
    for source_map, required, prefix in ((manifest["productionSourceSHA"], PRODUCTION_REQUIRED, "apps/api/app/"), (manifest["executorSourceSHA"], EXECUTOR_REQUIRED, "scripts/teaching-quality/")):
        require(type(source_map) is dict and source_map, "sourceSHA", "explicit source SHA map required")
        require(required <= set(source_map), "sourceSHA", "minimum production/executor source closure is missing", "MISSING_SOURCE_CLOSURE")
        for file, expected in source_map.items():
            require(type(file) is str and file.startswith(prefix) and file.endswith(".py") and "\\" not in file, "sourceSHA.file", "only explicit safe product/executor Python source paths allowed")
            ref_path({"file": file, "sha256": expected}, ROOT, "sourceSHA")
    require(manifest["ledgerRef"] is not None, "ledgerRef", "SHA-bound ledger/scope audit snapshot is required", "MISSING_SCOPE_BINDING")
    ledger_path = ref_path(manifest["ledgerRef"], path.parent, "ledgerRef")
    ledger = strict_json(ledger_path)
    no_secret_tree(ledger, "ledger")
    ledger_fields = {"schemaVersion", "authorizationId", "scopeSHA", "scope", "evidenceKind", "stopReason", "attempts", "tickets"}
    exact_object(ledger, "ledger", ledger_fields, ledger_fields)
    same(ledger["schemaVersion"], 1, "ledger.schemaVersion")
    live_scope(ledger["scope"], known)
    if manifest["mode"] == "live":
        require(not any(marker in ledger["scope"][key].lower() for key in ("modelProfileId", "modelId") for marker in ("fixture", "isolated", "mock")), "live.model", "fixture identity cannot be reported as live", "FIXTURE_NOT_LIVE")
    same(digest(ledger["scope"]), manifest["scopeSHA"], "scopeSHA.independentRecompute")
    same(ledger["scopeSHA"], manifest["scopeSHA"], "ledger.scopeSHA")
    same(ledger["scope"]["caseIds"], ids, "scope.selectedCaseIds")
    same(ledger["evidenceKind"], manifest["evidenceKind"], "ledger.evidenceKind")
    safe_text(ledger["authorizationId"], "ledger.authorizationId")
    same(ledger["stopReason"], manifest["stopReason"], "ledger.stopReason")
    require(type(ledger["tickets"]) is list and type(ledger["attempts"]) is dict, "ledger", "ticket list and attempt map required")
    require(len({ticket.get("ticketId") for ticket in ledger["tickets"]}) == len(ledger["tickets"]), "ledger.tickets", "duplicate ticket identity")
    ledger_sends = 0
    ordinals = {}
    for ticket in ledger["tickets"]:
        exact_object(ticket, "ledger.ticket", ATTEMPT_FIELDS, ATTEMPT_FIELDS)
        same(ticket["schemaVersion"], 1, "ledger.ticket.schemaVersion")
        require(ticket.get("caseId") in ids, "ledger.ticket.caseId", "ticket lies outside immutable scope selection")
        same(ticket.get("scopeSHA"), manifest["scopeSHA"], "ledger.ticket.scopeSHA")
        for key in ("ticketId", "jobId", "runLabel"):
            safe_text(ticket[key], "ledger.ticket." + key)
        for key in ("jobAttempt", "caseAttempt", "reservedTokens"):
            positive_int(ticket[key], "ledger.ticket." + key)
        for key in ("inputHash", "wireSHA", "boundProofSHA"):
            sha(ticket[key], "ledger.ticket." + key)
        for key in ("rawSHA", "usageSHA"):
            if ticket[key] is not None:
                sha(ticket[key], "ledger.ticket." + key)
        require(type(ticket["modelFingerprint"]) is str and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", ticket["modelFingerprint"])), "ledger.ticket.modelFingerprint", "production SHA fingerprint required")
        expected_ordinal = ordinals.get(ticket["caseId"], 0) + 1
        same(ticket["caseAttempt"], expected_ordinal, "ledger.ticket.attemptSequence")
        require(expected_ordinal <= ledger["scope"]["maxAttempts"], "ledger.ticket.caseAttempt", "ticket outside immutable attempt bound")
        ordinals[ticket["caseId"]] = expected_ordinal
        count = nonnegative(ticket.get("providerSendCount"), "ledger.ticket.providerSendCount")
        require(count in {0, 1}, "ledger.ticket.providerSendCount", "one ticket cannot represent hidden retry sends")
        require(ticket["state"] in {"reserved", "dispatched", "responded", "unknown", "settled"}, "ledger.ticket.state", "explicit executor ticket state required")
        require(ticket["state"] != "reserved" or count == 0, "ledger.ticket.state", "reservation cannot already contain a send")
        require(ticket["state"] not in {"dispatched", "responded", "settled"} or count == 1, "ledger.ticket.state", "dispatched ticket must contain one send")
        require(ticket["state"] != "unknown" or bool(ledger["stopReason"]), "ledger.stopReason", "uncertain ticket must stop its authorization")
        if ticket["state"] == "settled":
            nonnegative(ticket["settledTokens"], "ledger.ticket.settledTokens")
            require(ticket["settledTokens"] <= ticket["reservedTokens"], "ledger.ticket.settledTokens", "settlement exceeds reservation")
        else:
            same(ticket["settledTokens"], None, "ledger.ticket.settledTokens")
        require(ticket["state"] not in {"responded", "settled"} or (ticket["rawSHA"] is not None and ticket["usageSHA"] is not None), "ledger.ticket.response", "returned response hashes missing")
        if ticket.get("runLabel") == manifest["reviewLabel"]:
            ledger_sends += count
    same(ledger["attempts"], ordinals, "ledger.attempts.independentTicketCounts")
    sends = 0
    for case in manifest["cases"]:
        exact_object(case, "case", CASE_FIELDS, CASE_FIELDS)
        same(case["caseSpecSHA"], digest(next(s for s in specs["cases"] if s["caseId"] == case["caseId"])), "caseSpecSHA")
        exact_object(case["artifacts"], "artifacts", ARTIFACTS | {"billingProof"}, ARTIFACTS)
        if manifest["mode"] == "live" and case["providerSendCount"] > 0:
            require(case["artifacts"].get("billingProof") is not None, "artifacts.billingProof", "sent live case must carry its registered model proof", "LIVE_PROOF_UNREGISTERED")
            proof = artifact(case, "billingProof", path.parent)
            exact_object(proof, "billingProof", LIVE_PROOF_FIELDS, LIVE_PROOF_FIELDS)
            same(proof["schemaVersion"], 1, "billingProof.schemaVersion")
            require(proof["proofKind"] == LIVE_PROOF_KIND, "billingProof.proofKind", "proof kind is not registered as live provenance", "LIVE_PROOF_UNREGISTERED")
            same(proof["evidenceKind"], "live", "billingProof.evidenceKind")
            same(proof["modelProfileId"], ledger["scope"]["modelProfileId"], "billingProof.modelProfileId")
            same(proof["modelId"], ledger["scope"]["modelId"], "billingProof.modelId")
            require(proof["tokenizerSHA256"] == LIVE_TOKENIZER_SHA256, "billingProof.tokenizerSHA256", "tokenizer revision is not the registered one", "LIVE_PROOF_UNREGISTERED")
            require(proof["modelId"] == LIVE_MODEL_ID and proof["modelProfileId"] == LIVE_PROFILE_ID, "billingProof.model", "proof is not the registered model/profile", "LIVE_PROOF_UNREGISTERED")
            for key in ("inputUpper", "outputUpper", "reasoningUpper", "otherUpper"):
                nonnegative(proof[key], "billingProof." + key)
            same(proof["reasoningUpper"], 0, "billingProof.reasoningUpper")
            same(proof["otherUpper"], 0, "billingProof.otherUpper")
            sha(proof["wireSHA"], "billingProof.wireSHA")
            sha(proof["proofSHA"], "billingProof.proofSHA")
            wire_value = artifact(case, "wire", path.parent, optional=True)
            if wire_value is not None:
                same(proof["wireSHA"], digest(wire_value), "billingProof.wireSHA.actualWire")
                caps = [wire_value[key] for key in ("max_tokens", "max_completion_tokens", "max_output_tokens") if key in wire_value]
                require(len(caps) == 1, "billingProof.wireCap", "single generation cap required", "LIVE_PROOF_UNREGISTERED")
                same(proof["outputUpper"], caps[0], "billingProof.outputUpper.wireCap")
            require(type(proof["officialFacts"]) is dict and bool(proof["officialFacts"]) and type(proof["probeFacts"]) is dict and bool(proof["probeFacts"]), "billingProof.facts", "proof facts missing", "LIVE_PROOF_UNREGISTERED")
            require(proof["inputUpper"] > 0 and proof["outputUpper"] > 0, "billingProof.bounds", "proof bounds must be positive", "LIVE_PROOF_UNREGISTERED")
        if manifest["mode"] == "live" and case["providerSendCount"] == 0 and case["technicalStatus"] != "unrun":
            same(case["artifacts"].get("billingProof"), None, "artifacts.billingProof")
        for name, ref in case["artifacts"].items():
            if ref is not None:
                ref_path(ref, path.parent, "artifacts." + name)
        sends += nonnegative(case["providerSendCount"], "providerSendCount")
        safe_text(case["status"], "case.status")
        require(case["technicalStatus"] in {"technical_pass", "technical_fail", "unrun"}, "technicalStatus", "explicit technical status required")
        same(case["teacherStatus"], "teacher_pending", "teacherStatus")
        same(case["nativeStatus"], "native_pending", "nativeStatus")
        if case["artifacts"]["attempt"] is not None:
            attempt = artifact(case, "attempt", path.parent)
            tickets = [ticket for ticket in ledger["tickets"] if ticket.get("ticketId") == attempt.get("ticketId")]
            require(len(tickets) == 1, "ledger.ticket", "case attempt not found in SHA-bound audit snapshot")
            same(tickets[0], attempt, "ledger.ticket.artifact")
            require(ledger["attempts"].get(case["caseId"], 0) >= case["caseAttempt"], "ledger.attempts", "case attempt missing from cumulative snapshot")
    same(manifest["realModelCalls"], sends if manifest["mode"] == "live" else 0, "realModelCalls")
    same(manifest["fixtureWireSends"], sends if manifest["mode"] == "dry-run" else 0, "fixtureWireSends")
    same(sends, ledger_sends, "sendCount.independentLedgerRunLabel")
    if manifest["ledgerRef"] is not None:
        ref_path(manifest["ledgerRef"], path.parent, "ledgerRef")
    return manifest, {s["caseId"]: s for s in specs["cases"]}, ledger


def technical(manifest, specs, root, ledger):
    parse_output, normalize, validate, check_payload, check_wire, prompt = production()
    from app.services.lesson_generation.privacy import check_text
    rows = []
    for case in manifest["cases"]:
        if case["technicalStatus"] == "unrun":
            same(case["providerSendCount"], 0, "unrun.providerSendCount")
            require(case["status"] in {"unrun", "not_run"}, "unrun.status", "unrun cannot claim a finished job")
            require(all(ref is None for ref in case["artifacts"].values()), "unrun", "unrun cannot own prepared/returned/applied/exported evidence")
            for key in ("inputHash", "modelFingerprint", "jobId"):
                same(case[key], None, "unrun." + key)
            for key in ("jobAttempt", "caseAttempt"):
                same(case[key], 0, "unrun." + key)
            rows.append({"caseId": case["caseId"], "technicalStructure": "unrun", "applicationProtection": "not_run", "teacher": "teacher_pending", "native": "native_pending"})
            continue
        if case["providerSendCount"] == 0 and case["artifacts"]["frozenInput"] is None:
            require(case["technicalStatus"] == "technical_fail" and all(case["artifacts"][name] is None for name in ("raw", "usage", "candidate", "applied", "docx")), "unsentFailure", "unsent preparation failure must not own model output")
            rows.append({"caseId": case["caseId"], "technicalStructure": "technical_fail", "fixedFacts": "not_run_missing_prepared_input", "applicationProtection": "not_run", "teacher": "teacher_pending", "native": "native_pending"})
            continue
        frozen = artifact(case, "frozenInput", root)
        same(digest(frozen), case["inputHash"], "inputHash")
        same(frozen["modelProfileId"], ledger["scope"]["modelProfileId"], "scope.modelProfileId")
        positive_int(case["jobAttempt"], "jobAttempt")
        positive_int(case["caseAttempt"], "caseAttempt")
        require(type(case["modelFingerprint"]) is str and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", case["modelFingerprint"])), "modelFingerprint", "production SHA fingerprint required")
        fixed_facts(frozen, specs[case["caseId"]])
        check_payload(frozen["modelPayload"], frozen["source"]["personalTokens"])
        attempt = artifact(case, "attempt", root)
        exact_object(attempt, "attempt", ATTEMPT_FIELDS, ATTEMPT_FIELDS)
        same(attempt["schemaVersion"], 1, "attempt.schemaVersion")
        require(attempt["state"] in {"reserved", "dispatched", "responded", "unknown", "settled"}, "attempt.state", "explicit reservation state required")
        for key in ("caseId", "jobId", "jobAttempt", "caseAttempt", "modelFingerprint", "inputHash", "providerSendCount"):
            same(attempt[key], case[key], "attempt." + key)
        same(attempt["scopeSHA"], manifest["scopeSHA"], "attempt.scopeSHA")
        same(attempt["runLabel"], manifest["reviewLabel"], "attempt.runLabel")
        job = artifact(case, "job", root)
        exact_object(job, "job", {"jobId", "domain", "kind", "attempt", "state", "result", "error"}, {"jobId", "domain", "kind", "attempt", "state", "result", "error"})
        no_secret_tree(job, "job")
        same(job["jobId"], case["jobId"], "job.jobId")
        same(job["attempt"], case["jobAttempt"], "job.attempt")
        same(job["domain"], "teaching", "job.domain")
        same(job["kind"], "lesson_generation", "job.kind")
        require(job["state"] in {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}, "job.state", "production job state required")
        same(case["status"], job["state"], "case.status.jobState")
        wire = artifact(case, "wire", root, optional=case["providerSendCount"] == 0)
        usage = artifact(case, "usage", root, optional=True)
        raw = artifact(case, "raw", root, optional=True, text=True)
        for name in ("wire", "raw", "usage"):
            reference = case["artifacts"][name]
            if name == "raw" and reference is None and attempt["rawSHA"] is not None:
                require(case["technicalStatus"] == "technical_fail" and attempt["state"] == "unknown" and bool(ledger["stopReason"]), "suppressedRaw", "hash-only raw requires a stopped failed attempt")
                sha(attempt["rawSHA"], "suppressedRaw.sha256")
            else:
                same(attempt[name + "SHA"], reference["sha256"] if reference is not None else None, "attempt." + name + "SHA")
        if wire is not None:
            same(wire["model"], ledger["scope"]["modelId"], "scope.modelId")
            require(not SECRET.search(json.dumps(wire, ensure_ascii=False)), "wire", "credential/header material prohibited", "SECRET_MATERIAL")
            protocol = usage["protocol"] if usage is not None else ("anthropic-messages" if "system" in wire else "openai-responses" if "input" in wire else "openai-chat")
            check_wire(wire, frozen["source"]["personalTokens"], protocol=protocol, model_payload=frozen["modelPayload"], system_prompt=prompt)
        if usage is not None:
            no_secret_tree(usage, "usage")
            usage_fields = {"schemaVersion", "caseId", "scopeSHA", "jobId", "jobAttempt", "caseAttempt", "protocol", "evidenceKind", "rawUsage", "normalizedUsage", "validation", "rawSHA", "wireSHA"}
            exact_object(usage, "usage", usage_fields, usage_fields)
            same(usage["schemaVersion"], 1, "usage.schemaVersion")
            exact_object(usage["validation"], "usage.validation", {"status", "reason"}, {"status", "reason"})
            require(usage["validation"]["status"] in {"verified", "uncertain", "out_of_bound"}, "usage.validation.status", "explicit usage verification status required")
            for key in ("caseId", "jobId", "jobAttempt", "caseAttempt"):
                same(usage[key], case[key], "usage." + key)
            same(usage["scopeSHA"], manifest["scopeSHA"], "usage.scopeSHA")
            same(usage["evidenceKind"], manifest["evidenceKind"], "usage.evidenceKind")
            for name in ("raw", "wire"):
                ref = case["artifacts"][name]
                same(usage[name + "SHA"], ref["sha256"] if ref is not None else None, "usage." + name + "SHA")
        if raw is not None:
            require(not SECRET.search(raw), "raw", "credential material prohibited", "SECRET_MATERIAL")
            check_text(raw, frozen["source"]["personalTokens"], "rawEvidence")
        candidate = artifact(case, "candidate", root, optional=True)
        application = "not_run_missing_apply_evidence"
        structure = case["technicalStatus"]
        if structure == "technical_pass":
            require(raw is not None and candidate is not None and usage is not None, "technical_pass", "raw/candidate/usage evidence required")
            same(usage["validation"]["status"], "verified", "usage.validation")
            same(attempt["state"], "settled", "attempt.state")
            same(job["state"], "succeeded", "job.state")
            if "lessonPlanId" in frozen:
                require(type(job["result"]) is dict, "job.result", "successful job result required")
                same(job["result"].get("lessonPlanId"), frozen["lessonPlanId"], "job.result.lessonPlanId")
            require(type(usage["normalizedUsage"]) is dict, "normalizedUsage", "verified normalized usage required")
            exact_object(usage["normalizedUsage"], "normalizedUsage", {"inputTokens", "outputTokens", "totalTokens"}, {"inputTokens", "outputTokens", "totalTokens"})
            for key, value in usage["normalizedUsage"].items():
                nonnegative(value, "normalizedUsage." + key)
            same(usage["normalizedUsage"]["totalTokens"], usage["normalizedUsage"]["inputTokens"] + usage["normalizedUsage"]["outputTokens"], "normalizedUsage.total")
            same(attempt["settledTokens"], usage["normalizedUsage"]["totalTokens"], "attempt.settledUsage")
            raw_usage = usage["rawUsage"]
            in_key, out_key = ("prompt_tokens", "completion_tokens") if usage["protocol"] == "openai-chat" else ("input_tokens", "output_tokens")
            allowed_usage = {in_key, out_key, "total_tokens"}
            if manifest["mode"] == "live" and usage["protocol"] == "openai-chat":
                allowed_usage = allowed_usage | LIVE_USAGE_ALLOWED
            require(type(raw_usage) is dict and {in_key, out_key} <= set(raw_usage) <= allowed_usage, "rawUsage", "unproven billing dimensions or missing raw tokens")
            for key in (in_key, out_key):
                nonnegative(raw_usage[key], "rawUsage." + key)
            if manifest["mode"] == "live" and usage["protocol"] == "openai-chat":
                for name in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
                    if name in raw_usage:
                        nonnegative(raw_usage[name], "rawUsage." + name)
                if "prompt_cache_hit_tokens" in raw_usage and "prompt_cache_miss_tokens" in raw_usage:
                    same(raw_usage["prompt_cache_hit_tokens"] + raw_usage["prompt_cache_miss_tokens"], raw_usage[in_key], "rawUsage.cacheParts")
                for name, key in (("prompt_tokens_details", "cached_tokens"), ("completion_tokens_details", "reasoning_tokens")):
                    if name in raw_usage:
                        exact_object(raw_usage[name], "rawUsage." + name, {key}, {key})
                        nonnegative(raw_usage[name][key], "rawUsage." + name + "." + key)
                if "completion_tokens_details" in raw_usage:
                    require(raw_usage["completion_tokens_details"]["reasoning_tokens"] <= raw_usage[out_key], "rawUsage.reasoning", "reasoning tokens exceed completion tokens; probe containment disproved")
                proof = artifact(case, "billingProof", root)
                require(raw_usage[in_key] <= proof["inputUpper"] and raw_usage[out_key] <= proof["outputUpper"], "usage.proofBound", "returned usage exceeds the registered proof bound")
            same(raw_usage[in_key], usage["normalizedUsage"]["inputTokens"], "rawUsage.normalizedInput")
            same(raw_usage[out_key], usage["normalizedUsage"]["outputTokens"], "rawUsage.normalizedOutput")
            if "total_tokens" in raw_usage:
                same(raw_usage["total_tokens"], usage["normalizedUsage"]["totalTokens"], "rawUsage.normalizedTotal")
            normalized = normalize(parse_output(raw), frozen)
            same(validate(candidate, frozen), normalized, "candidate.normalizedRaw")
            applied = artifact(case, "applied", root, optional=True)
            selected = artifact(case, "selectedFields", root, optional=True)
            require(applied is None or selected is not None, "application", "applied revision requires exact selectedFields")
            if selected is not None:
                require(type(selected) is list and bool(selected) and len(selected) == len(set(selected)) and set(selected) <= set(FIELDS), "selectedFields", "explicit unique allowed fields required")
            if applied is not None:
                application = applied_check(applied, candidate, selected)
        else:
            require(candidate is None, "technical_fail", "failed output cannot own a passed candidate")
            require(job["state"] != "succeeded", "technical_fail", "successful job cannot be labelled failed structure")
            require(case["artifacts"]["applied"] is None and case["artifacts"]["docx"] is None, "technical_fail", "failed result cannot claim applied/exported evidence")
        if case["artifacts"]["docx"] is not None:
            require(case["artifacts"]["applied"] is not None, "docx", "new DOCX requires its fixed applied revision")
            docx_bound(case["artifacts"]["docx"], root)
        rows.append({"caseId": case["caseId"], "technicalStructure": structure, "fixedFacts": "pass", "applicationProtection": application,
                     "export": "not_run_new_docx_not_requested" if case["artifacts"]["docx"] is None else "hash_bound_only",
                     "rawEvidence": "hash_bound_text" if raw is not None else "suppressed_hash_only" if attempt["rawSHA"] is not None else "not_returned",
                     "teacher": "teacher_pending", "native": "native_pending"})
    return rows


def review_identity(value, manifest, case):
    for key, expected in (("reviewLabel", manifest["reviewLabel"]), ("evidenceKind", manifest["evidenceKind"]), ("caseId", case["caseId"]), ("caseSpecSHA", case["caseSpecSHA"])):
        same(value[key], expected, "return." + key)
    for key, name in (("outputSHA", "raw"), ("candidateSHA", "candidate"), ("docxSHA", "docx")):
        require(case["artifacts"][name] is not None, key, "review requires actual output/candidate/DOCX evidence", "MISSING_EVIDENCE")
        same(value[key], case["artifacts"][name]["sha256"], key)
    same(value["reviewerKind"], "human", "reviewerKind")
    safe_text(value["reviewer"], "reviewer")
    stamp(value["reviewedAt"], "reviewedAt")
    require(value["verdict"] in {"usable", "needs_revision", "unusable"}, "verdict", "human verdict required")


def review_privacy(value, case, artifact_root):
    from app.services.lesson_generation.privacy import check_tree
    frozen = artifact(case, "frozenInput", artifact_root)
    fields = {key: value[key] for key in ("reviewer", "suggestion", "dimensions", "hardFailures", "supported", "unsupported", "pages") if key in value}
    # Hashes and page filenames are identity paths, not person-supplied prose.
    if "pages" in fields:
        fields["pages"] = [{key: page[key] for key in ("checks", "reason") if key in page} for page in fields["pages"]]
    check_tree(fields, frozen["source"]["personalTokens"], "humanReturn")


def evidence_note(value, field):
    exact_object(value, field, {"location", "reason"}, {"location", "reason"})
    safe_text(value["location"], field + ".location")
    safe_text(value["reason"], field + ".reason")


def teacher_return(value, manifest, root, artifact_root):
    no_secret_tree(value, "teacherReturn")
    base = {"schemaVersion", "reviewLabel", "evidenceKind", "caseId", "caseSpecSHA", "outputSHA", "candidateSHA", "docxSHA", "reviewerKind", "reviewer", "reviewedAt", "verdict"}
    exact_object(value, "teacherReturn", base | {"dimensions", "hardFailures", "supported", "unsupported", "suggestion"}, base | {"dimensions", "hardFailures", "supported", "unsupported", "suggestion"})
    same(value["schemaVersion"], 1, "schemaVersion")
    case = next((c for c in manifest["cases"] if c["caseId"] == value["caseId"]), None)
    require(case is not None and case["technicalStatus"] == "technical_pass", "caseId", "only a selected returned candidate may be reviewed")
    review_identity(value, manifest, case)
    review_privacy(value, case, artifact_root)
    exact_object(value["dimensions"], "dimensions", set(DIMENSIONS), set(DIMENSIONS))
    for key, dimension in value["dimensions"].items():
        exact_object(dimension, key, {"score", "location", "reason"}, {"score", "location", "reason"})
        require(type(dimension["score"]) is int and 0 <= dimension["score"] <= 3, key + ".score", "exact score 0..3 required")
        evidence_note({k: dimension[k] for k in ("location", "reason")}, key)
    require(type(value["hardFailures"]) is list, "hardFailures", "explicit list required; [] means none observed")
    for failure in value["hardFailures"]:
        evidence_note(failure, "hardFailures")
    evidence_note(value["supported"], "supported")
    evidence_note(value["unsupported"], "unsupported")
    safe_text(value["suggestion"], "suggestion")
    require(not value["hardFailures"] or value["verdict"] != "usable", "verdict", "hard failure cannot be cancelled by average scores")
    return {"status": "human_return_integrity_pass", "humanVerdict": value["verdict"], "hardFailureCount": len(value["hardFailures"]), "createsTeacherApproval": False, "return": value}


def native_page_image(ref, root):
    """Exact-SHA page image that a real decoder can fully open, verify and decode to pixels."""
    path = ref_path(ref, root, "page.evidence")
    expected_format = NATIVE_IMAGE_EXTENSIONS.get(path.suffix.lower())
    require(expected_format is not None, "page.evidence", "actual native page image required")
    byte_size = path.stat().st_size
    require(0 < byte_size <= MAX_NATIVE_PAGE_IMAGE_BYTES, "page.evidence", "page image byte size outside declared bounds", "IMAGE_RESOURCE_OUT_OF_BOUND")
    try:
        with Image.open(path) as image:
            require(image.format in {"PNG", "JPEG", "WEBP"}, "page.evidence", "unsupported native page image format", "IMAGE_FORMAT_UNSUPPORTED")
            require(image.format == expected_format, "page.evidence", "image format does not match its file extension", "IMAGE_FORMAT_MISMATCH")
            width, height = image.size
            require(isinstance(width, int) and isinstance(height, int) and 0 < width <= MAX_NATIVE_PAGE_IMAGE_DIMENSION
                    and 0 < height <= MAX_NATIVE_PAGE_IMAGE_DIMENSION and width * height <= MAX_NATIVE_PAGE_IMAGE_PIXELS,
                    "page.evidence", "image dimensions outside declared bounds", "IMAGE_RESOURCE_OUT_OF_BOUND")
            image.verify()
        with Image.open(path) as image:
            frames = getattr(image, "n_frames", 1)
            require(isinstance(frames, int) and 1 <= frames <= MAX_NATIVE_PAGE_IMAGE_FRAMES, "page.evidence", "image frame count outside declared bounds", "IMAGE_RESOURCE_OUT_OF_BOUND")
            image.load()
            for frame in range(1, frames):
                image.seek(frame)
                image.load()
    except CheckError:
        raise
    except Image.DecompressionBombError as exc:
        raise CheckError("page.evidence", "image exceeds declared decoder resource bounds", "IMAGE_RESOURCE_OUT_OF_BOUND") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError) as exc:
        raise CheckError("page.evidence", "page evidence must be a fully decodable image; truncated, corrupt, zero-byte or non-image bytes are rejected", "IMAGE_DECODE_FAILED") from exc
    return path


def native_return(value, manifest, root, artifact_root):
    no_secret_tree(value, "nativeReturn")
    base = {"schemaVersion", "reviewLabel", "evidenceKind", "caseId", "caseSpecSHA", "outputSHA", "candidateSHA", "docxSHA", "reviewerKind", "reviewer", "reviewedAt", "verdict"}
    exact_object(value, "nativeReturn", base | {"application", "applicationVersion", "totalPages", "pages"}, base | {"application", "applicationVersion", "totalPages", "pages"})
    same(value["schemaVersion"], 1, "schemaVersion")
    case = next((c for c in manifest["cases"] if c["caseId"] == value["caseId"]), None)
    require(case is not None, "caseId", "selected case required")
    review_identity(value, manifest, case)
    review_privacy(value, case, artifact_root)
    require(value["application"] in {"Word", "WPS"}, "application", "actual Word or WPS required; PDF is historical reference")
    safe_text(value["applicationVersion"], "applicationVersion")
    total = positive_int(value["totalPages"], "totalPages")
    require(type(value["pages"]) is list, "pages", "actual per-page records required")
    same([p.get("pageNumber") for p in value["pages"]], list(range(1, total + 1)), "pages.actualCoverage")
    for page in value["pages"]:
        exact_object(page, "page", {"pageNumber", "totalPages", "evidence", "checks", "reason", "verdict"}, {"pageNumber", "totalPages", "evidence", "checks", "reason", "verdict"})
        positive_int(page["pageNumber"], "pageNumber")
        same(page["totalPages"], total, "page.totalPages")
        image_path = native_page_image(page["evidence"], root)
        exact_object(page["checks"], "checks", set(NATIVE_CHECKS), set(NATIVE_CHECKS))
        for key, item in page["checks"].items():
            exact_object(item, key, {"observation", "location", "reason"}, {"observation", "location", "reason"})
            require(item["observation"] in {"ok", "issue", "not_applicable"}, key, "explicit observation required")
            evidence_note({k: item[k] for k in ("location", "reason")}, key)
        safe_text(page["reason"], "page.reason")
        require(page["verdict"] in {"usable", "needs_revision", "unusable"}, "page.verdict", "human page verdict required")
    require(value["verdict"] != "usable" or all(p["verdict"] == "usable" for p in value["pages"]), "verdict", "overall verdict conflicts with page verdict")
    return {"status": "native_return_integrity_pass", "humanVerdict": value["verdict"], "actualPagesRecorded": total, "createsNativeApproval": False, "return": value}


def install_guard():
    counts = {"networkAttempts": 0, "mainImportAttempts": 0, "formalEnvReadAttempts": 0, "databaseOpenAttempts": 0}
    original = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == "app.main":
            counts["mainImportAttempts"] += 1
            raise RuntimeError("app.main import prohibited in result checker")
        return original(name, *args, **kwargs)
    builtins.__import__ = guarded_import
    def audit(event, args):
        if event.startswith("socket."):
            counts["networkAttempts"] += 1
            raise RuntimeError("network prohibited")
        if event == "sqlite3.connect":
            counts["databaseOpenAttempts"] += 1
            raise RuntimeError("database prohibited")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            if path.name == ".env" or path.name.startswith(".env."):
                counts["formalEnvReadAttempts"] += 1
                raise RuntimeError("credential file prohibited")
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                counts["databaseOpenAttempts"] += 1
                raise RuntimeError("database prohibited")
    sys.addaudithook(audit)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("technical", "teacher", "native"), default="technical")
    for name in ("manifest", "case-specs", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("manifest-sha", "case-specs-sha"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--return-file", type=Path)
    parser.add_argument("--return-sha")
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    timer = time.perf_counter()
    temp = Path(tempfile.mkdtemp(prefix="zqky-b7b-result-"))
    os.environ.update(ZQKY_DATA_DIR=str(temp / "data"), ZQKY_ENV="test", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    guard = install_guard()
    output_created = False
    code = 2
    try:
        create_output(args.output_dir)
        output_created = True
        manifest, specs, ledger = manifest_check(args.manifest, args.manifest_sha, args.case_specs, args.case_specs_sha)
        structure_rows = technical(manifest, specs, args.manifest.parent, ledger)
        if args.kind == "technical":
            require(args.return_file is None and args.return_sha is None, "return", "technical mode takes no human return")
            detail = structure_rows
        else:
            require(args.return_file is not None and args.return_sha is not None, "return", "explicit return file/hash required")
            value = checked_json(args.return_file, args.return_sha)
            detail = teacher_return(value, manifest, args.return_file.parent, args.manifest.parent) if args.kind == "teacher" else native_return(value, manifest, args.return_file.parent, args.manifest.parent)
        result = {"schemaVersion": 1, "status": "RESULT_INTEGRITY_PASS", "kind": args.kind, "manifestSHA": args.manifest_sha,
                  "caseSpecsSHA": args.case_specs_sha, "reviewLabel": manifest["reviewLabel"], "evidenceKind": manifest["evidenceKind"],
                  "selectedCaseIds": manifest["selectedCaseIds"], "unrunCaseIds": manifest["unrunCaseIds"], "detail": detail,
                  "teacher": "teacher_pending",
                  "native": "native_pending", "RAG_REL": "OPEN", "createsHumanAuthorization": False}
        code = 0
    except CheckError as exc:
        error = exc.as_dict()
        try:
            no_secret_tree(error, "error")
        except CheckError:
            error = {"code": exc.code, "field": "evidence", "reason": "credential material or invalid identity rejected"}
        result = {"schemaVersion": 1, "status": "FAIL_NO_RESULT_PASS_PUBLISHED", "error": error}
    except Exception as exc:
        # Do not serialize response text, credential values or source PII in errors.
        result = {"schemaVersion": 1, "status": "FAIL_NO_RESULT_PASS_PUBLISHED", "error": {"code": getattr(exc, "code", "INVALID_EVIDENCE"), "field": "production/evidence", "reason": "production validation or required evidence rejected"}}
    result["guard"] = guard
    result["productionModulesImported"] = sorted(name for name in sys.modules if name.startswith("app."))
    result["checkerSourceSHA"] = {"scripts/teaching-quality/trial_result_check.py": sha_file(Path(__file__)), "scripts/teaching-quality/common.py": sha_file(Path(__file__).with_name("common.py"))}
    result["isolation"] = {"dataRoot": os.environ["ZQKY_DATA_DIR"], "environment": "test", "credentialsFile": None, "retainedTEMP": str(temp)}
    result["command"] = {"argv": sys.argv, "PID": os.getpid(), "startedAt": started, "endedAt": datetime.now(timezone.utc).isoformat(), "elapsedMs": (time.perf_counter() - timer) * 1000, "exitCode": code}
    if output_created:
        write_json(args.output_dir / "RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
