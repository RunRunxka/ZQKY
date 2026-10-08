"""凭证绑定必须**原地生效**的回归测试（2026-10-08 真机测试发现）。

缺陷背景：``lifespan`` 曾用 ``SecretStore(credentials_file)`` **替换** ``app.state.secret_store``，
而知识点/题库/原卷等域服务在 ``create_app`` 装配期就捕获了替换前那个空 store：

- 走晚绑定（``app.state.secret_store``）的路径正常 —— ``/model-catalog`` 显示
  ``callable=true``、任务受理时的冻结指纹也能写；
- 走装配期捕获引用的**冻结模型解析器**（``_frozen_model_resolver``）在任务执行时读到空
  凭证，一律 ``MODEL_NOT_CONFIGURED``（"该连接未保存凭证"）。

本测试锁住修复后的契约：同一个 store 实例 ``bind_env_file`` 之后，**早先捕获该引用的
解析器**同样能看到 .env 凭证。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ModelConnection, ModelProfile, ModelProtocol, now_utc
from app.services.knowledge.service import _build_frozen_model_resolver
from app.services.model_runtime import fingerprint_of_handle, resolve_chat_model

CONNECTION_ID = "conn-bind-1"
PROFILE_ID = "prof-bind-1"


def _repo(tmp_path: Path) -> ModelConfigRepository:
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    repo.create_connection(
        ModelConnection(
            id=CONNECTION_ID,
            displayName="测试云连接",
            protocol=ModelProtocol.openai_chat,
            baseUrl="https://api.example.com/v1",
            createdAt=now_utc(),
            updatedAt=now_utc(),
        )
    )
    repo.create_profile(
        ModelProfile(
            id=PROFILE_ID,
            connectionId=CONNECTION_ID,
            displayName="测试云模型",
            modelId="m1",
            capabilities={"chat": "unknown"},
            createdAt=now_utc(),
            updatedAt=now_utc(),
        )
    )
    return repo


def test_bind_env_file_visible_to_early_captured_reference(tmp_path: Path) -> None:
    """装配期捕获的 store 引用在 bind_env_file 之后必须能看到凭证并完成冻结解析。"""
    store = SecretStore()  # 装配期的空实例（无 env 路径，只含进程环境）
    repo = _repo(tmp_path)
    frozen = _build_frozen_model_resolver(repo, store, None)  # 捕获该引用（缺陷现场）

    # 未加载 .env：云连接缺凭证 —— 与真机缺陷完全一致的可读错误
    with pytest.raises(AppError) as err:
        frozen({"profileId": PROFILE_ID, "fingerprint": "sha256:x"})
    assert err.value.code == "MODEL_NOT_CONFIGURED"

    # 启动时就地绑定（修复后的行为）
    env_file = tmp_path / ".env"
    env_file.write_text(f"ZQKY_API_KEY_{CONNECTION_ID}=sk-test\n", encoding="utf-8")
    store.bind_env_file(env_file)
    assert store.has(CONNECTION_ID) is True
    assert store.scope == "env-file"

    # 同一引用现在可以解析，并能通过冻结指纹核对
    handle = resolve_chat_model(repo, store, PROFILE_ID)
    fingerprint = fingerprint_of_handle(handle)
    resolved = frozen({"profileId": PROFILE_ID, "fingerprint": fingerprint})
    assert resolved.model_id == "m1"


def test_bind_env_file_is_idempotent_and_keeps_memory_values(tmp_path: Path) -> None:
    """重复绑定不报错、不丢已有值；文件不存在视为空凭证文件。"""
    store = SecretStore()
    store.bind_env_file(tmp_path / ".env")
    assert store.scope == "env-file"
    assert store.has(CONNECTION_ID) is False

    env_file = tmp_path / ".env"
    env_file.write_text(f"ZQKY_API_KEY_{CONNECTION_ID}=sk-test\n", encoding="utf-8")
    store.bind_env_file(env_file)
    store.bind_env_file(env_file)
    assert store.resolve(CONNECTION_ID) == "sk-test"
