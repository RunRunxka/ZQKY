"""B4-V00-A independent probe. Execute only after CTRL freezes these QA sources.

Fixture code supplies real databases and the real job engine, never expectations.
The only faulty output mutations are in literal_oracle.py response deep copies.
Runtime fault injections below wrap owned service/repository instances and retain
their original implementations; no product file or production aggregate changes.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import sqlite3
import sys
import subprocess
import time
import traceback
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literal_oracle import (CLASSES, EVIDENCE, NOTE, STUDENTS, base_packet, class_rows,
                            equal, evidence_rows, reject_wrong_outputs, student_rows)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PARSER = argparse.ArgumentParser()
PARSER.add_argument("--candidate", required=True)
PARSER.add_argument("--data-root", required=True)
PARSER.add_argument("--output", required=True)
ARGS = PARSER.parse_args()
ROOT = Path(ARGS.data_root).resolve()
OUT = Path(ARGS.output).resolve()
OUT.mkdir(exist_ok=False)
CHECKS = []
HTTP_COUNT = 0


def dump(name, value):
    path = OUT / (name + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def ms(start):
    return round((time.perf_counter() - start) * 1000, 3)


def candidate_identity(phase):
    candidate = Path(ARGS.candidate).resolve()
    manifest = json.loads(candidate.read_text(encoding="utf-8-sig"))
    checked, drift = {}, []
    for group in ("files", "executableQaFiles", "sharedContractFiles"):
        entries = manifest.get(group, {})
        if not isinstance(entries, dict):
            raise AssertionError("candidate hash map shape: " + group)
        for rel, expected in entries.items():
            path = REPO / rel
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            checked[rel] = digest
            if digest != expected:
                drift.append({"path": rel, "expected": expected, "actual": digest})
    env_path = REPO / "apps/web/next-env.d.ts"
    env_sha = hashlib.sha256(env_path.read_bytes()).hexdigest()
    if env_sha != manifest["nextEnvSHA256"]:
        drift.append({"path": "apps/web/next-env.d.ts", "expected": manifest["nextEnvSHA256"], "actual": env_sha})
    value = {"phase": phase, "candidatePath": str(candidate), "version": manifest["version"],
             "candidateSha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
             "sourceCount": manifest["count"], "executableQaCount": manifest["executableQaCount"],
             "checkedCount": len(checked), "drift": drift, "checked": checked, "nextEnvSha256": env_sha}
    dump("candidate-" + phase, value)
    equal(drift, [], "frozen candidate drift " + phase)
    return value


def enforce_outer_environment():
    # This executes BEFORE sys.path/app/fixture imports, including app.main.
    expected = {"ZQKY_ENV": "test", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1", "ZQKY_QDRANT_URL": "http://127.0.0.1:16333",
                "ZQKY_EMBEDDING_BASE_URL": "http://127.0.0.1:9"}
    for key, value in expected.items():
        equal(os.environ.get(key), value, "outer environment " + key)
    equal(Path(os.environ["ZQKY_DATA_DIR"]).resolve(), ROOT / "runtime", "outer fresh DATA_DIR")
    source = Path(os.environ["ZQKY_TEXTBOOK_SOURCE_DIR"]).resolve()
    equal(source, ROOT / "empty-source", "outer empty source")
    equal(list(source.iterdir()), [], "empty textbook source")
    if ROOT.parent != Path(os.environ["TEMP"]).resolve() or not ROOT.name.startswith("zqky-b4-v00-a-"):
        raise AssertionError("data root must be a new owned TEMP child")
    equal(list((ROOT / "runtime").iterdir()), [], "fresh isolated runtime")
    dump("outer-environment", {**expected, "ZQKY_DATA_DIR": str(ROOT / "runtime"),
                               "ZQKY_TEXTBOOK_SOURCE_DIR": str(source), "credentialsFile": None,
                               "beforeApplicationImport": True, "pid": os.getpid(), "argv": sys.argv})


def scene(name, **kwargs):
    from tests.analysis_support import AnalysisScene
    path = ROOT / name
    path.mkdir(exist_ok=False)
    return AnalysisScene(path, **kwargs)


def request(score="score-r", ids=None, submission="independent"):
    from app.contracts.b4 import AnalysisCreateRequest
    return AnalysisCreateRequest(submissionId=submission, scoreRevisionId=score,
                                 selectedParticipantIds=ids or ["p000", "p001", "p002", "p003"], ruleCode="any_loss_v1")


def wire(model):
    return model.model_dump(by_alias=True, mode="json")


async def ready(s, payload=None):
    receipt = await s.service.create_run("assessment", payload or request())
    job = await s.engine.run_job("teaching", receipt.job.job_id, s.service.execute_job)
    equal(job.state, "succeeded", "real job terminal state")
    return receipt


def rows(s, rid, kind, **filters):
    result = s.service.list_report_rows(rid, kind, limit=200, **filters)
    return [wire(r) for r in result.items]


def packet(s, rid):
    return {"run": wire(s.service.get_run(rid)), **{k: rows(s, rid, k) for k in ("classes", "students", "evidence")}}


def http(client, method, url, *, status=200, code=None, field=None, **kwargs):
    global HTTP_COUNT
    response = getattr(client, method)(url, **kwargs)
    HTTP_COUNT += 1
    try:
        body = response.json()
    except ValueError:
        body = {"rawText": response.text}
    dump(f"http/{HTTP_COUNT:04d}", {"method": method.upper(), "url": url, "request": kwargs,
                                  "status": response.status_code, "body": body})
    equal(response.status_code, status, f"HTTP {method} {url}")
    if code is not None:
        equal(body["code"], code, "error code")
        for required in ("code", "message", "requestId", "retryable"):
            if required not in body:
                raise AssertionError("missing error-envelope field " + required)
        if not body["message"] or not body["requestId"]:
            raise AssertionError("empty HTTP error envelope identity/message")
    if field is not None:
        equal(body["details"]["issues"][0]["field"], field, "error field location")
    return body


def app_error(fn, code):
    from app.core.exceptions import AppError
    try:
        fn()
    except AppError as error:
        equal(error.code, code, "AppError code")
        return {"code": error.code, "status": error.status_code, "message": str(error)}
    raise AssertionError("expected AppError " + code)


def sql_error(s, sql, args=(), text="IMMUTABLE_REVISION"):
    try:
        with s.catalog.write_transaction() as conn:
            conn.execute(sql, args)
    except sqlite3.IntegrityError as error:
        if text not in str(error):
            raise AssertionError(f"wrong SQL rejection {sql}: {error}") from error
        return {"sql": sql, "args": args, "error": str(error)}
    raise AssertionError("sealed SQL accepted: " + sql)


def new_fixed_score(s, *, changes=None, participant_changes=None, extra_attempt=False):
    """Independent legal new history: confirm through unchanged production gate."""
    from app.core.sqlite import now_iso
    with s.catalog.write_transaction() as conn:
        prior = conn.execute("SELECT * FROM score_revisions WHERE id='score-r'").fetchone()
        people = json.loads(prior["participant_snapshot_json"])
        cells = [dict(row) for row in conn.execute("SELECT * FROM student_item_scores WHERE score_revision_id='score-r'")]
        if participant_changes:
            for person in people:
                person.update(participant_changes.get(person["participantId"], {}))
        if extra_attempt:
            repeated = {**people[0], "participantId": "p-repeat", "attemptNo": 2}
            people.append(repeated)
            conn.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attempt_no,attendance,name_snapshot,student_no_snapshot) VALUES('p-repeat','assessment','s000','class',2,'present','A','00000')")
            cells += [{**c, "participant_id": "p-repeat"} for c in cells if c["participant_id"] == "p000"]
        conn.execute("INSERT INTO score_revisions(id,assessment_id,version,participant_snapshot_json,item_snapshot_json) VALUES('score-r2','assessment',2,?,?)",
                     (json.dumps(people, ensure_ascii=False), prior["item_snapshot_json"]))
        for cell in cells:
            key = (cell["participant_id"], cell["item_id"])
            if changes and key in changes:
                cell["status"], cell["score_units"] = changes[key]
            conn.execute("INSERT INTO student_item_scores VALUES('score-r2',?,?,?,?,?,?)",
                         (cell["assessment_id"], cell["paper_revision_id"], cell["participant_id"], cell["item_id"], cell["score_units"], cell["status"]))
        conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at=? WHERE id='score-r2'", (now_iso(),))
    return "score-r2"


async def base_http_and_wrong_output_oracle():
    s = scene("literal-base")
    with s.http_client() as client:
        create_url = "/api/v1/assessments/assessment/analysis-runs"
        body = wire(request())
        first = http(client, "post", create_url, json=body, status=202)
        equal((first["job"]["state"], first["job"]["result"], first["job"]["error"]), ("queued", None, None), "accept receipt")
        url = "/api/v1/analysis-runs/" + first["runId"]
        for kind in ("classes", "students", "evidence", "notes"):
            http(client, "get", url + "/" + kind, status=409, code="REPORT_NOT_READY")
        equal(http(client, "get", url)["reportReady"], False, "pending metadata")
        replay = http(client, "post", create_url, json={**body, "selectedParticipantIds": list(reversed(body["selectedParticipantIds"]))}, status=202)
        equal((replay["runId"], replay["job"]["jobId"], replay["inputHash"], replay["replayed"]),
              (first["runId"], first["job"]["jobId"], first["inputHash"], True), "same submission replay")
        http(client, "post", create_url, json={**body, "selectedParticipantIds": ["p000"]}, status=409, code="SUBMISSION_CONFLICT")
        same_input = http(client, "post", create_url, json={**body, "submissionId": "other-input-reuse"}, status=202)
        equal((same_input["runId"], same_input["reused"]), (first["runId"], True), "fixed input reuse")
        equal((s.count("analysis_runs"), s.count("workflow_jobs"), len(s.engine.accepted)), (1, 1, 1), "no duplicate task")
        actual_job = await s.engine.run_job("teaching", first["job"]["jobId"], s.service.execute_job)
        equal(actual_job.state, "succeeded", "actual execution")
        actual = {"run": http(client, "get", url)}
        for kind, total in (("classes", 2), ("students", 8), ("evidence", 12)):
            accumulated = []
            for offset in range(0, total, 5):
                page = http(client, "get", f"{url}/{kind}?limit=5&offset={offset}")
                equal((page["total"], page["offset"], page["limit"]), (total, offset, 5), "page identity")
                accumulated.extend(page["items"])
            actual[kind] = accumulated
        base_packet(actual, s.rich)
        dump("literal-base-full-packet", actual)
        dump("oracle-rejected-wrong-outputs", reject_wrong_outputs(actual, s.rich))
        for query, expected_total in (("knowledgePointId=k1", 8), ("knowledgePointId=k2", 8),
                                      ("participantId=p003", 3), ("classId=class", 12),
                                      ("participantId=p003&knowledgePointId=k1", 2)):
            equal(http(client, "get", url + "/evidence?" + query)["total"], expected_total, "filtered evidence total")
        for field in ("participantId", "classId", "knowledgePointId"):
            http(client, "get", url + "/evidence?" + field + "=foreign", status=422,
                 code="ANALYSIS_FILTER_INVALID", field=field)
        for query in ("limit=0", "limit=201", "offset=-1"):
            http(client, "get", url + "/evidence?" + query, status=422)
        equal(http(client, "get", url + "/evidence?offset=12")["items"], [], "page past end")
        for query, expected_total in (("assessmentId=assessment&scoreRevisionId=score-r", 1),
                                      ("assessmentId=foreign", 0), ("scoreRevisionId=foreign", 0)):
            equal(http(client, "get", "/api/v1/analysis-runs?" + query)["total"], expected_total, "history filter")
        http(client, "get", "/api/v1/analysis-runs/foreign", status=404, code="ANALYSIS_NOT_FOUND")
        raw_note = "  先保留原备注\n第二行：零分需要确认。  "
        note_body = {"submissionId": "raw-note", "participantId": "p003", "knowledgePointId": "k1", "note": raw_note}
        note = http(client, "post", url + "/notes", json=note_body, status=201)
        equal(note["note"], raw_note, "raw whitespace/newlines preserved")
        note_replay = http(client, "post", url + "/notes", json=note_body, status=201)
        equal((note_replay["noteId"], note_replay["replayed"]), (note["noteId"], True), "note replay")
        http(client, "post", url + "/notes", json={**note_body, "note": "不同内容"}, status=409, code="SUBMISSION_CONFLICT")
        http(client, "post", url + "/notes", json={**note_body, "submissionId": "blank", "note": "  \n "}, status=422, code="INVALID_REQUEST", field="note")
        http(client, "post", url + "/notes", json={**note_body, "submissionId": "foreign-note", "participantId": "foreign"}, status=422, code="ANALYSIS_FILTER_INVALID", field="participantId")
        equal(http(client, "get", url + "/notes")["total"], 1, "exactly one append-only note")
        base_packet(packet(s, first["runId"]), s.rich)
        client.app.state.analysis_service = None
        absent = http(client, "get", url, status=503, code="SERVICE_UNAVAILABLE")
        equal(absent["retryable"], True, "absent service truthful envelope")
    await s.engine.shutdown()
    return {"literalRows": {"students": 8, "classes": 2, "evidence": 12}, "wrongOutputVariants": 14}


async def edge_states_and_explicit_retake():
    results = []
    # Extra loss + missing is independent of the original four-person fixture.
    s = scene("loss-plus-missing")
    new_fixed_score(s, changes={("p000", "i000"): ("recorded", 100), ("p000", "i001"): ("missing", None)})
    receipt = await ready(s, request("score-r2", ["p000"]))
    expected_students = {("p000", "k1"): ("needs_consolidation", True, 1, (1, 1, 0, 0), None),
                         ("p000", "k2"): ("incomplete", True, 1, (1, 1, 0, 0), None)}
    student_rows(rows(s, receipt.run_id, "students"), expected_students)
    class_rows(rows(s, receipt.run_id, "classes"), {("class", "k1"): (1, 1, 1, 1, 0, 0, 1, 1, 1.0),
                                                  ("class", "k2"): (1, 1, 0, 1, 0, 0, 0, 1, 0.0)})
    evidence_rows(rows(s, receipt.run_id, "evidence"), s.rich, receipt.run_id, score_revision="score-r2",
                  expected={("p000", "i000"): ("recorded", 100), ("p000", "i001"): ("missing", None), ("p000", "i002"): ("recorded", 500)})
    dump("edge-loss-plus-missing", packet(s, receipt.run_id))
    results.append({"case": "loss-plus-missing", "evidence": 3, "totalScoreUnits": None})
    await s.engine.shutdown()
    for label, state, person in (("all-missing", "missing", "p001"), ("all-exempt", "exempt", "p002")):
        s = scene(label)
        updates = {person: {"attendance": "exempt"}} if state == "exempt" else None
        new_fixed_score(s, changes={(person, item): (state, None) for item in ("i000", "i001", "i002")}, participant_changes=updates)
        receipt = await ready(s, request("score-r2", [person]))
        counts = (0, 2, 0, 0) if state == "missing" else (0, 0, 0, 2)
        expected_students = {(person, "k1"): ("no_evidence", True, 0, counts, None),
                             (person, "k2"): ("no_evidence", True, 0, counts, None)}
        student_rows(rows(s, receipt.run_id, "students"), expected_students, check_people=state != "exempt")
        class_rows(rows(s, receipt.run_id, "classes"), {("class", "k1"): (1, 0, 0, 1, 1, 0, 0, 0, None),
                                                      ("class", "k2"): (1, 0, 0, 1, 1, 0, 0, 0, None)})
        if state == "exempt":
            for row in rows(s, receipt.run_id, "students"):
                equal(row["participant"]["attendance"], "exempt", "fixed exempt attendance")
        evidence_rows(rows(s, receipt.run_id, "evidence"), s.rich, receipt.run_id, score_revision="score-r2",
                      expected={(person, item): (state, None) for item in ("i000", "i001", "i002")}, check_people=state != "exempt")
        dump("edge-" + label, packet(s, receipt.run_id))
        results.append({"case": label, "denominator": 0, "ratio": None, "evidence": 3})
        await s.engine.shutdown()
    s = scene("explicit-retake")
    new_fixed_score(s, changes={("p-repeat", "i001"): ("recorded", 300)}, extra_attempt=True)
    with s.http_client() as client:
        url = "/api/v1/assessments/assessment/analysis-runs"
        body = wire(request("score-r2", ["p000", "p-repeat"], "bad-retake"))
        failure = http(client, "post", url, json=body, status=422, code="ANALYSIS_SELECTION_INVALID", field="selectedParticipantIds[1]")
        equal(failure["details"]["issues"][0]["code"], "DUPLICATE_STUDENT_ATTEMPT", "two attempts rejected")
        http(client, "post", url, json=wire(request("score-r2", ["p000", "p000"], "duplicate-id")), status=422, code="ANALYSIS_SELECTION_INVALID", field="selectedParticipantIds[1]")
        http(client, "post", url, json=wire(request("score-r2", ["foreign"], "foreign-id")), status=422, code="ANALYSIS_SELECTION_INVALID", field="selectedParticipantIds[0]")
        equal((s.count("analysis_runs"), s.count("workflow_jobs"), s.count("command_submissions")), (0, 0, 0), "invalid selections make no writes")
        receipt = await ready(s, request("score-r2", ["p-repeat"], "explicit-second-attempt"))
        student_rows(rows(s, receipt.run_id, "students"), {("p-repeat", "k1"): ("full_credit", False, 2, (2, 0, 0, 0), 1000),
                    ("p-repeat", "k2"): ("full_credit", False, 2, (2, 0, 0, 0), 1000)}, check_people=False)
        for row in rows(s, receipt.run_id, "students"):
            equal((row["participant"]["studentId"], row["participant"]["attemptNo"]), ("s000", 2), "explicit selected retake")
        evidence_rows(rows(s, receipt.run_id, "evidence"), s.rich, receipt.run_id, score_revision="score-r2",
                      expected={("p-repeat", "i000"): ("recorded", 200), ("p-repeat", "i001"): ("recorded", 300), ("p-repeat", "i002"): ("recorded", 500)}, check_people=False)
        snapshot = wire(s.service.get_run(receipt.run_id))["selectionSnapshot"]
        equal(snapshot, {"selectedParticipantIds": ["p-repeat"], "uniqueStudentCount": 1, "participantCount": 1,
              "leafCount": 3, "stateCounts": {"recorded": 3, "missing": 0, "absent": 0, "exempt": 0}}, "explicit retake snapshot")
        dump("edge-retake", packet(s, receipt.run_id))
    await s.engine.shutdown()
    results.append({"case": "explicit-retake", "selected": ["p-repeat"], "totalScoreUnits": 1000})
    return results


async def multiple_classes_and_history():
    from app.repositories.knowledge.catalog import KnowledgeCatalog
    s = scene("multi-class-history")
    # Two different fixed classes on a newly confirmed history, not on old snapshots.
    with s.catalog.write_transaction() as conn:
        conn.execute("INSERT INTO classes(id,code,name,school_year,grade_id) VALUES('second','second','新二班','2026','g')")
        conn.execute("INSERT INTO assessment_classes VALUES('assessment','second')")
        conn.execute("UPDATE assessment_participants SET class_id='second' WHERE id IN('p001','p003')")
    new_fixed_score(s, participant_changes={"p001": {"classId": "second"}, "p003": {"classId": "second"}})
    old = await ready(s, request(submission="old-score"))
    old_packet = packet(s, old.run_id)
    base_packet(old_packet, s.rich)
    current = await ready(s, request("score-r2", submission="two-classes"))
    expected = {("class", "k1"): (2, 1, 1, 1, 1, 0, 1, 1, 1.0),
                ("class", "k2"): (2, 1, 1, 1, 1, 0, 1, 1, 1.0),
                ("second", "k1"): (2, 2, 1, 0, 0, 1, 1, 2, 0.5),
                ("second", "k2"): (2, 2, 0, 1, 0, 1, 0, 2, 0.0)}
    class_rows(rows(s, current.run_id, "classes"), expected)
    with s.http_client() as client:
        url = "/api/v1/analysis-runs/" + current.run_id
        equal(http(client, "get", url + "/evidence?classId=second")["total"], 6, "second class evidence")
        equal(http(client, "get", url + "/students?classId=class")["total"], 4, "first class students")
        mismatch = http(client, "get", url + "/evidence?classId=class&participantId=p001", status=422, code="ANALYSIS_FILTER_INVALID", field="participantId")
        equal(mismatch["details"]["issues"][0]["code"], "CLASS_MISMATCH", "mismatched identity")
        selected_class = http(client, "get", url + "/classes?participantId=p001")["items"]
        class_rows(selected_class, {key: value for key, value in expected.items() if key[0] == "second"})
    # Populate a real knowledge database before its current name/revision/archive changes.
    knowledge = KnowledgeCatalog(s.root / "knowledge.sqlite3")
    knowledge.migrate()
    with knowledge.write_transaction() as conn:
        conn.execute("INSERT INTO subjects(id,code,name) VALUES('math','math','数学')")
        for kid in ("k1", "k2"):
            conn.execute("INSERT INTO knowledge_points(id,subject_id,code) VALUES(?,'math',?)", (kid, kid))
            conn.execute("INSERT INTO knowledge_point_revisions(id,knowledge_point_id,version,name) VALUES(?,?,1,?)", (kid + "-r", kid, "固定" + kid))
            conn.execute("UPDATE knowledge_points SET current_revision_id=? WHERE id=?", (kid + "-r", kid))
        conn.execute("INSERT INTO knowledge_point_revisions(id,knowledge_point_id,version,name) VALUES('k1-new','k1',2,'当前改名')")
        conn.execute("UPDATE knowledge_points SET current_revision_id='k1-new',status='archived',revision=revision+1 WHERE id='k1'")
    with s.catalog.write_transaction() as conn:
        conn.execute("UPDATE students SET name='当前学生改名',student_no='当前新学号' WHERE id='s000'")
        conn.execute("UPDATE classes SET name='当前班级改名' WHERE id='class'")
        conn.execute("UPDATE papers SET title='当前原卷改名' WHERE id='paper'")
        conn.execute("INSERT INTO class_memberships(id,class_id,student_id,joined_on) VALUES('transfer','second','s000','2026-10-02')")
        conn.execute("UPDATE assessments SET active_score_revision_id='score-r2' WHERE id='assessment'")
    after = packet(s, old.run_id)
    base_packet(after, s.rich)
    equal(after, old_packet, "old report exact same facts after live mutations")
    replay = await s.service.create_run("assessment", request(submission="old-score"))
    equal((replay.run_id, replay.replayed), (old.run_id, True), "old submission after active change")
    dump("historical-before", old_packet)
    dump("historical-after", after)
    dump("multi-class-full-packet", packet(s, current.run_id))
    with knowledge.read_connection() as conn:
        dump("historical-live-knowledge", [dict(row) for row in conn.execute("SELECT * FROM knowledge_points")])
    knowledge.close()
    await s.engine.shutdown()
    return {"fixedClassRows": 4, "historyIdentical": True, "mutations": ["student-name/no", "class-name", "transfer", "KP-current-revision/archive", "paper-title", "active-score"]}


async def damaged_sources_and_atomic_create():
    results = []
    for label, expected_code in (("matrix-missing", "ANALYSIS_SOURCE_CORRUPT"), ("asset-corrupt", "ASSET_CORRUPT"), ("asset-missing", "ASSET_MISSING")):
        s = scene(label)
        score = "score-r"
        if label == "matrix-missing":
            score = s.new_score(direct_bad=True)
        else:
            path = s.assets.path_of(s.image.blob_key)
            if label == "asset-corrupt":
                path.write_bytes(b"independent-owned-corrupt-image")
            else:
                # Move only this explicitly owned single test blob; retain its bytes.
                path.rename(path.with_name(path.name + ".missing-fixture-original"))
        with s.http_client() as client:
            failure = http(client, "post", "/api/v1/assessments/assessment/analysis-runs", json=wire(request(score)), status=500, code=expected_code)
            equal((s.count("analysis_runs"), s.count("workflow_jobs"), s.count("command_submissions")), (0, 0, 0), "damaged source has no half rows")
        results.append({"case": label, "envelope": failure, "halfRows": 0})
        await s.engine.shutdown()
    s = scene("create-tx-fault")
    original = s.service.repo.create_in
    def fail_after_insert(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("owned QA fault after analysis insert before command receipt")
    s.service.repo.create_in = fail_after_insert
    try:
        await s.service.create_run("assessment", request())
    except RuntimeError as error:
        equal(str(error), "owned QA fault after analysis insert before command receipt", "specific owned create fault")
    else:
        raise AssertionError("create fault unexpectedly succeeded")
    finally:
        s.service.repo.create_in = original
    equal((s.count("analysis_runs"), s.count("workflow_jobs"), s.count("command_submissions")), (0, 0, 0), "create transaction rolls back job/run/receipt")
    receipt = await ready(s)
    base_packet(packet(s, receipt.run_id), s.rich)
    results.append({"case": "create-tx-fault", "halfRows": 0, "retryFullEvidence": 12})
    await s.engine.shutdown()
    return results


async def seal_all_children():
    s = scene("seal")
    receipt = await s.service.create_run("assessment", request())
    evidence = []
    for sql in ("UPDATE analysis_runs SET input_json='{}'", "UPDATE analysis_runs SET job_id='foreign'",
                "UPDATE analysis_runs SET selected_count=5", "DELETE FROM analysis_runs"):
        evidence.append(sql_error(s, sql))
    evidence.append(sql_error(s, "UPDATE analysis_runs SET report_ready=1,ready_at='2026-10-02'", text="ANALYSIS_PARTICIPANTS_INCOMPLETE"))
    job = await s.engine.run_job("teaching", receipt.job.job_id, s.service.execute_job)
    equal(job.state, "succeeded", "seal ready job")
    before = packet(s, receipt.run_id)
    base_packet(before, s.rich)
    # Every sealed child INSERT/UPDATE/DELETE; INSERT retains real row values and
    # triggers before uniqueness checks, so an unrelated FK violation is rejected.
    for table in ("analysis_participants", "analysis_item_snapshots", "analysis_student_results", "analysis_class_results", "analysis_evidence"):
        with s.catalog.read_connection() as conn:
            row = dict(conn.execute("SELECT * FROM " + table + " LIMIT 1").fetchone())
        columns = list(row)
        insert = f"INSERT INTO {table} ({','.join(columns)}) VALUES({','.join('?' for _ in columns)})"
        evidence.append(sql_error(s, insert, tuple(row.values())))
        evidence.append(sql_error(s, f"UPDATE {table} SET run_id=run_id"))
        evidence.append(sql_error(s, f"DELETE FROM {table}"))
    evidence.append(sql_error(s, "UPDATE analysis_runs SET report_ready=0,ready_at=NULL"))
    from app.contracts.b4 import NoteRequest
    note = s.service.add_note(receipt.run_id, NoteRequest(submissionId="seal-note", note="保留"))
    evidence.append(sql_error(s, "UPDATE analysis_teacher_notes SET note='overwrite' WHERE id=?", (note.note_id,)))
    evidence.append(sql_error(s, "DELETE FROM analysis_teacher_notes WHERE id=?", (note.note_id,)))
    equal(packet(s, receipt.run_id), before, "sealed reports unchanged after attempted writes")
    dump("seal-rejections", evidence)
    await s.engine.shutdown()
    return {"rejectedSqlWrites": len(evidence), "sealedChildren": 5, "reportUnchanged": True}


async def cancellation_and_publish_fault_retry():
    results = []
    s = scene("publish-tx-fault")
    receipt = await s.service.create_run("assessment", request())
    original = s.service.repo.publish_in
    def after_full_publish(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("owned QA full publish/ready fault before job completion")
    s.service.repo.publish_in = after_full_publish
    try:
        failed = await s.engine.run_job("teaching", receipt.job.job_id, s.service.execute_job)
    finally:
        s.service.repo.publish_in = original
    equal((failed.state, failed.error["code"]), ("failed", "JOB_FAILED"), "publish fault terminal")
    equal(s.service.get_run(receipt.run_id).report_ready, False, "publish fault never seals")
    tables = ("analysis_participants", "analysis_item_snapshots", "analysis_student_results", "analysis_class_results", "analysis_evidence")
    for table in tables:
        equal(s.count(table), 0, "publish fault rolls back " + table)
    with s.http_client() as client:
        url = "/api/v1/workflow-jobs/" + failed.job_id
        response = http(client, "post", url + "/retry", json={"domain": "teaching"})
        equal(response["state"], "queued", "real registered public retry")
        equal(s.engine.accepted[-1][3], False, "analysis never reserves model slot")
        succeeded = await s.engine.run_job("teaching", failed.job_id, s.service.execute_job)
        equal((succeeded.state, succeeded.attempt), ("succeeded", 2), "retry attempt identity")
        base_packet(packet(s, receipt.run_id), s.rich)
        http(client, "post", url + "/retry", json={"domain": "teaching"}, status=409, code="JOB_NOT_RETRYABLE")
    dump("publish-fault-terminal", wire(failed.view()))
    dump("publish-retry-terminal", wire(succeeded.view()))
    await s.engine.shutdown()
    results.append({"case": "publish-tx-fault", "allFiveChildrenRolledBack": True, "publicRetryAttempt": 2})
    s = scene("running-cancel")
    receipt = await s.service.create_run("assessment", request())
    entered, release = asyncio.Event(), asyncio.Event()
    async def delayed(frozen, context):
        outcome = await s.service.execute_job(frozen, context)
        entered.set()
        await release.wait()
        return outcome
    task = asyncio.create_task(s.engine.run_job("teaching", receipt.job.job_id, delayed))
    await asyncio.wait_for(entered.wait(), timeout=15)
    with s.http_client() as client:
        job_url = "/api/v1/workflow-jobs/" + receipt.job.job_id
        cancel = http(client, "post", job_url + "/cancel", json={"domain": "teaching"})
        equal(cancel["state"], "running", "public running cancel state")
        equal(s.store.cancel_requested(receipt.job.job_id), True, "running cancel flag persisted")
        release.set()
        cancelled = await asyncio.wait_for(task, timeout=15)
        equal(cancelled.state, "cancelled", "late outcome cancellation")
        equal(s.service.get_run(receipt.run_id).report_ready, False, "late outcome not ready")
        for table in tables:
            equal(s.count(table), 0, "cancelled has no " + table)
        replay = http(client, "post", "/api/v1/assessments/assessment/analysis-runs", json=wire(request()), status=202)
        equal((replay["replayed"], replay["runId"]), (True, receipt.run_id), "cancelled original submission does not spawn")
        equal(s.count("workflow_jobs"), 1, "cancel replay no second job")
        http(client, "post", job_url + "/retry", json={"domain": "teaching"})
        success = await s.engine.run_job("teaching", receipt.job.job_id, s.service.execute_job)
        equal((success.state, success.attempt), ("succeeded", 2), "cancel retry attempt")
        base_packet(packet(s, receipt.run_id), s.rich)
    await s.engine.shutdown()
    results.append({"case": "running-cancel", "latePublishRejected": True, "publicRetryAttempt": 2})
    return results


async def expired_and_original_attempt_cas():
    from app.services.jobs.engine import FrozenJob, JobContext
    clock = [datetime(2026, 10, 2, tzinfo=UTC)]
    s = scene("lease-cas", now=lambda: clock[0].isoformat().replace("+00:00", "Z"))
    receipt = await s.service.create_run("assessment", request())
    lease1 = s.store.claim(receipt.job.job_id)
    record1 = s.store.get(receipt.job.job_id)
    frozen1 = FrozenJob(record1.job_id, record1.domain, record1.kind, record1.attempt,
                        record1.frozen_input, record1.model_snapshot, record1.input_hash)
    outcome1 = await s.service.execute_job(frozen1, JobContext(s.store, record1.job_id, lease1))
    clock[0] += timedelta(seconds=91)
    expired = app_error(lambda: s.store.complete(record1.job_id, lease1, result=outcome1.result, publish=outcome1.publish), "LEASE_LOST")
    equal(s.count("analysis_evidence"), 0, "expired lease no evidence")
    equal(s.store.heartbeat(lease1), False, "expired heartbeat cannot renew")
    equal(s.store.reconcile_interrupted(), [record1.job_id], "only expired owned job reconciled")
    s.store.retry(record1.job_id)
    lease2 = s.store.claim(record1.job_id)
    equal(lease2.attempt, 2, "new attempt CAS")
    old = app_error(lambda: s.store.complete(record1.job_id, lease1, result=outcome1.result, publish=outcome1.publish), "LEASE_LOST")
    equal(s.count("analysis_evidence"), 0, "original attempt cannot publish into current attempt")
    equal(s.store.get(record1.job_id).state, "running", "stale attempt cannot overwrite new state")
    record2 = s.store.get(record1.job_id)
    frozen2 = FrozenJob(record2.job_id, record2.domain, record2.kind, record2.attempt,
                        record2.frozen_input, record2.model_snapshot, record2.input_hash)
    outcome2 = await s.service.execute_job(frozen2, JobContext(s.store, record2.job_id, lease2))
    s.store.complete(record2.job_id, lease2, result=outcome2.result, publish=outcome2.publish)
    base_packet(packet(s, receipt.run_id), s.rich)
    dump("lease-cas", {"expired": expired, "staleOriginalAttempt": old, "lease1": {"attempt": lease1.attempt, "token": lease1.token},
                       "lease2": {"attempt": lease2.attempt, "token": lease2.token}, "terminal": wire(s.store.get(record2.job_id).view())})
    await s.engine.shutdown()
    return {"expiredRejected": True, "originalAttemptRejected": True, "currentAttempt": 2, "evidence": 12}


async def scale_200_by_100_all_pages():
    from app.services.analysis.snapshot import read_facts
    from app.services.jobs.engine import JobOutcome
    timings = {}
    start = time.perf_counter()
    s = scene("scale-200x100", participant_count=200, leaf_count=100)
    timings["fixturePreparationMs"] = ms(start)
    payload = request(ids=s.participant_ids, submission="scale-20k")
    start = time.perf_counter()
    facts = read_facts(s.catalog, "assessment", payload, "local")
    timings["fixedSnapshotReadMs"] = ms(start)
    # Cold means first aggregate call in a NEW Python process, then same-input
    # warm call. Actual implementation results never enter the literal oracle.
    input_path = OUT / "scale-frozen-input.json"
    input_path.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    benchmark_path = OUT / "scale-compute-benchmark.json"
    child = subprocess.run([sys.executable, "-B", str(HERE / "benchmark_compute.py"),
                            str(input_path), str(benchmark_path)], text=True, encoding="utf-8",
                           capture_output=True, check=False, timeout=60)
    (OUT / "scale-benchmark.stdout.log").write_text(child.stdout, encoding="utf-8")
    (OUT / "scale-benchmark.stderr.log").write_text(child.stderr, encoding="utf-8")
    equal(child.returncode, 0, "separate cold/warm benchmark process exit")
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    timings["coldAggregateMs"] = benchmark["coldAggregateMs"]
    timings["warmAggregateMs"] = benchmark["warmAggregateMs"]
    original_publish = s.service.repo.publish_in
    def timed_publish(*args, **kwargs):
        start = time.perf_counter()
        try:
            return original_publish(*args, **kwargs)
        finally:
            timings["publishWithinLeaseTransactionMs"] = ms(start)
    s.service.repo.publish_in = timed_publish
    async def timed_executor(frozen, context):
        start = time.perf_counter()
        outcome = await s.service.execute_job(frozen, context)
        timings["executorHashCancellationAndComputeMs"] = ms(start)
        if not isinstance(outcome, JobOutcome):
            raise AssertionError("real executor outcome type")
        return outcome
    with s.http_client() as client:
        start = time.perf_counter()
        accepted = http(client, "post", "/api/v1/assessments/assessment/analysis-runs", json=wire(payload), status=202)
        timings["httpCreateAcceptanceMs"] = ms(start)
        start = time.perf_counter()
        job = await s.engine.run_job("teaching", accepted["job"]["jobId"], timed_executor)
        timings["jobClaimExecutorPublishCompleteMs"] = ms(start)
        equal(job.state, "succeeded", "scale actual job")
        equal(s.count("analysis_evidence"), 20000, "full scale DB evidence")
        equal(s.count("analysis_student_results"), 1000, "full scale student/KP rows")
        equal(s.count("analysis_class_results"), 5, "full scale class/KP rows")
        url = "/api/v1/analysis-runs/" + accepted["runId"]
        view = http(client, "get", url)
        equal(view["selectionSnapshot"], {"selectedParticipantIds": s.participant_ids, "uniqueStudentCount": 200,
              "participantCount": 200, "leafCount": 100, "stateCounts": {"recorded": 20000, "missing": 0, "absent": 0, "exempt": 0}}, "full scale selection")
        evidence_keys, evidence_ids, http_latencies = set(), set(), []
        start_all = time.perf_counter()
        for page_no in range(100):
            offset = page_no * 200
            start = time.perf_counter()
            page = http(client, "get", f"{url}/evidence?limit=200&offset={offset}")
            http_latencies.append(ms(start))
            equal((page["total"], page["offset"], page["limit"], len(page["items"])), (20000, offset, 200, 200), "scale page metadata")
            for row in page["items"]:
                pid, iid = row["participant"]["participantId"], row["itemId"]
                key = (pid, iid)
                if key in evidence_keys or row["evidenceId"] in evidence_ids:
                    raise AssertionError("overlapping scale pages")
                evidence_keys.add(key)
                evidence_ids.add(row["evidenceId"])
                pindex, iindex = int(pid[1:]), int(iid[1:])
                # Inputs are 100 identical one-point leaves; these expected scores
                # are fixture-pattern literals, independent of any-loss aggregation.
                equal((row["status"], row["scoreUnits"], row["maxScoreUnits"]), ("recorded", (100, 90, 80)[pindex % 3], 100), "scale fixed cell")
                equal(row["itemPath"], "Q" + str(iindex + 1), "scale fixed path")
                equal(row["knowledgePoints"][0]["knowledgePointId"], "k" + str(iindex % 5), "scale fixed KP")
                equal(row["content"]["stemBlocks"], s.rich["stemBlocks"], "scale whole rich stem")
                equal(row["content"]["answerBlocks"], s.rich["answerBlocks"], "scale whole answer")
                equal(row["sharedMaterials"], s.rich["sharedMaterials"], "scale material")
                equal(row["assets"], s.rich["assets"], "scale assets")
                equal(row["participant"]["className"], None, "scale className null")
                equal((row["runId"], row["scoreRevisionId"], row["paperRevisionId"]), (accepted["runId"], "score-r", "paper-r"), "scale provenance")
        timings["all100HttpEvidencePagesWithJsonReceiptAndOracleMs"] = ms(start_all)
        equal(evidence_keys, {(f"p{p:03d}", f"i{i:03d}") for p in range(200) for i in range(100)}, "all 20k keys")
        start = time.perf_counter()
        student_keys = set()
        for offset in range(0, 1000, 200):
            page = http(client, "get", f"{url}/students?limit=200&offset={offset}")
            equal(page["total"], 1000, "scale student total")
            for row in page["items"]:
                pid, kid = row["participant"]["participantId"], row["knowledgePoint"]["knowledgePointId"]
                key = (pid, kid)
                if key in student_keys:
                    raise AssertionError("duplicate scale student/KP")
                student_keys.add(key)
                expected_total = (10000, 9000, 8000)[int(pid[1:]) % 3]
                observation = "full_credit" if int(pid[1:]) % 3 == 0 else "needs_consolidation"
                equal((row["observation"], row["informationIncomplete"], row["expectedCount"], row["validCount"], row["totalScoreUnits"], row["totalMaxScoreUnits"]),
                      (observation, False, 20, 20, expected_total, 10000), "scale hand-pattern student/KP")
        equal(student_keys, {(f"p{p:03d}", "k" + str(k)) for p in range(200) for k in range(5)}, "all 1000 student/KP keys")
        classes = http(client, "get", url + "/classes?limit=200")
        equal((classes["total"], len(classes["items"])), (5, 5), "scale class coverage")
        for row in classes["items"]:
            # 200 participants: 67 full-credit and 133 with recorded loss.
            equal(tuple(row[k] for k in ("selectedCount", "validCount", "needsCount", "incompleteCount", "noEvidenceCount", "fullCreditCount", "numerator", "denominator", "ratio")),
                  (200, 200, 133, 0, 0, 67, 133, 200, 0.665), "scale class literal")
        equal(http(client, "get", url + "/evidence?knowledgePointId=k0")["total"], 4000, "scale KP filter")
        equal(http(client, "get", url + "/evidence?participantId=p199")["total"], 100, "scale participant filter")
        equal(http(client, "get", url + "/evidence?classId=class")["total"], 20000, "scale class filter")
        timings["remainingStudentClassAndFilterHttpWithOracleMs"] = ms(start)
        timings["evidencePageHttpWithJsonReceiptMs"] = http_latencies
    s.service.repo.publish_in = original_publish
    await s.engine.shutdown()
    dump("scale-timings", timings)
    # A3sec computational gate applies to cold/warm actual aggregate, not data
    # preparation, transactional publication, or 100 complete HTTP/JSON pages.
    if timings["coldAggregateMs"] >= 3000 or timings["warmAggregateMs"] >= 3000:
        raise AssertionError("3-second pure-computation target missed")
    return {"participants": 200, "leaves": 100, "evidence": 20000, "evidenceHttpPages": 100,
            "studentKnowledgeRows": 1000, "studentHttpPages": 5, "timings": timings, "computeUnder3Seconds": True,
            "timingLimit": "HTTP includes response validation, complete JSON evidence writes, and independent oracle."}


async def run_all():
    for fn in (base_http_and_wrong_output_oracle, edge_states_and_explicit_retake, multiple_classes_and_history,
               damaged_sources_and_atomic_create, seal_all_children, cancellation_and_publish_fault_retry,
               expired_and_original_attempt_cas, scale_200_by_100_all_pages):
        name = fn.__name__
        print("START " + name, flush=True)
        start = time.perf_counter()
        value = await fn()
        CHECKS.append({"case": name, "status": "passed", "elapsedMs": ms(start), "result": value})
        dump("checks-so-far", CHECKS)
        print("PASS " + name, flush=True)


if __name__ == "__main__":
    started = time.perf_counter()
    exit_code = 1
    failure = None
    try:
        enforce_outer_environment()
        before = candidate_identity("before")
        sys.path.insert(0, str(REPO / "apps/api"))
        from app.core.config import Settings
        settings = Settings.from_env()
        equal(settings.credentials_file, None, "credentials disabled before app.main")
        equal(settings.data_dir.resolve(), ROOT / "runtime", "Settings fresh runtime")
        dump("runtime-identity", {"python": sys.executable, "pythonVersion": sys.version,
              "platform": platform.platform(), "processor": platform.processor(), "logicalCpuCount": os.cpu_count(),
              "testClient": "real create_app + owned real service/JobEngine; no TCP listener", "credentialsFile": None,
              "candidate": before["version"]})
        asyncio.run(run_all())
        exit_code = 0
    except BaseException as error:
        failure = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        traceback.print_exc()
        dump("first-failure", failure)
    finally:
        try:
            after = candidate_identity("after")
        except BaseException as error:
            exit_code = 1
            if failure is None:
                failure = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
                dump("first-failure", failure)
        dump("result", {"status": "passed" if exit_code == 0 else "failed", "exitCode": exit_code,
                        "caseCount": len(CHECKS), "checks": CHECKS, "httpRequests": HTTP_COUNT,
                        "elapsedMs": ms(started), "firstFailure": failure,
                        "dataRoot": str(ROOT), "output": str(OUT), "listeningServicesStarted": 0})
        print("FINAL " + ("passed" if exit_code == 0 else "failed") + " cases=" + str(len(CHECKS)), flush=True)
    sys.exit(exit_code)
