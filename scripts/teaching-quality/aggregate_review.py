"""Check the exact authorized case set and frozen evidence before any PASS.

Inputs and SHA anchors are explicit. Historical QA scripts are never imported.
SQLite is opened mode=ro/query_only only inside the explicitly supplied TEMP.
The result describes technical evidence; it cannot supply human scores or live
model quality, and never rewrites expected answers or source material.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import sqlite3
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from common import CheckError, canonical, checked_json, create_output, known_case_ids, offline_status, require, selection_scope, sha_bytes, sha_file, strict_json, write_json

BODY_FIELDS = {"title", "totalLessons", "currentLessonNo", "lessonTypes", "otherTypeText", "coreCompetencies", "keyPoints", "teachingDesign", "process", "exercises", "reflection"}
TEACHER_FIELDS = {"title", "totalLessons", "currentLessonNo", "lessonTypes", "otherTypeText", "reflection"}
AI_FIELDS = BODY_FIELDS - TEACHER_FIELDS
CASE_FILES = ("case.json", "expected.json", "student-state-table.json", "input.json", "input-frozen.json", "wire.json", "raw-transport-response.json", "source-snapshots.json", "original-lesson.json", "candidate.json", "selected-fields.json", "applied-result.json", "fixed-export-input.json", "case-bound-v3.json", "result.json")
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def exact_ids(records, expected, field):
    require(type(records) is list, field, "must be an array")
    ids = []
    for i, record in enumerate(records):
        require(type(record) is dict and type(record.get("caseId")) is str, f"{field}[{i}].caseId", "case ID is required")
        ids.append(record["caseId"])
    duplicate = sorted({x for x in ids if ids.count(x) > 1})
    missing, extra = sorted(set(expected) - set(ids)), sorted(set(ids) - set(expected))
    require(not duplicate and not missing and not extra, field, f"missing={missing}; extra={extra}; duplicate={duplicate}", "CASE_SET_MISMATCH")
    return {record["caseId"]: record for record in records}


def frozen_file(path, key, artifacts):
    require(key in artifacts, key, "missing frozen artifact SHA", "MISSING_HASH")
    return checked_json(path, artifacts[key])


def body_shape(body, field):
    require(type(body) is dict and set(body) == BODY_FIELDS, field, "must contain exactly the complete eleven body fields")
    for key in BODY_FIELDS - {"lessonTypes", "process"}:
        require(type(body[key]) is str, field + "." + key, "must be a string")
    require(type(body["lessonTypes"]) is list and all(type(x) is str for x in body["lessonTypes"]), field + ".lessonTypes", "must be a string array")
    require(type(body["process"]) is list, field + ".process", "must be an array")
    ids = []
    for i, process in enumerate(body["process"]):
        require(type(process) is dict and set(process) == {"id", "stage", "design", "secondary"} and all(type(x) is str for x in process.values()), field + f".process[{i}]", "complete ProcessItem with four strings is required")
        ids.append(process["id"])
    require(len(ids) == len(set(ids)), field + ".process", "duplicate process identity")


def compare(value, expected, field):
    require(value == expected, field, "differs from frozen expected/source identity", "EVIDENCE_MISMATCH")


def rows(conn, table, column, identifier):
    allowed = {"analysis_runs", "score_revisions", "student_item_scores", "paper_revisions", "paper_items", "paper_item_knowledge", "paper_source_blocks", "knowledge_point_revisions", "document_revisions", "question_revisions", "question_knowledge_links"}
    require(table in allowed and column in {"id", "score_revision_id", "paper_revision_id", "question_revision_id"}, "source.query", "unsupported readonly query")
    return [dict(x) for x in conn.execute(f'SELECT * FROM "{table}" WHERE "{column}"=? ORDER BY rowid', (identifier,))]


def fixed_rows(conn, binding, table, column, identifier, field):
    require(type(binding) is dict and type(binding.get("records")) is list, field, "full frozen records are required")
    compare(sha_bytes(canonical(binding["records"])), binding["canonicalSHA"], field + ".canonicalSHA")
    for record in binding["records"]:
        require(type(record) is dict and record.get(column) == identifier, field + ".recordIdentity", "wrong frozen source row identity")
    if table in {"analysis_runs", "score_revisions", "paper_revisions", "knowledge_point_revisions", "document_revisions", "question_revisions"}:
        require(len(binding["records"]) == 1, field + ".records", "exactly one fixed revision row is required")
    if conn is not None:
        actual = rows(conn, table, column, identifier)
        compare(actual, binding["records"], field + ".fullRecords")
    return binding["records"]


def readonly_sources(seed, data_root, stack):
    root = data_root.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    require(temporary_root in root.parents and root.parent.name.startswith("zqky-"), "dataRoot", "only an explicitly supplied zqky owned temporary data directory is accepted")
    compare(Path(seed["dataRoot"]).resolve(), root, "seed.dataRoot")
    require(set(seed["catalogPaths"]) == {"catalog", "knowledge", "question_bank", "teaching"}, "seed.catalogPaths", "exact four source catalogs required")
    db = {}
    for key, name in seed["catalogPaths"].items():
        path = Path(name).resolve()
        require(path.is_file() and root in path.parents, "seed.catalogPaths." + key, "must be an existing database under the explicit temporary root")
        conn = stack.enter_context(contextlib.closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        compare(conn.execute("PRAGMA query_only").fetchone()[0], 1, "sqlite.query_only")
        db[key] = conn
    return db


def source_check(case, frozen, source, binding, db, seed, field, physical):
    compare(frozen["analysisRunId"], case["runId"], field + ".analysisRunId")
    compare(frozen["classId"], case["classId"], field + ".classId")
    compare(frozen["scopeSnapshot"], case["scopeSnapshot"], field + ".scopeSnapshot")
    compare(frozen["evidenceRefs"], case["evidenceRefs"], field + ".evidenceRefs")
    compare(source["report"]["runId"], case["runId"], field + ".report.runId")
    compare(source["report"]["scoreRevisionId"], case["scoreRevisionId"], field + ".report.scoreRevisionId")
    compare(source["report"]["paperRevisionId"], case["paperRevisionId"], field + ".report.paperRevisionId")
    compare(source["selectedClassId"], case["classId"], field + ".selectedClassId")
    compare(source["selectedParticipantIds"], case["selectedParticipantIds"], field + ".selectedParticipantIds")
    compare(source["selectedPoints"], case["knowledge"], field + ".selectedPoints")
    compare(source["report"]["reportReady"], True, field + ".reportReady")
    selected_class_counts = []
    for point in case["knowledge"]:
        matches = [x for x in source["classes"] if x["classId"] == case["classId"] and x["knowledgePoint"]["knowledgePointId"] == point["knowledgePointId"]]
        require(len(matches) == 1, field + ".classes", "one explicit target class/knowledge count required")
        selected_class_counts.append({key: matches[0][key] for key in case["caseSpec"]["expectedTargetCounts"][len(selected_class_counts)]})
    compare(selected_class_counts, case["caseSpec"]["expectedTargetCounts"], field + ".classCountsAndNullDenominator")
    compare(frozen["contextSnapshot"]["analysis"]["scoreRevisionId"], case["scoreRevisionId"], field + ".context.scoreRevisionId")
    compare(frozen["contextSnapshot"]["analysis"]["paperRevisionId"], case["paperRevisionId"], field + ".context.paperRevisionId")
    refs = binding["refs"]
    teaching = db["teaching"]
    run_row = fixed_rows(teaching, refs["run"], "analysis_runs", "id", case["runId"], field + ".run")[0]
    score_row = fixed_rows(teaching, refs["score"], "score_revisions", "id", case["scoreRevisionId"], field + ".score")[0]
    matrix_rows = fixed_rows(teaching, refs["matrix"], "student_item_scores", "score_revision_id", case["scoreRevisionId"], field + ".matrix")
    compare(run_row["score_revision_id"], case["scoreRevisionId"], field + ".run.scoreRevision")
    compare(run_row["paper_revision_id"], case["paperRevisionId"], field + ".run.paperRevision")
    compare(run_row["assessment_id"], source["report"]["assessmentId"], field + ".run.assessment")
    compare(run_row["input_hash"], frozen["contextSnapshot"]["analysis"]["inputHash"], field + ".run.inputHash")
    compare(run_row["report_ready"], 1, field + ".run.ready")
    compare(run_row["rule_code"], case["ruleCode"], field + ".run.ruleCode")
    compare(score_row["assessment_id"], source["report"]["assessmentId"], field + ".score.assessment")
    compare(score_row["state"], "confirmed", field + ".score.state")
    compare(json.loads(score_row["participant_snapshot_json"]), source["score"]["participantSnapshot"], field + ".score.frozenParticipants")
    compare(json.loads(score_row["item_snapshot_json"]), source["score"]["itemSnapshot"], field + ".score.frozenItems")
    for row in matrix_rows:
        compare(row["assessment_id"], source["report"]["assessmentId"], field + ".matrix.assessment")
        compare(row["paper_revision_id"], case["paperRevisionId"], field + ".matrix.paperRevision")
    matrix = sorted((x["participant_id"], x["item_id"], x["status"], x["score_units"]) for x in matrix_rows)
    compare(matrix, sorted((x["participantId"], x["itemId"], x["status"], x["scoreUnits"]) for x in source["matrix"]), field + ".matrix.completeSourceCells")
    for key, table in (("revision", "paper_revisions"), ("items", "paper_items"), ("knowledge", "paper_item_knowledge"), ("blocks", "paper_source_blocks")):
        fixed_rows(teaching, refs["paper"][key], table, "id" if key == "revision" else "paper_revision_id", case["paperRevisionId"], field + ".paper." + key)
    compare(refs["paper"]["revision"]["records"][0]["state"], "confirmed", field + ".paper.state")
    compare({(x["knowledgePointId"], x["revisionId"]) for x in refs["knowledge"]}, {(x["knowledgePointId"], x["knowledgeRevisionId"]) for x in frozen["source"]["referenceKnowledge"]}, field + ".knowledge.identities")
    for kp in refs["knowledge"]:
        records = fixed_rows(db["knowledge"], kp, "knowledge_point_revisions", "id", kp["revisionId"], field + ".knowledge")
        require(len(records) == 1 and records[0]["knowledge_point_id"] == kp["knowledgePointId"], field + ".knowledge", "wrong knowledge source identity")
    compare({x["documentRevisionId"] for x in refs["material"]}, {x["documentRevisionId"] for x in frozen["source"]["textbooks"]}, field + ".material.identities")
    for material in refs["material"]:
        records = fixed_rows(db["catalog"], material, "document_revisions", "id", material["documentRevisionId"], field + ".material")
        require(len(records) == 1, field + ".material", "one fixed textbook revision required")
        row = records[0]
        base = Path(seed["catalogPaths"]["catalog"]).parent
        for name, blob_id, expected in (("originalBlobSHA", row["original_blob_id"], row["original_file_sha256"]), ("normalizedBlobSHA", row["normalized_blob_id"], row["normalized_text_sha256"]), ("sourceMapSHA", row["source_map_blob_id"], material["sourceMapSHA"])):
            require(type(blob_id) is str and len(blob_id) == 64 and all(x in "0123456789abcdef" for x in blob_id), field + ".material.blobId", "unsafe blob identity")
            if physical:
                path = base / ("blobs" if name == "originalBlobSHA" else "normalized") / blob_id
                compare(sha_file(path), expected, field + ".material." + name)
            compare(material[name], expected, field + ".material.bound." + name)
        selected = material["selectedSlice"]
        compare(selected, next(x for x in frozen["source"]["textbooks"] if x["documentRevisionId"] == material["documentRevisionId"]), field + ".material.selectedSlice")
        if physical:
            normal = (base / "normalized" / row["normalized_blob_id"]).read_text(encoding="utf-8")
            compare(normal[selected["charStart"]:selected["charEnd"]], selected["text"], field + ".material.sliceText")
        compare(sha_bytes(selected["text"].encode("utf-8")), material["selectedSliceSHA"], field + ".material.sliceSHA")
    compare({x["revisionId"] for x in refs["questions"]}, set(case["questionRevisionIds"]), field + ".question.identities")
    for question in refs["questions"]:
        fixed_rows(db["question_bank"], question["revision"], "question_revisions", "id", question["revisionId"], field + ".question.revision")
        fixed_rows(db["question_bank"], question["knowledge"], "question_knowledge_links", "question_revision_id", question["revisionId"], field + ".question.knowledge")
        compare(sha_bytes(canonical(question["fixedReader"])), question["fixedReaderSHA"], field + ".question.fixedReaderSHA")
    require(not refs["practices"] and not case["practiceRevisionIds"], field + ".practices", "this evidence schema has no practice row binding; cannot claim unverified practice sources")


def docx_check(path, data, record, fixed, binding, expected_sha):
    compare(sha_file(path), expected_sha, "docx.frozenSHA")
    compare(sha_file(path), record["fileSHA"], "docx.manifestSHA")
    compare(path.stat().st_size, record["byteSize"], "docx.byteSize")
    compare(record["revisionId"], fixed["revisionId"], "docx.revisionId")
    compare(record["sourceLabel"], fixed["sourceLabel"], "docx.sourceLabel")
    for key in ("fileSHA", "fixedExportInputSHA", "revisionId", "sourceLabel", "templateSHA", "exporterSourceSHA"):
        compare(record[key], binding["export"][key], "docx.boundExport." + key)
    try:
        with zipfile.ZipFile(path) as archive:
            require(archive.testzip() is None, "docx.zip", "bad CRC", "BAD_ZIP")
            names = archive.namelist()
            require(len(names) == len(set(names)), "docx.zip", "duplicate ZIP entry", "BAD_ZIP")
            root = ET.fromstring(archive.read("word/document.xml"))
            text = "".join(x.text or "" for x in root.findall(".//w:t", W))
            for key in BODY_FIELDS - {"lessonTypes", "process"}:
                require(data[key] in text, "docx." + key, "complete field missing")
            labels = {"new": "新课", "review": "复习课", "exercise": "试题讲评课", "experiment": "实验课", "other": "其它"}
            require(set(data["lessonTypes"]) <= set(labels), "docx.lessonTypes", "unknown lesson type")
            for key, label in labels.items():
                projected = ("☑" if key in data["lessonTypes"] else "□") + label
                require(projected in text, "docx.lessonTypes." + key, "complete checked/unchecked lesson type projection missing")
            for item in data["process"]:
                for key in ("stage", "design", "secondary"):
                    require(item[key] in text, "docx.process." + key, "complete process field missing")
            for name in names:
                if not name.endswith(".rels"):
                    continue
                base = "" if name == "_rels/.rels" else str(PurePosixPath(name).parent.parent)
                for rel in ET.fromstring(archive.read(name)):
                    if rel.attrib.get("TargetMode") == "External":
                        continue
                    target = posixpath.normpath(posixpath.join(base, rel.attrib.get("Target", ""))).lstrip("/")
                    require(target in names, "docx.relationships", "missing internal relationship target")
            require(len(root.findall(".//w:tbl", W)) >= 2, "docx.tables", "expected template tables missing")
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as error:
        raise CheckError("docx", "invalid DOCX ZIP/XML structure", "BAD_ZIP") from error
    return {"status": "PASS", "allBodyText": True, "allProcessSecondary": True, "zipCRC": "PASS", "relationships": "PASS", "nativeLayout": "not_run"}


def check_case(case_id, spec, summary_record, export, args, artifacts, db, seed):
    prefix = args.artifact_case_prefix.rstrip("/") + "/" + case_id
    directory = args.cases_root / case_id
    data = {name: frozen_file(directory / name, prefix + "/" + name, artifacts) for name in CASE_FILES}
    case, expected, frozen = data["case.json"], data["expected.json"], data["input-frozen.json"]
    result, binding = data["result.json"], data["case-bound-v3.json"]
    compare(summary_record, result, case_id + ".summaryResult")
    compare(case["caseSpec"], spec, case_id + ".handwrittenCaseSpec")
    compare(case["caseSpecPackSHA"], args.case_manifest_sha, case_id + ".caseSpecPackSHA")
    compare(expected["expectedTargetCounts"], spec["expectedTargetCounts"], case_id + ".handwrittenCounts")
    compare(result["caseId"], case_id, case_id + ".result.caseId")
    compare(binding["caseId"], case_id, case_id + ".binding.caseId")
    compare(result["caseHash"], sha_file(directory / "case.json"), case_id + ".caseHash")
    compare(result["expectedSHA"], sha_file(directory / "expected.json"), case_id + ".expectedSHA")
    binding_hashes = {"originalCaseSHA": "case.json", "expectedSHA": "expected.json", "inputSHA": "input.json", "frozenInputSHA": "input-frozen.json", "wireSHA": "wire.json", "rawSHA": "raw-transport-response.json", "candidateSHA": "candidate.json", "selectedFieldsSHA": "selected-fields.json", "appliedSHA": "applied-result.json"}
    for field_name, filename in binding_hashes.items():
        compare(binding[field_name], sha_file(directory / filename), case_id + ".binding." + field_name)
    for filename, digest in result["hashes"].items():
        require(filename in CASE_FILES, case_id + ".hashes", "unexpected evidence file")
        compare(sha_file(directory / filename), digest, case_id + ".hashes." + filename)
    compare(result["rawSHA"], sha_file(directory / "raw-transport-response.json"), case_id + ".rawSHA")
    compare(binding["modelFingerprint"], result["modelFingerprint"], case_id + ".boundModelFingerprint")
    compare(binding["promptVersion"], result["promptVersion"], case_id + ".boundPromptVersion")
    require(result["failure"] is None and result["technicalStructure"] == "PASS", case_id + ".technicalStructure", "recorded run is not a technical pass")
    source_check(case, frozen, data["source-snapshots.json"], binding, db, seed, case_id + ".source", args.source_mode == "readonly-catalogs")
    actual_counts = [x["counts"] for x in frozen["modelPayload"]["classSummary"]["knowledgePoints"]]
    for i, counts in enumerate(actual_counts):
        compare(counts, {k: v for k, v in expected["expectedTargetCounts"][i].items() if k != "ratio"}, case_id + f".anonymousCounts[{i}]")
    compare(len(actual_counts), len(expected["expectedTargetCounts"]), case_id + ".counts.length")
    body = data["wire.json"]["body"]
    users = [x["content"] for x in body["messages"] if x.get("role") == "user"]
    require(len(users) == 1, case_id + ".wire", "exactly one anonymous user message required")
    compare(json.loads(users[0]), frozen["modelPayload"], case_id + ".wire.anonymousPayload")
    system_messages = [x["content"] for x in body["messages"] if x.get("role") == "system"]
    require(len(system_messages) == 1 and type(system_messages[0]) is str, case_id + ".wire.system", "one frozen system prompt is required")
    compare(result["promptVersion"], "lesson_generation.SYSTEM_PROMPT@sha256:" + sha_bytes(system_messages[0].encode("utf-8")), case_id + ".wire.promptVersionSHA")
    for token in frozen["source"]["personalTokens"]:
        require(token not in users[0], case_id + ".wire.privacy", "fixed known personal identity appeared")
    original, candidate, applied, fixed = data["original-lesson.json"], data["candidate.json"], data["applied-result.json"], data["fixed-export-input.json"]
    revision = applied["currentRevision"]
    body_shape(original, case_id + ".originalBody")
    body_shape(revision["data"], case_id + ".appliedBody")
    selected = data["selected-fields.json"]
    require(type(selected) is list and selected and len(selected) == len(set(selected)) and set(selected) <= AI_FIELDS, case_id + ".selectedFields", "must be unique selected whole AI fields")
    compare(selected, spec["selectedFields"], case_id + ".handwrittenSelectedFields")
    compare(revision["selectedFields"], selected, case_id + ".appliedSelectedFields")
    compare(candidate["lessonPlanId"], frozen["lessonPlanId"], case_id + ".candidate.lessonPlanId")
    compare(candidate["baseRevisionId"], frozen["baseRevisionId"], case_id + ".candidate.baseRevisionId")
    compare(candidate["baseServerRevision"], frozen["baseServerRevision"], case_id + ".candidate.baseServerRevision")
    compare(candidate["modelFingerprint"], result["modelFingerprint"], case_id + ".modelFingerprint")
    compare(frozen["durationMinutes"], spec["durationMinutes"], case_id + ".durationMinutes")
    budget = candidate["budget"]
    compare(budget["durationMinutes"], spec["durationMinutes"], case_id + ".budget.durationMinutes")
    stages = budget["stages"]
    require(type(stages) is list and bool(stages), case_id + ".budget.stages", "complete stages required")
    require(all(type(x["minutes"]) is int and x["minutes"] > 0 for x in stages), case_id + ".budget.minutes", "positive exact integer minutes required")
    compare(sum(x["minutes"] for x in stages), spec["durationMinutes"], case_id + ".budget.totalMinutes")
    compare([x["minutes"] for x in stages], spec["stageMinutes"], case_id + ".budget.handwrittenStageMinutes")
    compare(set(x["phase"] for x in stages), {"introduction", "exploration", "practice", "conclusion"}, case_id + ".budget.fourPhases")
    compare([x["processId"] for x in stages], [x["id"] for x in candidate["patch"]["process"]], case_id + ".budget.processIdentity")
    knowledge_aliases = set(frozen["source"]["knowledgeAliases"])
    evidence_aliases = {x["alias"] for x in frozen["source"]["evidence"]}
    used = set()
    for stage in stages:
        for key, allowed in (("knowledgeAliases", knowledge_aliases), ("evidenceAliases", evidence_aliases)):
            require(type(stage[key]) is list and bool(stage[key]) and len(stage[key]) == len(set(stage[key])) and set(stage[key]) <= allowed, case_id + ".budget." + key, "nonempty unique frozen aliases required")
        used.update(stage["knowledgeAliases"])
    compare(used, knowledge_aliases, case_id + ".budget.targetKnowledgeCoverage")
    compare(revision["acceptedProposalId"], candidate["proposalId"], case_id + ".acceptedProposalId")
    for key in BODY_FIELDS:
        compare(revision["data"][key], candidate["patch"][key] if key in selected else original[key], case_id + ".wholeFields." + key)
    compare(revision["contextSnapshot"], frozen["contextSnapshot"], case_id + ".contextSnapshot")
    compare(candidate["generationSource"]["scopeSnapshot"], frozen["scopeSnapshot"], case_id + ".candidate.scope")
    compare(candidate["generationSource"]["evidenceRefs"], frozen["evidenceRefs"], case_id + ".candidate.evidenceRefs")
    compare(fixed["data"], revision["data"], case_id + ".export.completeBody")
    compare(fixed["context"], revision["contextSnapshot"], case_id + ".export.completeContext")
    compare(fixed["revisionId"], applied["currentRevisionId"], case_id + ".export.fixedRevision")
    compare(fixed["lessonPlanId"], frozen["lessonPlanId"], case_id + ".export.lessonPlanId")
    compare(fixed["sourceLabel"], "后台固定修订 " + fixed["revisionId"], case_id + ".export.sourceLabel")
    compare(export["fixedExportInputSHA"], sha_file(directory / "fixed-export-input.json"), case_id + ".export.fixedInputSHA")
    docx_key = args.artifact_docx_prefix.rstrip("/") + "/" + case_id + ".docx"
    require(docx_key in artifacts, docx_key, "missing frozen actual export SHA", "MISSING_HASH")
    docx = docx_check(args.docx_root / (case_id + ".docx"), fixed["data"], export, fixed, binding, artifacts[docx_key])
    return {"caseId": case_id, "caseHash": result["caseHash"], "technicalStructure": "PASS", "docxStructure": docx, "sourceBindingCheck": "PASS_FROZEN_FULL_ROW_CANONICAL_AND_IDENTITY", "physicalSourceCheck": "PASS_READ_ONLY_FOUR_CATALOGS_AND_BLOB_BYTES" if args.source_mode == "readonly-catalogs" else "not_run_source_temp_unavailable", "teacherQuality": "teacher_review_pending", "liveRun": "not_run_user_offline_only", "docxSHA": export["fileSHA"]}


def aggregate(args):
    manifest = checked_json(args.case_manifest, args.case_manifest_sha)
    known = known_case_ids(manifest)
    scope = strict_json(args.scope)
    selected = selection_scope(scope, known)
    artifact_manifest = checked_json(args.artifact_manifest, args.artifact_manifest_sha)
    artifacts = artifact_manifest.get("artifactFiles", artifact_manifest.get("frozenB6ArtifactFiles"))
    require(type(artifacts) is dict and bool(artifacts), "artifactManifest", "a frozen artifact SHA map is required")
    summary = strict_json(args.summary)
    exports = strict_json(args.docx_manifest)
    results = exact_ids(summary.get("results"), selected, "summary.results")
    export_records = exact_ids(exports.get("records"), selected, "docxManifest.records")
    compare(summary.get("caseCount"), len(selected), "summary.caseCount")
    compare(exports.get("caseCount"), len(selected), "docxManifest.caseCount")
    seed = frozen_file(args.seed, args.artifact_seed_path, artifacts)
    specs = {x["caseId"]: x for x in manifest["cases"]}
    checked = []
    with contextlib.ExitStack() as stack:
        if args.source_mode == "readonly-catalogs":
            db = readonly_sources(seed, args.data_root, stack)
        else:
            db = {key: None for key in ("catalog", "knowledge", "question_bank", "teaching")}
            compare(Path(seed["dataRoot"]).resolve(), args.data_root.resolve(), "seed.dataRoot")
        for case_id in selected:
            checked.append(check_case(case_id, specs[case_id], results[case_id], export_records[case_id], args, artifacts, db, seed))
    return {
        "status": "PASS_COMPLETE_SELECTED_SET",
        "expectedCaseCount": len(selected),
        "checkedCaseCount": len(checked),
        "technicalStructurePassed": sum(x["technicalStructure"] == "PASS" for x in checked),
        "docxStructurePassed": sum(x["docxStructure"]["status"] == "PASS" for x in checked),
        "unrunCaseIds": [x for x in known if x not in selected],
        "caseManifestSHA": args.case_manifest_sha,
        "artifactManifestSHA": args.artifact_manifest_sha,
        "scopeSHA": sha_bytes(canonical(scope)),
        "results": checked,
        "sourceMode": args.source_mode,
        "sourceBindingCheck": "PASS_FROZEN_FULL_ROW_CANONICAL_AND_IDENTITY",
        "physicalSourceCheck": "PASS_READ_ONLY_FOUR_CATALOGS_AND_BLOB_BYTES" if args.source_mode == "readonly-catalogs" else "not_run_source_temp_unavailable",
        "sourceAccess": "stdlib SQLite mode=ro/query_only and owned TEMP Blob bytes; no migration" if args.source_mode == "readonly-catalogs" else "frozen case-bound-v3 bytes pinned by explicit artifact manifest SHA; no database or Blob access; prior physical proofs referenced only",
        "humanScores": None,
        **offline_status(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case-manifest", "artifact-manifest", "scope", "summary", "cases-root", "docx-manifest", "docx-root", "seed", "data-root", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("case-manifest-sha", "artifact-manifest-sha", "artifact-case-prefix", "artifact-docx-prefix", "artifact-seed-path"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--source-mode", choices=("frozen-source-binding", "readonly-catalogs"), required=True)
    args = parser.parse_args(argv)
    try:
        create_output(args.output_dir)
    except CheckError as error:
        print(json.dumps({"status": "FAIL", "error": error.as_dict(), **offline_status()}, ensure_ascii=False))
        return 2
    try:
        result, exit_code = aggregate(args), 0
    except (CheckError, OSError, KeyError, TypeError, IndexError, sqlite3.Error, ValueError) as error:
        detail = error.as_dict() if isinstance(error, CheckError) else {"field": "evidence", "reason": "missing, malformed or unreadable evidence", "code": "INVALID_EVIDENCE"}
        result, exit_code = {"status": "FAIL_NO_PASS_PUBLISHED", "error": detail, "technicalStructure": "fail", "docxStructure": "fail_or_unchecked", **offline_status()}, 2
    result.update({"pid": os.getpid(), "at": datetime.now().astimezone().isoformat(), "exitCode": exit_code})
    write_json(args.output_dir / "RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
