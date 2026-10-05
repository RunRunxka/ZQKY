"""Independent-input author checks for the new offline preparation CLI."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
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
BATCH = ROOT / "docs/qa/TEACHING-LOOP-G4-B7A-20261005"
sys.path.insert(0, str(TOOLS))
from common import sha_file, strict_json
from prepare_review import NATIVE_FIELDS

GUARD = r'''
import builtins,json,os,pathlib,runpy,sys
counts={"networkAttempts":0,"appImportAttempts":0,"formalEnvReadAttempts":0,"databaseOpenAttempts":0}
original_import=builtins.__import__
def guarded_import(name,*args,**kwargs):
    if name=="app" or name.startswith("app."):
        counts["appImportAttempts"]+=1
        raise RuntimeError("Application import prohibited")
    return original_import(name,*args,**kwargs)
builtins.__import__=guarded_import
def audit(event,args):
    if event.startswith("socket."):
        counts["networkAttempts"]+=1
        raise RuntimeError("Network prohibited")
    if event=="sqlite3.connect":
        counts["databaseOpenAttempts"]+=1
        raise RuntimeError("Database open prohibited")
    if event=="open" and isinstance(args[0],(str,bytes,os.PathLike)):
        name=pathlib.Path(os.fsdecode(args[0])).name
        if name==".env" or name.startswith(".env."):
            counts["formalEnvReadAttempts"]+=1
            raise RuntimeError("Environment file prohibited")
        if pathlib.Path(os.fsdecode(args[0])).suffix.lower() in {".sqlite",".sqlite3",".db"}:
            counts["databaseOpenAttempts"]+=1
            raise RuntimeError("Database file open prohibited")
sys.addaudithook(audit)
target=sys.argv[1]
sys.argv=sys.argv[1:]
sys.path.insert(0,str(pathlib.Path(target).parent))
try:
    runpy.run_path(target,run_name="__main__")
finally:
    pathlib.Path(os.environ["PREP_GUARD_OUTPUT"]).write_text(json.dumps(counts),encoding="utf-8")
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def sources():
    return {str(p.relative_to(ROOT)): sha_file(p) for p in sorted(TOOLS.rglob("*")) if p.is_file() and p.suffix in {".py", ".md"}}


class PrepareReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = Path(os.environ["AUTHOR_RUN_DIR"])
        cls.runs.mkdir(parents=True, exist_ok=False)
        cls.plan = strict_json(BATCH / "b7a/plan-full-v1.json")
        cls.artifacts = strict_json(Path(cls.plan["aggregate"]["artifact_manifest"]))
        cls.old = {key: sha_file(ROOT / key) for key in cls.artifacts["frozenB6ArtifactFiles"]}
        write(cls.runs / "OLD-before.json", cls.old)
        cls.guard = Path(tempfile.mkdtemp(prefix="zqky-b7a-author-guard-")) / "guard_cli.py"
        cls.guard.write_text(GUARD, encoding="utf-8")
        write(cls.runs / "guard.json", {"file": str(cls.guard), "SHA": sha_file(cls.guard), "retained": True})

    @classmethod
    def tearDownClass(cls):
        after = {key: sha_file(ROOT / key) for key in cls.old}
        write(cls.runs / "OLD-after.json", {"hashes": after, "changed": [key for key in cls.old if cls.old[key] != after[key]]})
        if after != cls.old:
            raise AssertionError("old frozen material drift")

    def directory(self):
        directory = self.runs / self._testMethodName
        directory.mkdir(exist_ok=True)
        return directory

    def run_plan(self, value=None, label="run", output=None, expected_plan_sha=None):
        directory = self.directory()
        path = directory / (label + "-plan.json")
        if type(value) is str:
            with path.open("x", encoding="utf-8") as stream: stream.write(value)
        else:
            write(path, value if value is not None else self.plan)
        destination = output or directory / label
        guard_output = directory / (label + "-guard.json")
        argv = [sys.executable, "-B", str(self.guard), str(TOOLS / "prepare_review.py"), "--plan", str(path), "--output-dir", str(destination)]
        if expected_plan_sha:
            argv += ["--plan-sha", expected_plan_sha]
        before = sources()
        started = time.time()
        process = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "PREP_GUARD_OUTPUT": str(guard_output)})
        stdout, stderr = process.communicate(timeout=120)
        after = sources()
        with (directory / (label + ".log")).open("x", encoding="utf-8") as stream: stream.write(stdout + "\nSTDERR\n" + stderr)
        guard = strict_json(guard_output)
        write(directory / (label + "-command.json"), {"command": argv, "pid": process.pid, "startedEpoch": started, "durationMs": (time.time() - started) * 1000, "exitCode": process.returncode, "sourceQABefore": before, "sourceQAAfter": after, "changed": [key for key in before if before[key] != after.get(key)], "guard": guard, "logHandlesClosed": True})
        self.assertEqual(before, after)
        self.assertEqual(guard, {"networkAttempts": 0, "appImportAttempts": 0, "formalEnvReadAttempts": 0, "databaseOpenAttempts": 0})
        result = strict_json(destination / "RESULT.json") if (destination / "RESULT.json").is_file() else json.loads(stdout)
        return process.returncode, result, destination

    def assert_fails(self, plan, code=None, label="run"):
        exit_code, result, directory = self.run_plan(plan, label=label)
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(result["status"], "FAIL_NO_MATERIAL_PASS_PUBLISHED")
        self.assertFalse((directory / "MATERIALS.json").exists())
        if code: self.assertEqual(result["error"]["code"], code)

    def mutate_collection(self, plan, ids):
        directory = self.directory()
        scope = directory / "scope.json"
        summary = strict_json(Path(plan["aggregate"]["summary"]))
        docx = strict_json(Path(plan["aggregate"]["docx_manifest"]))
        summary.update(results=[x for x in summary["results"] if x["caseId"] in ids], caseCount=len(ids), technicalStructurePassed=len(ids))
        docx.update(records=[x for x in docx["records"] if x["caseId"] in ids], caseCount=len(ids))
        write(scope, {"caseIds": ids, "sampleCount": len(ids)})
        write(directory / "SUMMARY.json", summary)
        write(directory / "DOCX-MANIFEST.json", docx)
        plan["aggregate"].update(scope=str(scope), summary=str(directory / "SUMMARY.json"), docx_manifest=str(directory / "DOCX-MANIFEST.json"))
        return summary, docx

    def add_fixture_artifact(self, plan, filename, payload):
        directory = self.directory()
        path = directory / filename
        if isinstance(payload, bytes): path.write_bytes(payload)
        else: write(path, payload)
        key = path.relative_to(ROOT).as_posix()
        index = strict_json(Path(plan["aggregate"]["artifact_manifest"]))
        index["frozenB6ArtifactFiles"][key] = sha_file(path)
        index_path = directory / ("index-" + filename.replace(".", "-") + ".json")
        write(index_path, index)
        plan["aggregate"].update(artifact_manifest=str(index_path), artifact_manifest_sha=sha_file(index_path))
        return key

    def test_correct_fullset_and_native_blank(self):
        code, result, out = self.run_plan()
        self.assertEqual(code, 0, result)
        materials = strict_json(out / "MATERIALS.json")
        self.assertEqual(materials["selectedCaseIds"], ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14", "C15"])
        self.assertEqual(materials["caseTechnicalChecked"], 15)
        self.assertEqual(materials["historicalPdfPageEvidenceChecked"], 13)
        self.assertEqual(materials["requirementsMatrix"], self.plan["requirements"])
        self.assertEqual(materials["technical"]["physicalSourceCheck"], "not_run_source_temp_unavailable")
        self.assertEqual(materials["liveRun"], "not_run_user_offline_scope")
        self.assertFalse(materials["createsHumanAuthorization"])
        with (out / "native-pages-feedback.csv").open(encoding="utf-8-sig", newline="") as stream: native = list(csv.DictReader(stream))
        self.assertEqual(len(native), 4)
        for row in native:
            self.assertTrue(all(row[key] == "" for key in NATIVE_FIELDS[5:]))
        with (out / "pdf-reference-pages.csv").open(encoding="utf-8-sig", newline="") as stream: self.assertEqual(len(list(csv.DictReader(stream))), 13)

    def test_explicit_14_subset(self):
        plan = copy.deepcopy(self.plan)
        self.mutate_collection(plan, ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C14"])
        code, result, out = self.run_plan(plan)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["technicalCases"], 14)
        self.assertEqual(result["unrunCaseIds"], ["C15"])
        self.assertEqual(strict_json(out / "MATERIALS.json")["originalEmptyFeedbackRows"], 15)

    def test_missing_c15_fullscope(self):
        plan = copy.deepcopy(self.plan)
        summary = strict_json(Path(plan["aggregate"]["summary"]))
        summary["results"] = summary["results"][:-1]
        path = self.directory() / "SUMMARY.json"; write(path, summary)
        plan["aggregate"]["summary"] = str(path)
        self.assert_fails(plan, "CASE_SET_MISMATCH")

    def test_wrong_case_set(self):
        plan = copy.deepcopy(self.plan)
        scope = self.directory() / "scope.json"; write(scope, {"caseIds": ["C99"], "sampleCount": 1})
        plan["aggregate"]["scope"] = str(scope)
        self.assert_fails(plan, "UNKNOWN_CASE")

    def test_missing_frozen_artifact(self):
        plan = copy.deepcopy(self.plan)
        plan["materials"]["rubric"] = "docs/qa/no-such-frozen-rubric.md"
        self.assert_fails(plan, "MISSING_HASH")

    def test_wrong_manifest_sha(self):
        plan = copy.deepcopy(self.plan)
        plan["aggregate"]["artifact_manifest_sha"] = "0" * 64
        self.assert_fails(plan, "HASH_MISMATCH")

    def test_nonempty_human_feedback(self):
        plan = copy.deepcopy(self.plan)
        with (ROOT / plan["materials"]["feedbackCsv"]).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream); headers = reader.fieldnames; rows = list(reader)
        rows[0]["reviewer"] = "synthetic-unapproved-reviewer"
        output = io.StringIO(newline=""); writer = csv.DictWriter(output, fieldnames=headers); writer.writeheader(); writer.writerows(rows)
        plan["materials"]["feedbackCsv"] = self.add_fixture_artifact(plan, "nonempty-feedback.csv", b"\xef\xbb\xbf" + output.getvalue().encode("utf-8"))
        self.assert_fails(plan, "NONEMPTY_HUMAN_FEEDBACK")

    def test_wrong_four_export_set(self):
        plan = copy.deepcopy(self.plan)
        exports = strict_json(ROOT / plan["materials"]["representativeExportResult"]); exports["results"] = exports["results"][:-1]
        plan["materials"]["representativeExportResult"] = self.add_fixture_artifact(plan, "three-export-result.json", exports)
        self.assert_fails(plan, "CASE_SET_MISMATCH")

    def short_fixture(self, plan, omitted=None, corrupt_docx=False):
        directory = self.directory()
        original = ROOT / plan["materials"]["representativeRoot"] / "short"
        fixture = directory / "representative/short"; fixture.mkdir(parents=True)
        index = strict_json(Path(plan["aggregate"]["artifact_manifest"]))
        needed = ["manifest.json", "short.docx", "short.pdf", "offline-structure-and-pdf.json", "pdf-pages/page-1.png"]
        for filename in needed:
            key = (fixture / filename).relative_to(ROOT).as_posix()
            index["frozenB6ArtifactFiles"][key] = sha_file(original / filename)
            if filename == omitted: continue
            (fixture / filename).parent.mkdir(parents=True, exist_ok=True)
            (fixture / filename).write_bytes((original / filename).read_bytes())
        if corrupt_docx:
            (fixture / "short.docx").write_bytes(b"not a zip archive")
            index["frozenB6ArtifactFiles"][(fixture / "short.docx").relative_to(ROOT).as_posix()] = sha_file(fixture / "short.docx")
            manifest = strict_json(fixture / "manifest.json"); manifest["docx"]["SHA"] = sha_file(fixture / "short.docx")
            (fixture / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            index["frozenB6ArtifactFiles"][(fixture / "manifest.json").relative_to(ROOT).as_posix()] = sha_file(fixture / "manifest.json")
            exports = strict_json(ROOT / plan["materials"]["representativeExportResult"])
            exports["results"][0]["docx"]["SHA"] = sha_file(fixture / "short.docx"); exports["results"][0]["manifestSHA"] = sha_file(fixture / "manifest.json")
            exports_path = directory / "bad-docx-export-result.json"; write(exports_path, exports)
            key = exports_path.relative_to(ROOT).as_posix(); index["frozenB6ArtifactFiles"][key] = sha_file(exports_path)
            plan["materials"]["representativeExportResult"] = key
        index_path = directory / "fixture-index.json"; write(index_path, index)
        plan["aggregate"].update(artifact_manifest=str(index_path), artifact_manifest_sha=sha_file(index_path))
        plan["materials"]["representativeRoot"] = (directory / "representative").relative_to(ROOT).as_posix()

    def test_missing_actual_pdf(self):
        plan = copy.deepcopy(self.plan); self.short_fixture(plan, omitted="short.pdf"); self.assert_fails(plan, "MISSING_FILE")
    def test_missing_actual_pdf_page_png(self):
        plan = copy.deepcopy(self.plan); self.short_fixture(plan, omitted="pdf-pages/page-1.png"); self.assert_fails(plan, "MISSING_FILE")
    def test_representative_bad_docx_zip(self):
        plan = copy.deepcopy(self.plan); self.short_fixture(plan, corrupt_docx=True); self.assert_fails(plan, "BAD_ZIP")
    def test_wrong_source_binding(self):
        plan = copy.deepcopy(self.plan)
        plan["aggregate"]["data_root"] = str(ROOT / "apps/api/.local-data")
        self.assert_fails(plan, "EVIDENCE_MISMATCH")
    def test_schema_boolean(self):
        plan = copy.deepcopy(self.plan); plan["schemaVersion"] = True; self.assert_fails(plan)
    def test_schema_float(self):
        plan = copy.deepcopy(self.plan); plan["schemaVersion"] = 1.0; self.assert_fails(plan)
    def test_secret_field(self):
        plan = copy.deepcopy(self.plan); plan["apiKey"] = "non-sensitive-test-only"; self.assert_fails(plan, "UNEXPECTED_FIELD")
    def test_unknown_field(self):
        plan = copy.deepcopy(self.plan); plan["surprise"] = 1; self.assert_fails(plan, "UNEXPECTED_FIELD")
    def test_duplicate_json_key(self): self.assert_fails('{"schemaVersion":1,"schemaVersion":1}', "DUPLICATE_KEY")
    def test_non_json(self): self.assert_fails("not json", "INVALID_JSON")
    def test_nan_json(self): self.assert_fails('{"budget":NaN}', "NONFINITE_NUMBER")
    def test_wrong_requirements_matrix_sha(self):
        plan = copy.deepcopy(self.plan); plan["requirements"]["sha256"] = "0" * 64; self.assert_fails(plan, "EVIDENCE_MISMATCH")
    def test_output_preserves_first_result(self):
        code, _, out = self.run_plan(label="first"); self.assertEqual(code, 0)
        before = sha_file(out / "MATERIALS.json")
        code, _, _ = self.run_plan(label="second", output=out)
        self.assertNotEqual(code, 0); self.assertEqual(before, sha_file(out / "MATERIALS.json"))

    def feedback_csv_rows(self):
        with (ROOT / self.plan["materials"]["feedbackCsv"]).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream, strict=True))

    def csv_fixture_plan(self, rows, filename="feedback.csv", bom=True, newline="\r\n", quoting=csv.QUOTE_MINIMAL):
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator=newline, quoting=quoting).writerows(rows)
        payload = (b"\xef\xbb\xbf" if bom else b"") + output.getvalue().encode("utf-8")
        plan = copy.deepcopy(self.plan)
        plan["materials"]["feedbackCsv"] = self.add_fixture_artifact(plan, filename, payload)
        return plan

    def markdown_fixture_plan(self, text, filename="feedback.md"):
        plan = copy.deepcopy(self.plan)
        plan["materials"]["feedbackMd"] = self.add_fixture_artifact(plan, filename, text.encode("utf-8"))
        return plan

    def original_markdown(self):
        return (ROOT / self.plan["materials"]["feedbackMd"]).read_bytes().decode("utf-8-sig")

    def test_csv_extra_nonempty_cell(self):
        rows = self.feedback_csv_rows(); rows[1].append("synthetic human verdict PASS")
        self.assert_fails(self.csv_fixture_plan(rows), "INVALID_FEEDBACK_SHAPE")

    def test_csv_extra_empty_cell(self):
        rows = self.feedback_csv_rows(); rows[1].append("")
        self.assert_fails(self.csv_fixture_plan(rows), "INVALID_FEEDBACK_SHAPE")

    def test_csv_extra_empty_then_nonempty_cell(self):
        rows = self.feedback_csv_rows(); rows[1] += ["", "synthetic review content"]
        self.assert_fails(self.csv_fixture_plan(rows), "INVALID_FEEDBACK_SHAPE")

    def test_csv_short_row(self):
        rows = self.feedback_csv_rows(); rows[1].pop()
        self.assert_fails(self.csv_fixture_plan(rows), "INVALID_FEEDBACK_SHAPE")

    def test_csv_duplicate_header(self):
        rows = self.feedback_csv_rows(); rows[0][-1] = rows[0][-2]
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_unknown_header(self):
        rows = self.feedback_csv_rows(); rows[0][-1] = "unknown_review_field"
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_missing_header(self):
        rows = self.feedback_csv_rows(); rows[0].pop()
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_duplicate_case(self):
        rows = self.feedback_csv_rows(); rows[2] = rows[1].copy()
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_missing_case(self):
        rows = self.feedback_csv_rows(); rows.pop()
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_unknown_case(self):
        rows = self.feedback_csv_rows(); rows[1][0] = "C99"
        self.assert_fails(self.csv_fixture_plan(rows))

    def test_csv_wrong_case_hash(self):
        rows = self.feedback_csv_rows(); rows[1][1] = "0" * 64
        self.assert_fails(self.csv_fixture_plan(rows), "EVIDENCE_MISMATCH")

    def test_csv_wrong_docx_hash(self):
        rows = self.feedback_csv_rows(); rows[1][4] = "0" * 64
        self.assert_fails(self.csv_fixture_plan(rows), "EVIDENCE_MISMATCH")

    def test_csv_each_human_column_must_be_blank(self):
        for index, column in enumerate(self.feedback_csv_rows()[0][5:], 5):
            with self.subTest(column=column):
                rows = self.feedback_csv_rows(); rows[1][index] = "synthetic unapproved review content"
                filename = "feedback-human-" + str(index) + ".csv"
                self.assert_fails(self.csv_fixture_plan(rows, filename), "NONEMPTY_HUMAN_FEEDBACK", label="human-" + str(index))

    def test_csv_legal_quoting_bom_newline_and_multiline_blank(self):
        for label, bom, newline in (("bom-crlf", True, "\r\n"), ("plain-lf", False, "\n")):
            with self.subTest(label=label):
                rows = self.feedback_csv_rows()
                rows[1][5:] = [" \t\r\n"] * 15
                plan = self.csv_fixture_plan(rows, label + ".csv", bom=bom, newline=newline, quoting=csv.QUOTE_ALL)
                code, result, out = self.run_plan(plan, label=label)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["humanFieldsFilled"], 0)
                self.assertEqual(len(strict_json(out / "MATERIALS.json")["materialReferences"]), 273)

    def test_csv_unterminated_quote(self):
        plan = copy.deepcopy(self.plan)
        payload = (ROOT / plan["materials"]["feedbackCsv"]).read_bytes() + b'"unclosed'
        plan["materials"]["feedbackCsv"] = self.add_fixture_artifact(plan, "unterminated.csv", payload)
        self.assert_fails(plan, "INVALID_MATERIALS")

    def test_markdown_every_human_slot_must_be_blank(self):
        fields = ["评审人", "日期", "硬失败及原文位置", "学情事实解释", "教材支持相关性", "目标KP覆盖", "活动课堂检测", "分钟可实施性", "教师字段保持", "内容准确可解释", "练习反馈", "不足", "修改建议", "真人结论"]
        for index, field in enumerate(fields):
            with self.subTest(field=field):
                original = self.original_markdown()
                self.assertIn(field + "：____", original)
                changed = original.replace(field + "：____", field + "：synthetic unapproved review content", 1)
                self.assert_fails(self.markdown_fixture_plan(changed, "feedback-slot-" + str(index) + ".md"), "INVALID_FEEDBACK_TEMPLATE", label="slot-" + str(index))

    def test_markdown_append_unknown_review_body(self):
        changed = self.original_markdown() + "\n附加教学评价：synthetic reviewer says PASS\n"
        self.assert_fails(self.markdown_fixture_plan(changed), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_prepend_unknown_review_body(self):
        changed = "synthetic reviewer says PASS\n" + self.original_markdown()
        self.assert_fails(self.markdown_fixture_plan(changed), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_unknown_case(self):
        changed = self.original_markdown().replace("## C01 ", "## C99 ", 1)
        self.assert_fails(self.markdown_fixture_plan(changed), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_duplicate_case_block(self):
        original = self.original_markdown()
        block = original.split("## C01 ", 1)[1].split("## C02 ", 1)[0]
        self.assert_fails(self.markdown_fixture_plan(original + "\n## C01 " + block), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_missing_case_block(self):
        changed = self.original_markdown().split("## C15 ", 1)[0]
        self.assert_fails(self.markdown_fixture_plan(changed), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_wrong_frozen_title(self):
        changed = self.original_markdown().replace("## C01 单知识点失分", "## C01 synthetic changed title", 1)
        self.assert_fails(self.markdown_fixture_plan(changed), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_wrong_frozen_case_hash(self):
        original = self.original_markdown()
        first_hash = original.split("CaseHash `", 1)[1].split("`", 1)[0]
        self.assert_fails(self.markdown_fixture_plan(original.replace(first_hash, "0" * 64, 1)), "INVALID_FEEDBACK_TEMPLATE")

    def test_markdown_legal_bom_and_line_endings(self):
        original = self.original_markdown().replace("\r\n", "\n").replace("\r", "\n")
        for label, prefix, newline in (("bom-crlf", "\ufeff", "\r\n"), ("bom-cr", "\ufeff", "\r"), ("plain-lf", "", "\n")):
            with self.subTest(label=label):
                plan = self.markdown_fixture_plan(prefix + original.replace("\n", newline), label + ".md")
                code, result, _ = self.run_plan(plan, label=label)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["humanFieldsFilled"], 0)

    def test_feedback_path_escape(self):
        plan = copy.deepcopy(self.plan); plan["materials"]["feedbackMd"] = "../escape.md"
        self.assert_fails(plan)

    def test_feedback_missing_frozen_artifact(self):
        plan = copy.deepcopy(self.plan)
        index = strict_json(Path(plan["aggregate"]["artifact_manifest"]))
        del index["frozenB6ArtifactFiles"][plan["materials"]["feedbackMd"]]
        path = self.directory() / "index.json"; write(path, index)
        plan["aggregate"].update(artifact_manifest=str(path), artifact_manifest_sha=sha_file(path))
        self.assert_fails(plan, "MISSING_HASH")

    def test_feedback_sha_mismatch(self):
        plan = self.markdown_fixture_plan(self.original_markdown())
        index = strict_json(Path(plan["aggregate"]["artifact_manifest"]))
        index["frozenB6ArtifactFiles"][plan["materials"]["feedbackMd"]] = "0" * 64
        path = self.directory() / "wrong-index.json"; write(path, index)
        plan["aggregate"].update(artifact_manifest=str(path), artifact_manifest_sha=sha_file(path))
        self.assert_fails(plan, "EVIDENCE_MISMATCH")

    def test_case_manifest_sha_mismatch(self):
        plan = copy.deepcopy(self.plan); plan["aggregate"]["case_manifest_sha"] = "0" * 64
        self.assert_fails(plan, "HASH_MISMATCH")


if __name__ == "__main__":
    unittest.main(verbosity=2)
