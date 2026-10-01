"""V00 · RV11 探针：修订级标题快照 + 迁移 0005 在 B2 旧库上的回填/回滚（自建）。

缺陷回顾（B2-RV11）：固定修订的标题读取可变 `papers.title`；新草稿改名会改变旧修订展示。

断言：
  A. 已确认修订标题固定：确认 "Original Title" → 新草稿改名 "NEW DRAFT Title" 后，
     旧 revisionId 的内容 API 仍返回 "Original Title"；DB 里修订快照/来源列正确；
  B. 迁移 0005 在**有数据的 B2 旧库**（0001–0004 已登记 + 真实 papers/revisions 行）上：
     新增两列、旧行回填 `title_snapshot = papers.title` 且来源标注 backfilled_from_paper、
     迁移登记散列正确、重复调用不再执行；
  C. 失败回滚：UPDATE 触发器注入失败 → 事务整体回滚（列未新增、未登记），
     移除触发器后可重跑成功。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p11_rv11_titles_migration.py
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
from _v00_papers import PapersProbe, items_payload_from_view  # noqa: E402

from app.core.migrations import (  # noqa: E402
    REGISTERED_MIGRATIONS,
    applied_migrations,
    apply_migrations,
    pending_migrations,
)
from app.core.migrations.teaching import MIGRATIONS as TEACHING_MIGRATIONS  # noqa: E402
from app.core.sqlite import now_iso  # noqa: E402
from tests.papers_support import build_paper_docx  # noqa: E402

ORIGINAL_TITLE = "Original Title"
DRAFT_TITLE = "NEW DRAFT Title"


def confirm_paper_probe(probe: PapersProbe) -> tuple[str, str, str]:
    """导入 + 绑定知识点 + 解决阻断 + 确认；返回 (paperId, revisionId, question-free)。"""
    docx = build_paper_docx(V.PROBE_TMP / "rv11.docx", with_unknown_object=True)
    imported = probe.import_paper(Path(docx).read_bytes(), title=ORIGINAL_TITLE)
    assert imported.status_code == 201, imported.text
    paper_id = imported.json()["paper"]["paperId"]
    revision = imported.json()["revision"]
    blocks = revision["blocks"]
    paragraph = next(b for b in blocks if b["kind"] == "paragraph")
    items = items_payload_from_view(revision["items"], content={})
    for entry in items:
        if entry["isScored"]:
            point = probe.add_point(
                code=f"KP-{entry['questionNo']}", name=f"知识点 {entry['questionNo']}"
            )
            entry["knowledge"] = [{"knowledgePointId": point.point_id, "role": "primary"}]
    issues = [
        {
            "issueId": issue["issueId"],
            "status": "resolved",
            "resolution": {
                "kind": "supplement_text",
                "targetBlockId": issue.get("blockId") or paragraph["blockId"],
                "text": "补录说明。",
            },
        }
        for issue in revision["issues"]
        if issue["status"] == "open"
    ]
    patched = probe.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={
            "expectedRevision": probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
            "items": items,
            "issues": issues,
        },
    )
    assert patched.status_code == 200, patched.text
    confirmed = probe.client.post(
        f"/api/v1/papers/{paper_id}/confirm",
        json={
            "expectedRevision": probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
            "submissionId": "rv11-confirm",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    return paper_id, confirmed.json()["paperRevisionId"], revision["paperRevisionId"]


def build_legacy_teaching_db(path: Path, *, with_confirmed: bool = True) -> sqlite3.Connection:
    """构造 B2 旧库：0001–0004 登记 + 一条 paper 的两条修订（无 title_snapshot 列）。"""
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
    columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
    assert "title_snapshot" not in columns, "旧库不应已有 title_snapshot"
    sealed_trigger = next(
        statement
        for migration in TEACHING_MIGRATIONS
        for statement in migration.statements
        if "no_direct_sealed_paper_revisions" in statement
    )
    with connection:
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, media_type, original_name, byte_size, created_at) "
            "VALUES ('fa-1','local','paper',?,?, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'old.docx', 10, '2026-09-01T00:00:00Z')",
            ("blobs/" + "a" * 64, "a" * 64),
        )
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title, revision, created_at) "
            "VALUES ('paper-1','local','math',?,0,'2026-09-01T00:00:00Z')",
            ("旧卷标题（当前值）",),
        )
        # 真实 B2 库中的已确认行是走确认路径写入的；构造夹具时临时卸下"禁止直接插入
        # 已确认行"的触发器，插入后原样恢复（不改产品代码）。
        connection.execute("DROP TRIGGER IF EXISTS no_direct_sealed_paper_revisions")
        for revision_id, version, state in (
            ("rev-1", 1, "confirmed" if with_confirmed else "draft"),
            ("rev-2", 2, "draft"),
        ):
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, state, confirmed_at, created_at) "
                "VALUES (?, 'paper-1', ?, 'fa-1', 0, ?, ?, '2026-09-01T00:00:00Z')",
                (revision_id, version, state, now_iso() if state == "confirmed" else None),
            )
        connection.execute(sealed_trigger)
    return connection


def _apply_and_collect(connection: sqlite3.Connection) -> dict[str, Any]:
    """在给定旧库上应用迁移并收集结果（异常也如实收集，不抛出）。"""
    outcome: dict[str, Any] = {}
    try:
        outcome["applied"] = apply_migrations(connection, database="teaching")
    except Exception as exc:  # noqa: BLE001 - 观察失败类型与首败信息
        outcome["error"] = f"{type(exc).__name__}: {exc}"
    outcome["columns"] = sorted(
        {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
        & {"title_snapshot", "title_snapshot_source"}
    )
    if "title_snapshot" in outcome["columns"]:
        outcome["rows"] = [
            dict(row)
            for row in connection.execute(
                "SELECT id, state, title_snapshot, title_snapshot_source FROM paper_revisions ORDER BY version"
            )
        ]
    else:
        outcome["rows"] = [
            dict(row)
            for row in connection.execute(
                "SELECT id, state FROM paper_revisions ORDER BY version"
            )
        ]
    outcome["registry"] = {
        row["id"]: row["sha256"]
        for row in connection.execute("SELECT id, sha256 FROM schema_migrations")
    }
    outcome["fk"] = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    return outcome


def migration_checks(results: dict[str, Any], failures: list[str]) -> None:
    expected_sha = next(
        m.sha256
        for m in REGISTERED_MIGRATIONS["teaching"]
        if m.id == "0005_teaching_paper_revision_titles"
    )

    # ---- B1. 只有草稿行的 B2 旧库（回填 + 来源标注 + 幂等）
    db_path = V.PROBE_TMP / "rv11-legacy-draft" / "teaching.sqlite3"
    connection = build_legacy_teaching_db(db_path, with_confirmed=False)
    try:
        pending_before = pending_migrations(connection, database="teaching")
        outcome = _apply_and_collect(connection)
        applied_again = (
            apply_migrations(connection, database="teaching") if "error" not in outcome else None
        )
        results["migration_backfill_drafts_only"] = {
            "pendingBefore": pending_before,
            "applied": outcome.get("applied"),
            "error": outcome.get("error"),
            "columnsAdded": outcome["columns"],
            "rows": outcome["rows"],
            "shaMatches": outcome["registry"].get("0005_teaching_paper_revision_titles")
            == expected_sha,
            "secondApplyNoop": applied_again == [],
            "foreignKeys": outcome["fk"],
        }
        if not (
            pending_before == ["0005_teaching_paper_revision_titles"]
            and outcome.get("applied") == ["0005_teaching_paper_revision_titles"]
            and {"title_snapshot", "title_snapshot_source"} <= set(outcome["columns"])
            and all(row["title_snapshot"] == "旧卷标题（当前值）" for row in outcome["rows"])
            and all(
                row["title_snapshot_source"] == "backfilled_from_paper"
                for row in outcome["rows"]
            )
            and outcome["registry"].get("0005_teaching_paper_revision_titles") == expected_sha
            and applied_again == []
        ):
            failures.append("B1: 0005 在纯草稿旧库上的回填/登记/幂等不符")

        # ---- B2. 含**已确认修订**的 B2 旧库（真实用户库的常见形态）
        db_confirmed = V.PROBE_TMP / "rv11-legacy-confirmed" / "teaching.sqlite3"
        connection_confirmed = build_legacy_teaching_db(db_confirmed, with_confirmed=True)
        outcome_confirmed = _apply_and_collect(connection_confirmed)
        results["migration_backfill_with_confirmed_revision"] = {
            "applied": outcome_confirmed.get("applied"),
            "error": outcome_confirmed.get("error"),
            "columnsAdded": outcome_confirmed["columns"],
            "rows": outcome_confirmed["rows"],
            "registered": "0005_teaching_paper_revision_titles"
            in outcome_confirmed["registry"],
        }
        if outcome_confirmed.get("error") is not None:
            failures.append(
                "B2: 含已确认修订的 B2 旧库上迁移 0005 失败（"
                + str(outcome_confirmed["error"])
                + "）；真实用户库升级会卡在启动迁移"
            )
        elif not (
            {"title_snapshot", "title_snapshot_source"} <= set(outcome_confirmed["columns"])
            and all(
                row["title_snapshot"] == "旧卷标题（当前值）"
                and row["title_snapshot_source"] == "backfilled_from_paper"
                for row in outcome_confirmed["rows"]
            )
        ):
            failures.append("B2: 含已确认修订的旧库回填结果不符")

        # ---- C. 失败回滚：注入 UPDATE 触发器（纯草稿库，聚焦回滚语义）
        db2 = V.PROBE_TMP / "rv11-legacy2" / "teaching.sqlite3"
        connection2 = build_legacy_teaching_db(db2, with_confirmed=False)
        connection2.execute(
            "CREATE TRIGGER block_backfill BEFORE UPDATE OF title_snapshot ON paper_revisions "
            "BEGIN SELECT RAISE(ABORT,'BLOCKED'); END"
        )
        error: str | None = None
        try:
            apply_migrations(connection2, database="teaching")
        except Exception as exc:  # noqa: BLE001 - 观察失败类型
            error = f"{type(exc).__name__}: {exc}"
        columns_after_fail = {
            row[1] for row in connection2.execute("PRAGMA table_info(paper_revisions)")
        }
        registry_after_fail = {
            row["id"] for row in connection2.execute("SELECT id FROM schema_migrations")
        }
        pending_after_fail = pending_migrations(connection2, database="teaching")
        # 移除触发器后可重跑
        connection2.execute("DROP TRIGGER block_backfill")
        retry_applied = apply_migrations(connection2, database="teaching")
        rows_retry = [
            dict(row)
            for row in connection2.execute(
                "SELECT id, title_snapshot, title_snapshot_source FROM paper_revisions ORDER BY version"
            )
        ]
        results["migration_rollback"] = {
            "error": error,
            "columnsAfterFailure": sorted(columns_after_fail & {"title_snapshot", "title_snapshot_source"}),
            "registered0005AfterFailure": "0005_teaching_paper_revision_titles" in registry_after_fail,
            "pendingAfterFailure": pending_after_fail,
            "retryApplied": retry_applied,
            "rowsAfterRetry": rows_retry,
        }
        if not (
            error is not None
            and "title_snapshot" not in columns_after_fail
            and "0005_teaching_paper_revision_titles" not in registry_after_fail
            and pending_after_fail == ["0005_teaching_paper_revision_titles"]
            and retry_applied == ["0005_teaching_paper_revision_titles"]
            and all(row["title_snapshot_source"] == "backfilled_from_paper" for row in rows_retry)
        ):
            failures.append("C: 0005 失败未整体回滚或不可重跑")
        connection2.close()
    finally:
        connection.close()


def behavior_checks(results: dict[str, Any], failures: list[str]) -> None:
    probe = PapersProbe(V.PROBE_TMP / "rv11")
    try:
        paper_id, confirmed_revision_id, _draft = confirm_paper_probe(probe)
        before = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{confirmed_revision_id}/content"
        ).json()
        # 新草稿改名（patch 仅 title → fork 新草稿并同步修订级快照）
        renamed = probe.client.patch(
            f"/api/v1/papers/{paper_id}/draft",
            json={
                "expectedRevision": probe.client.get(f"/api/v1/papers/{paper_id}").json()["revision"],
                "title": DRAFT_TITLE,
            },
        )
        assert renamed.status_code == 200, renamed.text
        after = probe.client.get(
            f"/api/v1/papers/{paper_id}/revisions/{confirmed_revision_id}/content"
        ).json()
        paper_view = probe.client.get(f"/api/v1/papers/{paper_id}").json()
        rows = probe.raw_rows(
            "SELECT id, state, title_snapshot, title_snapshot_source FROM paper_revisions "
            "WHERE paper_id = ? ORDER BY version",
            (paper_id,),
        )
        results["revision_title_snapshot"] = {
            "beforeTitle": before["title"],
            "afterTitle": after["title"],
            "paperTitleNow": paper_view["title"],
            "revisions": rows,
        }
        if not (
            before["title"] == ORIGINAL_TITLE
            and after["title"] == ORIGINAL_TITLE
            and paper_view["title"] == DRAFT_TITLE
            and any(
                row["id"] == confirmed_revision_id
                and row["state"] == "confirmed"
                and row["title_snapshot"] == ORIGINAL_TITLE
                for row in rows
            )
            and any(
                row["state"] == "draft" and row["title_snapshot"] == DRAFT_TITLE for row in rows
            )
        ):
            failures.append("A: 固定修订标题随草稿改名或快照列不符")
    finally:
        probe.close()


def main() -> int:
    results: dict[str, Any] = {}
    failures: list[str] = []
    behavior_checks(results, failures)
    migration_checks(results, failures)
    results["failures"] = failures
    results["verdict"] = "pass" if not failures else "fail"
    V.emit("p11_rv11_titles_migration", results)
    print(f"verdict={results['verdict']} failures={failures}")
    for key in ("revision_title_snapshot", "migration_backfill", "migration_rollback"):
        print(key, json.dumps(results.get(key), ensure_ascii=False)[:520])
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
