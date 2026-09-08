"""配置加载：默认值必须回环安全，环境变量覆盖可解析。"""

from __future__ import annotations

import pytest

from app.core.config import Settings


def test_defaults_are_loopback_safe():
    settings = Settings.from_env(environ={})
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert "http://127.0.0.1:5173" in settings.allowed_origins
    assert "http://127.0.0.1:5174" in settings.allowed_origins
    assert settings.env == "development"


def test_env_overrides():
    settings = Settings.from_env(
        environ={
            "ZQKY_API_PORT": "8001",
            "ZQKY_ALLOWED_ORIGINS": "http://127.0.0.1:5174",
            "ZQKY_ENV": "test",
        }
    )
    assert settings.port == 8001
    assert settings.allowed_origins == frozenset({"http://127.0.0.1:5174"})
    assert settings.env == "test"


def test_rejects_non_loopback_host():
    with pytest.raises(ValueError, match="回环"):
        Settings.from_env(environ={"ZQKY_API_HOST": "0.0.0.0"})


def test_rejects_bad_port():
    with pytest.raises(ValueError, match="整数"):
        Settings.from_env(environ={"ZQKY_API_PORT": "not-a-port"})
    with pytest.raises(ValueError, match="范围"):
        Settings.from_env(environ={"ZQKY_API_PORT": "70000"})
