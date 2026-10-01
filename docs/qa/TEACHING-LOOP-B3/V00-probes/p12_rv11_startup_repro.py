"""V00 · RV11 附：真实启动路径上的迁移 0005 失败（最小复现）。

场景：数据目录里已有 B2 时代的 teaching.sqlite3（0001–0004 已登记，且**含一条已确认原卷
修订**），随后启动应用（`create_app`）应能正常升级；实际在迁移 0005 的回填 UPDATE 上被
0003 的 `immutable_paper_revisions_update` 触发器以 `IMMUTABLE_REVISION` 中止，迁移
整体回滚 → 应用启动失败。

运行（在 apps/api 下）：.venv/Scripts/python.exe -X utf8 <abs>/p12_rv11_startup_repro.py
退出码 0 = 启动成功（期望）；1 = 启动失败（复现缺陷）。
"""

from __future__ import annotations

import json
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _v00 as V  # noqa: E402
from _v00 import make_settings  # noqa: E402

from app.core.migrations.teaching import MIGRATIONS as TEACHING_MIGRATIONS  # noqa: E402
from app.core.sqlite import now_iso  # noqa: E402
from app.main import create_app  # noqa: E402


def build_b2_teaching_db(data_dir: Path) -> Path:
    """在 data_dir/teaching/teaching.sqlite3 构造带已确认修订的 B2 旧库。"""
    path = data_dir / "teaching" / "teaching.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
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
    sealed_trigger = next(
        statement
        for migration in TEACHING_MIGRATIONS
        for statement in migration.statements
        if "no_direct_sealed_paper_revisions" in statement
    )
    with connection:
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, media_type, original_name, byte_size, created_at) "
            "VALUES ('fa-1','local','paper',?,?, 'application/octet-stream', 'old.docx', 10, '2026-09-01T00:00:00Z')",
            ("blobs/" + "a" * 64, "a" * 64),
        )
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title, revision, created_at) "
            "VALUES ('paper-1','local','math','旧卷标题',0,'2026-09-01T00:00:00Z')"
        )
        connection.execute("DROP TRIGGER IF EXISTS no_direct_sealed_paper_revisions")
        connection.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, state, confirmed_at, created_at) "
            "VALUES ('rev-1','paper-1',1,'fa-1',0,'confirmed',?,'2026-09-01T00:00:00Z')",
            (now_iso(),),
        )
        connection.execute(sealed_trigger)
    connection.commit()
    connection.close()
    return path


def main() -> int:
    results: dict[str, Any] = {}
    data_dir = V.PROBE_TMP / "rv11-startup-repro"
    db_path = build_b2_teaching_db(data_dir)
    results["legacyDb"] = str(db_path)
    error: str | None = None
    try:
        create_app(make_settings(data_dir))
    except Exception:  # noqa: BLE001 - 复现阶段如实记录
        error = traceback.format_exc(limit=6)
    results["startupError"] = error
    connection = sqlite3.connect(str(db_path))
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
        registered = [
            row[0] for row in connection.execute("SELECT id FROM schema_migrations ORDER BY id")
        ]
        results["dbState"] = {
            "hasTitleSnapshot": "title_snapshot" in columns,
            "registeredMigrations": registered,
        }
    finally:
        connection.close()
    results["verdict"] = "pass" if error is None else "fail"
    V.emit("p12_rv11_startup_repro", results)
    print(json.dumps(results, ensure_ascii=False, indent=2)[:2000])
    return 0 if error is None else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        V.cleanup()
