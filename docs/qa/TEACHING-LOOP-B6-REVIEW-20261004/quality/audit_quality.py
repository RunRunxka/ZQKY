"""Stdlib review only; reads frozen evidence, writes only this review directory."""
from pathlib import Path
import ast
import copy
import csv
import hashlib
import json
import os
import subprocess
import sys
import zipfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
Q = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality"
RUN = Q / "runs/offline-third"
load = lambda p: json.loads(p.read_bytes())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
canonical = lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
pack = load(Q / "case-specs.json")
summary = load(RUN / "SUMMARY.json")
spec_ids = [c["caseId"] for c in pack["cases"]]
assert len(spec_ids) == len(set(spec_ids)) == 15
assert [c["caseId"] for c in summary["results"]] == spec_ids
assert summary["caseCount"] == summary["technicalStructurePassed"] == 15
assert summary["caseSpecsSHA"] == sha(Q / "case-specs.json")
facts = []
for spec, result in zip(pack["cases"], summary["results"]):
    c = RUN / "quality-cases" / spec["caseId"]
    table, expected, bound = [load(c / p) for p in ["student-state-table.json", "expected.json", "case-bound-v3.json"]]
    chosen = [table["participants"][i] for i in table["selectedIndexes"] if table["participants"][i]["classIndex"] == table["selectedClassIndex"]]
    assert len(chosen) == len({p["alias"] for p in chosen})
    recount = []
    for kp in table["selectedKnowledgeIndexes"]:
        indexes = [i for i, item in enumerate(table["items"]) if kp in item["knowledgeIndexes"]]
        states = []
        for p in chosen:
            cells = [p["cells"][i] for i in indexes]
            valid = any(s == "recorded" for s, _ in cells)
            needs = any(p["cells"][i][0] == "recorded" and p["cells"][i][1] < table["items"][i]["maxScoreUnits"] for i in indexes)
            incomplete = any(s != "recorded" for s, _ in cells)
            states.append((valid, needs, incomplete, not valid, bool(cells) and not incomplete and not needs))
        v, n, inc, none, full = [sum(x[i] for x in states) for i in range(5)]
        recount.append(dict(selectedCount=len(chosen), validCount=v, needsCount=n, incompleteCount=inc, noEvidenceCount=none, fullCreditCount=full, numerator=n, denominator=v, ratio=n/v if v else None))
    assert recount == expected["expectedTargetCounts"] == spec["expectedTargetCounts"]
    assert result["expectedSHA"] == sha(c / "expected.json")
    for name, h in result["hashes"].items():
        assert sha(c / name) == h
    for name, filename in {"originalCaseSHA": "case.json", "expectedSHA": "expected.json", "inputSHA": "input.json", "frozenInputSHA": "input-frozen.json", "wireSHA": "wire.json", "rawSHA": "raw-transport-response.json", "candidateSHA": "candidate.json", "selectedFieldsSHA": "selected-fields.json", "appliedSHA": "applied-result.json"}.items():
        assert sha(c / filename) == bound[name]
    frozen, wire, candidate, original, applied, raw = [load(c / p) for p in ["input-frozen.json", "wire.json", "candidate.json", "original-lesson.json", "applied-result.json", "raw-transport-response.json"]]
    messages = [m for m in wire["body"]["messages"] if m["role"] == "user"]
    assert len(messages) == 1 and json.loads(messages[0]["content"]) == frozen["modelPayload"]
    wire_text = json.dumps(wire, ensure_ascii=False)
    assert all(t not in wire_text for t in frozen["source"]["personalTokens"] if t)
    assert [x["counts"] for x in frozen["modelPayload"]["classSummary"]["knowledgePoints"]] == [{k: v for k, v in count.items() if k != "ratio"} for count in recount]
    fields = load(c / "selected-fields.json")
    data = applied["currentRevision"]["data"]
    for field in original:
        assert data[field] == (candidate["patch"][field] if field in fields else original[field])
    assert [x["minutes"] for x in candidate["budget"]["stages"]] == spec["stageMinutes"]
    assert sum(spec["stageMinutes"]) == spec["durationMinutes"]
    assert result["providerTransportCalls"] == 1
    assert result["humanScores"] is None and result["qualityVerdict"] == "teacher_review_pending"
    assert result["usage"]["inputTokens"] is None and result["usage"]["outputTokens"] is None
    for material in bound["refs"]["material"]:
        selected = material["selectedSlice"]
        assert hashlib.sha256(selected["text"].encode()).hexdigest() == material["selectedSliceSHA"]
    doc = Path(bound["export"]["file"])
    assert sha(doc) == bound["export"]["fileSHA"]
    with zipfile.ZipFile(doc) as z:
        assert z.testzip() is None
    facts.append(dict(caseId=spec["caseId"], counts=recount, materialCase=spec["materialCase"], claimSupported=spec["requestedClaimSupported"], minutes=spec["durationMinutes"], selectedFields=fields, providerCalls=1, anonymousWire=True, hashesPass=True, docxCRC=True))

