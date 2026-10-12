"""受控原文读取：按不可变修订与半开字符区间返回规范化文本与来源定位。

规则（对应 `GET /textbook-revisions/{id}/source`）：
- 越界或空区间 → 422（``INVALID_REQUEST``）；
- 规范化文本指纹与修订登记不符 → 409（``SOURCE_HASH_MISMATCH``），不返回可疑内容；
- 定位取自封存来源映射，不做外部路径推断。
"""

from __future__ import annotations

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.schemas.textbook import LocatorView, SourceSpanView
from app.services.document_parsing.parser import parsed_from_source_map
from app.services.textbook_ingest.blobs import BlobStore, sha256_text


def read_source_span(
    *,
    catalog: TextbookCatalog,
    blobs: BlobStore,
    revision_id: str,
    char_start: int,
    char_end: int,
) -> SourceSpanView:
    revision = catalog.get_revision(revision_id)
    if revision is None:
        raise AppError("文档修订不存在。", code="REVISION_NOT_FOUND", status_code=404)
    if (
        isinstance(char_start, bool)
        or isinstance(char_end, bool)
        or char_start < 0
        or char_end <= char_start
        or char_end > revision.char_count
    ):
        raise AppError(
            f"字符区间不合法：[{char_start}, {char_end}) 超出修订长度 {revision.char_count}。",
            code="INVALID_REQUEST",
            status_code=422,
        )

    text = blobs.read_text(area="normalized", blob_id=revision.normalized_blob_id)
    if len(text) != revision.char_count or sha256_text(text) != revision.normalized_text_sha256:
        raise AppError(
            "规范化文本指纹与修订登记不符，拒绝返回原文。",
            code="SOURCE_HASH_MISMATCH",
            status_code=409,
        )

    payload = blobs.read_json(area="normalized", blob_id=revision.source_map_blob_id)
    parsed = parsed_from_source_map(payload, normalized_text=text)
    locator = _locator(parsed, char_start=char_start, char_end=char_end)
    return SourceSpanView(
        documentRevisionId=revision.revision_id,
        normalizedTextSha256=revision.normalized_text_sha256,
        charStart=char_start,
        charEnd=char_end,
        text=text[char_start:char_end],
        locator=locator,
    )


def _locator(parsed, *, char_start: int, char_end: int) -> LocatorView:
    blocks = parsed.blocks_in(char_start, char_end)
    kind = parsed.source_kind
    if not blocks:
        return LocatorView(kind=kind)
    line_starts = [block.line_start for block in blocks if block.line_start is not None]
    line_ends = [block.line_end for block in blocks if block.line_end is not None]
    page_starts = [block.page_start for block in blocks if block.page_start is not None]
    page_ends = [block.page_end for block in blocks if block.page_end is not None]
    block_starts = [block.block_start for block in blocks if block.block_start is not None]
    block_ends = [block.block_end for block in blocks if block.block_end is not None]
    return LocatorView(
        kind=kind,
        lineStart=min(line_starts) if line_starts else None,
        lineEnd=max(line_ends) if line_ends else None,
        pageStart=min(page_starts) if page_starts else None,
        pageEnd=max(page_ends) if page_ends else None,
        blockStart=min(block_starts) if block_starts else None,
        blockEnd=max(block_ends) if block_ends else None,
    )
