"""B1-RAG-ANSWER 验收回归：Q1 单一正文 / Q3 有界窗口与可解释状态 / Q4 首答长度 / Q5 引用准入。

首败证据（同一批修复前，探针与输出见 ``_work/rag-quality-v1/B1-RAG-ANSWER/``）：

- Q3：823 码点命中沿同章无上限扩张成 45,577 码点 → 合并结果超预算被**整条丢弃** →
  最终 ``evidence_items = 0``，服务层只能报"没有找到教材依据"；
- Q4：替身模型返回 100 个知识点（正文 6,490 码点）被原样接受；
- Q5：引用"被预算排除、不在提示词里"的 evidenceId 的知识点被接受；
- Q1：``render_result`` 正文同时包含知识点与 ``> `` 原文块，并暴露 ``ev-…`` 长标识。

本文件只注入替身（Embedding / 向量库 / 本地概括 / 聊天模型），目录、修订、分块、原文与
定位都是真实 B0/B1 产物，全部在 ``tmp_path`` 内；不读正式 ``.env``、不写正式 ``.local-data``。
"""

from __future__ import annotations

import json as jsonlib

import pytest

from app.services.text_projection import TEXT_PROJECTION_VERSION
from app.core.rag_budget import (
    EVIDENCE_PROMPT_MAX_CHARS,
    EVIDENCE_SINGLE_CLEANED_MAX_CHARS,
    EVIDENCE_SINGLE_RAW_MAX_CHARS,
    EVIDENCE_TOTAL_RAW_MAX_CHARS,
    FIRST_ANSWER_EVIDENCE_MAX_ITEMS,
    SUMMARY_MAX_POINT_CHARS,
    SUMMARY_MAX_POINTS,
    SUMMARY_MAX_TOTAL_CHARS,
)
from app.providers.embeddings.fingerprint import canonical_json
from app.repositories.textbook_catalog.records import ChunkInput
from app.repositories.vector_store import (
    PAYLOAD_CHUNK_SET_ID,
    PAYLOAD_DOCUMENT_ID,
    PAYLOAD_GENERATION_ID,
    PAYLOAD_ORDINAL,
    PAYLOAD_OWNER_ID,
    PAYLOAD_REGION,
    PAYLOAD_REVISION_ID,
    PAYLOAD_TEXT_SHA256,
    VectorPoint,
    point_id_for,
)
from app.schemas.rag_v2 import RagPoint, RagResultV2
from app.services.document_parsing import (
    PARSER_VERSION,
    chunk_manifest_sha256,
    chunk_policy_fingerprint,
    parse_document,
    source_map_payload,
)
from app.services.rag_v2.evidence import evidence_id, select_evidence
from app.services.rag_v2.presenter import body_char_count, reference_labels, render_result
from app.services.rag_v2.requests import RagStreamRequestV2
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from app.services.rag_v2.summary import KnowledgeSummarizer, pack_evidence, prompt_char_budget
from app.services.textbook_ingest.blobs import sha256_text
from tests.test_rag_v2_explain import StubProvider, handle
from tests.summary_support import SummaryWire
from tests.test_rag_v2_support import FakeSummarizer, RagEnv, ScriptedVectorStore, textbook_text

IMAGE_LINE = "![加速度与力关系图](images/a1b2c3d4e5f6.png)"
#: 空 alt 的图片节点：清洗后不留任何说明文字（仅历史索引代可能留下这种"纯图块"）
EMPTY_IMAGE_LINE = "![](images/aaaaaaaaaaaaaaaa.png)"
FORMULA_BODY = "集合的 $$A\\cup B$$ 运算与 emoji 🙂 说明。\n\n"


def summarizer_with(replies: list[dict], **kwargs) -> tuple[KnowledgeSummarizer, SummaryWire]:
    """脚本化概括上游：按顺序返回给定 payload，并记录每次 ``(path, body)``。

    返回 ``(summarizer, wire)``；``wire.requests`` 与旧的假 client 形状一致。
    """
    wire = SummaryWire(replies=list(replies), **kwargs)
    return wire.summarizer(), wire


