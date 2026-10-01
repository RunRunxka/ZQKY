"""V00-B2 · V1 独立探针：迁移与分期 CHECK / 触发器 / 三路径升级 / 回滚 / 外键。

只读候选产品代码；全部资源在临时目录（ZQKY_DATA_DIR + tempfile），不触正式 .local-data。
不 import app.main（不需要应用装配），只用迁移登记表与 SQL 层。

覆盖：
  A 新库升级 + 幂等 + 表齐备 + foreign_key_check / quick_check
  B B0 旧库 / B1 旧库两条升级路径（旧库按"当时只应用了前置迁移"真实构造）
  C 中途失败整体回滚、不写登记
  D B0/B1 已登记散列：与 B0/B1 独立验收记录比对 + 与 B1 提交（git HEAD）源码逐语句比对
  E 分期 CHECK：source_practice_revision_id 非空拒 / source_file_id 空拒 /
    assessments.active_score_revision_id 非空拒
  F 触发器：paper_confirm 四分支、freeze_paper_*（UPDATE 归属/DELETE）、
    immutable_paper_revisions / no_direct_sealed、paper_cycle、assessment 两触发器
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]  # V00-probes -> TEACHING-LOOP-B2 -> qa -> docs -> 仓库根
API = REPO / "apps" / "api"
# 先设隔离数据根，再导入产品模块（本探针不 import app.main，但纪律一致）
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v1-"))
os.environ["ZQKY_DATA_DIR"] = str(_TMP_ROOT)
sys.path.insert(0, str(API))

from app.core.migrations import (  # noqa: E402
    REGISTERED_MIGRATIONS,
    Migration,
    applied_migrations,
    apply_migrations,
    statement_digest,
    verify_migrations,
)
from app.core.migrations import question_bank as qb_mod  # noqa: E402
from app.core.migrations import teaching as te_mod  # noqa: E402
from app.core.sqlite import connect, now_iso  # noqa: E402

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {detail}")
    return ok


def tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def triggers(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }


def rejects(conn: sqlite3.Connection, sql: str, params=()) -> tuple[bool, str]:
    """执行 SQL；被 SQLite 拒绝返回 (True, message)。"""
    try:
        conn.execute(sql, params)
    except sqlite3.Error as exc:
        return True, f"{exc.__class__.__name__}: {exc}"
    return False, ""


def legacy_db(path: Path, database: str, prefix: int) -> None:
    """真实构造"旧版应用只应用了前 prefix 条迁移"的库（登记行与声明散列同真实现）。"""
    conn = connect(path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)")
        for migration in REGISTERED_MIGRATIONS[database][:prefix]:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?,?,?)",
                (migration.id, migration.sha256, now_iso()),
            )
    finally:
        conn.close()


B2_TABLES = {
    "teaching": {
        "papers", "paper_revisions", "paper_items", "paper_item_knowledge",
        "paper_source_blocks", "paper_issues", "ai_proposals",
        "assessments", "assessment_classes", "assessment_participants",
    },
    "question_bank": {
        "question_knowledge_links", "question_draft_knowledge_links",
        "question_import_provenance", "question_content_fingerprints",
    },
}
FULL_IDS = {
    db: [m.id for m in REGISTERED_MIGRATIONS[db]] for db in ("teaching", "question_bank")
}


# --------------------------------------------------------------------------- A
def part_a(work: Path) -> None:
    for db in ("teaching", "question_bank"):
        path = work / f"A-{db}.sqlite3"
        conn = connect(path)
        try:
            applied = apply_migrations(conn, database=db)
            check(f"A1[{db}] 新库应用全部登记迁移", applied == FULL_IDS[db], f"applied={applied}")
            check(f"A2[{db}] 重复应用幂等（返回空）", apply_migrations(conn, database=db) == [], "second apply == []")
            check(f"A3[{db}] B2 新表齐备", B2_TABLES[db] <= tables(conn), f"missing={sorted(B2_TABLES[db] - tables(conn))}")
            check(f"A4[{db}] foreign_key_check 为空", conn.execute("PRAGMA foreign_key_check").fetchall() == [], "0 rows")
            check(f"A5[{db}] quick_check ok", conn.execute("PRAGMA quick_check").fetchone()[0] == "ok", "ok")
            n = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
            check(f"A6[{db}] 登记行数 = 迁移条数", n == len(FULL_IDS[db]), f"{n} rows")
            verify_migrations(conn, database=db)
            check(f"A7[{db}] verify_migrations 不报漂移", True, "no drift")
        finally:
            conn.close()


# --------------------------------------------------------------------------- B
def part_b(work: Path) -> None:
    for db in ("teaching", "question_bank"):
        total = len(FULL_IDS[db])
        for prefix, label in ((1, "B0"), (total - 1, "B1")):
            path = work / f"B-{db}-{label}.sqlite3"
            legacy_db(path, db, prefix)
            conn = connect(path)
            try:
                before = sorted(applied_migrations(conn))
                check(
                    f"B1[{db}/{label}] 旧库前置登记 = 前 {prefix} 条",
                    before == sorted(FULL_IDS[db][:prefix]),
                    f"before={len(before)} 条",
                )
                applied = apply_migrations(conn, database=db)
                check(
                    f"B2[{db}/{label}] 增量只应用 B2 迁移",
                    applied == FULL_IDS[db][prefix:],
                    f"applied={applied}",
                )
                check(
                    f"B3[{db}/{label}] 升级后 B2 表齐备",
                    B2_TABLES[db] <= tables(conn),
                    f"missing={sorted(B2_TABLES[db] - tables(conn))}",
                )
                check(
                    f"B4[{db}/{label}] 升级后 foreign_key_check 为空",
                    conn.execute("PRAGMA foreign_key_check").fetchall() == [],
                    "0 rows",
                )
                check(
                    f"B5[{db}/{label}] 升级后再应用幂等",
                    apply_migrations(conn, database=db) == [],
                    "third apply == []",
                )
            finally:
                conn.close()


# --------------------------------------------------------------------------- C
def part_c(work: Path) -> None:
    conn = connect(work / "C-rollback.sqlite3")
    original = REGISTERED_MIGRATIONS["teaching"]
    try:
        apply_migrations(conn, database="teaching")
        broken = Migration(
            id="9999_v00_broken",
            description="V00 探针：故意失败（第二条语句非法）",
            statements=(
                "CREATE TABLE v00_should_roll_back (id TEXT PRIMARY KEY)",
                "THIS IS NOT VALID SQL FOR V00",
            ),
        )
        REGISTERED_MIGRATIONS["teaching"] = (*original, broken)
        failed = False
        try:
            apply_migrations(conn, database="teaching")
        except sqlite3.Error:
            failed = True
        check("C1 中途失败抛错", failed, "sqlite3.Error raised")
        check(
            "C2 失败迁移第一句已回滚（表不存在）",
            "v00_should_roll_back" not in tables(conn),
            f"has_table={'v00_should_roll_back' in tables(conn)}",
        )
        check(
            "C3 失败迁移未写登记行",
            "9999_v00_broken" not in applied_migrations(conn),
            str(sorted(applied_migrations(conn))[-1:]),
        )
        check(
            "C4 失败后既有登记未损",
            sorted(applied_migrations(conn)) == sorted(FULL_IDS["teaching"]),
            f"{len(applied_migrations(conn))} 条",
        )
    finally:
        REGISTERED_MIGRATIONS["teaching"] = original
        conn.close()


# --------------------------------------------------------------------------- D
def _old_source_root(rel_path: str) -> ast.Module:
    raw = subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:{rel_path}"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return ast.parse(raw)


def _old_assignments(tree: ast.Module, names: tuple[str, ...]) -> dict[str, object]:
    found: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in names:
                found[node.target.id] = ast.literal_eval(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    found[target.id] = ast.literal_eval(node.value)
    return found


FROZEN_RECORDED = {
    # 来源：docs/qa/TEACHING-LOOP-B0/V00-probes/evidence/v1_migrations_probe.json（B0 独立验收实跑记录）
    "teaching": {
        "0001_teaching_baseline": "bf78fb3fb702b6f65f3d9802dfd9b53b6628d14e58d33380a9a7da8936b8612a",
    },
    "question_bank": {
        "0001_question_bank_baseline": "b7025e4ad9e2b042c5cc943927bf5b17a40a3dc01116bb99dadbb8b573298156",
        "0002_question_jobs_engine_columns": "61e5595258709835d269b84c3b6d96594124ac818a5f67168c6af2bfe3fb9ee1",
        "0003_question_jobs_engine_state_index": "b4e4aa295b7bd8f004f8d80f6680792dc74fc8a17a26d7ac747d82795a0cb1fb",
    },
}


def part_d() -> None:
    for db, expected in FROZEN_RECORDED.items():
        for mid, digest in expected.items():
            actual = next(m.sha256 for m in REGISTERED_MIGRATIONS[db] if m.id == mid)
            check(f"D1[{db}/{mid}] 已登记散列 == 已验收记录", actual == digest, actual[:16])
    # 与 B1 提交源码逐语句比对（证明 B0/B1 声明未被 B2 改写）
    te_tree = _old_source_root("apps/api/app/core/migrations/teaching.py")
    qb_tree = _old_source_root("apps/api/app/core/migrations/question_bank.py")
    te_old = _old_assignments(te_tree, ("_BASELINE_STATEMENTS", "_BUSINESS_STATEMENTS"))
    qb_old = _old_assignments(
        qb_tree, ("_BASELINE_STATEMENTS", "_JOB_ENGINE_COLUMNS", "_ENGINE_INDEX_STATEMENTS")
    )
    # question_bank 的 0002 声明由列清单派生：按源码同一规则重建（逐字比较）
    qb_old_engine = tuple(stmt for _column, stmt in qb_old["_JOB_ENGINE_COLUMNS"]) + tuple(
        qb_old["_ENGINE_INDEX_STATEMENTS"]
    )
    comparisons = (
        ("teaching.py", "_BASELINE_STATEMENTS", tuple(te_old["_BASELINE_STATEMENTS"]), te_mod._BASELINE_STATEMENTS),
        ("teaching.py", "_BUSINESS_STATEMENTS", tuple(te_old["_BUSINESS_STATEMENTS"]), te_mod._BUSINESS_STATEMENTS),
        ("question_bank.py", "_BASELINE_STATEMENTS", tuple(qb_old["_BASELINE_STATEMENTS"]), qb_mod._BASELINE_STATEMENTS),
        ("question_bank.py", "_ENGINE_STATEMENTS(派生)", qb_old_engine, qb_mod._ENGINE_STATEMENTS),
    )
    for file_name, name, old_stmts, new_stmts in comparisons:
        same = old_stmts == tuple(new_stmts)
        check(
            f"D2[{file_name}/{name}] 声明语句与 B1 提交逐字一致",
            same and statement_digest(old_stmts) == statement_digest(new_stmts),
            f"old={statement_digest(old_stmts)[:12]} new={statement_digest(new_stmts)[:12]} "
            f"len={len(old_stmts)}/{len(new_stmts)}",
        )
    # 旧库登记散列（0001/0002）与当前代码一致 → 不判漂移（模拟既有库升级）
    for db in ("teaching", "question_bank"):
        for migration in REGISTERED_MIGRATIONS[db]:
            if migration.id.startswith(("0001", "0002", "0003")):
                check(
                    f"D3[{db}/{migration.id}] 声明散列稳定（重复计算一致）",
                    migration.sha256 == statement_digest(migration.statements),
                    migration.sha256[:16],
                )


# --------------------------------------------------------------------------- E/F 数据夹具
def seed_paper(conn: sqlite3.Connection, *, revision_id: str = "r1") -> None:
    conn.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
        "media_type, byte_size, created_at) VALUES ('a1','local','paper','blobs/x',?,'p.docx',"
        "'application/vnd',10,?)",
        ("a" * 64, now_iso()),
    )
    conn.execute("INSERT INTO papers (id, owner_id, subject_id, title) VALUES ('p1','local','math','月考')")
    conn.execute(
        "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, created_at) "
        "VALUES (?, 'p1', 1, 'a1', 0, ?)",
        (revision_id, now_iso()),
    )
    conn.execute("UPDATE papers SET current_revision_id=? WHERE id='p1'", (revision_id,))


def part_e(work: Path) -> None:
    conn = connect(work / "E-checks.sqlite3")
    try:
        apply_migrations(conn, database="teaching")
        seed_paper(conn)
        # E1 未来练习引用非空 → CHECK 拒
        ok, msg = rejects(
            conn,
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "source_practice_revision_id, total_score_units, created_at) "
            "VALUES ('rE1','p1',2,'a1','practice-1',100,?)",
            (now_iso(),),
        )
        check("E1 source_practice_revision_id 非空被拒（分期 CHECK）", ok, msg[:120])
        # E2 source_file_id 为空 → NOT NULL 拒
        ok, msg = rejects(
            conn,
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, created_at) VALUES ('rE2','p1',3,NULL,100,?)",
            (now_iso(),),
        )
        check("E2 source_file_id 为空被拒（NOT NULL）", ok, msg[:120])
        # E3 草稿总分允许 0（分期容差）
        ok, msg = rejects(
            conn,
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, created_at) VALUES ('rE3','p1',4,'a1',0,?)",
            (now_iso(),),
        )
        check("E3 草稿 total_score_units=0 允许（分期容差）", not ok, "inserted" if not ok else msg[:120])
        # E4 未知 source_file_id → 外键拒
        ok, msg = rejects(
            conn,
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, created_at) VALUES ('rE4','p1',5,'nope',0,?)",
            (now_iso(),),
        )
        check("E4 source_file_id 指向不存在资产被拒（外键）", ok, msg[:120])
        # E5 直接插 confirmed 修订 → 拒
        ok, msg = rejects(
            conn,
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, state, confirmed_at, created_at) "
            "VALUES ('rE5','p1',6,'a1',100,'confirmed',?,?)",
            (now_iso(), now_iso()),
        )
        check("E5 直接写入 confirmed 修订被拒（no_direct_sealed）", ok and "USE_CONFIRM_TRANSITION" in msg, msg[:120])
        # E6 施测未来引用非空 → 拒
        conn.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16',1,1,100,'{}')"
        )
        conn.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        conn.execute(
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        conn.execute(
            "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, held_on, created_at) "
            "VALUES ('as1','local','r1','月考','exam','2026-10-08',?)",
            (now_iso(),),
        )
        ok, msg = rejects(conn, "UPDATE assessments SET active_score_revision_id='sc1' WHERE id='as1'")
        check("E6 assessments.active_score_revision_id 非空被拒（分期 CHECK）", ok, msg[:120])
        check("E7 foreign_key_check 仍为空", conn.execute("PRAGMA foreign_key_check").fetchall() == [], "0 rows")
    finally:
        conn.close()


def part_f(work: Path) -> None:
    # ---- paper_confirm 四分支
    # F1 无计分小题
    conn = connect(work / "F1.sqlite3")
    try:
        apply_migrations(conn, database="teaching")
        seed_paper(conn)
        ok, msg = rejects(
            conn,
            "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        check("F1 paper_confirm: 无计分小题 → NO_SCORED_ITEMS", ok and "NO_SCORED_ITEMS" in msg, msg[:140])
        # F2 总分不符
        conn.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16',1,1,100,'{}')"
        )
        conn.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        ok, msg = rejects(
            conn,
            "UPDATE paper_revisions SET total_score_units=90, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        check("F2 paper_confirm: 总分不符 → PAPER_TOTAL_MISMATCH", ok and "PAPER_TOTAL_MISMATCH" in msg, msg[:140])
        # F3 缺知识点
        conn.execute("DELETE FROM paper_item_knowledge WHERE item_id='i1'")
        ok, msg = rejects(
            conn,
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        check("F3 paper_confirm: 计分叶缺知识点 → ITEM_KNOWLEDGE_MISSING", ok and "ITEM_KNOWLEDGE_MISSING" in msg, msg[:140])
        # F4 父容器计分
        conn.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        conn.execute(
            "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, "
            "is_scored, max_score_units, content_json) "
            "VALUES ('i2','r1','i1','16(1)',2,0,NULL,'{}')"
        )
        ok, msg = rejects(
            conn,
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        check("F4 paper_confirm: 父容器计分 → SCORED_ITEM_MUST_BE_LEAF", ok and "SCORED_ITEM_MUST_BE_LEAF" in msg, msg[:140])
        # F5 正常路径可确认
        conn.execute("DELETE FROM paper_items WHERE id='i2'")
        ok, msg = rejects(
            conn,
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        check("F5 paper_confirm: 合法草稿可确认", not ok, msg[:140])
        # F6..F11 冻结触发器（确认后）
        frozen = [
            ("F6 freeze_paper_items_update：改归属/题号被拒",
             "UPDATE paper_items SET question_no='17' WHERE id='i1'"),
            ("F7 freeze_paper_items_update：改 parent 归属被拒",
             "UPDATE paper_items SET parent_item_id='i9' WHERE id='i1'"),
            ("F8 freeze_paper_items_delete：删题被拒", "DELETE FROM paper_items WHERE id='i1'"),
            ("F9 freeze_paper_items_insert：插题被拒",
             "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
             "max_score_units, content_json) VALUES ('iX','r1','18',9,1,10,'{}')"),
            ("F10 freeze_paper_item_knowledge_update：改关联被拒",
             "UPDATE paper_item_knowledge SET role='secondary' WHERE item_id='i1'"),
            ("F11 freeze_paper_item_knowledge_delete：删关联被拒",
             "DELETE FROM paper_item_knowledge WHERE item_id='i1'"),
            ("F12 immutable_paper_revisions_update：改已确认修订被拒",
             "UPDATE paper_revisions SET total_score_units=50 WHERE id='r1'"),
            ("F13 freeze_paper_source_blocks_insert：插块被拒",
             "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json) "
             "VALUES ('bX','r1',1,'paragraph','{}')"),
            ("F14 freeze_paper_issues_insert：插问题被拒",
             "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, created_at) "
             "VALUES ('xX','r1','C','warning','m',?)"),
        ]
        for name, sql in frozen:
            params = (now_iso(),) if sql.endswith("?)") else ()
            ok, msg = rejects(conn, sql, params)
            check(name, ok and "IMMUTABLE_REVISION" in msg, msg[:140])
    finally:
        conn.close()

    # ---- 块 UPDATE 改归属 + DELETE（草稿块的处置改写在草稿修订上是允许的；这里验证确认后拒绝）
    conn = connect(work / "F2.sqlite3")
    try:
        apply_migrations(conn, database="teaching")
        seed_paper(conn)
        conn.execute(
            "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json) "
            "VALUES ('b1','r1',1,'paragraph','{}')"
        )
        conn.execute(
            "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, created_at) "
            "VALUES ('x1','r1','C','warning','m',?)",
            (now_iso(),),
        )
        # 草稿期可改写处置（正向对照）
        conn.execute("UPDATE paper_source_blocks SET disposition='shared_material' WHERE id='b1'")
        conn.execute("UPDATE paper_issues SET status='resolved' WHERE id='x1'")
        check("F15 草稿期块处置/问题状态可改（正向对照）", True, "ok")
        conn.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16',1,1,100,'{}')"
        )
        conn.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        conn.execute(
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        for name, sql in (
            ("F16 freeze_paper_source_blocks_update：确认后改处置被拒",
             "UPDATE paper_source_blocks SET disposition='excluded', exclude_reason='x' WHERE id='b1'"),
            ("F17 freeze_paper_source_blocks_update：确认后改归属被拒",
             "UPDATE paper_source_blocks SET disposition='item', item_id='i1' WHERE id='b1'"),
            ("F18 freeze_paper_source_blocks_delete：确认后删块被拒",
             "DELETE FROM paper_source_blocks WHERE id='b1'"),
            ("F19 freeze_paper_issues_update：确认后改问题被拒",
             "UPDATE paper_issues SET status='excluded' WHERE id='x1'"),
            ("F20 freeze_paper_issues_delete：确认后删问题被拒",
             "DELETE FROM paper_issues WHERE id='x1'"),
        ):
            ok, msg = rejects(conn, sql)
            check(name, ok and "IMMUTABLE_REVISION" in msg, msg[:140])
    finally:
        conn.close()

    # ---- 环
    conn = connect(work / "F3.sqlite3")
    try:
        apply_migrations(conn, database="teaching")
        seed_paper(conn)
        for iid, parent in (("c1", None), ("c2", "c1"), ("c3", "c2")):
            conn.execute(
                "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, "
                "is_scored, content_json) VALUES (?, 'r1', ?, ?, ?, 0, '{}')",
                (iid, parent, iid, int(iid[1])),
            )
        ok, msg = rejects(conn, "UPDATE paper_items SET parent_item_id='c3' WHERE id='c1'")
        check("F21 paper_cycle_update：父子成环被拒（ITEM_CYCLE）", ok and "ITEM_CYCLE" in msg, msg[:140])
        ok, msg = rejects(conn, "UPDATE paper_items SET parent_item_id='c1' WHERE id='c1'")
        check("F22 paper_items 自引用被拒（CHECK parent_item_id<>id）", ok, msg[:140])
        check(
            "F23 存在 paper_cycle_insert/update 两个触发器",
            {"paper_cycle_insert", "paper_cycle_update"} <= triggers(conn),
            str(sorted(t for t in triggers(conn) if t.startswith("paper_cycle"))),
        )
    finally:
        conn.close()

    # ---- 施测触发器
    conn = connect(work / "F4.sqlite3")
    try:
        apply_migrations(conn, database="teaching")
        seed_paper(conn)
        conn.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c1','local','A1','高一(1)班','2026-2027','senior-1')"
        )
        ok, msg = rejects(
            conn,
            "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, held_on, created_at) "
            "VALUES ('as1','local','r1','月考','exam','2026-10-08',?)",
            (now_iso(),),
        )
        check("F24 assessment_confirmed_paper_insert：draft 修订被拒", ok and "PAPER_NOT_CONFIRMED" in msg, msg[:140])
        conn.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16',1,1,100,'{}')"
        )
        conn.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        conn.execute(
            "UPDATE paper_revisions SET total_score_units=100, state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        conn.execute(
            "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, held_on, created_at) "
            "VALUES ('as1','local','r1','月考','exam','2026-10-08',?)",
            (now_iso(),),
        )
        ok, msg = rejects(conn, "UPDATE assessments SET paper_revision_id='other' WHERE id='as1'")
        check("F25 assessment_paper_fixed：施测换卷被拒", ok and "ASSESSMENT_PAPER_FIXED" in msg, msg[:140])
        # class_confirmed=1 必须带依据
        conn.execute("INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as1','c1')")
        conn.execute("INSERT INTO students (id, owner_id, student_no, name) VALUES ('s1','local','001','张伟')")
        ok, msg = rejects(
            conn,
            "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attendance, "
            "name_snapshot, class_confirmed) VALUES ('pt1','as1','s1','c1','present','张伟',1)",
        )
        check("F26 class_confirmed=1 无依据被拒（CHECK）", ok, msg[:140])
        ok, msg = rejects(
            conn,
            "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attendance, "
            "name_snapshot) VALUES ('pt2','as1','s1','c2','present','张伟')",
        )
        check("F27 班级范围外参测被拒（复合外键）", ok, msg[:140])
        check("F28 foreign_key_check 为空", conn.execute("PRAGMA foreign_key_check").fetchall() == [], "0 rows")
    finally:
        conn.close()


def main(evidence: str) -> int:
    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v1-work-"))
    print(f"临时工作目录：{work}")
    try:
        part_a(work)
        part_b(work)
        part_c(work)
        part_d()
        part_e(work)
        part_f(work)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-400:]})
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    print(f"\n== v1_migrations_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[r['name'] for r in failed]} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"probe": "v1_migrations_probe", "results": RESULTS}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    raise SystemExit(main(_args.evidence))
