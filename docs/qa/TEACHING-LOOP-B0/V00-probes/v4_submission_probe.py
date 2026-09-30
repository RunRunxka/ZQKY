"""V4 提交幂等独立探针（V00 / TEACHING-LOOP B0）。

覆盖：
  4① 同键同 hash 重放：apply 只执行一次、返回原结果
  4② 同键不同 hash → 409 SUBMISSION_CONFLICT（反例：第二次提交改了 payload）
      —— 并断言业务表未被二次修改
  4③ expected_revision 不符 → 409 REVISION_CONFLICT + details.currentRevision
  4④ apply 抛错 → 业务表与 submission 表都无写入
  4⑤ 非法 table → 422
  附加：复合身份 (owner, operation, submission_id) 的独立性；request_hash 与冻结口径
       （sorted keys / ensure_ascii=False / compact separators）逐字节一致且与键顺序无关
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from _probe_common import check, cleanup, record, run_main, temp_root

from app.core.exceptions import AppError
from app.core.sqlite import connect
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.submissions.service import execute_command, make_command

PROBE = "v4_submission_probe"
BUSINESS = "probe_business"
SUBMISSIONS = "command_submissions"


def _setup(root: Path) -> tuple[TeachingCatalog, sqlite3.Connection]:
    catalog = TeachingCatalog(root / "teaching" / "teaching.sqlite3")
    catalog.migrate()
    connection = connect(catalog.db_path)
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {BUSINESS} (id TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS probe_state (id INTEGER PRIMARY KEY CHECK (id = 1), revision INTEGER NOT NULL)"
    )
    connection.execute("INSERT OR IGNORE INTO probe_state (id, revision) VALUES (1, 7)")
    return catalog, connection


def _count(connection: sqlite3.Connection, table: str, where: str = "1=1") -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])


def _apply_insert(marker: str):
    def apply(conn: sqlite3.Connection) -> dict:
        conn.execute(f"INSERT INTO {BUSINESS} (id, value) VALUES (?, ?)", (marker, marker))
        return {"created": marker}

    return apply


def part_1_replay(root: Path) -> None:
    catalog, connection = _setup(root / "replay")
    calls: list[str] = []

    def apply(conn: sqlite3.Connection) -> dict:
        calls.append("apply")
        conn.execute(f"INSERT INTO {BUSINESS} (id, value) VALUES ('b1', 'v1')")
        return {"created": "b1", "revision": 1}

    command = make_command(operation="create", submission_id="sub-1", payload={"name": "甲", "n": 1})
    first = execute_command(catalog=catalog, command=command, apply=apply)
    second = execute_command(catalog=catalog, command=command, apply=apply)
    check("v4.1a first submit executes apply", first.replayed is False and calls == ["apply"], f"replayed={first.replayed} calls={calls}")
    check(
        "v4.1b replay returns original result and does NOT execute apply again",
        second.replayed is True and second.result == first.result and calls == ["apply"],
        f"replayed={second.replayed} result={second.result} calls={calls}",
    )
    check("v4.1c business row written exactly once", _count(connection, BUSINESS) == 1, str(_count(connection, BUSINESS)))
    check(
        "v4.1d exactly one submission row",
        _count(connection, SUBMISSIONS) == 1,
        str(_count(connection, SUBMISSIONS)),
    )

    # 键顺序无关：同内容不同键顺序 → 同 hash → 仍是重放
    reordered = make_command(operation="create", submission_id="sub-1", payload={"n": 1, "name": "甲"})
    third = execute_command(catalog=catalog, command=reordered, apply=apply)
    check(
        "v4.1e key order does not change request hash (still a replay)",
        reordered.request_hash == command.request_hash and third.replayed is True and calls == ["apply"],
        f"hash_equal={reordered.request_hash == command.request_hash}",
    )
    catalog.close()
    connection.close()


def part_2_conflict(root: Path) -> None:
    catalog, connection = _setup(root / "conflict")
    calls: list[str] = []
    command = make_command(operation="create", submission_id="sub-2", payload={"name": "甲", "score": 100})

    def apply(conn: sqlite3.Connection) -> dict:
        calls.append("apply")
        conn.execute(f"INSERT INTO {BUSINESS} (id, value) VALUES ('b2', 'v1')")
        return {"created": "b2"}

    first = execute_command(catalog=catalog, command=command, apply=apply)
    check("v4.2a first submit ok", first.replayed is False, str(first))

    # 反例：同一 submissionId、payload 改了（hash 变）
    changed = make_command(operation="create", submission_id="sub-2", payload={"name": "甲", "score": 101})
    check(
        "v4.2b payload change actually changes hash",
        changed.request_hash != command.request_hash,
        f"{changed.request_hash[:12]} vs {command.request_hash[:12]}",
    )
    try:
        execute_command(catalog=catalog, command=changed, apply=apply)
        record("v4.2c changed payload under same key -> 409 SUBMISSION_CONFLICT", False, "no exception")
    except AppError as exc:
        check(
            "v4.2c changed payload under same key -> 409 SUBMISSION_CONFLICT",
            exc.code == "SUBMISSION_CONFLICT" and exc.status_code == 409,
            f"code={exc.code} status={exc.status_code} msg={exc}",
        )
    check("v4.2d second submit did not run apply", calls == ["apply"], str(calls))
    check("v4.2e business table untouched by conflict", _count(connection, BUSINESS) == 1, str(_count(connection, BUSINESS)))
    check("v4.2f submission table still one row, hash unchanged",
          _count(connection, SUBMISSIONS) == 1
          and connection.execute(f"SELECT request_hash FROM {SUBMISSIONS}").fetchone()[0] == command.request_hash,
          "ok")

    # 复合身份：不同 operation / 不同 owner 视为不同提交
    other_operation = make_command(operation="update", submission_id="sub-2", payload={"name": "甲", "score": 101})
    out = execute_command(catalog=catalog, command=other_operation, apply=_apply_insert("b2b"))
    check("v4.2g different operation = different identity", out.replayed is False, str(out))
    other_owner = make_command(operation="create", submission_id="sub-2", payload={"name": "乙"}, owner_id="teacher-9")
    out2 = execute_command(catalog=catalog, command=other_owner, apply=_apply_insert("b2c"))
    check("v4.2h different owner = different identity", out2.replayed is False, str(out2))
    catalog.close()
    connection.close()


def part_3_revision(root: Path) -> None:
    catalog, connection = _setup(root / "revision")

    def current(conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT revision FROM probe_state WHERE id = 1").fetchone()[0])

    command = make_command(operation="edit", submission_id="sub-3", payload={"body": "x"})
    try:
        execute_command(
            catalog=catalog,
            command=command,
            expected_revision=6,
            current_revision=current,
            apply=_apply_insert("b3"),
        )
        record("v4.3a stale expected_revision -> 409 REVISION_CONFLICT", False, "no exception")
    except AppError as exc:
        check(
            "v4.3a stale expected_revision -> 409 REVISION_CONFLICT",
            exc.code == "REVISION_CONFLICT" and exc.status_code == 409,
            f"code={exc.code} status={exc.status_code}",
        )
        details = getattr(exc, "details", None)
        check(
            "v4.3b details.currentRevision is the actual current revision",
            isinstance(details, dict) and details.get("currentRevision") == 7,
            f"details={details}",
        )
    check("v4.3c conflict wrote nothing", _count(connection, BUSINESS) == 0 and _count(connection, SUBMISSIONS) == 0,
          f"business={_count(connection, BUSINESS)} submissions={_count(connection, SUBMISSIONS)}")

    ok = execute_command(
        catalog=catalog,
        command=command,
        expected_revision=7,
        current_revision=current,
        apply=_apply_insert("b3"),
    )
    check("v4.3d matching expected_revision applies", ok.replayed is False, str(ok))
    catalog.close()
    connection.close()


def part_4_apply_failure(root: Path) -> None:
    catalog, connection = _setup(root / "apply-failure")

    def exploding_apply(conn: sqlite3.Connection) -> dict:
        conn.execute(f"INSERT INTO {BUSINESS} (id, value) VALUES ('b4', 'v4')")
        raise RuntimeError("业务写入探针失败")

    command = make_command(operation="create", submission_id="sub-4", payload={"k": "v"})
    try:
        execute_command(catalog=catalog, command=command, apply=exploding_apply)
        record("v4.4a apply failure propagates", False, "no exception")
    except RuntimeError as exc:
        record("v4.4a apply failure propagates", True, f"{exc!r}")
    check(
        "v4.4b apply failure rolled back business write",
        _count(connection, BUSINESS) == 0,
        str(_count(connection, BUSINESS)),
    )
    check(
        "v4.4c apply failure left no submission row",
        _count(connection, SUBMISSIONS) == 0,
        str(_count(connection, SUBMISSIONS)),
    )
    retried = execute_command(catalog=catalog, command=command, apply=_apply_insert("b4-ok"))
    check("v4.4d after failure the same key can be submitted again", retried.replayed is False, str(retried))

    def non_dict(conn: sqlite3.Connection) -> list:
        return ["not", "a", "dict"]  # type: ignore[return-value]

    try:
        execute_command(
            catalog=catalog,
            command=make_command(operation="create", submission_id="sub-4b", payload={}),
            apply=non_dict,
        )
        record("v4.4e non-object apply result rejected (422)", False, "no exception")
    except AppError as exc:
        check("v4.4e non-object apply result rejected (422)", exc.code == "INVALID_REQUEST" and exc.status_code == 422, exc.code)
    catalog.close()
    connection.close()


def part_5_table_guard(root: Path) -> None:
    catalog, connection = _setup(root / "table-guard")
    for table, label in (
        ("question_submissions", "题库既有表"),
        ("file_assets", "非提交表"),
        ("command_submissions; DROP TABLE probe_business", "注入尝试"),
    ):
        try:
            execute_command(
                catalog=catalog,
                command=make_command(operation="op", submission_id="s", payload={}),
                apply=_apply_insert("x"),
                table=table,
            )
            record(f"v4.5 illegal table rejected ({label})", False, "no exception")
        except AppError as exc:
            check(
                f"v4.5 illegal table rejected ({label})",
                exc.code == "INVALID_REQUEST" and exc.status_code == 422,
                f"code={exc.code} status={exc.status_code}",
            )
    check(
        "v4.5b guard wrote nothing",
        _count(connection, BUSINESS) == 0 and _count(connection, SUBMISSIONS) == 0,
        "ok",
    )
    # knowledge_submissions 白名单可用（知识点库）
    from app.repositories.knowledge.catalog import KnowledgeCatalog

    knowledge = KnowledgeCatalog(root / "table-guard" / "knowledge" / "knowledge.sqlite3")
    knowledge.migrate()
    out = execute_command(
        catalog=knowledge,
        command=make_command(operation="op", submission_id="s", payload={"a": 1}),
        apply=lambda conn: (conn.execute(
            "INSERT INTO knowledge_submissions (owner_id, operation, submission_id, request_hash, "
            "result_json, created_at) VALUES ('probe', 'inner', 'inner', 'h', '{}', 'now')"
        ), {"ok": True})[1],
        table="knowledge_submissions",
    )
    check("v4.5c knowledge_submissions whitelist works", out.replayed is False, str(out))
    catalog.close()
    connection.close()
    knowledge.close()


def part_6_hash_spec(root: Path) -> None:
    payload = {"b": "中文", "a": [1, 2, {"z": None}], "c": True}
    expected = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    command = make_command(operation="op", submission_id="s", payload=payload)
    check("v4.6a request_hash matches frozen canonical JSON recipe", command.request_hash == expected,
          f"{command.request_hash[:16]} vs {expected[:16]}")
    non_ascii = make_command(operation="op", submission_id="s", payload={"k": "中文"})
    ascii_escaped = hashlib.sha256(json.dumps({"k": "中文"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    check(
        "v4.6b hash uses ensure_ascii=False (not escaped)",
        non_ascii.request_hash != ascii_escaped,
        f"probe={non_ascii.request_hash[:12]} escaped={ascii_escaped[:12]}",
    )


def main() -> None:
    root = temp_root("v4")
    try:
        part_1_replay(root)
        part_2_conflict(root)
        part_3_revision(root)
        part_4_apply_failure(root)
        part_5_table_guard(root)
        part_6_hash_spec(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
