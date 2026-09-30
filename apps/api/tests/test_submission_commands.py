"""提交幂等（B0 A5）：同键同 hash 重放、同键异 hash 409、版本冲突 409+currentRevision、
apply 抛错整体回滚与表白名单（防注入）。

知识点库（``knowledge_submissions``）与教学库（``command_submissions``）两种表名都覆盖；
全部使用 pytest ``tmp_path`` 临时库，不联网、不读写正式数据目录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import connect, transaction
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.submissions.service import (
    make_command,
    execute_command,
)


def _create_probe(catalog: Any) -> None:
    """业务表替身：验证 apply 的写入与事务回滚（教学库/知识点库 B0 无业务表）。"""
    connection = connect(catalog.db_path)
    try:
        with transaction(connection, immediate=True) as tx:
            tx.execute(
                "CREATE TABLE IF NOT EXISTS submission_probe (id TEXT PRIMARY KEY)"
            )
    finally:
        connection.close()


@pytest.fixture(params=["teaching", "knowledge"])
def submission_env(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Any, str]:
    if request.param == "teaching":
        catalog: Any = TeachingCatalog(tmp_path / "teaching.sqlite3")
        table = "command_submissions"
    else:
        catalog = KnowledgeCatalog(tmp_path / "knowledge.sqlite3")
        table = "knowledge_submissions"
    catalog.migrate()
    _create_probe(catalog)
    return catalog, table


def _count(catalog: Any, target: str) -> int:
    connection = connect(catalog.db_path)
    try:
        row = connection.execute(f"SELECT COUNT(*) FROM {target}").fetchone()
        return int(row[0])
    finally:
        connection.close()


def test_same_key_same_hash_replays_without_apply(
    submission_env: tuple[Any, str],
) -> None:
    catalog, table = submission_env
    calls: list[str] = []

    def apply(conn: Any) -> dict[str, Any]:
        calls.append("apply")
        conn.execute("INSERT INTO submission_probe (id) VALUES ('p1')")
        return {"created": True, "revision": 1}

    payload = {"name": "集合", "type": "concept"}
    command = make_command(
        operation="knowledge.create", submission_id="s-1", payload=payload
    )
    assert command.request_hash == canonical_hash(payload)

    first = execute_command(catalog=catalog, command=command, apply=apply, table=table)
    assert first.replayed is False
    assert first.result == {"created": True, "revision": 1}

    # 同载荷、键序不同 → 同一 request_hash → 直接重放，不再执行 apply
    replay_command = make_command(
        operation="knowledge.create",
        submission_id="s-1",
        payload={"type": "concept", "name": "集合"},
    )
    second = execute_command(
        catalog=catalog, command=replay_command, apply=apply, table=table
    )
    assert second.replayed is True
    assert second.result == first.result
    assert calls == ["apply"]
    assert _count(catalog, table) == 1
    assert _count(catalog, "submission_probe") == 1


def test_same_key_different_hash_conflicts(submission_env: tuple[Any, str]) -> None:
    catalog, table = submission_env
    calls: list[str] = []

    def apply(conn: Any) -> dict[str, Any]:
        calls.append("apply")
        return {"ok": True}

    execute_command(
        catalog=catalog,
        command=make_command(operation="op", submission_id="s-2", payload={"a": 1}),
        apply=apply,
        table=table,
    )
    with pytest.raises(AppError) as err:
        execute_command(
            catalog=catalog,
            command=make_command(
                operation="op", submission_id="s-2", payload={"a": 2}
            ),
            apply=apply,
            table=table,
        )
    assert err.value.code == "SUBMISSION_CONFLICT"
    assert err.value.status_code == 409
    assert calls == ["apply"]
    assert _count(catalog, table) == 1


def test_expected_revision_mismatch_reports_current_revision(
    submission_env: tuple[Any, str],
) -> None:
    catalog, table = submission_env
    calls: list[str] = []

    def apply(conn: Any) -> dict[str, Any]:
        calls.append("apply")
        conn.execute("INSERT INTO submission_probe (id) VALUES ('rev')")
        return {"ok": True}

    command = make_command(operation="op", submission_id="s-3", payload={"x": 1})
    with pytest.raises(AppError) as err:
        execute_command(
            catalog=catalog,
            command=command,
            expected_revision=3,
            current_revision=lambda conn: 5,
            apply=apply,
            table=table,
        )
    assert err.value.code == "REVISION_CONFLICT"
    assert err.value.status_code == 409
    assert err.value.details == {"currentRevision": 5}
    assert calls == []  # apply 未执行，整笔未登记
    assert _count(catalog, table) == 0
    assert _count(catalog, "submission_probe") == 0

    matched = execute_command(
        catalog=catalog,
        command=command,
        expected_revision=5,
        current_revision=lambda conn: 5,
        apply=apply,
        table=table,
    )
    assert matched.replayed is False
    assert calls == ["apply"]


def test_replay_returns_original_even_with_stale_expected_revision(
    submission_env: tuple[Any, str],
) -> None:
    catalog, table = submission_env
    command = make_command(operation="op", submission_id="s-4", payload={"x": 1})
    first = execute_command(
        catalog=catalog, command=command, apply=lambda conn: {"n": 1}, table=table
    )

    def forbidden(conn: Any) -> dict[str, Any]:
        raise AssertionError("重放不得再次执行 apply")

    replay = execute_command(
        catalog=catalog,
        command=command,
        expected_revision=999,
        current_revision=lambda conn: 0,
        apply=forbidden,
        table=table,
    )
    assert replay.replayed is True
    assert replay.result == first.result == {"n": 1}


def test_apply_failure_rolls_back_business_and_submission(
    submission_env: tuple[Any, str],
) -> None:
    catalog, table = submission_env

    def failing(conn: Any) -> dict[str, Any]:
        conn.execute("INSERT INTO submission_probe (id) VALUES ('doomed')")
        raise RuntimeError("业务失败")

    command = make_command(operation="op", submission_id="s-5", payload={"y": 2})
    with pytest.raises(RuntimeError):
        execute_command(catalog=catalog, command=command, apply=failing, table=table)
    assert _count(catalog, table) == 0  # submission 未登记
    assert _count(catalog, "submission_probe") == 0  # 业务写入回滚

    # 修复后同键可重新提交成功，不残留半成品
    done = execute_command(
        catalog=catalog,
        command=command,
        apply=lambda conn: {"retried": True},
        table=table,
    )
    assert done.replayed is False
    assert _count(catalog, table) == 1
    assert _count(catalog, "submission_probe") == 0


def test_apply_app_error_propagates_and_rolls_back(
    submission_env: tuple[Any, str],
) -> None:
    catalog, table = submission_env

    def failing(conn: Any) -> dict[str, Any]:
        conn.execute("INSERT INTO submission_probe (id) VALUES ('x')")
        raise AppError("字段非法。", code="INVALID_REQUEST", status_code=422)

    command = make_command(operation="op", submission_id="s-6", payload={"z": 3})
    with pytest.raises(AppError) as err:
        execute_command(catalog=catalog, command=command, apply=failing, table=table)
    assert err.value.code == "INVALID_REQUEST"
    assert _count(catalog, table) == 0
    assert _count(catalog, "submission_probe") == 0


def test_key_includes_owner_and_operation(submission_env: tuple[Any, str]) -> None:
    catalog, table = submission_env
    calls: list[str] = []

    def apply(conn: Any) -> dict[str, Any]:
        calls.append("apply")
        return {"ok": True}

    execute_command(
        catalog=catalog,
        command=make_command(operation="op-a", submission_id="same", payload={"k": 1}),
        apply=apply,
        table=table,
    )
    execute_command(
        catalog=catalog,
        command=make_command(operation="op-b", submission_id="same", payload={"k": 1}),
        apply=apply,
        table=table,
    )
    execute_command(
        catalog=catalog,
        command=make_command(
            operation="op-a", submission_id="same", payload={"k": 1}, owner_id="other"
        ),
        apply=apply,
        table=table,
    )
    assert calls == ["apply", "apply", "apply"]
    assert _count(catalog, table) == 3


def test_table_outside_whitelist_is_rejected(submission_env: tuple[Any, str]) -> None:
    catalog, _table = submission_env
    command = make_command(operation="op", submission_id="s-7", payload={"a": 1})
    with pytest.raises(AppError) as err:
        execute_command(
            catalog=catalog,
            command=command,
            apply=lambda conn: {},
            table="workflow_jobs; DROP TABLE submission_probe",
        )
    assert err.value.code == "INVALID_REQUEST"
    assert err.value.status_code == 422
    with pytest.raises(AppError) as err2:
        execute_command(catalog=catalog, command=command, apply=lambda conn: {}, table="")
    assert err2.value.code == "INVALID_REQUEST"


def test_execute_command_rejects_non_command(submission_env: tuple[Any, str]) -> None:
    catalog, table = submission_env
    with pytest.raises(AppError) as err:
        execute_command(
            catalog=catalog, command="not-a-command", apply=lambda conn: {}, table=table
        )
    assert err.value.code == "INVALID_REQUEST"
    assert err.value.status_code == 422


def test_make_command_rejects_empty_identity_and_non_json_payload() -> None:
    with pytest.raises(AppError) as err:
        make_command(operation="", submission_id="s", payload={})
    assert err.value.code == "INVALID_REQUEST"
    with pytest.raises(AppError) as err2:
        make_command(operation="op", submission_id="s", payload=object())
    assert err2.value.code == "INVALID_REQUEST"
    with pytest.raises(AppError) as err3:
        make_command(operation="op", submission_id=" ", payload={})
    assert err3.value.code == "INVALID_REQUEST"
