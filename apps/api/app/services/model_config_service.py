"""模型配置服务层：跨 `.env`（凭证）与 JSON（非敏感配置）写入的原子性与补偿（R-01）。

R-01 的两类失败序列：
1. 更新连接时凭证先写成功、随后配置 JSON 保存失败 → 旧 Key 已被覆盖，需要回滚；
2. 删除连接时配置先删成功、随后凭证删除失败 → 留下孤儿凭证，需要补偿。

本服务的策略（MR-04/MR-05 修正后）：
- 更新/删除的 revision 校验、文档变更与凭证写入共用仓储的同一临界区
  (`ModelConfigRepository.run_atomic`)，并发请求不会交错，也不会用过期 revision
  回滚别人刚写入的凭证。
- 更新：凭证快照 → 写新值 → 落盘；落盘失败按快照回滚（含"原先无凭证"）。
- 删除：先校验引用与 revision，再清理凭证，最后落盘；落盘失败恢复凭证。
  凭证清理失败则整体不删，避免"配置已删、凭证仍在"的孤儿状态。
- 创建：配置保存失败则删除刚写入的凭证。
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
    """连接增删改的唯一写入者；凭证与配置的原子写入和补偿都在此完成。"""

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

        # 快照在进入临界区时读取；回滚只在同一临界区内的落盘失败时发生。
        def credential_side_effect() -> Callable[[], None] | None:
            had_before = self._secrets.has(connection_id)
            previous_value = self._secrets.resolve(connection_id)
            touched = False
            if action == CREDENTIAL_CLEAR:
                self._secrets.delete(connection_id)
                touched = True
            elif action == CREDENTIAL_REPLACE and api_key:
                self._secrets.put(connection_id, api_key)
                touched = True
            if not touched:
                return None

            def rollback() -> None:
                if had_before and previous_value is not None:
                    self._secrets.put(connection_id, previous_value)
                else:
                    self._secrets.delete(connection_id)

            return rollback

        return self._repo.update_connection_atomic(
            connection_id,
            apply,
            expected_revision=expected_revision,
            credential_side_effect=credential_side_effect,
        )

    # --- 删除 -----------------------------------------------------------
    def delete_connection(self, connection_id: str, expected_revision: int | None) -> None:
        def credential_side_effect() -> Callable[[], None] | None:
            had_credential = self._secrets.has(connection_id)
            previous_value = self._secrets.resolve(connection_id)
            if not had_credential:
                return None
            # 清理失败直接抛出：整体不落盘，配置与凭证都保持原状，可安全重试。
            self._secrets.delete(connection_id)

            def restore() -> None:
                if previous_value is not None:
                    self._secrets.put(connection_id, previous_value)

            return restore

        self._repo.delete_connection_atomic(
            connection_id,
            expected_revision=expected_revision,
            credential_side_effect=credential_side_effect,
        )

    # --- 迁移 -----------------------------------------------------------
    # 迁移只在首次真实写入时发生（见 ModelConfigRepository._save）；这里不提供
    # 会自增 revision 的空操作入口，避免读取路径意外改写文件。


__all__ = [
    "CREDENTIAL_CLEAR",
    "CREDENTIAL_KEEP",
    "CREDENTIAL_REPLACE",
    "ModelConfigService",
]
