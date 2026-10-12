"""不可变规范化文本读取与来源定位（只读，复用 B1 的解析产物）。

- ``ImmutableSource.read_normalized_text``：读该修订封存的规范化文本，并核验
  UTF-8 sha256 与字符数与修订登记一致；不符抛 409 ``RAG_EVIDENCE_UNAVAILABLE``，
  绝不返回可疑内容。目录若实现了 ``read_normalized_text`` 就优先复用，否则读
  ``textbooks_root/normalized`` 下的内容寻址 blob。
- ``ImmutableSource.locate``：把 char 区间转成 markdown 行号 / pdf 页码 / docx 段落序号。
  语义与 ``services/textbook_ingest/source_access.py`` 的定位逐字段一致（同一
  ``parsed_from_source_map`` + ``ParsedDocument.blocks_in``），本模块只是加了每修订缓存，
  避免一次详解对同一册重复读来源映射；不改动 B1 文件。
- ``ImmutableSource.region_of``：区间所属正文/习题区（与分块器同一 ``regions`` 规则）。

缓存按修订 id 有界（一次会话最多几十册），只缓存不可变产物，不缓存用户内容。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.records import RevisionRecord
from app.schemas.textbook import LocatorView
from app.services.document_parsing.parser import (
    ParsedDocument,
    parsed_from_source_map,
)
from app.services.document_parsing.regions import (
    REGION_BODY,
    RegionSpan,
    region_for_span,
    split_regions,
)
from app.services.textbook_ingest.blobs import BlobStore, sha256_text


class ImmutableTextSource(Protocol):
    """按文档修订读取规范化文本的端口（测试可注入替身）。"""

    def read_normalized_text(self, revision: RevisionRecord) -> str: ...


def unavailable(message: str) -> AppError:
    return AppError(message, code="RAG_EVIDENCE_UNAVAILABLE", status_code=409)


def blob_root_for(catalog: object) -> Path:
    """教材数据根：目录数据库所在目录（``textbooks_root``）。"""
    db_path = getattr(catalog, "db_path", None)
    if not isinstance(db_path, Path):
        db_path = Path(str(db_path))
    return db_path.parent


class ImmutableSource:
    """规范化文本 / 来源映射 / 定位的统一只读入口。"""

    def __init__(
        self,
        *,
        catalog: object,
        blob_store: BlobStore | None = None,
        blobs_root: Path | str | None = None,
    ) -> None:
        self.catalog = catalog
        if blob_store is None:
            root = Path(blobs_root) if blobs_root is not None else blob_root_for(catalog)
            blob_store = BlobStore(root)
        self.blobs = blob_store
        self._parsed: dict[str, ParsedDocument] = {}
        self._text: dict[str, str] = {}

    # ------------------------------------------------------------------ 文本

    def read_normalized_text(self, revision: RevisionRecord) -> str:
        cached = self._text.get(revision.revision_id)
        if cached is None:
            cached = self._load_text(revision)
            self._text[revision.revision_id] = cached
        if len(cached) != revision.char_count or sha256_text(cached) != revision.normalized_text_sha256:
            raise unavailable("规范化原文与修订登记不符，已停止使用该教材原句。")
        return cached

    def _load_text(self, revision: RevisionRecord) -> str:
        reader = getattr(self.catalog, "read_normalized_text", None)
        if callable(reader):
            text = reader(revision.revision_id)
            if not isinstance(text, str):
                raise unavailable("规范化原文读取结果非法，已停止使用该教材原句。")
            return text
        try:
            return self.blobs.read_text(area="normalized", blob_id=revision.normalized_blob_id)
        except AppError as exc:
            raise unavailable(f"规范化原文不可用：{exc}") from exc

    # ------------------------------------------------------------ 来源映射

    def parsed_document(self, revision: RevisionRecord) -> ParsedDocument:
        cached = self._parsed.get(revision.revision_id)
        if cached is not None:
            return cached
        try:
            payload = self.blobs.read_json(area="normalized", blob_id=revision.source_map_blob_id)
        except AppError as exc:
            raise unavailable(f"教材来源映射不可用：{exc}") from exc
        parsed = parsed_from_source_map(payload, normalized_text=self.read_normalized_text(revision))
        self._parsed[revision.revision_id] = parsed
        return parsed

    # ---------------------------------------------------------------- 定位

    def locate(self, revision: RevisionRecord, char_start: int, char_end: int) -> LocatorView:
        """与 ``source_access.read_source_span`` 同一套定位语义（行号 / 页码 / 段落序号）。"""
        blocks = self.parsed_document(revision).blocks_in(char_start, char_end)
        kind = self.parsed_document(revision).source_kind
        if not blocks:
            return LocatorView(kind=kind)
        return LocatorView(
            kind=kind,
            lineStart=_min_of(blocks, "line_start"),
            lineEnd=_max_of(blocks, "line_end"),
            pageStart=_min_of(blocks, "page_start"),
            pageEnd=_max_of(blocks, "page_end"),
            blockStart=_min_of(blocks, "block_start"),
            blockEnd=_max_of(blocks, "block_end"),
        )

    def region_spans(self, revision: RevisionRecord) -> list[RegionSpan]:
        return split_regions(self.parsed_document(revision))

    def region_of(self, revision: RevisionRecord, char_start: int, char_end: int) -> str:
        return region_for_span(self.region_spans(revision), char_start, char_end)

    def clear_cache(self) -> None:
        self._parsed.clear()
        self._text.clear()


def _values(blocks: list, attribute: str) -> list[int]:
    return [value for value in (getattr(block, attribute) for block in blocks) if value is not None]


def _min_of(blocks: list, attribute: str) -> int | None:
    values = _values(blocks, attribute)
    return min(values) if values else None


def _max_of(blocks: list, attribute: str) -> int | None:
    values = _values(blocks, attribute)
    return max(values) if values else None


__all__ = ["ImmutableSource", "ImmutableTextSource", "REGION_BODY", "blob_root_for", "unavailable"]