def candidate_for(chunk, document, *, score: float = 0.5) -> Candidate:
    return Candidate(
        chunk_set_id=document.chunk_set_id,
        ordinal=chunk.ordinal,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        region=chunk.region,
        chapter_path=tuple(chunk.chapter_path),
        dense_rank=1,
        lexical_rank=None,
        fused_score=score,
        document_revision_id=document.revision_id,
    )


def stream_request(
    env: RagEnv,
    *,
    question: str = "集合的表示方法",
    turn: str = "turn-1",
    document_ids: list[str] | None = None,
) -> RagStreamRequestV2:
    return RagStreamRequestV2(
        requestId="request-1",
        sessionId="session-1",
        turnId=turn,
        question=question,
        scope={"kind": "frozen", "snapshot": env.snapshot(document_ids=document_ids)},
        afterEventId=0,
    )


async def drain(service, turn, *, until: str | None = None):
    frames = []
    async for event in service.events(turn, 0):
        if event is None:
            continue
        frames.append(event)
        if until is not None and event["event"] == until:
            break
        if event["event"] in ("message.end", "error"):
            break
    return frames


def add_legacy_image_only_chunk(env: RagEnv, *, title: str = "历史纯图册"):
    """历史索引代遗留现场：一个**清洗后为空**的图片块（新分块清单会排除它）。

    这条路径只能由"图片块没有被排除"的旧 chunk_set 产生，用于验证
    ``uncertain / EVIDENCE_TEXT_EMPTY`` 状态语义（有命中但清洗后没有可读文本）。
    """
    text = "# 第一章 集合\n\n正文说明。\n\n" + EMPTY_IMAGE_LINE + "\n"
    path = env.tmp_path / "legacy-image.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_document(path=path, file_name="legacy-image.md")
    normalized = parsed.normalized_text
    normalized_blob = env.blobs.write_staged_bytes(normalized.encode("utf-8"))
    env.blobs.seal(area="normalized", blob_id=normalized_blob)
    source_map_blob = env.blobs.write_staged_bytes(
        canonical_json(source_map_payload(parsed)).encode("utf-8")
    )
    env.blobs.seal(area="normalized", blob_id=source_map_blob)
    original_blob = env.blobs.write_staged_bytes(path.read_bytes())
    env.blobs.seal(area="blobs", blob_id=original_blob)

    document = env.catalog.create_document(
        owner_id="system",
        title=title,
        stage_id="senior",
        grade_ids=["senior-1"],
        subject_id="math",
        edition_id="renjiao-a",
        library_ids=[env.library.library_id],
    )
    revision = env.catalog.create_document_revision(
        document.document_id,
        original_file_sha256=original_blob,
        normalized_text_sha256=sha256_text(normalized),
        parser_version=PARSER_VERSION,
        original_blob_id=original_blob,
        normalized_blob_id=normalized_blob,
        source_map_blob_id=source_map_blob,
        char_count=len(normalized),
    )
    start = normalized.index("![")
    image_piece = normalized[start:]
    chunk = ChunkInput(
        ordinal=0,
        char_start=start,
        char_end=len(normalized),
        region="body",
        chapter_path=("第一章 集合",),
        text_sha256=sha256_text(image_piece),
    )
    manifest = chunk_manifest_sha256([chunk])
    chunk_set = env.catalog.create_chunk_set(
        revision.revision_id,
        policy_fingerprint=chunk_policy_fingerprint(),
        manifest_sha256=manifest,
        chunks=[chunk],
    )
    env.catalog.publish_document_revision(
        document.document_id,
        revision_id=revision.revision_id,
        metadata_revision_id=document.current_metadata_revision_id,
    )
    env.catalog.upsert_generation_revision(
        env.generation.generation_id,
        revision.revision_id,
        chunk_set.chunk_set_id,
        state="ready",
        expected_chunk_count=1,
        manifest_sha256=manifest,
    )
    env.vectors.upsert(
        name=env.collection,
        points=[
            VectorPoint(
                point_id=point_id_for(
                    env.generation.generation_id, chunk_set.chunk_set_id, 0, chunk.text_sha256
                ),
                vector=env.embeddings.vector_for(image_piece),
                payload={
                    PAYLOAD_GENERATION_ID: env.generation.generation_id,
                    PAYLOAD_DOCUMENT_ID: document.document_id,
                    PAYLOAD_REVISION_ID: revision.revision_id,
                    PAYLOAD_CHUNK_SET_ID: chunk_set.chunk_set_id,
                    PAYLOAD_ORDINAL: 0,
                    PAYLOAD_OWNER_ID: "system",
                    PAYLOAD_REGION: "body",
                    PAYLOAD_TEXT_SHA256: chunk.text_sha256,
                },
            )
        ],
    )
    return document, revision, chunk_set


