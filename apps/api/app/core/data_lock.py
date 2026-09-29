"""数据根协议：跨进程文件锁与恢复状态标记。

与 ``docs/PLAN.md`` §5.2 / §5.3 一致：

- 写数据的进程（API 生命周期、写入型 CLI）与备份进程共用同一把**数据根**锁；
  备份拿不到锁时抛 ``DATA_LOCK_BUSY``（409，可重试），**不自动停止用户进程**；
- 数据根里的 ``restore-state.json`` 记录恢复进度：应用启动读到 ``incomplete``
  必须明确拒绝，避免自动创建空库掩盖恢复失败。

锁用**操作系统级文件锁**实现，不是"锁文件存在即占用"：进程崩溃时由操作系统自动释放，
不会留下假锁。

- Windows：排他锁用 ``msvcrt.locking(LK_NBLCK)``；共享锁用 ``LockFileEx``
  （不带 ``LOCKFILE_EXCLUSIVE_LOCK``）——CRT 的 ``LK_NBRLCK`` 在 Windows 上实际互斥，
  两个读锁不能共存，故共享语义必须走 ``LockFileEx``。
- POSIX：``fcntl.flock`` 的 ``LOCK_EX`` / ``LOCK_SH``。

锁文件是 ``<root>/.zqky-data.lock``：

```text
偏移 0        1 字节锁字节（真正被锁定的范围）
偏移 1 起     持有者信息 JSON（pid / 获取时间 / 是否排他 / 标签）
```

Windows 的字节范围锁是**强制锁**，读取被锁字节会失败，所以读取者只读偏移 ≥1 的内容；
读不到不影响"是否被占用"的判定（判定只认 ``LOCK_NB`` 加锁结果）。
锁文件不属于任何备份清单（备份只收录被数据库引用的文件）。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import AppError

#: 数据根下的锁文件名；备份只复制被引用的数据文件，不会收录它
LOCK_FILE_NAME = ".zqky-data.lock"
#: 恢复状态文件名（数据根直属，用于启动闸门）
RESTORE_STATE_FILE_NAME = "restore-state.json"

RESTORE_STATUS_INCOMPLETE = "incomplete"
RESTORE_STATUS_READY = "ready"
_RESTORE_STATUSES = (RESTORE_STATUS_INCOMPLETE, RESTORE_STATUS_READY)

#: 持有者信息从偏移 1 开始写，避开被锁字节
_HOLDER_OFFSET = 1
_HOLDER_MAX_BYTES = 1024
#: 非阻塞尝试失败后的轮询间隔（阻塞模式）
_POLL_SECONDS = 0.05


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lock_path(root: Path | str) -> Path:
    """数据根下的锁文件路径。"""
    return Path(root) / LOCK_FILE_NAME


def restore_state_path(root: Path | str) -> Path:
    return Path(root) / RESTORE_STATE_FILE_NAME


def _format_holder(info: dict | None) -> str | None:
    if not isinstance(info, dict):
        return None
    pid = info.get("pid")
    acquired = info.get("acquiredAt")
    mode = "排他锁" if info.get("exclusive") else "共享锁"
    label = info.get("label")
    parts = [f"pid={pid}" if pid is not None else "pid=未知", mode]
    if isinstance(acquired, str) and acquired:
        parts.append(f"自 {acquired}")
    if isinstance(label, str) and label:
        parts.append(f"标签 {label}")
    return "，".join(parts)


def read_lock_info(root: Path | str) -> dict | None:
    """读锁文件里的持有者信息；文件不存在、被占用或内容损坏都返回 ``None``。

    只读偏移 ≥1 的内容：偏移 0 是锁字节，Windows 上读它会失败。
    """
    path = lock_path(root)
    try:
        with open(path, "rb") as handle:
            handle.seek(_HOLDER_OFFSET)
            raw = handle.read(_HOLDER_MAX_BYTES)
    except OSError:
        return None
    text = raw.decode("utf-8", errors="ignore").strip("\x00 \r\n")
    if not text:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def data_lock_holder(root: Path | str) -> str | None:
    """锁持有者的可读描述（含 pid 与时间戳）；读不到返回 ``None``，不影响占用判定。"""
    return _format_holder(read_lock_info(root))


def _busy_error(root: Path | str) -> AppError:
    holder = data_lock_holder(root)
    detail = f"当前持有者：{holder}。" if holder else "未能读到持有者信息。"
    return AppError(
        f"数据根正被其他进程占用（{lock_path(root)}）；"
        f"备份/写入需要独占，请先停止对应进程后重试。{detail}",
        code="DATA_LOCK_BUSY",
        status_code=409,
        retryable=True,
    )


def _open_lock_file(root: Path | str) -> int:
    path = lock_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise AppError(
            f"无法打开数据根锁文件（{path}）：{exc.__class__.__name__}",
            code="DATA_LOCK_UNAVAILABLE",
            status_code=500,
        ) from exc
    try:
        # 锁字节必须存在：Windows 的字节范围锁落在文件长度之外时行为不稳定
        if os.fstat(fd).st_size < 1:
            os.write(fd, b"\n")
            os.fsync(fd)
    except OSError:
        os.close(fd)
        raise
    return fd


def _try_lock(fd: int, *, exclusive: bool) -> bool:
    """非阻塞尝试加锁；占用返回 ``False``，其他错误原样抛 ``OSError``。"""
    try:
        if os.name == "nt":  # pragma: no cover - 平台分支由本机/CI 分别覆盖
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            if exclusive:
                # CRT 写锁（_LK_NBLCK）在 Windows 上就是 LockFileEx 独占锁
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                # CRT 的读锁（_LK_NBRLCK）在 Windows 上互斥，不能做共享锁；
                # 用 LockFileEx 不带 EXCLUSIVE 标志才是真正的共享锁
                _windows_lock(fd, exclusive=False)
        else:
            import fcntl

            flags = (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
            fcntl.flock(fd, flags)
    except OSError:
        return False
    return True


def _unlock(fd: int, *, exclusive: bool) -> None:
    try:
        if os.name == "nt":  # pragma: no cover - 平台分支
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            if exclusive:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                _windows_unlock(fd)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        return None
    return None


if os.name == "nt":  # pragma: no cover - 仅 Windows 定义
    import ctypes
    import msvcrt as _msvcrt
    from ctypes import wintypes as _wintypes

    _LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
    _LOCKFILE_EXCLUSIVE_LOCK = 0x00000002

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", _wintypes.DWORD),
            ("OffsetHigh", _wintypes.DWORD),
            ("hEvent", _wintypes.HANDLE),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL32.LockFileEx.argtypes = [
        _wintypes.HANDLE,
        _wintypes.DWORD,
        _wintypes.DWORD,
        _wintypes.DWORD,
        _wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    _KERNEL32.LockFileEx.restype = _wintypes.BOOL
    _KERNEL32.UnlockFileEx.argtypes = [
        _wintypes.HANDLE,
        _wintypes.DWORD,
        _wintypes.DWORD,
        _wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    _KERNEL32.UnlockFileEx.restype = _wintypes.BOOL

    def _windows_handle(fd: int) -> object:
        return _wintypes.HANDLE(_msvcrt.get_osfhandle(fd))

    def _windows_lock(fd: int, *, exclusive: bool) -> None:
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        overlapped = _Overlapped()
        if not _KERNEL32.LockFileEx(
            _windows_handle(fd), flags, 0, 1, 0, ctypes.byref(overlapped)
        ):
            raise OSError(ctypes.get_last_error(), "LockFileEx 失败")

    def _windows_unlock(fd: int) -> None:
        overlapped = _Overlapped()
        if not _KERNEL32.UnlockFileEx(
            _windows_handle(fd), 0, 1, 0, ctypes.byref(overlapped)
        ):
            raise OSError(ctypes.get_last_error(), "UnlockFileEx 失败")


def _write_holder_info(fd: int, info: dict | None) -> None:
    """在偏移 ≥1 处写/清持有者信息；尾部补空格，文件长度不变（不截断锁字节）。"""
    payload = b""
    if info is not None:
        payload = json.dumps(info, ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(payload) > _HOLDER_MAX_BYTES:
            payload = payload[:_HOLDER_MAX_BYTES]
    try:
        os.lseek(fd, _HOLDER_OFFSET, os.SEEK_SET)
        current = os.fstat(fd).st_size - _HOLDER_OFFSET
        padded = payload + b" " * max(0, current - len(payload))
        os.write(fd, padded)
        os.fsync(fd)
    except OSError:
        # 持有者信息只是可读性辅助，写失败不影响锁本身
        return None
    return None


@dataclass
class DataLock:
    """一次成功的加锁结果；上下文管理器或显式 ``close()`` 释放，``close`` 幂等。

    进程异常退出时由操作系统释放，不需要清理"锁文件残留"。
    """

    root: Path
    path: Path
    exclusive: bool
    info: dict
    _fd: int | None = None

    def __enter__(self) -> "DataLock":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def holder(self) -> str | None:
        return _format_holder(self.info)

    def close(self) -> None:
        fd = self._fd
        if fd is None:
            return
        self._fd = None
        if self.exclusive:
            _write_holder_info(fd, None)
        _unlock(fd, exclusive=self.exclusive)
        try:
            os.close(fd)
        except OSError:
            return None
        return None


def acquire_data_lock(
    root: Path | str,
    *,
    exclusive: bool,
    blocking: bool = False,
    timeout: float = 0.0,
    label: str | None = None,
) -> DataLock:
    """取得数据根锁；拿不到且 ``blocking=False`` 抛 ``DATA_LOCK_BUSY``（409，可重试）。

    ``blocking=True`` 时按 ``timeout`` 秒轮询等待（``timeout<=0`` 表示一直等）。
    锁文件里的持有者信息只用于可读报错，不参与占用判定。
    """
    target = Path(root)
    fd = _open_lock_file(target)
    deadline = None if timeout <= 0 else time.monotonic() + float(timeout)
    while True:
        if _try_lock(fd, exclusive=exclusive):
            break
        if not blocking:
            os.close(fd)
            raise _busy_error(target)
        if deadline is not None and time.monotonic() >= deadline:
            os.close(fd)
            raise _busy_error(target)
        time.sleep(_POLL_SECONDS)
    info = {
        "pid": os.getpid(),
        "acquiredAt": _now_iso(),
        "exclusive": bool(exclusive),
        "label": label or "",
    }
    if exclusive:
        _write_holder_info(fd, info)
    return DataLock(root=target, path=lock_path(target), exclusive=bool(exclusive), info=info, _fd=fd)


# --------------------------------------------------------------------------- 恢复状态


def restore_state(root: Path | str) -> dict | None:
    """读数据根的恢复状态；没有该文件（普通目录）返回 ``None``。

    返回对象至少含 ``status``（``incomplete`` / ``ready``）；损坏时报错，不静默当正常。
    """
    path = restore_state_path(root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise AppError(
            f"恢复状态文件损坏，无法判定数据根是否可用（{path}）：{exc}",
            code="DATA_RESTORE_STATE_CORRUPT",
            status_code=500,
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        raise AppError(
            f"恢复状态文件结构不符（{path}）。",
            code="DATA_RESTORE_STATE_CORRUPT",
            status_code=500,
        )
    return payload


def write_restore_state(
    root: Path | str, *, status: str, **fields: object
) -> dict:
    """原子写恢复状态；与既有内容合并（失败明细不会因为后续写入而丢失）。"""
    if status not in _RESTORE_STATUSES:
        raise AppError(
            f"恢复状态只能是 {list(_RESTORE_STATUSES)} 之一，收到：{status}",
            code="INVALID_REQUEST",
            status_code=422,
        )
    target = Path(root)
    target.mkdir(parents=True, exist_ok=True)
    existing = restore_state(target) or {}
    payload: dict = {**existing, **fields, "status": status}
    payload.setdefault("startedAt", _now_iso())
    payload["updatedAt"] = _now_iso()
    path = restore_state_path(target)
    temporary = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
    return payload


def require_data_root_ready(root: Path | str) -> None:
    """启动闸门：恢复目录处于 ``incomplete`` 时拒绝启动，避免静默新建空库。

    没有 ``restore-state.json`` 的普通数据根、以及 ``status: "ready"`` 的恢复目录都放行；
    未知状态一律拒绝（fail closed）。
    """
    state = restore_state(root)
    if state is None:
        return None
    status = state.get("status")
    if status == RESTORE_STATUS_READY:
        return None
    failures = state.get("failures")
    detail = ""
    if isinstance(failures, list) and failures:
        rendered = "；".join(str(item) for item in failures[:5])
        detail = f" 已知失败：{rendered}"
    raise AppError(
        f"数据根处于恢复未完成状态（status={status}），已拒绝启动以免覆盖未恢复的数据：{root}。"
        f"请重新执行 scripts/rag/backup.py restore 或人工修复后再启动。{detail}",
        code="DATA_RESTORE_INCOMPLETE",
        status_code=503,
        retryable=False,
    )
