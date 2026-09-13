"""凭证只写入不回显；生产使用后端 .env，注入测试实例默认仅存内存。"""

from __future__ import annotations

import threading
import json
import os
import re
import uuid
from pathlib import Path
from app.core.exceptions import AppError

PREFIX = 'ZQKY_API_KEY_'

# 凭证键必须能被文件型存储安全地写成 .env 变量名后缀（MR-03）。
KEY_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]+')


def scoped_key(scope: str, connection_id: str) -> str:
    """命名空间化的托管凭证键，例如 `codex-tokens__<连接ID>`。

    早期实现用 `codex-tokens:<id>` 这样的冒号分隔，内存存储接受但文件型
    `.env` 存储会以 `INVALID_REQUEST` 拒绝，导致"换票成功却存不进去"（MR-03）。
    这里统一用正则允许的 `__` 连接，两种存储都可用。
    """
    if not KEY_ID_PATTERN.fullmatch(scope or '') or not KEY_ID_PATTERN.fullmatch(connection_id or ''):
        raise AppError('凭证标识无效。', code='INVALID_REQUEST', status_code=422)
    return f'{scope}__{connection_id}'


LEGACY_MANAGED_PREFIXES = ('codex-tokens', 'copilot-token', 'copilot-access')


def legacy_scoped_key(scope: str, connection_id: str) -> str:
    """历史冒号形式的键，仅用于读取/清理兼容。"""
    return f'{scope}:{connection_id}'


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, str) else ''
        except ValueError:
            return ''
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


class SecretStore:
    def __init__(self, env_path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._secrets: dict[str, str] = {}
        self._env_path = env_path
        if env_path:
            try:
                lines = env_path.read_text(encoding='utf-8-sig').splitlines() if env_path.exists() else []
                for line in lines:
                    name, separator, raw = line.strip().removeprefix('export ').partition('=')
                    if separator and name.strip().startswith(PREFIX):
                        value = _parse_value(raw)
                        if value:
                            self._secrets[name.strip()[len(PREFIX):]] = value
            except OSError as exc:
                raise AppError('无法读取后端凭证文件。', code='CREDENTIAL_STORAGE_ERROR', status_code=500) from exc
            for name, value in os.environ.items():
                if name.startswith(PREFIX) and value:
                    self._secrets[name[len(PREFIX):].lower()] = value

    @property
    def scope(self) -> str:
        return 'env-file' if self._env_path else 'process'

    def _persist(self, key_id: str, value: str | None) -> None:
        if not self._env_path:
            return
        if not re.fullmatch(r'[A-Za-z0-9_-]+', key_id):
            raise AppError('凭证标识无效。', code='INVALID_REQUEST', status_code=422)
        path = self._env_path
        temporary = path.with_name(f'.env.{uuid.uuid4().hex}.tmp')
        try:
            lines = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
            name = PREFIX + key_id
            lines = [line for line in lines if line.strip().removeprefix('export ').partition('=')[0].strip() != name]
            if value is not None:
                lines.append(f'{name}={json.dumps(value, ensure_ascii=False)}')
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('x', encoding='utf-8', newline='\n') as output:
                output.write('\n'.join(lines) + '\n')
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            raise AppError('后端凭证保存失败，请检查 .env 文件权限后重试。', code='CREDENTIAL_STORAGE_ERROR', status_code=500) from exc
        finally:
            temporary.unlink(missing_ok=True)

    def put(self, key_id: str, value: str) -> None:
        with self._lock:
            self._persist(key_id, value)
            self._secrets[key_id] = value

    def resolve(self, key_id: str) -> str | None:
        with self._lock:
            return self._secrets.get(key_id)

    def has(self, key_id: str) -> bool:
        with self._lock:
            return key_id in self._secrets

    def delete(self, key_id: str) -> None:
        with self._lock:
            self._persist(key_id, None)
            self._secrets.pop(key_id, None)
