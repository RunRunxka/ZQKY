"""Handwritten synthetic result/return oracles; no teacher/native approval."""
from __future__ import annotations

import ast
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
import zlib

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from common import canonical, sha_bytes, sha_file, strict_json, write_json
from trial_result_check import ARTIFACTS, DIMENSIONS, NATIVE_CHECKS, PRODUCTION_REQUIRED, EXECUTOR_REQUIRED, install_guard

SPECS_PATH = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json"
PRODUCTION = ("apps/api/app/services/lesson_generation/validation.py", "apps/api/app/services/lesson_generation/privacy.py", "apps/api/app/services/lesson_generation/service.py", "apps/api/app/contracts/lesson_plans.py")
OWN = (TOOLS / "trial_result_check.py", Path(__file__))


def _synthetic_png() -> bytes:
    # 完全可解码的 1x1 对照图：只作工具正常对照，不是真实页面，也不构成 native 或排版结论。
    from PIL import Image as PILImage
    buffer = io.BytesIO()
    PILImage.new("RGB", (1, 1), (0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _synthetic_png()


def digest(value):
    return sha_bytes(canonical(value))


def prompt():
    tree = ast.parse((ROOT / PRODUCTION[2]).read_text(encoding="utf-8"))
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SYSTEM_PROMPT" for t in node.targets))


def synthetic(spec):
    """New identities + owned text; no old answer()/exact stageMinutes reuse."""
    points = [{"knowledgePointId": f"r-kp-{index}", "knowledgeRevisionId": f"r-kpr-{index}", "name": f"知识点{index}", "role": "primary"} for index in spec["selectedKnowledgeIndexes"]]
    analysis = {"analysisRunId": "r-analysis", "scoreRevisionId": "r-score", "paperRevisionId": "r-paper", "inputHash": "1" * 64, "className": None, "classNameNote": "该成绩未记录班名", "knowledgePoints": points}
    selected = [spec["participants"][i] for i in spec["selectedParticipantIndexes"]]
    state_counts = {key: sum(cell[0] == key for part in selected for cell in part["cells"]) for key in ("recorded", "missing", "absent", "exempt")}
    report = {**analysis, "runId": "r-analysis", "reportReady": True, "ruleCode": "any_loss_v1", "classes": [{"classId": "r-class", "className": None, "knowledgePoint": point, **expected} for point, expected in zip(points, spec["expectedTargetCounts"])], "participants": [{"attemptNo": part["attemptNo"], "attendance": part["attendance"], "classId": "r-class" if part["classIndex"] == spec["selectedClassIndex"] else f"r-other-{part['classIndex']}"} for part in selected], "selectionSnapshot": {"stateCounts": state_counts, "uniqueStudentCount": len({p["alias"] for p in selected}), "participantCount": len(selected)}}
    evidence = [{"alias": "E1", "kind": "textbook", "referenceId": "r-evidence", "title": "自有合成教材", "sha256": "2" * 64, "locator": {"lineStart": 1, "lineEnd": 1}, "text": "有理数加法先判断符号，再核对绝对值。"}]
    original = {"title": "教师合成原稿", "totalLessons": "3", "currentLessonNo": "2", "lessonTypes": ["review"], "otherTypeText": "教师原课型", "reflection": "教师原反思", "coreCompetencies": "原素养", "keyPoints": "原重点", "teachingDesign": "原设计", "exercises": "原练习", "process": [{"id": "r-old-process", "stage": "原环节", "design": "原活动", "secondary": "原二次备课"}]}
    payload = {"lesson": {key: copy.deepcopy(original[key]) for key in ("coreCompetencies", "keyPoints", "teachingDesign", "exercises")}, "classSummary": {"knowledgePoints": [{"alias": f"K{i+1}", "name": point["name"], "counts": {k: v for k, v in expected.items() if k != "ratio"}} for i, (point, expected) in enumerate(zip(points, spec["expectedTargetCounts"]))]}, "durationMinutes": spec["durationMinutes"], "requirements": spec["requirements"], "evidence": [{k: evidence[0][k] for k in ("alias", "kind", "title", "text")}], "processAliases": ["P1"], "newProcessAliases": [f"new:N{i}" for i in range(1, 13)]}
    payload["lesson"]["process"] = [{**original["process"][0], "id": "P1"}]
    frozen = {"durationMinutes": spec["durationMinutes"], "requirements": spec["requirements"], "analysisRunId": "r-analysis", "classId": "r-class", "modelProfileId": "r-fixture-profile", "contextSnapshot": {"analysis": analysis}, "source": {"selectedKnowledgePoints": points, "knowledgeAliases": {f"K{i+1}": point for i, point in enumerate(points)}, "processAliases": {"P1": "r-old-process"}, "evidence": evidence, "personalTokens": ["SYNTHETIC_PRIVATE_STUDENT"], "report": report}, "modelPayload": payload, "scopeSnapshot": {"schemaVersion": 2, "selection": {"subjectId": "math", "gradeId": "senior-1", "editionId": "renjiao-a", "documentIds": ["r-textbook"]}, "documents": [{"documentId": "r-textbook", "documentRevisionId": "r-textbook-rev", "metadataRevisionId": "r-metadata"}], "embeddingGenerationId": "r-generation", "scopeHash": "3" * 64}, "evidenceRefs": [{"evidenceId": "r-evidence", "documentRevisionId": "r-textbook-rev", "normalizedTextSha256": "2" * 64, "charStart": 0, "charEnd": 20}]}
    frozen["source"].update(questions=[{"question_status": "confirmed", "question_revision_id": "r-question-revision"}] if spec["questionSource"] == "confirmed" else [], practices=[])
    minutes = [5, 15, 15, 5] if spec["durationMinutes"] == 40 else [6, 14, 20, 5] if spec["durationMinutes"] == 45 else [1, 1, 1, 2]
    raw = {"patch": {"coreCompetencies": "依据说明", "keyPoints": "符号判断", "teachingDesign": "先独立检测再讨论证据", "exercises": "教师审核后练习", "process": [{"id": f"new:N{i+1}", "stage": name, "design": "合成活动与出口检测", "secondary": "保留教师二次备课入口"} for i, name in enumerate(("导入", "探究", "练习", "总结"))]}, "budget": {"durationMinutes": spec["durationMinutes"], "stages": [{"processId": f"new:N{i+1}", "phase": name, "minutes": minutes[i], "knowledgeAliases": list(frozen["source"]["knowledgeAliases"]), "evidenceAliases": ["E1"], "activity": "独立计算并解释", "check": "根据实际答案核实困难"} for i, name in enumerate(("introduction", "exploration", "practice", "conclusion"))]}}
    return frozen, raw, original


class TrialResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outer_guard = install_guard()
        cls.runs = Path(os.environ["B7B_R_RUN_DIR"])
        cls.runs.mkdir(parents=True, exist_ok=False)
        cls.specs = strict_json(SPECS_PATH)
        materials = strict_json(ROOT / "docs/qa/TEACHING-LOOP-G4-B7A-20261005/b7a/prepared-full-v1/MATERIALS.json")
        cls.old = {ref["path"]: sha_file(ROOT / ref["path"]) for ref in materials["materialReferences"]}
        write_json(cls.runs / "ORIGINALS-before.json", cls.old)
        write_json(cls.runs / "ORACLE.json", strict_json(ROOT / "docs/qa/TEACHING-LOOP-G6-B7B-20261005/result/ORACLE-v1.json"))
        cls.calls = []

    @classmethod
    def tearDownClass(cls):
        after = {path: sha_file(ROOT / path) for path in cls.old}
        write_json(cls.runs / "ORIGINALS-after.json", {"hashes": after, "changed": [key for key in cls.old if cls.old[key] != after[key]]})
        write_json(cls.runs / "CLI-SUMMARY.json", {"calls": cls.calls, "actualCalls": len(cls.calls), "expectedResults": sum(item["matchesOracle"] for item in cls.calls), "guard": cls.outer_guard, "realModelCalls": 0, "teacher": "teacher_pending", "native": "native_pending", "syntheticOnly": True})
        if cls.old != after:
            raise AssertionError("original 273 material references drift")

    def sources(self):
        closure = sorted(PRODUCTION_REQUIRED | EXECUTOR_REQUIRED)
        return {str(path.relative_to(ROOT)).replace("\\", "/"): sha_file(path) for path in OWN + tuple(ROOT / name for name in closure)}

    def bundle(self, label, case_id="C01", mutate=None, apply=False, docx=False, live=False, live_fault=None):
        directory = self.runs / self._testMethodName / label
        directory.mkdir(parents=True, exist_ok=False)
        spec = next(spec for spec in self.specs["cases"] if spec["caseId"] == case_id)
        frozen, raw, original = synthetic(spec)
        scope = {"modelProfileId": "63b3ffdc87fb4c8f8b278c3b58923296" if live else "r-fixture-profile", "modelId": "deepseek-flash" if live else "r-fixture-model", "caseIds": [case_id], "sampleCount": 1, "maxAttempts": 1, "maxTotalTokens": 10000}
        frozen["modelProfileId"] = scope["modelProfileId"]
        scope_sha = digest(scope)
        values = {"frozenInput": frozen, "raw": raw, "beforeData": original}
        if mutate:
            mutate(values)
        frozen, raw = values["frozenInput"], values["raw"]
        candidate = copy.deepcopy(raw)
        for item in candidate["patch"]["process"]:
            item["id"] = "lp_" + sha_bytes((digest(frozen) + "\0" + item["id"]).encode())[:32]
        for stage in candidate["budget"]["stages"]:
            stage["processId"] = "lp_" + sha_bytes((digest(frozen) + "\0" + stage["processId"]).encode())[:32]
        candidate.update(evidence=frozen["source"]["evidence"], generationSource={"analysis": frozen["contextSnapshot"]["analysis"], "classId": frozen["classId"], "selectedKnowledgePoints": frozen["source"]["selectedKnowledgePoints"], "modelProfileId": frozen["modelProfileId"], "scopeSnapshot": frozen["scopeSnapshot"], "evidenceRefs": frozen["evidenceRefs"], "requirements": frozen["requirements"]})
        wire = {"model": scope["modelId"], "max_tokens": 16384 if live else 2000, "messages": [{"role": "system", "content": prompt()}, {"role": "user", "content": canonical(frozen["modelPayload"]).decode()}]}
        if live:
            wire["reasoning_effort"] = "max"
        artifacts = {name: None for name in ARTIFACTS}
        def save(name, value):
            path = directory / (name + (".txt" if name == "raw" else ".json"))
            if name == "raw":
                path.write_bytes(values.get("rawBytes", canonical(value)))
            else:
                write_json(path, value)
            artifacts[name] = {"file": path.name, "sha256": sha_file(path)}
        save("frozenInput", frozen)
        save("raw", raw)
        save("wire", wire)
        save("candidate", candidate)
        save("job", {"jobId": "r-job", "domain": "teaching", "kind": "lesson_generation", "attempt": 1, "state": "succeeded", "result": {}, "error": None})
        raw_usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "prompt_cache_hit_tokens": 40, "prompt_cache_miss_tokens": 60, "completion_tokens_details": {"reasoning_tokens": 10}} if live else {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        if live and live_fault == "usage-unknown":
            raw_usage["unknown_tokens"] = 1
        if live and live_fault == "reasoning":
            raw_usage["completion_tokens_details"] = {"reasoning_tokens": 51}
        save("usage", {"schemaVersion": 1, "caseId": case_id, "scopeSHA": scope_sha, "jobId": "r-job", "jobAttempt": 1, "caseAttempt": 1, "protocol": "openai-chat", "evidenceKind": "live" if live else "fixture", "rawUsage": raw_usage, "normalizedUsage": {"inputTokens": 100 if live else 10, "outputTokens": 20, "totalTokens": 120 if live else 30}, "validation": {"status": "verified", "reason": None}, "rawSHA": artifacts["raw"]["sha256"], "wireSHA": artifacts["wire"]["sha256"]})
        if live:
            from trial_result_check import LIVE_PROOF_KIND, LIVE_TOKENIZER_SHA256
            proof_doc = {"schemaVersion": 1, "proofKind": LIVE_PROOF_KIND, "evidenceKind": "live",
                         "modelProfileId": scope["modelProfileId"], "modelId": scope["modelId"],
                         "wireSHA": digest(wire), "inputUpper": 300, "outputUpper": 16384,
                         "reasoningUpper": 0, "otherUpper": 0, "tokenizerSHA256": LIVE_TOKENIZER_SHA256,
                         "tokenizerSourceURL": "https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip",
                         "officialFacts": {"official": True}, "probeFacts": {"probe": True}, "proofSHA": "6" * 64}
            if live_fault == "proof-kind":
                proof_doc["proofKind"] = "other-proof"
            if live_fault == "tokenizer":
                proof_doc["tokenizerSHA256"] = "0" * 64
            save("billingProof", proof_doc)
        save("attempt", {"schemaVersion": 1, "ticketId": "r-ticket", "caseId": case_id, "scopeSHA": scope_sha, "jobId": "r-job", "jobAttempt": 1, "caseAttempt": 1, "modelFingerprint": "sha256:" + "5" * 64, "inputHash": digest(frozen), "wireSHA": artifacts["wire"]["sha256"], "rawSHA": artifacts["raw"]["sha256"], "usageSHA": artifacts["usage"]["sha256"], "reservedTokens": 10000, "settledTokens": 120 if live else 30, "providerSendCount": 1, "state": "settled", "boundProofSHA": "6" * 64, "runLabel": label})
        if apply or docx:
            fields = spec["selectedFields"]
            after = copy.deepcopy(original)
            for field in fields:
                after[field] = copy.deepcopy(candidate["patch"][field])
            after.update(values.get("afterOverrides", {}))
            save("selectedFields", fields)
            save("applied", {"beforeData": original, "afterData": after, "selectionActor": "qa", "revisionId": "r-new-fixed-revision"})
        if docx:
            path = directory / "new-synthetic.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
                archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>合成新修订接口样例</w:t></w:r></w:p></w:body></w:document>')
            artifacts["docx"] = {"file": path.name, "sha256": sha_file(path)}
        case = {"caseId": case_id, "caseSpecSHA": digest(spec), "inputHash": digest(frozen), "modelFingerprint": "sha256:" + "5" * 64, "jobId": "r-job", "jobAttempt": 1, "caseAttempt": 1, "providerSendCount": 1, "status": "succeeded", "technicalStatus": "technical_pass", "teacherStatus": "teacher_pending", "nativeStatus": "native_pending", "artifacts": artifacts}
        ledger = {"schemaVersion": 1, "authorizationId": "synthetic-author-selfcheck", "scopeSHA": scope_sha, "scope": scope, "evidenceKind": "live" if live else "fixture", "stopReason": None, "attempts": {case_id: 1}, "tickets": [strict_json(directory / "attempt.json")]}
        write_json(directory / "ledger-snapshot.json", ledger)
        manifest = {"schemaVersion": 1, "mode": "live" if live else "dry-run", "evidenceKind": "live" if live else "fixture", "reviewLabel": label, "scopeSHA": scope_sha, "authorizationSHA": "a" * 64 if live else None, "selectedCaseIds": [case_id], "unrunCaseIds": [s["caseId"] for s in self.specs["cases"] if s["caseId"] != case_id], "productionSourceSHA": {name: sha_file(ROOT / name) for name in PRODUCTION_REQUIRED}, "executorSourceSHA": {name: sha_file(ROOT / name) for name in EXECUTOR_REQUIRED}, "cases": [case], "stopReason": None, "realModelCalls": 1 if live else 0, "fixtureWireSends": 0 if live else 1, "ledgerRef": {"file": "ledger-snapshot.json", "sha256": sha_file(directory / "ledger-snapshot.json")}, "technicalGate": "synthetic_author_selfcheck"}
        return directory, manifest

    def run_cli(self, directory, manifest, expected=0, kind="technical", returned=None, repeat=False):
        path = directory / "trial-result.json"
        if not repeat:
            write_json(path, manifest)
        output = directory / "checked"
        old_result_sha = sha_file(output / "RESULT.json") if repeat else None
        argv = [sys.executable, "-B", str(TOOLS / "trial_result_check.py"), "--kind", kind, "--manifest", str(path), "--manifest-sha", sha_file(path), "--case-specs", str(SPECS_PATH), "--case-specs-sha", sha_file(SPECS_PATH), "--output-dir", str(output)]
        if returned is not None:
            return_path = directory / "returned.json"
            write_json(return_path, returned)
            argv += ["--return-file", str(return_path), "--return-sha", sha_file(return_path)]
        before = self.sources()
        started = datetime.now(timezone.utc).isoformat()
        timer = time.perf_counter()
        temp = tempfile.mkdtemp(prefix="zqky-b7b-r-author-")
        child = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "ZQKY_DATA_DIR": str(Path(temp) / "data"), "ZQKY_ENV": "test", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        stdout, stderr = child.communicate(timeout=60)
        ended = datetime.now(timezone.utc).isoformat()
        log = directory / ("repeat-CLI.log" if repeat else "CLI.log")
        log.write_text(stdout + "\nSTDERR\n" + stderr, encoding="utf-8")
        result = json.loads(stdout) if repeat else strict_json(output / "RESULT.json")
        after = self.sources()
        receipt = {"argv": argv, "PID": child.pid, "startedAt": started, "endedAt": ended, "elapsedMs": (time.perf_counter() - timer) * 1000, "exitCode": child.returncode, "expectedExitCode": expected, "matchesOracle": child.returncode == expected, "sourceQABefore": before, "sourceQAAfter": after, "guard": result["guard"], "productionModulesImported": result["productionModulesImported"], "logSHA": sha_file(log), "processClosed": True, "logHandlesClosed": True, "retainedTEMP": temp}
        command_path = directory / ("repeat-COMMAND.json" if repeat else "COMMAND.json")
        write_json(command_path, receipt)
        self.calls.append({"file": str(command_path.relative_to(self.runs)), "sha256": sha_file(command_path), "matchesOracle": receipt["matchesOracle"]})
        if repeat:
            self.assertEqual(old_result_sha, sha_file(output / "RESULT.json"))
        self.assertEqual(before, after)
        self.assertEqual(result["guard"], {"networkAttempts": 0, "mainImportAttempts": 0, "formalEnvReadAttempts": 0, "databaseOpenAttempts": 0})
        self.assertEqual(child.returncode, expected, result)
        self.assertEqual(result["status"], "RESULT_INTEGRITY_PASS" if expected == 0 else "FAIL_NO_RESULT_PASS_PUBLISHED")
        return result

    def test_existing_output_refusal(self):
        directory, manifest = self.bundle("existing-new-output")
        self.run_cli(directory, manifest)
        self.run_cli(directory, manifest, 2, repeat=True)

    def review(self, manifest):
        case = manifest["cases"][0]
        return {"schemaVersion": 1, "reviewLabel": manifest["reviewLabel"], "evidenceKind": "fixture", "caseId": case["caseId"], "caseSpecSHA": case["caseSpecSHA"], "outputSHA": case["artifacts"]["raw"]["sha256"], "candidateSHA": case["artifacts"]["candidate"]["sha256"], "docxSHA": case["artifacts"]["docx"]["sha256"], "reviewerKind": "human", "reviewer": "SYNTHETIC_RETURN_ONLY", "reviewedAt": "2026-10-05T12:00:00+08:00", "verdict": "needs_revision"}

    def test_variable_minutes_and_pending(self):
        for case_id in ("C01", "C11", "C14"):
            directory, manifest = self.bundle("variable-minutes-" + case_id, case_id)
            result = self.run_cli(directory, manifest)
            self.assertEqual(result["detail"][0]["applicationProtection"], "not_run_missing_apply_evidence")
            self.assertEqual(result["teacher"], "teacher_pending")
            self.assertEqual(result["native"], "native_pending")
            self.assertEqual(len(result["unrunCaseIds"]), 14)

    def test_partial_apply_teacher_and_unselected_protection(self):
        directory, manifest = self.bundle("good-partial", "C14", apply=True)
        self.assertEqual(self.run_cli(directory, manifest)["detail"][0]["applicationProtection"], "pass_qa_selection")
        for field in ("title", "totalLessons", "currentLessonNo", "lessonTypes", "otherTypeText", "reflection", "coreCompetencies", "keyPoints", "exercises"):
            value = ["new"] if field == "lessonTypes" else "changed"
            directory, manifest = self.bundle("bad-" + field, "C14", mutate=lambda b, f=field, v=value: b.update(afterOverrides={f: v}), apply=True)
            self.run_cli(directory, manifest, 2)

    def test_production_shape_refusals(self):
        mutations = {"sum": lambda b: b["raw"]["budget"]["stages"][0].update(minutes=6), "bool": lambda b: b["raw"]["budget"]["stages"][0].update(minutes=True), "negative": lambda b: b["raw"]["budget"]["stages"][0].update(minutes=-1), "phase": lambda b: b["raw"]["budget"]["stages"][0].update(phase="practice"), "kp": lambda b: b["raw"]["budget"]["stages"][0].update(knowledgeAliases=["K999"]), "evidence": lambda b: b["raw"]["budget"]["stages"][0].update(evidenceAliases=["E999"]), "teacher-field": lambda b: b["raw"]["patch"].update(title="unauthorized"), "pii": lambda b: b["raw"]["patch"].update(teachingDesign="SYNTHETIC_PRIVATE_STUDENT"), "zero-denominator": lambda b: b["frozenInput"]["source"]["report"]["classes"][0].update(ratio=0.0), "four-states": lambda b: b["frozenInput"]["source"]["report"]["selectionSnapshot"]["stateCounts"].update(recorded=1)}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label, "C15" if label in {"zero-denominator", "four-states"} else "C01", mutate=mutation)
            self.run_cli(directory, manifest, 2)

    def test_manifest_identity_refusals(self):
        mutations = {"mode": lambda m: m.update(evidenceKind="live"), "extra": lambda m: m.update(unknown=True), "spec": lambda m: m["cases"][0].update(caseSpecSHA="a" * 64), "input": lambda m: m["cases"][0].update(inputHash="b" * 64), "job": lambda m: m["cases"][0].update(jobId="other-job"), "attempt": lambda m: m["cases"][0].update(caseAttempt=2), "hash": lambda m: m["cases"][0]["artifacts"]["raw"].update(sha256="c" * 64), "unselected": lambda m: m.update(unrunCaseIds=[]), "sends": lambda m: m.update(realModelCalls=1), "empty-source": lambda m: m.update(productionSourceSHA={}), "missing-runtime": lambda m: m["productionSourceSHA"].pop("apps/api/app/services/model_runtime.py"), "missing-executor": lambda m: m["executorSourceSHA"].pop("scripts/teaching-quality/controlled_ledger.py"), "secret-path": lambda m: m["productionSourceSHA"].update({"apps/api/.env": "a" * 64}), "scope-mismatch": lambda m: m.update(scopeSHA="b" * 64), "no-ledger": lambda m: m.update(ledgerRef=None), "status": lambda m: m["cases"][0].update(status="failed"), "stop-reason": lambda m: m.update(stopReason="unbound_stop")}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label)
            mutation(manifest)
            self.run_cli(directory, manifest, 2)

    def test_independent_ledger_and_live_refusals(self):
        mutations = {"attempt-count": lambda l: l["attempts"].update(C01=2), "bool-attempt": lambda l: l["attempts"].update(C01=True), "unknown-case": lambda l: l["attempts"].update(C99=1), "send-label": lambda l: l["tickets"][0].update(runLabel="borrowed-old-label"), "hidden-send": lambda l: l["tickets"][0].update(providerSendCount=2), "settled-usage": lambda l: l["tickets"][0].update(settledTokens=31), "ticket-extra": lambda l: l["tickets"][0].update(extra="untrusted"), "ticket-ordinal": lambda l: l["tickets"][0].update(caseAttempt=2)}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label)
            ledger_path = directory / "ledger-snapshot.json"
            ledger = strict_json(ledger_path)
            mutation(ledger)
            # Rebind the individual attempt too: even internally equal copies
            # cannot override the independent counts/state/usage oracle.
            if label != "send-label":
                (directory / "attempt.json").write_bytes(canonical(ledger["tickets"][0]) + b"\n")
                manifest["cases"][0]["artifacts"]["attempt"]["sha256"] = sha_file(directory / "attempt.json")
            ledger_path.write_bytes(canonical(ledger) + b"\n")
            manifest["ledgerRef"]["sha256"] = sha_file(ledger_path)
            self.run_cli(directory, manifest, 2)
        directory, manifest = self.bundle("relabeled-live")
        manifest.update(mode="live", evidenceKind="live", authorizationSHA="a" * 64, realModelCalls=1, fixtureWireSends=0)
        result = self.run_cli(directory, manifest, 2)
        # A fixture snapshot relabelled live is refused at the fixture-identity gate.
        self.assertEqual(result["error"]["code"], "FIXTURE_NOT_LIVE")
        # A live-shaped label without the registered billing proof is refused too.
        directory, manifest = self.bundle("relabeled-live-unproven")
        ledger_path = directory / "ledger-snapshot.json"
        ledger = strict_json(ledger_path)
        ledger["scope"]["modelProfileId"] = "unregistered-live-profile"
        ledger["scope"]["modelId"] = "unregistered-live-model"
        ledger["evidenceKind"] = "live"
        scope_sha = digest(ledger["scope"])
        ledger["scopeSHA"] = scope_sha
        for ticket in ledger["tickets"]:
            ticket["scopeSHA"] = scope_sha
        (directory / "attempt.json").write_bytes(canonical(ledger["tickets"][0]) + b"\n")
        ledger_path.write_bytes(canonical(ledger) + b"\n")
        manifest.update(mode="live", evidenceKind="live", authorizationSHA="a" * 64, realModelCalls=1, fixtureWireSends=0,
                        scopeSHA=scope_sha)
        manifest["cases"][0]["artifacts"]["attempt"]["sha256"] = sha_file(directory / "attempt.json")
        manifest["ledgerRef"]["sha256"] = sha_file(ledger_path)
        result = self.run_cli(directory, manifest, 2)
        self.assertEqual(result["error"]["code"], "LIVE_PROOF_UNREGISTERED")

    def test_live_registered_proof_accepts_official_usage(self):
        directory, manifest = self.bundle("live-registered", live=True)
        result = self.run_cli(directory, manifest)
        self.assertEqual(result["status"], "RESULT_INTEGRITY_PASS")
        directory, manifest = self.bundle("live-bad-proof-kind", live=True, live_fault="proof-kind")
        result = self.run_cli(directory, manifest, 2)
        self.assertEqual(result["error"]["code"], "LIVE_PROOF_UNREGISTERED")
        directory, manifest = self.bundle("live-bad-tokenizer", live=True, live_fault="tokenizer")
        result = self.run_cli(directory, manifest, 2)
        self.assertEqual(result["error"]["code"], "LIVE_PROOF_UNREGISTERED")
        directory, manifest = self.bundle("live-bad-reasoning", live=True, live_fault="reasoning")
        result = self.run_cli(directory, manifest, 2)
        self.assertEqual(result["error"]["field"], "rawUsage.reasoning")
        directory, manifest = self.bundle("live-unknown-dimension", live=True, live_fault="usage-unknown")
        result = self.run_cli(directory, manifest, 2)
        self.assertEqual(result["error"]["field"], "rawUsage")

    def test_invalid_raw_and_unsent_unrun(self):
        for label, raw_bytes in (("invalid-json", b"not JSON"), ("duplicate-json", b'{"patch":{},"patch":{},"budget":{}}'), ("secret", b'{"apiKey":"prohibited"}')):
            directory, manifest = self.bundle(label, mutate=lambda b, content=raw_bytes: b.update(rawBytes=content))
            self.run_cli(directory, manifest, 2)
        directory, manifest = self.bundle("selected-but-unrun")
        case = manifest["cases"][0]
        case.update(inputHash=None, modelFingerprint=None, jobId=None, jobAttempt=0, caseAttempt=0, providerSendCount=0, status="not_run", technicalStatus="unrun", artifacts={name: None for name in ARTIFACTS})
        manifest.update(fixtureWireSends=0, stopReason="NO_AUTHORIZED_LIVE_SCOPE")
        ledger_path = directory / "ledger-snapshot.json"
        ledger = strict_json(ledger_path)
        ledger.update(tickets=[], attempts={}, stopReason=manifest["stopReason"])
        ledger_path.write_bytes(canonical(ledger))
        manifest["ledgerRef"]["sha256"] = sha_file(ledger_path)
        result = self.run_cli(directory, manifest)
        self.assertEqual(result["detail"][0]["technicalStructure"], "unrun")

    def test_failed_evidence_and_suppressed_raw(self):
        def failure(directory, manifest, suppress=False):
            case = manifest["cases"][0]
            case.update(status="failed", technicalStatus="technical_fail")
            case["artifacts"]["candidate"] = None
            job_path = directory / "job.json"
            job = strict_json(job_path)
            job.update(state="failed", result=None, error={"code": "SYNTHETIC_FAILURE"})
            job_path.write_bytes(canonical(job) + b"\n")
            case["artifacts"]["job"]["sha256"] = sha_file(job_path)
            if suppress:
                manifest["stopReason"] = "SYNTHETIC_RAW_SUPPRESSED"
                case["artifacts"]["raw"] = case["artifacts"]["usage"] = None
                attempt_path = directory / "attempt.json"
                attempt = strict_json(attempt_path)
                attempt.update(state="unknown", settledTokens=None, usageSHA=None)
                attempt_path.write_bytes(canonical(attempt) + b"\n")
                case["artifacts"]["attempt"]["sha256"] = sha_file(attempt_path)
                ledger_path = directory / "ledger-snapshot.json"
                ledger = strict_json(ledger_path)
                ledger.update(stopReason=manifest["stopReason"], tickets=[attempt])
                ledger_path.write_bytes(canonical(ledger) + b"\n")
                manifest["ledgerRef"]["sha256"] = sha_file(ledger_path)
        directory, manifest = self.bundle("failed-bound")
        failure(directory, manifest)
        result = self.run_cli(directory, manifest)
        self.assertEqual(result["detail"][0]["technicalStructure"], "technical_fail")
        directory, manifest = self.bundle("suppressed-raw")
        failure(directory, manifest, suppress=True)
        result = self.run_cli(directory, manifest)
        self.assertEqual(result["detail"][0]["rawEvidence"], "suppressed_hash_only")
        directory, manifest = self.bundle("failed-with-apply", apply=True)
        failure(directory, manifest)
        self.run_cli(directory, manifest, 2)

    def test_raw_usage_refusals(self):
        mutations = {"raw-input": lambda u: u["rawUsage"].update(prompt_tokens=11), "raw-bool": lambda u: u["rawUsage"].update(prompt_tokens=True), "raw-dimension": lambda u: u["rawUsage"].update(cache_tokens=1)}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label)
            usage_path, attempt_path, ledger_path = (directory / name for name in ("usage.json", "attempt.json", "ledger-snapshot.json"))
            usage = strict_json(usage_path)
            mutation(usage)
            usage_path.write_bytes(canonical(usage) + b"\n")
            manifest["cases"][0]["artifacts"]["usage"]["sha256"] = sha_file(usage_path)
            attempt = strict_json(attempt_path)
            attempt["usageSHA"] = sha_file(usage_path)
            attempt_path.write_bytes(canonical(attempt) + b"\n")
            manifest["cases"][0]["artifacts"]["attempt"]["sha256"] = sha_file(attempt_path)
            ledger = strict_json(ledger_path)
            ledger["tickets"] = [attempt]
            ledger_path.write_bytes(canonical(ledger) + b"\n")
            manifest["ledgerRef"]["sha256"] = sha_file(ledger_path)
            self.run_cli(directory, manifest, 2)

    def test_teacher_integrity_and_refusals(self):
        def teacher(manifest):
            value = self.review(manifest)
            value.update(dimensions={key: {"score": 3, "location": "输出过程第1环节", "reason": "合成完整性反证；并未真人评分"} for key in DIMENSIONS}, hardFailures=[{"location": "输出过程第1环节", "reason": "合成硬失败样例"}], supported={"location": "教材第1行", "reason": "合成支持记录"}, unsupported={"location": "输出第1段", "reason": "合成不足记录"}, suggestion="教师返回时填写修改建议；此处仅合成接口样例")
            return value
        directory, manifest = self.bundle("complete", docx=True)
        result = self.run_cli(directory, manifest, kind="teacher", returned=teacher(manifest))
        self.assertEqual(result["detail"]["humanVerdict"], "needs_revision")
        self.assertFalse(result["detail"]["createsTeacherApproval"])
        self.assertEqual(result["teacher"], "teacher_pending")
        mutations = {"reviewer": lambda r: r.update(reviewer=""), "time": lambda r: r.update(reviewedAt="2026-10-05"), "score": lambda r: r["dimensions"]["facts"].update(score=True), "reason": lambda r: r["dimensions"]["facts"].update(reason=""), "location": lambda r: r["dimensions"]["facts"].update(location=""), "candidate": lambda r: r.update(candidateSHA="a" * 64), "docx": lambda r: r.update(docxSHA="b" * 64), "hard-failure": lambda r: r.update(verdict="usable"), "suggestion": lambda r: r.update(suggestion=""), "fixture-as-live": lambda r: r.update(evidenceKind="live"), "automated": lambda r: r.update(reviewerKind="model"), "extra": lambda r: r.update(extra=1)}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label, docx=True)
            value = teacher(manifest)
            mutation(value)
            self.run_cli(directory, manifest, 2, kind="teacher", returned=value)

    def test_native_integrity_and_refusals(self):
        def page_image(fmt="PNG", size=(2, 2)):
            from PIL import Image as PILImage
            buffer = io.BytesIO()
            PILImage.new("RGB", size, (12, 34, 56)).save(buffer, format=fmt)
            return buffer.getvalue()

        def native(directory, manifest, image=None):
            name, content = image or ("synthetic-page.png", PNG)
            image_path = directory / name
            image_path.write_bytes(content)
            value = self.review(manifest)
            value.update(application="WPS", applicationVersion="SYNTHETIC_VERSION_ONLY", totalPages=1, pages=[{"pageNumber": 1, "totalPages": 1, "evidence": {"file": name, "sha256": sha_file(image_path)}, "checks": {key: {"observation": "not_applicable", "location": "合成第1页", "reason": "仅返回完整性样例，未实际开Word/WPS"} for key in NATIVE_CHECKS}, "reason": "合成逐页记录", "verdict": "needs_revision"}])
            return value
        directory, manifest = self.bundle("complete", docx=True)
        result = self.run_cli(directory, manifest, kind="native", returned=native(directory, manifest))
        self.assertFalse(result["detail"]["createsNativeApproval"])
        self.assertEqual(result["native"], "native_pending")
        self.assertEqual(result["detail"]["humanVerdict"], "needs_revision")
        mutations = {"pdf": lambda r: r.update(application="PDF"), "version": lambda r: r.update(applicationVersion=""), "missing-page": lambda r: r.update(totalPages=2), "duplicate-page": lambda r: r["pages"].append(copy.deepcopy(r["pages"][0])), "total": lambda r: r["pages"][0].update(totalPages=2), "reason": lambda r: r["pages"][0]["checks"]["secondary"].update(reason=""), "clipping": lambda r: r["pages"][0]["checks"].pop("clipping"), "wrong-image": lambda r: r["pages"][0]["evidence"].update(sha256="a" * 64), "verdict": lambda r: r.update(verdict="usable")}
        for label, mutation in mutations.items():
            directory, manifest = self.bundle(label, docx=True)
            value = native(directory, manifest)
            mutation(value)
            self.run_cli(directory, manifest, 2, kind="native", returned=value)
        # 合法可解码 PNG/JPEG/WebP 仍通过接口完整性；合成小图只作工具正常对照，native 保持 pending。
        for fmt, name in (("PNG", "synthetic-page.png"), ("JPEG", "synthetic-page.jpg"), ("JPEG", "synthetic-page.jpeg"), ("WEBP", "synthetic-page.webp")):
            directory, manifest = self.bundle("decodable-" + fmt.lower() + "-" + name.rsplit(".", 1)[-1], docx=True)
            result = self.run_cli(directory, manifest, kind="native", returned=native(directory, manifest, (name, page_image(fmt))))
            self.assertEqual(result["detail"]["status"], "native_return_integrity_pass")
            self.assertEqual(result["native"], "native_pending")
        # 正确 SHA 不能覆盖截断/坏结构/伪装/超资源：全部硬拒并定位到 page.evidence。
        valid_png = page_image("PNG")
        idat = valid_png.index(b"IDAT") + 4
        bad_crc = valid_png[:idat] + bytes([valid_png[idat] ^ 0xFF]) + valid_png[idat + 1:]
        oversize = bytearray(valid_png)
        oversize[16:20] = (100_000).to_bytes(4, "big")
        oversize[20:24] = (100_000).to_bytes(4, "big")
        oversize[29:33] = (zlib.crc32(bytes(oversize[12:29])) & 0xFFFFFFFF).to_bytes(4, "big")
        faults = {
            "zero-byte": ("synthetic-page.png", b""),
            "png-header-only": ("synthetic-page.png", valid_png[:8]),
            "jpeg-header-only": ("synthetic-page.png", b"\xff\xd8\xff"),
            "webp-header-only": ("synthetic-page.png", b"RIFF" + (4).to_bytes(4, "little") + b"WEBP"),
            "truncated-png": ("synthetic-page.png", valid_png[: len(valid_png) // 2]),
            "bad-crc": ("synthetic-page.png", bytes(bad_crc)),
            "format-extension-mismatch": ("synthetic-page.jpg", valid_png),
            "pdf-disguised": ("synthetic-page.png", b"%PDF-1.7\n1 0 obj\n"),
        }
        for label, (name, content) in faults.items():
            directory, manifest = self.bundle("fault-" + label, docx=True)
            result = self.run_cli(directory, manifest, 2, kind="native", returned=native(directory, manifest, (name, content)))
            self.assertEqual(result["error"]["field"], "page.evidence")
        directory, manifest = self.bundle("fault-oversize", docx=True)
        result = self.run_cli(directory, manifest, 2, kind="native", returned=native(directory, manifest, ("synthetic-page.png", bytes(oversize))))
        self.assertEqual(result["error"]["field"], "page.evidence")
        self.assertEqual(result["error"]["code"], "IMAGE_RESOURCE_OUT_OF_BOUND")


if __name__ == "__main__":
    unittest.main(verbosity=2)
