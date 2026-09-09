"""服务配置：仅从环境变量读取本机运行参数，不含任何凭证或密钥字段。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SERVICE_NAME = "zhiqikeyuan-api"
API_VERSION = "v1"

DEFAULT_ALLOWED_ORIGINS = ("http://127.0.0.1:5173", "http://127.0.0.1:5174")
# 服务只允许监听本机回环地址；0.0.0.0 等对外地址在配置阶段直接拒绝
LOCAL_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})

# 项目根 = apps/api/app/core/config.py 向上四级（core→app→api→apps→根）
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = REPO_ROOT / ".local-data"


def _split_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: frozenset[str]
    env: str
    data_dir: Path
    credentials_file: Path | None = None

    @staticmethod
    def from_env(environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        host = env.get("ZQKY_API_HOST", "127.0.0.1")
        if host not in LOCAL_HOSTNAMES:
            raise ValueError(f"ZQKY_API_HOST 只允许本机回环地址，收到：{host}")
        port_raw = env.get("ZQKY_API_PORT", "8000")
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError(f"ZQKY_API_PORT 必须是整数，收到：{port_raw}") from exc
        if not 0 <= port <= 65535:
            raise ValueError(f"ZQKY_API_PORT 超出范围，收到：{port}")
        raw_origins = env.get("ZQKY_ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS))
        data_dir = Path(env.get("ZQKY_DATA_DIR", str(DEFAULT_DATA_DIR)))
        return Settings(
            host=host,
            port=port,
            allowed_origins=frozenset(_split_origins(raw_origins)),
            env=env.get("ZQKY_ENV", "development"),
            data_dir=data_dir,
            credentials_file=REPO_ROOT / 'apps' / 'api' / '.env',
        )
