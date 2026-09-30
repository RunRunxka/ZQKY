"""任务引擎通用仓储（TEACHING-LOOP B0 / T00-a 冻结接口）。

三张任务表（``question_jobs`` / ``knowledge_jobs`` / ``workflow_jobs``）共用同一列集合，
本模块是它们的唯一读写入口：租约、attempt、取消标志、冻结输入、结果与错误都在这里落库。
调用方按域传入 ``catalog``、表名与 kind 白名单（未知域/表/kind 一律拒绝）。

纪律（与四库一致）：

- 读操作每次独立 ``connect(catalog.db_path)`` 并关闭；写操作走
  ``catalog.write_transaction()``（``BEGIN IMMEDIATE``，异常整体回滚）。
- 事务内只做 SQL 与 JSON 编解码：不做网络、文件与推理；``complete`` 的
  ``publish(tx)`` 也在同一事务内，抛错则结果与状态一起回滚。
- 状态机：``queued → running → succeeded|failed|cancelled|interrupted``；
  只有持有**当前租约**（``job_id + attempt + token``）的 worker 才能推进运行态任务；
  取消请求优先于迟到结果；重启遗留 ``running`` 由 ``reconcile_interrupted`` 收敛。
- ``succeeded`` 不允许 ``retry`` 重跑（结果已发布）；``failed|interrupted|cancelled``
  可重试回 ``queued``，保留冻结输入与模型指纹，下次 ``claim`` 才递增 attempt。
- 读回的行逐列校验：state 不在六态、JSON 列损坏、标志/计数非法 → ``CORRUPT_JOB_ROW``
  （500），不把坏行静默当 ``queued``。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.contracts.teaching_loop import (
    JOB_DOMAINS,
    JOB_NOT_FOUND,
    JOB_NOT_RETRYABLE,
    JOB_STATES,
    JOB_TERMINAL_STATES,
    LEASE_LOST,
    ApiErrorEnvelope,
    JobView,
    canonical_hash,
)
from app.core.exceptions import AppError
from app.core.sqlite import connect, now_iso

#: 结构性损坏（state 不在六态、JSON 列损坏、标志非法）的统一错误码。
CORRUPT_JOB_ROW = "CORRUPT_JOB_ROW"
#: 运行中且租约未过期时的重复领取。
JOB_BUSY = "JOB_BUSY"
#: 调用方显式指定 job_id 且已存在。
JOB_ALREADY_EXISTS = "JOB_ALREADY_EXISTS"

#: 允许作为 JobStore 目标表的白名单（防表名注入；与冻结 DDL 一致）。
JOB_TABLES: frozenset[str] = frozenset(
    {"question_jobs", "knowledge_jobs", "workflow_jobs"}
)

#: 可重试的终态：成功结果已发布，不允许重跑。
_RETRYABLE_STATES: frozenset[str] = frozenset({"failed", "interrupted", "cancelled"})


def _invalid(message: str) -> AppError:
    return AppError(message, code="INVALID_REQUEST", status_code=422)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def _corrupt(message: str) -> AppError:
    return AppError(f"任务数据损坏：{message}", code=CORRUPT_JOB_ROW, status_code=500)


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。")
    return value


def _optional_text_field(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _corrupt(f"{field} 不是字符串或为空。")
    return value


def _stored_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _corrupt(f"{field} 不是非空字符串。")
    return value


def _json_object(value: object, *, field: str) -> dict[str, Any]:
    """入参 JSON 对象：非 dict → 422（调用方错误）。"""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _invalid(f"{field} 必须是 JSON 对象。")
    return dict(value)


def _dump_json(value: Mapping[str, Any], *, field: str) -> str:
    """规范序列化（键排序、紧凑分隔符）；不可序列化 → 422。"""
    try:
        return json.dumps(
            dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as exc:
        raise _invalid(f"{field} 必须是可序列化的 JSON 对象。") from exc


def _load_json_object(raw: object, *, field: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _corrupt(f"{field} 不是 JSON 文本。")
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise _corrupt(f"{field} 不是合法 JSON。") from exc
    if not isinstance(value, dict):
        raise _corrupt(f"{field} 不是 JSON 对象。")
    return value


def _load_optional_json_object(raw: object, *, field: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    return _load_json_object(raw, field=field)


def _parse_moment(value: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def _lease_deadline(now: str, seconds: int) -> str:
    base = _parse_moment(now)
    if base is None:
        raise AppError("任务时钟值非法。", code="JOB_CLOCK_INVALID", status_code=500)
    return (
        (base + timedelta(seconds=seconds))
        .astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _lease_active(expires_at: object, now: str) -> bool:
    if not isinstance(expires_at, str) or not expires_at:
        return False
    expiry = _parse_moment(expires_at)
    moment = _parse_moment(now)
    if expiry is None or moment is None:
        # 租约时间戳不可解析：视为已过期，允许接管（不能让坏行把任务永久卡死）
        return False
    return expiry > moment


@dataclass(frozen=True)
class JobLease:
    """一次 ``claim`` 的凭据；只有 job_id+attempt+token 三者同时匹配才能发布。"""

    job_id: str
    domain: str
    attempt: int
    token: str
    expires_at: str


@dataclass(frozen=True)
class JobRecord:
    """任务行只读快照；JSON 列已逐列校验，``*_json`` 原文不暴露。"""

    job_id: str
    domain: str
    kind: str
    owner_id: str
    state: str
    attempt: int
    frozen_input: dict[str, Any]
    input_hash: str
    model_snapshot: dict[str, Any]
    checkpoint: dict[str, Any]
    result: dict[str, Any] | None
    error_code: str | None
    error: dict[str, Any] | None
    cancel_requested: bool
    lease_token: str | None
    lease_expires_at: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None

    def view(self) -> JobView:
        """对外视图（camelCase 别名）；``error`` 非空时给出统一错误信封。"""
        error: ApiErrorEnvelope | None = None
        if self.error is not None:
            error = ApiErrorEnvelope(
                code=str(self.error.get("code") or "JOB_FAILED"),
                message=str(self.error.get("message") or ""),
                retryable=bool(self.error.get("retryable", False)),
            )
        return JobView(
            job_id=self.job_id,
            domain=self.domain,  # type: ignore[arg-type]  # 构造时已限定 JOB_DOMAINS
            kind=self.kind,
            attempt=self.attempt,
            state=self.state,  # type: ignore[arg-type]  # 读回时已校验六态
            result=self.result,
            error=error,
        )


class JobStore:
    """单个任务域的任务表入口；实例本身无状态（每次操作独立开连接）。"""

    def __init__(
        self,
        catalog: Any,
        *,
        domain: str,
        table: str,
        kinds: frozenset[str],
        lease_seconds: int = 90,
        now: Callable[[], str] | None = None,
    ) -> None:
        if domain not in JOB_DOMAINS:
            raise _invalid(f"未知任务域：{domain!r}。")
        if table not in JOB_TABLES:
            raise _invalid(f"未知任务表：{table!r}。")
        if isinstance(kinds, str) or not isinstance(kinds, (set, frozenset)):
            raise _invalid("kinds 必须是字符串集合。")
        kind_set = frozenset(kinds)
        if not kind_set or not all(
            isinstance(kind, str) and kind for kind in kind_set
        ):
            raise _invalid("kinds 必须是非空字符串集合。")
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or lease_seconds < 1
        ):
            raise _invalid("lease_seconds 必须是不小于 1 的整数。")
        if now is not None and not callable(now):
            raise _invalid("now 必须是可调用对象。")
        self._catalog = catalog
        self._domain = domain
        self._table = table
        self._kinds = kind_set
        self._lease_seconds = lease_seconds
        self._now: Callable[[], str] = now or now_iso

    # ------------------------------------------------------------ 只读属性

    @property
    def lease_seconds(self) -> int:
        return self._lease_seconds

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def table(self) -> str:
        return self._table

    # ------------------------------------------------------------ 生命周期

    def create(
        self,
        *,
        kind: str,
        frozen_input: dict[str, Any] | None = None,
        model_snapshot: dict[str, Any] | None = None,
        owner_id: str = "local",
        job_id: str | None = None,
    ) -> JobRecord:
        """新建 ``queued`` 任务：冻结输入与模型指纹一并落库，``input_hash`` 取规范散列。"""
        if kind not in self._kinds:
            raise _invalid(f"未知任务类型：{kind!r}。")
        owner_id = _text(owner_id, field="owner_id")
        payload = _json_object(frozen_input, field="frozen_input")
        snapshot = _json_object(model_snapshot, field="model_snapshot")
        payload_json = _dump_json(payload, field="frozen_input")
        snapshot_json = _dump_json(snapshot, field="model_snapshot")
        try:
            input_hash = canonical_hash(payload)
        except (TypeError, ValueError) as exc:
            raise _invalid("frozen_input 必须是可序列化的 JSON 对象。") from exc
        new_id = uuid.uuid4().hex if job_id is None else _text(job_id, field="job_id")
        now = self._now()
        try:
            with self._catalog.write_transaction() as conn:
                conn.execute(
                    f"INSERT INTO {self._table} "
                    "(id, owner_id, kind, state, frozen_input_json, input_hash, "
                    "model_snapshot_json, attempt, cancel_requested, checkpoint_json, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, 'queued', ?, ?, ?, 0, 0, '{}', ?, ?)",
                    (
                        new_id,
                        owner_id,
                        kind,
                        payload_json,
                        input_hash,
                        snapshot_json,
                        now,
                        now,
                    ),
                )
                return self._require_record_in(conn, new_id)
        except sqlite3.IntegrityError as exc:
            raise _conflict("任务标识已存在。", code=JOB_ALREADY_EXISTS) from exc

    def get(self, job_id: str) -> JobRecord:
        """按 id 读取；不存在 → 404 ``JOB_NOT_FOUND``，结构损坏 → 500。"""
        job_id = _text(job_id, field="job_id")
        with self._read_connection() as conn:
            row = self._row_in(conn, job_id)
        if row is None:
            raise AppError("任务不存在。", code=JOB_NOT_FOUND, status_code=404)
        return self._record_from_row(row)

    def list_recent(self, *, limit: int = 50) -> list[JobRecord]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise _invalid("limit 必须是不小于 1 的整数。")
        if limit > 500:
            raise _invalid("limit 不能超过 500。")
        with self._read_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self._table} "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def load_frozen_input(self, job_id: str) -> JobRecord:
        """执行器启动前载入冻结输入（模型指纹与 input_hash 一同返回）。"""
        return self.get(job_id)

    # ------------------------------------------------------------ 领取与租约

    def claim(self, job_id: str) -> JobLease:
        """领取任务：``BEGIN IMMEDIATE`` 内 attempt+1、生成新 token 与租约到期时间。

        - 运行中且租约未过期 → 409 ``JOB_BUSY``（retryable）；
        - 运行中但租约已过期 → 允许接管（上一持有者失权）；
        - ``succeeded`` 不允许重新领取（结果已发布，需要重跑请走 retry 语义之外）。
        """
        job_id = _text(job_id, field="job_id")
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            if record.state == "running" and _lease_active(
                record.lease_expires_at, now
            ):
                raise _conflict(
                    "任务正在执行中，请勿重复领取。",
                    code=JOB_BUSY,
                    retryable=True,
                )
            if record.state == "succeeded":
                raise _conflict(
                    "任务已成功完成，不允许重新领取。",
                    code=JOB_NOT_RETRYABLE,
                )
            attempt = record.attempt + 1
            token = uuid.uuid4().hex
            started_at = record.started_at or now
            conn.execute(
                f"UPDATE {self._table} SET state = 'running', attempt = ?, "
                "lease_token = ?, lease_expires_at = ?, started_at = ?, "
                "error_code = NULL, error_json = NULL, updated_at = ? WHERE id = ?",
                (
                    attempt,
                    token,
                    _lease_deadline(now, self._lease_seconds),
                    started_at,
                    now,
                    job_id,
                ),
            )
            updated = self._require_record_in(conn, job_id)
        return JobLease(
            job_id=job_id,
            domain=self._domain,
            attempt=updated.attempt,
            token=updated.lease_token or token,
            expires_at=updated.lease_expires_at or "",
        )

    def heartbeat(self, lease: JobLease) -> bool:
        """续租：仅当 ``job_id + attempt + token`` 匹配且 state==running 才续期。

        失权/任务不存在/租约形状不合法一律返回 ``False``（不得抛错），且不修改任何行。
        """
        if (
            not isinstance(lease, JobLease)
            or not isinstance(lease.job_id, str)
            or not lease.job_id
            or not isinstance(lease.attempt, int)
            or isinstance(lease.attempt, bool)
            or lease.attempt < 1
            or not isinstance(lease.token, str)
            or not lease.token
        ):
            return False
        now = self._now()
        with self._catalog.write_transaction() as conn:
            row = self._row_in(conn, lease.job_id)
            if row is None:
                return False
            record = self._record_from_row(row)
            if not self._lease_matches(record, lease):
                return False
            conn.execute(
                f"UPDATE {self._table} SET lease_expires_at = ?, updated_at = ? "
                "WHERE id = ? AND lease_token = ? AND attempt = ? AND state = 'running'",
                (
                    _lease_deadline(now, self._lease_seconds),
                    now,
                    lease.job_id,
                    lease.token,
                    lease.attempt,
                ),
            )
            return True

    def cancel_requested(self, job_id: str) -> bool:
        """只读取消探测：标志已置或已是 ``cancelled`` 即视为已请求取消。"""
        record = self.get(job_id)
        return record.cancel_requested or record.state == "cancelled"

    def request_cancel(self, job_id: str) -> JobRecord:
        """协作式取消：``queued`` 立即置 ``cancelled``；``running`` 只置标志；

        终态（含 ``succeeded``）是幂等空操作，原样返回。
        """
        job_id = _text(job_id, field="job_id")
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            if record.state in JOB_TERMINAL_STATES:
                return record
            if record.state == "queued":
                conn.execute(
                    f"UPDATE {self._table} SET state = 'cancelled', cancel_requested = 1, "
                    "finished_at = ?, lease_token = NULL, lease_expires_at = NULL, "
                    "updated_at = ? WHERE id = ?",
                    (now, now, job_id),
                )
            else:  # running：由执行器下一次探测/发布点生效
                conn.execute(
                    f"UPDATE {self._table} SET cancel_requested = 1, updated_at = ? "
                    "WHERE id = ?",
                    (now, job_id),
                )
            return self._require_record_in(conn, job_id)

    def retry(self, job_id: str) -> JobRecord:
        """终态 ``failed|interrupted|cancelled`` → ``queued``；

        保留冻结输入/模型指纹/``input_hash``，清取消标志、租约与**上一轮错误**
        （``error_code``/``error_json`` 一并置空，避免 ``queued`` 视图残留历史失败被
        UI 误读为当前错误），attempt 不变（下次 ``claim`` 才 +1）。
        ``queued|running|succeeded`` → 409 ``JOB_NOT_RETRYABLE``。
        """
        job_id = _text(job_id, field="job_id")
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            if record.state not in _RETRYABLE_STATES:
                raise _conflict(
                    f"任务当前状态为 {record.state}，不能重试。",
                    code=JOB_NOT_RETRYABLE,
                )
            conn.execute(
                f"UPDATE {self._table} SET state = 'queued', cancel_requested = 0, "
                "lease_token = NULL, lease_expires_at = NULL, error_code = NULL, "
                "error_json = NULL, updated_at = ? WHERE id = ?",
                (now, job_id),
            )
            return self._require_record_in(conn, job_id)

    # ------------------------------------------------------------ 收尾

    def complete(
        self,
        job_id: str,
        lease: JobLease,
        *,
        result: dict[str, Any],
        publish: Callable[[sqlite3.Connection], None] | None = None,
    ) -> JobRecord:
        """**单事务**发布结果：核对当前租约 → 取消优先 → ``publish(tx)`` → succeeded。

        - 租约不匹配 → 409 ``LEASE_LOST``（迟到结果不得发布）；
        - 已请求取消 → 改置 ``cancelled`` 并返回，**不**调用 publish；
        - ``publish`` 抛错 → 整个事务回滚（状态、结果、业务写入全部不变），异常向上抛。
        """
        job_id = _text(job_id, field="job_id")
        result_json = _dump_json(_json_object(result, field="result"), field="result")
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            self._require_current_lease(record, lease)
            if record.cancel_requested:
                conn.execute(
                    f"UPDATE {self._table} SET state = 'cancelled', finished_at = ?, "
                    "lease_token = NULL, lease_expires_at = NULL, updated_at = ? "
                    "WHERE id = ?",
                    (now, now, job_id),
                )
                return self._require_record_in(conn, job_id)
            if publish is not None:
                publish(conn)
            conn.execute(
                f"UPDATE {self._table} SET state = 'succeeded', result_json = ?, "
                "error_code = NULL, error_json = NULL, finished_at = ?, "
                "lease_token = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                (result_json, now, now, job_id),
            )
            return self._require_record_in(conn, job_id)

    def mark_cancelled(self, job_id: str, lease: JobLease) -> JobRecord:
        """租约仍有效才置 ``cancelled``；失权返回当前记录（不覆盖新持有者）。"""
        job_id = _text(job_id, field="job_id")
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            if not self._lease_matches(record, lease):
                return record
            conn.execute(
                f"UPDATE {self._table} SET state = 'cancelled', finished_at = ?, "
                "lease_token = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                (now, now, job_id),
            )
            return self._require_record_in(conn, job_id)

    def fail_if_current_lease(
        self,
        job_id: str,
        lease: JobLease,
        *,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> JobRecord:
        """租约有效 → ``failed`` + ``error_json``；失权 → 不写，返回当前记录。"""
        job_id = _text(job_id, field="job_id")
        code = _text(code, field="code")
        message = _text(message, field="message")
        error_json = _dump_json(
            {"code": code, "message": message, "retryable": bool(retryable)},
            field="error",
        )
        now = self._now()
        with self._catalog.write_transaction() as conn:
            record = self._require_record_in(conn, job_id)
            if not self._lease_matches(record, lease):
                return record
            conn.execute(
                f"UPDATE {self._table} SET state = 'failed', error_code = ?, "
                "error_json = ?, finished_at = ?, lease_token = NULL, "
                "lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                (code, error_json, now, now, job_id),
            )
            return self._require_record_in(conn, job_id)

    def reconcile_interrupted(self) -> list[str]:
        """重启收敛：所有 ``running`` → ``interrupted`` + finished_at + 清租约。

        返回本次被收敛的 job id 列表（幂等：重复调用返回空列表）。不自动重跑，
        恢复由调用方决定（``retry``）。
        """
        now = self._now()
        with self._catalog.write_transaction() as conn:
            rows = conn.execute(
                f"SELECT id FROM {self._table} WHERE state = 'running' "
                "ORDER BY created_at ASC, rowid ASC"
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                conn.execute(
                    f"UPDATE {self._table} SET state = 'interrupted', finished_at = ?, "
                    "lease_token = NULL, lease_expires_at = NULL, updated_at = ? "
                    "WHERE state = 'running'",
                    (now, now),
                )
            return ids

    # ------------------------------------------------------------ 内部：连接

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = connect(self._catalog.db_path)
        try:
            yield connection
        finally:
            connection.close()

    # ------------------------------------------------------------ 内部：行

    def _row_in(self, conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return conn.execute(
            f"SELECT * FROM {self._table} WHERE id = ?", (job_id,)
        ).fetchone()

    def _require_record_in(self, conn: sqlite3.Connection, job_id: str) -> JobRecord:
        row = self._row_in(conn, job_id)
        if row is None:
            raise AppError("任务不存在。", code=JOB_NOT_FOUND, status_code=404)
        return self._record_from_row(row)

    @staticmethod
    def _lease_matches(record: JobRecord, lease: JobLease) -> bool:
        return (
            isinstance(lease.token, str)
            and bool(lease.token)
            and record.state == "running"
            and record.attempt == lease.attempt
            and record.lease_token == lease.token
        )

    @staticmethod
    def _require_current_lease(record: JobRecord, lease: JobLease) -> None:
        if not JobStore._lease_matches(record, lease):
            raise _conflict(
                "任务租约已失效，迟到结果不能发布。", code=LEASE_LOST
            )

    def _record_from_row(self, row: sqlite3.Row) -> JobRecord:
        state = row["state"]
        if state not in JOB_STATES:
            raise _corrupt(f"state={state!r} 不在六态内。")
        attempt = row["attempt"]
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
            raise _corrupt("attempt 不是非负整数。")
        cancel_flag = row["cancel_requested"]
        if cancel_flag not in (0, 1):
            raise _corrupt("cancel_requested 不是 0/1 标志。")
        job_id = _stored_text(row["id"], field="id")
        owner_id = _stored_text(row["owner_id"], field="owner_id")
        kind = _stored_text(row["kind"], field="kind")
        created_at = _stored_text(row["created_at"], field="created_at")
        updated_at = _stored_text(row["updated_at"], field="updated_at")
        input_hash = row["input_hash"]
        if not isinstance(input_hash, str):
            raise _corrupt("input_hash 不是字符串。")
        frozen_input = _load_json_object(
            row["frozen_input_json"], field="frozen_input_json"
        )
        model_snapshot = _load_json_object(
            row["model_snapshot_json"], field="model_snapshot_json"
        )
        checkpoint = _load_json_object(
            row["checkpoint_json"], field="checkpoint_json"
        )
        result = _load_optional_json_object(row["result_json"], field="result_json")
        error = _load_optional_json_object(row["error_json"], field="error_json")
        return JobRecord(
            job_id=job_id,
            domain=self._domain,
            kind=kind,
            owner_id=owner_id,
            state=state,
            attempt=attempt,
            frozen_input=frozen_input,
            input_hash=input_hash,
            model_snapshot=model_snapshot,
            checkpoint=checkpoint,
            result=result,
            error_code=_optional_text_field(
                row["error_code"], field="error_code"
            ),
            error=error,
            cancel_requested=bool(cancel_flag),
            lease_token=_optional_text_field(row["lease_token"], field="lease_token"),
            lease_expires_at=_optional_text_field(
                row["lease_expires_at"], field="lease_expires_at"
            ),
            created_at=created_at,
            updated_at=updated_at,
            started_at=_optional_text_field(row["started_at"], field="started_at"),
            finished_at=_optional_text_field(row["finished_at"], field="finished_at"),
        )
