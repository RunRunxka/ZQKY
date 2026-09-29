"""数据根跨进程文件锁与恢复状态：DATA_LOCK_BUSY、OS 级释放、启动闸门语义。

只用 pytest ``tmp_path``；不使用正式 ``.local-data``，也不启动任何外部进程服务
（跨进程用例只派生一个短命 Python 子进程做加锁尝试）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.core.data_lock import (
    LOCK_FILE_NAME,
    RESTORE_STATUS_INCOMPLETE,
    RESTORE_STATUS_READY,
    acquire_data_lock,
    data_lock_holder,
    lock_path,
    read_lock_info,
    require_data_root_ready,
    restore_state,
    write_restore_state,
)
from app.core.exceptions import AppError

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    return root


# ------------------------------------------------------------------------ 加锁语义


def test_exclusive_lock_blocks_second_acquire_and_reports_holder(data_root: Path) -> None:
    with acquire_data_lock(data_root, exclusive=True, label="api") as lock:
        assert lock.path == lock_path(data_root)
        assert lock.path.name == LOCK_FILE_NAME
        assert lock.exclusive is True

        holder = data_lock_holder(data_root)
        assert holder is not None
        assert f"pid={os.getpid()}" in holder
        assert "排他锁" in holder

        # 同一进程的另一个 fd 也拿不到：锁是操作系统级句柄锁，不是内存标记
        with pytest.raises(AppError) as excinfo:
            acquire_data_lock(data_root, exclusive=True)
        error = excinfo.value
        assert error.code == "DATA_LOCK_BUSY"
        assert error.status_code == 409
        assert error.retryable is True
        assert str(os.getpid()) in str(error)

    # 释放后可再次获取；close 幂等
    again = acquire_data_lock(data_root, exclusive=True)
    again.close()
    again.close()
    assert data_lock_holder(data_root) is None
    assert read_lock_info(data_root) is None


def test_shared_locks_coexist_but_block_exclusive(data_root: Path) -> None:
    first = acquire_data_lock(data_root, exclusive=False)
    second = acquire_data_lock(data_root, exclusive=False)
    try:
        with pytest.raises(AppError) as excinfo:
            acquire_data_lock(data_root, exclusive=True)
        assert excinfo.value.code == "DATA_LOCK_BUSY"
    finally:
        first.close()
        second.close()
    third = acquire_data_lock(data_root, exclusive=True)
    third.close()


def test_blocking_acquire_waits_then_reports_busy(data_root: Path) -> None:
    held = acquire_data_lock(data_root, exclusive=True)
    started = time.monotonic()
    try:
        with pytest.raises(AppError) as excinfo:
            acquire_data_lock(data_root, exclusive=True, blocking=True, timeout=0.3)
        assert excinfo.value.code == "DATA_LOCK_BUSY"
        assert time.monotonic() - started >= 0.3
    finally:
        held.close()


def test_lock_is_cross_process_and_released_on_process_exit(data_root: Path) -> None:
    """子进程崩溃/退出后锁由操作系统释放，不留下"锁文件存在即占用"的假锁。"""
    program = (
        "import sys;"
        f"sys.path.insert(0, r'{API_ROOT}');"
        "from pathlib import Path;"
        "from app.core.data_lock import acquire_data_lock;"
        "from app.core.exceptions import AppError;"
        "root = Path(sys.argv[1]);"
        "\ntry:\n"
        "    lock = acquire_data_lock(root, exclusive=True)\n"
        "except AppError as exc:\n"
        "    print('BUSY', exc.code); sys.exit(3)\n"
        "print('LOCKED'); sys.exit(0)\n"
    )
    holder = acquire_data_lock(data_root, exclusive=True, label="parent")
    try:
        result = subprocess.run(
            [sys.executable, "-c", program, str(data_root)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(API_ROOT),
        )
        assert result.returncode == 3, result.stdout + result.stderr
        assert "BUSY DATA_LOCK_BUSY" in result.stdout
    finally:
        holder.close()

    # 父进程已释放：子进程逻辑此时应能拿到锁
    result = subprocess.run(
        [sys.executable, "-c", program, str(data_root)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(API_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LOCKED" in result.stdout


# ------------------------------------------------------------------------ 恢复状态


def test_plain_data_root_has_no_restore_state_and_passes_gate(data_root: Path) -> None:
    assert restore_state(data_root) is None
    require_data_root_ready(data_root)  # 不抛


def test_incomplete_restore_state_refuses_startup(data_root: Path) -> None:
    write_restore_state(
        data_root,
        status=RESTORE_STATUS_INCOMPLETE,
        failures=["缺失文件：textbooks/blobs/abc"],
        restoredFrom="X:/backups/one",
    )
    state = restore_state(data_root)
    assert state is not None and state["status"] == RESTORE_STATUS_INCOMPLETE
    assert state["startedAt"]

    with pytest.raises(AppError) as excinfo:
        require_data_root_ready(data_root)
    error = excinfo.value
    assert error.code == "DATA_RESTORE_INCOMPLETE"
    assert error.status_code == 503
    assert error.retryable is False
    assert "缺失文件" in str(error)

    # 第二次写入保留 startedAt 与失败明细（失败记录不会被后续写入抹掉）
    write_restore_state(data_root, status=RESTORE_STATUS_INCOMPLETE, note="仍在恢复")
    merged = restore_state(data_root)
    assert merged is not None
    assert merged["startedAt"] == state["startedAt"]
    assert merged["failures"] == ["缺失文件：textbooks/blobs/abc"]
    assert merged["note"] == "仍在恢复"

    ready = write_restore_state(data_root, status=RESTORE_STATUS_READY, failures=[])
    assert ready["status"] == RESTORE_STATUS_READY
    require_data_root_ready(data_root)  # 不抛


def test_unknown_or_corrupt_restore_state_fails_closed(data_root: Path) -> None:
    with pytest.raises(AppError) as excinfo:
        write_restore_state(data_root, status="halfway")
    assert excinfo.value.code == "INVALID_REQUEST"

    (data_root / "restore-state.json").write_text(
        '{"status": "weird"}', encoding="utf-8"
    )
    with pytest.raises(AppError) as excinfo:
        require_data_root_ready(data_root)
    assert excinfo.value.code == "DATA_RESTORE_INCOMPLETE"

    (data_root / "restore-state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(AppError) as excinfo:
        restore_state(data_root)
    assert excinfo.value.code == "DATA_RESTORE_STATE_CORRUPT"
