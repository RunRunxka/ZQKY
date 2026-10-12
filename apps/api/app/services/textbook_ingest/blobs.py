"""教材托管文件的 blob 存储：内容寻址、原子落盘、封存后不可变。

目录约定（``settings.textbooks_root`` 之下，与计划 §2.2 一致）：

```text
staging/     上传中与未发布产物（草稿的规范化文本、来源映射）
blobs/       封存的教材原件（按内容 sha256 命名）
normalized/  封存的规范化文本与来源映射（按内容 sha256 命名）
```

所有写入先写 ``*.tmp-*`` 再 ``os.replace`` 原子替换；读取时重新计算 sha256，
与文件名不符一律抛错，绝不静默返回可疑内容。
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from app.core.exceptions import AppError

AREA_STAGING = "staging"
AREA_BLOBS = "blobs"
AREA_NORMALIZED = "normalized"
AREAS = (AREA_STAGING, AREA_BLOBS, AREA_NORMALIZED)

_CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact_missing(detail: str) -> AppError:
    return AppError(
        f"导入产物缺失或损坏：{detail}",
        code="IMPORT_ARTIFACT_MISSING",
        status_code=500,
    )


def _artifact_corrupt(detail: str) -> AppError:
    return AppError(
        f"导入产物损坏：{detail}",
        code="IMPORT_ARTIFACT_CORRUPT",
        status_code=500,
    )


class BlobStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------- 路径与目录

    def area_dir(self, area: str) -> Path:
        if area not in AREAS:
            raise ValueError(f"未知的 blob 区域：{area}")
        return self.root / area

    def ensure_dirs(self) -> None:
        for area in AREAS:
            self.area_dir(area).mkdir(parents=True, exist_ok=True)

    def path_of(self, area: str, blob_id: str) -> Path:
        return self.area_dir(area) / blob_id

    def exists(self, area: str, blob_id: str) -> bool:
        return self.path_of(area, blob_id).is_file()

    # ------------------------------------------------------------- 写入

    def stage_temp_path(self) -> Path:
        directory = self.area_dir(AREA_STAGING)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"tmp-{uuid.uuid4().hex}.part"

    def write_staged_bytes(self, data: bytes) -> str:
        """写入 staging 并返回内容 sha256（同内容重复写入是幂等的）。"""
        blob_id = sha256_bytes(data)
        target = self.path_of(AREA_STAGING, blob_id)
        if target.is_file() and target.stat().st_size == len(data):
            return blob_id
        self._atomic_write(target, data)
        return blob_id

    def write_staged_text(self, text: str) -> str:
        return self.write_staged_bytes(text.encode("utf-8"))

    def write_staged_json(self, payload: object) -> str:
        return self.write_staged_bytes(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )

    def stage_file(self, source: Path) -> tuple[str, int]:
        """把上传的临时文件移动/复制到 staging/<sha256>；返回 (blob_id, 字节数)。"""
        source = Path(source)
        if not source.is_file():
            raise _artifact_missing(f"上传暂存文件不存在：{source.name}")
        blob_id, size = self._hash_file(source)
        target = self.path_of(AREA_STAGING, blob_id)
        if target.is_file() and target.stat().st_size == size:
            source.unlink(missing_ok=True)
            return blob_id, size
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(source, target)
        except OSError:
            # 跨卷或占用时退化为复制 + 删除源文件
            self._copy_file(source, target)
            source.unlink(missing_ok=True)
        return blob_id, size

    def seal(self, *, area: str, blob_id: str) -> Path:
        """把 staging 中的产物封存到不可变区域；已存在则校验后直接返回。"""
        if area not in (AREA_BLOBS, AREA_NORMALIZED):
            raise ValueError(f"不可封存到 {area}")
        if not isinstance(blob_id, str) or not blob_id:
            raise _artifact_missing("blob id 为空")
        target = self.path_of(area, blob_id)
        if target.is_file():
            actual = sha256_bytes(target.read_bytes())
            if actual != blob_id:
                raise _artifact_corrupt(f"{area}/{blob_id} 已存在但内容指纹不符")
            return target
        source = self.path_of(AREA_STAGING, blob_id)
        if not source.is_file():
            raise _artifact_missing(f"staging/{blob_id} 不存在，无法封存")
        data = source.read_bytes()
        if sha256_bytes(data) != blob_id:
            raise _artifact_corrupt(f"staging/{blob_id} 内容指纹不符")
        self._atomic_write(target, data)
        return target

    def read_bytes(self, *, area: str, blob_id: str) -> bytes:
        target = self.path_of(area, blob_id)
        if not target.is_file():
            raise _artifact_missing(f"{area}/{blob_id} 不存在")
        data = target.read_bytes()
        if sha256_bytes(data) != blob_id:
            raise _artifact_corrupt(f"{area}/{blob_id} 内容指纹不符")
        return data

    def read_text(self, *, area: str, blob_id: str) -> str:
        data = self.read_bytes(area=area, blob_id=blob_id)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _artifact_corrupt(f"{blob_id} 不是合法 UTF-8 文本") from exc

    def read_json(self, *, area: str, blob_id: str) -> object:
        text = self.read_text(area=area, blob_id=blob_id)
        try:
            return json.loads(text)
        except ValueError as exc:
            raise _artifact_corrupt(f"{blob_id} 不是合法 JSON") from exc

    # ------------------------------------------------------------- 内部

    def _atomic_write(self, target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.tmp-{uuid.uuid4().hex}")
        try:
            with open(temporary, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    def _copy_file(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(source, "rb") as reader, open(target, "wb") as writer:
            while True:
                chunk = reader.read(_CHUNK_SIZE)
                if not chunk:
                    break
                writer.write(chunk)
