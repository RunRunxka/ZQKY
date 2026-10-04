"""Independent R19 audit: real retrieval, only the RAG service clock replaced."""
from __future__ import annotations

import atexit
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

_temporary = tempfile.TemporaryDirectory(prefix="zqky-v00-clock-audit-")
atexit.register(_temporary.cleanup)
os.environ["ZQKY_DATA_DIR"] = str(Path(_temporary.name) / "data")
os.environ["ZQKY_ENV"] = "test"
os.environ.pop("ZQKY_CREDENTIALS_FILE", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "apps" / "api"))

import pytest
import app.services.rag_v2.service as rag_module
from app.core.exceptions import AppError
from app.services.rag_v2.requests import RagStreamRequestV2
from tests.test_rag_v2_support import FakeSummarizer, RagEnv, RecordingRetrieval, sample_text


class Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value


@pytest.mark.asyncio
@pytest.mark.parametrize("expired_at", [0.05, 0.07], ids=["exact-boundary", "original-70ms"])
async def test_r19_capacity_before_expiry_then_expired_restart(tmp_path, monkeypatch, expired_at):
    clock = Clock()
    real_monotonic = time.monotonic
    monkeypatch.setattr(rag_module, "time", SimpleNamespace(monotonic=clock.now))
    assert time.monotonic is real_monotonic  # shared time/asyncio clocks must stay real
    env = RagEnv(tmp_path, summarizer=FakeSummarizer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    retrieval = RecordingRetrieval(env.retriever)
    service = env.make_service(retrieval=retrieval, max_turns=1, ttl=0.05)
    body = RagStreamRequestV2(requestId="r19", sessionId="r19-session", turnId="r19-first",
        question="集合的表示方法", scope={"kind": "selection", "selection": env.selection()}, afterEventId=0)
    try:
        turn = service.start(body)
        frames = []
        async with asyncio.timeout(15):
            async for event in service.events(turn, 0):
                if event:
                    frames.append(event)
                    assert event["event"] != "error", event
                    if event["event"] == "wait-user":
                        break
        assert frames[-1]["event"] == "wait-user" and turn.state == "waiting"
        assert len(retrieval.calls) == 1
        assert service.ttl == 0.05 and turn.expires_at == 0.05
        # Real blocking retrieval is finished; wall time does not determine logical TTL.
        for unexpired_at in (0.0, 0.049):
            clock.value = unexpired_at
            assert service.start(body) is turn
            with pytest.raises(AppError) as capacity:
                service.start(body.model_copy(update={"turnId": "r19-second"}))
            assert capacity.value.code == "RAG_CAPACITY" and capacity.value.status_code == 429
            assert len(service.turns) == 1 and len(retrieval.calls) == 1
        loop_before = asyncio.get_running_loop().time()
        await asyncio.sleep(0.03)  # Windows monotonic resolution can exceed 3ms
        assert asyncio.get_running_loop().time() > loop_before
        clock.value = expired_at
        for after_id in (1, 0):
            with pytest.raises(AppError) as expired:
                service.start(body.model_copy(update={"afterEventId": after_id}))
            assert expired.value.code == "RAG_TURN_EXPIRED" and expired.value.status_code == 410
        assert len(service.turns) == 0 and len(service.retired) <= 4
        assert turn.terminal and turn.cancel.is_set()
        assert len(retrieval.calls) == 1  # no invisible old-turn model/retrieval replay
        assert service.start(body.model_copy(update={"turnId": "r19-second"})).turn_id == "r19-second"
        print({"expiry": expired_at, "ttl": service.ttl, "capacity_before": True,
               "expired_410": True, "original_retrieval_calls": len(retrieval.calls)})
    finally:
        await service.close()
    restarted = env.make_service()
    try:
        with pytest.raises(AppError) as expired:
            restarted.start(body.model_copy(update={"afterEventId": 3}))
        assert expired.value.code == "RAG_TURN_EXPIRED" and expired.value.status_code == 410
    finally:
        await restarted.close()
