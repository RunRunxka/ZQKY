"""V2 启动门控独立探针（V00 / TEACHING-LOOP B0）。

覆盖：
  2① 垃圾文件 / 缺必需表 / 散列漂移 → 拒绝启动且**不重建**（文件字节不变、无新库）
  2② 拒绝后文件句柄已释放（Windows 上可删除/改名）
  2③ 缺文件放行且**不创建**库文件
  附加：restore-state.json=incomplete 时 create_app 拒绝（ready 时放行）

真实装配路径：探针直接调用 `app.main.create_app(Settings)`（门控在其中运行），
并用临时数据根；不读 apps/api/.env（显式注入进程内 SecretStore）。
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from _probe_common import check, cleanup, record, run_main, temp_root

from app.core.config import Settings
from app.core.database_gate import DatabaseExpectation, verify_existing_databases
from app.core.exceptions import AppError
from app.core.secrets import SecretStore

PROBE = "v2_startup_gate_probe"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settings(data_dir: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8000,
        allowed_origins=frozenset({"http://127.0.0.1:5173"}),
        env="test",
        data_dir=data_dir,
        credentials_file=None,
    )


def _app_factory():
    from app.main import create_app

    return create_app


def _make_app(data_dir: Path):
    return _app_factory()(_settings(data_dir), secret_store=SecretStore())


def _list_root(root: Path) -> list[str]:
    return sorted(
        str(item.relative_to(root)).replace("\\", "/") for item in root.rglob("*")
    )


def case_garbage(root: Path) -> None:
    gate_dir = root / "garbage"
    db = gate_dir / "textbooks" / "catalog.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"this is definitely not a sqlite database" * 40)
    before = _sha(db)

    expectation = DatabaseExpectation(db, "textbooks", ("catalog_state",))
    for attempt in range(3):
        try:
            verify_existing_databases([expectation])
            record(f"v2.1a[{attempt}] garbage file refused", False, "no exception")
        except AppError as exc:
            check(
                f"v2.1a[{attempt}] garbage file refused",
                exc.code == "DATABASE_UNREADABLE",
                f"code={exc.code} status={exc.status_code} msg={exc}",
            )
    check("v2.1b garbage file not rewritten (bytes unchanged)", _sha(db) == before, _sha(db)[:16])
    files_in_gate_dir = [
        p.relative_to(gate_dir).as_posix() for p in gate_dir.rglob("*") if p.is_file()
    ]
    check(
        "v2.1c refusal creates no database/sidecar files",
        files_in_gate_dir == ["textbooks/catalog.sqlite3"],
        str(files_in_gate_dir),
    )
    # 2②：拒绝后句柄已释放（Windows 可删除/可改名）
    try:
        probe = db.with_name("catalog.sqlite3.renamed")
        db.rename(probe)
        probe.rename(db)
        record("v2.2 refusal releases the file handle (rename ok)", True)
    except OSError as exc:
        record("v2.2 refusal releases the file handle (rename ok)", False, f"{exc!r}")

    # 走真实装配路径：数据根里有一个垃圾库 → create_app 必须在门控处失败，且不建其它库
    app_root = root / "garbage-app"
    app_db = app_root / "textbooks" / "catalog.sqlite3"
    app_db.parent.mkdir(parents=True, exist_ok=True)
    app_db.write_bytes(b"\x00garbage-not-sqlite\xff" * 100)
    app_db_before = _sha(app_db)
    try:
        _make_app(app_root)
        record("v2.1d create_app refuses garbage db", False, "no exception")
    except AppError as exc:
        check(
            "v2.1d create_app refuses garbage db",
            exc.code == "DATABASE_UNREADABLE",
            f"code={exc.code}",
        )
    created = [
        p.relative_to(app_root).as_posix()
        for p in app_root.rglob("*")
        if p.is_file() and p.name != "catalog.sqlite3"
    ]
    check("v2.1e refusal creates no other database", created == [], str(created))
    check(
        "v2.1f garbage app db still byte-identical after create_app refusal",
        _sha(app_db) == app_db_before,
        _sha(app_db)[:16],
    )


def case_missing_table(root: Path) -> None:
    gate_dir = root / "missing-table"
    db = gate_dir / "teaching" / "teaching.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db))
    try:
        connection.execute("CREATE TABLE command_submissions (owner_id TEXT)")
        connection.commit()
    finally:
        connection.close()
    before = _sha(db)
    expectation = DatabaseExpectation(
        db, "teaching", ("command_submissions", "file_assets", "workflow_jobs")
    )
    try:
        verify_existing_databases([expectation])
        record("v2.3a missing required table refused", False, "no exception")
    except AppError as exc:
        check(
            "v2.3a missing required table refused",
            exc.code == "DATABASE_SCHEMA_INCOMPLETE",
            f"code={exc.code} msg={exc}",
        )
    check("v2.3b incomplete db not rebuilt (bytes unchanged)", _sha(db) == before, _sha(db)[:16])
    raw = sqlite3.connect(str(db))
    try:
        tables = sorted(
            row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )
    finally:
        raw.close()
    check("v2.3c refusal did not add tables", tables == ["command_submissions"], str(tables))


def case_drift(root: Path) -> None:
    gate_dir = root / "drift"
    db = gate_dir / "knowledge" / "knowledge.sqlite3"
    db.parent.mkdir(parents=True, exist_ok=True)
    from app.core.migrations import apply_migrations, REGISTERED_MIGRATIONS
    from app.core.sqlite import connect

    connection = connect(db)
    try:
        apply_migrations(connection, database="knowledge")
        connection.execute("UPDATE schema_migrations SET sha256 = ?", ("11" * 32,))
    finally:
        connection.close()
    before = _sha(db)
    expectation = DatabaseExpectation(
        db, "knowledge", ("knowledge_submissions", "knowledge_jobs")
    )
    try:
        verify_existing_databases([expectation])
        record("v2.4a drift refused by gate", False, "no exception")
    except AppError as exc:
        check(
            "v2.4a drift refused by gate",
            exc.code == "SCHEMA_MIGRATION_DRIFT",
            f"code={exc.code} msg={exc}",
        )
    check("v2.4b drift refusal leaves file untouched", _sha(db) == before, _sha(db)[:16])


def case_missing_file(root: Path) -> None:
    missing_root = root / "missing-file"
    db = missing_root / "textbooks" / "catalog.sqlite3"
    try:
        verify_existing_databases([DatabaseExpectation(db, "textbooks", ("catalog_state",))])
        record("v2.5a missing file passes gate", True)
    except AppError as exc:
        record("v2.5a missing file passes gate", False, f"{exc.code}: {exc}")
    check(
        "v2.5b missing file is not created by the gate",
        not db.exists() and not db.parent.exists(),
        f"exists={db.exists()} parent_exists={db.parent.exists()}",
    )


def case_restore_state(root: Path) -> None:
    from app.core.data_lock import write_restore_state

    incomplete_root = root / "restore-incomplete"
    write_restore_state(incomplete_root, status="incomplete", failures=["探针注入"])
    try:
        _make_app(incomplete_root)
        record("v2.6a incomplete restore root refuses create_app", False, "no exception")
    except AppError as exc:
        check(
            "v2.6a incomplete restore root refuses create_app",
            exc.code == "DATA_RESTORE_INCOMPLETE",
            f"code={exc.code}",
        )
    check(
        "v2.6b refusal created no database under incomplete root",
        _list_root(incomplete_root) == ["restore-state.json"],
        str(_list_root(incomplete_root)),
    )

    ready_root = root / "restore-ready"
    ready_root.mkdir(parents=True, exist_ok=True)
    write_restore_state(ready_root, status="ready", failures=[])
    try:
        _make_app(ready_root)
        record("v2.6c ready restore root passes gate and migrates", True)
    except AppError as exc:
        record("v2.6c ready restore root passes gate and migrates", False, f"{exc.code}: {exc}")
    four = sorted(
        p for p in _list_root(ready_root) if p.endswith(".sqlite3")
    )
    check(
        "v2.6d ready root migrates all four databases",
        four
        == [
            "knowledge/knowledge.sqlite3",
            "question-bank/question-bank.sqlite3",
            "teaching/teaching.sqlite3",
            "textbooks/catalog.sqlite3",
        ],
        str(four),
    )


def main() -> None:
    root = temp_root("v2")
    try:
        case_garbage(root)
        case_missing_table(root)
        case_drift(root)
        case_missing_file(root)
        case_restore_state(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
