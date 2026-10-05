"""Prepare a frozen offline review index, never model execution or human scores.

Reuse the G4 fail-closed aggregator. Existing cases, outputs, DOCX/PDF and
rendered pages are checked and referenced, never regenerated or copied.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET

from common import CheckError, checked_json, create_output, exact_object, known_case_ids, offline_status, require, sha_file, strict_json, trimmed_string, write_json
from aggregate_review import CASE_FILES, BODY_FIELDS, W, aggregate, body_shape, compare, exact_ids

AGGREGATE_PATHS = {"case_manifest", "artifact_manifest", "scope", "summary", "cases_root", "docx_manifest", "docx_root", "seed", "data_root"}
AGGREGATE_STRINGS = {"case_manifest_sha", "artifact_manifest_sha", "artifact_case_prefix", "artifact_docx_prefix", "artifact_seed_path", "source_mode"}
REVIEW_DIMENSIONS = ["学情事实解释", "教材支持相关性", "目标KP覆盖", "活动课堂检测", "分钟可实施性", "教师字段保持", "内容准确可解释", "练习反馈"]
FEEDBACK_FIELDS = ["case_id", "case_hash", "bound_v3_sha", "candidate_sha", "docx_sha", "reviewer", "reviewed_at", "hard_failure", "evidence_location"] + REVIEW_DIMENSIONS + ["不足", "修改建议", "真人结论"]
SAMPLE_IDS = ["short", "long", "multi", "symbols"]
PDF_PAGE_COUNTS = {"short": 1, "long": 8, "multi": 2, "symbols": 2}
NATIVE_FIELDS = ["sample_id", "docx_path", "docx_sha", "fixed_revision_id", "source_label", "reviewer", "reviewed_at", "application", "application_version", "native_total_pages", "native_page_no", "complete_fields", "complete_secondary", "chinese_and_symbols", "merged_cells", "table_continuation", "clipping_or_overlap", "evidence_location", "reason", "modification_advice", "human_verdict"]


def relative_key(key, field):
    trimmed_string(key, field)
    path = PurePosixPath(key)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in key and ":" not in key, field, "must be a safe repository-relative artifact key")
    return key


def rooted_file(root, key):
    relative_key(key, "artifactKey")
    path = (root / key).resolve()
    require(root in path.parents, key, "artifact escapes explicit root")
    return path


def load_plan(path, expected_sha=None):
    plan = checked_json(path, expected_sha) if expected_sha else strict_json(path)
    fields = {"schemaVersion", "mode", "artifactRoot", "requirements", "g4Close", "aggregate", "materials"}
    exact_object(plan, "plan", fields, fields)
    require(type(plan["schemaVersion"]) is int and plan["schemaVersion"] == 1, "plan.schemaVersion", "must be exact integer schema version 1; boolean and float are not versions")
    compare(plan["mode"], "offline_review_preparation", "plan.mode")
    root = Path(trimmed_string(plan["artifactRoot"], "plan.artifactRoot")).resolve()
    require(root.is_dir(), "plan.artifactRoot", "explicit artifact root must exist")
    for name in ("requirements", "g4Close"):
        item = exact_object(plan[name], "plan." + name, {"file", "sha256"}, {"file", "sha256"})
        reference = rooted_file(root, item["file"])
        if name == "g4Close":
            close = checked_json(reference, item["sha256"])
            compare(close["status"], "G4_CLOSED_LIMITED_INDEPENDENT_TECHNICAL", "plan.g4Close.status")
        else:
            compare(sha_file(reference), item["sha256"], "plan.requirements.sha256")
    values = exact_object(plan["aggregate"], "plan.aggregate", AGGREGATE_PATHS | AGGREGATE_STRINGS, AGGREGATE_PATHS | AGGREGATE_STRINGS)
    args = argparse.Namespace()
    for key in AGGREGATE_PATHS:
        setattr(args, key, Path(trimmed_string(values[key], "plan.aggregate." + key)))
    for key in AGGREGATE_STRINGS:
        setattr(args, key, trimmed_string(values[key], "plan.aggregate." + key))
    require(args.source_mode in {"frozen-source-binding", "readonly-catalogs"}, "plan.aggregate.source_mode", "unknown explicit source mode")
    material_fields = {"rubric", "feedbackCsv", "feedbackMd", "representativeExportResult", "representativeRoot", "representativeCases"}
    materials = exact_object(plan["materials"], "plan.materials", material_fields, material_fields)
    for key in material_fields - {"representativeCases"}:
        relative_key(materials[key], "plan.materials." + key)
    compare(materials["representativeCases"], SAMPLE_IDS, "plan.materials.representativeCases")
    return plan, root, args


def blank_feedback(path, manifest, artifacts, prefix):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        compare(reader.fieldnames, FEEDBACK_FIELDS, "feedbackCsv.fieldnames")
        records = list(reader)
    ids = known_case_ids(manifest)
    compare(len(records), len(ids), "feedbackCsv.rowCount")
    for index, row in enumerate(records):
        require(set(row) == set(FEEDBACK_FIELDS), "feedbackCsv.row[" + str(index) + "]", "must contain exactly the twenty feedback columns; extra cells are forbidden", "INVALID_FEEDBACK_SHAPE")
        require(all(type(row[column]) is str for column in FEEDBACK_FIELDS), "feedbackCsv.row[" + str(index) + "]", "all twenty cells must be strings; missing cells are forbidden", "INVALID_FEEDBACK_SHAPE")
    compare([x["case_id"] for x in records], ids, "feedbackCsv.fullFrozenCaseIds")
    for row in records:
        key = prefix.rstrip("/") + "/" + row["case_id"] + "/"
        for column, name in (("case_hash", "case.json"), ("bound_v3_sha", "case-bound-v3.json"), ("candidate_sha", "candidate.json")):
            compare(row[column], artifacts[key + name], "feedbackCsv." + row["case_id"] + "." + column)
        require(all(type(row.get(column)) is str and not row[column].strip() for column in FEEDBACK_FIELDS[5:]), "feedbackCsv." + row["case_id"], "human review fields must be empty; this entry cannot fabricate or approve teacher feedback", "NONEMPTY_HUMAN_FEEDBACK")
    return records


def blank_feedback_markdown(path, manifest, artifacts, prefix):
    """Require the entire frozen blank template, not just its reference SHA.

    Only the initial UTF-8 BOM and line-ending representation may vary. All
    cases, titles, hashes, fixed prose and the fourteen empty slots per case
    must match; no scores, reviewer content or additional prose are accepted.
    """
    ids = known_case_ids(manifest)
    blocks = []
    for case, case_id in zip(manifest["cases"], ids):
        key = prefix.rstrip("/") + "/" + case_id + "/case.json"
        require(key in artifacts, key, "missing frozen case SHA", "MISSING_HASH")
        title = trimmed_string(case["title"], "feedbackMd." + case_id + ".frozenTitle")
        blocks.append(
            "## " + case_id + " " + title + "\n\n"
            "CaseHash `" + artifacts[key] + "`。\n\n"
            "评审人：____  日期：____  硬失败及原文位置：____\n\n"
            + "；".join(dimension + "：____" for dimension in REVIEW_DIMENSIONS)
            + "\n\n不足：____  修改建议：____  真人结论：____"
        )
    expected = (
        "# 教师反馈填写表\n\n"
        "所有分数与真人结论留空，当前teacher_review_pending。请先读RUBRIC.md，逐例填写硬失败与证据位置，再填八维0～3及修改建议。替身和JSON合法不作教学质量评价。\n\n"
        + "\n\n".join(blocks) + "\n"
    )
    actual = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    require(actual == expected, "feedbackMd", "must match the complete frozen blank template, including every case/title/hash and empty human slot; additional review content is forbidden", "INVALID_FEEDBACK_TEMPLATE")


def representative_docx(path, body):
    body_shape(body, "representative.completeBody")
    try:
        with zipfile.ZipFile(path) as archive:
            require(archive.testzip() is None, "representative.docx", "bad CRC", "BAD_ZIP")
            names = archive.namelist()
            require(len(names) == len(set(names)), "representative.docx", "duplicate ZIP entry", "BAD_ZIP")
            document = ET.fromstring(archive.read("word/document.xml"))
            text = "".join(x.text or "" for x in document.findall(".//w:t", W))
            for key in BODY_FIELDS - {"lessonTypes", "process"}:
                require(body[key] in text, "representative.docx." + key, "complete field missing")
            for item in body["process"]:
                for key in ("stage", "design", "secondary"):
                    require(item[key] in text, "representative.docx.process." + key, "complete process text missing")
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as error:
        raise CheckError("representative.docx", "invalid DOCX ZIP/XML", "BAD_ZIP") from error


def prepare(args):
    plan, root, aggregate_args = load_plan(args.plan, args.plan_sha)
    technical = aggregate(aggregate_args)  # New fail-closed checks, not a historical finalizer.
    manifest = checked_json(aggregate_args.case_manifest, aggregate_args.case_manifest_sha)
    index = checked_json(aggregate_args.artifact_manifest, aggregate_args.artifact_manifest_sha)
    artifacts = index.get("artifactFiles", index.get("frozenB6ArtifactFiles"))
    require(type(artifacts) is dict, "artifactManifest", "frozen SHA map is required")
    references = {}

    def ref(key):
        relative_key(key, "artifactKey")
        require(key in artifacts, key, "missing frozen artifact entry", "MISSING_HASH")
        path = rooted_file(root, key)
        compare(sha_file(path), artifacts[key], key + ".frozenSHA")
        item = {"artifactKey": key, "path": str(path), "SHA": artifacts[key]}
        references[key] = item
        return path

    selected = [x["caseId"] for x in technical["results"]]
    for case_id in selected:
        prefix = aggregate_args.artifact_case_prefix.rstrip("/") + "/" + case_id + "/"
        for filename in CASE_FILES:
            ref(prefix + filename)
        ref(aggregate_args.artifact_docx_prefix.rstrip("/") + "/" + case_id + ".docx")
    materials = plan["materials"]
    rubric = ref(materials["rubric"])
    feedback_csv = ref(materials["feedbackCsv"])
    feedback_md = ref(materials["feedbackMd"])
    original_feedback = blank_feedback(feedback_csv, manifest, artifacts, aggregate_args.artifact_case_prefix)
    for row in original_feedback:
        compare(row["docx_sha"], artifacts[aggregate_args.artifact_docx_prefix.rstrip("/") + "/" + row["case_id"] + ".docx"], "feedbackCsv." + row["case_id"] + ".docxSHA")
    blank_feedback_markdown(feedback_md, manifest, artifacts, aggregate_args.artifact_case_prefix)
    exports_path = ref(materials["representativeExportResult"])
    exports = strict_json(exports_path)
    records = exact_ids(exports["results"], SAMPLE_IDS, "representativeExports.results")
    native_rows, pdf_rows = [], []
    for sample_id in SAMPLE_IDS:
        record = records[sample_id]
        prefix = materials["representativeRoot"].rstrip("/") + "/" + sample_id + "/"
        manifest_path = ref(prefix + "manifest.json")
        sample = strict_json(manifest_path)
        compare(record["manifestSHA"], sha_file(manifest_path), "representative." + sample_id + ".manifestSHA")
        compare(sample["caseId"], sample_id, "representative." + sample_id + ".caseId")
        compare(sample["saved"]["currentRevisionId"], record["currentRevisionId"], "representative." + sample_id + ".fixedRevision")
        compare(sample["fullData"], sample["saved"]["currentRevision"]["data"], "representative." + sample_id + ".completeFixedBody")
        fixed = sample["saved"]["currentRevision"]
        compare(sample["context"]["analysisRunId"], fixed["contextSnapshot"]["analysis"]["analysisRunId"], "representative." + sample_id + ".selectedAnalysisRun")
        compare(sample["context"]["selectedKnowledgePointIds"], [x["knowledgePointId"] for x in fixed["contextSnapshot"]["analysis"]["knowledgePoints"]], "representative." + sample_id + ".selectedKnowledgePoints")
        compare(sample["before"]["current"]["currentRevision"], fixed, "representative." + sample_id + ".beforeCompleteFixedRevision")
        compare(sample["after"]["current"]["currentRevision"], fixed, "representative." + sample_id + ".afterCompleteFixedRevision")
        compare(sample["before"]["history"], sample["after"]["history"], "representative." + sample_id + ".fixedHistory")
        compare(sample["before"]["revisions"], sample["after"]["revisions"], "representative." + sample_id + ".allFixedHistoryJson")
        compare(sample["source"], record["sourceLabel"], "representative." + sample_id + ".fixedSourceLabel")
        docx_path, pdf_path = ref(prefix + sample_id + ".docx"), ref(prefix + sample_id + ".pdf")
        compare(record["docx"]["SHA"], sha_file(docx_path), "representative." + sample_id + ".docxSHA")
        compare(record["pdf"]["SHA"], sha_file(pdf_path), "representative." + sample_id + ".pdfSHA")
        compare(sample["docx"]["SHA"], record["docx"]["SHA"], "representative." + sample_id + ".manifestDocxSHA")
        compare(sample["pdf"]["SHA"], record["pdf"]["SHA"], "representative." + sample_id + ".manifestPdfSHA")
        require(pdf_path.read_bytes().startswith(b"%PDF-"), "representative." + sample_id + ".pdf", "actual PDF header missing")
        representative_docx(docx_path, sample["fullData"])
        offline_path = ref(prefix + "offline-structure-and-pdf.json")
        proof = strict_json(offline_path)
        pages = proof["pdf"]["pages"]
        pngs = proof["pdf"]["pagePNGs"]
        compare(record["PDFpages"], PDF_PAGE_COUNTS[sample_id], "representative." + sample_id + ".oldPDFpageCount")
        compare([x["page"] for x in pages], list(range(1, PDF_PAGE_COUNTS[sample_id] + 1)), "representative." + sample_id + ".oldPDFpages")
        compare(len(pngs), len(pages), "representative." + sample_id + ".oldPDFpagePNGs")
        for page, png in zip(pages, pngs):
            png_path = ref(prefix + "pdf-pages/page-" + str(page["page"]) + ".png")
            compare(png["SHA"], sha_file(png_path), "representative." + sample_id + ".pngSHA")
            require(png_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "representative." + sample_id + ".png", "actual PNG header missing")
            pdf_rows.append({"sample_id": sample_id, "reference_pdf_path": str(pdf_path), "reference_pdf_sha": sha_file(pdf_path), "historical_pdf_page_no": page["page"], "historical_pdf_total_pages": len(pages), "reference_png_path": str(png_path), "reference_png_sha": sha_file(png_path), "frozen_pdf_proof_sha": sha_file(offline_path), "native_word_wps_status": "not_run"})
        native_rows.append({"sample_id": sample_id, "docx_path": str(docx_path), "docx_sha": sha_file(docx_path), "fixed_revision_id": record["currentRevisionId"], "source_label": record["sourceLabel"]})
    compare(len(pdf_rows), 13, "historicalPdfReferencePages")
    return {
        "task": "B7A-OFFLINE-PREPARE", "status": "OFFLINE_MATERIALS_PREPARED",
        "planSHA": sha_file(args.plan), "requirementsMatrix": plan["requirements"], "g4Close": plan["g4Close"],
        "caseManifestSHA": aggregate_args.case_manifest_sha, "artifactManifestSHA": aggregate_args.artifact_manifest_sha,
        "selectedCaseIds": selected, "unrunCaseIds": technical["unrunCaseIds"], "technical": technical,
        "caseTechnicalChecked": len(selected), "caseActualDocxChecked": technical["docxStructurePassed"],
        "representativeDocxChecked": 4, "historicalPdfFilesChecked": 4, "historicalPdfPageEvidenceChecked": 13,
        "historicalOutputKind": "handwritten HTTP Transport fixture; no new outputs generated",
        "historicalPdfEvidence": "old actual PDF and rendered page SHA reference, not new rendering or native acceptance",
        "rubric": references[materials["rubric"]], "originalEmptyFeedbackCsv": references[materials["feedbackCsv"]],
        "originalEmptyFeedbackMd": references[materials["feedbackMd"]], "originalEmptyFeedbackRows": len(original_feedback),
        "rubricDimensions": REVIEW_DIMENSIONS, "materialReferences": list(references.values()),
        "nativeFeedbackStarterRows": native_rows, "pdfReferencePages": pdf_rows,
        "realModelCalls": 0, "executorPresent": False, "createsHumanAuthorization": False, "budgetEnforced": False,
        "originalB6B7Overall": "not_closed", "newExportOrRenderingCalls": 0,
        **offline_status(), "liveRun": "not_run_user_offline_scope", "nativeWordWps": "not_run_pending_human_manual_open",
    }


def csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        create_output(args.output_dir)
    except CheckError as error:
        print(json.dumps({"status": "FAIL", "error": error.as_dict(), **offline_status()}, ensure_ascii=False))
        return 2
    try:
        result = prepare(args)
        (args.output_dir / "native-pages-feedback.csv").write_bytes(csv_bytes(NATIVE_FIELDS, result["nativeFeedbackStarterRows"]))
        (args.output_dir / "pdf-reference-pages.csv").write_bytes(csv_bytes(list(result["pdfReferencePages"][0]), result["pdfReferencePages"]))
        usage = (
            "# 离线教学质量材料使用说明\n\n"
            "本包只核材料结构和SHA，不运行模型、不确认教学质量或Word/WPS排版。先读需求矩阵、手写expected和八维rubric，再读固定输入/fixture输出及原15行空feedback。"
            "需要填写时先复制空表到新的教师评审label；由真人填原文位置、支持/不支持理由、修改建议与评分，不覆盖旧证据。"
            "硬失败不能用平均分抵消。C10～C13只是未来优先阅读建议，不构成模型调用授权。\n\n"
            "native-pages-feedback.csv只有四个文件的起始行：应用/版本、真人姓名日期、实际原生页号/总页数和所有结论留空。"
            "请在Word/WPS手动打开原DOCX的工作副本，逐一实际页面新增行，填实际页数，核长中文/全部secondary/合并/表格续排/截断与来源文件名。"
            "pdf-reference-pages.csv的13页来自历史实际PDF，仅作对照，不能把其页码或总页数填作原生页数。"
            "当前原物理源复核状态在technical.physicalSourceCheck单列，冻结source binding核查不代表新四库/Blob物理通过。\n\n"
            "真实模型、真人教学判断与原生排版分别待验；本批用户明确只做离线。预检合法也不提供模型存在、真实授权或总预算执行保证。RAG-REL OPEN，原B6/B7整体未关闭。"
            "旧15输出、DOCX/PDF/PNG没有复制或重新生成。\n"
        )
        with (args.output_dir / "README.md").open("x", encoding="utf-8") as stream:
            stream.write(usage)
        for filename in ("native-pages-feedback.csv", "pdf-reference-pages.csv", "README.md"):
            result.setdefault("newPreparationFiles", {})[filename] = sha_file(args.output_dir / filename)
        write_json(args.output_dir / "MATERIALS.json", result)
        receipt = {"status": result["status"], "materialIndexSHA": sha_file(args.output_dir / "MATERIALS.json"), "planSHA": result["planSHA"], "requirementsMatrix": result["requirementsMatrix"], "selectedCaseIds": result["selectedCaseIds"], "unrunCaseIds": result["unrunCaseIds"], "technicalCases": result["caseTechnicalChecked"], "representativeDocx": 4, "historicalPdfReferencePages": 13, "humanFieldsFilled": 0, "createsHumanAuthorization": False, **offline_status(), "liveRun": "not_run_user_offline_scope"}
        exit_code = 0
    except (CheckError, OSError, KeyError, TypeError, IndexError, ValueError, csv.Error, sqlite3.Error) as error:
        detail = error.as_dict() if isinstance(error, CheckError) else {"field": "materials", "reason": "missing, malformed or unreadable preparation input", "code": "INVALID_MATERIALS"}
        receipt = {"status": "FAIL_NO_MATERIAL_PASS_PUBLISHED", "error": detail, **offline_status(), "liveRun": "not_run_user_offline_scope"}
        exit_code = 2
    receipt.update({"pid": os.getpid(), "at": datetime.now().astimezone().isoformat(), "exitCode": exit_code})
    write_json(args.output_dir / "RESULT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
