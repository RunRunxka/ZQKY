"""V00-B2 · V3 独立探针：T40 确认闸门与确认后不可变。

覆盖：
  闸门逐项拒绝（未归属块 / blocking issue / 无叶子 / 总分不符 / 缺知识点 / 已确认重复确认 /
  submissionId 冲突 / expectedRevision 过期）→ 修正后成功；
  同 submissionId 重放（replayed=True，不重复写）；
  确认后**绕过服务**直写 UPDATE/DELETE/INSERT（items/knowledge/blocks/issues/revisions）被触发器拒绝；
  改已确认卷自动新建 draft 修订，旧修订逐字节不变；
  旧施测仍引旧修订（真实创建）。
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v3-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:220]}")
    return ok


def err(response) -> tuple[int, str, dict]:
    body = response.json()
    error = body.get("error") or body
    return response.status_code, error.get("code"), error.get("details") or {}


def raw(har, sql: str, params=()):
    conn = har.db("teaching")
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def try_sql(har, sql: str, params=()) -> tuple[bool, str]:
    conn = har.db("teaching")
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(sql, params)
        conn.commit()
        return True, ""
    except sqlite3.Error as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    finally:
        conn.close()


def confirm(har, paper_id: str, revision: int, submission_id: str):
    return har.client.post(f"/api/v1/papers/{paper_id}/confirm",
                           json={"expectedRevision": revision, "submissionId": submission_id})


def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v3-work-"))
    sample = S.build_sample_docx(work / "v00-sample.docx")
    har, _provider = S.new_harness("v3")
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")

    state = S.prepare_ready_draft(har, sample, point_a=point_a, point_b=point_b)
    paper_id, revision_id = state["paper_id"], state["revision_id"]
    check("V3.1 可确认草稿就绪（4 题 / 1500 单位 / 归属齐全）",
          state["total_score_units"] == 1500 and len(state["item_views"]) == 4,
          f"total={state['total_score_units']} items={len(state['item_views'])}")

    # ---------------------------------------------------------------- 闸门拒绝
    conn = har.db("teaching")
    try:
        rows = conn.execute(
            "SELECT id, item_id FROM paper_source_blocks WHERE paper_revision_id=? ORDER BY ordinal",
            (revision_id,)).fetchall()
    finally:
        conn.close()
    block_ids = {row["id"].split(":", 1)[1]: row["id"] for row in rows}
    reassign = {
        "p3": state["items"]["16"], "p4": state["items"]["16(1)"], "p5": state["items"]["16(2)"],
        "p6": state["items"]["16(2)"], "p6-1": state["items"]["16(2)"], "p7": state["items"]["16(2)"],
        "t8": state["items"]["16(2)"], "p9": state["items"]["17"], "p10": state["items"]["17"],
        "p10-1": state["items"]["17"],
    }
    patch_blocks = []
    for parser_id, namespaced in block_ids.items():
        if parser_id in ("p1", "p2"):
            patch_blocks.append({"blockId": namespaced, "disposition": "shared_material"})
        elif parser_id == "p13":
            patch_blocks.append({"blockId": namespaced, "disposition": "excluded",
                                 "excludeReason": "V00：解析损失，人工排除。"})
        else:
            patch_blocks.append({"blockId": namespaced, "disposition": "item",
                                 "itemId": reassign[parser_id]})
    items_payload = [
        {"itemId": state["items"]["16"], "questionNo": "16", "ordinal": 1, "isScored": False,
         "content": {}, "sourceLocator": {}, "knowledge": []},
        {"itemId": state["items"]["16(1)"], "parentItemId": state["items"]["16"], "questionNo": "16(1)",
         "ordinal": 2, "isScored": True, "maxScore": "4", "content": {}, "sourceLocator": {},
         "knowledge": [{"knowledgePointId": point_a}]},
        {"itemId": state["items"]["16(2)"], "parentItemId": state["items"]["16"], "questionNo": "16(2)",
         "ordinal": 3, "isScored": True, "maxScore": "6", "content": {}, "sourceLocator": {},
         "knowledge": [{"knowledgePointId": point_b}]},
        {"itemId": state["items"]["17"], "questionNo": "17", "ordinal": 4, "isScored": True,
         "maxScore": "5", "content": {}, "sourceLocator": {},
         "knowledge": [{"knowledgePointId": point_a}]},
    ]

    def patch_draft(body, *, label):
        """前置补丁：必须 200，且仍作用于同一草稿修订（不发生意外 fork）。"""
        current = har.client.get(f"/api/v1/papers/{paper_id}").json()
        response = har.client.patch(f"/api/v1/papers/{paper_id}/draft",
                                    json={"expectedRevision": current["revision"], **body})
        ok = response.status_code == 200 and response.json().get("paperRevisionId") == revision_id
        check(f"{label}（前置补丁 200 且未 fork）", ok,
              f"{response.status_code} rev={str(response.json().get('paperRevisionId'))[:8]} {response.text[:120]}")
        return response

    gate_state = {"ok": True, "n": 0}

    def gate_expect(name, expect_status, expect_code, *, field=None, need_row=False):
        """在当前草稿上提交确认，断言闸门拒绝且草稿状态未被改变。"""
        if not gate_state["ok"]:
            check(name, False, "跳过：先前的闸门用例意外成功（状态已非 draft）")
            return None
        current = har.client.get(f"/api/v1/papers/{paper_id}").json()
        if current["currentState"] != "draft":
            gate_state["ok"] = False
            check(name, False, "前置状态已非 draft（闸门未拦住）")
            return None
        gate_state["n"] += 1
        response = confirm(har, paper_id, current["revision"], f"v00-gate-{gate_state['n']}")
        status, code, details = err(response)
        after = har.client.get(f"/api/v1/papers/{paper_id}").json()
        still_draft = after["currentState"] == "draft" and after["revision"] == current["revision"]
        ok = status == expect_status and code == expect_code and still_draft
        detail = f"{status}/{code} still_draft={still_draft}"
        if ok and field is not None:
            issues = details.get("issues") or []
            ok = any(issue.get("field") == field for issue in issues)
            detail += f" field={field}:{any(i.get('field') == field for i in issues)}"
        if ok and need_row:
            ok = any(issue.get("row") is not None for issue in details.get("issues") or [])
            detail += f" rows={[i.get('row') for i in details.get('issues') or []]}"
        if expect_code == "PAPER_REVISION_STALE":
            ok = ok and details.get("currentRevision") == current["revision"]
            detail += f" currentRevision={details.get('currentRevision')}"
        check(name, ok, detail)
        if not ok:
            gate_state["ok"] = False
        return response

    # (a) 未归属块（草稿期可改回 unassigned）
    patch_draft({"items": items_payload,
                 "blocks": [{"blockId": block_ids["p3"], "disposition": "unassigned"}]},
                label="V3.2a 把 p3 改回 unassigned")
    gate_expect("V3.2 存在未归属块 → 422 PAPER_BLOCK_UNASSIGNED（带块序号定位）",
                422, "PAPER_BLOCK_UNASSIGNED", need_row=True)
    patch_draft({"blocks": patch_blocks}, label="V3.2b 复原 p3 归属（全表重发）")

    # (b) 缺知识点
    patch_draft({"items": [items_payload[0], dict(items_payload[1], knowledge=[]),
                           items_payload[2], items_payload[3]]},
                label="V3.4a 去掉 16(1) 的知识点")
    gate_expect("V3.4 计分叶缺知识点 → 422 ITEM_KNOWLEDGE_MISSING（逐题定位）",
                422, "ITEM_KNOWLEDGE_MISSING", need_row=True)
    patch_draft({"items": items_payload}, label="V3.4b 恢复知识点")

    # (c) 无计分叶子
    none_scored = [
        dict(items_payload[0]),
        {"itemId": state["items"]["16(1)"], "parentItemId": state["items"]["16"], "questionNo": "16(1)",
         "ordinal": 2, "isScored": False, "content": {}, "sourceLocator": {}, "knowledge": []},
        {"itemId": state["items"]["16(2)"], "parentItemId": state["items"]["16"], "questionNo": "16(2)",
         "ordinal": 3, "isScored": False, "content": {}, "sourceLocator": {}, "knowledge": []},
        {"itemId": state["items"]["17"], "questionNo": "17", "ordinal": 4, "isScored": False,
         "content": {}, "sourceLocator": {}, "knowledge": []},
    ]
    patch_draft({"items": none_scored}, label="V3.5a 全部改不计分")
    gate_expect("V3.5 无计分叶子 → 422 NO_SCORED_ITEMS", 422, "NO_SCORED_ITEMS")
    patch_draft({"items": items_payload}, label="V3.5b 恢复计分")

    # (d) 总分不符：绕过服务直改草稿总分（闸门本身）
    conn = har.db("teaching")
    try:
        conn.execute("UPDATE paper_revisions SET total_score_units=99 WHERE id=?", (revision_id,))
        conn.commit()
    finally:
        conn.close()
    gate_expect("V3.6 草稿总分与叶子合计不符 → 422 PAPER_TOTAL_MISMATCH",
                422, "PAPER_TOTAL_MISMATCH")
    conn = har.db("teaching")
    try:
        conn.execute("UPDATE paper_revisions SET total_score_units=1500 WHERE id=?", (revision_id,))
        conn.commit()
    finally:
        conn.close()

    # (e) blocking 问题未解决
    conn = har.db("teaching")
    try:
        conn.execute("UPDATE paper_issues SET status='open' WHERE paper_revision_id=? AND severity='blocking'",
                     (revision_id,))
        conn.commit()
    finally:
        conn.close()
    gate_expect("V3.7 仍有 open 的 blocking 问题 → 422 PAPER_ISSUE_BLOCKING",
                422, "PAPER_ISSUE_BLOCKING")
    conn = har.db("teaching")
    try:
        conn.execute("UPDATE paper_issues SET status='resolved', resolution_json='{\"note\":\"v00\"}' "
                     "WHERE paper_revision_id=? AND severity='blocking'", (revision_id,))
        conn.commit()
    finally:
        conn.close()

    # (f) expectedRevision 过期
    current = har.client.get(f"/api/v1/papers/{paper_id}").json()
    stale = confirm(har, paper_id, current["revision"] + 3, "v00-gate-stale")
    status, code, details = err(stale)
    check("V3.8 expectedRevision 过期 → 409 PAPER_REVISION_STALE + currentRevision",
          stale.status_code == 409 and code == "PAPER_REVISION_STALE"
          and details.get("currentRevision") == current["revision"],
          f"{status}/{code} {details}")

    # ---------------------------------------------------------------- 成功 + 幂等
    current = har.client.get(f"/api/v1/papers/{paper_id}").json()
    check("V3.9a 闸门用例全部被拒且草稿仍可确认",
          gate_state["ok"] and current["currentState"] == "draft",
          f"gate_ok={gate_state['ok']} state={current['currentState']}")
    ok = confirm(har, paper_id, current["revision"], "v00-confirm-ok")
    check("V3.9 闸门全过 → 确认成功", ok.status_code == 200 and ok.json()["state"] == "confirmed"
          and ok.json()["totalScoreUnits"] == 1500 and ok.json()["scoredLeafCount"] == 3,
          f"{ok.status_code} {ok.text[:160]}")
    confirmed_revision_id = ok.json()["paperRevisionId"]
    replay = confirm(har, paper_id, current["revision"], "v00-confirm-ok")
    check("V3.10 同 submissionId 重放 → replayed=True 且结果一致",
          replay.status_code == 200 and replay.json()["replayed"] is True
          and replay.json()["paperRevisionId"] == confirmed_revision_id,
          f"{replay.status_code} {replay.text[:160]}")
    paper_view = har.client.get(f"/api/v1/papers/{paper_id}").json()
    check("V3.11 确认后 currentState=confirmed 且 papers.revision +1",
          paper_view["currentState"] == "confirmed" and paper_view["revision"] == current["revision"] + 1,
          f"{paper_view['currentState']} rev={paper_view['revision']}")

    conflict = har.client.post(f"/api/v1/papers/{paper_id}/confirm",
                               json={"expectedRevision": current["revision"] + 1, "submissionId": "v00-confirm-ok"})
    status, code, _details = err(conflict)
    check("V3.12 同 submissionId 不同载荷 → 409（SUBMISSION_CONFLICT / 已确认）",
          conflict.status_code == 409 and code in ("SUBMISSION_CONFLICT", "PAPER_NOT_EDITABLE"),
          f"{status}/{code}")
    again = confirm(har, paper_id, current["revision"] + 1, "v00-confirm-again")
    status, code, _details = err(again)
    check("V3.13 新 submissionId 重复确认 → 409 PAPER_NOT_EDITABLE",
          again.status_code == 409 and code == "PAPER_NOT_EDITABLE", f"{status}/{code}")

    # ---------------------------------------------------------------- 绕过服务直写
    snapshot_before = S.revision_snapshot(har, confirmed_revision_id)
    item_id = state["items"]["16(1)"]
    bypass = [
        ("V3.14 直写 UPDATE paper_items 题号被拒",
         "UPDATE paper_items SET question_no='16(9)' WHERE id=?", (item_id,)),
        ("V3.15 直写 UPDATE paper_items 分值被拒",
         "UPDATE paper_items SET max_score_units=999 WHERE id=?", (item_id,)),
        ("V3.16 直写 DELETE paper_items 被拒",
         "DELETE FROM paper_items WHERE id=?", (item_id,)),
        ("V3.17 直写 INSERT paper_items 被拒",
         "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
         "max_score_units, content_json) VALUES ('v00x', ?, '99', 99, 1, 100, '{}')",
         (confirmed_revision_id,)),
        ("V3.18 直写 UPDATE paper_item_knowledge 被拒",
         "UPDATE paper_item_knowledge SET role='secondary' WHERE item_id=?", (item_id,)),
        ("V3.19 直写 DELETE paper_item_knowledge 被拒",
         "DELETE FROM paper_item_knowledge WHERE item_id=?", (item_id,)),
        ("V3.20 直写 INSERT paper_item_knowledge 被拒",
         "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
         "knowledge_revision_id, knowledge_name_snapshot, role, source) "
         "VALUES (?, ?, 'kpz', 'kpzr', 'K', 'primary', 'human')",
         (item_id, confirmed_revision_id)),
        ("V3.21 直写 UPDATE paper_source_blocks 归属被拒",
         "UPDATE paper_source_blocks SET disposition='item', item_id=? WHERE paper_revision_id=?",
         (item_id, confirmed_revision_id)),
        ("V3.22 直写 DELETE paper_source_blocks 被拒",
         "DELETE FROM paper_source_blocks WHERE paper_revision_id=?", (confirmed_revision_id,)),
        ("V3.23 直写 INSERT paper_source_blocks 被拒",
         "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json) "
         "VALUES ('v00b', ?, 99, 'paragraph', '{}')", (confirmed_revision_id,)),
        ("V3.24 直写 UPDATE paper_issues 被拒",
         "UPDATE paper_issues SET status='excluded' WHERE paper_revision_id=? AND severity='blocking'",
         (confirmed_revision_id,)),
        ("V3.25 直写 DELETE paper_issues 被拒",
         "DELETE FROM paper_issues WHERE paper_revision_id=?", (confirmed_revision_id,)),
        ("V3.26 直写 INSERT paper_issues 被拒",
         "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, created_at) "
         "VALUES ('v00i', ?, 'X', 'warning', 'm', '2026-10-01T00:00:00Z')", (confirmed_revision_id,)),
        ("V3.27 直写 UPDATE 已确认修订（改总分）被拒",
         "UPDATE paper_revisions SET total_score_units=1 WHERE id=?", (confirmed_revision_id,)),
        ("V3.28 直写 UPDATE 已确认修订（改回 draft）被拒",
         "UPDATE paper_revisions SET state='draft' WHERE id=?", (confirmed_revision_id,)),
        ("V3.29 直写 DELETE 已确认修订被拒",
         "DELETE FROM paper_revisions WHERE id=?", (confirmed_revision_id,)),
    ]
    for name, sql, params in bypass:
        ok_sql, message = try_sql(har, sql, params)
        check(name, (not ok_sql) and "IMMUTABLE_REVISION" in message, message[:150] or "语句被接受（缺陷）")
    snapshot_after = S.revision_snapshot(har, confirmed_revision_id)
    check("V3.30 绕过尝试后旧修订逐字节未变", snapshot_before["digest"] == snapshot_after["digest"],
          snapshot_before["digest"][:16])

    # ---------------------------------------------------------------- 旧施测仍引旧修订
    today = "2026-10-01"
    klass = har.client.post("/api/v1/classes", json={
        "code": "V00C1", "name": "高一(1)班", "schoolYear": "2026-2027", "gradeId": "senior-1"})
    check("V3.31 建班成功", klass.status_code == 201, f"{klass.status_code} {klass.text[:120]}")
    class_id = klass.json()["id"]
    student = har.client.post("/api/v1/students", json={
        "name": "张伟", "studentNo": "V0001", "classId": class_id, "joinedOn": "2026-09-01"})
    check("V3.32 建学生 + 归属成功", student.status_code == 201, f"{student.status_code} {student.text[:120]}")
    student_id = student.json()["id"]
    assessment = har.client.post("/api/v1/assessments", json={
        "submissionId": "v00-assessment-1",
        "paperRevisionId": confirmed_revision_id,
        "title": "V00 期中施测",
        "assessmentType": "exam",
        "heldOn": today,
        "classIds": [class_id],
        "participants": [{"studentId": student_id, "classId": class_id, "attendance": "present"}],
    })
    check("V3.33 旧修订可真实建立施测", assessment.status_code == 201,
          f"{assessment.status_code} {assessment.text[:200]}")

    # ---------------------------------------------------------------- 改已确认卷 → 新 draft 修订
    before_modify = har.client.get(f"/api/v1/papers/{paper_id}").json()
    modify = har.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={"expectedRevision": before_modify["revision"], "items": items_payload},
    )
    check("V3.34 改已确认卷自动新建 draft 修订", modify.status_code == 200
          and modify.json()["state"] == "draft" and modify.json()["version"] == 2,
          f"{modify.status_code} {modify.text[:200]}")
    check("V3.35 旧修订（v1）逐字节未变", S.revision_snapshot(har, confirmed_revision_id)["digest"]
          == snapshot_before["digest"], snapshot_before["digest"][:16])
    new_revision_id = modify.json()["paperRevisionId"] if modify.status_code == 200 else None
    check("V3.36 新草稿复制了旧内容（题数/总分一致）",
          modify.status_code == 200 and len(modify.json()["items"]) == 4
          and modify.json()["totalScoreUnits"] == 1500, str(len(modify.json().get("items", []))))
    if new_revision_id:
        conn = har.db("teaching")
        try:
            rows = conn.execute(
                "SELECT count(*) FROM paper_source_blocks WHERE paper_revision_id=?", (new_revision_id,)
            ).fetchone()[0]
            old_rows = conn.execute(
                "SELECT count(*) FROM paper_source_blocks WHERE paper_revision_id=?", (confirmed_revision_id,)
            ).fetchone()[0]
            old_state = conn.execute(
                "SELECT state FROM paper_revisions WHERE id=?", (confirmed_revision_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        check("V3.37 新修订块行独立复制且旧修订仍 confirmed",
              rows == old_rows == 13 and old_state == "confirmed", f"new={rows} old={old_rows} state={old_state}")

    assessment_id = assessment.json()["assessment"]["assessmentId"] if assessment.status_code == 201 else None
    detail = har.client.get(f"/api/v1/assessments/{assessment_id}").json() if assessment_id else {}
    check("V3.38 旧施测仍指旧修订（paper revision 未被改写）",
          detail.get("assessment", {}).get("paperRevisionId") == confirmed_revision_id,
          str(detail.get("assessment", {}).get("paperRevisionId")))

    har.client.close()
    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v3_papers_confirm_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v3_papers_confirm_probe", "results": RESULTS},
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