# --------------------------------------------------------------------- Q3 回归

@pytest.mark.asyncio
async def test_q3_long_chapter_single_hit_returns_bounded_evidence_not_no_evidence(tmp_path):
    """长章节单个命中：证据有界（≤6 条 / 单条 ≤6000 / 总量 ≤16000）且绝不误报无依据。"""
    store = ScriptedVectorStore([])
    env = RagEnv(tmp_path, vectors=store, summarizer=FakeSummarizer())
    document = env.add_document(title="长章节册", text=textbook_text("集合", paragraphs=280))
    scope = verify_scope(env.catalog, env.snapshot(document))
    body = document.body_chunks()
    assert len(body) >= 10, "同章应有不少于 10 个可合并块（旧实现据此扩成整章）"
    middle = body[len(body) // 2]
    store.hits = [(document.chunk_set_id, middle.ordinal, document.revision_id, "p-middle")]
    # 题面无中文词元：词法路不命中，构造出真正的"单个命中"
    service = env.make_service()
    try:
        turn = service.start(stream_request(env, question="SINGLEHITPROBE"))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "ok", "有命中绝不能返回 no_evidence"
        assert result["reasonCode"] is None
        assert 1 <= len(result["evidence"]) <= FIRST_ANSWER_EVIDENCE_MAX_ITEMS
        assert sum(len(item["text"]) for item in result["evidence"]) <= EVIDENCE_TOTAL_RAW_MAX_CHARS
        for item in result["evidence"]:
            assert len(item["text"]) <= EVIDENCE_SINGLE_RAW_MAX_CHARS
            assert len(item["readable"]["text"]) <= EVIDENCE_SINGLE_CLEANED_MAX_CHARS
            assert item["readable"]["version"] == TEXT_PROJECTION_VERSION
            assert item["text"] == document.normalized_text[item["charStart"] : item["charEnd"]]
        # 未被扩成整章：命中块附近的窗口远小于全书正文
        assert len(result["evidence"]) == 1
        assert len(result["evidence"][0]["text"]) < len(document.normalized_text) // 2
        # 首答正文只有知识点，不含原文块与长 ev-id
        text = frames[2]["data"]["text"]
        assert "> " not in text and "教材原文摘录" not in text
        assert result["evidence"][0]["evidenceId"] not in text
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_q3_over_long_protected_unit_is_partial_with_reason_not_missing_evidence(tmp_path):
    """命中含超长公式：partial + EVIDENCE_UNIT_TOO_LARGE + locator，不报"没有找到教材依据"。"""
    store = ScriptedVectorStore([])
    env = RagEnv(tmp_path, vectors=store, summarizer=FakeSummarizer())
    formula = "$$\n" + "x_{1}+y_{2}=z_{3};" * 400 + "\n$$"
    document = env.add_document(
        title="公式超长册",
        text=f"# 第一章 向量\n\n向量公式：\n\n{formula}\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    body = document.body_chunks()
    hit = max(body, key=lambda chunk: chunk.char_end - chunk.char_start)
    assert hit.char_end - hit.char_start > EVIDENCE_SINGLE_RAW_MAX_CHARS
    store.hits = [(document.chunk_set_id, hit.ordinal, document.revision_id, "p-formula")]
    service = env.make_service()
    try:
        # 题面无中文词元：词法路不命中，只保留这一个超长公式块
        turn = service.start(stream_request(env, question="OVERLONGFORMULAPROBE"))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "partial"
        assert result["reasonCode"] == "EVIDENCE_UNIT_TOO_LARGE"
        assert result["evidence"] == [] and result["points"] == []
        assert result["reason"] and "超长公式" in result["reason"]
        text = frames[2]["data"]["text"]
        assert "没有找到足够依据" not in text
        assert "超长公式" in text
        assert env.summarizer.calls == [], "没有可用证据时不得调用概括模型"
    finally:
        await service.close()


# --------------------------------------------------------------------- Q4 回归

def test_q4_hundred_points_are_capped_and_over_long_point_is_rejected(tmp_path):
    """替身返回 100 个知识点：只保留 ≤3 条 / 合计 ≤250 码点；超长单点整点拒绝。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    evidence = list(
        select_evidence(
            catalog=env.catalog,
            scope=scope,
            candidates=[candidate_for(chunk, document)],
        ).evidence
    )
    assert evidence
    known = evidence[0].evidenceId
    long_point = {"title": "超长单点", "summary": "长" * (SUMMARY_MAX_POINT_CHARS + 5), "evidenceIds": [known]}
    many = [
        {"title": f"知识点{index}", "summary": "说明" * 30, "evidenceIds": [known]}
        for index in range(100)
    ]
    summarizer, client = summarizer_with([{"points": [long_point, *many]}, {"points": [long_point, *many]}])
    outcome = summarizer.summarize(question="集合的表示方法", evidence=evidence)

    assert len(outcome.points) <= SUMMARY_MAX_POINTS
    body_chars = sum(len(point.title) + len(point.summary) for point in outcome.points)
    assert body_chars <= SUMMARY_MAX_TOTAL_CHARS
    assert all("超长单点" != point.title for point in outcome.points), "超长单点必须整点拒绝"
    assert outcome.reason_code == "SUMMARY_PARTIAL"
    assert outcome.corrected == 1 and len(client.requests) == 2, "最多修正一次，不无限重试"
    assert outcome.admitted_evidence_ids, "必须回报真实准入集合"


@pytest.mark.asyncio
async def test_q4_presentation_body_char_count_matches_points(tmp_path):
    """RagResultV2.presentation 与正文口径一致：bodyCharCount == 知识点正文码点数。"""
    env = RagEnv(tmp_path, summarizer=FakeSummarizer())
    env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    service = env.make_service()
    try:
        turn = service.start(stream_request(env))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        expected = sum(len(point["title"]) + len(point["summary"]) for point in result["points"])
        assert result["presentation"] == {
            "version": "compact-v1",
            "answerStyle": "brief",
            "bodyCharCount": expected,
        }
        assert expected <= SUMMARY_MAX_TOTAL_CHARS
        assert result["points"][0]["title"] in frames[2]["data"]["text"]
    finally:
        await service.close()


# --------------------------------------------------------------------- Q5 回归

def test_q5_excluded_evidence_reference_is_rejected_as_a_whole_point(tmp_path):
    """引用"证据列表内但被预算排除（未进入提示词）"的 id：整点拒绝，且证明用的是 admitted 集合。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    base = list(
        select_evidence(
            catalog=env.catalog,
            scope=scope,
            candidates=[candidate_for(chunk, document)],
        ).evidence
    )[0]
    evidence = [
        base.model_copy(
            update={
                "evidenceId": evidence_id(document.revision_id, index, index + 1),
                "text": base.text + f"（第{index}段补充。）",
                "readable": None if base.readable is None else base.readable.model_copy(
                    update={"text": base.readable.text + f"（第{index}段补充。）"}
                ),
            }
        )
        for index in range(8)
    ]

    budget = prompt_char_budget(4096, 1024)
    pack = pack_evidence(question="集合的表示方法", evidence=evidence, budget_chars=budget)
    admitted = set(pack.admitted_evidence_ids)
    excluded_id = next(item.evidenceId for item in evidence if item.evidenceId not in admitted)
    assert excluded_id in {item.evidenceId for item in evidence}, "被排除的 id 仍在证据列表里"
    assert excluded_id not in pack.prompt and excluded_id not in admitted

    admitted_id = next(iter(admitted))
    proposal = {
        "points": [
            {"title": "合法点", "summary": "引用进入提示词的证据。", "evidenceIds": [admitted_id]},
            {"title": "越界点", "summary": "引用了被预算排除的证据。", "evidenceIds": [excluded_id]},
        ]
    }
    summarizer, client = summarizer_with([proposal, proposal], context_tokens=4096, max_output_tokens=1024)
    outcome = summarizer.summarize(question="集合的表示方法", evidence=evidence)
    assert [point.title for point in outcome.points] == ["合法点"]
    assert outcome.admitted_evidence_ids == pack.admitted_evidence_ids
    assert outcome.reason_code == "SUMMARY_PARTIAL"
    assert outcome.dropped == 1 and "REF_NOT_ADMITTED" in outcome.violation_codes
    # 提示词里只有准入证据：被排除的 id 从未进入模型上下文
    _path, payload = client.requests[0]
    assert excluded_id not in payload["messages"][1]["content"]


@pytest.mark.asyncio
async def test_q5_service_second_check_uses_admitted_set(tmp_path):
    """服务端二次校验同样只认准入集合：替身给出"列表内但未入模"的引用也必须整点拒绝。"""
    env = RagEnv(tmp_path / "ragdata")
    document = env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    admitted_item = list(
        select_evidence(
            catalog=env.catalog, scope=scope, candidates=[candidate_for(chunk, document)]
        ).evidence
    )[0]
    forged = candidate_for(chunk, document)  # 同一块，另一个区间被排除在同一提示词之外
    excluded_id = evidence_id(document.revision_id, chunk.char_start, chunk.char_end - 1)
    assert excluded_id != admitted_item.evidenceId and forged
    env.summarizer = FakeSummarizer(
        points=[
            RagPoint(pointId="pt-ok", title="合法", summary="引用准入证据。", evidenceIds=[admitted_item.evidenceId]),
            RagPoint(pointId="pt-out", title="越界", summary="引用未入模证据。", evidenceIds=[excluded_id]),
        ],
        admitted_evidence_ids=frozenset({admitted_item.evidenceId}),
    )
    service = env.make_service()
    try:
        turn = service.start(stream_request(env))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        titles = [point["title"] for point in result["points"]]
        assert titles == ["合法"], "服务端二次校验必须整点拒绝越界引用"
        assert result["status"] == "partial" and result["reasonCode"] == "SUMMARY_PARTIAL"
        assert all(
            set(point["evidenceIds"]) <= {item["evidenceId"] for item in result["evidence"]}
            for point in result["points"]
        )
    finally:
        await service.close()


# ------------------------------------------------------------------ 修正一次

def test_summary_correction_runs_once_and_accepts_the_second_attempt(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    evidence = list(
        select_evidence(catalog=env.catalog, scope=scope, candidates=[candidate_for(chunk, document)]).evidence
    )
    known = evidence[0].evidenceId
    invalid = {"points": [{"title": "越界", "summary": "未入模引用。", "evidenceIds": ["ev-nope"]}]}
    valid = {"points": [{"title": "并集", "summary": "由所有属于 A 或 B 的元素组成。", "evidenceIds": [known]}]}

    accepted_summarizer, _accepted_wire = summarizer_with([invalid, valid])
    accepted = accepted_summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in accepted.points] == ["并集"]
    assert accepted.reason is None and accepted.reason_code is None
    assert accepted.corrected == 1

    rejected_summarizer, client = summarizer_with([invalid, invalid])
    rejected = rejected_summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert rejected.points == [] and rejected.reason_code == "SUMMARY_INVALID"
    assert len(client.requests) == 2, "两次都非法时不得继续重试"
    assert "未通过原文引用校验" in rejected.reason


# --------------------------------------------------------------------- Q1 presenter

def test_presenter_renders_points_only_without_raw_excerpt_or_long_ids(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(
        title="含公式册",
        text="# 第一章 集合\n\n" + FORMULA_BODY + "并集由所有属于 A 或属于 B 的元素组成。" * 4
        + "\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    evidence = list(
        select_evidence(catalog=env.catalog, scope=scope, candidates=[candidate_for(chunk, document)]).evidence
    )
    item = evidence[0]
    points = [
        RagPoint(pointId="pt-1", title="并集", summary="由所有属于 A 或属于 B 的元素组成。", evidenceIds=[item.evidenceId]),
        RagPoint(pointId="pt-2", title="交集", summary="由同时属于 A 与 B 的元素组成。", evidenceIds=[item.evidenceId]),
    ]
    result = RagResultV2(
        resultId="r1",
        status="ok",
        scopeSnapshot=env.snapshot(document),
        points=points,
        evidence=list(evidence),
        reason=None,
        presentation=None,
    )
    body = render_result(result)
    assert "1. **并集**" in body and "2. **交集**" in body
    assert "[1]" in body
    assert "> " not in body, "正文不得再拼接 > 原文块"
    assert "教材原文摘录" not in body
    assert item.evidenceId not in body, "长 ev-… 标识不得出现在正文"
    assert item.text not in body, "正文不追加教材原文"
    assert "$$A\\cup B$$" not in body
    assert body_char_count(points) == sum(len(p.title) + len(p.summary) for p in points)
    assert reference_labels(result) == {item.evidenceId: 1}

    # no_evidence / partial 的说明保持可读
    no_evidence = result.model_copy(update={"status": "no_evidence", "points": [], "evidence": []})
    text = render_result(no_evidence)
    assert "没有找到" in text and text.strip()
    partial = result.model_copy(update={"status": "partial", "points": [], "reason": "保留教材原文供核对。"})
    partial_text = render_result(partial)
    assert "保留教材原文供核对" in partial_text and "教材依据" in partial_text


# ------------------------------------------------------------------- readable

def test_new_evidence_always_carries_readable_cleaned_projection(tmp_path):
    """每条新证据：readable.version 正确、不含图片 Markdown，text 与封存原文逐字节相同。"""
    env = RagEnv(tmp_path)
    document = env.add_document(
        title="图册",
        text="# 第一章 集合\n\n" + FORMULA_BODY + IMAGE_LINE + "\n\n并集的定义说明。\n\n"
        "## 练习 1.1\n\n1. 求并集。\n",
    )
    scope = verify_scope(env.catalog, env.snapshot(document))
    candidates = [candidate_for(chunk, document) for chunk in document.body_chunks()]
    evidence = list(select_evidence(catalog=env.catalog, scope=scope, candidates=candidates).evidence)
    assert evidence
    for item in evidence:
        assert item.readable is not None and item.readable.version == TEXT_PROJECTION_VERSION
        assert "![" not in item.readable.text
        assert "images/a1b2c3d4e5f6.png" not in item.readable.text
        assert item.text == document.normalized_text[item.charStart : item.charEnd]
    assert any("$$A\\cup B$$" in item.text for item in evidence), "公式逐字保留"
    assert any("加速度与力关系图" in item.readable.text for item in evidence), "有意义的图片说明保留"
    combined_readable = "".join(item.readable.text for item in evidence)
    assert "![" not in combined_readable


# --------------------------------------------------------------------- 详解清洗

@pytest.mark.asyncio
async def test_explain_sends_cleaned_text_and_closes_upstream_on_disconnect(tmp_path):
    """详解：送模型的证据不含图片 Markdown；提前断开仍关闭上游。"""
    env = RagEnv(tmp_path)
    document = env.add_document(
        title="图册",
        text="# 第一章 集合\n\n" + FORMULA_BODY + IMAGE_LINE + "\n\n并集的定义说明。\n\n"
        "## 练习 1.1\n\n1. 求并集。\n",
    )
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    evidence = list(
        select_evidence(catalog=env.catalog, scope=scope, candidates=[candidate_for(chunk, document)]).evidence
    )
    assert evidence and "![" in evidence[0].text, "封存原文切片里确实有图片 Markdown"

    from app.schemas.rag_v2 import EvidenceRef

    item = evidence[0]
    from app.services.rag_v2.evidence import rebuild_evidence_refs

    refs = [
        EvidenceRef(
            evidenceId=item.evidenceId,
            documentRevisionId=item.documentRevisionId,
            normalizedTextSha256=item.normalizedTextSha256,
            charStart=item.charStart,
            charEnd=item.charEnd,
        )
    ]
    rebuilt = rebuild_evidence_refs(catalog=env.catalog, scope=scope, refs=refs)
    from app.services.rag_v2.explain import Explainer, build_explanation_request

    assert rebuilt[0].readable is not None and "![" not in rebuilt[0].readable.text
    from app.schemas.rag_v2 import RagExplainRequest

    body = RagExplainRequest(
        requestId="explain-1",
        sessionId="session-1",
        turnId="turn-1",
        modelProfileId="chat-profile-1",
        originalQuestion="并集是什么？",
        followUp="请结合教材原文讲清并集。",
        scopeSnapshot=env.snapshot(document),
        evidenceRefs=refs,
        history=[],
    )
    messages, _budget = build_explanation_request(
        body=body, evidence=rebuilt, model=handle(StubProvider())
    )
    joined = "\n".join(message.content for message in messages)
    assert "![" not in joined and "images/a1b2c3d4e5f6.png" not in joined
    assert "加速度与力关系图" in joined
    assert "不要把教材原文整段复述" in messages[0].content

    provider = StubProvider(deltas=("第一段。", "第二段。"))
    explainer = Explainer(lambda profile_id: handle(provider, profile_id))
    stream = explainer.explain(body, evidence=rebuilt, model=explainer.freeze_model("chat-profile-1"))
    assert (await stream.__anext__()).text == "第一段。"
    await stream.aclose()
    assert provider.closed == 1, "断开必须关闭上游"


# ----------------------------------------------------------------- 状态映射表

@pytest.mark.asyncio
async def test_status_and_reason_code_mapping_is_explicit(tmp_path):
    """ok / partial / uncertain / no_evidence 四种状态与 reasonCode 的固定映射。"""
    # ok / None
    ok_env = RagEnv(tmp_path / "ok", summarizer=FakeSummarizer())
    ok_env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    ok_service = ok_env.make_service()
    try:
        turn = ok_service.start(stream_request(ok_env))
        frames = await drain(ok_service, turn, until="wait-user")
        assert frames[1]["data"]["result"]["status"] == "ok"
        assert frames[1]["data"]["result"]["reasonCode"] is None
    finally:
        await ok_service.close()

    # partial / EVIDENCE_UNIT_TOO_LARGE
    unit_store = ScriptedVectorStore([])
    unit_env = RagEnv(tmp_path / "unit", vectors=unit_store, summarizer=FakeSummarizer())
    formula = "$$\n" + "x_{1}+y_{2}=z_{3};" * 400 + "\n$$"
    unit_document = unit_env.add_document(
        title="公式册",
        text=f"# 第一章 向量\n\n向量公式：\n\n{formula}\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    unit_hit = max(
        unit_document.body_chunks(), key=lambda chunk: chunk.char_end - chunk.char_start
    )
    unit_store.hits = [
        (unit_document.chunk_set_id, unit_hit.ordinal, unit_document.revision_id, "p-unit")
    ]
    unit_service = unit_env.make_service()
    try:
        turn = unit_service.start(stream_request(unit_env, question="OVERLONGFORMULAPROBE"))
        frames = await drain(unit_service, turn, until="wait-user")
        assert frames[1]["data"]["result"]["status"] == "partial"
        assert frames[1]["data"]["result"]["reasonCode"] == "EVIDENCE_UNIT_TOO_LARGE"
    finally:
        await unit_service.close()

    # partial / SUMMARY_INVALID（概括不可用）
    fail_env = RagEnv(tmp_path / "fail", summarizer=FakeSummarizer(unavailable=True))
    fail_env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    fail_service = fail_env.make_service()
    try:
        turn = fail_service.start(stream_request(fail_env))
        frames = await drain(fail_service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "partial" and result["reasonCode"] == "SUMMARY_INVALID"
        assert result["evidence"], "概括失败必须保留证据"
    finally:
        await fail_service.close()

    # uncertain / EVIDENCE_TEXT_EMPTY（有命中但清洗后没有可读文本）
    # 说明：只用一个候选替身（词法索引在"单块且词元为空"的极端语料上会退化，
    # 那是 retrieval.py 的问题，不属于本卡范围）。
    legacy_env = RagEnv(tmp_path / "legacy", summarizer=FakeSummarizer())
    legacy_document, legacy_revision, legacy_chunk_set = add_legacy_image_only_chunk(legacy_env)
    legacy_chunk = legacy_env.catalog.list_chunks(legacy_chunk_set.chunk_set_id)[0]
    legacy_candidate = Candidate(
        chunk_set_id=legacy_chunk_set.chunk_set_id,
        ordinal=legacy_chunk.ordinal,
        char_start=legacy_chunk.char_start,
        char_end=legacy_chunk.char_end,
        region=legacy_chunk.region,
        chapter_path=tuple(legacy_chunk.chapter_path),
        dense_rank=1,
        lexical_rank=None,
        fused_score=0.5,
        document_revision_id=legacy_revision.revision_id,
    )
    legacy_service = legacy_env.make_service(
        retrieval=FixedCandidateRetrieval(legacy_candidate)
    )
    try:
        turn = legacy_service.start(
            stream_request(
                legacy_env,
                question="ExplainThisFigure",
                document_ids=[legacy_document.document_id],
            )
        )
        frames = await drain(legacy_service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "uncertain"
        assert result["reasonCode"] == "EVIDENCE_TEXT_EMPTY"
        assert result["evidence"] == []
        assert "没有找到足够依据" not in (result["reason"] or "")
        assert "清洗后没有可读文本" in result["reason"]
        assert legacy_env.summarizer.calls == []
    finally:
        await legacy_service.close()

    # no_evidence / NO_MATCH（范围内没有任何文本命中）
    empty_env = RagEnv(tmp_path / "empty", summarizer=FakeSummarizer())
    empty_env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    empty_service = empty_env.make_service(retrieval=NoCandidates())
    try:
        turn = empty_service.start(stream_request(empty_env))
        frames = await drain(empty_service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "no_evidence" and result["reasonCode"] == "NO_MATCH"
        assert "没有找到足够依据" in result["reason"]
    finally:
        await empty_service.close()


class NoCandidates:
    """检索替身：永远没有候选（范围内没有任何文本命中）。"""

    dense_limit, lexical_limit, rrf_k = 50, 50, 60
    vectors = None
    embeddings = None

    def retrieve(self, **kwargs):
        return []


class FixedCandidateRetrieval:
    """检索替身：直接给出指定候选块（绕开词法索引，专注证据/状态语义）。"""

    dense_limit, lexical_limit, rrf_k = 50, 50, 60
    vectors = None
    embeddings = None

    def __init__(self, candidate: Candidate) -> None:
        self.candidate = candidate

    def retrieve(self, **kwargs):
        return [self.candidate]


def test_pack_budget_never_exceeds_first_answer_prompt_limit(tmp_path):
    """打包上限受 EVIDENCE_PROMPT_MAX_CHARS 约束（预算唯一事实来源）。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=textbook_text("集合", paragraphs=12))
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    base = list(
        select_evidence(catalog=env.catalog, scope=scope, candidates=[candidate_for(chunk, document)]).evidence
    )[0]
    evidence = [
        base.model_copy(
            update={
                "evidenceId": f"ev-{index:016d}",
                "text": base.text,
                "readable": None if base.readable is None else base.readable.model_copy(
                    update={"text": base.readable.text}
                ),
            }
        )
        for index in range(6)
    ]
    pack = pack_evidence(
        question="集合的表示方法", evidence=evidence, budget_chars=EVIDENCE_PROMPT_MAX_CHARS
    )
    assert pack.fits and pack.chars <= EVIDENCE_PROMPT_MAX_CHARS
    summarizer, _wire = summarizer_with([{"points": []}])
    assert summarizer.prompt_budget_chars <= EVIDENCE_PROMPT_MAX_CHARS
