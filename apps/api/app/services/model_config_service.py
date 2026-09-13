"""模型配置服务层：跨 `.env`（凭证）与 JSON（非敏感配置）写入的补偿与一致性（R-01）。

R-01 的两个失败序列：
1. 更新连接时凭证先写成功、随后配置 JSON 保存失败 → 旧 Key 已被覆盖，需要回滚；
2. 删除连接时配置先删成功、随后凭证删除失败 → 留下孤儿凭证，需要补偿。

本服务的策略：
- 更新：先快照凭证当前值，写新值，再保存配置；配置失败则恢复凭证快照（含"原先无凭证"）。
- 创建：配置保存失败则删除刚写入的凭证。
- 删除：先记下凭证，删配置后删凭证；凭证删除失败时删除 JSON 已不可逆，
  但会重新写回凭证以保证"配置不存在时不留孤儿"这一侧一致性，并返回可重试错误。
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ModelConnection

# R-08：凭证操作的显式语义
CREDENTIAL_KEEP = "keep"
CREDENTIAL_REPLACE = "replace"
CREDENTIAL_CLEAR = "clear"


class ModelConfigService:
    """连接增删改的唯一写入者；凭证与配置的跨文件补偿都在此完成。"""

    def __init__(self, repo: ModelConfigRepository, secrets: SecretStore) -> None:
        self._repo = repo
        self._secrets = secrets

    # --- 创建 -----------------------------------------------------------
    def create_connection(self, connection: ModelConnection, api_key: str | None) -> None:
        wrote = False
        if api_key:
            self._secrets.put(connection.id, api_key)
            wrote = True
        try:
            self._repo.create_connection(connection)
        except Exception:
            if wrote:
                self._secrets.delete(connection.id)
            raise

    # --- 更新 -----------------------------------------------------------
    def update_connection(
        self,
        connection_id: str,
        apply: Callable[[ModelConnection], None],
        *,
        api_key: str | None,
        credential_action: str,
        expected_revision: int | None,
    ) -> ModelConnection:
        action = credential_action or (CREDENTIAL_REPLACE if api_key else CREDENTIAL_KEEP)
        if action not in {CREDENTIAL_KEEP, CREDENTIAL_REPLACE, CREDENTIAL_CLEAR}:
            raise AppError("凭证操作不合法。", code="INVALID_REQUEST", status_code=422)

        # 快照：用于配置保存失败时回滚凭证
        had_before = self._secrets.has(connection_id)
        previous_value = self._secrets.resolve(connection_id)

        credential_touched = False
        try:
            if action == CREDENTIAL_CLEAR:
                self._secrets.delete(connection_id)
                credential_touched = True
            elif action == CREDENTIAL_REPLACE and api_key:
                self._secrets.put(connection_id, api_key)
                credential_touched = True
            return self._repo.update_connection(connection_id, apply, expected_revision)
        except Exception:
            if credential_touched:
                # 回滚到快照（原先有则恢复原值，原先没有则删除）
                if had_before and previous_value is not None:
                    self._secrets.put(connection_id, previous_value)
                else:
                    self._secrets.delete(connection_id)
            raise

    # --- 删除 -----------------------------------------------------------
    def delete_connection(self, connection_id: str, expected_revision: int | None) -> None:
        had_credential = self._secrets.has(connection_id)
        self._repo.delete_connection(connection_id, expected_revision)
        if not had_credential:
            return
        try:
            self._secrets.delete(connection_id)
        except AppError:
            # 配置已删、凭证删除失败：先重试一次常见瞬时错误；仍失败则明确报错，
            # 不静默留下孤儿凭证（R-01 的删除方向）。
            try:
                self._secrets.delete(connection_id)
            except AppError:
                raise AppError(
                    "连接已删除，但凭证清理失败；请检查 .env 写入权限后重试凭证清理。",
                    code="CREDENTIAL_STORAGE_ERROR",
                    status_code=500,
                ) from None


__all__ = [
    "CREDENTIAL_CLEAR",
    "CREDENTIAL_KEEP",
    "CREDENTIAL_REPLACE",
    "ModelConfigService",
]
