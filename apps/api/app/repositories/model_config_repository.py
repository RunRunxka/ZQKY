"""模型配置仓储：单个 JSON 文件，原子写入、revision 冲突检测、无数据库。"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from app.core.exceptions import (
    ConfigCorruptedError,
    InvalidRequestError,
    NotFoundError,
    RevisionConflictError,
)
from app.schemas.model_config import (
    ModelConfigDocument,
    ModelConnection,
    ModelProfile,
    now_utc,
)

T = TypeVar("T")

CREDENTIAL_SCOPE = "process"


class ModelConfigRepository:
    """串行化的配置读写；调用方在 create_app 时注入路径，测试使用临时目录。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> ModelConfigDocument:
        if not self._path.exists():
            return ModelConfigDocument()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return ModelConfigDocument.model_validate(raw)
        except (OSError, ValueError) as exc:
            raise ConfigCorruptedError(
                f"模型配置文件损坏或无法读取：{self._path.name}；请备份后修复，服务不会自动覆盖。"
            ) from exc

    def _save(self, document: ModelConfigDocument) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        tmp.write_text(
            document.model_dump_json(indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    def mutate(self, mutator: Callable[[ModelConfigDocument], T]) -> T:
        with self._lock:
            document = self._load()
            result = mutator(document)
            document.revision += 1
            self._save(document)
            return result

    def with_document(self, reader: Callable[[ModelConfigDocument], T]) -> T:
        with self._lock:
            return reader(self._load())

    def _check_revision(self, document: ModelConfigDocument, expected_revision: int | None) -> None:
        if expected_revision is not None and expected_revision != document.revision:
            raise RevisionConflictError(
                f"配置已被其他操作更新（当前 revision={document.revision}），请刷新后重试。"
            )

    def _require_connection(self, document: ModelConfigDocument, connection_id: str) -> ModelConnection:
        for connection in document.connections:
            if connection.id == connection_id:
                return connection
        raise NotFoundError("模型连接不存在。")

    def _require_profile(self, document: ModelConfigDocument, profile_id: str) -> ModelProfile:
        for profile in document.profiles:
            if profile.id == profile_id:
                return profile
        raise NotFoundError("模型配置不存在。")

    # 连接

    def create_connection(self, connection: ModelConnection) -> ModelConnection:
        def mutate(document: ModelConfigDocument) -> ModelConnection:
            document.connections.append(connection)
            return connection

        return self.mutate(mutate)

    def update_connection(
        self,
        connection_id: str,
        apply: Callable[[ModelConnection], None],
        expected_revision: int | None = None,
    ) -> ModelConnection:
        def mutate(document: ModelConfigDocument) -> ModelConnection:
            self._check_revision(document, expected_revision)
            connection = self._require_connection(document, connection_id)
            previous = connection.model_dump()
            apply(connection)
            if any(previous[key] != getattr(connection, key) for key in ('protocol', 'baseUrl', 'extraHeaders')):
                for profile in document.profiles:
                    if profile.connectionId == connection_id:
                        profile.capabilities = {"chat": "unknown", "stream": "unknown"}
            connection.updatedAt = now_utc()
            return connection

        return self.mutate(mutate)

    def delete_connection(self, connection_id: str, expected_revision: int | None = None) -> None:
        def mutate(document: ModelConfigDocument) -> None:
            self._check_revision(document, expected_revision)
            self._require_connection(document, connection_id)
            if any(profile.connectionId == connection_id for profile in document.profiles):
                raise InvalidRequestError(
                    "该连接仍被模型配置引用，请先删除相关模型配置。",
                    code="CONFLICT",
                    status_code=409,
                )
            document.connections = [
                c for c in document.connections if c.id != connection_id
            ]

        self.mutate(mutate)

    def list_connections(self) -> list[ModelConnection]:
        return self.with_document(lambda document: list(document.connections))

    def get_connection(self, connection_id: str) -> ModelConnection:
        return self.with_document(lambda document: self._require_connection(document, connection_id))

    # 模型配置

    def create_profile(self, profile: ModelProfile) -> ModelProfile:
        def mutate(document: ModelConfigDocument) -> ModelProfile:
            self._require_connection(document, profile.connectionId)
            if any(p.connectionId == profile.connectionId and p.modelId == profile.modelId for p in document.profiles):
                raise InvalidRequestError("该连接中已存在此模型。", code="CONFLICT", status_code=409)
            document.profiles.append(profile)
            return profile

        return self.mutate(mutate)

    def update_profile(
        self,
        profile_id: str,
        apply: Callable[[ModelProfile], None],
        expected_revision: int | None = None,
    ) -> ModelProfile:
        def mutate(document: ModelConfigDocument) -> ModelProfile:
            self._check_revision(document, expected_revision)
            profile = self._require_profile(document, profile_id)
            previous = profile.model_dump()
            apply(profile)
            self._require_connection(document, profile.connectionId)
            if any(previous[key] != getattr(profile, key) for key in ('connectionId', 'modelId', 'params', 'maxOutputTokens')):
                profile.capabilities = {"chat": "unknown", "stream": "unknown"}
            if any(p.id != profile.id and p.connectionId == profile.connectionId and p.modelId == profile.modelId for p in document.profiles):
                raise InvalidRequestError("该连接中已存在此模型。", code="CONFLICT", status_code=409)
            profile.updatedAt = now_utc()
            return profile

        return self.mutate(mutate)

    def delete_profile(self, profile_id: str, expected_revision: int | None = None) -> None:
        def mutate(document: ModelConfigDocument) -> None:
            self._check_revision(document, expected_revision)
            self._require_profile(document, profile_id)
            document.profiles = [p for p in document.profiles if p.id != profile_id]
            if document.defaultChatProfileId == profile_id:
                document.defaultChatProfileId = None

        self.mutate(mutate)

    def list_profiles(self) -> list[ModelProfile]:
        return self.with_document(lambda document: list(document.profiles))

    def get_profile(self, profile_id: str) -> ModelProfile:
        return self.with_document(lambda document: self._require_profile(document, profile_id))

    def revision(self) -> int:
        return self.with_document(lambda document: document.revision)
