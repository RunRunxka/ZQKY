"""题库原件 blob：内容寻址、原子落盘、只增不改。

目录：``<question_bank_root>/blobs/<sha256>``（与任务卡规格一致）。
读取时重新计算 sha256，与文件名不符一律抛错，绝不返回可疑内容。
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from app.core.exceptions import AppError

AREA_BLOBS = "blobs"
_CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _missing(detail: str) -> AppError:
    return AppError(f"题库原件缺失：{detail}", code="QUESTION_BLOB_MISSING", status_code=500)


def _corrupt(detail: str) -> AppError:
    return AppError(f"题库原件损坏：{detail}", code="QUESTION_BLOB_CORRUPT", status_code=500)


class QuestionBlobStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    @property
    def blobs_dir(self) -> Path:
        return self.root / AREA_BLOBS

    def path_of(self, blob_id: str) -> Path:
        if not isinstance(blob_id, str) or not blob_id:
            raise _missing("blob id 为空")
        return self.blobs_dir / blob_id

    def write(self, data: bytes) -> tuple[str, int]:
        """写入原件并返回 ``(sha256, 字节数)``；同内容重复写入是幂等的。"""
        if not isinstance(data, (bytes, bytearray)):
            raise AppError("上传内容必须是字节串。", code="INVALID_REQUEST", status_code=422)
        payload = bytes(data)
        blob_id = sha256_bytes(payload)
        target = self.path_of(blob_id)
        if target.is_file() and target.stat().st_size == len(payload):
            return blob_id, len(payload)
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
        return blob_id, len(payload)

    def read(self, blob_id: str) -> bytes:
        target = self.path_of(blob_id)
        if not target.is_file():
            raise _missing(f"{AREA_BLOBS}/{blob_id} 不存在")
        data = target.read_bytes()
        if sha256_bytes(data) != blob_id:
            raise _corrupt(f"{AREA_BLOBS}/{blob_id} 内容指纹不符")
        return data

    def size_of(self, blob_id: str) -> int:
        target = self.path_of(blob_id)
        if not target.is_file():
            raise _missing(f"{AREA_BLOBS}/{blob_id} 不存在")
        return target.stat().st_size
