"""RAG v2 专属测试的共享夹具：临时目录 + 替身，不读正式 .env、不写正式 .local-data。

这里只搭"真实 B0/B1 产物 + 替身向量/替身概括/替身聊天模型"的现场：

- 目录、修订、分块集、索引代全部经 `TextbookCatalog` 真实写入 SQLite；
- 规范化文本与来源映射真实封存进 `BlobStore`（B1 的内容寻址布局）；
- 向量写入内存向量库替身，payload 字段与 B1 索引器一致；
- 唯一替身是 Embedding 输出、向量库（可选脚本化）、本地概括与聊天模型；
- 不使用正式 `.local-data`、正式 `.env`，不做任何真实 Ollama / Qdrant 调用。
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import AppError
from app.providers.embeddings.fingerprint import canonical_json, embedding_fingerprint
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.vector_store import (
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_GENERATION_ID,
    PAYLOAD_ORDINAL,
    PAYLOAD_OWNER_ID,
    PAYLOAD_REGION,
    PAYLOAD_REVISION_ID,
    PAYLOAD_TEXT_SHA256,
    AllowedFilter,
    InMemoryVectorStore,
    VectorPoint,
    point_id_for,
)
from app.schemas.rag_v2 import RagPoint, ScopeSnapshot
from app.schemas.textbook import TextbookSelection
from app.services.document_parsing import (
    DEFAULT_CHUNK_POLICY,
    PARSER_VERSION,
    chunk_document,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
    parse_document,
    source_map_payload,
)
from app.services.rag_v2.explain import ChatModelHandle, ExplainDelta
from app.services.rag_v2.retrieval import HybridRetriever
from app.services.rag_v2.scope import resolve_scope
from app.services.rag_v2.service import RagV2Service
from app.services.rag_v2.summary import SummaryOutcome
from app.services.textbook_ingest.blobs import BlobStore, sha256_text
from app.services.textbook_ingest.generation_doc import generation_policy_document

DIMENSIONS = 8
MODEL = "bge-m3"
DIGEST = "digest-1"
QUERY_PREFIX = ""


def deterministic_vector(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    """确定性的非零向量：任何两条都正相关，便于断言"命中范围"而不是"相似度运气"。"""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [1.0 + digest[index] / 255.0 for index in range(dimensions)]


class FakeEmbeddings:
    """Embedding 替身：只按文本产出确定性向量，不触碰任何本机服务。"""

    def __init__(
        self,
        *,
        dimensions: int = DIMENSIONS,
        model: str = MODEL,
        digest: str = DIGEST,
        fail: AppError | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.model_name = model
        self.digest = digest
        self.fail = fail
        self.calls: list[tuple[str, list[str]]] = []

    def vector_for(self, text: str) -> list[float]:
        return deterministic_vector(text, self.dimensions)

    def manifest_digest(self, model: str) -> str:
        if model != self.model_name:
            raise AppError("模型不存在。", code="EMBEDDING_MODEL_MISSING", status_code=404)
        return self.digest

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        self.calls.append((model, list(texts)))
        if self.fail is not None:
            raise self.fail
        return [self.vector_for(text) for text in texts]


class RecordingVectorStore:
    """包装内存向量库：记录每次 search 的过滤条件，供"必须下推 filter"断言。"""

    def __init__(self, inner: InMemoryVectorStore | None = None) -> None:
        self.inner = inner if inner is not None else InMemoryVectorStore()
        self.calls: list[dict] = []

    def ensure_collection(self, **kwargs):
        return self.inner.ensure_collection(**kwargs)

    def upsert(self, **kwargs):
        return self.inner.upsert(**kwargs)

    def search(self, *, name: str, vector: list[float], limit: int, allowed: AllowedFilter | None = None):
        self.calls.append({"name": name, "limit": limit, "allowed": allowed})
        return self.inner.search(name=name, vector=vector, limit=limit, allowed=allowed)

    def delete_by_filter(self, **kwargs):
        return self.inner.delete_by_filter(**kwargs)

    def count(self, **kwargs):
        return self.inner.count(**kwargs)

    def collection_exists(self, name: str) -> bool:
        return self.inner.collection_exists(name)

    def ping(self) -> bool:
        return self.inner.ping()

    def delete_collection(self, name: str) -> None:
        self.inner.delete_collection(name)


class ScriptedVectorStore:
    """按脚本返回稠密命中（payload 由脚本给出）；同时记录 filter。"""

    def __init__(self, hits: list[tuple[str, int, str, str]]) -> None:
        # hits: (chunk_set_id, ordinal, document_revision_id, point_id)
        self.hits = list(hits)
        self.calls: list[dict] = []
        self.score = 0.9

    def ensure_collection(self, **kwargs) -> None: ...

    def upsert(self, **kwargs) -> None: ...

    def search(self, *, name: str, vector: list[float], limit: int, allowed: AllowedFilter | None = None):
        from app.repositories.vector_store import VectorHit

        self.calls.append({"name": name, "limit": limit, "allowed": allowed})
        results = []
        score = self.score
        for index, (chunk_set_id, ordinal, revision_id, point_id) in enumerate(self.hits[:limit]):
            results.append(
                VectorHit(
                    point_id=point_id,
                    score=score - index * 0.01,
                    payload={
                        PAYLOAD_CHUNK_SET_ID: chunk_set_id,
                        PAYLOAD_ORDINAL: ordinal,
                        PAYLOAD_REVISION_ID: revision_id,
                        PAYLOAD_REGION: "body",
                    },
                )
            )
        return results

    def delete_by_filter(self, **kwargs) -> None: ...

    def count(self, **kwargs) -> int:
        return len(self.hits)

    def collection_exists(self, name: str) -> bool:
        return True

    def ping(self) -> bool:
        return True

    def delete_collection(self, name: str) -> None: ...


@dataclass
class DocumentHandle:
    document_id: str
    revision_id: str
    metadata_revision_id: str
    chunk_set_id: str
    title: str
    normalized_text: str
    chunks: list = field(default_factory=list)

    @property
    def chunk_texts(self) -> dict[int, str]:
        return {
            chunk.ordinal: self.normalized_text[chunk.char_start:chunk.char_end]
            for chunk in self.chunks
        }

    def body_chunks(self) -> list:
        return [chunk for chunk in self.chunks if chunk.region == "body"]

    def first_body_chunk(self):
        return self.body_chunks()[0]


class RecordingRetrieval:
    """包装真实检索器：记录调用与线程、可注入闸门，用于有界/超时/迟到结果断言。"""

    def __init__(self, inner: HybridRetriever, *, gate=None) -> None:
        self.inner = inner
        self.gate = gate
        self.calls: list[str] = []
        self.thread_ids: list[int] = []
        self.dense_limit = inner.dense_limit
        self.lexical_limit = inner.lexical_limit
        self.rrf_k = inner.rrf_k
        self.vectors = inner.vectors
        self.embeddings = inner.embeddings

    def retrieve(self, **kwargs):
        self.calls.append(kwargs["question"])
        self.thread_ids.append(threading.get_ident())
        if self.gate is not None:
            self.gate.wait(3)
        return self.inner.retrieve(**kwargs)


class EmptyRetrieval:
    """永远没有候选：验证"无证据不编造"与"详解不得再次检索"。"""

    dense_limit, lexical_limit, rrf_k = 50, 50, 60
    vectors = None
    embeddings = None

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        return []


class FakeSummarizer:
    """本地概括替身：默认给一条引用首条证据的知识点；可指定不可用/非法输出。"""

    def __init__(
        self,
        *,
        points: list[RagPoint] | None = None,
        reason: str | None = None,
        unavailable: bool = False,
        error: AppError | None = None,
        model: str = "qwen2.5:7b",
        provider_url: str = "http://127.0.0.1:11434",
    ) -> None:
        self.points = points
        self.reason = reason
        self.unavailable = unavailable
        self.error = error
        self.model = model
        self.provider_url = provider_url
        self.calls: list[tuple[str, list]] = []

    def status(self) -> dict:
        reason = "本地知识点概括服务当前不可用。" if self.unavailable else None
        return {
            "available": not self.unavailable,
            "reason": reason,
            "model": self.model,
            "providerUrl": self.provider_url,
        }

    def summarize(self, *, question: str, evidence) -> SummaryOutcome:
        self.calls.append((question, list(evidence)))
        if self.error is not None:
            raise self.error
        if self.unavailable:
            raise AppError(
                "本地知识点概括服务不可用。",
                code="RAG_SUMMARY_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if self.points is not None:
            return SummaryOutcome(points=list(self.points), reason=self.reason)
        ids = [item.evidenceId for item in evidence]
        return SummaryOutcome(
            points=[
                RagPoint(
                    pointId="pt-test-1",
                    title="教材知识点",
                    summary="教材原文要点摘录。",
                    evidenceIds=ids[:1],
                )
            ],
            reason=self.reason,
        )


class FakeExplainer:
    """详解替身：记录调用与关闭次数；产出指定增量或失败。"""

    def __init__(
        self,
        *,
        deltas: tuple[ExplainDelta, ...] | None = None,
        error: BaseException | None = None,
        freeze_error: BaseException | None = None,
    ) -> None:
        self.deltas = deltas if deltas is not None else (
            ExplainDelta(type="text", text="教材依据说明。"),
            ExplainDelta(type="end", finishReason="stop"),
        )
        self.error = error
        self.freeze_error = freeze_error
        self.calls: list[dict] = []
        self.frozen: list[str] = []
        self.closed = 0

    def freeze_model(self, model_profile_id: str) -> ChatModelHandle:
        self.frozen.append(model_profile_id)
        if self.freeze_error is not None:
            raise self.freeze_error
        return ChatModelHandle(
            profile_id=model_profile_id,
            model_id="chat-model-1",
            provider=None,  # 替身：不经过真实 Provider
            config=None,  # type: ignore[arg-type]
            max_output_tokens=1024,
        )

    async def explain(self, body, *, evidence, model):
        self.calls.append({"body": body, "evidence": list(evidence), "model": model})
        try:
            if self.error is not None:
                raise self.error
            for delta in self.deltas:
                yield delta
        finally:
            self.closed += 1


class RagEnv:
    """一套完整的教材目录 + 索引代 + 检索器现场（全部在 ``tmp_path`` 内）。"""

    def __init__(
        self,
        tmp_path: Path,
        *,
        vectors=None,
        embeddings: FakeEmbeddings | None = None,
        summarizer: FakeSummarizer | None = None,
        explainer: FakeExplainer | None = None,
        query_prefix: str = QUERY_PREFIX,
        dimensions: int = DIMENSIONS,
    ) -> None:
        self.tmp_path = Path(tmp_path)
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset(),
            env="test",
            data_dir=self.tmp_path / "data",
        )
        self.catalog = TextbookCatalog(self.settings.textbooks_root / "catalog.sqlite3")
        self.catalog.migrate()
        self.blobs = BlobStore(self.settings.textbooks_root)
        self.blobs.ensure_dirs()
        self.embeddings = embeddings if embeddings is not None else FakeEmbeddings(dimensions=dimensions)
        self.vectors = vectors if vectors is not None else RecordingVectorStore()
        self.dimensions = dimensions
        self.profile = self.catalog.create_embedding_profile(
            fingerprint=embedding_fingerprint(
                model_manifest_digest=DIGEST,
                dimensions=dimensions,
                query_prefix=query_prefix,
                document_prefix="",
                normalization="none",
            ),
            adapter="ollama",
            native_base_url="http://127.0.0.1:11434",
            model_name=MODEL,
            model_manifest_digest=DIGEST,
            dimensions=dimensions,
            distance="cosine",
            query_prefix=query_prefix,
            document_prefix="",
            normalization="none",
        )
        self.collection = f"textbooks_{uuid.uuid4().hex}"
        self.generation = self.catalog.create_generation(
            profile_id=self.profile.profile_id,
            collection_name=self.collection,
            chunk_policy_json=generation_policy_document(DEFAULT_CHUNK_POLICY, []),
            state="building",
        )
        self.vectors.ensure_collection(
            name=self.collection, dimensions=dimensions, distance="Cosine"
        )
        self.catalog.publish_generation(self.generation.generation_id)
        self.catalog.set_active_generation(self.generation.generation_id)
        self.library = self.catalog.create_library(
            kind="base",
            owner_id="system",
            display_name="基础库·高一数学",
            grade_id="senior-1",
            subject_id="math",
            edition_id="renjiao-a",
        )
        self.documents: dict[str, DocumentHandle] = {}
        self.retriever = HybridRetriever(self.catalog, self.vectors, self.embeddings)
        self.summarizer = summarizer
        self.explainer = explainer

    # ------------------------------------------------------------------ 现场

    def new_library(
        self,
        *,
        grade_id: str,
        subject_id: str,
        edition_id: str = "renjiao-a",
        owner_id: str = "system",
        display_name: str = "逻辑库",
    ) -> str:
        record = self.catalog.create_library(
            kind="base" if owner_id == "system" else "personal",
            owner_id=owner_id,
            display_name=display_name,
            grade_id=grade_id,
            subject_id=subject_id,
            edition_id=edition_id,
        )
        return record.library_id

    def add_document(
        self,
        *,
        title: str,
        text: str,
        library_ids: list[str] | None = None,
        subject_id: str = "math",
        grade_ids: tuple[str, ...] = ("senior-1",),
        edition_id: str = "renjiao-a",
        owner_id: str = "system",
        file_name: str = "chapter.md",
        vector_overrides: dict[int, list[float]] | None = None,
    ) -> DocumentHandle:
        target_libraries = library_ids if library_ids is not None else [self.library.library_id]
        path = self.tmp_path / f"{uuid.uuid4().hex}-{file_name}"
        path.write_text(text, encoding="utf-8")
        parsed = parse_document(path=path, file_name=file_name)
        normalized_blob_id = self.blobs.write_staged_bytes(parsed.normalized_text.encode("utf-8"))
        self.blobs.seal(area="normalized", blob_id=normalized_blob_id)
        source_map_blob_id = self.blobs.write_staged_bytes(
            canonical_json(source_map_payload(parsed)).encode("utf-8")
        )
        self.blobs.seal(area="normalized", blob_id=source_map_blob_id)
        original_blob_id = self.blobs.write_staged_bytes(path.read_bytes())
        self.blobs.seal(area="blobs", blob_id=original_blob_id)

        document = self.catalog.create_document(
            owner_id=owner_id,
            title=title,
            stage_id="senior",
            grade_ids=list(grade_ids),
            subject_id=subject_id,
            edition_id=edition_id,
            library_ids=target_libraries,
        )
        revision = self.catalog.create_document_revision(
            document.document_id,
            original_file_sha256=original_blob_id,
            normalized_text_sha256=sha256_text(parsed.normalized_text),
            parser_version=PARSER_VERSION,
            original_blob_id=original_blob_id,
            normalized_blob_id=normalized_blob_id,
            source_map_blob_id=source_map_blob_id,
            char_count=len(parsed.normalized_text),
        )
        chunks = chunk_document(parsed, policy=DEFAULT_CHUNK_POLICY)
        chunk_set = self.catalog.create_chunk_set(
            revision.revision_id,
            policy_fingerprint=chunk_policy_fingerprint(),
            manifest_sha256=chunk_manifest_sha256(chunks),
            chunks=chunks,
        )
        self.catalog.publish_document_revision(
            document.document_id,
            revision_id=revision.revision_id,
            metadata_revision_id=document.current_metadata_revision_id,
        )
        self.catalog.upsert_generation_revision(
            self.generation.generation_id,
            revision.revision_id,
            chunk_set.chunk_set_id,
            state="ready",
            expected_chunk_count=len(chunks),
            manifest_sha256=chunk_manifest_sha256(chunks),
        )
        points = []
        overrides = vector_overrides or {}
        for chunk in chunks:
            piece = parsed.normalized_text[chunk.char_start:chunk.char_end]
            assert sha256_text(piece) == chunk.text_sha256
            vector = overrides.get(chunk.ordinal) or [
                float(value) for value in self.embeddings.vector_for(piece)
            ]
            points.append(
                VectorPoint(
                    point_id=point_id_for(
                        self.generation.generation_id,
                        chunk_set.chunk_set_id,
                        chunk.ordinal,
                        chunk.text_sha256,
                    ),
                    vector=vector,
                    payload={
                        PAYLOAD_GENERATION_ID: self.generation.generation_id,
                        PAYLOAD_DOCUMENT_ID: document.document_id,
                        PAYLOAD_REVISION_ID: revision.revision_id,
                        PAYLOAD_CHUNK_SET_ID: chunk_set.chunk_set_id,
                        PAYLOAD_ORDINAL: chunk.ordinal,
                        PAYLOAD_OWNER_ID: owner_id,
                        PAYLOAD_REGION: chunk.region,
                        PAYLOAD_TEXT_SHA256: chunk.text_sha256,
                    },
                )
            )
        self.vectors.upsert(name=self.collection, points=points)
        handle = DocumentHandle(
            document_id=document.document_id,
            revision_id=revision.revision_id,
            metadata_revision_id=document.current_metadata_revision_id,
            chunk_set_id=chunk_set.chunk_set_id,
            title=title,
            normalized_text=parsed.normalized_text,
            chunks=list(self.catalog.list_chunks(chunk_set.chunk_set_id)),
        )
        self.documents[handle.document_id] = handle
        return handle

    # ------------------------------------------------------------------ 范围

    def selection(
        self,
        *documents: DocumentHandle,
        grade_id: str = "senior-1",
        subject_id: str = "math",
        edition_id: str = "renjiao-a",
        document_ids: list[str] | None = None,
    ) -> TextbookSelection:
        if document_ids is None:
            handles = documents or tuple(self.documents.values())
            document_ids = [handle.document_id for handle in handles]
        return TextbookSelection(
            gradeId=grade_id,
            subjectId=subject_id,
            editionId=edition_id,
            documentIds=list(document_ids),
        )

    def snapshot(self, *documents: DocumentHandle, **kwargs) -> ScopeSnapshot:
        return resolve_scope(self.catalog, self.selection(*documents, **kwargs))

    def save_teaching_settings(self, selection: TextbookSelection) -> None:
        record = self.catalog.get_teaching_settings()
        self.catalog.set_teaching_settings(
            selection_json=selection.model_dump(), expected_revision=record.revision
        )

    # ------------------------------------------------------------------ 服务

    def make_service(self, **overrides) -> RagV2Service:
        arguments = {
            "catalog": self.catalog,
            "retrieval": self.retriever,
            "summarizer": self.summarizer if self.summarizer is not None else FakeSummarizer(),
            "explainer": self.explainer,
        }
        arguments.update(overrides)
        return RagV2Service(**arguments)


def long_body(topic: str, *, paragraphs: int = 24, sentences: int = 5) -> str:
    """足够长的正文：保证被切成多个块，便于断言邻块扩展与预算。"""
    blocks = []
    for index in range(paragraphs):
        sentence = f"{topic}的第{index}条说明用于构成足够长的正文，便于分块与邻块扩展。"
        blocks.append(f"{topic}要点{index}：" + "".join([sentence] * sentences))
    return "\n\n".join(blocks)


def textbook_text(topic: str = "集合", *, paragraphs: int = 24) -> str:
    """单章正文 + 末尾习题区：正文块与习题块在文本上相邻但区不同。"""
    return (
        f"# 第一章 {topic}\n\n{long_body(topic, paragraphs=paragraphs)}"
        "\n\n## 练习 1.1\n\n1. 求并集。\n2. 求交集。\n"
    )


def multi_chapter_text(chapters: tuple[str, ...] = ("集合", "函数")) -> str:
    """多章正文 + 末尾习题区：用于断言邻块扩展不跨章节。"""
    blocks = [
        f"# 第{index + 1}章 {name}\n\n{long_body(name, paragraphs=14)}"
        for index, name in enumerate(chapters)
    ]
    return "\n\n".join(blocks) + "\n\n## 练习 1.1\n\n1. 求并集。\n"


def sample_text(*, title: str = "集合", sentences: int = 40) -> str:
    """兼容旧调用签名的默认教材正文（长正文 + 习题区）。"""
    return textbook_text(title, paragraphs=max(8, sentences // 4))


__all__ = [
    "DIGEST",
    "DIMENSIONS",
    "MODEL",
    "DocumentHandle",
    "EmptyRetrieval",
    "FakeEmbeddings",
    "FakeExplainer",
    "FakeSummarizer",
    "RagEnv",
    "RecordingRetrieval",
    "RecordingVectorStore",
    "ScriptedVectorStore",
    "deterministic_vector",
    "long_body",
    "multi_chapter_text",
    "sample_text",
    "textbook_text",
]
