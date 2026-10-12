"""RAG v2 范围解析与使用前核验：SQLite 权威 → 冻结快照 → 允许集合（下推过滤）。

规则（对应 docs/PLAN.md §6.2/§6.3）：

- ``resolve_scope`` 调 B0 的 ``catalog.resolve_selection`` 做全部权威核验（存活、归属、
  年级/学科/版本、逻辑库、当前修订、代内 ready），再由 ``catalog_state.active_generation_id``
  取当前索引代，算出稳定 ``scopeHash``。
- ``verify_scope`` **每次使用前重算**：先比当前代与快照代，再重新解析范围，逐条比对
  快照里的 (documentId, documentRevisionId, metadataRevisionId)，最后重算 ``scopeHash``；
  任一不符抛 409 ``RAG_SCOPE_CHANGED``，缺口抛 409 ``INDEX_NOT_READY``。
- ``allowed_filter`` 把允许的修订/分块集白名单交给向量库下推，绝不"先全库取回再过滤"。
  空范围返回空元组条件（语义为"不允许任何值"），不回退全库。

``scopeHash`` 只用于检测快照意外变化，不是认证凭证；服务端始终重新检查归属与删除状态。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import MetadataRevisionRecord, ResolvedDocument
from app.repositories.vector_store.base import AllowedFilter
from app.schemas.rag_v2 import ScopeDocument, ScopeSnapshot
from app.schemas.textbook import TextbookSelection
from app.services.textbook_ingest.taxonomy import SUBJECTS

SCOPE_SCHEMA_VERSION = 2
ALLOWED_OWNERS: tuple[str, ...] = ("system", "local-user")
BODY_REGION = "body"

_SUBJECT_LABELS = {item.id: item.label for item in SUBJECTS}


def canonical_json(payload: Any) -> str:
    """固定键序与分隔符的 JSON：同一逻辑内容产生同一字节串。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _scope_changed(message: str) -> AppError:
    return AppError(message, code="RAG_SCOPE_CHANGED", status_code=409)


def _index_not_ready(message: str) -> AppError:
    return AppError(message, code="INDEX_NOT_READY", status_code=409)


def _field(source: object, snake: str, camel: str) -> str:
    """同一字段的两种命名（B0 记录用 snake_case，契约模型用 camelCase）。"""
    value = getattr(source, snake, None)
    if value is None:
        value = getattr(source, camel, None)
    if not isinstance(value, str) or not value:
        raise _scope_changed("教材范围快照字段缺失或非法，请重新确认范围。")
    return value


def scope_document_entries(documents: Sequence[object]) -> list[dict[str, str]]:
    """把快照条目或 B0 解析结果统一成按 documentId 排序的规范化条目。"""
    entries = [
        {
            "documentId": _field(item, "document_id", "documentId"),
            "documentRevisionId": _field(item, "document_revision_id", "documentRevisionId"),
            "metadataRevisionId": _field(item, "metadata_revision_id", "metadataRevisionId"),
        }
        for item in documents
    ]
    entries.sort(key=lambda entry: entry["documentId"])
    return entries


