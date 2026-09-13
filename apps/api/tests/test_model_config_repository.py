"""模型配置仓储：原子写入、revision、损坏保护与持久化。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import (
    ConfigCorruptedError,
    InvalidRequestError,
    NotFoundError,
    RevisionConflictError,
)
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import (
    ModelProtocol,
    ModelConnection,
    ModelProfile,
    now_utc,
)


def make_connection(connection_id: str = "conn-1") -> ModelConnection:
    return ModelConnection(
        id=connection_id,
        displayName="测试连接",
        protocol=ModelProtocol.openai_chat,
        baseUrl="https://api.example.com/v1",
        createdAt=now_utc(),
        updatedAt=now_utc(),
    )


def make_profile(profile_id: str = "prof-1", connection_id: str = "conn-1") -> ModelProfile:
    return ModelProfile(
        id=profile_id,
        connectionId=connection_id,
        displayName="测试模型",
        modelId="test-model",
        createdAt=now_utc(),
        updatedAt=now_utc(),
    )


def test_create_and_persist_roundtrip(tmp_path: Path):
    path = tmp_path / "model-config.json"
    repo = ModelConfigRepository(path)
    repo.create_connection(make_connection())

    reloaded = ModelConfigRepository(path)
    assert [c.id for c in reloaded.list_connections()] == ["conn-1"]
    data = json.loads(path.read_text(encoding="utf-8"))
    # contract-v1：新写入的文档为 schemaVersion 2。
    # providerId 保持 None 是允许的（仓库直建的旧式对象），迁移只在读取 v1 文档时发生。
    assert data["schemaVersion"] == 2
    assert data["connections"][0]["providerId"] is None
    assert data["revision"] == 2


def test_update_with_expected_revision_conflict(tmp_path: Path):
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    repo.create_connection(make_connection())
    revision = repo.revision()

    with pytest.raises(RevisionConflictError):
        repo.update_connection(
            "conn-1",
            lambda c: setattr(c, "displayName", "改名"),
            expected_revision=revision - 1,
        )
    assert repo.list_connections()[0].displayName == "测试连接"


def test_delete_referenced_connection_blocked(tmp_path: Path):
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    repo.create_connection(make_connection())
    repo.create_profile(make_profile())
    with pytest.raises(InvalidRequestError):
        repo.delete_connection("conn-1")


def test_missing_profile_raises_not_found(tmp_path: Path):
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    with pytest.raises(NotFoundError):
        repo.get_profile("missing")


def test_corrupted_file_not_overwritten(tmp_path: Path):
    path = tmp_path / "model-config.json"
    path.write_text("{broken", encoding="utf-8")
    repo = ModelConfigRepository(path)
    with pytest.raises(ConfigCorruptedError):
        repo.list_connections()
    assert path.read_text(encoding="utf-8") == "{broken"
