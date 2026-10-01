"""V00-B2 · V7 独立探针：T30-b 施测（真实 T30-a 名单 + T40 原卷 链路）。

真装配 + 真 HTTP（TestClient）；不联网、不占端口。

覆盖：
  1. 真链路：名单导入（CSV）→ 确认建档/归属 → T40 原卷确认 → 施测创建；
  2. 闸门：draft/不存在卷 422；heldOn 非法 422；空名单；班级不存在/越范围/重复班级；
     学生不存在；客户端伪造姓名/学号字段被拒；
  3. 归属未覆盖 heldOn → 422 PARTICIPANT_CLASS_UNCONFIRMED（逐行定位）→ 带依据确认成功，
     且 class_memberships 逐行未变；
  4. 同学生跨班重复人工选定；人次唯一；补考新增且旧记录不变；批量回滚；
  5. 幂等重放（同 submissionId）；不同载荷 409；
  6. 学生改名/转班后快照不变；PATCH 施测 revision+1 与过期 409。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v7-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

RESULTS: list[dict] = []
TODAY = date.today()
HELD_ON = TODAY.isoformat()


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def error_of(response) -> tuple[int, str, dict]:
    body = response.json()
    error = body.get("error") or body
    return response.status_code, error.get("code"), error.get("details") or {}


def membership_rows(har) -> list[dict]:
    conn = har.db("teaching")
    try:
        return [dict(row) for row in conn.execute(
            "SELECT id, class_id, student_id, joined_on, left_on FROM class_memberships "
            "ORDER BY id")]
    finally:
        conn.close()


def participant_rows(har, assessment_id: str) -> list[dict]:
    conn = har.db("teaching")
    try:
        return [dict(row) for row in conn.execute(
            "SELECT id, student_id, class_id, attempt_no, attendance, name_snapshot, "
            "student_no_snapshot, class_confirmed, class_confirmation_note "
            "FROM assessment_participants WHERE assessment_id=? ORDER BY student_id, attempt_no",
            (assessment_id,))]
    finally:
        conn.close()


def digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v7-work-"))
    sample = S.build_sample_docx(work / "v00-sample.docx")
    har, _provider = S.new_harness("v7")
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")

    # ---------------------------------------------------------------- 1. 真链路
    state = S.prepare_ready_draft(har, sample, point_a=point_a, point_b=point_b)
    paper_id = state["paper_id"]
    paper_rev = har.client.get(f"/api/v1/papers/{paper_id}").json()
    confirmed = har.client.post(f"/api/v1/papers/{paper_id}/confirm", json={
        "expectedRevision": paper_rev["revision"], "submissionId": "v00-v7-confirm"})
    check("V7.1 T40 原卷确认成功（真实链路第一步）",
          confirmed.status_code == 200 and confirmed.json()["state"] == "confirmed",
          f"{confirmed.status_code} {confirmed.text[:160]}")
    paper_revision_id = confirmed.json()["paperRevisionId"]

    klass = har.client.post("/api/v1/classes", json={
        "code": "V00C7", "name": "高一(7)班", "schoolYear": "2026-2027", "gradeId": "senior-1"})
    check("V7.2 建班成功", klass.status_code == 201, f"{klass.status_code}")
    class_id = klass.json()["id"]
    klass2 = har.client.post("/api/v1/classes", json={
        "code": "V00C8", "name": "高一(8)班", "schoolYear": "2026-2027", "gradeId": "senior-1"})
    class2_id = klass2.json()["id"]

    csv_text = "学号,姓名\nV0001,张伟\nV0002,李娜\n"
    data, content_type = S.multipart({}, {"file": ("v00-roster.csv", csv_text.encode("utf-8"), "text/csv")})
    roster = har.client.post(f"/api/v1/classes/{class_id}/roster-imports", content=data,
                             headers={"content-type": content_type})
    check("V7.3 名单导入（T30-a 真 API）返回预览行",
          roster.status_code == 201 and len(roster.json()["rows"]) == 2
          and roster.json()["state"] == "reviewing",
          f"{roster.status_code} rows={len(roster.json().get('rows', []))}")
    import_id = roster.json()["importId"]
    roster_rows = roster.json()["rows"]
    created = har.client.post(f"/api/v1/roster-imports/{import_id}/confirm", json={
        "expectedRevision": roster.json()["revision"],
        "submissionId": "v00-v7-roster-confirm",
        "identityMatches": [{"rowNo": row["rowNo"], "action": "create"} for row in roster_rows],
    })
    check("V7.4 名单确认建档 + 归属成功",
          created.status_code == 200 and len(created.json()["applied"]) == 2
          and all(item["createdStudent"] and item["createdMembership"] for item in created.json()["applied"]),
          f"{created.status_code} {created.text[:200]}")
    applied = created.json()["applied"]
    student_z = applied[0]["studentId"]
    student_l = applied[1]["studentId"]
    memberships_before = membership_rows(har)
    check("V7.5 归属历史建立（2 行）", len(memberships_before) == 2, str(len(memberships_before)))

    # 施测创建（真链路）
    payload = {
        "submissionId": "v00-v7-assessment-1",
        "paperRevisionId": paper_revision_id,
        "title": "V00 期中施测（真链路）",
        "assessmentType": "exam",
        "heldOn": HELD_ON,
        "classIds": [class_id],
        "participants": [
            {"studentId": student_z, "classId": class_id, "attendance": "present"},
            {"studentId": student_l, "classId": class_id, "attendance": "absent"},
        ],
    }
    first = har.client.post("/api/v1/assessments", json=payload)
    check("V7.6 名单→原卷确认→施测 真链路创建成功",
          first.status_code == 201 and first.json()["assessment"]["paperRevisionId"] == paper_revision_id
          and first.json()["assessment"]["participantCount"] == 2,
          f"{first.status_code} {first.text[:200]}")
    assessment_id = first.json()["assessment"]["assessmentId"]
    rows_after_first = participant_rows(har, assessment_id)
    check("V7.7 参测姓名/学号从服务端读取冻结（不信任客户端）",
          {row["name_snapshot"] for row in rows_after_first} == {"张伟", "李娜"}
          and {row["student_no_snapshot"] for row in rows_after_first} == {"V0001", "V0002"}
          and {row["attempt_no"] for row in rows_after_first} == {1},
          str([(r["name_snapshot"], r["student_no_snapshot"], r["attempt_no"]) for r in rows_after_first]))

    # ---------------------------------------------------------------- 2. 幂等与冲突
    replay = har.client.post("/api/v1/assessments", json=payload)
    check("V7.8 同 submissionId 同载荷重放 → replayed=True 且不重复建",
          replay.status_code == 201 and replay.json()["replayed"] is True
          and replay.json()["assessment"]["assessmentId"] == assessment_id
          and len(participant_rows(har, assessment_id)) == 2,
          f"{replay.status_code} replayed={replay.json().get('replayed')}")
    conflict_payload = dict(payload, title="V00 改了标题的同一提交")
    conflict = har.client.post("/api/v1/assessments", json=conflict_payload)
    status, code, _details = error_of(conflict)
    check("V7.9 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT",
          conflict.status_code == 409 and code == "SUBMISSION_CONFLICT", f"{status}/{code}")

    # ---------------------------------------------------------------- 3. 闸门
    draft_state = S.prepare_ready_draft(har, sample, point_a=point_a, point_b=point_b, title="V00 另一待确认卷")
    draft_revision_id = draft_state["revision_id"]

    gates = [
        ("V7.10 draft 修订 → 422 ASSESSMENT_PAPER_INVALID",
         dict(payload, submissionId="v00-v7-g1", paperRevisionId=draft_revision_id),
         422, "ASSESSMENT_PAPER_INVALID", None),
        ("V7.11 不存在的修订 → 422 ASSESSMENT_PAPER_INVALID",
         dict(payload, submissionId="v00-v7-g2", paperRevisionId="no-such-revision"),
         422, "ASSESSMENT_PAPER_INVALID", None),
        ("V7.12 heldOn 非法日历日期 → 422 ASSESSMENT_HELD_ON_INVALID",
         dict(payload, submissionId="v00-v7-g3", heldOn="2026-02-30"),
         422, "ASSESSMENT_HELD_ON_INVALID", "heldOn"),
        ("V7.13 空 participants → 422（契约拒绝，不建零人施测）",
         dict(payload, submissionId="v00-v7-g4", participants=[]),
         422, None, "participants"),
        ("V7.14 班级不存在 → 422 PARTICIPANT_INVALID",
         dict(payload, submissionId="v00-v7-g5", classIds=["no-such-class"],
              participants=[{"studentId": student_z, "classId": "no-such-class"}]),
         422, "PARTICIPANT_INVALID", "classIds[0]"),
        ("V7.15 行班级不在 classIds 范围内 → 422 PARTICIPANT_CLASS_SCOPE",
         dict(payload, submissionId="v00-v7-g6", classIds=[class_id],
              participants=[{"studentId": student_z, "classId": class2_id}]),
         422, "PARTICIPANT_CLASS_SCOPE", "classId"),
        ("V7.16 classIds 重复 → 422（契约拒绝）",
         dict(payload, submissionId="v00-v7-g7", classIds=[class_id, class_id]),
         422, None, "classIds"),
        ("V7.17 学生不存在 → 422 PARTICIPANT_INVALID（逐行定位）",
         dict(payload, submissionId="v00-v7-g8",
              participants=[{"studentId": "no-such-student", "classId": class_id}]),
         422, "PARTICIPANT_INVALID", "studentId"),
        ("V7.18 客户端伪造姓名字段 → 422（extra=forbid，快照只从服务端读）",
         dict(payload, submissionId="v00-v7-g9",
              participants=[{"studentId": student_z, "classId": class_id, "nameSnapshot": "冒名"}]),
         422, None, "participants"),
        ("V7.19 客户端伪造学号字段 → 422（extra=forbid）",
         dict(payload, submissionId="v00-v7-g10",
              participants=[{"studentId": student_z, "classId": class_id, "studentNoSnapshot": "X999"}]),
         422, None, "participants"),
    ]
    for name, body, expect_status, expect_code, expect_field in gates:
        response = har.client.post("/api/v1/assessments", json=body)
        status, code, details = error_of(response)
        ok = status == expect_status and (expect_code is None or code == expect_code)
        detail = f"{status}/{code}"
        if ok and expect_field is not None:
            fields = details.get("fields") or [str(issue.get("field")) for issue in details.get("issues") or []]
            hit = any(expect_field == field or expect_field in str(field) for field in fields)
            ok = hit
            detail += f" fields={fields}"
        check(name, ok, detail)

    # ---------------------------------------------------------------- 4. 归属未覆盖
    # 学生 L 今天转班到 C8 → 对 C7 的归属只覆盖到今天；明天施测时不被覆盖
    moved_on = TODAY.isoformat()
    held_tomorrow = (TODAY + timedelta(days=1)).isoformat()
    transfer = har.client.post(f"/api/v1/students/{student_l}/transfer", json={
        "fromClassId": class_id, "toClassId": class2_id, "movedOn": moved_on,
        "expectedStudentRevision": 0})
    check("V7.20 学生转班成功（归属历史关闭旧行）", transfer.status_code == 200,
          f"{transfer.status_code} {transfer.text[:160]}")
    memberships_after_transfer = membership_rows(har)
    unconfirmed_payload = dict(payload, submissionId="v00-v7-unconfirmed", title="V00 归属未覆盖",
        heldOn=held_tomorrow,
        participants=[{"studentId": student_l, "classId": class_id, "attendance": "present"}])
    unconfirmed = har.client.post("/api/v1/assessments", json=unconfirmed_payload)
    status, code, details = error_of(unconfirmed)
    check("V7.21 归属未覆盖 heldOn → 422 PARTICIPANT_CLASS_UNCONFIRMED（逐行定位）",
          unconfirmed.status_code == 422 and code == "PARTICIPANT_CLASS_UNCONFIRMED"
          and any(issue.get("row") == 0 for issue in details.get("issues") or []),
          f"{status}/{code} {details}")
    confirm_payload = dict(unconfirmed_payload, submissionId="v00-v7-confirmed-class",
        participants=[{"studentId": student_l, "classId": class_id, "attendance": "present",
                       "classConfirmed": True,
                       "classConfirmationNote": "V00 探针：今日导入名单，历史归属未覆盖施测日"}])
    confirmed_create = har.client.post("/api/v1/assessments", json=confirm_payload)
    check("V7.22 教师带依据显式确认后创建成功，且 class_confirmed 落库",
          confirmed_create.status_code == 201
          and any(row["class_confirmed"] == 1 and row["class_confirmation_note"]
                  for row in participant_rows(har, confirmed_create.json()["assessment"]["assessmentId"])),
          f"{confirmed_create.status_code} {confirmed_create.text[:200]}")
    check("V7.23 归属历史逐行未被修改（不自动改历史）",
          membership_rows(har) == memberships_after_transfer,
          f"{digest(membership_rows(har))[:16]} == {digest(memberships_after_transfer)[:16]}")
    # 无依据的 classConfirmed=True 被契约拒绝
    bad_note = har.client.post("/api/v1/assessments", json=dict(
        unconfirmed_payload, submissionId="v00-v7-badnote",
        participants=[{"studentId": student_l, "classId": class_id, "classConfirmed": True}]))
    status, code, _d = error_of(bad_note)
    check("V7.24 classConfirmed=true 无依据 → 422（契约与 DB CHECK 对称）",
          bad_note.status_code == 422, f"{status}/{code}")

    # 同学生跨班重复（同一次请求两条，两个班都在 classIds）
    duplicate_cross = har.client.post("/api/v1/assessments", json=dict(
        payload, submissionId="v00-v7-cross", classIds=[class_id, class2_id],
        participants=[{"studentId": student_z, "classId": class_id},
                      {"studentId": student_z, "classId": class2_id}]))
    status, code, details = error_of(duplicate_cross)
    check("V7.25 同一学生跨班重复 → 422 PARTICIPANT_INVALID（要求人工选定）",
          duplicate_cross.status_code == 422 and code == "PARTICIPANT_INVALID"
          and any(issue.get("field") == "classId" for issue in details.get("issues") or []),
          f"{status}/{code} {details}")

    # ---------------------------------------------------------------- 5. 人次
    add_same_attempt = har.client.post(f"/api/v1/assessments/{assessment_id}/participants", json={
        "submissionId": "v00-v7-attempt-1", "expectedRevision": first.json()["assessment"]["revision"],
        "participants": [{"studentId": student_z, "classId": class_id, "attemptNo": 1}],
    })
    status, code, details = error_of(add_same_attempt)
    check("V7.26 (施测,学生,人次) 重复 → 409 PARTICIPANT_ATTEMPT_CONFLICT",
          add_same_attempt.status_code == 409 and code == "PARTICIPANT_ATTEMPT_CONFLICT",
          f"{status}/{code} {details}")
    before_makeup = participant_rows(har, assessment_id)
    makeup = har.client.post(f"/api/v1/assessments/{assessment_id}/participants", json={
        "submissionId": "v00-v7-makeup", "expectedRevision": first.json()["assessment"]["revision"],
        "participants": [{"studentId": student_z, "classId": class_id}],
    })
    check("V7.27 补考缺省新增下一人次（attempt 2）",
          makeup.status_code == 200
          and any(row["attemptNo"] == 2 for row in makeup.json()["participants"]),
          f"{makeup.status_code} {makeup.text[:200]}")
    after_makeup = participant_rows(har, assessment_id)
    attempt1_before = [row for row in before_makeup if row["attempt_no"] == 1]
    attempt1_after = [row for row in after_makeup if row["attempt_no"] == 1]
    check("V7.28 补考只新增行：首次记录逐字节不变",
          digest(attempt1_before) == digest(attempt1_after)
          and len(after_makeup) == len(before_makeup) + 1,
          f"{len(before_makeup)} → {len(after_makeup)}")

    # 批量回滚：第二条非法 → 第一条也不落库
    current = har.client.get(f"/api/v1/assessments/{assessment_id}").json()["assessment"]
    before_batch = participant_rows(har, assessment_id)
    rollback = har.client.post(f"/api/v1/assessments/{assessment_id}/participants", json={
        "submissionId": "v00-v7-rollback", "expectedRevision": current["revision"],
        "participants": [{"studentId": student_l, "classId": class_id, "attemptNo": 3},
                         {"studentId": "no-such-student", "classId": class_id}],
    })
    status, code, _d = error_of(rollback)
    check("V7.29 批量补录含非法行 → 422 且整批回滚（第一条也不落库）",
          rollback.status_code == 422 and participant_rows(har, assessment_id) == before_batch,
          f"{status}/{code} rows={len(participant_rows(har, assessment_id))}")

    # ---------------------------------------------------------------- 6. 快照冻结 / 更新
    rename = har.client.patch(f"/api/v1/students/{student_z}", json={
        "expectedRevision": 0, "name": "张伟（改名）"})
    check("V7.30 学生改名成功", rename.status_code == 200, f"{rename.status_code} {rename.text[:120]}")
    detail = har.client.get(f"/api/v1/assessments/{assessment_id}").json()
    check("V7.31 改名后既有施测快照不变（仍为旧名）",
          all(row["nameSnapshot"] != "张伟（改名）" for row in detail["participants"])
          and any(row["nameSnapshot"] == "张伟" for row in detail["participants"]),
          str({row["nameSnapshot"] for row in detail["participants"]}))
    detail_after_makeup = har.client.get(f"/api/v1/assessments/{assessment_id}").json()["assessment"]
    updated = har.client.patch(f"/api/v1/assessments/{assessment_id}", json={
        "expectedRevision": detail_after_makeup["revision"], "title": "V00 施测（改标题）"})
    check("V7.32 PATCH 施测 → revision+1 且标题更新",
          updated.status_code == 200 and updated.json()["revision"] == detail_after_makeup["revision"] + 1
          and updated.json()["title"] == "V00 施测（改标题）",
          f"{updated.status_code} rev={detail_after_makeup['revision']}→{updated.json().get('revision')}")
    stale = har.client.patch(f"/api/v1/assessments/{assessment_id}", json={
        "expectedRevision": detail_after_makeup["revision"], "title": "V00 过期更新"})
    status, code, details = error_of(stale)
    check("V7.33 PATCH 过期 → 409 ASSESSMENT_REVISION_STALE + currentRevision",
          stale.status_code == 409 and code == "ASSESSMENT_REVISION_STALE"
          and details.get("currentRevision") == updated.json()["revision"],
          f"{status}/{code} {details}")

    har.client.close()
    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v7_assessments_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v7_assessments_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    try:
        raise SystemExit(main(_args.evidence))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-300:]})
        raise SystemExit(finish(_args.evidence, reason="crashed"))
