"""跨库发布协调器测试（TEACHING-LOOP B1 / CTRL）。

覆盖：同线程可重入、并发获取超时 409 且错误信息含持有者操作名、释放后可再次获取。
"""

from __future__ import annotations

import threading
import time

import pytest

from app.core.exceptions import AppError
from app.services.publication import PublicationCoordinator


def test_reentrant_acquire_in_same_thread() -> None:
    coordinator = PublicationCoordinator(timeout=1.0)
    with coordinator.publication(operation="knowledge.import.confirm"):
        with coordinator.publication(operation="knowledge.archive"):
            assert coordinator.busy is True
    assert coordinator.busy is False


def test_concurrent_acquire_times_out_with_busy_error() -> None:
    coordinator = PublicationCoordinator(timeout=0.2)
    release = threading.Event()
    entered = threading.Event()

    def holder() -> None:
        with coordinator.publication(operation="knowledge.import.confirm"):
            entered.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=holder)
    thread.start()
    try:
        assert entered.wait(timeout=5)
        with pytest.raises(AppError) as error:
            with coordinator.publication(operation="knowledge.archive"):
                pass
        assert error.value.code == "PUBLICATION_BUSY"
        assert error.value.status_code == 409
        assert error.value.retryable is True
        assert "knowledge.import.confirm" in str(error.value)
    finally:
        release.set()
        thread.join(timeout=5)
    # 释放后可再次获取
    with coordinator.publication(operation="knowledge.archive"):
        pass


def test_release_happens_on_exception() -> None:
    coordinator = PublicationCoordinator(timeout=0.2)
    with pytest.raises(RuntimeError):
        with coordinator.publication(operation="boom"):
            raise RuntimeError("boom")
    assert coordinator.busy is False
    started = time.monotonic()
    with coordinator.publication(operation="after"):
        pass
    assert time.monotonic() - started < 0.2
