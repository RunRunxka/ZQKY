"""提交幂等（TEACHING-LOOP B0 / T00-a 冻结接口）。

复合身份 ``(owner_id, operation, submission_id)`` 是提交的幂等键：

- 命中且 ``request_hash`` 相同 → 返回原结果（``replayed=True``），**不再执行** ``apply``；
- 命中但 hash 不同 → 409 ``SUBMISSION_CONFLICT``；
- 未命中：先做 ``expected_revision`` 乐观锁校验（不符 → 409 ``REVISION_CONFLICT`` +
  ``details.currentRevision``），再 ``apply(conn)`` 写业务变更，最后登记 submission 行；
- 以上判定、业务写入与登记在**同一写事务**内（``catalog.write_transaction()``），
  ``apply``/登记抛错整体回滚，不出现"业务改了但没登记"或反过来的中间态。

``table`` 只允许 ``{"command_submissions", "knowledge_submissions"}``（防表名注入），
其余一律 422 ``INVALID_REQUEST``。``request_hash`` 由 ``canonical_hash``（规范化 JSON 的
sha256，键顺序无关）计算；调用方在收到请求时就固定它，才能可靠重放。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.contracts.teaching_loop import (
    REVISION_CONFLICT,
    SUBMISSION_CONFLICT,
    canonical_hash,
)
from app.core.exceptions import AppError
from app.core.sqlite import now_iso

#: 允许写入的提交幂等表白名单（防注入；与冻结 DDL 一致）。
SUBMISSION_TABLES: frozenset[str] = frozenset(
    {"command_submissions", "knowledge_submissions"}
)


@dataclass(frozen=True)
class SubmissionCommand:
    """一次提交请求的稳定身份：owner+operation+submission_id 固定，hash 固定载荷。"""

    owner_id: str
    operation: str
    submission_id: str
    request_hash: str


@dataclass(frozen=True)
class SubmissionOutcome:
    """``replayed=True`` 表示返回的是既有结果，本次未执行 ``apply``。"""

    result: dict[str, Any]
    replayed: bool


def make_command(
    *,
    operation: str,
    submission_id: str,
    payload: Any,
    owner_id: str = "local",
) -> SubmissionCommand:
    """构造提交命令：``request_hash = canonical_hash(payload)``（与键顺序无关）。"""
    operation = _text(operation, field="operation")
    submission_id = _text(submission_id, field="submission_id")
    owner_id = _text(owner_id, field="owner_id")
    try:
        request_hash = canonical_hash(payload)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "payload 必须是可序列化的 JSON 值。",
            code="INVALID_REQUEST",
            status_code=422,
        ) from exc
    return SubmissionCommand(
        owner_id=owner_id,
        operation=operation,
        submission_id=submission_id,
        request_hash=request_hash,
    )


def execute_command(
    *,
    catalog: Any,
    command: SubmissionCommand,
    expected_revision: int | None = None,
    current_revision: Callable[[sqlite3.Connection], int | None] | None = None,
    apply: Callable[[sqlite3.Connection], dict[str, Any]],
    table: str = "command_submissions",
) -> SubmissionOutcome:
    """在单事务内执行或重放一次提交（语义见模块 docstring）。"""
    if table not in SUBMISSION_TABLES:
        raise AppError(
            f"未知提交表：{table!r}。", code="INVALID_REQUEST", status_code=422
        )
    if not isinstance(command, SubmissionCommand):
        raise AppError(
            "command 必须是 SubmissionCommand。", code="INVALID_REQUEST", status_code=422
        )
    _text(command.owner_id, field="owner_id")
    _text(command.operation, field="operation")
    _text(command.submission_id, field="submission_id")
    _text(command.request_hash, field="request_hash")
    if not callable(apply):
        raise AppError(
            "apply 必须是可调用对象。", code="INVALID_REQUEST", status_code=422
        )
    if expected_revision is not None and (
        not isinstance(expected_revision, int) or isinstance(expected_revision, bool)
    ):
        raise AppError(
            "expected_revision 必须是整数。", code="INVALID_REQUEST", status_code=422
        )

    with catalog.write_transaction() as conn:
        row = conn.execute(
            f"SELECT request_hash, result_json FROM {table} "
            "WHERE owner_id = ? AND operation = ? AND submission_id = ?",
            (command.owner_id, command.operation, command.submission_id),
        ).fetchone()
        if row is not None:
            stored_hash = row["request_hash"]
            if not isinstance(stored_hash, str) or stored_hash != command.request_hash:
                raise AppError(
                    "同一提交标识已用于不同请求；请换 submissionId 或核对请求内容。",
                    code=SUBMISSION_CONFLICT,
                    status_code=409,
                )
            return SubmissionOutcome(
                result=_load_result(row["result_json"]), replayed=True
            )

        if expected_revision is not None:
            current = (
                current_revision(conn) if current_revision is not None else None
            )
            if current != expected_revision:
                raise AppError(
                    "数据已被其他操作更新，请刷新后重试。",
                    code=REVISION_CONFLICT,
                    status_code=409,
                    details={"currentRevision": current},
                )

        result = apply(conn)
        if not isinstance(result, dict):
            raise AppError(
                "apply 必须返回 JSON 对象。", code="INVALID_REQUEST", status_code=422
            )
        result_payload = _dump_result(result)
        conn.execute(
            f"INSERT INTO {table} "
            "(owner_id, operation, submission_id, request_hash, result_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                command.owner_id,
                command.operation,
                command.submission_id,
                command.request_hash,
                result_payload,
                now_iso(),
            ),
        )
        return SubmissionOutcome(result=dict(result), replayed=False)


# --------------------------------------------------------------------------- 内部


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"{field} 必须是非空字符串。", code="INVALID_REQUEST", status_code=422
        )
    return value


def _dump_result(result: dict[str, Any]) -> str:
    try:
        return json.dumps(
            dict(result), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise AppError(
            "apply 的返回值必须是可序列化的 JSON 对象。",
            code="INVALID_REQUEST",
            status_code=422,
        ) from exc


def _load_result(raw: object) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise AppError("提交记录损坏。", code="SUBMISSION_CORRUPT", status_code=500)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise AppError("提交记录损坏。", code="SUBMISSION_CORRUPT", status_code=500) from exc
    if not isinstance(value, dict):
        raise AppError("提交记录损坏。", code="SUBMISSION_CORRUPT", status_code=500)
    return value


__all__ = [
    "SUBMISSION_TABLES",
    "SubmissionCommand",
    "SubmissionOutcome",
    "execute_command",
    "make_command",
]
