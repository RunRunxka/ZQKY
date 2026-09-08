"""进程内凭证存储：凭证只写入、不返回明文，服务重启即失效。

D03 明确采用“仅当前服务进程使用”方案；磁盘加密存储属后续增强，
在此之前不得把任何凭证写入文件、日志或错误信息。
"""

from __future__ import annotations

import threading


class SecretStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._secrets: dict[str, str] = {}

    def put(self, key_id: str, value: str) -> None:
        with self._lock:
            self._secrets[key_id] = value

    def resolve(self, key_id: str) -> str | None:
        with self._lock:
            return self._secrets.get(key_id)

    def has(self, key_id: str) -> bool:
        with self._lock:
            return key_id in self._secrets

    def delete(self, key_id: str) -> None:
        with self._lock:
            self._secrets.pop(key_id, None)
