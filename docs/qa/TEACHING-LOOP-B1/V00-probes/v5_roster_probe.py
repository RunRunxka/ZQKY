"""V5 名单导入 / 身份消歧 / 确认 探针（TEACHING-LOOP B1 / V00）。

覆盖：0012 前导零（XLSX 文本列 vs 数值列）；无学号/同名/重复行/姓名不符的建议分类；
未给决定 → 422 逐行定位；重复行未消歧 → 422 且零写入；link 缺 studentId / create 带
studentId → 422；确认成功建立归属；未出现的学生不动；转班保留旧归属；重放幂等；整批回滚。
反例：同一学生两行（一行 link 一行 create，同姓名同学号）与（同名都无学号）。
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v5_roster")
root = temp_data_root("v5")
ensure_api_on_path()

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

ALLOWED = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})
settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=root / "data")
client = TestClient(create_app(settings), base_url="http://127.0.0.1:8001")
client.__enter__()

DB = root / "data" / "teaching" / "teaching.sqlite3"


def api(method: str, path: str, **kwargs):
    return client.request(method, f"/api/v1{path}", **kwargs)


def err(resp):
    try:
        return resp.json()
    except ValueError:
        return {"code": None, "message": resp.text[:200]}


def xlsx(headers: list[str], rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def db_scalar(sql: str, params: tuple = ()):
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def upload_roster(class_id: str, name: str, payload: bytes, media: str):
    return api(
        "POST",
        f"/classes/{class_id}/roster-imports",
        files={"file": (name, payload, media)},
    )


try:
    # ------------------------------------------------------------------ 基础数据
    klass_a = api(
        "POST",
        "/classes",
        json={"code": "C1", "name": "一年一班", "schoolYear": "2026-2027", "gradeId": "g1"},
    )
    p.check("v5.0a 建班 201", klass_a.status_code == 201, f"{klass_a.status_code} {json.dumps(err(klass_a), ensure_ascii=False)[:200]}")
    class_a = klass_a.json()["id"]
    class_b = api(
        "POST",
        "/classes",
        json={"code": "C2", "name": "一年二班", "schoolYear": "2026-2027", "gradeId": "g1"},
    ).json()["id"]
    dupe_class = api(
        "POST",
        "/classes",
        json={"code": "C1", "name": "重复编码", "schoolYear": "2026-2027", "gradeId": "g1"},
    )
    p.check(
        "v5.0b 同学年同 code → 409 CLASS_CODE_CONFLICT",
        dupe_class.status_code == 409 and err(dupe_class).get("code") == "CLASS_CODE_CONFLICT",
        f"{dupe_class.status_code} {err(dupe_class).get('code')}",
    )

    def make_student(name: str, no: str | None, class_id: str | None = None):
        body = {"name": name}
        if no is not None:
            body["studentNo"] = no
        if class_id:
            body["classId"] = class_id
        return api("POST", "/students", json=body)

    s1 = make_student("张三", "0012", class_a).json()          # 已在 A 班（未出现学生不动）
    s2 = make_student("李四", "0007").json()
    s3 = make_student("王五", None).json()
    s4 = make_student("张伟", None).json()
    s5 = make_student("张伟", None).json()
    p.check(
        "v5.0c 学号原样保存（前导零不丢）",
        s1["studentNo"] == "0012" and s2["studentNo"] == "0007" and s3["studentNo"] is None,
        json.dumps([s1["studentNo"], s2["studentNo"], s3["studentNo"]]),
    )

    # ------------------------------------------------------------------ XLSX 导入 + 前导零
    sheet = xlsx(
        ["学号", "姓名"],
        [
            ["0012", "张三"],   # 文本学号：前导零保留
            [12, "张伟"],       # 数值学号 12（无学号匹配，仅验证数字格式）
            [None, "张伟"],     # 无学号 + 同名两人 → conflict
            ["9999", "新同学"],  # 新建
            ["0007", "王五"],   # 学号命中李四但姓名不符 → name_mismatch
            ["8888", "重复同学"],
            ["8888", "重复同学"],
        ],
    )
    first = upload_roster(class_a, "roster.xlsx", sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    p.check("v5.1a 名单上传 201", first.status_code == 201, f"{first.status_code} {json.dumps(err(first), ensure_ascii=False)[:300]}")
    view = first.json()
    rid = view["importId"]
    rows = {row["rowNo"]: row for row in view["rows"]}
    p.check(
        "v5.1b 表头自动映射（学号/姓名）+ state=reviewing",
        view["mapping"] == {"studentNo": "学号", "name": "姓名"} and view["state"] == "reviewing",
        json.dumps({"mapping": view["mapping"], "state": view["state"]}, ensure_ascii=False),
    )
    p.check(
        "v5.1c XLSX 文本学号保留前导零（0012）",
        rows[1]["studentNo"] == "0012",
        f"row1.studentNo={rows[1]['studentNo']!r}",
    )
    p.check(
        "v5.1d XLSX 数值学号无小数噪声（12 → \"12\"）",
        rows[2]["studentNo"] == "12",
        f"row2.studentNo={rows[2]['studentNo']!r}",
    )
    p.check(
        "v5.1e 无学号行保留 None（不当空串/占位）",
        rows[3]["studentNo"] is None,
        f"row3.studentNo={rows[3]['studentNo']!r}",
    )
    suggestions = {no: row["suggestion"] for no, row in rows.items()}
    p.check(
        "v5.1f 建议分类：1=link 2=create(数值学号) 3=conflict 4=create 5=name_mismatch 6/7=duplicate",
        suggestions
        == {1: "link", 2: "create", 3: "conflict", 4: "create", 5: "name_mismatch", 6: "duplicate", 7: "duplicate"},
        json.dumps(suggestions, ensure_ascii=False),
    )
    p.check(
        "v5.1g 建议不构成写入决定（decision 仍为空）",
        all(row["decision"] is None for row in view["rows"]),
        json.dumps([row["decision"] for row in view["rows"]]),
    )
    p.check(
        "v5.1h 同名冲突行带可定位 issue（ROSTER_NAME_CONFLICT）",
        any(
            issue["code"] == "ROSTER_NAME_CONFLICT" and issue.get("row") == 3
            for issue in rows[3]["issues"]
        ),
        json.dumps(rows[3]["issues"], ensure_ascii=False)[:300],
    )

    # ------------------------------------------------------------------ 未给决定 / 重复未消歧
    before_students = db_scalar("SELECT COUNT(*) FROM students")
    base_confirm = {"expectedRevision": view["revision"], "submissionId": "v5-no-decision"}
    no_decision = api("POST", f"/roster-imports/{rid}/confirm", json=base_confirm)
    nd_body = err(no_decision)
    nd_rows = sorted({item["row"] for item in (nd_body.get("details") or {}).get("issues") or []})
    p.check(
        "v5.2a 未给决定 → 422 ROSTER_IMPORT_BLOCKING_ISSUES（先报阻断行 3/6/7）",
        no_decision.status_code == 422
        and nd_body.get("code") == "ROSTER_IMPORT_BLOCKING_ISSUES"
        and nd_rows == [3, 6, 7],
        f"{no_decision.status_code} {json.dumps(nd_body, ensure_ascii=False)[:400]}",
    )
    p.check("v5.2b 未给决定零写入", db_scalar("SELECT COUNT(*) FROM students") == before_students, "students unchanged")

    blocking_ok = {
        "expectedRevision": view["revision"],
        "submissionId": "v5-blocking-2",
        "identityMatches": [
            {"rowNo": 3, "action": "link", "studentId": s4["id"]},
            {"rowNo": 6, "action": "create"},
            {"rowNo": 7, "action": "ignore"},
        ],
    }
    unresolved = api("POST", f"/roster-imports/{rid}/confirm", json=blocking_ok)
    un_body = err(unresolved)
    un_rows = sorted({item["row"] for item in (un_body.get("details") or {}).get("issues") or []})
    p.check(
        "v5.2c 消歧后仍有未决定行 → 422 ROSTER_IDENTITY_UNRESOLVED 逐行定位 [1,2,4,5]",
        unresolved.status_code == 422
        and un_body.get("code") == "ROSTER_IDENTITY_UNRESOLVED"
        and un_rows == [1, 2, 4, 5],
        f"{unresolved.status_code} {json.dumps(un_body, ensure_ascii=False)[:400]}",
    )
    p.check("v5.2d 零写入", db_scalar("SELECT COUNT(*) FROM students") == before_students, "students unchanged")

    # ------------------------------------------------------------------ 形状校验
    link_missing = api(
        "POST",
        f"/roster-imports/{rid}/confirm",
        json={
            "expectedRevision": view["revision"],
            "submissionId": "v5-link-missing",
            "identityMatches": [
                {"rowNo": 1, "action": "link"},
                {"rowNo": 2, "action": "create"},
                {"rowNo": 3, "action": "link", "studentId": s4["id"]},
                {"rowNo": 4, "action": "create"},
                {"rowNo": 5, "action": "link", "studentId": s2["id"]},
                {"rowNo": 6, "action": "create"},
                {"rowNo": 7, "action": "ignore"},
            ],
        },
    )
    lm_body = err(link_missing)
    p.check(
        "v5.3a link 缺 studentId → 422 ROSTER_IDENTITY_UNRESOLVED + field=studentId",
        link_missing.status_code == 422
        and lm_body.get("code") == "ROSTER_IDENTITY_UNRESOLVED"
        and ((lm_body.get("details") or {}).get("issues") or [{}])[0].get("field") == "studentId"
        and ((lm_body.get("details") or {}).get("issues") or [{}])[0].get("row") == 1,
        f"{link_missing.status_code} {json.dumps(lm_body, ensure_ascii=False)[:300]}",
    )
    create_with_id = api(
        "POST",
        f"/roster-imports/{rid}/confirm",
        json={
            "expectedRevision": view["revision"],
            "submissionId": "v5-create-with-id",
            "identityMatches": [
                {"rowNo": 1, "action": "link", "studentId": s1["id"]},
                {"rowNo": 2, "action": "create"},
                {"rowNo": 3, "action": "link", "studentId": s4["id"]},
                {"rowNo": 4, "action": "create", "studentId": s1["id"]},
                {"rowNo": 5, "action": "link", "studentId": s2["id"]},
                {"rowNo": 6, "action": "create"},
                {"rowNo": 7, "action": "ignore"},
            ],
        },
    )
    cw_body = err(create_with_id)
    p.check(
        "v5.3b create 带 studentId → 422 INVALID_REQUEST + field=studentId",
        create_with_id.status_code == 422
        and cw_body.get("code") == "INVALID_REQUEST"
        and ((cw_body.get("details") or {}).get("issues") or [{}])[0].get("field") == "studentId"
        and ((cw_body.get("details") or {}).get("issues") or [{}])[0].get("row") == 4,
        f"{create_with_id.status_code} {json.dumps(cw_body, ensure_ascii=False)[:300]}",
    )
    p.check("v5.3c 形状校验失败零写入", db_scalar("SELECT COUNT(*) FROM students") == before_students, "students unchanged")

    # ------------------------------------------------------------------ 成功确认
    confirm_body = {
        "expectedRevision": view["revision"],
        "submissionId": "v5-confirm-1",
        "identityMatches": [
            {"rowNo": 1, "action": "link", "studentId": s1["id"]},
            {"rowNo": 2, "action": "create"},
            {"rowNo": 3, "action": "link", "studentId": s4["id"]},
            {"rowNo": 4, "action": "create"},
            {"rowNo": 5, "action": "link", "studentId": s2["id"]},
            {"rowNo": 6, "action": "create"},
            {"rowNo": 7, "action": "ignore"},
        ],
    }
    confirmed = api("POST", f"/roster-imports/{rid}/confirm", json=confirm_body)
    p.check(
        "v5.4a 确认成功 200 + state=confirmed",
        confirmed.status_code == 200 and confirmed.json()["state"] == "confirmed",
        f"{confirmed.status_code} {json.dumps(err(confirmed), ensure_ascii=False)[:300]}",
    )
    cbody = confirmed.json()
    applied_rows = [item["rowNo"] for item in cbody["applied"]]
    p.check(
        "v5.4b applied 覆盖 1..6、ignored=[7]；已建班学生的归属复用（createdMembership=false）",
        applied_rows == [1, 2, 3, 4, 5, 6]
        and cbody["ignored"] == [7]
        and next(item for item in cbody["applied"] if item["rowNo"] == 1)["createdStudent"] is False
        and next(item for item in cbody["applied"] if item["rowNo"] == 1)["createdMembership"] is False,
        json.dumps(cbody, ensure_ascii=False)[:500],
    )
    p.check(
        "v5.4c 新建 3 名学生（行 2/5/6），link 行不建学生",
        db_scalar("SELECT COUNT(*) FROM students") == before_students + 3,
        f"students={db_scalar('SELECT COUNT(*) FROM students')}",
    )
    active_in_a = api("GET", f"/classes/{class_a}/students").json()
    p.check(
        "v5.4d 班级活跃成员 = 6（张三/李四/张伟 + 行2/4/6 新建）",
        active_in_a["total"] == 6,
        json.dumps({"total": active_in_a["total"], "names": [item["name"] for item in active_in_a["items"]]}, ensure_ascii=False),
    )
    wangwu = api("GET", f"/students/{s3['id']}").json()
    p.check(
        "v5.4e 未出现的学生不动（王五 仍在、无新归属、姓名学号不变）",
        wangwu["name"] == "王五"
        and wangwu["studentNo"] is None
        and wangwu["memberships"] == [],
        json.dumps({k: wangwu[k] for k in ("name", "studentNo", "memberships")}, ensure_ascii=False),
    )
    replay = api("POST", f"/roster-imports/{rid}/confirm", json=confirm_body)
    p.check(
        "v5.4f 同 submissionId 重放 → replayed=true 且结果一致、无重复写入",
        replay.status_code == 200
        and replay.json()["replayed"] is True
        and replay.json()["applied"] == cbody["applied"]
        and db_scalar("SELECT COUNT(*) FROM students") == before_students + 3,
        json.dumps({"status": replay.status_code, "replayed": replay.json().get("replayed"), "students": db_scalar("SELECT COUNT(*) FROM students")}),
    )
    conflict_replay = api(
        "POST",
        f"/roster-imports/{rid}/confirm",
        json={**confirm_body, "submissionId": "v5-confirm-other"},
    )
    p.check(
        "v5.4g 已确认批次换新 submissionId 再确认 → 409 ROSTER_IMPORT_CONFIRMED",
        conflict_replay.status_code == 409 and err(conflict_replay).get("code") == "ROSTER_IMPORT_CONFIRMED",
        f"{conflict_replay.status_code} {err(conflict_replay).get('code')}",
    )

    # ------------------------------------------------------------------ 转班保留旧归属
    s2_now = api("GET", f"/students/{s2['id']}").json()
    transfer = api(
        "POST",
        f"/students/{s2['id']}/transfer",
        json={
            "expectedStudentRevision": s2_now["revision"],
            "fromClassId": class_a,
            "toClassId": class_b,
            "movedOn": "2026-10-08",
        },
    )
    p.check("v5.5a 转班 200", transfer.status_code == 200, f"{transfer.status_code} {json.dumps(err(transfer), ensure_ascii=False)[:200]}")
    s2_after = api("GET", f"/students/{s2['id']}").json()
    memberships = {item["classId"]: item for item in s2_after["memberships"]}
    p.check(
        "v5.5b 转班后旧归属置 leftOn、新归属活跃（历史保留）",
        len(s2_after["memberships"]) == 2
        and memberships[class_a]["leftOn"] is not None
        and memberships[class_b]["leftOn"] is None,
        json.dumps(s2_after["memberships"], ensure_ascii=False),
    )
    class_a_after = api("GET", f"/classes/{class_a}/students").json()
    p.check(
        "v5.5c A 班活跃成员不再含李四（6-1=5 人）",
        class_a_after["total"] == 5 and all(item["id"] != s2["id"] for item in class_a_after["items"]),
        json.dumps({"total": class_a_after["total"]}, ensure_ascii=False),
    )

    # ------------------------------------------------------------------ 反例：同一学生两行（link + create，同姓名同学号）
    before_students = db_scalar("SELECT COUNT(*) FROM students")
    before_members = db_scalar("SELECT COUNT(*) FROM class_memberships WHERE left_on IS NULL")
    dup_sheet = xlsx(["学号", "姓名"], [["0012", "张三"], ["0012", "张三"]])
    dup_import = upload_roster(
        class_a, "dup-link-create.xlsx", dup_sheet,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    dview = dup_import.json()
    did = dview["importId"]
    dup_confirm = api(
        "POST",
        f"/roster-imports/{did}/confirm",
        json={
            "expectedRevision": dview["revision"],
            "submissionId": "v5-link-plus-create-same-no",
            "identityMatches": [
                {"rowNo": 1, "action": "link", "studentId": s1["id"]},
                {"rowNo": 2, "action": "create"},
            ],
        },
    )
    dd = err(dup_confirm)
    p.check(
        "v5.6a 同姓名同学号 link+create → 阻断且零写入（实测错误码记录）",
        dup_confirm.status_code in (409, 422)
        and db_scalar("SELECT COUNT(*) FROM students") == before_students
        and db_scalar("SELECT COUNT(*) FROM class_memberships WHERE left_on IS NULL") == before_members,
        f"{dup_confirm.status_code} {json.dumps(dd, ensure_ascii=False)[:400]}",
    )
    p.check(
        "v5.6b 阻断行可定位（details.issues[].row 指向第 2 行）",
        any(item.get("row") == 2 for item in (dd.get("details") or {}).get("issues") or []),
        json.dumps(dd.get("details"), ensure_ascii=False)[:300],
    )
    p.check(
        "v5.6c 阻断后批次仍可编辑（state 未变 confirmed）",
        api("GET", f"/roster-imports/{did}").json()["state"] == "reviewing",
        f"state={api('GET', f'/roster-imports/{did}').json()['state']}",
    )

    # ------------------------------------------------------------------ 反例：同名都无学号 link + create
    before_students = db_scalar("SELECT COUNT(*) FROM students")
    same_name_sheet = xlsx(["学号", "姓名"], [[None, "张伟"], [None, "张伟"]])
    sn_import = upload_roster(
        class_a, "dup-link-create-name.xlsx", same_name_sheet,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    sview = sn_import.json()
    sid = sview["importId"]
    sn_confirm = api(
        "POST",
        f"/roster-imports/{sid}/confirm",
        json={
            "expectedRevision": sview["revision"],
            "submissionId": "v5-link-plus-create-same-name",
            "identityMatches": [
                {"rowNo": 1, "action": "link", "studentId": s4["id"]},
                {"rowNo": 2, "action": "create"},
            ],
        },
    )
    sn_body = err(sn_confirm)
    sn_blocked = sn_confirm.status_code != 200
    p.check(
        "v5.7a 同名(均无学号) link+create：记录实际行为（阻断 or 新建同名学生）",
        True,
        f"status={sn_confirm.status_code} students {before_students}->{db_scalar('SELECT COUNT(*) FROM students')} code={sn_body.get('code')}",
    )
    p.check(
        "v5.7b 若未阻断则必须真的新建了一名同名学生（不是假成功）",
        sn_confirm.status_code != 200
        or db_scalar("SELECT COUNT(*) FROM students") == before_students + 1,
        f"status={sn_confirm.status_code} students={db_scalar('SELECT COUNT(*) FROM students')}",
    )

    # ------------------------------------------------------------------ 重复行未消歧 → 阻断零写入
    before_students = db_scalar("SELECT COUNT(*) FROM students")
    dup_only = xlsx(["学号", "姓名"], [["5555", "甲"], ["5555", "乙"]])
    do_import = upload_roster(
        class_a, "dup-only.xlsx", dup_only,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    dov = do_import.json()
    do_confirm = api(
        "POST",
        f"/roster-imports/{dov['importId']}/confirm",
        json={
            "expectedRevision": dov["revision"],
            "submissionId": "v5-dup-unresolved",
            "identityMatches": [
                {"rowNo": 1, "action": "create"},
                {"rowNo": 2, "action": "create"},
            ],
        },
    )
    do_body = err(do_confirm)
    p.check(
        "v5.8a 同学号异名两行都 create → 阻断（实测 STUDENT_NO_CONFLICT 409）+ 零写入",
        do_confirm.status_code in (409, 422)
        and db_scalar("SELECT COUNT(*) FROM students") == before_students
        and any(item.get("row") for item in (do_body.get("details") or {}).get("issues") or []),
        f"{do_confirm.status_code} {json.dumps(do_body, ensure_ascii=False)[:300]}",
    )
    resolved = api(
        "POST",
        f"/roster-imports/{dov['importId']}/confirm",
        json={
            "expectedRevision": dov["revision"],
            "submissionId": "v5-dup-resolved",
            "identityMatches": [
                {"rowNo": 1, "action": "create"},
                {"rowNo": 2, "action": "ignore"},
            ],
        },
    )
    p.check(
        "v5.8b 消歧后（一行 create 一行 ignore）确认成功",
        resolved.status_code == 200 and resolved.json()["ignored"] == [2],
        f"{resolved.status_code} {json.dumps(err(resolved), ensure_ascii=False)[:250]}",
    )

    # ------------------------------------------------------------------ CSV 名单 + 归档班级
    csv_bytes_ = "学号,姓名\n6001,新甲\n6002,新乙\n".encode("utf-8")
    csv_import = upload_roster(class_a, "roster.csv", csv_bytes_, "text/csv")
    p.check(
        "v5.9a CSV 名单上传 + 自动映射（学号/姓名）",
        csv_import.status_code == 201 and csv_import.json()["mapping"] == {"studentNo": "学号", "name": "姓名"},
        f"{csv_import.status_code} {json.dumps(csv_import.json().get('mapping'), ensure_ascii=False)}",
    )
    archived = api("POST", f"/classes/{class_b}/archive", json={"expectedRevision": api('GET', f'/classes/{class_b}').json()['revision']})
    p.check(
        "v5.9b 归档班级 200 + status=archived",
        archived.status_code == 200 and archived.json()["status"] == "archived",
        f"{archived.status_code} {json.dumps(err(archived), ensure_ascii=False)[:200]}",
    )
    import_into_archived = upload_roster(class_b, "roster.csv", csv_bytes_, "text/csv")
    p.check(
        "v5.9c 归档班级导入名单被拒（409 CLASS_ARCHIVED）",
        import_into_archived.status_code == 409 and err(import_into_archived).get("code") == "CLASS_ARCHIVED",
        f"{import_into_archived.status_code} {err(import_into_archived).get('code')}",
    )
finally:
    client.__exit__(None, None, None)

sys.exit(p.finish())