feedback = list(csv.DictReader((Q / "feedback-offline-third.csv").open(encoding="utf-8-sig")))
dimensions = ["学情事实解释", "教材支持相关性", "目标KP覆盖", "活动课堂检测", "分钟可实施性", "教师字段保持", "内容准确可解释", "练习反馈"]
assert len(feedback) == 15
assert all(row[k] == "" for row in feedback for k in dimensions + ["reviewer", "reviewed_at", "真人结论", "hard_failure", "evidence_location"])
close = load(Q.parent / "B6-CLOSE-v1.json")
assert all(sha(Q.parent / p) == h for p, h in close["evidence"].items())

scopes = OUT / "scopes"
scopes.mkdir(exist_ok=True)
base = dict(modelProfileId="synthetic-review-only", modelId="synthetic-model", caseIds=["C10"], sampleCount=1, maxTotalTokens=1, maxCostCny=None)
variants = {
    "valid-shape": base,
    "string-caseIds": dict(base, caseIds="C10", sampleCount=3),
    "duplicate-caseIds": dict(base, caseIds=["C10", "C10"], sampleCount=2),
    "unknown-caseId": dict(base, caseIds=["C99"]),
    "boolean-sampleCount": dict(base, sampleCount=True),
    "non-string-profile": dict(base, modelProfileId={"wrong": "type"}),
    "nan-cost-no-token-limit": dict(base, maxTotalTokens=None, maxCostCny=float("nan")),
    "infinite-cost-no-token-limit": dict(base, maxTotalTokens=None, maxCostCny=float("inf")),
    "missing-input": load(Q / "live-scope.template.json"),
}
probes = []
for name, scope in variants.items():
    p = scopes / (name + ".json")
    p.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    proc = subprocess.run([sys.executable, str(Q / "review_tool.py"), "--scope", str(p)], capture_output=True, text=True, encoding="utf8", timeout=15, env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf8"})
    response = json.loads(proc.stdout)
    assert response["networkCalls"] == 0 and response["mainImported"] is False and response["formalEnvRead"] is False
    probes.append(dict(name=name, exitCode=proc.returncode, response=response, scopeSHA=sha(p)))
assert next(x for x in probes if x["name"] == "missing-input")["exitCode"] == 2

tree = ast.parse((Q / "finalize_review_v3.py").read_text("utf8"))
case_count_guards = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Assert) and any(word in ast.unparse(node) for word in ["caseCount", "len(results)", "len(summary", "len(manifest"]) ]
audit = dict(task="B6-QUALITY-INDEPENDENT-READONLY-REVIEW", sourceRunnerSHA=sha(Q / "review_tool.py"), finalizerSHA=sha(Q / "finalize_review_v3.py"), caseCount=15, handwrittenExpectedIndependentRecount="PASS15", wireAnonymousHashes="PASS15", selectedWholeFieldsAndTeacherFields="PASS15", providerFixtureCalls=15, realModelCalls=0, teacherReview="pending", feedbackRows=15, allScoresBlank=True, closeEvidenceHashes="PASS", docxCRC="PASS15", finalizerCaseCountAssertions=case_count_guards, preflightProbes=probes, cases=facts, limits="No original SQL/Blob readback, product API/service, native WPS, real model or teaching judgement run in this review. Existing proof audited only as frozen evidence.")
(OUT / "AUDIT.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
print(json.dumps(dict(caseCount=15, recount="PASS", evidenceHashes="PASS", teacherReview="pending", preflight=[dict(name=x["name"], exitCode=x["exitCode"], status=x["response"]["status"]) for x in probes], finalizerCaseCountAssertions=case_count_guards), ensure_ascii=False))