def scope_hash(
    *,
    selection: TextbookSelection,
    documents: Sequence[object],
    embedding_generation_id: str,
) -> str:
    """快照散列：schemaVersion + selection + 按 documentId 排序的条目 + 索引代。"""
    payload = {
        "schemaVersion": SCOPE_SCHEMA_VERSION,
        "selection": selection.model_dump(),
        "documents": scope_document_entries(documents),
        "embeddingGenerationId": embedding_generation_id,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RevisionScope:
    """允许检索的一段教材范围：一次修订 + 其分块集 + 展示用分类标签。"""

    document_id: str
    document_revision_id: str
    metadata_revision_id: str
    chunk_set_id: str
    owner_id: str
    title: str
    edition_label: str
    subject_label: str
    grade_ids: tuple[str, ...]
    library_ids: tuple[str, ...]


def edition_label(metadata: MetadataRevisionRecord) -> str:
    """人类可读版本标签：版次 + 册次；都为空时退回版本 id。"""
    parts = [part.strip() for part in (metadata.publication_label, metadata.volume_label) if part.strip()]
    return " ".join(parts) if parts else metadata.edition_id


def subject_label(subject_id: str) -> str:
    return _SUBJECT_LABELS.get(subject_id, subject_id)


def resolve_scope(catalog: TextbookCatalog, selection: TextbookSelection) -> ScopeSnapshot:
    """解析任教范围为冻结快照；任何不满足都抛 B0 的 409/422，不给部分结果。"""
    resolved = catalog.resolve_selection(selection)
    state = catalog.catalog_state()
    generation_id = state.active_generation_id
    if not generation_id:
        raise _index_not_ready("当前没有已发布的教材索引代，无法冻结检索范围。")
    entries = scope_document_entries(resolved)
    return ScopeSnapshot(
        selection=selection,
        documents=[ScopeDocument(**entry) for entry in entries],
        embeddingGenerationId=generation_id,
        scopeHash=scope_hash(
            selection=selection,
            documents=resolved,
            embedding_generation_id=generation_id,
        ),
    )


def verify_scope(catalog: TextbookCatalog, snapshot: ScopeSnapshot) -> tuple[RevisionScope, ...]:
    """使用前重算：代、范围、快照条目与散列全部一致才返回允许的修订集合。"""
    state = catalog.catalog_state()
    if not state.active_generation_id or state.active_generation_id != snapshot.embeddingGenerationId:
        raise _scope_changed("当前索引代已切换，教材范围需要重新确认。")
    generation = catalog.get_generation(snapshot.embeddingGenerationId)
    if generation is None or generation.state != "ready":
        raise _index_not_ready("当前索引代未就绪，无法按该范围检索。")

    resolved = catalog.resolve_selection(snapshot.selection)
    expected = scope_document_entries(resolved)
    provided = scope_document_entries(snapshot.documents)
    if expected != provided:
        raise _scope_changed("教材范围中的书册或修订已变化，请重新确认范围。")
    recomputed = scope_hash(
        selection=snapshot.selection,
        documents=resolved,
        embedding_generation_id=snapshot.embeddingGenerationId,
    )
    if recomputed != snapshot.scopeHash:
        raise _scope_changed("教材范围快照校验失败，请重新确认范围后重试。")

    allowed = catalog.allowed_chunks(
        snapshot.embeddingGenerationId,
        [item.document_revision_id for item in resolved],
    )
    scopes: list[RevisionScope] = []
    for item in resolved:
        document = catalog.get_document(item.document_id)
        if document is None or document.deleted_at is not None:
            raise _scope_changed("所选教材已删除或不存在，请重新确认范围。")
        if document.owner_id not in ALLOWED_OWNERS:
            raise _scope_changed("所选教材归属异常，请重新确认范围。")
        if document.current_revision_id != item.document_revision_id:
            raise _scope_changed("所选教材的当前修订已变化，请重新确认范围。")
        metadata = catalog.get_metadata_revision(item.metadata_revision_id)
        if metadata is None or metadata.document_id != item.document_id:
            raise _scope_changed("所选教材的分类修订已变化，请重新确认范围。")
        scopes.append(
            RevisionScope(
                document_id=item.document_id,
                document_revision_id=item.document_revision_id,
                metadata_revision_id=item.metadata_revision_id,
                chunk_set_id=item.chunk_set_id,
                owner_id=document.owner_id,
                title=metadata.title,
                edition_label=edition_label(metadata),
                subject_label=subject_label(metadata.subject_id),
                grade_ids=tuple(metadata.grade_ids),
                library_ids=tuple(item.library_ids),
            )
        )
    # B0 的 allowed_chunks 是代内 ready 白名单的权威顺序来源：两者必须一致。
    returned_revisions = tuple(scope.document_revision_id for scope in scopes)
    if set(returned_revisions) != set(allowed.revision_ids):
        raise _index_not_ready("教材索引代尚未包含所选修订，请等待入库完成后重试。")
    if set(allowed.chunk_set_ids) != {item.chunk_set_id for item in resolved}:
        raise _index_not_ready("教材分块集与索引代不一致，请等待重新入库完成后重试。")
    return tuple(sorted(scopes, key=lambda scope: scope.document_id))


def allowed_filter(scope: Sequence[RevisionScope]) -> AllowedFilter:
    """允许集合过滤：修订 / 分块集白名单 + 归属 + 正文区，一次性下推给向量库。

    空范围产生空元组条件（"不允许任何值"），因此不会回退全库。
    """
    revision_ids: list[str] = []
    chunk_set_ids: list[str] = []
    for item in scope:
        if item.document_revision_id not in revision_ids:
            revision_ids.append(item.document_revision_id)
        if item.chunk_set_id not in chunk_set_ids:
            chunk_set_ids.append(item.chunk_set_id)
    return AllowedFilter(
        revision_ids=tuple(sorted(revision_ids)),
        chunk_set_ids=tuple(sorted(chunk_set_ids)),
        owners=ALLOWED_OWNERS,
        region=BODY_REGION,
    )


def scope_by_revision(scope: Sequence[RevisionScope]) -> dict[str, RevisionScope]:
    return {item.document_revision_id: item for item in scope}


def scope_by_chunk_set(scope: Sequence[RevisionScope]) -> dict[str, RevisionScope]:
    return {item.chunk_set_id: item for item in scope}
