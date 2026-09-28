"""索引代（generation）文档格式：分块策略与代内冻结清单。

B0 的 ``index_generations.chunk_policy_json`` 是唯一的 JSON 存储位；这里固定其结构：

```json
{
  "policy": {"targetChars": 800, "maxChars": 1200, "overlapChars": 120, "version": "zqky-chunk-v1"},
  "manifest": [{"documentId": "...", "documentRevisionId": "...", "metadataRevisionId": "...", "title": "..."}]
}
```

``manifest`` 是"开始构建时现存教材的当前修订快照"：重建期间被删除的书册整条跳过且不复活，
新建/更新被闸门挡住，因此快照只可能收缩而不会膨胀，发布前用它与当前状态对账。

接口缺口（已上报总控）：B0 未提供独立的代内清单表，也没有"重建期间更新清单"的写入路径，
故清单与策略同存一列；若后续新增 ``generation_manifest`` 表，本模块是唯一需要改动的读取点。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.records import GenerationRecord
from app.services.document_parsing.chunking import (
    DEFAULT_CHUNK_POLICY,
    ChunkPolicy,
    chunk_policy_from_json,
    chunk_policy_json,
)

GENERATION_POLICY_KEY = "policy"
GENERATION_MANIFEST_KEY = "manifest"
COLLECTION_PREFIX = "textbooks_"


@dataclass(frozen=True)
class ManifestEntry:
    document_id: str
    document_revision_id: str
    metadata_revision_id: str
    title: str

    def to_json(self) -> dict:
        return {
            "documentId": self.document_id,
            "documentRevisionId": self.document_revision_id,
            "metadataRevisionId": self.metadata_revision_id,
            "title": self.title,
        }

    @classmethod
    def from_json(cls, payload: object) -> "ManifestEntry":
        if not isinstance(payload, dict):
            raise _corrupt("清单条目不是 JSON 对象。")
        values = []
        for key in ("documentId", "documentRevisionId", "metadataRevisionId"):
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                raise _corrupt(f"清单条目缺少 {key}。")
            values.append(value)
        title = payload.get("title")
        return cls(
            document_id=values[0],
            document_revision_id=values[1],
            metadata_revision_id=values[2],
            title=title if isinstance(title, str) else "",
        )


def _corrupt(detail: str) -> AppError:
    return AppError(
        f"索引代数据损坏：{detail}",
        code="GENERATION_DOC_CORRUPT",
        status_code=500,
    )


def new_collection_name() -> str:
    """collection 名唯一且不可变；不使用 alias 维护第二个"当前"指针。

    说明：B0 的 ``create_generation`` 不允许调用方指定 generation_id，因此这里用
    独立 uuid 生成 collection 名（计划中的 ``textbooks_<generation_id>`` 形式需要
    B0 增加该入参；已作为接口缺口上报总控）。
    """
    return f"{COLLECTION_PREFIX}{uuid.uuid4().hex}"


def generation_policy_document(
    policy: ChunkPolicy = DEFAULT_CHUNK_POLICY,
    manifest: list[ManifestEntry] | tuple[ManifestEntry, ...] = (),
) -> dict:
    return {
        GENERATION_POLICY_KEY: chunk_policy_json(policy),
        GENERATION_MANIFEST_KEY: [entry.to_json() for entry in manifest],
    }


def generation_policy(generation: GenerationRecord) -> ChunkPolicy:
    payload = generation.chunk_policy
    raw = payload.get(GENERATION_POLICY_KEY)
    if raw is None:
        # 兼容早期只写策略参数的代
        raw = {key: value for key, value in payload.items() if key != GENERATION_MANIFEST_KEY}
    return chunk_policy_from_json(raw)


def generation_manifest(generation: GenerationRecord) -> tuple[ManifestEntry, ...]:
    payload = generation.chunk_policy
    raw = payload.get(GENERATION_MANIFEST_KEY, [])
    if not isinstance(raw, list):
        raise _corrupt("manifest 不是数组。")
    return tuple(ManifestEntry.from_json(item) for item in raw)
