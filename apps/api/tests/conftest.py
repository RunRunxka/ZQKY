"""测试公共夹具：后端测试统一使用 8001 端口语义、受控来源列表与临时数据目录。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# 隔离默认数据根：`app.main` 在**导入时**执行模块级 ``create_app()``，会对默认数据根
# （仓库 `.local-data`）建库与迁移。测试不得读写正式 .local-data，因此在导入 app.main
# 之前把默认目录指到会话级临时目录；调用方显式提供 ZQKY_DATA_DIR 时尊重其设置。
_PYTEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="zqky-pytest-data-"))
os.environ.setdefault("ZQKY_DATA_DIR", str(_PYTEST_DATA_DIR))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})


@pytest.fixture(scope="session", autouse=True)
def _pytest_data_dir_lifecycle():
    """会话结束后清理隔离数据根（不给下一个进程留垃圾目录）。"""
    yield
    shutil.rmtree(_PYTEST_DATA_DIR, ignore_errors=True)


def make_settings(data_dir: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=data_dir,
    )


@pytest.fixture()
def client(tmp_path: Path):
    with TestClient(
        create_app(make_settings(tmp_path / "data")), base_url="http://127.0.0.1:8001"
    ) as test_client:
        yield test_client


@pytest.fixture()
def foreign_host_client(tmp_path: Path):
    # 默认 base_url 为 http://testserver，用于模拟非回环 Host 的请求
    with TestClient(create_app(make_settings(tmp_path / "data"))) as test_client:
        yield test_client
