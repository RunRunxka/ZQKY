"""Explicit bridge for the older one-shot contract; streaming keeps richer states."""

import hashlib
import uuid
from contextlib import suppress

from app.contracts.rag_adapter import (
    RagAdapterUnavailable, RagContractError, RagQuery, validate_answer_payload,
)
from app.schemas.rag import RagStreamRequest
from app.core.exceptions import AppError
from app.services.rag_presenter import render_result


class LocalRagAdapter:
    def __init__(self, service):
        self.service = service

    async def query(self, request: RagQuery, *, requestId: str):
        if request.courseScope or request.maxEvidence != 5:
            raise RagContractError("当前教材运行时不接受范围或证据数覆盖，不能静默忽略。")
        turn = self.service.start(RagStreamRequest(
            requestId=requestId, sessionId="adapter-" + uuid.uuid4().hex,
            turnId=uuid.uuid4().hex, question=request.question,
        ))
        try:
            async for event in self.service.events(turn):
                if event is None:
                    continue
                if event["event"] == "error":
                    raise RagAdapterUnavailable(event["data"]["message"])
                if event["event"] != "rag.result":
                    continue
                result = event["data"]["result"]
                if result["status"] != "ok":
                    # In particular uncertain != no_evidence. Preserve that difference
                    # by rejecting this lossy old interface instead of coercing status.
                    raise RagContractError(
                        "旧 RagAnswer 无法表达 " + result["status"] + "；请使用 RAG 流式结果与澄清接口。"
                    )
                evidence, citations = [], []
                for item in result["evidence"]:
                    evidence.append({
                        "evidenceId": item["citation_id"], "sourceType": "textbook",
                        "sourceId": item["file"], "sourceName": item["book"],
                        "charStart": item["char_span"][0], "charEnd": item["char_span"][1],
                        "lineStart": item["line_span"][0], "lineEnd": item["line_span"][1],
                        "text": item["text"],
                    })
                for item in result["citations"]:
                    citations.append({
                        "evidenceId": item["citation_id"], "fileId": item["file"],
                        "fileFingerprint": item["source_sha256"],
                        "charStart": item["char_span"][0], "charEnd": item["char_span"][1],
                        "lineStart": item["line_span"][0], "lineEnd": item["line_span"][1],
                        "textHash": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                    })
                return validate_answer_payload({
                    "status": "ok", "answer": render_result(result), "evidence": evidence,
                    "citations": citations, "warnings": ["人工教学质量验收尚未完成。"],
                })
            raise RagAdapterUnavailable("本地教材查询未返回结果。")
        finally:
            # Expiry may already have removed the bounded session. Do not replace
            # the actual query error with a cleanup-only "turn expired" error.
            with suppress(AppError):
                self.service.cancel(turn.session_id, turn.turn_id)
