"""Bounded local RAG turns. No chat text is logged or persisted by this service.

One dedicated executor owns the engine. Timing out/cancelling a consumer never
releases that worker early: an uninterruptible model call retains its slot until
it actually returns, and its late result is counted and discarded.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import AppError
from app.schemas.rag import RagReplyRequest, RagStreamRequest
from app.services.rag_presenter import public_result, render_result


def _failure(code: str, message: str, status: int = 409) -> AppError:
    return AppError(message, code=code, status_code=status, retryable=code == "RAG_QUEUE_FULL")


@dataclass
class Turn:
    session_id: str
    turn_id: str
    request_id: str
    question: str
    subject: str | None
    expires_at: float
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    events: list[dict] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    state: str = "running"
    round: int = 0
    interaction: dict | None = None
    submissions: dict[str, str] = field(default_factory=dict)
    clarifications: list[str] = field(default_factory=list)
    terminal: bool = False


@dataclass
class Job:
    turn: Turn
    question: str
    deadline: float
    expired: bool = False
    timer: asyncio.Task | None = None


class RagSessionService:
    def __init__(
        self, assets_root: Path, state_root: Path, *,
        runtime_factory: Callable | None = None, probe: Callable | None = None,
        queue_size: int = 4, max_turns: int = 64, ttl: float = 600,
        timeout: float = 180, max_rounds: int = 3,
    ):
        self.assets_root, self.state_root = assets_root, state_root
        self.runtime_factory, self.probe = runtime_factory, probe
        self.ttl, self.timeout, self.max_rounds = ttl, timeout, max_rounds
        self.max_turns = max_turns
        self.queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=queue_size)
        self.turns: dict[tuple[str, str], Turn] = {}
        self.owners: dict[str, str] = {}
        self.retired: OrderedDict[str, None] = OrderedDict()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="textbook-rag")
        self.runtime = None
        self.worker: asyncio.Task | None = None
        self.janitor: asyncio.Task | None = None
        self.closed = False
        self.active: Job | None = None
        self.discarded_late_results = 0
        self._probe_task: asyncio.Task | None = None
        self._status_cache: tuple[float, dict] | None = None

    def _start_tasks(self) -> None:
        if self.closed:
            raise _failure("RAG_UNAVAILABLE", "教材服务已停止。", 503)
        if self.worker is None:
            self.worker = asyncio.create_task(self._work())
            self.janitor = asyncio.create_task(self._expire_turns())

    def _runtime(self):
        if self.runtime is None:
            factory = self.runtime_factory
            if factory is None:
                from app.services.rag_engine.runtime import LocalRagRuntime
                factory = LocalRagRuntime
            self.runtime = factory(assets_root=self.assets_root, state_root=self.state_root)
        return self.runtime

    def _locate(self, job: Job) -> dict:
        if job.expired or job.turn.cancel.is_set():
            return {"status": "cancelled"}
        return self._runtime().locate(
            job.question, subject=job.turn.subject, cancel_token=job.turn.cancel,
        )

    async def status(self) -> dict:
        if self._status_cache and time.monotonic() - self._status_cache[0] < 10:
            return dict(self._status_cache[1])
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(asyncio.to_thread(self._probe))
        try:
            status = await asyncio.wait_for(asyncio.shield(self._probe_task), timeout=10)
        except TimeoutError:
            status = {"available": False, "detail": "本地教材依赖检查尚未完成，请稍后重试。"}
        except Exception:
            status = {"available": False, "detail": "本地教材资产或模型服务不可用，请检查安装。"}
        result = {
            "available": bool(status.get("available")),
            "detail": status.get("detail", "本地教材运行时状态未知。"),
            "humanQuality": "not_run", "localOnly": True,
            "limits": {"concurrency": 1, "queue": self.queue.maxsize, "maxRounds": self.max_rounds,
                       "turnTtlSeconds": self.ttl, "timeoutSeconds": self.timeout},
        }
        self._status_cache = (time.monotonic(), result)
        return dict(result)

    def _probe(self) -> dict:
        if self.probe is not None:
            return self.probe(self.assets_root)
        from app.services.rag_engine.runtime import probe_runtime
        return probe_runtime(self.assets_root)

    def _emit(self, turn: Turn, name: str, **payload) -> None:
        if turn.terminal:
            return
        turn.events.append({
            "id": len(turn.events) + 1, "event": name,
            "data": {"requestId": turn.request_id, "sessionId": turn.session_id,
                     "turnId": turn.turn_id, "messageId": turn.message_id, **payload},
        })
        turn.changed.set()

    def _end(self, turn: Turn, *, code: str | None = None, message: str = "", retryable: bool = False) -> None:
        if turn.terminal:
            return
        if code:
            self._emit(turn, "error", code=code, message=message, retryable=retryable)
        else:
            self._emit(turn, "message.end", finishReason="stop")
        turn.terminal = True
        turn.state = "failed" if code else "complete"
        turn.interaction = None
        turn.changed.set()

    def _lookup(self, session_id: str, turn_id: str) -> Turn:
        self._prune()
        if self.owners.get(turn_id) not in (None, session_id):
            raise _failure("RAG_SESSION_MISMATCH", "该轮不属于当前会话。", 403)
        turn = self.turns.get((session_id, turn_id))
        if turn is None:
            raise _failure("RAG_TURN_EXPIRED", "该轮已过期或服务已重启，请重新发送题目。", 410)
        return turn

    def _prune(self) -> None:
        now = time.monotonic()
        for key, turn in list(self.turns.items()):
            if now >= turn.expires_at:
                turn.cancel.set()
                self._end(turn, code="RAG_TURN_EXPIRED", message="本轮已过期，请重新发送题目。")
                del self.turns[key]
                self.owners.pop(turn.turn_id, None)
                self.retired[turn.turn_id] = None
                while len(self.retired) > self.max_turns * 4:
                    self.retired.popitem(last=False)

    async def _expire_turns(self) -> None:
        while True:
            await asyncio.sleep(min(15, self.ttl))
            self._prune()

            prune_cache = getattr(self.runtime, "prune_cache", None)
            if prune_cache is not None:
                prune_cache()

    def start(self, body: RagStreamRequest) -> Turn:
        self._start_tasks()
        self._prune()
        if body.turnId in self.retired:
            raise _failure("RAG_TURN_EXPIRED", "该轮已过期，请使用新轮次重新发送题目。", 410)
        if self.owners.get(body.turnId) not in (None, body.sessionId):
            raise _failure("RAG_SESSION_MISMATCH", "该轮不属于当前会话。", 403)
        key = (body.sessionId, body.turnId)
        if key in self.turns:
            turn = self.turns[key]
            if turn.question != body.question or turn.subject != body.subject:
                raise _failure("RAG_TURN_CONFLICT", "同一轮不能替换原题或学科。")
            if body.afterEventId > len(turn.events):
                raise _failure("RAG_EVENT_CONFLICT", "恢复事件位置超出本轮范围。")
            return turn
        if body.afterEventId:
            raise _failure("RAG_TURN_EXPIRED", "该轮已过期或服务已重启，请重新发送题目。", 410)
        if len(self.turns) >= self.max_turns:
            raise _failure("RAG_CAPACITY", "教材会话容量已满，请等待旧轮次过期后重试。", 429)
        if self.queue.full():
            raise _failure("RAG_QUEUE_FULL", "本地教材推理队列已满，请稍后重试。", 429)
        turn = Turn(body.sessionId, body.turnId, body.requestId, body.question,
                    body.subject, time.monotonic() + self.ttl)
        self.turns[key] = turn
        self.owners[body.turnId] = body.sessionId
        self._emit(turn, "message.start")
        self._enqueue(turn, body.question)
        return turn

    def _enqueue(self, turn: Turn, question: str) -> None:
        job = Job(turn, question, time.monotonic() + self.timeout)
        self.queue.put_nowait(job)
        job.timer = asyncio.create_task(self._deadline(job))
        turn.state = "running"

    async def _deadline(self, job: Job) -> None:
        await asyncio.sleep(max(0, job.deadline - time.monotonic()))
        job.expired = True
        job.turn.cancel.set()
        self._end(job.turn, code="RAG_TIMEOUT", message="本地教材查询超时，请稍后重新发送。", retryable=True)

    async def _work(self) -> None:
        while True:
            job = await self.queue.get()
            self.active = job
            try:
                if job.expired or job.turn.terminal:
                    continue
                raw = await asyncio.get_running_loop().run_in_executor(self.executor, self._locate, job)
                if time.monotonic() >= job.deadline and not job.turn.terminal:
                    job.expired = True
                    job.turn.cancel.set()
                    self._end(job.turn, code="RAG_TIMEOUT", message="本地教材查询超时，请稍后重新发送。", retryable=True)
                if job.expired or job.turn.cancel.is_set() or job.turn.terminal or self.closed:
                    self.discarded_late_results += 1
                    continue
                result = public_result(raw)
                turn = job.turn
                turn.round += 1
                self._emit(turn, "rag.result", result=result)
                self._emit(turn, "text.delta", text=render_result(result))
                if turn.round >= self.max_rounds:
                    self._end(turn)
                else:
                    turn.state = "waiting"
                    turn.interaction = self._interaction(result)
                    self._emit(turn, "wait-user", interaction=turn.interaction)
            except asyncio.CancelledError:
                raise
            except AppError as exc:
                if job.turn.terminal:
                    self.discarded_late_results += 1
                else:
                    self._end(job.turn, code=exc.code, message=str(exc), retryable=exc.retryable)
            except Exception:
                if job.turn.terminal:
                    self.discarded_late_results += 1
                else:
                    self._end(job.turn, code="RAG_MODEL_UNAVAILABLE",
                              message="本地教材模型或索引执行失败，请检查本机服务后重试。", retryable=True)
            finally:
                if job.timer:
                    job.timer.cancel()
                self.active = None
                self.queue.task_done()

    @staticmethod
    def _interaction(result: dict) -> dict:
        missing = result["status"] not in {"ok", "partial"}
        return {
            "interactionId": uuid.uuid4().hex, "status": "waiting",
            "intro": "教材证据不足，请补充后重新定位。" if missing else "可继续细讲、纠正定位，或跳过结束本轮。",
            "questions": [{
                "questionId": "textbook-follow-up", "header": "补充题目信息" if missing else "继续讲解",
                "prompt": "请补充完整题干、学科、教材章节或你最困惑的步骤。" if missing else "定位是否符合题意？你希望进一步理解哪一步？",
                "options": [] if missing else [{"label": "细讲解题思路"}, {"label": "重新核对知识点"}],
                "multiSelect": False, "allowFreeText": True,
                "placeholder": "填写补充信息；不需要继续时可跳过",
            }],
        }

    def reply(self, body: RagReplyRequest) -> dict:
        turn = self._lookup(body.sessionId, body.turnId)
        if turn.cancel.is_set():
            raise _failure("RAG_TURN_CLOSED", "该轮已取消或超时，不能再次提交。")
        canonical = json.dumps({"interactionId": body.interactionId,
                                "answers": [answer.model_dump() for answer in body.answers]},
                               sort_keys=True, ensure_ascii=False)
        if body.submissionId in turn.submissions:
            if turn.submissions[body.submissionId] != canonical:
                raise _failure("RAG_SUBMISSION_CONFLICT", "同一提交标识不能替换答案。")
            return {"accepted": True}
        if turn.terminal or turn.state != "waiting" or turn.interaction is None:
            raise _failure("RAG_TURN_CLOSED", "该轮当前不接受回答，请检查轮次是否已结束。")
        if body.interactionId != turn.interaction["interactionId"]:
            raise _failure("RAG_INTERACTION_EXPIRED", "该追问卡已失效，请使用当前追问卡。")
        questions = {item["questionId"]: item for item in turn.interaction["questions"]}
        if len(body.answers) != len(questions) or {a.questionId for a in body.answers} != set(questions):
            raise _failure("RAG_INVALID_ANSWERS", "回答必须逐项对应当前追问卡。", 422)
        supplements = []
        for answer in body.answers:
            question = questions[answer.questionId]
            labels = {item["label"] for item in question["options"]}
            if len(answer.labels) > 1 or not set(answer.labels).issubset(labels):
                raise _failure("RAG_INVALID_ANSWERS", "回答选项不属于当前追问卡。", 422)
            if answer.skipped and (answer.labels or answer.freeText.strip()):
                raise _failure("RAG_INVALID_ANSWERS", "跳过的回答不能同时包含补充内容。", 422)
            if not answer.skipped:
                text = "；".join([*answer.labels, answer.freeText.strip()]).strip("；")
                if text:
                    supplements.append(text)
        if supplements and self.queue.full():
            raise _failure("RAG_QUEUE_FULL", "本地教材推理队列已满，请稍后重试。", 429)
        combined = ""
        if supplements:
            combined = "原始题目：\n" + turn.question + "\n\n用户补充（用于纠正题意与讲解重点）：\n" + "\n".join([*turn.clarifications, *supplements])
            if len(combined) > 4000:
                raise _failure("RAG_INPUT_TOO_LONG", "原题与补充内容合计超过 4000 字符，请精简补充后重试。", 422)
        turn.submissions[body.submissionId] = canonical
        self._emit(turn, "reply.accepted", interactionId=body.interactionId,
                   submissionId=body.submissionId, answers=[answer.model_dump() for answer in body.answers])
        turn.interaction = None
        turn.expires_at = time.monotonic() + self.ttl
        if not supplements:
            self._end(turn)
        else:
            turn.clarifications.extend(supplements)
            self._enqueue(turn, combined)
        return {"accepted": True}

    def cancel(self, session_id: str, turn_id: str) -> dict:
        turn = self._lookup(session_id, turn_id)
        turn.cancel.set()
        self._end(turn, code="RAG_CANCELLED", message="本轮教材查询已取消。")
        return {"accepted": True}

    async def events(self, turn: Turn, after: int = 0) -> AsyncIterator[dict | None]:
        cursor = after
        while True:
            turn.changed.clear()
            while cursor < len(turn.events):
                event = turn.events[cursor]
                cursor += 1
                yield event
            if turn.terminal:
                return
            try:
                await asyncio.wait_for(turn.changed.wait(), timeout=15)
            except TimeoutError:
                yield None  # SSE heartbeat, not a new persistent event.

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for turn in self.turns.values():
            turn.cancel.set()
            self._end(turn, code="RAG_UNAVAILABLE", message="教材服务已停止，请重新发送题目。")
        if self.active and self.active.timer:
            self.active.timer.cancel()
        while not self.queue.empty():
            job = self.queue.get_nowait()
            if job.timer:
                job.timer.cancel()
            self.queue.task_done()
        for task in (self.worker, self.janitor):
            if task:
                task.cancel()
        await asyncio.gather(*(task for task in (self.worker, self.janitor) if task), return_exceptions=True)
        # Queue close after any in-flight synchronous call, never race its resources.
        self.executor.submit(self._close_runtime)
        self.executor.shutdown(wait=False, cancel_futures=False)
        self.turns.clear()
        self.owners.clear()
        self.retired.clear()

    def _close_runtime(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
