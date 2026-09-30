"""V3 知识点表格导入 / 预览 / 映射 / 确认 探针（TEACHING-LOOP B1 / V00）。

覆盖：XLSX/CSV 各一；自动与手工映射；预览持久化（批次 + 行 + issues）；
阻断问题拒绝且零写入；确认成功（created/updated/ignored + 批内父节点拓扑）；
同 submissionId 重放返回原结果且不重复写；apply 失败整批回滚；
空白不清空 vs clearFields 清空。
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v3_knowledge_imports")
root = temp_data_root("v3")
ensure_api_on_path()

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

ALLOWED = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})
settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=root / "data")
client = TestClient(create_app(settings), base_url="http://127.0.0.1:8001")
client.__enter__()

DB = root / "data" / "knowledge" / "knowledge.sqlite3"


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


def csv_bytes(headers: list[str], rows: list[list[str]]) -> bytes:
    lines = [",".join(headers)] + [",".join(row) for row in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def point_count() -> int:
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
    finally:
        conn.close()


def upload(name: str, payload: bytes, media: str, **extra):
    data = {"subjectId": "math", **extra}
    return api(
        "POST",
        "/knowledge-imports",
        files={"file": (name, payload, media)},
        data={key: value for key, value in data.items() if value is not None},
    )


try:
    # ------------------------------------------------------------------ A XLSX 自动映射 + 预览持久化
    sheet = xlsx(
        ["编码", "名称", "描述", "父级", "别名", "备注"],
        [
            ["A-02", "子节点", "子说明", "A-01", "别一、bei", "忽略我"],
            ["A-01", "父节点", "父说明", None, None, None],
            ["A-03", "环A", "", "A-04", None, None],
            ["A-04", "环B", "", "A-03", None, None],
        ],
    )
    first = upload("points.xlsx", sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    p.check("v3.1a XLSX 上传 201", first.status_code == 201, f"{first.status_code} {json.dumps(err(first), ensure_ascii=False)[:300]}")
    view = first.json()
    import_id = view["importId"]
    p.check(
        "v3.1b 自动映射命中（编码/名称/描述/父级/别名）+ 未映射列提示；无缺必需列 issue",
        view["mapping"].get("code") == "编码"
        and view["mapping"].get("name") == "名称"
        and view["mapping"].get("parentCode") == "父级"
        and view["mapping"].get("aliases") == "别名"
        and view["state"] == "reviewing"
        and [issue["code"] for issue in view["issues"]] == ["KNOWLEDGE_IMPORT_UNKNOWN_COLUMN"]
        and "subjectCode" not in view["mapping"],
        json.dumps({"mapping": view["mapping"], "issues": view["issues"], "warnings": view["warnings"]}, ensure_ascii=False)[:600],
    )
    p.check(
        "v3.1c 预览行落库（4 行、别名拆分、原始单元格保留）",
        len(view["rows"]) == 4
        and view["rows"][0]["rowNo"] == 1
        and view["rows"][0]["code"] == "A-02"
        and view["rows"][0]["parentCode"] == "A-01"
        and view["rows"][0]["aliases"] == ["别一", "bei"]
        and view["rows"][0]["decision"] is None,
        json.dumps(view["rows"][0], ensure_ascii=False)[:400],
    )
    cycle_rows = [row for row in view["rows"] if row["rowNo"] in (3, 4)]
    p.check(
        "v3.1d 批内父链成环 → 逐行可定位 KNOWLEDGE_CYCLE（field=parentCode）",
        all(
            any(issue["code"] == "KNOWLEDGE_CYCLE" and issue.get("field") == "parentCode" for issue in row["issues"])
            for row in cycle_rows
        ),
        json.dumps([row["issues"] for row in cycle_rows], ensure_ascii=False)[:500],
    )
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    stored = conn.execute(
        "SELECT mapping_json, issues_json, warnings_json FROM knowledge_imports WHERE id = ?", (import_id,)
    ).fetchone()
    row_issues = conn.execute(
        "SELECT COUNT(*) FROM knowledge_import_rows WHERE import_id = ? AND issues_json <> '[]'", (import_id,)
    ).fetchone()[0]
    conn.close()
    p.check(
        "v3.1e 预览持久化：批次 issues_json 非空 + 行 issues 独立落列",
        json.loads(stored["issues_json"]) != [] and row_issues >= 2,
        f"batch_issues={stored['issues_json'][:120]} rows_with_issues={row_issues}",
    )
    cycle_confirm = api(
        "POST",
        f"/knowledge-imports/{import_id}/confirm",
        json={
            "expectedRevision": view["revision"],
            "submissionId": "v3-cycle",
            "actions": [
                {"rowNo": 1, "decision": "create"},
                {"rowNo": 2, "decision": "create"},
                {"rowNo": 3, "decision": "ignore"},
                {"rowNo": 4, "decision": "ignore"},
            ],
        },
    )
    p.check(
        "v3.1f 环行即使 ignore 也被预检拒绝（blocking 只看行 issues，不看动作）",
        cycle_confirm.status_code == 422
        and err(cycle_confirm).get("code") == "KNOWLEDGE_IMPORT_BLOCKING_ISSUES",
        f"{cycle_confirm.status_code} {json.dumps(err(cycle_confirm), ensure_ascii=False)[:300]}",
    )
    p.check("v3.1g 阻断时零写入", point_count() == 0, f"points={point_count()}")

    # ------------------------------------------------------------------ B 干净批次：拓扑序 + created/updated/ignored + 重放
    clean = xlsx(
        ["编码", "名称", "描述", "父级", "别名"],
        [
            ["B-02", "B 子", "子说明", "B-01", None],
            ["B-01", "B 父", "父说明", None, None],
            ["B-09", "忽略我", "", None, None],
        ],
    )
    second = upload("clean.xlsx", clean, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    cview = second.json()
    cid = cview["importId"]
    confirm_body = {
        "expectedRevision": cview["revision"],
        "submissionId": "v3-clean-1",
        "actions": [
            {"rowNo": 1, "decision": "create"},
            {"rowNo": 2, "decision": "create"},
            {"rowNo": 3, "decision": "ignore"},
        ],
    }
    confirmed = api("POST", f"/knowledge-imports/{cid}/confirm", json=confirm_body)
    p.check(
        "v3.2a 确认成功 200 + state=confirmed",
        confirmed.status_code == 200 and confirmed.json()["state"] == "confirmed",
        f"{confirmed.status_code} {json.dumps(err(confirmed), ensure_ascii=False)[:300]}",
    )
    cbody = confirmed.json()
    p.check(
        "v3.2b created 按批内拓扑序（父先子后），ignored 记录行号",
        [item["rowNo"] for item in cbody["created"]] == [2, 1]
        and cbody["updated"] == []
        and cbody["ignored"] == [3]
        and cbody["replayed"] is False,
        json.dumps(cbody, ensure_ascii=False)[:400],
    )
    p.check("v3.2c 入库 2 个知识点、被忽略的 1 行未建", point_count() == 2, f"points={point_count()}")
    parent_point = api("GET", f"/knowledge-points/{cbody['created'][0]['knowledgePointId']}").json()
    child_point = api("GET", f"/knowledge-points/{cbody['created'][1]['knowledgePointId']}").json()
    p.check(
        "v3.2d 子点父链正确（parentCode=B-01）",
        child_point["parentCode"] == "B-01" and child_point["parentId"] == parent_point["id"],
        json.dumps({"childParent": child_point["parentCode"], "childParentId": child_point["parentId"], "parentId": parent_point["id"]}),
    )

    replay = api("POST", f"/knowledge-imports/{cid}/confirm", json=confirm_body)
    p.check(
        "v3.2e 同 submissionId 重放 → replayed=true 且返回原结果",
        replay.status_code == 200
        and replay.json()["replayed"] is True
        and replay.json()["created"] == cbody["created"]
        and replay.json()["ignored"] == cbody["ignored"],
        json.dumps({k: replay.json()[k] for k in ("replayed", "ignored")}, ensure_ascii=False),
    )
    p.check("v3.2f 重放不重复写", point_count() == 2, f"points={point_count()}")

    again = api("POST", f"/knowledge-imports/{cid}/confirm", json={**confirm_body, "expectedRevision": 99})
    p.check(
        "v3.2g 同 submissionId 不同载荷 → 409 SUBMISSION_CONFLICT",
        again.status_code == 409 and err(again).get("code") == "SUBMISSION_CONFLICT",
        f"{again.status_code} {err(again).get('code')}",
    )

    # ------------------------------------------------------------------ C update 行：空白不清空 + 过期修订整批回滚
    update_sheet = xlsx(
        ["编码", "名称", "描述", "别名"],
        [["B-01", "B 父改名", None, None]],
    )
    third = upload("update.xlsx", update_sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    uview = third.json()
    uid = uview["importId"]
    row1 = uview["rows"][0]
    p.check(
        "v3.3a 既有 code 自动匹配 update 目标并冻结 baseRevision",
        row1["targetKnowledgePointId"] == parent_point["id"]
        and row1["baseRevision"] == parent_point["revision"]
        and row1["baseVersion"] == parent_point["version"]
        and row1["decision"] == "update",
        json.dumps(row1, ensure_ascii=False)[:400],
    )
    blank_update = api(
        "POST",
        f"/knowledge-imports/{uid}/confirm",
        json={
            "expectedRevision": uview["revision"],
            "submissionId": "v3-blank",
            "actions": [{"rowNo": 1, "decision": "update"}],
        },
    )
    p.check(
        "v3.3b 空白可选字段默认不修改（description 保持原值）",
        blank_update.status_code == 200
        and blank_update.json()["updated"][0]["version"] == 2,
        f"{blank_update.status_code} {json.dumps(err(blank_update), ensure_ascii=False)[:300]}",
    )
    after_blank = api("GET", f"/knowledge-points/{parent_point['id']}").json()
    p.check(
        "v3.3c 改名生效但 description/aliases 未被空白清空",
        after_blank["name"] == "B 父改名"
        and after_blank["description"] == "父说明"
        and after_blank["aliases"] == [],
        json.dumps({k: after_blank[k] for k in ("name", "description", "aliases")}, ensure_ascii=False),
    )
    cleared = api(
        "PATCH",
        f"/knowledge-points/{parent_point['id']}",
        json={"expectedRevision": after_blank["revision"], "clearFields": ["description"]},
    )
    p.check(
        "v3.3d 知识点级 clearFields 才清空 description",
        cleared.status_code == 200 and cleared.json()["description"] == "",
        json.dumps({"status": cleared.status_code, "description": cleared.json().get("description")}, ensure_ascii=False),
    )

    # 过期 expectedRevision 的 update 行 + 一个 create 行 → 整批回滚
    mixed_sheet = xlsx(
        ["编码", "名称", "父级"],
        [["C-01", "C 新建", None], ["B-01", "B 父再改", None]],
    )
    fourth = upload("mixed.xlsx", mixed_sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    mview = fourth.json()
    mid = mview["importId"]
    before_points = point_count()
    stale_confirm = api(
        "POST",
        f"/knowledge-imports/{mid}/confirm",
        json={
            "expectedRevision": mview["revision"],
            "submissionId": "v3-stale",
            "actions": [
                {"rowNo": 1, "decision": "create"},
                {"rowNo": 2, "decision": "update", "expectedRevision": 0},
            ],
        },
    )
    p.check(
        "v3.4a update 行 expectedRevision 过期 → 409 REVISION_CONFLICT + details.currentRevision",
        stale_confirm.status_code == 409
        and err(stale_confirm).get("code") == "REVISION_CONFLICT"
        and (err(stale_confirm).get("details") or {}).get("currentRevision") == cleared.json()["revision"],
        f"{stale_confirm.status_code} {json.dumps(err(stale_confirm), ensure_ascii=False)[:300]}",
    )
    p.check(
        "v3.4b apply 失败整批回滚（同批 create 行也没写）",
        point_count() == before_points,
        f"before={before_points} after={point_count()}",
    )
    p.check(
        "v3.4c 失败批次状态未置 confirmed（仍可重试）",
        api("GET", f"/knowledge-imports/{mid}").json()["state"] == "reviewing",
        f"state={api('GET', f'/knowledge-imports/{mid}').json()['state']}",
    )
    retry = api(
        "POST",
        f"/knowledge-imports/{mid}/confirm",
        json={
            "expectedRevision": mview["revision"],
            "submissionId": "v3-stale-retry",
            "actions": [
                {"rowNo": 1, "decision": "create"},
                {"rowNo": 2, "decision": "ignore"},
            ],
        },
    )
    p.check(
        "v3.4d 修正动作后重试成功（同批重试可用）",
        retry.status_code == 200 and [item["rowNo"] for item in retry.json()["created"]] == [1],
        f"{retry.status_code} {json.dumps(err(retry), ensure_ascii=False)[:200]}",
    )

    # ------------------------------------------------------------------ D 缺行动作 → 逐行定位 422
    mid_state = api("GET", f"/knowledge-imports/{mid}").json()
    no_action = api(
        "POST",
        f"/knowledge-imports/{mid}/confirm",
        json={"expectedRevision": mid_state["revision"], "submissionId": "v3-no-action"},
    )
    na_body = err(no_action)
    p.check(
        "v3.5a 已确认批次再确认 → 409 KNOWLEDGE_IMPORT_CONFIRMED",
        no_action.status_code == 409 and na_body.get("code") == "KNOWLEDGE_IMPORT_CONFIRMED",
        f"{no_action.status_code} {na_body.get('code')}",
    )

    pending = upload(
        "pending.csv",
        csv_bytes(["编码", "名称"], [["D-01", "D 行"], ["D-02", "D 行2"]]),
        "text/csv",
    )
    pview = pending.json()
    missing_actions = api(
        "POST",
        f"/knowledge-imports/{pview['importId']}/confirm",
        json={"expectedRevision": pview["revision"], "submissionId": "v3-missing-actions"},
    )
    ma_body = err(missing_actions)
    issues = (ma_body.get("details") or {}).get("issues") or []
    p.check(
        "v3.5b 行缺决定 → 422 KNOWLEDGE_ROW_INVALID + 逐行定位（rows 1/2 都在 issues）",
        missing_actions.status_code == 422
        and ma_body.get("code") == "KNOWLEDGE_ROW_INVALID"
        and sorted({item["row"] for item in issues}) == [1, 2],
        f"{missing_actions.status_code} {json.dumps(ma_body, ensure_ascii=False)[:300]}",
    )
    p.check("v3.5c 缺决定时零写入", point_count() == 3, f"points={point_count()}")

    # ------------------------------------------------------------------ E CSV + 手工映射
    csv_view = pending.json()
    p.check(
        "v3.6a CSV 上传成功（表头自动映射）",
        pending.status_code == 201 and csv_view["mapping"] == {"code": "编码", "name": "名称"},
        json.dumps({"status": pending.status_code, "mapping": csv_view["mapping"]}, ensure_ascii=False),
    )
    manual = upload(
        "manual.csv",
        csv_bytes(["甲", "乙"], [["E-01", "E 名"]]),
        "text/csv",
    )
    mview2 = manual.json()
    p.check(
        "v3.6b 无法自动识别的表头 → 缺必需列 issue（code/name）",
        manual.status_code == 201
        and mview2["mapping"] == {}
        and {issue.get("field") for issue in mview2["issues"]} >= {"code", "name"},
        json.dumps({"mapping": mview2["mapping"], "issues": mview2["issues"]}, ensure_ascii=False)[:400],
    )
    patched = api(
        "PATCH",
        f"/knowledge-imports/{mview2['importId']}",
        json={"expectedRevision": mview2["revision"], "mapping": {"code": "甲", "name": "乙"}},
    )
    pcheck_body = patched.json()
    p.check(
        "v3.6c 手工映射后重算行（code/name 就位、批次 issues 清空）",
        patched.status_code == 200
        and pcheck_body["mapping"] == {"code": "甲", "name": "乙"}
        and pcheck_body["rows"][0]["code"] == "E-01"
        and pcheck_body["rows"][0]["name"] == "E 名"
        and pcheck_body["issues"] == [],
        json.dumps({"mapping": pcheck_body.get("mapping"), "row": pcheck_body["rows"][0] if pcheck_body.get("rows") else None}, ensure_ascii=False)[:400],
    )
    bad_map = api(
        "PATCH",
        f"/knowledge-imports/{mview2['importId']}",
        json={"expectedRevision": pcheck_body["revision"], "mapping": {"code": "不存在列"}},
    )
    p.check(
        "v3.6d 映射不存在列 → 422 + details.fields 定位",
        bad_map.status_code == 422 and "不存在列" in json.dumps(err(bad_map), ensure_ascii=False),
        f"{bad_map.status_code} {json.dumps(err(bad_map), ensure_ascii=False)[:250]}",
    )
    bad_field = api(
        "PATCH",
        f"/knowledge-imports/{mview2['importId']}",
        json={"expectedRevision": pcheck_body["revision"], "mapping": {"unknownField": "甲"}},
    )
    p.check(
        "v3.6e 映射未知字段 → 422 INVALID_REQUEST",
        bad_field.status_code == 422 and err(bad_field).get("code") == "INVALID_REQUEST",
        f"{bad_field.status_code} {err(bad_field).get('code')}",
    )
    csv_confirm = api(
        "POST",
        f"/knowledge-imports/{mview2['importId']}/confirm",
        json={"expectedRevision": pcheck_body["revision"], "submissionId": "v3-csv-manual", "actions": [{"rowNo": 1, "decision": "create"}]},
    )
    p.check(
        "v3.6f 手工映射批次确认入库成功",
        csv_confirm.status_code == 200 and len(csv_confirm.json()["created"]) == 1,
        f"{csv_confirm.status_code} {json.dumps(err(csv_confirm), ensure_ascii=False)[:200]}",
    )

    # ------------------------------------------------------------------ F create 撞既有 code
    conflict_sheet = xlsx(["编码", "名称"], [["E-01", "撞车"]])
    conflict = upload("conflict.xlsx", conflict_sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    cf_view = conflict.json()
    cf_row = cf_view["rows"][0]
    p.check(
        "v3.7a 既有 code 的行自动落 update 目标（不会误 create）",
        cf_row["targetKnowledgePointId"] is not None and cf_row["decision"] == "update",
        json.dumps(cf_row, ensure_ascii=False)[:300],
    )
    cf_confirm = api(
        "POST",
        f"/knowledge-imports/{cf_view['importId']}/confirm",
        json={"expectedRevision": cf_view["revision"], "submissionId": "v3-force-create", "actions": [{"rowNo": 1, "decision": "create"}]},
    )
    cf_body = err(cf_confirm)
    p.check(
        "v3.7b 强行 create 既有 code → 422 KNOWLEDGE_CODE_CONFLICT（逐行定位）",
        cf_confirm.status_code == 422
        and cf_body.get("code") == "KNOWLEDGE_IMPORT_BLOCKING_ISSUES"
        and any(issue.get("code") == "KNOWLEDGE_CODE_CONFLICT" for issue in (cf_body.get("details") or {}).get("issues") or []),
        f"{cf_confirm.status_code} {json.dumps(cf_body, ensure_ascii=False)[:400]}",
    )

    # ------------------------------------------------------------------ G 批次列表/详情/上传校验
    imports_list = api("GET", "/knowledge-imports", params={"limit": 100})
    p.check(
        "v3.8a 批次列表形状 {items,total,offset,limit} 且摘要含 rowCount/blockingIssueCount",
        imports_list.status_code == 200
        and set(imports_list.json()) == {"items", "total", "offset", "limit"}
        and all({"rowCount", "blockingIssueCount"} <= set(item) for item in imports_list.json()["items"]),
        json.dumps(imports_list.json()["items"][:1], ensure_ascii=False)[:300],
    )
    detail = api("GET", f"/knowledge-imports/{cid}")
    p.check(
        "v3.8b 已确认批次详情 state=confirmed（列表/详情可读）",
        detail.status_code == 200 and detail.json()["state"] == "confirmed",
        f"{detail.status_code} {detail.json().get('state')}",
    )
    no_subject = api("POST", "/knowledge-imports", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    p.check(
        "v3.8c 缺 subjectId → 422 INVALID_REQUEST（不猜学科）",
        no_subject.status_code == 422 and err(no_subject).get("code") == "INVALID_REQUEST",
        f"{no_subject.status_code} {err(no_subject).get('code')}",
    )
    bad_format = upload(
        "x.docx",
        b"not a table",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    p.check(
        "v3.8d 不支持的格式 → 422 UNSUPPORTED_DOCUMENT_FORMAT",
        bad_format.status_code == 422 and err(bad_format).get("code") == "UNSUPPORTED_DOCUMENT_FORMAT",
        f"{bad_format.status_code} {err(bad_format).get('code')}",
    )
    txt_like = upload("notes.txt", b"not a table", "text/plain")
    p.check(
        "v3.8e .txt + text/plain 被当作 CSV 解析（read_table 声明的 CSV 媒体类型；记录为 observation）",
        txt_like.status_code == 201 and txt_like.json()["rows"] == [],
        f"{txt_like.status_code} rows={len(txt_like.json().get('rows', []))}",
    )
finally:
    client.__exit__(None, None, None)

sys.exit(p.finish())
