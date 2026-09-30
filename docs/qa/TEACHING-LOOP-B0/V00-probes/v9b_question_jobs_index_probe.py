"""V9b 最小复现：question_jobs 缺失 §3.5 声明的 (state, created_at) 索引（V00 发现）。

现象：TASK-CARD §3.5 冻结的索引声明包含 `idx_*_jobs_state(state, created_at)`；
`app/core/migrations/question_bank.py` 的 0002 也**声明**了
`CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state ON question_jobs(state, created_at)`，
但该语句从未执行——因为 `Migration.adjust`（`_skip_existing_columns`）只返回 12 条
`ALTER TABLE ADD COLUMN`，声明集合里的索引语句在执行前被钩子丢掉。
对照：knowledge_jobs / workflow_jobs（同批新建表）都有 (state, created_at) 索引。

影响：题库任务的按状态扫描（例如 reconcile/列表）没有该索引；冻结 DDL 与库内实际结构不一致，
且散列登记覆盖了这条从未执行的语句，后续迁移不会察觉。
"""

from __future__ import annotations

from _probe_common import check, cleanup, run_main, temp_root

from app.core.migrations import Migration
from app.core.migrations import question_bank as qb_migrations
from app.core.sqlite import connect
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog

PROBE = "v9b_question_jobs_index_probe"
EXPECTED_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state "
    "ON question_jobs(state, created_at)"
)


def _indexes(path) -> dict[str, list[str]]:
    connection = connect(path)
    try:
        return {
            row["name"]: [
                item["name"] for item in connection.execute(f'PRAGMA index_info("{row["name"]}")')
            ]
            for row in connection.execute('PRAGMA index_list("question_jobs")')
        }
    finally:
        connection.close()


def _indexes_of(path, table: str) -> dict[str, list[str]]:
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


def main() -> None:
    root = temp_root("v9b")
    try:
        declared = [statement for statement in qb_migrations._ENGINE_STATEMENTS if "CREATE INDEX" in statement]
        check(
            "v9b.1 迁移模块确实声明了该索引（散列覆盖的声明集合里）",
            declared == [EXPECTED_SQL],
            str(declared),
        )
        fresh_db = root / "question-bank" / "question-bank.sqlite3"
        QuestionBankCatalog(fresh_db).migrate()
        indexes = _indexes(fresh_db)
        check(
            "v9b.2 全新题库库：question_jobs 没有 (state, created_at) 索引",
            not any(tuple(columns) == ("state", "created_at") for columns in indexes.values()),
            str(indexes),
        )
        # 根因：在"只有 7 个旧列"的 question_jobs 上调用 adjust 钩子
        pre_db = root / "pre-0002" / "question-bank.sqlite3"
        pre_db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3

        raw = sqlite3.connect(str(pre_db))
        try:
            raw.executescript(
                "CREATE TABLE question_jobs ("
                "id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, "
                "checkpoint_json TEXT NOT NULL DEFAULT '{}', error_code TEXT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
            )
            raw.commit()
        finally:
            raw.close()
        connection = connect(pre_db)
        try:
            filtered = tuple(qb_migrations._skip_existing_columns(connection))
        finally:
            connection.close()
        check(
            "v9b.3 根因：adjust 钩子只返回实际执行的 12 条 ALTER，索引语句不在其中",
            len(filtered) == len(qb_migrations._JOB_ENGINE_COLUMNS) == 12
            and all(statement.startswith("ALTER TABLE") for statement in filtered)
            and not any("CREATE INDEX" in statement for statement in filtered),
            f"hook 返回 {len(filtered)} 条（全部 ALTER）；声明集合共 {len(qb_migrations._ENGINE_STATEMENTS)} 条"
            "（12 ALTER + 1 CREATE INDEX）→ 索引语句永远不会被执行",
        )
        knowledge_db = root / "knowledge" / "knowledge.sqlite3"
        teaching_db = root / "teaching" / "teaching.sqlite3"
        KnowledgeCatalog(knowledge_db).migrate()
        TeachingCatalog(teaching_db).migrate()
        check(
            "v9b.4 对照：knowledge_jobs / workflow_jobs 都有 (state, created_at) 索引",
            any(
                tuple(columns) == ("state", "created_at")
                for columns in _indexes_of(knowledge_db, "knowledge_jobs").values()
            )
            and any(
                tuple(columns) == ("state", "created_at")
                for columns in _indexes_of(teaching_db, "workflow_jobs").values()
            ),
            f"knowledge={_indexes_of(knowledge_db, 'knowledge_jobs')} teaching={_indexes_of(teaching_db, 'workflow_jobs')}",
        )
        # 既有库（旧 question_jobs，无 schema_migrations）路径：ALTER 补齐列后索引仍缺失
        legacy_db = root / "legacy" / "question-bank.sqlite3"
        legacy_db.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3

        raw = sqlite3.connect(str(legacy_db))
        try:
            raw.executescript(
                "CREATE TABLE question_jobs ("
                "id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, "
                "checkpoint_json TEXT NOT NULL DEFAULT '{}', error_code TEXT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
            )
            raw.commit()
        finally:
            raw.close()
        QuestionBankCatalog(legacy_db).migrate()
        legacy_indexes = _indexes(legacy_db)
        connection = connect(legacy_db)
        try:
            legacy_columns = [row["name"] for row in connection.execute("PRAGMA table_info(question_jobs)")]
        finally:
            connection.close()
        check(
            "v9b.5 既有库路径：ALTER 补齐了 12 列，但 (state, created_at) 索引同样缺失",
            "frozen_input_json" in legacy_columns
            and not any(tuple(columns) == ("state", "created_at") for columns in legacy_indexes.values()),
            f"columns={len(legacy_columns)} indexes={legacy_indexes}",
        )
        # 迁移散列登记覆盖了未执行的语句：verify 不会报漂移
        connection = connect(fresh_db)
        try:
            rows = dict(
                connection.execute("SELECT id, sha256 FROM schema_migrations").fetchall()
            )
        finally:
            connection.close()
        baseline, engine = qb_migrations.MIGRATIONS
        check(
            "v9b.6 登记散列与声明语句一致（因此漂移校验不会揭示该索引缺失）",
            rows.get(baseline.id) == baseline.sha256 and rows.get(engine.id) == engine.sha256,
            f"registered={sorted(rows)}",
        )
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
