"""V00 · RV11 r2 复验：迁移 0005 在含已确认修订的 B2 旧库上的变体与不变量。

r1 结论：迁移 0005 的回填 UPDATE 被 0003 的 `immutable_paper_revisions_update` 触发器
以 `IMMUTABLE_REVISION` 中止 → 启动失败（V00-G0-REPORT-01 §11）。r2 修复：adjust 钩子在
同一事务内 DROP → 回填 → 逐字恢复该触发器（声明集合/散列不变）。

本探针自建三类旧库（全部经**合法确认路径**造出已确认修订，含子行），并检查：
  A. 形状变体：两个已确认修订 + 一个草稿；一草稿 + 一已确认；已确认修订带
     paper_items / paper_item_knowledge / paper_source_blocks / paper_issues 子行；
  B. 回填与来源标注；子行原样；`foreign_key_check` 空、`integrity_check=ok`、
     `foreign_keys=1`；登记散列正确、重复应用为空操作；
  C. 触发器逐字恢复：与 0003 声明文本（去 IF NOT EXISTS/空白归一）一致，且
     已确认行 UPDATE 仍 `IMMUTABLE_REVISION`、直接插已确认行仍 `USE_CONFIRM_TRANSITION`、
     已确认修订子表插入/更新仍被冻结；
  D. 部分迁移状态（title_snapshot 列已存在）→ 钩子过滤 ALTER 后仍能回填并恢复触发器；
  E. 失败回滚 + 可重跑：注入坏 0006（内存注册，不落产品）→ 0005 保持已登记、
     0006 未登记且 pending 列出；换成好 0006 后只补跑 0006；
  F. 声明集合/散列不变：0005 声明文本与 r1 一致（探针内置 r1 文本比对），登记散列
     与当前 `Migration.sha256` 相同，且"已登记同散列"的库不报 SCHEMA_MIGRATION_DRIFT。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p16_rv11_r2_migration.py
退出码 0 = 全部断言通过。
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402

from app.core.exceptions import AppError  # noqa: E402
from app.core.migrations import (  # noqa: E402
    REGISTERED_MIGRATIONS,
    apply_migrations,
    pending_migrations,
)
from app.core.migrations.base import Migration  # noqa: E402
from app.core.migrations.teaching import (  # noqa: E402
    MIGRATIONS as TEACHING_MIGRATIONS,
    _IMMUTABLE_REVISIONS_UPDATE_TRIGGER,
    _PAPER_STATEMENTS,
    _TITLE_BACKFILL,
    _TITLE_SNAPSHOT_COLUMNS,
    _TITLE_SNAPSHOT_STATEMENTS,
)
from app.core.sqlite import now_iso  # noqa: E402

#: r1 验收时读取到的 0005 声明文本（用于"声明集合不变"的文本级比对）
R1_DECLARED: tuple[str, ...] = (
    "ALTER TABLE paper_revisions ADD COLUMN title_snapshot TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE paper_revisions ADD COLUMN title_snapshot_source TEXT NULL",
    "UPDATE paper_revisions SET title_snapshot = (SELECT title FROM papers WHERE papers.id = paper_revisions.paper_id), title_snapshot_source = 'backfilled_from_paper' WHERE title_snapshot = ''",
)
PAPER_TITLE = "旧卷标题（当前值）"


def normalize(sql: str | None) -> str:
    text = " ".join((sql or "").split())
    return text.replace("IF NOT EXISTS ", "", 1)


def build_legacy_db(path: Path, shape: str) -> sqlite3.Connection:
    """按形状构造 B2 旧库；已确认修订经合法 UPDATE 过渡写入（不卸触发器）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    for migration in TEACHING_MIGRATIONS[:4]:
        statements = (
            tuple(migration.adjust(connection)) if migration.adjust else migration.statements
        )
        with connection:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?, ?, ?)",
                (migration.id, migration.sha256, now_iso()),
            )
    assert "title_snapshot" not in {
        row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")
    }
    if shape == "two_confirmed":
        revisions = [("rev-1", 1, True), ("rev-2", 2, True), ("rev-3", 3, False)]
    elif shape == "draft_and_confirmed":
        revisions = [("rev-1", 1, True), ("rev-2", 2, False)]
    else:
        raise ValueError(shape)
    with connection:
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, media_type, original_name, byte_size, created_at) "
            "VALUES ('fa-1','local','paper',?,?, 'application/octet-stream', 'old.docx', 10, '2026-09-01T00:00:00Z')",
            ("blobs/" + "a" * 64, "a" * 64),
        )
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title, revision, created_at) "
            "VALUES ('paper-1','local','math',?,0,'2026-09-01T00:00:00Z')",
            (PAPER_TITLE,),
        )
        for revision_id, version, confirmed in revisions:
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, state, confirmed_at, created_at) "
                "VALUES (?, 'paper-1', ?, 'fa-1', 10, 'draft', NULL, '2026-09-01T00:00:00Z')",
                (revision_id, version),
            )
            item_id = f"item-{revision_id}"
            connection.execute(
                "INSERT INTO paper_items (id, paper_revision_id, parent_item_id, question_no, ordinal, is_scored, max_score_units, content_json, source_locator_json) "
                "VALUES (?, ?, NULL, '16', 1, 1, 10, ?, '{}')",
                (
                    item_id,
                    revision_id,
                    json.dumps(
                        {
                            "stemBlocks": [
                                {"id": f"blk-{revision_id}", "kind": "paragraph", "text": "题面"}
                            ],
                            "assets": [],
                            "sharedMaterials": [],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, knowledge_revision_id, knowledge_name_snapshot, role, source) "
                "VALUES (?, ?, 'kp-1', 'kpr-1', '一次函数', 'primary', 'human')",
                (item_id, revision_id),
            )
            connection.execute(
                "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json, locator_json, disposition, item_id, exclude_reason) "
                "VALUES (?, ?, 1, 'paragraph', ?, '{}', 'item', ?, NULL)",
                (
                    f"blk-{revision_id}",
                    revision_id,
                    json.dumps(
                        {"id": f"blk-{revision_id}", "kind": "paragraph", "text": "原文段落"},
                        ensure_ascii=False,
                    ),
                    item_id,
                ),
            )
            connection.execute(
                "INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, block_id, locator_json, status, resolution_json, created_at) "
                "VALUES (?, ?, 'UNSUPPORTED_OBJECT', 'warning', '探针问题', NULL, '{}', 'open', NULL, ?)",
                (f"iss-{revision_id}", revision_id, now_iso()),
            )
            if confirmed:
                # 合法确认路径（paper_confirm 触发器校验计分叶/总分/知识点）
                connection.execute(
                    "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id=?",
                    (now_iso(), revision_id),
                )
        last_confirmed = [r for r, _v, c in revisions if c][-1]
        connection.execute(
            "UPDATE papers SET current_revision_id=? WHERE id='paper-1'", (last_confirmed,)
        )
    return connection


def snapshot_rows(connection: sqlite3.Connection) -> dict[str, Any]:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
    snapshot_select = ", ".join(
        column if column in columns else f"NULL AS {column}"
        for column in ("title_snapshot", "title_snapshot_source")
    )
    return {
        "revisions": [
            dict(row)
            for row in connection.execute(
                "SELECT id, version, state, total_score_units, "
                + snapshot_select
                + " FROM paper_revisions ORDER BY version"
            )
        ],
        "items": [
            dict(row)
            for row in connection.execute(
                "SELECT id, paper_revision_id, question_no, is_scored, max_score_units FROM paper_items ORDER BY id"
            )
        ],
        "knowledge": [
            dict(row)
            for row in connection.execute(
                "SELECT item_id, paper_revision_id, knowledge_point_id FROM paper_item_knowledge ORDER BY item_id"
            )
        ],
        "blocks": [
            dict(row)
            for row in connection.execute(
                "SELECT id, paper_revision_id, disposition, item_id FROM paper_source_blocks ORDER BY id"
            )
        ],
        "issues": [
            dict(row)
            for row in connection.execute(
                "SELECT id, paper_revision_id, status FROM paper_issues ORDER BY id"
            )
        ],
    }


def expect_raises(connection: sqlite3.Connection, sql: str, params: tuple = ()) -> str | None:
    try:
        with connection:
            connection.execute(sql, params)
    except sqlite3.IntegrityError as exc:
        return str(exc)
    return None


def check_migration(results: dict[str, Any], failures: list[str], *, name: str,
                    shape: str, pre_add_title_snapshot: bool = False) -> sqlite3.Connection:
    path = V.PROBE_TMP / f"rv11-r2-{name}" / "teaching.sqlite3"
    connection = build_legacy_db(path, shape)
    if pre_add_title_snapshot:
        connection.execute(
            "ALTER TABLE paper_revisions ADD COLUMN title_snapshot TEXT NOT NULL DEFAULT ''"
        )
    before = snapshot_rows(connection)
    outcome: dict[str, Any] = {"shape": shape, "preAddedTitleSnapshot": pre_add_title_snapshot}
    try:
        outcome["pendingBefore"] = pending_migrations(connection, database="teaching")
        try:
            outcome["applied"] = apply_migrations(connection, database="teaching")
        except Exception as exc:  # noqa: BLE001 - 复现阶段如实收集
            outcome["error"] = f"{type(exc).__name__}: {exc}"
        after = snapshot_rows(connection)
        expected_sha = next(
            m.sha256 for m in REGISTERED_MIGRATIONS["teaching"]
            if m.id == "0005_teaching_paper_revision_titles"
        )
        registry = {
            row["id"]: row["sha256"]
            for row in connection.execute("SELECT id, sha256 FROM schema_migrations")
        }
        live_trigger = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='immutable_paper_revisions_update'"
        ).fetchone()
        source_0003 = next(
            statement for statement in _PAPER_STATEMENTS
            if "immutable_paper_revisions_update" in statement
        )
        outcome.update({
            "columns": sorted(
                {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
                & {"title_snapshot", "title_snapshot_source"}
            ),
            "revisions": after["revisions"],
            "childrenUnchanged": {
                key: before[key] == after[key] for key in ("items", "knowledge", "blocks", "issues")
            },
            "triggerVerbatim": normalize(live_trigger[0] if live_trigger else None)
            == normalize(source_0003)
            == normalize(_IMMUTABLE_REVISIONS_UPDATE_TRIGGER),
            "registered0005ShaMatches": registry.get("0005_teaching_paper_revision_titles")
            == expected_sha,
            "foreignKeys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
            "foreignKeyCheck": [
                tuple(row) for row in connection.execute("PRAGMA foreign_key_check")
            ],
            "integrityCheck": [str(row[0]) for row in connection.execute("PRAGMA integrity_check")],
            "updateConfirmedStillBlocked": expect_raises(
                connection,
                "UPDATE paper_revisions SET title_snapshot='x' WHERE state='confirmed'",
            ),
            "insertConfirmedStillBlocked": expect_raises(
                connection,
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, state, confirmed_at, created_at) "
                "VALUES ('rev-x','paper-1',99,'fa-1',10,'confirmed',?,?)",
                (now_iso(), now_iso()),
            ),
            "freezeItemsStillBlocked": expect_raises(
                connection,
                "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, max_score_units, content_json, source_locator_json) "
                "SELECT 'item-x', id, '99', 2, 1, 5, '{}', '{}' FROM paper_revisions WHERE state='confirmed' LIMIT 1",
            ),
        })
        if "error" not in outcome:
            outcome["appliedAgain"] = apply_migrations(connection, database="teaching")
    except Exception as exc:  # noqa: BLE001
        outcome["unexpected"] = f"{type(exc).__name__}: {exc}"
    results[name] = outcome
    if outcome.get("error") or outcome.get("unexpected"):
        failures.append(f"{name}: 迁移失败（{outcome.get('error') or outcome.get('unexpected')}）")
        return connection
    if not (
        outcome["applied"] == ["0005_teaching_paper_revision_titles"]
        and {"title_snapshot", "title_snapshot_source"} <= set(outcome["columns"])
        and all(
            row["title_snapshot"] == PAPER_TITLE
            and row["title_snapshot_source"] == "backfilled_from_paper"
            for row in outcome["revisions"]
        )
        and all(outcome["childrenUnchanged"].values())
        and outcome["triggerVerbatim"]
        and outcome["registered0005ShaMatches"]
        and outcome["foreignKeys"] == 1
        and outcome["foreignKeyCheck"] == []
        and outcome["integrityCheck"] == ["ok"]
        and "IMMUTABLE_REVISION" in (outcome["updateConfirmedStillBlocked"] or "")
        and "USE_CONFIRM_TRANSITION" in (outcome["insertConfirmedStillBlocked"] or "")
        and "IMMUTABLE_REVISION" in (outcome["freezeItemsStillBlocked"] or "")
        and outcome.get("appliedAgain") == []
    ):
        failures.append(f"{name}: 回填/子行/触发器/完整性/幂等不变量不符")
    return connection


def digest_and_failure_checks(results: dict[str, Any], failures: list[str]) -> None:
    expected_sha = next(
        m.sha256 for m in REGISTERED_MIGRATIONS["teaching"]
        if m.id == "0005_teaching_paper_revision_titles"
    )
    results["declaration_invariance"] = {
        "declaredTexts": list(_TITLE_SNAPSHOT_STATEMENTS),
        "equalsR1Texts": tuple(_TITLE_SNAPSHOT_STATEMENTS) == R1_DECLARED,
        "r1BackfillTextMatches": _TITLE_BACKFILL == R1_DECLARED[2],
        "sha256": expected_sha,
    }
    if not (
        tuple(_TITLE_SNAPSHOT_STATEMENTS) == R1_DECLARED
        and _TITLE_BACKFILL == R1_DECLARED[2]
        and len(_TITLE_SNAPSHOT_STATEMENTS) == 3
    ):
        failures.append("F1: 0005 声明文本与 r1 不一致（散列可能漂移）")

    # F2：登记同散列的库不得报漂移；且只跳过、不重复执行
    path = V.PROBE_TMP / "rv11-r2-registered" / "teaching.sqlite3"
    connection = build_legacy_db(path, "draft_and_confirmed")
    try:
        with connection:  # 提交，避免遗留隐式事务（探针夹具；产品连接为 autocommit）
            connection.execute(
                "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?, ?, ?)",
                ("0005_teaching_paper_revision_titles", expected_sha, now_iso()),
            )
        error: str | None = None
        applied: list[str] = []
        try:
            applied = apply_migrations(connection, database="teaching")
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
        results["registered_same_digest_no_drift"] = {
            "error": error,
            "applied": applied,
            "hasTitleSnapshot": "title_snapshot" in {
                row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")
            },
        }
        if error is not None or applied != []:
            failures.append("F2: 已登记同散列的库报漂移或被重复执行")
    finally:
        connection.close()

    # E：坏 0006 注入（仅内存注册）→ 0005 不受影响；换好 0006 后可补跑
    bad_six = Migration(
        id="9001_v00_bad",
        description="探针坏迁移",
        statements=("CREATE TABLE v00_bad (id TEXT)", "SELECT * FROM v00_does_not_exist"),
    )
    good_six = Migration(
        id="9001_v00_bad",
        description="探针修好的迁移",
        statements=("CREATE TABLE v00_bad (id TEXT)",),
    )
    original = REGISTERED_MIGRATIONS["teaching"]
    path_bad = V.PROBE_TMP / "rv11-r2-bad-six" / "teaching.sqlite3"
    connection_bad = build_legacy_db(path_bad, "draft_and_confirmed")
    try:
        REGISTERED_MIGRATIONS["teaching"] = original + (bad_six,)
        error_bad: str | None = None
        applied_bad: list[str] = []
        try:
            applied_bad = apply_migrations(connection_bad, database="teaching")
        except Exception as exc:  # noqa: BLE001
            error_bad = f"{type(exc).__name__}: {exc}"
        registry_bad = {
            row[0] for row in connection_bad.execute("SELECT id FROM schema_migrations")
        }
        revisions_bad = snapshot_rows(connection_bad)["revisions"]
        pending_bad = pending_migrations(connection_bad, database="teaching")
        REGISTERED_MIGRATIONS["teaching"] = original + (good_six,)
        applied_retry = apply_migrations(connection_bad, database="teaching")
        registry_after = {
            row[0] for row in connection_bad.execute("SELECT id FROM schema_migrations")
        }
        revisions_after = snapshot_rows(connection_bad)["revisions"]
        results["bad_0006_rollback_and_rerun"] = {
            "error": error_bad,
            "appliedBeforeFailure": applied_bad,
            "registered0005AfterFailure": "0005_teaching_paper_revision_titles" in registry_bad,
            "registeredBadAfterFailure": "9001_v00_bad" in registry_bad,
            "backfilledAfterFailure": all(
                row["title_snapshot"] == PAPER_TITLE for row in revisions_bad
            ),
            "pendingAfterFailure": pending_bad,
            "retryApplied": applied_retry,
            "registeredBadAfterRetry": "9001_v00_bad" in registry_after,
            "revisionsUnchangedByRetry": revisions_bad == revisions_after,
        }
        if not (
            error_bad is not None
            and "0005_teaching_paper_revision_titles" in registry_bad
            and "9001_v00_bad" not in registry_bad
            and all(row["title_snapshot"] == PAPER_TITLE for row in revisions_bad)
            and pending_bad == ["9001_v00_bad"]
            and applied_retry == ["9001_v00_bad"]
            and "9001_v00_bad" in registry_after
            and revisions_bad == revisions_after
        ):
            failures.append("E: 坏 0006 回滚/重跑语义不符")
    finally:
        REGISTERED_MIGRATIONS["teaching"] = original
        connection_bad.close()


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    connections = []
    try:
        connections.append(
            check_migration(results, failures, name="two_confirmed_children", shape="two_confirmed")
        )
        connections.append(
            check_migration(results, failures, name="draft_plus_confirmed", shape="draft_and_confirmed")
        )
        connections.append(
            check_migration(
                results, failures, name="partial_columns", shape="two_confirmed",
                pre_add_title_snapshot=True,
            )
        )
        digest_and_failure_checks(results, failures)
    finally:
        for connection in connections:
            connection.close()
    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p16_rv11_r2_migration", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("two_confirmed_children", "draft_plus_confirmed", "partial_columns",
                "declaration_invariance", "registered_same_digest_no_drift",
                "bad_0006_rollback_and_rerun"):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:520])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
