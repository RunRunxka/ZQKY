"""r2 · V00-F1 复验探针：question_jobs 索引修复（独立自建，不复用实现者用例）。

覆盖：
  F1① 全新库：question_jobs 存在覆盖 (state, created_at) 的索引
       （idx_question_jobs_engine_state）；knowledge_jobs / workflow_jobs 同样各自有；
  F1② 模拟"修复前的既有库"：手工造 0001(已登记) + 12 条 ALTER 已执行 + 用**当前** 0002 散列
       登记 0002、索引缺失 → 应用完整清单后**只新增 0003**、索引出现、0002 未被判漂移；
  F1③ 0002 的声明散列仍与 r1 一致（61e55952…），即既有库不会因修复被判漂移。

另附：钩子在"列不全"的旧表上返回 12 条 ALTER + 1 条索引（原缺陷根因已消除）；
      0003 幂等（重复 apply 不再应用、索引仍只有一条）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from _probe_common import check, cleanup, record, run_main, temp_root

from app.core.exceptions import AppError
from app.core.migrations import applied_migrations, apply_migrations, verify_migrations
from app.core.migrations import question_bank as qb
from app.core.migrations.base import statement_digest
from app.core.sqlite import connect
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog

PROBE = "v00r2_f1_index_probe"
R1_0002_SHA256 = "61e5595258709835d269b84c3b6d96594124ac818a5f67168c6af2bfe3fb9ee1"

LEGACY_DDL = (
    "CREATE TABLE question_jobs ("
    "id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, "
    "checkpoint_json TEXT NOT NULL DEFAULT '{}', error_code TEXT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
)

BASELINE_STATEMENTS = qb.MIGRATIONS[0].statements
ENGINE_COLUMNS = qb._JOB_ENGINE_COLUMNS
ENGINE_STATEMENTS = qb._ENGINE_STATEMENTS


def indexes(path: Path, table: str) -> dict[str, list[str]]:
    connection = connect(path)
    try:
        return {
            row["name"]: [
                item["name"] for item in connection.execute(f'PRAGMA index_info("{row["name"]}")')
            ]
            for row in connection.execute(f'PRAGMA index_list("{table}")')
        }
    finally:
        connection.close()


def has_state_index(path: Path, table: str) -> bool:
    return any(
        tuple(columns) == ("state", "created_at")
        for columns in indexes(path, table).values()
    )


def part_fresh(root: Path) -> None:
    question_db = root / "fresh" / "question-bank" / "question-bank.sqlite3"
    knowledge_db = root / "fresh" / "knowledge" / "knowledge.sqlite3"
    teaching_db = root / "fresh" / "teaching" / "teaching.sqlite3"
    QuestionBankCatalog(question_db).migrate()
    KnowledgeCatalog(knowledge_db).migrate()
    TeachingCatalog(teaching_db).migrate()

    q_indexes = indexes(question_db, "question_jobs")
    check(
        "F1.1a 全新库 question_jobs 存在 idx_question_jobs_engine_state(state, created_at)",
        q_indexes.get("idx_question_jobs_engine_state") == ["state", "created_at"],
        str(q_indexes),
    )
    check(
        "F1.1b 对照：knowledge_jobs / workflow_jobs 也各自有 (state, created_at) 索引",
        has_state_index(knowledge_db, "knowledge_jobs") and has_state_index(teaching_db, "workflow_jobs"),
        f"knowledge={indexes(knowledge_db, 'knowledge_jobs')} teaching={indexes(teaching_db, 'workflow_jobs')}",
    )
    connection = connect(question_db)
    try:
        migrate_again = apply_migrations(connection, database="question_bank")
        verify_migrations(connection, database="question_bank")
        registered = dict(applied_migrations(connection))
    finally:
        connection.close()
    check("F1.1c 重复 apply 不再应用任何迁移（幂等）", migrate_again == [], str(migrate_again))
    after = indexes(question_db, "question_jobs")
    check(
        "F1.1d 0003 幂等：索引仍只有一条且列不变",
        after == q_indexes and list(after.values()).count(["state", "created_at"]) == 1,
        str(after),
    )
    check(
        "F1.1e 0003 已登记且 0002 散列与 r1 一致",
        registered.get("0003_question_jobs_engine_state_index") == qb.MIGRATIONS[2].sha256
        and registered.get("0002_question_jobs_engine_columns") == R1_0002_SHA256,
        f"registered={sorted(registered)}",
    )


def part_legacy_pre_fix(root: Path) -> None:
    """模拟修复前的既有库：0001 已登记、12 列已补齐、0002 已登记（当前散列）、索引缺失。"""
    db = root / "legacy" / "question-bank.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(db))
    try:
        raw.execute(LEGACY_DDL)
        raw.commit()
    finally:
        raw.close()

    connection = connect(db)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in BASELINE_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "CREATE TABLE schema_migrations (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?, ?, '2026-09-30T00:00:00Z')",
            (qb.MIGRATIONS[0].id, qb.MIGRATIONS[0].sha256),
        )
        # 手工执行 12 条 ALTER（等价修复前 0002 实际做过的事）
        for _column, statement in ENGINE_COLUMNS:
            connection.execute(statement)
        # 用当前（r2）0002 散列登记：既有库早已登记过 0002
        connection.execute(
            "INSERT INTO schema_migrations (id, sha256, applied_at) VALUES (?, ?, '2026-09-30T00:00:00Z')",
            (qb.MIGRATIONS[1].id, qb.MIGRATIONS[1].sha256),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()

    fixture_indexes = indexes(db, "question_jobs")
    check(
        "F1.2a 修复前既有库夹具：12 列已补齐但 (state, created_at) 索引缺失",
        not has_state_index(db, "question_jobs") and fixture_indexes.get("idx_question_jobs_state") == ["kind", "state"],
        str(fixture_indexes),
    )
    connection = connect(db)
    try:
        pre_registered = sorted(applied_migrations(connection))
    finally:
        connection.close()
    check(
        "F1.2b 夹具登记状态：只有 0001/0002",
        pre_registered == [qb.MIGRATIONS[0].id, qb.MIGRATIONS[1].id],
        str(pre_registered),
    )

    connection = connect(db)
    try:
        try:
            applied_now = apply_migrations(connection, database="question_bank")
            drift_error = None
        except AppError as exc:  # 0002 被判漂移就是失败
            applied_now, drift_error = [], f"{exc.code}: {exc}"
    finally:
        connection.close()
    check("F1.2c 应用完整清单未把 0002 判为漂移", drift_error is None, str(drift_error))
    check(
        "F1.2d 只新增应用 0003",
        applied_now == [qb.MIGRATIONS[2].id],
        str(applied_now),
    )
    after = indexes(db, "question_jobs")
    check(
        "F1.2e 既有库补上 idx_question_jobs_engine_state(state, created_at)",
        after.get("idx_question_jobs_engine_state") == ["state", "created_at"],
        str(after),
    )
    connection = connect(db)
    try:
        verify_migrations(connection, database="question_bank")
        registered = dict(applied_migrations(connection))
        second = apply_migrations(connection, database="question_bank")
    finally:
        connection.close()
    check(
        "F1.2f 0001/0002 登记散列未被改写（仍是原值）",
        registered.get("0001_question_bank_baseline") == qb.MIGRATIONS[0].sha256
        and registered.get("0002_question_jobs_engine_columns") == R1_0002_SHA256,
        "ok",
    )
    check("F1.2g 再次 apply 无事发生（幂等）", second == [], str(second))


def part_declared_hash(root: Path) -> None:
    check(
        "F1.3a 0002 声明散列 == r1 口径 61e55952…（既有库不被判漂移）",
        qb.MIGRATIONS[1].sha256 == R1_0002_SHA256,
        qb.MIGRATIONS[1].sha256,
    )
    check(
        "F1.3b 0002 的声明集合仍为 12 ALTER + 1 索引（散列对象未变）",
        ENGINE_STATEMENTS[:-1] == tuple(statement for _c, statement in ENGINE_COLUMNS)
        and ENGINE_STATEMENTS[-1].startswith("CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state"),
        f"声明 {len(ENGINE_STATEMENTS)} 条",
    )
    expected = statement_digest(
        tuple(statement for _c, statement in ENGINE_COLUMNS)
        + (
            "CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state "
            "ON question_jobs(state, created_at)",
        )
    )
    check(
        "F1.3c 独立复算的声明散列 == 登记常量（我自己的 digest 计算）",
        expected == R1_0002_SHA256,
        f"{expected[:16]} vs {R1_0002_SHA256[:16]}",
    )
    pre_db = root / "pre-0002" / "question-bank.sqlite3"
    pre_db.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(pre_db))
    try:
        raw.execute(LEGACY_DDL)
        raw.commit()
    finally:
        raw.close()
    connection = connect(pre_db)
    try:
        filtered = tuple(qb._skip_existing_columns(connection))
    finally:
        connection.close()
    check(
        "F1.4 根因已修：钩子在旧表上返回 12 条 ALTER + 1 条索引（索引不再被丢）",
        len(filtered) == 13
        and sum(1 for s in filtered if s.startswith("ALTER TABLE")) == 12
        and filtered[-1].startswith("CREATE INDEX"),
        f"hook 返回 {len(filtered)} 条",
    )
    # 0003 的声明与 0002 里的索引语句一致（同一对象，保证结构相同）
    check(
        "F1.5 0003 声明 == 0002 声明集合里的索引语句",
        qb.MIGRATIONS[2].statements == ENGINE_STATEMENTS[-1:],
        str(qb.MIGRATIONS[2].statements),
    )


def main() -> None:
    root = temp_root("r2-f1")
    try:
        part_fresh(root)
        part_legacy_pre_fix(root)
        part_declared_hash(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
