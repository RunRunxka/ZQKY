"""受管资产本体：内容寻址、写入幂等、原子落盘，读取时重算 sha256。

布局：``<assets_root>/blobs/<sha256>``（任务卡 §3.7）。与题库 blob 同一套纪律，
但受管资产的键形状被显式冻结并可被路径穿越输入：

- ``blob_key`` 只接受 ``blobs/<64 位小写 hex>``；``..``、绝对路径、盘符、反斜杠、
  大小写异常、长度不符一律 ``INVALID_ASSET_KEY``（422），且**不创建任何目录**；
- ``media_type`` 与 ``original_name`` 只在数据库登记中使用，**不参与路径拼接**；
- 写入先落临时文件、``fsync`` 后 ``os.replace`` 原子替换；失败清理临时文件；
- 读取/校验重新计算 sha256，与文件名不符一律 ``ASSET_CORRUPT``（500），绝不返回
  可疑内容；文件缺失报 ``ASSET_MISSING``（500）。
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import AppError

AREA_BLOBS = "blobs"
#: 受管键形状：仅 ``blobs/<64 位小写 hex>`` 一个目录层级
BLOB_KEY_PATTERN = re.compile(r"blobs/[0-9a-f]{64}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _invalid_key(detail: str) -> AppError:
    return AppError(
        f"受管资产键非法：{detail}", code="INVALID_ASSET_KEY", status_code=422
    )


def _missing(detail: str) -> AppError:
    return AppError(f"受管资产文件缺失：{detail}", code="ASSET_MISSING", status_code=500)


def _corrupt(detail: str) -> AppError:
    return AppError(
        f"受管资产内容指纹不符：{detail}", code="ASSET_CORRUPT", status_code=500
    )


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"{field} 必须是非空字符串。", code="INVALID_REQUEST", status_code=422
        )
    return value


def _digest_of(blob_key: str) -> str:
    """从合法 ``blob_key`` 取出散列部分（调用前必须已通过 ``path_of`` 校验）。"""
    return blob_key.split("/", 1)[1]


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


@dataclass(frozen=True)
class StoredAsset:
    """一次成功写入（或幂等命中）的结果。"""

    blob_key: str
    sha256: str
    byte_size: int


class AssetStore:
    """受管资产本体的唯一读写入口；调用方给出 ``assets_root``。"""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @property
    def blobs_dir(self) -> Path:
        return self.root / AREA_BLOBS

    def path_of(self, blob_key: str) -> Path:
        """把受管键映射为路径；非法键抛 ``INVALID_ASSET_KEY``，不创建目录。"""
        if (
            not isinstance(blob_key, str)
            or BLOB_KEY_PATTERN.fullmatch(blob_key) is None
        ):
            raise _invalid_key(f"只接受 blobs/<64 位小写 hex>，收到：{blob_key!r}")
        return self.blobs_dir / _digest_of(blob_key)

    def store_original(
        self, content: bytes, *, media_type: str, original_name: str
    ) -> StoredAsset:
        """写入原件并返回 ``StoredAsset``；同内容重复写入幂等（同键同内容）。

        ``media_type`` / ``original_name`` 仅做非空校验，绝不参与路径拼接。
        """
        if not isinstance(content, (bytes, bytearray)):
            raise AppError(
                "上传内容必须是字节串。", code="INVALID_REQUEST", status_code=422
            )
        _require_text(media_type, field="media_type")
        _require_text(original_name, field="original_name")
        payload = bytes(content)
        digest = sha256_bytes(payload)
        blob_key = f"{AREA_BLOBS}/{digest}"
        target = self.path_of(blob_key)
        if target.is_file() and target.stat().st_size == len(payload):
            existing_hash, _size = _hash_file(target)
            if existing_hash == digest:
                return StoredAsset(blob_key=blob_key, sha256=digest, byte_size=len(payload))
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.tmp-{uuid.uuid4().hex}")
        try:
            with open(temporary, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        return StoredAsset(blob_key=blob_key, sha256=digest, byte_size=len(payload))

    def read(self, blob_key: str) -> bytes:
        target = self.path_of(blob_key)
        if not target.is_file():
            raise _missing(blob_key)
        data = target.read_bytes()
        if sha256_bytes(data) != _digest_of(blob_key):
            raise _corrupt(blob_key)
        return data

    def verify(self, blob_key: str) -> int:
        """重算 sha256 并返回字节数；缺失/指纹不符按上述错误码抛出。"""
        target = self.path_of(blob_key)
        if not target.is_file():
            raise _missing(blob_key)
        digest, size = _hash_file(target)
        if digest != _digest_of(blob_key):
            raise _corrupt(blob_key)
        return size

    def exists(self, blob_key: str) -> bool:
        """受管键是否已有文件；非法键仍抛 ``INVALID_ASSET_KEY``（不静默返回 False）。"""
        return self.path_of(blob_key).is_file()


def is_managed_blob_key(value: object) -> bool:
    """``value`` 是否为合法受管键（供备份/恢复等只读工具复用，不访问文件系统）。"""
    return isinstance(value, str) and BLOB_KEY_PATTERN.fullmatch(value) is not None


def is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and _SHA256_PATTERN.fullmatch(value) is not None
