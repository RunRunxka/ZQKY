"""V00 · B3-D11 RV11 复算（探针 p11 在 B3 迁移集下的口径修正）。

p11（G0 时冻结的探针）把"待应用/本次应用/重跑应用"硬编码为 `["0005…"]`；B3 登记了
0006/0007 后，同一份**正确行为**会让这些列表变成 3 条，p11 因此 exit 1。本探针用同一
旧库构造器（`p11.build_legacy_teaching_db`，0001–0004 登记 + 真实 papers/revisions 行）
按 B3 口径复算 RV11 的实质断言，避免把 stale 期望当成回归、也避免把回归当成 stale：
  - 纯草稿旧库：0005/0006/0007 全部应用、两列回填 + 来源标注、0005 散列一致、二次应用为空；
  - 含已确认修订旧库：回填正确、0005–0007 应用、三个 paper_revisions 冻结触发器在位；
  - 失败注入（BEFORE UPDATE OF title_snapshot）：整体回滚（列未加、0005 未登记）、
    移除触发器后可重跑且回填正确。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p29_rv11_recheck.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402
import _v00 as V  # noqa: E402
import p11_rv11_titles_migration as P  # noqa: E402

from app.core.migrations import apply_migrations, pending_migrations  # noqa: E402

B3_SCORES = ["0005_teaching_paper_revision_titles", "0006_teaching_score_tables",
             "0007_teaching_assessment_active_score_fk"]


def main() -> int:
    verdict = B.Verdict("p29_rv11_recheck")
    expected_sha = next(
        m.sha256 for m in P.TEACHING_MIGRATIONS if m.id == "0005_teaching_paper_revision_titles"
    )

    # ---- 纯草稿旧库
    db = V.PROBE_TMP / "rv11-b3-draft" / "teaching.sqlite3"
    connection = P.build_legacy_teaching_db(db, with_confirmed=False)
    try:
        pending_before = pending_migrations(connection, database="teaching")
        applied = apply_migrations(connection, database="teaching")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT title_snapshot, title_snapshot_source FROM paper_revisions ORDER BY version"
            )
        ]
        registry = {
            row["id"]: row["sha256"]
            for row in connection.execute("SELECT id, sha256 FROM schema_migrations")
        }
        again = apply_migrations(connection, database="teaching")
        verdict.expect("草稿旧库 pending=0005/0006/0007", pending_before, B3_SCORES)
        verdict.expect("草稿旧库 applied=0005/0006/0007", applied, B3_SCORES)
        verdict.check("两列已加", {"title_snapshot", "title_snapshot_source"} <= columns, sorted(columns))
        verdict.check(
            "旧行回填 + 来源标注",
            all(r["title_snapshot"] == "旧卷标题（当前值）" for r in rows)
            and all(r["title_snapshot_source"] == "backfilled_from_paper" for r in rows),
            rows,
        )
        verdict.expect("0005 登记散列一致", registry.get("0005_teaching_paper_revision_titles"), expected_sha)
        verdict.expect("二次应用为空", again, [])
        verdict.expect("foreign_key_check 空", connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        verdict.expect(
            "integrity_check=ok",
            [r[0] for r in connection.execute("PRAGMA integrity_check")],
            ["ok"],
        )
    finally:
        connection.close()

    # ---- 含已确认修订旧库 + 触发器在位
    db2 = V.PROBE_TMP / "rv11-b3-confirmed" / "teaching.sqlite3"
    connection2 = P.build_legacy_teaching_db(db2, with_confirmed=True)
    try:
        applied2 = apply_migrations(connection2, database="teaching")
        verdict.expect("含已确认修订旧库 applied=0005/0006/0007", applied2, B3_SCORES)
        rows2 = [
            dict(row)
            for row in connection2.execute(
                "SELECT title_snapshot, title_snapshot_source, state FROM paper_revisions ORDER BY version"
            )
        ]
        verdict.check(
            "全部修订（含已确认）回填 + 来源标注",
            all(
                r["title_snapshot"] == "旧卷标题（当前值）"
                and r["title_snapshot_source"] == "backfilled_from_paper"
                for r in rows2
            ),
            rows2,
        )
        triggers = {
            row["name"]
            for row in connection2.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='paper_revisions'"
            )
        }
        verdict.check(
            "paper_revisions 冻结触发器在位",
            {"immutable_paper_revisions_update", "immutable_paper_revisions_delete",
             "no_direct_sealed_paper_revisions"} <= triggers,
            sorted(triggers),
        )
    finally:
        connection2.close()

    # ---- 失败回滚 + 可重跑
    db3 = V.PROBE_TMP / "rv11-b3-rollback" / "teaching.sqlite3"
    connection3 = P.build_legacy_teaching_db(db3, with_confirmed=False)
    try:
        connection3.execute(
            "CREATE TRIGGER block_backfill BEFORE UPDATE OF title_snapshot ON paper_revisions "
            "BEGIN SELECT RAISE(ABORT,'BLOCKED'); END"
        )
        error: str | None = None
        try:
            apply_migrations(connection3, database="teaching")
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        columns_after = {
            row[1] for row in connection3.execute("PRAGMA table_info(paper_revisions)")
        }
        registered_after = {
            row["id"] for row in connection3.execute("SELECT id FROM schema_migrations")
        }
        pending_after = pending_migrations(connection3, database="teaching")
        connection3.execute("DROP TRIGGER block_backfill")
        retry = apply_migrations(connection3, database="teaching")
        rows3 = [
            dict(row)
            for row in connection3.execute(
                "SELECT title_snapshot, title_snapshot_source FROM paper_revisions"
            )
        ]
        verdict.check("注入失败：迁移报错", error is not None and "BLOCKED" in error, error)
        verdict.check(
            "注入失败：两列未加入（整体回滚）",
            not ({"title_snapshot", "title_snapshot_source"} & columns_after),
            sorted(columns_after),
        )
        verdict.check(
            "注入失败：0005 未登记",
            "0005_teaching_paper_revision_titles" not in registered_after,
            sorted(registered_after),
        )
        verdict.expect("注入失败：pending=0005/0006/0007", pending_after, B3_SCORES)
        verdict.expect("移除触发器后重跑 applied=0005/0006/0007", retry, B3_SCORES)
        verdict.check(
            "重跑后回填正确",
            all(
                r["title_snapshot"] == "旧卷标题（当前值）"
                and r["title_snapshot_source"] == "backfilled_from_paper"
                for r in rows3
            ),
            rows3,
        )
    finally:
        connection3.close()

    code = verdict.finish(path=HERE / "p29_rv11_recheck.json")
    print(json.dumps({"tmp": str(V.PROBE_TMP)}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
