"""V2r2 F1 窄复验探针（TEACHING-LOOP B1 r2 / V00）。

F1 修复复验（r1 的两条最小场景 + 触发器/仓储兜底 + 导入环 + 合法改父回归）：
  1. 自指（parentId / parentCode 两种入参）→ 422 KNOWLEDGE_PARENT_INVALID + details.issues[0].field 按入参；
  2. 成环（parentId / parentCode 两种入参）→ 422 KNOWLEDGE_CYCLE + details.issues[0].field 按入参；
  3. 绕过服务层预检直写仓储 → 同样形状的 422 KNOWLEDGE_CYCLE（触发器兜底 + translate_integrity_error）；
  4. 裸 SQL 造环 → DB 触发器仍 RAISE(ABORT,'KNOWLEDGE_CYCLE')；裸 SQL 自指 → CHECK 约束仍拒；
  5. 导入批内 parentCode 成环 → 行动 issues field=parentCode、确认 422 且零写入；
  6. 合法改父（含跨分支、同父不变）仍 200（预检不过度拒绝）。
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v2r2_f1")
root = temp_data_root("v2r2")
ensure_api_on_path()

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.knowledge.catalog import KnowledgeCatalog  # noqa: E402
from app.repositories.knowledge.points import KnowledgePointRepository  # noqa: E402

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


def issue_of(body: dict, index: int = 0) -> dict:
    return ((body.get("details") or {}).get("issues") or [{}])[index]


def point_count() -> int:
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
    finally:
        conn.close()


def xlsx(headers: list[str], rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


try:
    # ------------------------------------------------------------------ 建树 A → B → C
    a = api("POST", "/knowledge-points", json={"subjectId": "math", "code": "A", "name": "A 根"}).json()
    b = api(
        "POST", "/knowledge-points",
        json={"subjectId": "math", "code": "B", "name": "B 子", "parentCode": "A"},
    ).json()
    c = api(
        "POST", "/knowledge-points",
        json={"subjectId": "math", "code": "C", "name": "C 孙", "parentCode": "B"},
    ).json()
    p.check(
        "v2r2.0 建树成功（B.parent=A, C.parent=B）",
        b["parentId"] == a["id"] and c["parentId"] == b["id"],
        json.dumps({"B.parent": b["parentId"], "A.id": a["id"], "C.parent": c["parentId"], "B.id": b["id"]}),
    )

    def current(point_id: str) -> dict:
        return api("GET", f"/knowledge-points/{point_id}").json()

    # ------------------------------------------------------------------ 1 自指
    a_now = current(a["id"])
    self_id = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentId": a["id"]},
    )
    self_id_body = err(self_id)
    p.check(
        "v2r2.1 自指（parentId）→ 422 KNOWLEDGE_PARENT_INVALID + issues[0].field=parentId",
        self_id.status_code == 422
        and self_id_body.get("code") == "KNOWLEDGE_PARENT_INVALID"
        and issue_of(self_id_body).get("field") == "parentId",
        f"{self_id.status_code} {json.dumps(self_id_body, ensure_ascii=False)[:300]}",
    )
    p.check(
        "v2r2.1b 自指（parentId）错误带可读 message 且无部分写入",
        "自身" in str(issue_of(self_id_body).get("message"))
        and current(a["id"])["revision"] == a_now["revision"],
        json.dumps({"message": issue_of(self_id_body).get("message"), "revision": current(a["id"])["revision"]}, ensure_ascii=False),
    )

    a_now = current(a["id"])
    self_code = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentCode": "A"},
    )
    self_code_body = err(self_code)
    p.check(
        "v2r2.2 自指（parentCode）→ 422 KNOWLEDGE_PARENT_INVALID + issues[0].field=parentCode",
        self_code.status_code == 422
        and self_code_body.get("code") == "KNOWLEDGE_PARENT_INVALID"
        and issue_of(self_code_body).get("field") == "parentCode",
        f"{self_code.status_code} {json.dumps(self_code_body, ensure_ascii=False)[:300]}",
    )

    # ------------------------------------------------------------------ 2 成环
    a_now = current(a["id"])
    cycle_id = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentId": c["id"]},
    )
    cycle_id_body = err(cycle_id)
    p.check(
        "v2r2.3 成环（parentId 指向孙节点）→ 422 KNOWLEDGE_CYCLE + issues[0].field=parentId",
        cycle_id.status_code == 422
        and cycle_id_body.get("code") == "KNOWLEDGE_CYCLE"
        and issue_of(cycle_id_body).get("field") == "parentId",
        f"{cycle_id.status_code} {json.dumps(cycle_id_body, ensure_ascii=False)[:300]}",
    )
    p.check(
        "v2r2.3b 成环被拒后父关系与 revision 不变（无部分写入）",
        current(a["id"])["parentId"] is None and current(a["id"])["revision"] == a_now["revision"],
        json.dumps({"parentId": current(a["id"])["parentId"], "revision": current(a["id"])["revision"]}),
    )

    a_now = current(a["id"])
    cycle_code = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentCode": "C"},
    )
    cycle_code_body = err(cycle_code)
    p.check(
        "v2r2.4 成环（parentCode）→ 422 KNOWLEDGE_CYCLE + issues[0].field=parentCode",
        cycle_code.status_code == 422
        and cycle_code_body.get("code") == "KNOWLEDGE_CYCLE"
        and issue_of(cycle_code_body).get("field") == "parentCode",
        f"{cycle_code.status_code} {json.dumps(cycle_code_body, ensure_ascii=False)[:300]}",
    )

    # 直接子节点（B 的父是 A）也可成环：把 B 挂到 C → A→B→C→B 环
    b_now = current(b["id"])
    cycle_mid = api(
        "PATCH", f"/knowledge-points/{b['id']}",
        json={"expectedRevision": b_now["revision"], "parentId": c["id"]},
    )
    cm_body = err(cycle_mid)
    p.check(
        "v2r2.4b 中间节点成环（B→C）同样 422 KNOWLEDGE_CYCLE + field=parentId",
        cycle_mid.status_code == 422
        and cm_body.get("code") == "KNOWLEDGE_CYCLE"
        and issue_of(cm_body).get("field") == "parentId",
        f"{cycle_mid.status_code} {json.dumps(cm_body, ensure_ascii=False)[:250]}",
    )

    # ------------------------------------------------------------------ 3 绕过服务层：仓储直写
    catalog = KnowledgeCatalog(DB)
    catalog.migrate()  # 直接构造的 catalog 需先迁移（幂等）才允许写事务
    repo = KnowledgePointRepository()
    a_now = current(a["id"])
    repo_error = None
    try:
        with catalog.write_transaction() as conn:
            repo.update_point(conn, a["id"], expected_revision=a_now["revision"], parent_id=c["id"])
    except AppError as exc:
        repo_error = exc
    p.check(
        "v2r2.5 仓储直写（绕过服务层预检）→ 422 KNOWLEDGE_CYCLE + details.issues[0].field=parentId",
        repo_error is not None
        and repo_error.code == "KNOWLEDGE_CYCLE"
        and repo_error.status_code == 422
        and ((repo_error.details or {}).get("issues") or [{}])[0].get("field") == "parentId",
        f"{type(repo_error).__name__}: {getattr(repo_error, 'code', None)} details={(repo_error.details if repo_error else None)}",
    )
    repo_self = None
    a_now = current(a["id"])
    try:
        with catalog.write_transaction() as conn:
            repo.update_point(conn, a["id"], expected_revision=a_now["revision"], parent_id=a["id"])
    except AppError as exc:
        repo_self = exc
    p.check(
        "v2r2.5c 仓储直写自指 → 422 KNOWLEDGE_PARENT_INVALID + details.issues[0].field=parentId",
        repo_self is not None
        and repo_self.code == "KNOWLEDGE_PARENT_INVALID"
        and repo_self.status_code == 422
        and ((repo_self.details or {}).get("issues") or [{}])[0].get("field") == "parentId",
        f"{type(repo_self).__name__}: {getattr(repo_self, 'code', None)} details={(repo_self.details if repo_self else None)}",
    )
    p.check(
        "v2r2.5d 仓储拒绝后树与 revision 未变",
        current(a["id"])["parentId"] is None and current(a["id"])["revision"] == a_now["revision"],
        json.dumps({"parentId": current(a["id"])["parentId"], "revision": current(a["id"])["revision"]}),
    )

    # ------------------------------------------------------------------ 4 裸 SQL：触发器 / CHECK 兜底
    conn = sqlite3.connect(str(DB))
    conn.isolation_level = None
    trigger_error = None
    try:
        conn.execute("SAVEPOINT sp_cycle")
        conn.execute("UPDATE knowledge_points SET parent_id = ? WHERE id = ?", (c["id"], a["id"]))
    except sqlite3.IntegrityError as exc:
        trigger_error = str(exc)
    finally:
        conn.execute("ROLLBACK TO sp_cycle")
        conn.execute("RELEASE sp_cycle")
    check_error = None
    try:
        conn.execute("SAVEPOINT sp_self")
        conn.execute("UPDATE knowledge_points SET parent_id = id WHERE id = ?", (a["id"],))
    except sqlite3.IntegrityError as exc:
        check_error = str(exc)
    finally:
        conn.execute("ROLLBACK TO sp_self")
        conn.execute("RELEASE sp_self")
    check_ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='knowledge_points'"
    ).fetchone()[0]
    conn.close()
    p.check(
        "v2r2.6 DB 触发器仍兜底（裸 SQL 造环 → RAISE KNOWLEDGE_CYCLE）",
        trigger_error is not None and "KNOWLEDGE_CYCLE" in trigger_error,
        f"{trigger_error}",
    )
    p.check(
        "v2r2.6b 裸 SQL 自指仍被 DB 拒绝（实测触发器先报 KNOWLEDGE_CYCLE；CHECK 为第二道）",
        check_error is not None and ("KNOWLEDGE_CYCLE" in check_error or "parent_id" in check_error),
        f"{check_error}",
    )
    p.check(
        "v2r2.6c DDL 仍保留 CHECK(parent_id IS NULL OR parent_id<>id)",
        "CHECK(parent_id IS NULL OR parent_id<>id)" in check_ddl.replace("  ", " "),
        json.dumps([line.strip() for line in check_ddl.splitlines() if "CHECK(parent_id" in line]),
    )

    # ------------------------------------------------------------------ 5 导入批内环
    before_points = point_count()
    sheet = xlsx(
        ["编码", "名称", "父级"],
        [["X-01", "X 环一", "X-02"], ["X-02", "X 环二", "X-01"], ["X-03", "X 正常", None]],
    )
    imported = api(
        "POST", "/knowledge-imports",
        files={"file": ("cycle.xlsx", sheet, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"subjectId": "math"},
    )
    view = imported.json()
    cycle_rows = [row for row in view["rows"] if row["rowNo"] in (1, 2)]
    p.check(
        "v2r2.7 导入预览：批内成环行带 KNOWLEDGE_CYCLE + field=parentCode",
        imported.status_code == 201
        and all(
            any(issue["code"] == "KNOWLEDGE_CYCLE" and issue.get("field") == "parentCode" for issue in row["issues"])
            for row in cycle_rows
        ),
        json.dumps([row["issues"] for row in cycle_rows], ensure_ascii=False)[:400],
    )
    confirm = api(
        "POST", f"/knowledge-imports/{view['importId']}/confirm",
        json={
            "expectedRevision": view["revision"],
            "submissionId": "v2r2-cycle",
            "actions": [
                {"rowNo": 1, "decision": "create"},
                {"rowNo": 2, "decision": "create"},
                {"rowNo": 3, "decision": "create"},
            ],
        },
    )
    confirm_body = err(confirm)
    p.check(
        "v2r2.8 导入确认：批内环 → 422 KNOWLEDGE_IMPORT_BLOCKING_ISSUES + issues[].field=parentCode",
        confirm.status_code == 422
        and confirm_body.get("code") == "KNOWLEDGE_IMPORT_BLOCKING_ISSUES"
        and any(
            issue.get("code") == "KNOWLEDGE_CYCLE" and issue.get("field") == "parentCode"
            for issue in (confirm_body.get("details") or {}).get("issues") or []
        ),
        f"{confirm.status_code} {json.dumps(confirm_body, ensure_ascii=False)[:400]}",
    )
    p.check(
        "v2r2.9 导入环阻断时零写入（含同批正常行）",
        point_count() == before_points,
        f"before={before_points} after={point_count()}",
    )

    # ------------------------------------------------------------------ 6 合法改父回归
    c_now = current(c["id"])
    move_ok = api(
        "PATCH", f"/knowledge-points/{c['id']}",
        json={"expectedRevision": c_now["revision"], "parentCode": "A"},
    )
    p.check(
        "v2r2.10 合法改父（C 挂到 A，跨层上移）→ 200 且父关系更新",
        move_ok.status_code == 200
        and move_ok.json()["parentId"] == a["id"]
        and move_ok.json()["parentCode"] == "A",
        f"{move_ok.status_code} {json.dumps({k: move_ok.json().get(k) for k in ('parentId', 'parentCode')})}",
    )
    b_now = current(b["id"])
    move_b = api(
        "PATCH", f"/knowledge-points/{b['id']}",
        json={"expectedRevision": b_now["revision"], "parentCode": "C"},
    )
    p.check(
        "v2r2.11 合法改父（B 挂到 C，按当前树判定不成环）→ 200",
        move_b.status_code == 200 and move_b.json()["parentId"] == c["id"],
        f"{move_b.status_code} {json.dumps(err(move_b), ensure_ascii=False)[:200]}",
    )
    # 当前树：A 根 → C → B（v2r2.11 后）；把 C 挂到自己的子节点 B → 2 节点环
    c_now = current(c["id"])
    cycle_after = api(
        "PATCH", f"/knowledge-points/{c['id']}",
        json={"expectedRevision": c_now["revision"], "parentCode": "B"},
    )
    ca_body = err(cycle_after)
    p.check(
        "v2r2.12 改父后新树成环（C→B 与 B→C 冲突）→ 422 KNOWLEDGE_CYCLE + field=parentCode",
        cycle_after.status_code == 422
        and ca_body.get("code") == "KNOWLEDGE_CYCLE"
        and issue_of(ca_body).get("field") == "parentCode",
        f"{cycle_after.status_code} {json.dumps(ca_body, ensure_ascii=False)[:300]}",
    )
    p.check(
        "v2r2.12b 新树形下合法改父仍 200（B 挂到 A：A 无父，非环）",
        (lambda r: r.status_code == 200 and r.json()["parentCode"] == "A")(
            api("PATCH", f"/knowledge-points/{b['id']}", json={"expectedRevision": current(b["id"])["revision"], "parentCode": "A"})
        ),
        "valid move after cycle rejection",
    )
    a_now = current(a["id"])
    self_after = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentCode": "A"},
    )
    p.check(
        "v2r2.13 自指（改父后仍生效）→ 422 KNOWLEDGE_PARENT_INVALID + field=parentCode",
        self_after.status_code == 422
        and err(self_after).get("code") == "KNOWLEDGE_PARENT_INVALID"
        and issue_of(err(self_after)).get("field") == "parentCode",
        f"{self_after.status_code} {json.dumps(err(self_after), ensure_ascii=False)[:250]}",
    )

    # 其它既有行为未被 F1 改动破坏（抽两条）
    p.check(
        "v2r2.14 未改父的普通更新不受预检影响（改 name 200）",
        (lambda r: r.status_code == 200 and r.json()["parentId"] == current(a["id"])["parentId"])(
            api("PATCH", f"/knowledge-points/{a['id']}", json={"expectedRevision": current(a["id"])["revision"], "name": "A 根改名"})
        ),
        "edit without parent change",
    )
    a_now = current(a["id"])
    cross = api(
        "PATCH", f"/knowledge-points/{a['id']}",
        json={"expectedRevision": a_now["revision"], "parentCode": "NOPE"},
    )
    cross_body = err(cross)
    p.check(
        "v2r2.15 缺父（parentCode）仍 422 KNOWLEDGE_PARENT_INVALID + field=parentCode（未被 F1 改动）",
        cross.status_code == 422
        and cross_body.get("code") == "KNOWLEDGE_PARENT_INVALID"
        and issue_of(cross_body).get("field") == "parentCode",
        f"{cross.status_code} {json.dumps(cross_body, ensure_ascii=False)[:250]}",
    )
finally:
    client.__exit__(None, None, None)

sys.exit(p.finish())
