"""教材/题库/知识点库/教学库与受管资产的离线一致性备份 / 校验 / 恢复（v3）。

方案与 ``docs/PLAN.md`` §5.2、§5.3 一致：

- 备份前先取**数据根排他锁**（``app.core.data_lock``）；拿不到只报 ``DATA_LOCK_BUSY``
  并退出，**不自动停止用户进程**；
- 检查没有未结束的入库 / 整理 / 重建任务，有则拒绝备份，**不擅自修改遗留任务状态**；
- **四库**（教材目录、题库、知识点库、教学业务库）用 **SQLite backup API**
  （``sqlite3.Connection.backup``）生成一致性副本，不直接复制正在写入的 WAL 文件；
  缺任何一个库都算失败（``status: "failed"``），不悄悄少备份一个库；
- **只**从备份后的数据库读取被引用的文件（``textbooks/blobs``、``textbooks/normalized``、
  ``textbooks/staging`` 里草稿引用的产物、``question-bank/blobs``、教学库 ``file_assets``
  引用的 ``assets/blobs/<sha256>``），逐文件记录 ``bytes`` 与 ``sha256``，并核对
  "文件名 = 内容 sha256" 的内容寻址约定；
- 需要快照的 collection 走 Qdrant 官方 snapshot，下载后核对**点数、维度**并用
  ``exact=true`` 对账 payload 指纹；
- 全部通过才把 manifest 标 ``status: "complete"``；任一必需文件、原文哈希或快照缺失
  都保留失败记录、标 ``failed`` 并非零退出，**绝不输出"备份完成"**。

恢复**只写新目录**且必须显式指向隔离 Qdrant（本机回环、非 6333），按应用真实布局生成
``textbooks/catalog.sqlite3``、``textbooks/blobs/…``、``question-bank/question-bank.sqlite3``、
``knowledge/knowledge.sqlite3``、``teaching/teaching.sqlite3``、``assets/blobs/…`` 等，
并把 ``restore-state.json`` 留在 ``incomplete``/``ready`` 供应用启动检查。恢复完成后对
**恢复到本目录的每个库**做 ``PRAGMA integrity_check`` + ``foreign_key_check``，并从恢复后的
教学库重新推导 ``file_assets`` 引用逐文件重算 sha256。``schema_migrations`` 是库内表，
随库一起备份/恢复，恢复过程不改写它。

清单版本：``schemaVersion: 3``（四库 + 资产）；既有 ``schemaVersion: 2``（两库）与
legacy（无版本/1）清单仍可 verify / restore，语义不变。

用法::

    uv run --directory apps/api python ../../scripts/rag/backup.py create --label pre-migration
    uv run --directory apps/api python ../../scripts/rag/backup.py verify --path <备份目录>
    uv run --directory apps/api python ../../scripts/rag/backup.py restore \\
        --path <备份目录> --into <新目录> --isolated-qdrant http://127.0.0.1:16333

退出码：``0`` 成功；``1`` 已记录失败（清单 ``status: failed`` 或恢复留下
``incomplete``）；``2`` 未写任何文件的拒绝（锁占用、未结束任务、目标已存在、
Qdrant 地址不是隔离实例、清单缺失或路径穿越）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import httpx  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.data_lock import (  # noqa: E402
    RESTORE_STATUS_INCOMPLETE,
    RESTORE_STATUS_READY,
    acquire_data_lock,
    write_restore_state,
)
from app.core.exceptions import AppError  # noqa: E402
from app.core.sqlite import now_iso  # noqa: E402
from app.providers.embeddings.fingerprint import sha256_hex  # noqa: E402
from app.repositories.textbook_catalog.records import ChunkInput  # noqa: E402
from app.services.assets.store import is_managed_blob_key, is_sha256_hex  # noqa: E402
from app.services.document_parsing import chunk_manifest_sha256  # noqa: E402

BACKUP_ROOT = REPO_ROOT / "_work" / "rag-backups"
SCHEMA_VERSION = 3
#: 旧两库清单版本；仍然只读兼容 verify/restore
SCHEMA_VERSION_V2 = 2
MANIFEST_NAME = "manifest.json"

#: 正式 Qdrant 端口；恢复时明确拒绝，绝不覆盖正式 collection
FORMAL_QDRANT_PORT = 6333
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

ROLE_TEXTBOOK_CATALOG = "textbook-catalog"
ROLE_TEXTBOOK_BLOB = "textbook-blob"
ROLE_TEXTBOOK_NORMALIZED = "textbook-normalized"
ROLE_TEXTBOOK_STAGING = "textbook-staging"
ROLE_QUESTION_CATALOG = "question-bank-catalog"
ROLE_QUESTION_BLOB = "question-bank-blob"
ROLE_KNOWLEDGE_CATALOG = "knowledge-catalog"
ROLE_TEACHING_CATALOG = "teaching-catalog"
ROLE_ASSET_BLOB = "asset-blob"

#: 教材区域的运行目录名 → 清单角色
TEXTBOOK_AREA_ROLES = {
    "blobs": ROLE_TEXTBOOK_BLOB,
    "normalized": ROLE_TEXTBOOK_NORMALIZED,
    "staging": ROLE_TEXTBOOK_STAGING,
}
QUESTION_AREA_ROLES = {"blobs": ROLE_QUESTION_BLOB}
#: 受管资产区域：归档 ``files/assets/<blob_key>`` → 恢复 ``assets/<blob_key>``
ASSET_AREA_ROLES = {"blobs": ROLE_ASSET_BLOB}
BLOB_ROLES = (
    frozenset(TEXTBOOK_AREA_ROLES.values())
    | frozenset(QUESTION_AREA_ROLES.values())
    | frozenset(ASSET_AREA_ROLES.values())
)

TEXTBOOK_CATALOG_ARCHIVE = "sqlite/textbooks-catalog.sqlite3"
TEXTBOOK_CATALOG_RESTORE = "textbooks/catalog.sqlite3"
QUESTION_CATALOG_ARCHIVE = "sqlite/question-bank.sqlite3"
QUESTION_CATALOG_RESTORE = "question-bank/question-bank.sqlite3"
KNOWLEDGE_CATALOG_ARCHIVE = "sqlite/knowledge.sqlite3"
KNOWLEDGE_CATALOG_RESTORE = "knowledge/knowledge.sqlite3"
TEACHING_CATALOG_ARCHIVE = "sqlite/teaching.sqlite3"
TEACHING_CATALOG_RESTORE = "teaching/teaching.sqlite3"

#: v3 完整清单必需的四库恢复路径（顺序即校验顺序）
CATALOG_RESTORE_PATHS = (
    TEXTBOOK_CATALOG_RESTORE,
    QUESTION_CATALOG_RESTORE,
    KNOWLEDGE_CATALOG_RESTORE,
    TEACHING_CATALOG_RESTORE,
)
#: v2 清单只覆盖两库（旧语义原样保留）
CATALOG_RESTORE_PATHS_V2 = (TEXTBOOK_CATALOG_RESTORE, QUESTION_CATALOG_RESTORE)

#: (数据根内相对路径, 归档路径, 恢复路径, 清单角色, 可读名称)
CATALOG_SPECS = (
    (
        "textbooks/catalog.sqlite3",
        TEXTBOOK_CATALOG_ARCHIVE,
        TEXTBOOK_CATALOG_RESTORE,
        ROLE_TEXTBOOK_CATALOG,
        "教材目录",
    ),
    (
        "question-bank/question-bank.sqlite3",
        QUESTION_CATALOG_ARCHIVE,
        QUESTION_CATALOG_RESTORE,
        ROLE_QUESTION_CATALOG,
        "题库数据库",
    ),
    (
        "knowledge/knowledge.sqlite3",
        KNOWLEDGE_CATALOG_ARCHIVE,
        KNOWLEDGE_CATALOG_RESTORE,
        ROLE_KNOWLEDGE_CATALOG,
        "知识点库",
    ),
    (
        "teaching/teaching.sqlite3",
        TEACHING_CATALOG_ARCHIVE,
        TEACHING_CATALOG_RESTORE,
        ROLE_TEACHING_CATALOG,
        "教学业务库",
    ),
)

RESTORE_PATH_PREFIXES = ("textbooks/", "question-bank/", "knowledge/", "teaching/", "assets/")
#: 受管资产归档目录前缀（归档路径 = ``files/assets/<blob_key>``）
ASSET_ARCHIVE_PREFIX = "files/assets/"
#: 草稿处于这些状态时预览/继续编辑不再需要 staging 产物
FINAL_IMPORT_STATES = frozenset({"ready", "cancelled"})
#: 未完成的临时文件不是有效草稿产物，永不收录
TEMPORARY_PREFIXES = ("tmp-",)
TEMPORARY_MARKERS = (".tmp-",)

QDRANT_TIMEOUT_SECONDS = 120.0
QDRANT_SCROLL_LIMIT = 1000
QDRANT_POINT_PAYLOAD_FIELDS = (
    "document_revision_id",
    "chunk_set_id",
    "ordinal",
    "text_sha256",
)


class BackupRefused(Exception):
    """安全拒绝：未写任何文件（锁占用、未结束任务、目标已存在、参数非法、路径穿越）。"""


class BackupFailed(Exception):
    """已开始写文件后失败（恢复中失败会把 restore-state 留在 incomplete）。"""


# --------------------------------------------------------------------------- 基础工具


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_temporary_file(name: str) -> bool:
    """未完成的临时产物（``tmp-*.part`` / ``*.tmp-*``）不是有效数据。"""
    return name.startswith(TEMPORARY_PREFIXES) or any(
        marker in name for marker in TEMPORARY_MARKERS
    )


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_atomic(path: Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def copy_hashed(source: Path, target: Path) -> tuple[int, str]:
    """复制并同时计算大小与 sha256（单次顺序读）。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as reader, target.open("wb") as writer:
        for block in iter(lambda: reader.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
            writer.write(block)
    return size, digest.hexdigest()


def open_sqlite(path: Path) -> sqlite3.Connection:
    """打开数据库读数据。

    连接本身允许写：SQLite 在打开 WAL 库时需要完成 WAL 恢复/检查点，只读连接会直接
    失败。调用方只执行 SELECT / ``backup``，**不**修改逻辑数据（锁已保证无并发写者）。
    """
    connection = sqlite3.connect(str(path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    return connection


def sqlite_snapshot(source: Path, target: Path) -> None:
    """用 SQLite backup API 生成一致性副本；不直接复制 WAL。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    source_connection = open_sqlite(source)
    try:
        target_connection = sqlite3.connect(str(target), isolation_level=None)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
    finally:
        source_connection.close()
    if target.stat().st_size == 0:
        raise BackupFailed(f"生成的数据库副本为空：{target}")


def sqlite_quick_check(path: Path) -> str:
    """返回 ``ok`` 或具体损坏信息；用于备份副本与恢复目录的自检。"""
    connection = open_sqlite(path)
    try:
        row = connection.execute("PRAGMA quick_check").fetchone()
        return str(row[0]) if row is not None else "quick_check 无返回"
    finally:
        connection.close()


# --------------------------------------------------------------------------- Qdrant


def _qdrant_unavailable(base_url: str, detail: str) -> AppError:
    return AppError(
        f"向量库不可用（{base_url}）：{detail}",
        code="QDRANT_UNAVAILABLE",
        status_code=503,
        retryable=True,
    )


class QdrantAdmin:
    """Qdrant 运维接口（快照 / 计数 / payload 对账）；只用官方 REST 路径。

    与 ``app/repositories/vector_store/qdrant.py`` 同一错误约定：不可达抛
    ``QDRANT_UNAVAILABLE``（503，可重试），404 抛 ``QDRANT_COLLECTION_MISSING``，
    **不**把失败降级成"没有数据"。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = QDRANT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        raw = (base_url or "").strip()
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AppError(
                "Qdrant 地址必须是 http/https URL。",
                code="QDRANT_BASE_URL_INVALID",
                status_code=422,
            )
        self.base_url = raw.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self._transport,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        allow_missing: bool = False,
        files: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response | None:
        try:
            with self._client() as client:
                response = client.request(
                    method, path, json=json_body, files=files, params=params
                )
        except httpx.HTTPError as exc:
            raise _qdrant_unavailable(self.base_url, exc.__class__.__name__) from exc
        if response.status_code >= 400:
            if response.status_code == 404 and allow_missing:
                return None
            if response.status_code == 404:
                raise AppError(
                    f"Qdrant collection 不存在（{path}）。",
                    code="QDRANT_COLLECTION_MISSING",
                    status_code=404,
                )
            if response.status_code >= 500:
                raise _qdrant_unavailable(self.base_url, f"HTTP {response.status_code}")
            raise AppError(
                f"Qdrant 拒绝了请求（HTTP {response.status_code}）：{path}",
                code="QDRANT_REQUEST_REJECTED",
                status_code=422,
            )
        return response

    def _json(self, method: str, path: str, **kwargs: Any) -> dict:
        response = self._request(method, path, **kwargs)
        if response is None:
            raise AppError(
                f"Qdrant 响应缺失（{path}）。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(
                "Qdrant 返回了非 JSON 响应。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                "Qdrant 响应顶层不是 JSON 对象。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return payload

    # ------------------------------------------------------------------ 集合

    def ping(self) -> bool:
        try:
            response = self._request("GET", "/")
        except AppError:
            return False
        return response is not None

    def collections(self) -> list[str]:
        payload = self._json("GET", "/collections")
        result = payload.get("result")
        entries = result.get("collections") if isinstance(result, dict) else None
        if not isinstance(entries, list):
            raise AppError(
                "Qdrant /collections 响应缺少 result.collections。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return [str(item.get("name")) for item in entries if isinstance(item, dict)]

    def collection_exists(self, name: str) -> bool:
        response = self._request("GET", f"/collections/{name}", allow_missing=True)
        return response is not None

    def collection_info(self, name: str) -> dict:
        """返回 ``{"dimensions","distance","pointsCount"}``；collection 不存在抛 404。"""
        payload = self._json("GET", f"/collections/{name}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise AppError(
                f"Qdrant collection 信息结构不符（{name}）。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        config = result.get("config")
        params = config.get("params") if isinstance(config, dict) else None
        vectors = params.get("vectors") if isinstance(params, dict) else None
        if not isinstance(vectors, dict):
            # 具名向量（多向量）不在本批范围内：如实报错，不猜
            raise AppError(
                f"collection {name} 不是单一未命名向量配置，无法核对维度。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return {
            "dimensions": vectors.get("size"),
            "distance": vectors.get("distance"),
            "pointsCount": result.get("points_count"),
        }

    def count_points(self, name: str, *, exact: bool = True) -> int:
        payload = self._json(
            "POST", f"/collections/{name}/points/count", json_body={"exact": bool(exact)}
        )
        result = payload.get("result")
        count = result.get("count") if isinstance(result, dict) else None
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AppError(
                "Qdrant 计数响应缺少合法 count。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return count

    # ------------------------------------------------------------------ 快照

    def create_snapshot(self, name: str) -> str:
        payload = self._json("POST", f"/collections/{name}/snapshots")
        result = payload.get("result")
        snapshot = result.get("name") if isinstance(result, dict) else None
        if not isinstance(snapshot, str) or not snapshot:
            raise AppError(
                "Qdrant 快照响应缺少 result.name。",
                code="QDRANT_INVALID_RESPONSE",
                status_code=502,
            )
        return snapshot

    def download_snapshot(self, name: str, snapshot: str) -> bytes:
        response = self._request(
            "GET", f"/collections/{name}/snapshots/{snapshot}", allow_missing=True
        )
        if response is None:
            raise AppError(
                f"Qdrant 快照不存在：{name}/{snapshot}",
                code="QDRANT_SNAPSHOT_MISSING",
                status_code=404,
            )
        return response.content

    def delete_snapshot(self, name: str, snapshot: str) -> None:
        self._request(
            "DELETE", f"/collections/{name}/snapshots/{snapshot}", allow_missing=True
        )

    def restore_snapshot(
        self,
        *,
        collection: str,
        snapshot_path: Path,
        priority: str = "snapshot",
        wait: bool = True,
    ) -> None:
        """用上传快照的方式在目标实例新建 collection（绝不覆盖既有 collection）。"""
        path = Path(snapshot_path)
        if not path.is_file():
            raise AppError(
                f"快照文件不存在：{path}",
                code="QDRANT_SNAPSHOT_MISSING",
                status_code=404,
            )
        with self._client() as client:
            try:
                response = client.post(
                    f"/collections/{collection}/snapshots/upload",
                    params={"priority": priority, "wait": "true" if wait else "false"},
                    files={"snapshot": (path.name, path.read_bytes(), "application/octet-stream")},
                )
            except httpx.HTTPError as exc:
                raise _qdrant_unavailable(self.base_url, exc.__class__.__name__) from exc
        if response.status_code >= 400:
            if response.status_code >= 500:
                raise _qdrant_unavailable(self.base_url, f"HTTP {response.status_code}")
            raise AppError(
                f"Qdrant 拒绝恢复快照（HTTP {response.status_code}）：{collection}",
                code="QDRANT_REQUEST_REJECTED",
                status_code=422,
            )

    # ------------------------------------------------------------------ payload 对账

    def point_manifest(self, name: str) -> str:
        """对 payload 的确定性指纹：point id + 关键字段排序后 sha256。"""
        lines: list[str] = []
        offset: object | None = None
        while True:
            body: dict = {
                "limit": QDRANT_SCROLL_LIMIT,
                "with_payload": list(QDRANT_POINT_PAYLOAD_FIELDS),
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            payload = self._json("POST", f"/collections/{name}/points/scroll", json_body=body)
            result = payload.get("result")
            points = result.get("points") if isinstance(result, dict) else None
            if not isinstance(points, list):
                raise AppError(
                    "Qdrant scroll 响应缺少 result.points。",
                    code="QDRANT_INVALID_RESPONSE",
                    status_code=502,
                )
            for point in points:
                if not isinstance(point, dict):
                    continue
                item = point.get("payload")
                item = item if isinstance(item, dict) else {}
                fields = [str(point.get("id"))]
                for key in QDRANT_POINT_PAYLOAD_FIELDS:
                    fields.append(str(item.get(key, "")))
                lines.append("\t".join(fields))
            offset = result.get("next_page_offset") if isinstance(result, dict) else None
            if offset is None or not points:
                break
        lines.sort()
        return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def ensure_isolated_qdrant_url(url: str | None) -> str:
    """恢复只允许写本机回环上的隔离实例；缺失或 6333 一律拒绝。"""
    raw = (url or "").strip()
    if not raw:
        raise BackupRefused(
            "恢复必须显式指定隔离 Qdrant（--isolated-qdrant http://127.0.0.1:16333）；"
            "未指定时拒绝执行，避免误写正式 collection。"
        )
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BackupRefused(f"隔离 Qdrant 地址不是合法 http/https URL：{raw}")
    if parsed.hostname not in LOOPBACK_HOSTS:
        raise BackupRefused(
            f"隔离 Qdrant 必须是本机回环地址（{sorted(LOOPBACK_HOSTS)}），收到：{parsed.hostname}"
        )
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if port == FORMAL_QDRANT_PORT:
        raise BackupRefused(
            f"恢复拒绝指向正式 Qdrant 端口 {FORMAL_QDRANT_PORT}（{raw}）："
            "请使用隔离实例（如 16333），绝不覆盖正式 collection。"
        )
    return raw


# --------------------------------------------------------------------------- 清单


@dataclass(frozen=True)
class BlobNeed:
    """一个被数据库引用的 blob；``candidates`` 是允许出现的区域（按优先级）。"""

    kind: str
    blob_id: str
    candidates: tuple[str, ...]
    require_staging: bool
    reason: str


def _textbook_blob_needs(db_path: Path) -> tuple[list[BlobNeed], list[str]]:
    """从**备份后的**教材目录读出所有被引用的 blob（修订原件、规范化文本、草稿产物）。"""
    needs: list[BlobNeed] = []
    failures: list[str] = []
    connection = open_sqlite(db_path)
    try:
        for row in connection.execute(
            "SELECT id, original_blob_id, normalized_blob_id, source_map_blob_id "
            "FROM document_revisions ORDER BY rowid ASC"
        ):
            needs.append(
                BlobNeed(
                    "textbook",
                    str(row["original_blob_id"]),
                    ("blobs",),
                    False,
                    f"修订 {row['id']} 的教材原件",
                )
            )
            needs.append(
                BlobNeed(
                    "textbook",
                    str(row["normalized_blob_id"]),
                    ("normalized",),
                    False,
                    f"修订 {row['id']} 的规范化正文",
                )
            )
            needs.append(
                BlobNeed(
                    "textbook",
                    str(row["source_map_blob_id"]),
                    ("normalized",),
                    False,
                    f"修订 {row['id']} 的来源映射",
                )
            )
        for row in connection.execute(
            "SELECT id, state, uploaded_blob_id, parsed_artifacts_json "
            "FROM import_drafts ORDER BY rowid ASC"
        ):
            preview_needed = str(row["state"]) not in FINAL_IMPORT_STATES
            needs.append(
                BlobNeed(
                    "textbook",
                    str(row["uploaded_blob_id"]),
                    ("blobs", "staging"),
                    False,
                    f"导入草稿 {row['id']} 的上传原件",
                )
            )
            raw = row["parsed_artifacts_json"]
            artifacts = json.loads(raw) if isinstance(raw, str) and raw else None
            if not isinstance(artifacts, dict):
                continue
            for key, label, require_staging in (
                ("normalizedBlobId", "规范化正文", preview_needed),
                ("sourceMapBlobId", "来源映射", False),
            ):
                blob_id = artifacts.get(key)
                if isinstance(blob_id, str) and blob_id:
                    needs.append(
                        BlobNeed(
                            "textbook",
                            blob_id,
                            ("staging", "normalized", "blobs"),
                            require_staging,
                            f"导入草稿 {row['id']} 的{label}产物",
                        )
                    )
    except sqlite3.Error as exc:
        failures.append(f"读取备份后的教材目录失败：{exc.__class__.__name__}: {exc}")
    finally:
        connection.close()
    return needs, failures


def _question_blob_needs(db_path: Path) -> tuple[list[BlobNeed], list[str]]:
    needs: list[BlobNeed] = []
    failures: list[str] = []
    connection = open_sqlite(db_path)
    try:
        for row in connection.execute(
            "SELECT id, original_blob_id FROM question_imports ORDER BY rowid ASC"
        ):
            needs.append(
                BlobNeed(
                    "question",
                    str(row["original_blob_id"]),
                    ("blobs",),
                    False,
                    f"题库导入 {row['id']} 的原件",
                )
            )
    except sqlite3.Error as exc:
        failures.append(f"读取备份后的题库数据库失败：{exc.__class__.__name__}: {exc}")
    finally:
        connection.close()
    return needs, failures


def _file_assets_rows(db_path: Path) -> tuple[list[dict], list[str]]:
    """从（备份后或恢复后的）教学库读受管资产引用行。

    行结构非法（``blob_key`` 不是 ``blobs/<64 位小写 hex>``、``sha256`` 形状不对、
    键与散列不一致、``byte_size`` 非法）如实报失败，**不当合法行**。
    """
    rows_out: list[dict] = []
    failures: list[str] = []
    connection = open_sqlite(db_path)
    try:
        for row in connection.execute(
            "SELECT id, blob_key, sha256, byte_size FROM file_assets ORDER BY rowid ASC"
        ):
            asset_id = str(row["id"])
            blob_key = row["blob_key"]
            sha256 = row["sha256"]
            if not is_managed_blob_key(blob_key):
                failures.append(
                    f"教学库 file_assets {asset_id} 的 blob_key 不是受管键：{blob_key!r}"
                )
                continue
            if not is_sha256_hex(sha256):
                failures.append(
                    f"教学库 file_assets {asset_id} 的 sha256 不是 64 位小写 hex"
                )
                continue
            if blob_key != f"blobs/{sha256}":
                failures.append(
                    f"教学库 file_assets {asset_id} 的 blob_key 与 sha256 不一致（内容寻址）"
                )
                continue
            byte_size = row["byte_size"]
            if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size < 0:
                failures.append(f"教学库 file_assets {asset_id} 的 byte_size 非法")
                continue
            rows_out.append(
                {
                    "assetId": asset_id,
                    "blobKey": blob_key,
                    "sha256": sha256,
                    "byteSize": byte_size,
                }
            )
    except sqlite3.Error as exc:
        failures.append(
            f"读取教学库 file_assets 失败：{exc.__class__.__name__}: {exc}"
        )
    finally:
        connection.close()
    return rows_out, failures


def _collect_teaching_assets(
    *,
    teaching_snapshot: Path | None,
    assets_root: Path,
    destination: Path,
    files: list[dict],
) -> list[str]:
    """把教学库引用的受管资产复制进归档并逐文件校验（缺失/指纹/大小/内容寻址）。

    归档路径为 ``files/assets/<blob_key>``，恢复路径为 ``assets/<blob_key>``
    （即 ``assets/blobs/<sha256>``）。同一内容只收录一次。
    """
    if teaching_snapshot is None or not teaching_snapshot.is_file():
        return []
    rows, failures = _file_assets_rows(teaching_snapshot)
    seen: set[str] = set()
    for row in rows:
        blob_key = row["blobKey"]
        if blob_key in seen:
            continue
        seen.add(blob_key)
        label = f"受管资产 {blob_key}（file_assets {row['assetId']}）"
        source = assets_root / blob_key
        if not source.is_file():
            failures.append(f"{label} 缺失：{source}")
            continue
        archive_path = f"{ASSET_ARCHIVE_PREFIX}{blob_key}"
        archive_file = destination / archive_path
        try:
            size, digest = copy_hashed(source, archive_file)
        except OSError as exc:
            failures.append(f"{label} 复制失败：{exc.__class__.__name__}: {exc}")
            continue
        if digest != row["sha256"]:
            failures.append(
                f"{label} 内容指纹不符（实际 {digest}），源文件缺失或损坏"
            )
            archive_file.unlink(missing_ok=True)
            continue
        if size != row["byteSize"]:
            failures.append(
                f"{label} 大小不符（登记 {row['byteSize']}，实际 {size}）"
            )
            archive_file.unlink(missing_ok=True)
            continue
        files.append(
            {
                "logicalRole": ROLE_ASSET_BLOB,
                "archivePath": archive_path,
                "restorePath": f"assets/{blob_key}",
                "sourcePath": f"assets/{blob_key}",
                "bytes": size,
                "sha256": digest,
            }
        )
    return failures


def _resolve_needs(
    root: Path, needs: Sequence[BlobNeed], role_by_area: dict[str, str]
) -> tuple[list[dict], list[str]]:
    """把引用解析成实际存在的文件（每条引用可对应多个区域的同内容副本）。"""
    copies: list[dict] = []
    failures: list[str] = []
    for need in needs:
        found = [
            area for area in need.candidates if (root / area / need.blob_id).is_file()
        ]
        if not found:
            failures.append(
                f"{need.reason}：找不到 {need.blob_id}（已查区域 {', '.join(need.candidates)}）"
            )
            continue
        if need.require_staging and "staging" not in found:
            failures.append(
                f"{need.reason}：草稿预览需要 staging/{need.blob_id}，源目录中缺失"
            )
            continue
        for area in found:
            copies.append(
                {
                    "kind": need.kind,
                    "area": area,
                    "role": role_by_area[area],
                    "blob_id": need.blob_id,
                    "source": root / area / need.blob_id,
                }
            )
    return copies, failures


def _unfinished_jobs(textbook_db: Path | None, question_db: Path | None) -> list[str]:
    """列出未结束任务；只读，不修改任何任务状态。"""
    pending: list[str] = []
    if textbook_db is not None and textbook_db.is_file():
        connection = open_sqlite(textbook_db)
        try:
            for row in connection.execute(
                "SELECT id, kind, state, updated_at FROM index_jobs "
                "WHERE state IN ('queued', 'running') ORDER BY created_at ASC, rowid ASC"
            ):
                pending.append(
                    f"教材任务 {row['id']}（kind={row['kind']}, state={row['state']}, "
                    f"updated_at={row['updated_at']}）"
                )
            state_row = connection.execute(
                "SELECT rebuild_job_id FROM catalog_state WHERE id = 1"
            ).fetchone()
            if state_row is not None and state_row["rebuild_job_id"]:
                job_id = str(state_row["rebuild_job_id"])
                job = connection.execute(
                    "SELECT state FROM index_jobs WHERE id = ?", (job_id,)
                ).fetchone()
                detail = f"，任务状态 {job['state']}" if job is not None else "，任务行不存在"
                pending.append(f"重建指针 catalog_state.rebuild_job_id={job_id}{detail}")
        except sqlite3.Error as exc:
            pending.append(f"读取教材任务状态失败：{exc.__class__.__name__}")
        finally:
            connection.close()
    if question_db is not None and question_db.is_file():
        connection = open_sqlite(question_db)
        try:
            for row in connection.execute(
                "SELECT id, kind, state, updated_at FROM question_jobs "
                "WHERE state IN ('queued', 'running') ORDER BY created_at ASC, rowid ASC"
            ):
                pending.append(
                    f"题库任务 {row['id']}（kind={row['kind']}, state={row['state']}, "
                    f"updated_at={row['updated_at']}）"
                )
        except sqlite3.Error as exc:
            pending.append(f"读取题库任务状态失败：{exc.__class__.__name__}")
        finally:
            connection.close()
    return pending


def _unfinished_extra_jobs(
    knowledge_db: Path | None, teaching_db: Path | None
) -> list[str]:
    """知识点库 / 教学库里的未结束任务（v3 新增；只读，不修改任何状态）。

    表不存在视为该库尚未迁移（迁移登记会拒绝启动），不误报为任务；读取失败如实列出。
    """
    plan = (
        (knowledge_db, "knowledge_jobs", "知识点任务"),
        (teaching_db, "workflow_jobs", "教学任务"),
    )
    pending: list[str] = []
    for db_path, table, label in plan:
        if db_path is None or not db_path.is_file():
            continue
        connection = open_sqlite(db_path)
        try:
            present = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            if present is None:
                continue
            for row in connection.execute(
                f"SELECT id, kind, state, updated_at FROM {table} "
                "WHERE state IN ('queued', 'running') ORDER BY created_at ASC, rowid ASC"
            ):
                pending.append(
                    f"{label} {row['id']}（kind={row['kind']}, state={row['state']}, "
                    f"updated_at={row['updated_at']}）"
                )
        except sqlite3.Error as exc:
            pending.append(f"读取{label}状态失败：{exc.__class__.__name__}")
        finally:
            connection.close()
    return pending


def _collection_plan(textbook_db: Path, failures: list[str]) -> list[dict]:
    """活动索引代的 collection 列表（需要快照并逐项对账）。"""
    connection = open_sqlite(textbook_db)
    try:
        state_row = connection.execute(
            "SELECT active_generation_id FROM catalog_state WHERE id = 1"
        ).fetchone()
        active_id = state_row["active_generation_id"] if state_row is not None else None
        if not active_id:
            return []
        generation = connection.execute(
            "SELECT id, profile_id, collection_name, state FROM index_generations WHERE id = ?",
            (active_id,),
        ).fetchone()
        if generation is None:
            failures.append(f"活动索引代 {active_id} 在 index_generations 中不存在")
            return []
        if str(generation["state"]) != "ready":
            failures.append(
                f"活动索引代 {active_id} 状态为 {generation['state']}，不是 ready："
                "拒绝把它当作完整索引备份"
            )
            return []
        profile = connection.execute(
            "SELECT dimensions, distance FROM embedding_profiles WHERE id = ?",
            (generation["profile_id"],),
        ).fetchone()
        expected = connection.execute(
            "SELECT COALESCE(SUM(expected_chunk_count), 0) AS total FROM generation_revisions "
            "WHERE generation_id = ? AND state = 'ready'",
            (active_id,),
        ).fetchone()
        return [
            {
                "generationId": str(generation["id"]),
                "collectionName": str(generation["collection_name"]),
                "generationState": str(generation["state"]),
                "dimensions": int(profile["dimensions"]) if profile is not None else None,
                "distance": str(profile["distance"]) if profile is not None else None,
                "expectedPointCount": int(expected["total"]) if expected is not None else None,
            }
        ]
    finally:
        connection.close()
    return []


def _snapshot_collections(
    admin: Any, plan: Sequence[dict], target: Path, failures: list[str]
) -> list[dict]:
    collections: list[dict] = []
    snapshot_dir = target / "qdrant"
    for item in plan:
        name = item["collectionName"]
        try:
            info = admin.collection_info(name)
            if info.get("dimensions") != item["dimensions"]:
                failures.append(
                    f"collection {name} 维度为 {info.get('dimensions')}，"
                    f"目录声明 {item['dimensions']}"
                )
                continue
            declared = (item["distance"] or "").lower()
            actual = str(info.get("distance") or "").lower()
            if declared and actual and declared != actual:
                failures.append(
                    f"collection {name} 距离为 {info.get('distance')}，目录声明 {item['distance']}"
                )
                continue
            point_count = admin.count_points(name, exact=True)
            if item["expectedPointCount"] is not None and point_count != item["expectedPointCount"]:
                failures.append(
                    f"collection {name} 实际点数 {point_count}，"
                    f"目录内就绪分块合计 {item['expectedPointCount']}"
                )
                continue
            point_manifest = admin.point_manifest(name)
            snapshot = admin.create_snapshot(name)
            data = admin.download_snapshot(name, snapshot)
            if not data:
                failures.append(f"collection {name} 的 Qdrant 快照为空")
                continue
            file_name = f"{name}__{snapshot}"
            snapshot_path = snapshot_dir / file_name
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_bytes(data)
            collections.append(
                {
                    "generationId": item["generationId"],
                    "collectionName": name,
                    "dimensions": item["dimensions"],
                    "distance": item["distance"],
                    "pointCount": point_count,
                    "snapshotPath": f"qdrant/{file_name}",
                    "snapshotSha256": hashlib.sha256(data).hexdigest(),
                    "pointManifestSha256": point_manifest,
                }
            )
            admin.delete_snapshot(name, snapshot)
        except AppError as exc:
            failures.append(f"collection {name} 快照失败：{exc.code}: {exc}")
        except Exception as exc:  # noqa: BLE001 - 快照链路任何异常都要留痕，不伪装成功
            failures.append(f"collection {name} 快照失败：{exc.__class__.__name__}: {exc}")
    return collections


# --------------------------------------------------------------------------- 备份


def create_backup(
    *,
    data_dir: Path,
    target: Path,
    label: str = "",
    qdrant_url: str | None = None,
    qdrant_client: Any | None = None,
) -> dict:
    """离线一致性备份；返回清单（``status`` 为 ``complete`` 或 ``failed``）。

    ``BackupRefused`` 表示未写任何文件；其余失败会写出 ``status: "failed"`` 的清单后返回。
    """
    root = Path(data_dir)
    destination = Path(target)
    textbooks_root = root / "textbooks"
    question_root = root / "question-bank"
    assets_root = root / "assets"
    textbook_db = textbooks_root / "catalog.sqlite3"
    question_db = question_root / "question-bank.sqlite3"
    knowledge_db = root / "knowledge" / "knowledge.sqlite3"
    teaching_db = root / "teaching" / "teaching.sqlite3"

    if not root.is_dir():
        raise BackupRefused(f"数据根不存在，拒绝备份：{root}")

    with acquire_data_lock(root, exclusive=True, blocking=False, label="backup"):
        if destination.exists():
            raise BackupRefused(f"备份目录已存在，拒绝覆盖：{destination}")
        present_databases = [
            root / relative for relative, *_rest in CATALOG_SPECS if (root / relative).is_file()
        ]
        if not present_databases:
            raise BackupRefused(
                "数据根没有任何数据库，拒绝生成空备份："
                + " / ".join(str(root / relative) for relative, *_rest in CATALOG_SPECS)
            )
        pending = _unfinished_jobs(
            textbook_db if textbook_db.is_file() else None,
            question_db if question_db.is_file() else None,
        )
        pending.extend(
            _unfinished_extra_jobs(
                knowledge_db if knowledge_db.is_file() else None,
                teaching_db if teaching_db.is_file() else None,
            )
        )
        if pending:
            detail = "\n".join(f"  - {item}" for item in pending)
            raise BackupRefused(
                "存在未结束的入库/整理/重建任务，拒绝离线备份（不修改任何任务状态）：\n" + detail
            )

        destination.mkdir(parents=True, exist_ok=False)
        failures: list[str] = []
        files: list[dict] = []

        for relative_db, archive_path, restore_path, role, label_text in CATALOG_SPECS:
            db_path = root / relative_db
            if not db_path.is_file():
                # 四个库缺任何一个都是失败：绝不悄悄少备份一个库
                failures.append(f"{label_text}缺失：{db_path}")
                continue
            copy_path = destination / archive_path
            try:
                sqlite_snapshot(db_path, copy_path)
                check = sqlite_quick_check(copy_path)
                if check != "ok":
                    failures.append(f"{label_text}副本自检失败：{check}")
                    continue
                size, digest = copy_path.stat().st_size, sha256_file(copy_path)
                files.append(
                    {
                        "logicalRole": role,
                        "archivePath": archive_path,
                        "restorePath": restore_path,
                        "sourcePath": str(db_path.relative_to(root)).replace("\\", "/"),
                        "bytes": size,
                        "sha256": digest,
                    }
                )
            except (BackupFailed, sqlite3.Error, OSError) as exc:
                failures.append(f"{label_text}一致性备份失败：{exc.__class__.__name__}: {exc}")

        needs: list[BlobNeed] = []
        if (destination / TEXTBOOK_CATALOG_ARCHIVE).is_file():
            textbook_needs, textbook_failures = _textbook_blob_needs(
                destination / TEXTBOOK_CATALOG_ARCHIVE
            )
            needs.extend(textbook_needs)
            failures.extend(textbook_failures)
        if (destination / QUESTION_CATALOG_ARCHIVE).is_file():
            question_needs, question_failures = _question_blob_needs(
                destination / QUESTION_CATALOG_ARCHIVE
            )
            needs.extend(question_needs)
            failures.extend(question_failures)

        copies: list[dict] = []
        textbook_copies, textbook_copy_failures = _resolve_needs(
            textbooks_root,
            [need for need in needs if need.kind == "textbook"],
            TEXTBOOK_AREA_ROLES,
        )
        question_copies, question_copy_failures = _resolve_needs(
            question_root,
            [need for need in needs if need.kind == "question"],
            QUESTION_AREA_ROLES,
        )
        copies.extend(textbook_copies)
        copies.extend(question_copies)
        failures.extend(textbook_copy_failures)
        failures.extend(question_copy_failures)

        seen: set[tuple[str, str]] = set()
        for copy in copies:
            prefix = "textbooks" if copy["kind"] == "textbook" else "question-bank"
            key = (prefix, f"{copy['area']}/{copy['blob_id']}")
            if key in seen:
                continue
            seen.add(key)
            archive_path = f"files/{copy['role']}/{copy['blob_id']}"
            restore_path = f"{prefix}/{copy['area']}/{copy['blob_id']}"
            source = copy["source"]
            archive_file = destination / archive_path
            try:
                size, digest = copy_hashed(source, archive_file)
            except OSError as exc:
                failures.append(
                    f"{copy['role']} {copy['blob_id']} 复制失败：{exc.__class__.__name__}: {exc}"
                )
                continue
            # 内容寻址：文件名必须等于内容 sha256，任何一个字节不同都拒绝收录
            if digest != copy["blob_id"]:
                failures.append(
                    f"{copy['role']} {copy['blob_id']} 内容指纹不符（实际 {digest}），"
                    "源文件缺失或损坏"
                )
                archive_file.unlink(missing_ok=True)
                continue
            files.append(
                {
                    "logicalRole": copy["role"],
                    "archivePath": archive_path,
                    "restorePath": restore_path,
                    "sourcePath": f"{prefix}/{copy['area']}/{copy['blob_id']}",
                    "bytes": size,
                    "sha256": digest,
                }
            )

        # 教学库引用的受管资产：从**备份后的**教学库快照读 file_assets，逐文件校验
        failures.extend(
            _collect_teaching_assets(
                teaching_snapshot=destination / TEACHING_CATALOG_ARCHIVE,
                assets_root=assets_root,
                destination=destination,
                files=files,
            )
        )

        effective_qdrant = qdrant_url or Settings.from_env().qdrant_url
        admin = qdrant_client
        if admin is None:
            admin = QdrantAdmin(effective_qdrant)
        plan: list[dict] = []
        if (destination / TEXTBOOK_CATALOG_ARCHIVE).is_file():
            try:
                plan = _collection_plan(destination / TEXTBOOK_CATALOG_ARCHIVE, failures)
            except sqlite3.Error as exc:
                failures.append(f"读取活动索引代失败：{exc.__class__.__name__}: {exc}")
        collections = _snapshot_collections(admin, plan, destination, failures)

        active_generation_id = None
        if (destination / TEXTBOOK_CATALOG_ARCHIVE).is_file():
            connection = open_sqlite(destination / TEXTBOOK_CATALOG_ARCHIVE)
            try:
                row = connection.execute(
                    "SELECT active_generation_id FROM catalog_state WHERE id = 1"
                ).fetchone()
                active_generation_id = row["active_generation_id"] if row is not None else None
            finally:
                connection.close()

        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "status": "failed" if failures else "complete",
            "createdAt": now_iso(),
            "label": label,
            "dataDir": str(root),
            "activeGenerationId": active_generation_id,
            "qdrantUrl": effective_qdrant,
            "files": files,
            "collections": collections,
            "failures": failures,
            "note": (
                "只有 status=complete 才是可恢复的完整备份；"
                "凭证（apps/api/.env）与锁文件不在清单内；"
                "恢复只写新目录且必须指向隔离 Qdrant。"
            ),
        }
        write_json_atomic(destination / MANIFEST_NAME, manifest)
        return manifest


# --------------------------------------------------------------------------- 清单规范化


def _relative_inside(root: Path, relative: str, *, what: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise BackupRefused(f"{what} 为空。")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise BackupRefused(f"{what} 必须是数据根内的相对路径，收到：{relative}")
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise BackupRefused(f"{what} 越出数据根：{relative}")
    return resolved


def _legacy_manifest_files(backup: Path, manifest: dict) -> tuple[list[dict], list[dict], list[str]]:
    """旧清单（无 schemaVersion 或 =1）只读映射到运行目录布局。"""
    files: list[dict] = []
    collections: list[dict] = []
    notes: list[str] = []
    unknown_kinds: dict[str, int] = {}
    sqlite_restore = {
        "sqlite/catalog.sqlite3": (TEXTBOOK_CATALOG_RESTORE, ROLE_TEXTBOOK_CATALOG),
        "sqlite/question-bank.sqlite3": (QUESTION_CATALOG_RESTORE, ROLE_QUESTION_CATALOG),
    }
    tree_restore = {
        "textbooks-blobs": ("textbooks/blobs", ROLE_TEXTBOOK_BLOB),
        "textbooks-normalized": ("textbooks/normalized", ROLE_TEXTBOOK_NORMALIZED),
        "textbooks-staging": ("textbooks/staging", ROLE_TEXTBOOK_STAGING),
        "question-bank-blobs": ("question-bank/blobs", ROLE_QUESTION_BLOB),
    }
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise BackupRefused("旧清单缺少 entries 数组，无法恢复。")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == "sqlite":
            relative = entry.get("path")
            if not isinstance(relative, str):
                if entry.get("skipped"):
                    notes.append(f"旧清单记录数据库缺失：{entry.get('name')}（{entry['skipped']}）")
                continue
            mapped = sqlite_restore.get(relative)
            if mapped is None:
                notes.append(f"旧清单存在未知 sqlite 路径，忽略：{relative}")
                continue
            restore_path, role = mapped
            files.append(
                {
                    "logicalRole": role,
                    "archivePath": relative,
                    "restorePath": restore_path,
                    "bytes": None,
                    "sha256": entry.get("sha256"),
                }
            )
        elif kind == "tree":
            name = entry.get("name")
            mapped = tree_restore.get(str(name))
            if mapped is None:
                notes.append(f"旧清单存在未知文件树，忽略：{name}")
                continue
            prefix, role = mapped
            directory = backup / "files" / str(name)
            if not directory.is_dir():
                notes.append(f"旧清单声明的文件树目录不存在：files/{name}")
                continue
            for item in sorted(directory.rglob("*")):
                if not item.is_file():
                    continue
                if is_temporary_file(item.name):
                    notes.append(f"跳过未完成临时文件：{item.name}")
                    continue
                relative = item.relative_to(directory).as_posix()
                files.append(
                    {
                        "logicalRole": role,
                        "archivePath": f"files/{name}/{relative}",
                        "restorePath": f"{prefix}/{relative}",
                        "bytes": None,
                        "sha256": None,
                    }
                )
        elif kind == "qdrant":
            relative = entry.get("path")
            if not isinstance(relative, str):
                if entry.get("error"):
                    notes.append(f"旧清单记录 Qdrant 快照失败：{entry['error']}")
                continue
            files.append(
                {
                    "logicalRole": "qdrant-snapshot",
                    "archivePath": relative,
                    "restorePath": None,
                    "bytes": None,
                    "sha256": entry.get("sha256"),
                }
            )
            collections.append(
                {
                    "generationId": None,
                    "collectionName": str(entry.get("name") or ""),
                    "dimensions": None,
                    "distance": None,
                    "pointCount": None,
                    "snapshotPath": relative,
                    "snapshotSha256": entry.get("sha256"),
                    "pointManifestSha256": None,
                    "legacy": True,
                }
            )
        else:
            unknown_kinds.setdefault(str(kind), 0)
            unknown_kinds[str(kind)] += 1
            if entry.get("error"):
                notes.append(f"旧清单记录了失败条目（kind={kind}）：{entry['error']}")
    for kind_name, count in sorted(unknown_kinds.items()):
        notes.append(
            f"旧清单含 {count} 个未映射条目（kind={kind_name}）：不在运行目录布局内，"
            "本次只读兼容不校验这些文件。"
        )
    return files, collections, notes


def normalize_manifest(backup: Path) -> dict:
    """读清单并归一成内部结构；v3/v2 保持原字段，旧清单映射到运行目录布局。"""
    manifest_path = Path(backup) / MANIFEST_NAME
    if not manifest_path.is_file():
        raise BackupRefused(f"备份清单不存在：{manifest_path}")
    try:
        raw = read_json(manifest_path)
    except ValueError as exc:
        raise BackupRefused(f"备份清单不是合法 JSON：{exc}") from exc
    if not isinstance(raw, dict):
        raise BackupRefused("备份清单顶层不是 JSON 对象。")

    version = raw.get("schemaVersion")
    if version in (SCHEMA_VERSION_V2, SCHEMA_VERSION):
        return {
            "schemaVersion": version,
            "legacy": False,
            "status": str(raw.get("status") or ""),
            "createdAt": raw.get("createdAt"),
            "activeGenerationId": raw.get("activeGenerationId"),
            "files": [item for item in raw.get("files", []) if isinstance(item, dict)],
            "collections": [
                {**item, "legacy": False}
                for item in raw.get("collections", [])
                if isinstance(item, dict)
            ],
            "failures": [str(item) for item in raw.get("failures", []) if isinstance(item, str)],
            "notes": [],
            "raw": raw,
        }
    if version not in (None, 1):
        raise BackupRefused(f"未知的清单 schemaVersion：{version}")
    files, collections, notes = _legacy_manifest_files(Path(backup), raw)
    return {
        "schemaVersion": 1,
        "legacy": True,
        "status": None,
        "createdAt": raw.get("createdAt"),
        "activeGenerationId": raw.get("activeGenerationId"),
        "files": files,
        "collections": collections,
        "failures": [],
        "notes": notes,
        "raw": raw,
    }


# --------------------------------------------------------------------------- 校验


def _archived_catalog(backup_root: Path, normalized: dict) -> sqlite3.Connection | None:
    """打开归档里的教材目录副本（旧清单的 collection 归属只能这样查）。"""
    entry = next(
        (
            item
            for item in normalized["files"]
            if item.get("restorePath") == TEXTBOOK_CATALOG_RESTORE
        ),
        None,
    )
    if entry is None:
        return None
    path = backup_root / str(entry.get("archivePath"))
    if not path.is_file():
        return None
    return open_sqlite(path)


def _archived_active_generation(
    backup_root: Path, normalized: dict
) -> tuple[str | None, str | None]:
    """返回归档目录里的 ``(活动代 id, 该代的 collection 名)``。"""
    connection = _archived_catalog(backup_root, normalized)
    if connection is None:
        return (None, None)
    try:
        row = connection.execute(
            "SELECT active_generation_id FROM catalog_state WHERE id = 1"
        ).fetchone()
        active = row["active_generation_id"] if row is not None else None
        if not active:
            return (None, None)
        generation = connection.execute(
            "SELECT collection_name FROM index_generations WHERE id = ?", (active,)
        ).fetchone()
        return (str(active), str(generation["collection_name"]) if generation is not None else None)
    finally:
        connection.close()


def verify_backup(
    backup: Path, *, qdrant_client: Any | None = None
) -> tuple[list[str], list[str]]:
    """逐文件核 size + sha256、核 status、核快照与 collection 声明；返回 (失败, 说明)。"""
    root = Path(backup)
    normalized = normalize_manifest(root)
    failures: list[str] = []
    notes: list[str] = []
    notes.extend(normalized["notes"])

    if normalized["legacy"]:
        notes.append(
            "旧清单（schemaVersion<2）只读兼容：只能证明其覆盖的旧资产状态，"
            "不能据此宣称当前数据已有完整灾备。"
        )
        notes.append(
            "legacy_revalidated：以下检查只核对该归档内实际存在的文件与快照。"
        )
    else:
        if normalized["status"] != "complete":
            failures.append(
                f"清单 status={normalized['status'] or '缺失'}，不是 complete：备份未通过一致性校验"
            )
        for item in normalized["failures"]:
            failures.append(f"清单内记录的备份失败：{item}")
        if normalized["schemaVersion"] < SCHEMA_VERSION:
            notes.append(
                "旧 v2 清单只覆盖教材目录与题库：不含知识点库/教学库与受管资产，"
                "不能据此宣称四库完整。"
            )

    active = normalized["activeGenerationId"]
    if not normalized["legacy"]:
        declared_paths = {item.get("restorePath") for item in normalized["files"]}
        required_restores = (
            CATALOG_RESTORE_PATHS
            if normalized["schemaVersion"] >= SCHEMA_VERSION
            else CATALOG_RESTORE_PATHS_V2
        )
        for required in required_restores:
            if required not in declared_paths:
                failures.append(f"完整清单缺少必需文件：{required}")
    snapshot_names = {
        str(item.get("collectionName")) for item in normalized["collections"]
    }
    if normalized["legacy"]:
        archived_active, archived_collection = _archived_active_generation(root, normalized)
        if archived_active:
            if not snapshot_names:
                failures.append(
                    f"旧归档缺少活动索引代 {archived_active} 的必要快照"
                    f"（collection {archived_collection}）"
                )
            elif archived_collection and archived_collection not in snapshot_names:
                failures.append(
                    f"旧归档缺少活动索引代 {archived_active} 的必要快照："
                    f"collection {archived_collection} 不在快照列表 {sorted(snapshot_names)}"
                )
    elif active:
        collection_generations = {
            item.get("generationId")
            for item in normalized["collections"]
            if item.get("generationId")
        }
        if not normalized["collections"]:
            failures.append(f"清单声明活动索引代 {active}，但没有任何 collection 快照")
        elif active not in collection_generations:
            failures.append(f"活动索引代 {active} 没有对应快照，恢复后索引会缺失")

    seen_restore: set[str] = set()
    for item in normalized["files"]:
        archive_path = item.get("archivePath")
        if not isinstance(archive_path, str) or not archive_path:
            failures.append(f"清单条目缺少 archivePath：{item}")
            continue
        try:
            archive_file = _relative_inside(root, archive_path, what="archivePath")
        except BackupRefused as exc:
            failures.append(str(exc))
            continue
        if not archive_file.is_file():
            failures.append(f"缺失文件（含未完成临时文件与失败记录）：{archive_path}")
            continue
        restore_path = item.get("restorePath")
        if isinstance(restore_path, str) and restore_path:
            if restore_path in seen_restore:
                failures.append(f"restorePath 重复：{restore_path}")
            seen_restore.add(restore_path)
            if not restore_path.startswith(RESTORE_PATH_PREFIXES) and item.get(
                "logicalRole"
            ) != "qdrant-snapshot":
                failures.append(f"restorePath 不在运行目录内：{restore_path}")
            if Path(restore_path).name == ".zqky-data.lock":
                failures.append("清单试图收录数据根锁文件，拒绝：.zqky-data.lock")
        actual_size = archive_file.stat().st_size
        declared_bytes = item.get("bytes")
        if isinstance(declared_bytes, int) and declared_bytes != actual_size:
            failures.append(
                f"大小不符：{archive_path}（声明 {declared_bytes}，实际 {actual_size}）"
            )
        actual_hash = sha256_file(archive_file)
        declared_hash = item.get("sha256")
        if isinstance(declared_hash, str) and declared_hash:
            if declared_hash != actual_hash:
                failures.append(f"指纹不符：{archive_path}")
        elif not normalized["legacy"]:
            failures.append(f"清单条目缺少 sha256：{archive_path}")
        role = item.get("logicalRole")
        if role in BLOB_ROLES:
            blob_id = Path(archive_path).name
            if actual_hash != blob_id:
                failures.append(
                    f"内容寻址不符：{archive_path} 文件名不是内容 sha256（实际 {actual_hash}）"
                )

    for item in normalized["collections"]:
        snapshot_path = item.get("snapshotPath")
        name = str(item.get("collectionName") or "")
        if not isinstance(snapshot_path, str) or not snapshot_path:
            failures.append(f"collection {name} 缺少 snapshotPath")
            continue
        try:
            snapshot_file = _relative_inside(root, snapshot_path, what="snapshotPath")
        except BackupRefused as exc:
            failures.append(str(exc))
            continue
        if not snapshot_file.is_file():
            failures.append(f"缺失快照：{snapshot_path}")
            continue
        if name and name not in snapshot_file.name:
            failures.append(
                f"快照文件名与 collection 不一致：{snapshot_path} 不含 {name}"
            )
        actual_hash = sha256_file(snapshot_file)
        declared_hash = item.get("snapshotSha256")
        if isinstance(declared_hash, str) and declared_hash:
            if declared_hash != actual_hash:
                failures.append(f"快照指纹不符：{snapshot_path}")
        elif not normalized["legacy"]:
            failures.append(f"快照缺少 sha256：{snapshot_path}")
        if not normalized["legacy"] and not item.get("pointManifestSha256"):
            failures.append(f"collection {name} 缺少 payload 对账指纹（pointManifestSha256）")

    if qdrant_client is not None:
        for item in normalized["collections"]:
            name = str(item.get("collectionName") or "")
            try:
                actual = qdrant_client.point_manifest(name)
            except Exception as exc:  # noqa: BLE001 - 校验工具如实报告不可达
                failures.append(f"无法读取 collection {name} 的 payload 指纹：{exc}")
                continue
            declared = item.get("pointManifestSha256")
            if isinstance(declared, str) and declared and declared != actual:
                failures.append(f"collection {name} 与快照/清单的 payload 指纹不一致")
    return failures, [note for note in notes if note]


# --------------------------------------------------------------------------- 恢复


def _legacy_precheck(backup: Path, normalized: dict) -> None:
    """旧清单：缺未发布草稿产物或缺活动代必要快照时，在写任何文件前明确失败。

    旧格式（无 ``schemaVersion``）没有 ``status`` 字段，也没有 staging 目录；
    这里只读归档内的目录副本做两件事：确认活动代有快照、确认草稿产物齐备。
    """
    if not normalized["legacy"]:
        return
    snapshot_collections = {
        str(item.get("collectionName")) for item in normalized["collections"]
    }
    active, active_collection = _archived_active_generation(backup, normalized)
    if active:
        if active_collection is None:
            raise BackupRefused(
                f"旧清单的活动索引代 {active} 在归档目录中不存在，无法安全恢复。"
            )
        if active_collection not in snapshot_collections:
            raise BackupRefused(
                "旧清单缺少活动索引代的必要快照"
                f"（collection {active_collection}）："
                "恢复后会得到一个看似完整但索引缺失的目录，已拒绝。"
            )
    connection = _archived_catalog(backup, normalized)
    if connection is None:
        return
    try:
        restore_paths = {item.get("restorePath") for item in normalized["files"]}
        for draft in connection.execute(
            "SELECT id, state, parsed_artifacts_json FROM import_drafts ORDER BY rowid ASC"
        ):
            if str(draft["state"]) in FINAL_IMPORT_STATES:
                continue
            raw = draft["parsed_artifacts_json"]
            artifacts = json.loads(raw) if isinstance(raw, str) and raw else None
            if not isinstance(artifacts, dict):
                continue
            for key, label in (("normalizedBlobId", "规范化正文"), ("sourceMapBlobId", "来源映射")):
                blob_id = artifacts.get(key)
                if not isinstance(blob_id, str) or not blob_id:
                    continue
                if f"textbooks/staging/{blob_id}" not in restore_paths:
                    raise BackupRefused(
                        f"旧清单缺少未发布草稿 {draft['id']} 的 staging 产物（{label} {blob_id}）："
                        "恢复后草稿预览/提交不可用，已拒绝。"
                    )
    finally:
        connection.close()


def _restore_target_check(new_root: Path) -> None:
    if Path(new_root).exists():
        raise BackupRefused(f"恢复目标已存在，拒绝覆盖：{new_root}")


def _verify_required_structure(normalized: dict) -> None:
    """完整清单必须在写文件前含齐必需库（v3 四库；v2 两库，旧语义不变）。"""
    if normalized["legacy"]:
        return
    required_restores = (
        CATALOG_RESTORE_PATHS
        if normalized["schemaVersion"] >= SCHEMA_VERSION
        else CATALOG_RESTORE_PATHS_V2
    )
    restore_paths = {item.get("restorePath") for item in normalized["files"]}
    for required in required_restores:
        if required not in restore_paths:
            raise BackupRefused(f"完整清单缺少必需文件：{required}")


def _verify_paths_stay_inside_roots(backup: Path, normalized: dict, new_root: Path) -> None:
    for item in normalized["files"]:
        archive_path = item.get("archivePath")
        if not isinstance(archive_path, str) or not archive_path:
            raise BackupRefused(f"清单条目缺少 archivePath：{item}")
        _relative_inside(backup, archive_path, what="archivePath")
        restore_path = item.get("restorePath")
        if item.get("logicalRole") == "qdrant-snapshot":
            continue
        if not isinstance(restore_path, str) or not restore_path:
            raise BackupRefused(f"清单条目缺少 restorePath：{archive_path}")
        if not restore_path.startswith(RESTORE_PATH_PREFIXES):
            raise BackupRefused(f"restorePath 不在运行目录内：{restore_path}")
        _relative_inside(new_root, restore_path, what="restorePath")
    for item in normalized["collections"]:
        snapshot_path = item.get("snapshotPath")
        if not isinstance(snapshot_path, str) or not snapshot_path:
            raise BackupRefused(f"collection {item.get('collectionName')} 缺少 snapshotPath")
        _relative_inside(backup, snapshot_path, what="snapshotPath")


def _verify_files_before_restore(backup: Path, normalized: dict) -> None:
    missing: list[str] = []
    for item in normalized["files"]:
        archive_path = item.get("archivePath")
        file_path = backup / str(archive_path)
        if not file_path.is_file():
            missing.append(f"缺失文件：{archive_path}")
            continue
        actual_hash = sha256_file(file_path)
        declared = item.get("sha256")
        if isinstance(declared, str) and declared and declared != actual_hash:
            missing.append(f"指纹不符：{archive_path}")
            continue
        role = item.get("logicalRole")
        if role in BLOB_ROLES and Path(str(archive_path)).name != actual_hash:
            missing.append(f"内容寻址不符：{archive_path}")
    for item in normalized["collections"]:
        snapshot_path = item.get("snapshotPath")
        file_path = backup / str(snapshot_path)
        if not file_path.is_file():
            missing.append(f"缺失快照：{snapshot_path}")
            continue
        declared = item.get("snapshotSha256")
        if isinstance(declared, str) and declared and sha256_file(file_path) != declared:
            missing.append(f"快照指纹不符：{snapshot_path}")
    if missing:
        detail = "\n".join(f"  - {item}" for item in missing)
        raise BackupRefused("恢复前校验失败，未写任何文件：\n" + detail)


def _restore_files_to_runtime_layout(backup: Path, normalized: dict, new_root: Path) -> int:
    restored = 0
    for item in normalized["files"]:
        restore_path = item.get("restorePath")
        if not isinstance(restore_path, str) or not restore_path:
            continue
        source = backup / str(item["archivePath"])
        target = new_root / restore_path
        if target.exists():
            if sha256_file(target) == sha256_file(source):
                continue
            raise BackupFailed(f"恢复目标内已存在不同内容的文件：{restore_path}")
        size, digest = copy_hashed(source, target)
        declared_hash = item.get("sha256")
        if isinstance(declared_hash, str) and declared_hash and digest != declared_hash:
            target.unlink(missing_ok=True)
            raise BackupFailed(f"恢复写入后指纹不符：{restore_path}")
        declared_bytes = item.get("bytes")
        if isinstance(declared_bytes, int) and declared_bytes != size:
            target.unlink(missing_ok=True)
            raise BackupFailed(f"恢复写入后大小不符：{restore_path}")
        restored += 1
    return restored


def _restore_collection_name(collection: dict) -> str:
    base = str(collection.get("collectionName") or "textbooks")
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base)
    return f"{safe}__restored_{uuid.uuid4().hex[:10]}"


def _remap_collection_in_restored_catalog_only(
    catalog_db: Path, collection: dict, new_name: str
) -> str:
    """只在**恢复出来的**目录里把索引代指到新 collection 名；绝不改原始数据。"""
    connection = sqlite3.connect(str(catalog_db), isolation_level=None)
    try:
        generation_id = collection.get("generationId")
        if not isinstance(generation_id, str) or not generation_id:
            row = connection.execute(
                "SELECT id FROM index_generations WHERE collection_name = ?",
                (str(collection.get("collectionName") or ""),),
            ).fetchone()
            if row is None:
                raise BackupFailed(
                    f"快照 collection {collection.get('collectionName')} 在恢复目录中"
                    "找不到对应索引代，无法重映射"
                )
            generation_id = row[0]
        cursor = connection.execute(
            "UPDATE index_generations SET collection_name = ? WHERE id = ?",
            (new_name, generation_id),
        )
        if cursor.rowcount != 1:
            raise BackupFailed(f"恢复目录内找不到索引代 {generation_id}，无法重映射 collection")
        return str(generation_id)
    finally:
        connection.close()


def _verify_collection_against_manifest(admin: Any, name: str, collection: dict) -> None:
    if not admin.collection_exists(name):
        raise BackupFailed(f"恢复后 collection {name} 不存在")
    info = admin.collection_info(name)
    declared_dims = collection.get("dimensions")
    if isinstance(declared_dims, int) and info.get("dimensions") != declared_dims:
        raise BackupFailed(
            f"恢复后的 collection {name} 维度为 {info.get('dimensions')}，清单声明 {declared_dims}"
        )
    declared_distance = collection.get("distance")
    if isinstance(declared_distance, str) and declared_distance:
        actual = str(info.get("distance") or "")
        if actual.lower() != declared_distance.lower():
            raise BackupFailed(
                f"恢复后的 collection {name} 距离为 {actual}，清单声明 {declared_distance}"
            )
    declared_points = collection.get("pointCount")
    count = admin.count_points(name, exact=True)
    if isinstance(declared_points, int) and count != declared_points:
        raise BackupFailed(
            f"恢复后的 collection {name} 点数为 {count}，清单声明 {declared_points}"
        )
    declared_manifest = collection.get("pointManifestSha256")
    if isinstance(declared_manifest, str) and declared_manifest:
        actual_manifest = admin.point_manifest(name)
        if actual_manifest != declared_manifest:
            raise BackupFailed(
                f"恢复后的 collection {name} payload 指纹与清单不一致"
                "（点数相同但内容不同）"
            )
    elif not collection.get("legacy"):
        raise BackupFailed(f"清单缺少 collection {name} 的 payload 对账指纹")


def _sqlite_rows(path: Path, sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
    connection = open_sqlite(path)
    try:
        return list(connection.execute(sql, params).fetchall())
    finally:
        connection.close()


def _verify_sqlite_integrity_and_foreign_keys(
    new_root: Path, restore_paths: Sequence[str]
) -> None:
    """对本次恢复到目录里的每个库做 integrity_check + foreign_key_check。"""
    for relative in restore_paths:
        db_path = new_root / relative
        if not db_path.is_file():
            raise BackupFailed(f"恢复目录缺少数据库：{db_path}")
        connection = open_sqlite(db_path)
        try:
            row = connection.execute("PRAGMA integrity_check").fetchone()
            if row is None or str(row[0]).lower() != "ok":
                raise BackupFailed(f"恢复后的数据库完整性检查失败：{db_path}（{row[0] if row else '无返回'}）")
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise BackupFailed(
                    f"恢复后的数据库外键校验失败：{db_path}（{len(violations)} 处）"
                )
        finally:
            connection.close()


def _verify_teaching_assets(new_root: Path) -> None:
    """从**恢复后的**教学库重新推导 ``file_assets`` 引用并逐文件重算 sha256。

    恢复目录没有教学库（v2/legacy 清单）时跳过；只要教学库存在，每条引用都必须能
    在 ``assets/blobs/<sha256>`` 找到且内容、大小与登记一致，否则恢复失败。
    """
    db_path = new_root / TEACHING_CATALOG_RESTORE
    if not db_path.is_file():
        return
    rows, failures = _file_assets_rows(db_path)
    if failures:
        raise BackupFailed("；".join(failures))
    missing: list[str] = []
    seen: set[str] = set()
    for row in rows:
        blob_key = row["blobKey"]
        if blob_key in seen:
            continue
        seen.add(blob_key)
        target = new_root / "assets" / blob_key
        if not target.is_file():
            missing.append(
                f"受管资产缺失：assets/{blob_key}（file_assets {row['assetId']}）"
            )
            continue
        if target.stat().st_size != row["byteSize"]:
            missing.append(f"受管资产大小不符：assets/{blob_key}")
            continue
        if sha256_file(target) != row["sha256"]:
            missing.append(f"受管资产内容指纹不符：assets/{blob_key}")
    if missing:
        detail = "\n".join(f"  - {item}" for item in missing[:20])
        raise BackupFailed("恢复后受管资产校验失败：\n" + detail)


def _verify_all_referenced_blobs(new_root: Path) -> None:
    """教材与题库的每个被引用文件都必须存在且内容与 blob id 一致。

    每条引用可落在多个区域（同一内容寻址文件的封存副本与 staging 副本），
    但至少有一个可用副本；草稿预览必需的 staging 副本单独要求。
    """
    roots = {
        "textbook": (new_root / "textbooks", TEXTBOOK_AREA_ROLES),
        "question": (new_root / "question-bank", QUESTION_AREA_ROLES),
    }
    needs, failures = _textbook_blob_needs(new_root / TEXTBOOK_CATALOG_RESTORE)
    if failures:
        raise BackupFailed("；".join(failures))
    question_needs, question_failures = _question_blob_needs(
        new_root / QUESTION_CATALOG_RESTORE
    )
    if question_failures:
        raise BackupFailed("；".join(question_failures))
    needs.extend(question_needs)

    missing: list[str] = []
    for need in needs:
        root, _roles = roots[need.kind]
        found: list[str] = []
        for area in need.candidates:
            target = root / area / need.blob_id
            if not target.is_file():
                continue
            if sha256_file(target) != need.blob_id:
                missing.append(
                    f"{need.reason}：{need.kind}/{area}/{need.blob_id} 内容指纹不符"
                )
                continue
            found.append(area)
        if not found:
            missing.append(
                f"{need.reason}：缺少 {need.blob_id}"
                f"（已查 {need.kind} 区域 {', '.join(need.candidates)}）"
            )
            continue
        if need.require_staging and "staging" not in found:
            missing.append(
                f"{need.reason}：草稿预览需要 staging/{need.blob_id}，恢复目录中缺失"
            )
    if missing:
        detail = "\n".join(f"  - {item}" for item in missing[:20])
        raise BackupFailed("恢复后被引用文件校验失败：\n" + detail)


def _verify_draft_previews(new_root: Path) -> None:
    """未发布草稿的预览/提交产物必须在 staging（或已封存区）齐备且可解析。"""
    textbooks_root = new_root / "textbooks"
    catalog_db = new_root / TEXTBOOK_CATALOG_RESTORE
    problems: list[str] = []
    for row in _sqlite_rows(
        catalog_db,
        "SELECT id, state, uploaded_blob_id, parsed_artifacts_json FROM import_drafts "
        "ORDER BY rowid ASC",
    ):
        state = str(row["state"])
        raw = row["parsed_artifacts_json"]
        artifacts = json.loads(raw) if isinstance(raw, str) and raw else None
        if state in FINAL_IMPORT_STATES:
            continue
        if artifacts is None:
            continue
        for key, label in (("normalizedBlobId", "规范化正文"), ("sourceMapBlobId", "来源映射")):
            blob_id = artifacts.get(key)
            if not isinstance(blob_id, str) or not blob_id:
                problems.append(f"草稿 {row['id']} 的{label}产物缺少 blob id")
                continue
            found = [
                area
                for area in ("staging", "normalized", "blobs")
                if (textbooks_root / area / blob_id).is_file()
            ]
            if not found:
                problems.append(f"草稿 {row['id']} 的{label}产物缺失（{blob_id}）")
                continue
            if "staging" in found:
                if key != "normalizedBlobId":
                    continue
                try:
                    text = (textbooks_root / "staging" / blob_id).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    problems.append(
                        f"草稿 {row['id']} 的规范化正文物不可读：{exc.__class__.__name__}"
                    )
                    continue
                declared = artifacts.get("charCount")
                if isinstance(declared, int) and declared != len(text):
                    problems.append(
                        f"草稿 {row['id']} 的字符数不符（清单 {declared}，实际 {len(text)}）"
                    )
            elif key == "normalizedBlobId":
                problems.append(
                    f"草稿 {row['id']} 预览需要的 staging/{blob_id} 缺失（只在 {found[0]} 中找到）"
                )
    if problems:
        detail = "\n".join(f"  - {item}" for item in problems[:20])
        raise BackupFailed("恢复后草稿产物校验失败：\n" + detail)


def _verify_revision_and_point_manifests(new_root: Path) -> None:
    """分块清单、规范化切片指纹与代内清单必须自洽。"""
    catalog_db = new_root / TEXTBOOK_CATALOG_RESTORE
    textbooks_root = new_root / "textbooks"
    problems: list[str] = []

    revision_blobs: dict[str, str] = {}
    for row in _sqlite_rows(
        catalog_db, "SELECT id, normalized_blob_id FROM document_revisions ORDER BY rowid ASC"
    ):
        revision_blobs[str(row["id"])] = str(row["normalized_blob_id"])

    chunk_set_manifests: dict[str, str] = {}
    for row in _sqlite_rows(
        catalog_db,
        "SELECT id, document_revision_id, manifest_sha256, chunk_count FROM chunk_sets "
        "ORDER BY rowid ASC",
    ):
        chunk_set_id = str(row["id"])
        chunks = _sqlite_rows(
            catalog_db,
            "SELECT ordinal, char_start, char_end, region, chapter_path_json, text_sha256 "
            "FROM chunks WHERE chunk_set_id = ? ORDER BY ordinal ASC",
            (chunk_set_id,),
        )
        inputs: list[ChunkInput] = []
        for chunk in chunks:
            path = json.loads(str(chunk["chapter_path_json"]))
            inputs.append(
                ChunkInput(
                    ordinal=int(chunk["ordinal"]),
                    char_start=int(chunk["char_start"]),
                    char_end=int(chunk["char_end"]),
                    region=str(chunk["region"]),
                    chapter_path=tuple(str(item) for item in path),
                    text_sha256=str(chunk["text_sha256"]),
                )
            )
        declared_manifest = str(row["manifest_sha256"])
        recomputed = chunk_manifest_sha256(inputs)
        if recomputed != declared_manifest:
            problems.append(f"分块集 {chunk_set_id} 清单指纹不符")
        if int(row["chunk_count"]) != len(inputs):
            problems.append(f"分块集 {chunk_set_id} 块数与 chunks 行数不符")
        chunk_set_manifests[chunk_set_id] = declared_manifest

        revision_id = str(row["document_revision_id"])
        blob_id = revision_blobs.get(revision_id)
        if blob_id is None:
            problems.append(f"分块集 {chunk_set_id} 的修订 {revision_id} 不存在")
            continue
        normalized_path = textbooks_root / "normalized" / blob_id
        if not normalized_path.is_file():
            problems.append(f"修订 {revision_id} 的规范化正文缺失（{blob_id}）")
            continue
        if sha256_file(normalized_path) != blob_id:
            problems.append(f"修订 {revision_id} 的规范化正文指纹不符")
            continue
        text = normalized_path.read_text(encoding="utf-8")
        for chunk in chunks:
            slice_hash = sha256_hex(text[int(chunk["char_start"]): int(chunk["char_end"])])
            if slice_hash != str(chunk["text_sha256"]):
                problems.append(
                    f"分块集 {chunk_set_id} 第 {chunk['ordinal']} 块的正文切片指纹不符"
                )
                break

    for row in _sqlite_rows(
        catalog_db,
        "SELECT generation_id, document_revision_id, chunk_set_id, manifest_sha256 "
        "FROM generation_revisions ORDER BY generation_id ASC, document_revision_id ASC",
    ):
        chunk_set_id = str(row["chunk_set_id"])
        declared = str(row["manifest_sha256"])
        expected = chunk_set_manifests.get(chunk_set_id)
        if expected is None:
            problems.append(f"代内清单引用了不存在的分块集 {chunk_set_id}")
        elif declared != expected:
            problems.append(
                f"代内清单指纹与分块集不一致（generation {row['generation_id']}, "
                f"revision {row['document_revision_id']}）"
            )

    if problems:
        detail = "\n".join(f"  - {item}" for item in problems[:20])
        raise BackupFailed("恢复后修订/分块清单校验失败：\n" + detail)


def _expected_point_count(new_root: Path, generation_id: str | None) -> int | None:
    if not generation_id:
        return None
    rows = _sqlite_rows(
        new_root / TEXTBOOK_CATALOG_RESTORE,
        "SELECT COALESCE(SUM(expected_chunk_count), 0) AS total FROM generation_revisions "
        "WHERE generation_id = ? AND state = 'ready'",
        (generation_id,),
    )
    total = rows[0]["total"] if rows else None
    return int(total) if total is not None else None


def restore_backup(
    backup: Path,
    new_root: Path,
    isolated_qdrant: Any | None = None,
) -> dict:
    """把备份恢复成**应用可直接读取**的数据目录；返回 restore-state 内容。

    ``isolated_qdrant`` 在生产路径上必须是隔离实例的 URL 字符串（本机回环、非 6333）；
    测试可注入实现了同一运维接口的替身。Qdrant 不可达时明确失败并把
    ``restore-state`` 留在 ``incomplete``，绝不留下"看起来完整但索引缺失"的目录。
    """
    source = Path(backup)
    target = Path(new_root)
    normalized = normalize_manifest(source)
    if not normalized["legacy"] and normalized["status"] != "complete":
        raise BackupRefused(
            f"清单 status={normalized['status'] or '缺失'}，只有 complete 才能恢复；"
            "失败记录的备份不可用于恢复。"
        )
    if isinstance(isolated_qdrant, str) or isolated_qdrant is None:
        admin: Any = QdrantAdmin(ensure_isolated_qdrant_url(isolated_qdrant))
    else:
        admin = isolated_qdrant
    _restore_target_check(target)
    _verify_required_structure(normalized)
    _verify_paths_stay_inside_roots(source, normalized, target)
    _verify_files_before_restore(source, normalized)
    _legacy_precheck(source, normalized)

    legacy_note = (
        "本目录由旧清单（schemaVersion<2）兼容恢复，标记 legacy_revalidated："
        "只证明该归档覆盖的资产可用，不代表历史备份完整性通过。"
        if normalized["legacy"]
        else ""
    )
    write_restore_state(
        target,
        status=RESTORE_STATUS_INCOMPLETE,
        restoredFrom=str(source),
        manifestSchemaVersion=normalized["schemaVersion"],
        legacyRevalidated=bool(normalized["legacy"]),
        activeGenerationId=normalized["activeGenerationId"],
        qdrantUrl=getattr(admin, "base_url", None) or str(isolated_qdrant),
        restoredCollections=[],
        failures=[],
        note=legacy_note
        or "恢复尚未完成；应用启动检查必须拒绝 status=incomplete 的数据根。",
    )

    try:
        file_count = _restore_files_to_runtime_layout(source, normalized, target)
        restored_collections: list[dict] = []
        for item in normalized["collections"]:
            new_name = _restore_collection_name(item)
            attempts = 0
            while admin.collection_exists(new_name):
                attempts += 1
                if attempts > 5:
                    raise BackupFailed(
                        f"隔离 Qdrant 上无法找到空闲的恢复 collection 名（{new_name}）"
                    )
                new_name = _restore_collection_name(item)
            snapshot_file = source / str(item["snapshotPath"])
            admin.restore_snapshot(
                collection=new_name, snapshot_path=snapshot_file, priority="snapshot", wait=True
            )
            _verify_collection_against_manifest(admin, new_name, item)
            generation_id = _remap_collection_in_restored_catalog_only(
                target / TEXTBOOK_CATALOG_RESTORE, item, new_name
            )
            expected_points = _expected_point_count(target, generation_id)
            actual_points = admin.count_points(new_name, exact=True)
            if expected_points is not None and actual_points != expected_points:
                raise BackupFailed(
                    f"恢复后的 collection {new_name} 点数 {actual_points} 与恢复目录内"
                    f"就绪分块合计 {expected_points} 不一致"
                )
            restored_collections.append(
                {
                    "generationId": generation_id,
                    "sourceCollectionName": item.get("collectionName"),
                    "restoredCollectionName": new_name,
                    "pointCount": actual_points,
                }
            )

        # 恢复目录里声明了哪些库就逐个做 integrity_check + foreign_key_check
        declared_restores = {item.get("restorePath") for item in normalized["files"]}
        db_restores = [path for path in CATALOG_RESTORE_PATHS if path in declared_restores]
        _verify_sqlite_integrity_and_foreign_keys(target, db_restores)
        _verify_all_referenced_blobs(target)
        _verify_teaching_assets(target)
        _verify_draft_previews(target)
        _verify_revision_and_point_manifests(target)

        state_row = _sqlite_rows(
            target / TEXTBOOK_CATALOG_RESTORE,
            "SELECT active_generation_id FROM catalog_state WHERE id = 1",
        )
        active = state_row[0]["active_generation_id"] if state_row else None
        if active and not any(item["generationId"] == active for item in restored_collections):
            raise BackupFailed(
                f"恢复目录的活动索引代 {active} 没有对应的已恢复 collection"
            )
    except BaseException as exc:  # noqa: BLE001 - 失败必须留在 incomplete，含取消
        reason = f"{exc.__class__.__name__}: {exc}" if not isinstance(exc, AppError) else f"{exc.code}: {exc}"
        write_restore_state(
            target,
            status=RESTORE_STATUS_INCOMPLETE,
            failures=[reason],
            note="恢复失败：数据根保持 incomplete，应用启动必须拒绝。",
        )
        raise

    return write_restore_state(
        target,
        status=RESTORE_STATUS_READY,
        filesRestored=file_count,
        restoredCollections=restored_collections,
        failures=[],
        note=(
            "恢复完成。请把应用的数据根指向本目录，并把 Qdrant 指向本次使用的隔离实例"
            "（collection 已重命名为 __restored_*）。"
        ),
    )


# --------------------------------------------------------------------------- CLI


def _settings_with_data_dir(data_dir: str | None) -> Settings:
    settings = Settings.from_env()
    if data_dir:
        settings = replace(settings, data_dir=Path(data_dir))
    return settings


def _refusal_exit(error: AppError) -> int:
    """数据根被占用等"拒绝且未写文件"的错误统一走退出码 2。"""
    print(f"操作被拒绝（未写任何文件）：{error.code}: {error}", file=sys.stderr)
    return 2


def create_command(args: argparse.Namespace) -> int:
    settings = _settings_with_data_dir(args.data_dir)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    label = f"-{args.label}" if args.label else ""
    target = Path(args.into) if args.into else BACKUP_ROOT / f"rag-{stamp}{label}"
    try:
        manifest = create_backup(
            data_dir=settings.data_dir,
            target=target,
            label=args.label or "",
            qdrant_url=args.qdrant_url or settings.qdrant_url,
        )
    except BackupRefused as exc:
        print(f"备份被拒绝（未写任何文件）：{exc}", file=sys.stderr)
        return 2
    except AppError as exc:
        # 数据根被其他进程占用：DATA_LOCK_BUSY（可重试），不自动停止用户进程
        return _refusal_exit(exc)
    if manifest["status"] != "complete":
        print(f"备份失败，已保留失败记录：{target / MANIFEST_NAME}", file=sys.stderr)
        for failure in manifest["failures"]:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"备份完成：{target}")
    print(f"  文件 {len(manifest['files'])} 个；collection {len(manifest['collections'])} 个")
    print(f"  活动索引代：{manifest['activeGenerationId']}")
    return 0


def verify_command(args: argparse.Namespace) -> int:
    root = Path(args.path)
    try:
        failures, notes = verify_backup(root)
    except BackupRefused as exc:
        print(f"校验被拒绝：{exc}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"  说明：{note}")
    if failures:
        print(f"校验失败（{len(failures)} 项）：", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1
    normalized = normalize_manifest(root)
    kind = "旧清单（legacy_revalidated，只读兼容）" if normalized["legacy"] else "清单"
    print(
        f"{kind}校验通过：文件 {len(normalized['files'])} 个；"
        f"collection {len(normalized['collections'])} 个"
    )
    return 0


def restore_command(args: argparse.Namespace) -> int:
    try:
        state = restore_backup(
            Path(args.path), Path(args.into), isolated_qdrant=args.isolated_qdrant
        )
    except BackupRefused as exc:
        print(f"恢复被拒绝（未写任何文件）：{exc}", file=sys.stderr)
        return 2
    except BackupFailed as exc:
        print(f"恢复失败（数据根留在 incomplete）：{exc}", file=sys.stderr)
        return 1
    except AppError as exc:
        if exc.code in {"DATA_LOCK_BUSY", "DATA_LOCK_UNAVAILABLE"}:
            return _refusal_exit(exc)
        print(f"恢复失败（数据根留在 incomplete）：{exc.code}: {exc}", file=sys.stderr)
        return 1
    print(f"已恢复到新目录：{args.into}")
    print(f"  活动索引代：{state.get('activeGenerationId')}")
    for item in state.get("restoredCollections", []):
        print(
            f"  collection {item.get('sourceCollectionName')} → "
            f"{item.get('restoredCollectionName')}（{item.get('pointCount')} 点）"
        )
    print("  应用启动前请确认 restore-state.json 为 ready；incomplete 必须拒绝启动。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="四库（教材/题库/知识点/教学）+ 受管资产的离线一致性备份、校验与恢复（schemaVersion 3）"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建离线一致性备份（需要数据根排他锁）")
    create.add_argument("--label", help="备份标签（写入目录名与清单）")
    create.add_argument("--into", help="指定备份目录（默认 _work/rag-backups/…）")
    create.add_argument("--data-dir", help="数据根目录（默认取 Settings/ZQKY_DATA_DIR）")
    create.add_argument("--qdrant-url", help="Qdrant 地址（默认取 Settings）")
    create.set_defaults(func=create_command)

    verify = sub.add_parser("verify", help="校验备份指纹、快照与状态")
    verify.add_argument("--path", required=True)
    verify.set_defaults(func=verify_command)

    restore = sub.add_parser("restore", help="恢复到新目录（必须指向隔离 Qdrant）")
    restore.add_argument("--path", required=True)
    restore.add_argument("--into", required=True)
    restore.add_argument(
        "--isolated-qdrant",
        help="隔离 Qdrant 地址（本机回环、非 6333；缺失或 6333 一律拒绝）",
    )
    restore.set_defaults(func=restore_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
