"""跨库发布协调（TEACHING-LOOP B1 / CTRL 独占共享组件）。

用途：跨库引用发布（知识点归档 + 新引用、名单/原卷等后续批次）在同一进程内**串行化**，
使"核验外部修订 → 本库短事务发布"之间不被另一次归档/发布插队。

边界（不得越界）：

- 锁内**只做数据库读取与短事务**；调用模型、解析文件、写受管资产必须放在锁外。
- 这是**进程内**互斥锁，不是跨进程锁，也不是跨库原子事务：本项目只有单进程 FastAPI，
  不宣称跨库原子性；跨库一致性由"核验后冻结 + 本库快照"表达。
- 各模块不得自建第二把不共享的锁；服务通过 ``app.state.publication_coordinator`` 注入。

等锁有界：超时返回 409 ``PUBLICATION_BUSY``（可重试），不无限等待。
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.exceptions import AppError

PUBLICATION_BUSY = "PUBLICATION_BUSY"
DEFAULT_TIMEOUT_SECONDS = 30.0


class PublicationCoordinator:
    """进程内可重入协调器；同一线程嵌套获取不自杀（RLock）。"""

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if timeout <= 0:
            raise ValueError("timeout 必须为正数")
        self._lock = threading.RLock()
        self._timeout = float(timeout)
        self._owner: str | None = None

    @property
    def busy(self) -> bool:
        """当前是否有持有者（只用于可读报错/测试，不参与互斥判定）。"""
        return self._owner is not None

    @contextmanager
    def publication(self, *, operation: str) -> Iterator[None]:
        """进入发布临界区；把 ``operation`` 写进超时错误便于定位竞争者。"""
        acquired = self._lock.acquire(timeout=self._timeout)
        if not acquired:
            raise AppError(
                f"发布协调器正忙（{self._owner or '未知持有者'}），请稍后重试：{operation}。",
                code=PUBLICATION_BUSY,
                status_code=409,
                retryable=True,
            )
        if self._owner is None:
            self._owner = operation
        try:
            yield
        finally:
            self._owner = None
            self._lock.release()
