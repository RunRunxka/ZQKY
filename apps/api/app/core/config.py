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
# 只读原始教材目录（人教版 markdown）；仅迁移与基准导入读取，运行时不写入
DEFAULT_TEXTBOOK_SOURCE_DIR = Path("F:/人教版教材/markdown")
DEFAULT_QDRANT_URL = "http://127.0.0.1:6333"
DEFAULT_EMBEDDING_BASE_URL = "http://127.0.0.1:11434"


def _split_origins(raw: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


#: 回环主机的等价写法：开发时人最容易直接敲 localhost:5173，
#: 若默认只允许 127.0.0.1 形式，浏览器会得到难以理解的 403 FORBIDDEN_ORIGIN。
_LOOPBACK_ALIASES = ("127.0.0.1", "localhost", "[::1]")


def _with_loopback_aliases(origins: tuple[str, ...]) -> frozenset[str]:
    """给回环来源补齐等价主机名（只用于默认值；显式配置原样尊重）。"""
    expanded: set[str] = set(origins)
    for origin in origins:
        scheme, _, rest = origin.partition("://")
        if not rest:
            continue
        host, sep, port = rest.rpartition(":")
        if not sep:
            host, port = rest, ""
        if host not in _LOOPBACK_ALIASES:
            continue
        for alias in _LOOPBACK_ALIASES:
            expanded.add(f"{scheme}://{alias}{sep}{port}" if sep else f"{scheme}://{alias}")
    return frozenset(expanded)


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    allowed_origins: frozenset[str]
    env: str
    data_dir: Path
    credentials_file: Path | None = None
    # 教材/题库/知识点/教学/受管资产数据根；缺省由 data_dir 派生，测试整体注入临时目录
    textbooks_dir: Path | None = None
    question_bank_dir: Path | None = None
    knowledge_dir: Path | None = None
    teaching_dir: Path | None = None
    assets_dir: Path | None = None
    # 本机 Qdrant 与 Ollama 回环地址
    qdrant_url: str = DEFAULT_QDRANT_URL
    embedding_base_url: str = DEFAULT_EMBEDDING_BASE_URL
    textbook_source_dir: Path = DEFAULT_TEXTBOOK_SOURCE_DIR

    @property
    def textbooks_root(self) -> Path:
        return self.textbooks_dir or (self.data_dir / "textbooks")

    @property
    def question_bank_root(self) -> Path:
        return self.question_bank_dir or (self.data_dir / "question-bank")

    @property
    def knowledge_root(self) -> Path:
        """知识点库数据根（独立 SQLite；B0 起建立）。"""
        return self.knowledge_dir or (self.data_dir / "knowledge")

    @property
    def teaching_root(self) -> Path:
        """教学业务库数据根（班级/原卷/成绩/学情/教案/练习；B0 起建立）。"""
        return self.teaching_dir or (self.data_dir / "teaching")

    @property
    def assets_root(self) -> Path:
        """受管资产根（内容寻址 blobs；文件本体与数据库元数据分开）。"""
        return self.assets_dir or (self.data_dir / "assets")

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
        raw_origins = env.get("ZQKY_ALLOWED_ORIGINS")
        # 默认值补齐 localhost/127.0.0.1 等价写法；显式配置原样尊重（用户说了算）。
        origins = (
            _with_loopback_aliases(DEFAULT_ALLOWED_ORIGINS)
            if raw_origins is None
            else frozenset(_split_origins(raw_origins))
        )
        data_dir = Path(env.get("ZQKY_DATA_DIR", str(DEFAULT_DATA_DIR)))
        return Settings(
            host=host,
            port=port,
            allowed_origins=origins,
            env=env.get("ZQKY_ENV", "development"),
            data_dir=data_dir,
            credentials_file=REPO_ROOT / 'apps' / 'api' / '.env',
            qdrant_url=env.get("ZQKY_QDRANT_URL", DEFAULT_QDRANT_URL),
            embedding_base_url=env.get("ZQKY_EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL),
            textbook_source_dir=Path(
                env.get("ZQKY_TEXTBOOK_SOURCE_DIR", str(DEFAULT_TEXTBOOK_SOURCE_DIR))
            ),
        )
