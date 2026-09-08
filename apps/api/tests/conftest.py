"""测试公共夹具：后端测试统一使用 8001 端口语义、受控来源列表与临时数据目录。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://127.0.0.1:5174"})


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
