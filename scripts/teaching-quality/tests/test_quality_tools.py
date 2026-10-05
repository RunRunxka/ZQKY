"""Behavioral CLI counterexamples against frozen B6 evidence; no app imports.

Every subprocess output is kept under a new AUTHOR_RUN_DIR. Mutation cases use
new temporary copies, never change the original sample or handwritten oracle.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
OLD = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004"
QUALITY = OLD / "b6-quality"
MANIFEST_SHA = "353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55"
ARTIFACT_SHA = "f79ac91201f3d5ecedab2cf01ea92a2ebc0b6d794e7fa18ebf9e3796e0e54db9"
sys.path.insert(0, str(TOOLS))
from common import CheckError, sha_file, strict_json
from aggregate_review import docx_check


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def new_hashes():
    return {str(p.relative_to(ROOT)): sha_file(p) for p in sorted(TOOLS.rglob("*.py"))}


class QualityTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = Path(os.environ["AUTHOR_RUN_DIR"])
        cls.runs.mkdir(parents=True, exist_ok=False)
        cls.spec = strict_json(QUALITY / "case-specs.json")
        cls.ids = [x["caseId"] for x in cls.spec["cases"]]
        cls.summary = strict_json(QUALITY / "runs/offline-third/SUMMARY.json")
        cls.docx = strict_json(QUALITY / "exports/offline-third/DOCX-MANIFEST.json")
        cls.seed = strict_json(QUALITY / "runs/offline-third/seed.json")
        cls.originals_before = {str(p): sha_file(p) for p in sorted(QUALITY.rglob("*")) if p.is_file()}
        cls.database_before = {path: sha_file(Path(path)) if Path(path).is_file() else None for path in cls.seed["catalogPaths"].values()}
        write(cls.runs / "ORIGINALS-before.json", {"artifacts": cls.originals_before, "databases": cls.database_before})

    @classmethod
    def tearDownClass(cls):
        after = {str(p): sha_file(p) for p in sorted(QUALITY.rglob("*")) if p.is_file()}
        databases = {path: sha_file(Path(path)) if Path(path).is_file() else None for path in cls.seed["catalogPaths"].values()}
        write(cls.runs / "ORIGINALS-after.json", {"artifacts": after, "databases": databases, "artifactDrift": sorted(k for k in cls.originals_before if cls.originals_before[k] != after.get(k)), "databaseDrift": sorted(k for k in cls.database_before if cls.database_before[k] != databases.get(k))})
        if after != cls.originals_before or databases != cls.database_before:
            raise AssertionError("old material or source database drift")

    def run_cli(self, tool, args, label="run", output_override=None):
        case_dir = self.runs / self._testMethodName
        case_dir.mkdir(exist_ok=True)
        output = output_override or case_dir / label
        cmd = [sys.executable, "-B", str(TOOLS / tool), *map(str, args), "--output-dir", str(output)]
        before = new_hashes()
        started = time.time()
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        stdout, stderr = proc.communicate(timeout=120)
        elapsed = (time.time() - started) * 1000
        with (case_dir / (label + ".log")).open("x", encoding="utf-8") as stream:
            stream.write(stdout + "\nSTDERR\n" + stderr)
        after = new_hashes()
        write(case_dir / (label + "-command.json"), {"command": cmd, "pid": proc.pid, "startedEpoch": started, "durationMs": elapsed, "exitCode": proc.returncode, "sourceQABefore": before, "sourceQAAfter": after, "changedSourceQA": sorted(k for k in before if before[k] != after.get(k)), "logHandlesClosed": True, "networkCalls": 0, "mainImported": False, "formalEnvRead": False})
        self.assertEqual(before, after)
        result = strict_json(output / "RESULT.json") if (output / "RESULT.json").exists() else json.loads(stdout)
        return proc.returncode, result

    def scope_args(self, scope, name="scope.json"):
        directory = self.runs / self._testMethodName
        directory.mkdir(exist_ok=True)
        path = directory / name
        if isinstance(scope, str):
            with path.open("x", encoding="utf-8") as stream:
                stream.write(scope)
        else:
            write(path, scope)
        return ["--case-manifest", QUALITY / "case-specs.json", "--case-manifest-sha", MANIFEST_SHA, "--scope", path]

    def valid_scope(self):
        return {"modelProfileId": "human-explicit-profile", "modelId": "human-explicit-model", "caseIds": ["C10", "C11", "C12", "C13"], "sampleCount": 4, "maxAttempts": 1, "maxTotalTokens": 12000}

    def assert_bad_scope(self, **changes):
        scope = self.valid_scope()
        scope.update(changes)
        code, result = self.run_cli("scope_preflight.py", self.scope_args(scope))
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "FAIL_SCOPE_PREFLIGHT")
        self.assertFalse(result["createsHumanAuthorization"])

    def test_scope_string_caseids(self): self.assert_bad_scope(caseIds="C10", sampleCount=3)
    def test_scope_duplicate_ids(self): self.assert_bad_scope(caseIds=["C10", "C10"], sampleCount=2)
    def test_scope_unknown_id(self): self.assert_bad_scope(caseIds=["C99"], sampleCount=1)
    def test_scope_bool_count(self): self.assert_bad_scope(caseIds=["C10"], sampleCount=True)
    def test_scope_object_profile(self): self.assert_bad_scope(modelProfileId={"id": "profile"})
    def test_scope_blank_profile(self): self.assert_bad_scope(modelProfileId="  ")
    def test_scope_blank_model(self): self.assert_bad_scope(modelId=" ")
    def test_scope_untrimmed_model(self): self.assert_bad_scope(modelId=" model ")
    def test_scope_zero_count(self): self.assert_bad_scope(sampleCount=0)
    def test_scope_negative_count(self): self.assert_bad_scope(sampleCount=-1)
    def test_scope_float_count(self): self.assert_bad_scope(sampleCount=4.0)
    def test_scope_bool_token_budget(self): self.assert_bad_scope(maxTotalTokens=True)
    def test_scope_bool_cost_budget(self): self.assert_bad_scope(maxCostCny=True)
    def test_scope_negative_cost(self): self.assert_bad_scope(maxCostCny=-1)
    def test_scope_float_token_budget(self): self.assert_bad_scope(maxTotalTokens=12000.0)
    def test_scope_bool_attempts(self): self.assert_bad_scope(maxAttempts=True)
    def test_scope_zero_attempts(self): self.assert_bad_scope(maxAttempts=0)
    def test_scope_negative_attempts(self): self.assert_bad_scope(maxAttempts=-1)
    def test_scope_float_attempts(self): self.assert_bad_scope(maxAttempts=1.0)
    def test_scope_empty_cases(self): self.assert_bad_scope(caseIds=[], sampleCount=0)
    def test_scope_nonstring_case(self): self.assert_bad_scope(caseIds=[True], sampleCount=1)
    def test_scope_missing_attempts(self):
        value = self.valid_scope(); del value["maxAttempts"]
        code, _ = self.run_cli("scope_preflight.py", self.scope_args(value)); self.assertNotEqual(code, 0)
    def test_scope_missing_budget(self):
        value = self.valid_scope(); del value["maxTotalTokens"]
        code, _ = self.run_cli("scope_preflight.py", self.scope_args(value)); self.assertNotEqual(code, 0)
    def test_scope_secret_field(self): self.assert_bad_scope(apiKey="non-sensitive-test-placeholder")
    def test_scope_unknown_field(self): self.assert_bad_scope(surprise="unexpected")
    def test_scope_non_json(self):
        code, result = self.run_cli("scope_preflight.py", self.scope_args("not json")); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "INVALID_JSON")
    def test_scope_root_array(self):
        code, _ = self.run_cli("scope_preflight.py", self.scope_args([])); self.assertNotEqual(code, 0)
    def test_scope_duplicate_keys(self):
        code, result = self.run_cli("scope_preflight.py", self.scope_args('{"caseIds":[],"caseIds":["C10"]}')); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "DUPLICATE_KEY")
    def test_scope_nan_cost(self):
        value = self.valid_scope(); del value["maxTotalTokens"]
        text = json.dumps(value)[:-1] + ',"maxCostCny":NaN}'
        code, result = self.run_cli("scope_preflight.py", self.scope_args(text)); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "NONFINITE_NUMBER")
    def test_scope_infinite_cost(self):
        value = self.valid_scope(); del value["maxTotalTokens"]
        text = json.dumps(value)[:-1] + ',"maxCostCny":Infinity}'
        code, result = self.run_cli("scope_preflight.py", self.scope_args(text)); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "NONFINITE_NUMBER")
    def test_scope_overflow_cost(self):
        value = self.valid_scope(); del value["maxTotalTokens"]
        text = json.dumps(value)[:-1] + ',"maxCostCny":1e999}'
        code, _ = self.run_cli("scope_preflight.py", self.scope_args(text)); self.assertNotEqual(code, 0)
    def test_scope_valid_subset_no_authorization(self):
        code, result = self.run_cli("scope_preflight.py", self.scope_args(self.valid_scope()))
        self.assertEqual(code, 0); self.assertFalse(result["createsHumanAuthorization"]); self.assertFalse(result["modelVerified"]); self.assertFalse(result["budgetEnforced"]); self.assertEqual(result["maximumCalls"], 4)
    def test_scope_valid_fullset_cost(self):
        value = self.valid_scope(); value.update(caseIds=self.ids, sampleCount=15, maxCostCny=0.5); del value["maxTotalTokens"]
        code, result = self.run_cli("scope_preflight.py", self.scope_args(value)); self.assertEqual(code, 0); self.assertEqual(result["sampleCount"], 15)
    def test_scope_attempts_hash_and_explicit_review(self):
        value = self.valid_scope()
        code, first = self.run_cli("scope_preflight.py", self.scope_args(value), "first"); self.assertEqual(code, 0)
        value["maxAttempts"] = 2
        code, second = self.run_cli("scope_preflight.py", self.scope_args(value, "scope-two.json"), "second")
        self.assertEqual(code, 0); self.assertTrue(second["extraAttemptsNeedExplicitAuthorization"]); self.assertEqual(second["maximumCalls"], 8); self.assertNotEqual(first["scopeSHA"], second["scopeSHA"])
    def test_scope_output_preserves_first_result(self):
        args = self.scope_args(self.valid_scope())
        code, _ = self.run_cli("scope_preflight.py", args, "first"); self.assertEqual(code, 0)
        existing = self.runs / self._testMethodName / "first"
        before = sha_file(existing / "RESULT.json")
        code, _ = self.run_cli("scope_preflight.py", args, "second", output_override=existing)
        self.assertNotEqual(code, 0); self.assertEqual(before, sha_file(existing / "RESULT.json"))

    def aggregate_args(self, ids=None, mutate=None, copy_case=None):
        ids = ids or self.ids
        directory = self.runs / self._testMethodName
        directory.mkdir(exist_ok=True)
        summary, exports = copy.deepcopy(self.summary), copy.deepcopy(self.docx)
        summary.update(results=[x for x in summary["results"] if x["caseId"] in ids], caseCount=len(ids), technicalStructurePassed=len(ids))
        exports.update(records=[x for x in exports["records"] if x["caseId"] in ids], caseCount=len(ids))
        if mutate:
            mutate(summary, exports)
        write(directory / "scope.json", {"caseIds": ids, "sampleCount": len(ids)})
        write(directory / "SUMMARY.json", summary)
        write(directory / "DOCX-MANIFEST.json", exports)
        cases = QUALITY / "runs/offline-third/quality-cases"
        if copy_case:
            copied = Path(tempfile.mkdtemp(prefix="zqky-g4-quality-author-case-"))
            target = copied / copy_case
            target.mkdir()
            for path in (cases / copy_case).iterdir():
                if path.is_file():
                    (target / path.name).write_bytes(path.read_bytes())
            # Other cases still resolve to original files, with no writes there.
            cases = copied
            for cid in ids:
                if cid != copy_case:
                    (copied / cid).mkdir()
                    for path in (QUALITY / "runs/offline-third/quality-cases" / cid).iterdir():
                        if path.is_file():
                            (copied / cid / path.name).write_bytes(path.read_bytes())
            write(directory / "owned-case-temp.json", {"path": str(copied), "retained": True})
        return ["--case-manifest", QUALITY / "case-specs.json", "--case-manifest-sha", MANIFEST_SHA, "--artifact-manifest", OLD / "CANDIDATE-B6-r1.json", "--artifact-manifest-sha", ARTIFACT_SHA, "--scope", directory / "scope.json", "--summary", directory / "SUMMARY.json", "--cases-root", cases, "--docx-manifest", directory / "DOCX-MANIFEST.json", "--docx-root", QUALITY / "exports/offline-third", "--seed", QUALITY / "runs/offline-third/seed.json", "--data-root", self.summary["dataRoot"], "--artifact-case-prefix", "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/runs/offline-third/quality-cases", "--artifact-docx-prefix", "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/exports/offline-third", "--artifact-seed-path", "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/runs/offline-third/seed.json", "--source-mode", "frozen-source-binding"]

    def test_aggregate_original_missing_c15(self):
        def mutate(summary, _exports): summary["results"] = summary["results"][:-1]
        code, result = self.run_cli("aggregate_review.py", self.aggregate_args(mutate=mutate))
        self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "CASE_SET_MISMATCH"); self.assertIn("C15", result["error"]["reason"])
    def test_aggregate_duplicate_result(self):
        def mutate(summary, _exports): summary["results"].append(summary["results"][0])
        code, _ = self.run_cli("aggregate_review.py", self.aggregate_args(mutate=mutate)); self.assertNotEqual(code, 0)
    def test_aggregate_extra_unknown(self):
        def mutate(summary, _exports): summary["results"].append({"caseId": "C99"})
        code, _ = self.run_cli("aggregate_review.py", self.aggregate_args(mutate=mutate)); self.assertNotEqual(code, 0)
    def test_aggregate_extra_known_unselected(self):
        def mutate(summary, _exports): summary["results"].append(self.summary["results"][-1])
        code, _ = self.run_cli("aggregate_review.py", self.aggregate_args(ids=self.ids[:-1], mutate=mutate)); self.assertNotEqual(code, 0)
    def test_aggregate_missing_export(self):
        def mutate(_summary, exports): exports["records"] = exports["records"][:-1]
        code, _ = self.run_cli("aggregate_review.py", self.aggregate_args(mutate=mutate)); self.assertNotEqual(code, 0)
    def test_aggregate_duplicate_export(self):
        def mutate(_summary, exports): exports["records"].append(exports["records"][0])
        code, _ = self.run_cli("aggregate_review.py", self.aggregate_args(mutate=mutate)); self.assertNotEqual(code, 0)
    def test_aggregate_hash_mismatch(self):
        args = self.aggregate_args(copy_case="C01"); cases = Path(args[args.index("--cases-root") + 1])
        with (cases / "C01/input.json").open("a", encoding="utf-8") as stream: stream.write(" ")
        code, result = self.run_cli("aggregate_review.py", args); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "HASH_MISMATCH")
    def test_aggregate_missing_result_file(self):
        args = self.aggregate_args(copy_case="C01"); cases = Path(args[args.index("--cases-root") + 1])
        # This new copy is owned by the test. Original file remains read-only.
        (cases / "C01/result.json").rename(cases / "C01/result.omitted.json")
        code, result = self.run_cli("aggregate_review.py", args); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "MISSING_FILE")
    def test_aggregate_missing_docx_file(self):
        args = self.aggregate_args(); missing = self.runs / self._testMethodName / "empty-docx"; missing.mkdir()
        args[args.index("--docx-root") + 1] = missing
        code, result = self.run_cli("aggregate_review.py", args); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["code"], "MISSING_FILE")
    def test_aggregate_wrong_source(self):
        args = self.aggregate_args()
        args[args.index("--data-root") + 1] = ROOT / "apps/api/.local-data"
        code, result = self.run_cli("aggregate_review.py", args); self.assertNotEqual(code, 0); self.assertEqual(result["error"]["field"], "seed.dataRoot")
    def test_aggregate_readonly_catalogs_missing_source_fails(self):
        args = self.aggregate_args()
        args[args.index("--source-mode") + 1] = "readonly-catalogs"
        code, result = self.run_cli("aggregate_review.py", args); self.assertNotEqual(code, 0); self.assertIn("seed.catalogPaths", result["error"]["field"])
    def test_aggregate_bad_zip_even_with_consistent_hash(self):
        directory = self.runs / self._testMethodName; directory.mkdir()
        corrupt = directory / "bad.docx"; corrupt.write_bytes(b"not a zip archive")
        bound = strict_json(QUALITY / "runs/offline-third/quality-cases/C01/case-bound-v3.json")
        fixed = strict_json(QUALITY / "runs/offline-third/quality-cases/C01/fixed-export-input.json")
        record = copy.deepcopy(self.docx["records"][0]); record["fileSHA"] = sha_file(corrupt); record["byteSize"] = corrupt.stat().st_size
        bound["export"].update(fileSHA=record["fileSHA"], byteSize=record["byteSize"])
        with self.assertRaises(CheckError) as caught: docx_check(corrupt, fixed["data"], record, fixed, bound, record["fileSHA"])
        self.assertEqual(caught.exception.code, "BAD_ZIP")
        write(directory / "negative-result.json", {"status": "EXPECTED_FAIL", "code": caught.exception.code, "originalArtifactsChanged": False})
    def tampered_binding_args(self, mutate):
        args = self.aggregate_args(copy_case="C01")
        cases = Path(args[args.index("--cases-root") + 1])
        path = cases / "C01/case-bound-v3.json"
        binding = strict_json(path)
        mutate(binding)
        # This is a newly constructed contradictory frozen input, not a new oracle.
        path.write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding="utf-8")
        index = strict_json(OLD / "CANDIDATE-B6-r1.json")
        key = "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/runs/offline-third/quality-cases/C01/case-bound-v3.json"
        index["frozenB6ArtifactFiles"][key] = sha_file(path)
        index_path = self.runs / self._testMethodName / "contradictory-frozen-index.json"
        write(index_path, index)
        args[args.index("--artifact-manifest") + 1] = index_path
        args[args.index("--artifact-manifest-sha") + 1] = sha_file(index_path)
        return args
    def test_binding_bad_row_canonical_hash(self):
        def mutate(binding): binding["refs"]["run"]["canonicalSHA"] = "0" * 64
        code, result = self.run_cli("aggregate_review.py", self.tampered_binding_args(mutate))
        self.assertNotEqual(code, 0); self.assertIn("canonicalSHA", result["error"]["field"])
    def test_binding_wrong_fixed_row_identity(self):
        def mutate(binding):
            binding["refs"]["run"]["records"][0]["id"] = "wrong-source-run"
            encoded = json.dumps(binding["refs"]["run"]["records"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            binding["refs"]["run"]["canonicalSHA"] = hashlib.sha256(encoded).hexdigest()
        code, result = self.run_cli("aggregate_review.py", self.tampered_binding_args(mutate))
        self.assertNotEqual(code, 0); self.assertIn("recordIdentity", result["error"]["field"])
    def test_binding_missing_full_source_rows(self):
        def mutate(binding):
            binding["refs"]["run"]["records"] = []
            binding["refs"]["run"]["canonicalSHA"] = hashlib.sha256(b"[]").hexdigest()
        code, result = self.run_cli("aggregate_review.py", self.tampered_binding_args(mutate))
        self.assertNotEqual(code, 0); self.assertIn("records", result["error"]["field"])
    def test_aggregate_correct_full_15(self):
        code, result = self.run_cli("aggregate_review.py", self.aggregate_args())
        self.assertEqual(code, 0, result); self.assertEqual(result["checkedCaseCount"], 15); self.assertEqual(result["docxStructurePassed"], 15); self.assertEqual(result["unrunCaseIds"], []); self.assertEqual(result["physicalSourceCheck"], "not_run_source_temp_unavailable")
    def test_aggregate_explicit_subset_14(self):
        code, result = self.run_cli("aggregate_review.py", self.aggregate_args(ids=self.ids[:-1]))
        self.assertEqual(code, 0, result); self.assertEqual(result["checkedCaseCount"], 14); self.assertEqual(result["technicalStructurePassed"], 14); self.assertEqual(result["unrunCaseIds"], ["C15"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
