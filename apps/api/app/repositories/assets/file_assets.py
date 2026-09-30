"""受管资产仓储：教学库 ``file_assets`` 表的唯一读写入口。

与其它仓储同一套纪律：每次操作独立开连接、写操作一律
``transaction(conn, immediate=True)``、事务内只做 SQL；类型来自
``app.contracts.teaching_loop``（``AssetRef`` / ``ASSET_KINDS``），不复制字段。

- ``kind`` 必须属于 ``ASSET_KINDS``，``sha256`` 必须是 64 位小写 hex，``blob_key``
  必须是 ``blobs/<64 位小写 hex>``（§3.7 的内容寻址键）；不满足一律
  ``INVALID_REQUEST``（422），不落库；
- 读取时结构非法（kind 不在白名单、散列长度/形状不对、字节数非负整数等）一律
  ``ASSET_ROW_CORRUPT``（500），**不得静默当作合法行**；
- ``create_in(conn, ...)`` 供域服务在同一 SQL 写事务内登记资产，回滚与域写入一致。
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts.teaching_loop import ASSET_KINDS, AssetRef
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.assets.store import is_managed_blob_key, is_sha256_hex

DEFAULT_OWNER_ID = "local"
MAX_LIST_LIMIT = 500


def _invalid(message: str) -> AppError:
    return AppError(message, code="INVALID_REQUEST", status_code=422)


def _corrupt(message: str) -> AppError:
    return AppError(message, code="ASSET_ROW_CORRUPT", status_code=500)


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid(f"{field} 必须是非空字符串。")
    return value


@dataclass(frozen=True)
class FileAssetRecord:
    """教学库 ``file_assets`` 一行；``ref()`` 给出对外 camelCase 引用。"""

    asset_id: str
    owner_id: str
    kind: str
    blob_key: str
    sha256: str
    original_name: str
    media_type: str
    byte_size: int
    created_at: str

    def ref(self) -> AssetRef:
        return AssetRef(
            asset_id=self.asset_id,
            kind=self.kind,
            blob_key=self.blob_key,
            sha256=self.sha256,
            media_type=self.media_type,
            byte_size=self.byte_size,
            original_name=self.original_name,
        )


class FileAssetsRepository:
    """受管资产登记仓储；调用方注入已迁移的 ``TeachingCatalog``。"""

    def __init__(self, catalog: TeachingCatalog) -> None:
        self._catalog = catalog

    # -------------------------------------------------------------- 写入

    def create(
        self,
        *,
        kind: str,
        blob_key: str,
        sha256: str,
        media_type: str,
        byte_size: int,
        original_name: str,
        owner_id: str = DEFAULT_OWNER_ID,
        asset_id: str | None = None,
    ) -> FileAssetRecord:
        """独立事务登记一条资产（先校验后落库，非法输入不产生任何行）。"""
        with self._catalog.write_transaction() as conn:
            return self.create_in(
                conn,
                kind=kind,
                blob_key=blob_key,
                sha256=sha256,
                media_type=media_type,
                byte_size=byte_size,
                original_name=original_name,
                owner_id=owner_id,
                asset_id=asset_id,
            )

    def create_in(
        self,
        conn: sqlite3.Connection,
        *,
        kind: str,
        blob_key: str,
        sha256: str,
        media_type: str,
        byte_size: int,
        original_name: str,
        owner_id: str = DEFAULT_OWNER_ID,
        asset_id: str | None = None,
    ) -> FileAssetRecord:
        """在调用方事务内登记资产；抛异常时随外层事务整体回滚。"""
        values = self._insert_values(
            kind=kind,
            blob_key=blob_key,
            sha256=sha256,
            media_type=media_type,
            byte_size=byte_size,
            original_name=original_name,
            owner_id=owner_id,
            asset_id=asset_id,
        )
        conn.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        return FileAssetRecord(
            asset_id=values[0],
            owner_id=values[1],
            kind=values[2],
            blob_key=values[3],
            sha256=values[4],
            original_name=values[5],
            media_type=values[6],
            byte_size=values[7],
            created_at=values[8],
        )

    # -------------------------------------------------------------- 读取

    def get(self, asset_id: str) -> FileAssetRecord | None:
        asset_id = _require_text(asset_id, field="asset_id")
        with self._catalog.read_connection() as conn:
            row = conn.execute(
                "SELECT * FROM file_assets WHERE id = ?", (asset_id,)
            ).fetchone()
        return self._record(row) if row is not None else None

    def get_many(self, asset_ids: Sequence[str]) -> dict[str, FileAssetRecord]:
        requested: list[str] = []
        seen: set[str] = set()
        for asset_id in asset_ids:
            text = _require_text(asset_id, field="asset_id")
            if text not in seen:
                seen.add(text)
                requested.append(text)
        if not requested:
            return {}
        placeholders = ", ".join("?" for _ in requested)
        with self._catalog.read_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM file_assets WHERE id IN ({placeholders}) ORDER BY rowid ASC",
                requested,
            ).fetchall()
        return {row["id"]: self._record(row) for row in rows}

    def list_by_kind(self, kind: str, *, limit: int = 100) -> list[FileAssetRecord]:
        kind = self._valid_kind(kind)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise _invalid("limit 必须是不小于 1 的整数。")
        if limit > MAX_LIST_LIMIT:
            raise _invalid(f"limit 不能超过 {MAX_LIST_LIMIT}。")
        with self._catalog.read_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM file_assets WHERE kind = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    # -------------------------------------------------------------- 内部

    def _insert_values(
        self,
        *,
        kind: str,
        blob_key: str,
        sha256: str,
        media_type: str,
        byte_size: int,
        original_name: str,
        owner_id: str,
        asset_id: str | None,
    ) -> tuple[str, str, str, str, str, str, str, int, str]:
        kind = self._valid_kind(kind)
        if not is_sha256_hex(sha256):
            raise _invalid("sha256 必须是 64 位小写 hex。")
        if not is_managed_blob_key(blob_key):
            raise _invalid("blob_key 必须形如 blobs/<64 位小写 hex>。")
        if blob_key != f"blobs/{sha256}":
            raise _invalid("blob_key 必须等于 blobs/<sha256>（内容寻址）。")
        if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size < 0:
            raise _invalid("byte_size 必须是不小于 0 的整数。")
        media_type = _require_text(media_type, field="media_type")
        original_name = _require_text(original_name, field="original_name")
        owner_id = _require_text(owner_id, field="owner_id")
        if asset_id is None:
            asset_id = uuid.uuid4().hex
        else:
            asset_id = _require_text(asset_id, field="asset_id")
        return (
            asset_id,
            owner_id,
            kind,
            blob_key,
            sha256,
            original_name,
            media_type,
            byte_size,
            now_iso(),
        )

    @staticmethod
    def _valid_kind(kind: object) -> str:
        if not isinstance(kind, str) or kind not in ASSET_KINDS:
            raise _invalid(f"kind 必须是 {sorted(ASSET_KINDS)} 之一。")
        return kind

    @staticmethod
    def _record(row: sqlite3.Row) -> FileAssetRecord:
        """把行映射成记录；结构非法时报 ``ASSET_ROW_CORRUPT``，不静默放行。"""
        kind = row["kind"]
        if not isinstance(kind, str) or kind not in ASSET_KINDS:
            raise _corrupt(f"教学库数据损坏：file_assets.kind 结构不符（{kind!r}）。")
        sha256 = row["sha256"]
        if not is_sha256_hex(sha256):
            raise _corrupt("教学库数据损坏：file_assets.sha256 不是 64 位小写 hex。")
        blob_key = row["blob_key"]
        if not is_managed_blob_key(blob_key):
            raise _corrupt("教学库数据损坏：file_assets.blob_key 不是受管键。")
        if blob_key != f"blobs/{sha256}":
            raise _corrupt("教学库数据损坏：file_assets.blob_key 与 sha256 不一致。")
        byte_size = row["byte_size"]
        if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size < 0:
            raise _corrupt("教学库数据损坏：file_assets.byte_size 不是非负整数。")
        for field in ("id", "owner_id", "original_name", "media_type", "created_at"):
            value = row[field]
            if not isinstance(value, str) or not value:
                raise _corrupt(f"教学库数据损坏：file_assets.{field} 不是非空字符串。")
        return FileAssetRecord(
            asset_id=row["id"],
            owner_id=row["owner_id"],
            kind=kind,
            blob_key=blob_key,
            sha256=sha256,
            original_name=row["original_name"],
            media_type=row["media_type"],
            byte_size=byte_size,
            created_at=row["created_at"],
        )
