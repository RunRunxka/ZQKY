"""RAG v2 会话服务：有界、可恢复、范围冻结的定位与详解。

复用既有 ``RagSessionService`` 的可恢复/有界会话语义：

- 事件递增编号（1 起）与 ``afterEventId`` 续传，重放同一轮返回同一事件序列；
- 断线**不**取消本轮；只有显式 ``/rag/cancel`` 或 TTL 过期才结束；
- 过期轮返回 ``RAG_TURN_EXPIRED``（410），不偷偷重新推理；
- 同一会话同一轮不能替换原题或教材范围（``RAG_TURN_CONFLICT``）；
- 身份不符（别的会话持有该轮）返回 ``RAG_SESSION_MISMATCH``（403）；
- 澄清提交按 ``submissionId`` 幂等：同键同载荷返回原结果，同键不同载荷 409
  ``IDEMPOTENCY_CONFLICT``；澄清重定位始终使用本轮已冻结的快照；
- 所有同步重活（范围核验、向量检索、BM25、原文读取、本地概括）只在**单线程**
  executor 里执行，事件推进留在事件循环线程，避免跨线程改 asyncio 对象；
- 不落盘、不记录日志：题目、追问与详解内容只存在于进程内存。

一次定位的同步部分由 executor 承担；超时/取消不会提前释放该 worker，迟到的结果
被计数丢弃（``discarded_late_results``），不会污染已结束的轮次。
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.schemas.rag_v2 import RagExplainRequest, RagResultV2, ScopeSnapshot, TextbookEvidence
from app.schemas.textbook import TextbookSelection
from app.services.rag_v2.evidence import (
    MAX_EVIDENCE_CHARS,
    MAX_EVIDENCE_ITEMS,
    build_evidence,
    rebuild_evidence_refs,
)
from app.services.rag_v2.explain import (
    ChatModelHandle,
    Explainer,
    build_explanation_request,
)
from app.services.rag_v2.presenter import render_result
from app.services.rag_v2.requests import RagReplyRequestV2, RagStreamRequestV2
from app.services.rag_v2.retrieval import DENSE_LIMIT, LEXICAL_LIMIT, RRF_K, HybridRetriever
from app.services.rag_v2.scope import resolve_scope, verify_scope
from app.services.rag_v2.source_text import ImmutableSource
from app.services.rag_v2.summary import SummaryOutcome, filter_points
from app.services.textbook_ingest.views import run_in_thread

DEFAULT_TTL_SECONDS = 600.0
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MAX_ROUNDS = 3
DEFAULT_MAX_TURNS = 64
DEFAULT_QUEUE_SIZE = 4
FOLLOW_UP_QUESTION_ID = "textbook-follow-up"
MAX_FOLLOW_UP_CHARS = 4000
#: 状态探测：短超时（并行探测共享一个总预算），结果短暂缓存，绝不拖慢 /rag/status。
DEFAULT_PROBE_TIMEOUT_SECONDS = 2.5
DEFAULT_PROBE_CACHE_SECONDS = 5.0
MAX_INFLIGHT_PROBES = 3


def _failure(code: str, message: str, status: int = 409, *, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=status, retryable=retryable)


@dataclass
class Turn:
    session_id: str
    turn_id: str
    request_id: str
    question: str
    scope_snapshot: ScopeSnapshot
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
class LocationJob:
    turn: Turn
    question: str
    deadline: float
    expired: bool = False
    timer: asyncio.Task | None = None


@dataclass(frozen=True)
class ExplainPreparation:
    evidence: list[TextbookEvidence]
    model: ChatModelHandle


class RagV2Service:
    """装配点（总控在 main.py 注入）：

    ``RagV2Service(catalog=…, retrieval=…, summarizer=…, explainer=…)``；四个依赖都是
    关键字可选且默认 ``None``，未注入的部分在 ``status()`` 里如实报不可用（构造不抛错）。
    """

    #: 路由据此判定 app.state.rag_service 是否已是 v2 服务（旧服务一律 503）
    is_rag_v2 = True

    def __init__(
        self,
        *,
        catalog: TextbookCatalog | None = None,
        retrieval: HybridRetriever | None = None,
        summarizer: object | None = None,
        explainer: Explainer | None = None,
        ttl: float = DEFAULT_TTL_SECONDS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        max_turns: int = DEFAULT_MAX_TURNS,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        evidence_max_items: int = MAX_EVIDENCE_ITEMS,
        evidence_max_chars: int = MAX_EVIDENCE_CHARS,
        texts: ImmutableSource | None = None,
        probe_timeout: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        probe_cache_seconds: float = DEFAULT_PROBE_CACHE_SECONDS,
    ) -> None:
        self.catalog = catalog
        self.retrieval = retrieval
        self.summarizer = summarizer
        self.explainer = explainer
        self.ttl = float(ttl)
        self.timeout = float(timeout)
        self.max_rounds = int(max_rounds)
        self.max_turns = int(max_turns)
        self.evidence_max_items = int(evidence_max_items)
        self.evidence_max_chars = int(evidence_max_chars)
        self.texts = texts if texts is not None else (ImmutableSource(catalog=catalog) if catalog else None)
        self.probe_timeout = max(0.1, float(probe_timeout))
        self.probe_cache_seconds = max(0.0, float(probe_cache_seconds))

        self.queue: asyncio.Queue[LocationJob] = asyncio.Queue(maxsize=int(queue_size))
        self.turns: dict[tuple[str, str], Turn] = {}
        self.owners: dict[str, str] = {}
        self.retired: OrderedDict[str, None] = OrderedDict()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rag-v2")
        # 状态探测专用小池：短超时 + 最多 MAX_INFLIGHT_PROBES 个在途任务，避免堆积
        self._probe_pool = ThreadPoolExecutor(
            max_workers=MAX_INFLIGHT_PROBES, thread_name_prefix="rag-v2-probe"
        )
        self._probe_lock = threading.Lock()
        self._probe_inflight = 0
        self._probe_cache: tuple[float, dict] | None = None
        self.worker: asyncio.Task | None = None
        self.janitor: asyncio.Task | None = None
        self.closed = False
        self.active: LocationJob | None = None
        self.discarded_late_results = 0

    # ------------------------------------------------------------------ 生命周期

    def _start_tasks(self) -> None:
        if self.closed:
            raise _failure("RAG_UNAVAILABLE", "教材服务已停止。", 503, retryable=True)
        if self.worker is None:
            self.worker = asyncio.create_task(self._work())
            self.janitor = asyncio.create_task(self._expire_turns())

    def _require_catalog(self) -> TextbookCatalog:
        if self.catalog is None:
            raise _failure(
                "SERVICE_UNAVAILABLE", "教材目录未装配，无法定位教材内容。", 503, retryable=True
            )
        return self.catalog

    def _require_retrieval(self) -> HybridRetriever:
        if self.retrieval is None:
            raise _failure(
                "SERVICE_UNAVAILABLE", "教材检索器未装配，无法检索教材内容。", 503, retryable=True
            )
        return self.retrieval

    def _source(self) -> ImmutableSource:
        if self.texts is None:
            raise _failure(
                "SERVICE_UNAVAILABLE", "教材原文访问未装配，无法读取教材原文。", 503, retryable=True
            )
        return self.texts

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for turn in self.turns.values():
            turn.cancel.set()
            self._end(turn, code="RAG_UNAVAILABLE", message="教材服务已停止，请重新发送题目。", retryable=True)
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
        await asyncio.gather(
            *(task for task in (self.worker, self.janitor) if task), return_exceptions=True
        )
        # 队列关闭排在在途同步调用之后，不与它的资源竞争（同一单线程 executor）。
        self.executor.shutdown(wait=False, cancel_futures=False)
        self._probe_pool.shutdown(wait=False, cancel_futures=False)
        self.turns.clear()
        self.owners.clear()
        self.retired.clear()

    # ------------------------------------------------------------------ 状态

    async def status(self) -> dict:
        """分别报告检索 / 本地概括 / 原文访问三项状态；不把三项混成单一 localOnly。"""
        task = asyncio.create_task(run_in_thread(self._status_sync))
        task.add_done_callback(lambda finished: finished.cancelled() or finished.exception())
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=10)
        except TimeoutError:
            return self._unavailable_status("教材状态检查超时，请稍后重试。")
        except Exception:
            return self._unavailable_status("教材状态读取失败，请检查教材目录与索引。")

    def _unavailable_status(self, reason: str) -> dict:
        return self._status_payload(
            retrieval={"available": False, "reason": reason},
            summarization=self._summarizer_status({}),
            source_access={"available": False, "reason": reason},
            scope={"ready": False, "reason": reason, "selection": None},
            generation=None,
        )

    def _status_sync(self) -> dict:
        catalog = self.catalog
        if catalog is None:
            return self._status_payload(
                retrieval={"available": False, "reason": "教材目录未装配，无法核验范围并检索教材。"},
                summarization=self._summarizer_status({}),
                source_access={"available": False, "reason": "教材目录未装配，无法读取教材原文。"},
                scope={"ready": False, "reason": "教材目录未装配。", "selection": None},
                generation=None,
            )
        try:
            state = catalog.catalog_state()
            record = (
                catalog.get_generation(state.active_generation_id)
                if state.active_generation_id
                else None
            )
            generation = self._generation_status(catalog, record)
            scope = self._scope_status(catalog)
            probes = self._probe_upstreams(record)
        except AppError as exc:
            return self._unavailable_status(f"教材状态读取失败：{exc}")
        except Exception:
            return self._unavailable_status("教材状态读取失败，请检查教材目录与索引。")
        return self._status_payload(
            retrieval=self._retrieval_status(generation, probes),
            summarization=self._summarizer_status(probes),
            source_access=self._source_status(),
            scope=scope,
            generation=generation,
        )

    # ---------------------------------------------------------------- 上游探测

    def _probe_upstreams(self, record) -> dict:
        """短超时并行探测三类上游；失败只影响 available/reason，绝不抛错。

        结果按 ``probe_cache_seconds`` 短暂缓存（``/rag/status`` 与 ``/capabilities`` 都会调用），
        在途探测超过上限时不再排队，避免上游卡死拖垮状态接口。
        """
        now = time.monotonic()
        cached = self._probe_cache
        if cached is not None and now - cached[0] < self.probe_cache_seconds:
            return dict(cached[1])
        profile = None
        if record is not None:
            profile = self.catalog.get_embedding_profile(record.profile_id) if self.catalog else None
        tasks: dict[str, Callable[[], dict]] = {
            "embeddings": lambda: self._probe_embedding_profile(profile),
            "vectorStore": self._probe_vector_store,
            "summarization": self._probe_summarization,
        }
        results: dict[str, dict] = {}
        futures: dict[str, Future] = {}
        with self._probe_lock:
            allow = self._probe_inflight < MAX_INFLIGHT_PROBES and not self.closed
        deadline = time.monotonic() + self.probe_timeout
        for key, task in tasks.items():
            if not allow:
                results[key] = {
                    "available": False,
                    "reason": "上游探测尚未返回（上一次探测仍在进行），暂按不可用报告。",
                }
                continue
            try:
                futures[key] = self._probe_pool.submit(self._run_probe, task)
            except RuntimeError:
                results[key] = {"available": False, "reason": "上游探测不可用：服务已停止。"}
        for key, future in futures.items():
            remaining = max(0.0, deadline - time.monotonic())
            try:
                results[key] = future.result(timeout=remaining)
            except TimeoutError:
                future.cancel()
                results[key] = {
                    "available": False,
                    "reason": f"上游探测超时（超过 {self.probe_timeout:.1f} 秒未返回）。",
                }
            except Exception:  # noqa: BLE001 - 探测失败只影响状态
                results[key] = {"available": False, "reason": "上游探测失败。"}
        self._probe_cache = (time.monotonic(), dict(results))
        return results

    def _run_probe(self, task: Callable[[], dict]) -> dict:
        with self._probe_lock:
            self._probe_inflight += 1
        try:
            return task()
        except AppError as exc:
            return {"available": False, "reason": str(exc)}
        except Exception:  # noqa: BLE001 - 上游不可达/协议异常都只回报
            return {"available": False, "reason": "上游探测失败。"}
        finally:
            with self._probe_lock:
                self._probe_inflight -= 1

    def _probe_embedding_profile(self, profile) -> dict:
        """Embedding 上游探测：可达性 + 模型身份（digest 与登记一致）。"""
        if self.retrieval is None or getattr(self.retrieval, "embeddings", None) is None:
            return {"available": False, "reason": "Embedding 适配器未装配。"}
        if profile is None:
            return {"available": False, "reason": "当前没有可核验的 Embedding 配置。"}
        embeddings = self.retrieval.embeddings
        reader = getattr(embeddings, "manifest_digest", None)
        if not callable(reader):
            return {"available": True, "reason": None, "identityVerified": False}
        digest = reader(profile.model_name)
        if digest != profile.model_manifest_digest:
            return {
                "available": False,
                "reason": "Embedding 模型身份与登记不一致（同名 tag 可能已换权重），检索会拒绝执行。",
                "identityVerified": False,
            }
        return {"available": True, "reason": None, "identityVerified": True}

    def _probe_vector_store(self) -> dict:
        vectors = getattr(self.retrieval, "vectors", None)
        if vectors is None:
            return {"available": False, "reason": "向量库未装配。"}
        ping = getattr(vectors, "ping", None)
        if not callable(ping):
            return {"available": True, "reason": None}
        if ping():
            return {"available": True, "reason": None}
        detail = None
        error_reader = getattr(vectors, "ping_error", None)
        if callable(error_reader):
            try:
                detail = error_reader()
            except Exception:  # noqa: BLE001 - 只用于状态文案
                detail = None
        return {
            "available": False,
            "reason": f"向量库不可达：{detail}" if detail else "向量库不可达。",
        }

    def _probe_summarization(self) -> dict:
        if self.summarizer is None:
            return {"available": False, "reason": "本地知识点概括服务未装配。"}
        probe = getattr(self.summarizer, "probe", None)
        if callable(probe):
            return probe()
        # 替身没有真实探测能力时退回它自己的 status()（保持既有语义）
        reader = getattr(self.summarizer, "status", None)
        if callable(reader):
            value = reader()
            if isinstance(value, dict):
                return {
                    "available": bool(value.get("available")),
                    "reason": value.get("reason"),
                }
        return {"available": True, "reason": None}

    def _status_payload(
        self,
        *,
        retrieval: dict,
        summarization: dict,
        source_access: dict,
        scope: dict,
        generation: dict | None,
    ) -> dict:
        detail = (
            f"检索{'可用' if retrieval.get('available') else '不可用'}"
            f"（{retrieval.get('reason') or '索引代与任教范围均可核验'}）；"
            f"本地概括{'可用' if summarization.get('available') else '不可用'}"
            f"（{summarization.get('reason') or summarization.get('model') or '已装配'}）；"
            f"原文访问{'可用' if source_access.get('available') else '不可用'}"
            f"（{source_access.get('reason') or '按不可变修订读取封存原文'}）。"
            "详解使用用户所选聊天模型，可能不是本地模型。"
        )
        return {
            "retrieval": retrieval,
            "summarization": summarization,
            "sourceAccess": source_access,
            "scope": scope,
            "generation": generation,
            "humanQuality": "not_run",
            # capabilities.py（不在本任务可写范围）读取这两个兼容字段；
            # /rag/status 路由只投影上面六项，不暴露兼容字段。
            "available": bool(retrieval.get("available") and scope.get("ready")),
            "detail": detail,
        }

    def _retrieval_status(self, generation: dict | None, probes: dict | None = None) -> dict:
        """检索可用性 = 已装配 + 索引代就绪 + **上游真实可达**（Embedding 身份/向量库）。"""
        probes = probes or {}
        limits = {
            "denseLimit": getattr(self.retrieval, "dense_limit", DENSE_LIMIT),
            "lexicalLimit": getattr(self.retrieval, "lexical_limit", LEXICAL_LIMIT),
            "rrfK": getattr(self.retrieval, "rrf_k", RRF_K),
        }
        base = {
            **limits,
            "vectorStore": bool(getattr(self.retrieval, "vectors", None) is not None),
            "queryEmbedding": bool(getattr(self.retrieval, "embeddings", None) is not None),
        }
        if self.catalog is None:
            return {**base, "available": False, "reason": "教材目录未装配，无法核验范围。"}
        if self.retrieval is None:
            return {**base, "available": False, "reason": "教材检索器未装配。"}
        if generation is None:
            return {**base, "available": False, "reason": "当前没有已发布的教材索引代。"}
        if generation.get("state") != "ready":
            return {**base, "available": False, "reason": "当前索引代尚未就绪。"}
        vector_probe = probes.get("vectorStore")
        if isinstance(vector_probe, dict) and not vector_probe.get("available"):
            return {
                **base,
                "available": False,
                "reason": vector_probe.get("reason") or "向量库不可达。",
                "probed": True,
            }
        embedding_probe = probes.get("embeddings")
        if isinstance(embedding_probe, dict) and not embedding_probe.get("available"):
            return {
                **base,
                "available": False,
                "reason": embedding_probe.get("reason") or "Embedding 上游不可达。",
                "probed": True,
            }
        identity_verified = (
            bool(embedding_probe.get("identityVerified"))
            if isinstance(embedding_probe, dict) and "identityVerified" in embedding_probe
            else None
        )
        return {
            **base,
            "available": True,
            "reason": None,
            "probed": bool(probes),
            "identityVerified": identity_verified,
        }

    def _source_status(self) -> dict:
        if self.catalog is None:
            return {"available": False, "reason": "教材目录未装配，无法读取教材原文。"}
        if self.texts is None:
            return {"available": False, "reason": "教材原文访问未装配。"}
        return {"available": True, "reason": None, "verifiesHash": True}

    @staticmethod
    def _generation_status(catalog: TextbookCatalog, record) -> dict | None:
        if record is None:
            return None
        return {
            "generationId": record.generation_id,
            "collectionName": record.collection_name,
            "profileId": record.profile_id,
            "state": record.state,
            "chunkTotal": catalog.generation_chunk_total(record.generation_id),
            "documentTotal": len(catalog.list_generation_revisions(record.generation_id)),
            "createdAt": record.created_at,
            "publishedAt": record.published_at,
        }

    @staticmethod
    def _scope_status(catalog: TextbookCatalog) -> dict:
        record = catalog.get_teaching_settings()
        raw = record.selection
        selection: TextbookSelection | None = None
        if isinstance(raw, dict):
            try:
                selection = TextbookSelection.model_validate(raw)
            except Exception:  # noqa: BLE001 - 损坏设置不伪装成"已就绪"
                selection = None
        if selection is None:
            return {"ready": False, "reason": "尚未保存任教范围。", "selection": None}
        try:
            catalog.resolve_selection(selection)
        except AppError as exc:
            return {"ready": False, "reason": str(exc), "selection": selection.model_dump()}
        except Exception:  # noqa: BLE001 - 目录损坏按不可用报告
            return {
                "ready": False,
                "reason": "任教范围核验失败，请检查教材目录。",
                "selection": selection.model_dump(),
            }
        return {"ready": True, "reason": None, "selection": selection.model_dump()}

    def _summarizer_status(self, probes: dict | None = None) -> dict:
        """概括状态 = 已装配/地址合法 + **上游真实可达且目标模型已安装**（P1）。"""
        probes = probes or {}
        if self.summarizer is None:
            return {
                "available": False,
                "reason": "本地知识点概括服务未装配。",
                "model": None,
                "providerUrl": None,
            }
        base: dict = {"model": None, "providerUrl": None}
        reader = getattr(self.summarizer, "status", None)
        if callable(reader):
            try:
                value = reader()
            except Exception:  # noqa: BLE001 - 状态检查失败按不可用报告
                value = None
            if isinstance(value, dict):
                base = {"model": value.get("model"), "providerUrl": value.get("providerUrl")}
                if not value.get("available"):
                    return {
                        "available": False,
                        "reason": value.get("reason") or "本地知识点概括不可用。",
                        **base,
                    }
        else:
            base = {
                "model": getattr(self.summarizer, "model", None),
                "providerUrl": getattr(self.summarizer, "provider_url", None),
            }
        probe = probes.get("summarization")
        if isinstance(probe, dict) and not probe.get("available"):
            return {
                "available": False,
                "reason": probe.get("reason") or "本地概括上游不可达。",
                **base,
            }
        return {"available": True, "reason": None, **base}

    # ------------------------------------------------------------------ 事件

    def _emit(self, turn: Turn, name: str, **payload) -> None:
        if turn.terminal:
            return
        turn.events.append(
            {
                "id": len(turn.events) + 1,
                "event": name,
                "data": {
                    "requestId": turn.request_id,
                    "sessionId": turn.session_id,
                    "turnId": turn.turn_id,
                    "messageId": turn.message_id,
                    **payload,
                },
            }
        )
        turn.changed.set()

    def _end(
        self, turn: Turn, *, code: str | None = None, message: str = "", retryable: bool = False
    ) -> None:
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
            raise _failure(
                "RAG_TURN_EXPIRED", "该轮已过期或服务已重启，请重新发送题目。", 410
            )
        return turn

    def _prune(self) -> None:
        now = time.monotonic()
        for key, turn in list(self.turns.items()):
            if now >= turn.expires_at:
                turn.cancel.set()
                self._end(turn, code="RAG_TURN_EXPIRED", message="本轮已过期，请重新发送题目。", retryable=True)
                del self.turns[key]
                self.owners.pop(turn.turn_id, None)
                self.retired[turn.turn_id] = None
                while len(self.retired) > self.max_turns * 4:
                    self.retired.popitem(last=False)

    async def _expire_turns(self) -> None:
        while True:
            await asyncio.sleep(min(15, max(1.0, self.ttl)))
            self._prune()

    # ------------------------------------------------------------------ 定位

    def start(self, body: RagStreamRequestV2) -> Turn:
        """同步创建/恢复一轮定位；范围错误在此直接抛（流开始前即 HTTP 错误）。"""
        self._start_tasks()
        self._prune()
        self._require_catalog()
        self._require_retrieval()
        if body.turnId in self.retired:
            raise _failure(
                "RAG_TURN_EXPIRED", "该轮已过期，请使用新轮次重新发送题目。", 410
            )
        if self.owners.get(body.turnId) not in (None, body.sessionId):
            raise _failure("RAG_SESSION_MISMATCH", "该轮不属于当前会话。", 403)
        key = (body.sessionId, body.turnId)
        existing = self.turns.get(key)
        if existing is not None:
            if existing.question != body.question or not self._same_scope(existing, body):
                raise _failure("RAG_TURN_CONFLICT", "同一轮不能替换原题或教材范围。")
            if body.afterEventId > len(existing.events):
                raise _failure("RAG_EVENT_CONFLICT", "恢复事件位置超出本轮范围。")
            return existing
        if body.afterEventId:
            raise _failure(
                "RAG_TURN_EXPIRED", "该轮已过期或服务已重启，请重新发送题目。", 410
            )
        if len(self.turns) >= self.max_turns:
            raise _failure("RAG_CAPACITY", "教材会话容量已满，请等待旧轮次过期后重试。", 429)
        if self.queue.full():
            raise _failure("RAG_QUEUE_FULL", "教材推理队列已满，请稍后重试。", 429, retryable=True)
        snapshot = self._snapshot_for(body)
        turn = Turn(
            session_id=body.sessionId,
            turn_id=body.turnId,
            request_id=body.requestId,
            question=body.question,
            scope_snapshot=snapshot,
            expires_at=time.monotonic() + self.ttl,
        )
        self.turns[key] = turn
        self.owners[body.turnId] = body.sessionId
        self._emit(turn, "message.start", scopeSnapshot=snapshot.model_dump(mode="json"))
        self._enqueue(turn, body.question)
        return turn

    @staticmethod
    def _same_scope(turn: Turn, body: RagStreamRequestV2) -> bool:
        if body.scope.kind == "frozen":
            return body.scope.snapshot.scopeHash == turn.scope_snapshot.scopeHash
        return body.scope.selection.model_dump() == turn.scope_snapshot.selection.model_dump()

    def _snapshot_for(self, body: RagStreamRequestV2) -> ScopeSnapshot:
        catalog = self._require_catalog()
        if body.scope.kind == "selection":
            return resolve_scope(catalog, body.scope.selection)
        snapshot = body.scope.snapshot
        verify_scope(catalog, snapshot)
        return snapshot

    def _enqueue(self, turn: Turn, question: str) -> None:
        job = LocationJob(turn, question, time.monotonic() + self.timeout)
        self.queue.put_nowait(job)
        job.timer = asyncio.create_task(self._deadline(job))
        turn.state = "running"

    async def _deadline(self, job: LocationJob) -> None:
        await asyncio.sleep(max(0.0, job.deadline - time.monotonic()))
        job.expired = True
        job.turn.cancel.set()
        self._end(
            job.turn,
            code="RAG_TIMEOUT",
            message="教材定位超时，请稍后重新发送。",
            retryable=True,
        )

    async def _work(self) -> None:
        while True:
            job = await self.queue.get()
            self.active = job
            turn = job.turn
            try:
                if job.expired or turn.terminal:
                    continue
                result = await asyncio.get_running_loop().run_in_executor(
                    self.executor, self._locate, job
                )
                if time.monotonic() >= job.deadline and not turn.terminal:
                    job.expired = True
                    turn.cancel.set()
                    self._end(
                        turn,
                        code="RAG_TIMEOUT",
                        message="教材定位超时，请稍后重新发送。",
                        retryable=True,
                    )
                if job.expired or turn.cancel.is_set() or turn.terminal or self.closed:
                    self.discarded_late_results += 1
                    continue
                turn.round += 1
                self._emit(turn, "rag.result", result=result.model_dump(mode="json"))
                self._emit(turn, "text.delta", text=render_result(result))
                if turn.round >= self.max_rounds:
                    self._end(turn)
                else:
                    turn.state = "waiting"
                    turn.interaction = self._interaction(result)
                    self._emit(turn, "wait-user", **turn.interaction)
            except asyncio.CancelledError:
                raise
            except AppError as exc:
                if turn.terminal:
                    self.discarded_late_results += 1
                else:
                    self._end(turn, code=exc.code, message=str(exc), retryable=exc.retryable)
            except Exception:  # noqa: BLE001 - 未预期失败如实报错，不伪装成无匹配
                if turn.terminal:
                    self.discarded_late_results += 1
                else:
                    self._end(
                        turn,
                        code="RAG_UNAVAILABLE",
                        message="教材检索执行失败，请检查本机服务与索引后重试。",
                        retryable=True,
                    )
            finally:
                if job.timer:
                    job.timer.cancel()
                self.active = None
                self.queue.task_done()

    # ------------------------------------------------------------ 同步定位主体

    def _locate(self, job: LocationJob) -> RagResultV2:
        """在单线程 executor 里执行的同步重活；不触碰 turn 的事件列表。"""
        if job.expired or job.turn.cancel.is_set():
            raise _failure("RAG_CANCELLED", "本轮已取消。", 409)
        catalog = self._require_catalog()
        retrieval = self._require_retrieval()
        turn = job.turn
        scope = verify_scope(catalog, turn.scope_snapshot)
        generation_id = turn.scope_snapshot.embeddingGenerationId
        generation = catalog.get_generation(generation_id)
        if generation is None or generation.state != "ready":
            raise _failure("INDEX_NOT_READY", "当前索引代未就绪，无法检索教材。", 409)
        profile = catalog.get_embedding_profile(generation.profile_id)
        if profile is None:
            raise _failure(
                "INDEX_NOT_READY", "当前索引代的 Embedding 配置缺失，无法检索教材。", 409
            )
        candidates = retrieval.retrieve(
            question=job.question, scope=scope, profile=profile, generation=generation
        )
        evidence = build_evidence(
            catalog=catalog,
            scope=scope,
            candidates=candidates,
            texts=self._source(),
            max_items=self.evidence_max_items,
            max_chars=self.evidence_max_chars,
        )
        # 证据重建后再核验一次：来源可能在本轮中途被删除或换修订
        verify_scope(catalog, turn.scope_snapshot)
        if not evidence:
            return RagResultV2(
                resultId=uuid.uuid4().hex,
                status="no_evidence",
                scopeSnapshot=turn.scope_snapshot,
                points=[],
                evidence=[],
                reason="当前教材范围没有找到足够依据，请补充题干、章节或确认任教范围。",
            )
        outcome = self._summarize(job.question, evidence)
        return RagResultV2(
            resultId=uuid.uuid4().hex,
            status="ok" if outcome.points else "partial",
            scopeSnapshot=turn.scope_snapshot,
            points=outcome.points,
            evidence=list(evidence),
            reason=outcome.reason,
        )

    def _summarize(self, question: str, evidence: Sequence[TextbookEvidence]) -> SummaryOutcome:
        """概括失败一律保留证据：可用原文 + partial，绝不降级成 no_evidence、绝不编造。"""
        if self.summarizer is None:
            return SummaryOutcome(
                points=[], reason="本地知识点概括服务未装配，保留教材原文供核对。"
            )
        try:
            outcome = self.summarizer.summarize(question=question, evidence=list(evidence))
        except AppError as exc:
            if exc.code == "RAG_SUMMARY_UNAVAILABLE":
                return SummaryOutcome(
                    points=[], reason=f"{exc}（已保留教材原文供核对）"
                )
            raise
        raw_points = list(getattr(outcome, "points", []) or [])
        reason = getattr(outcome, "reason", None)
        # 服务端二次校验：任何实现（含替身）产出的知识点都必须只引用已核验证据
        points, dropped = filter_points(raw_points, evidence)
        if raw_points and not points:
            reason = "知识点概括未通过原文引用校验，保留教材原文供核对。"
        return SummaryOutcome(points=points, reason=reason, dropped=dropped)

    @staticmethod
    def _interaction(result: RagResultV2) -> dict:
        missing = result.status in {"no_evidence", "uncertain"}
        return {
            "interactionId": uuid.uuid4().hex,
            "status": "waiting",
            "intro": (
                "教材证据不足，请补充后重新定位。"
                if missing
                else "可继续追问细节，或跳过结束本轮。"
            ),
            "questions": [
                {
                    "questionId": FOLLOW_UP_QUESTION_ID,
                    "header": "补充题目信息" if missing else "继续追问",
                    "prompt": (
                        "请补充完整题干、教材章节或你最困惑的步骤。"
                        if missing
                        else "定位是否符合题意？你希望进一步理解哪一步？"
                    ),
                    "options": (
                        []
                        if missing
                        else [{"label": "细讲解题思路"}, {"label": "重新核对知识点"}]
                    ),
                    "multiSelect": False,
                    "allowFreeText": True,
                    "placeholder": "填写补充信息；不需要继续时可跳过",
                }
            ],
        }

    # ------------------------------------------------------------------ 澄清

    def reply(self, body: RagReplyRequestV2) -> dict:
        turn = self._lookup(body.sessionId, body.turnId)
        if turn.cancel.is_set():
            raise _failure("RAG_TURN_CLOSED", "该轮已取消或超时，不能再次提交。")
        canonical = json.dumps(
            {
                "interactionId": body.interactionId,
                "answers": [answer.model_dump() for answer in body.answers],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        if body.submissionId in turn.submissions:
            if turn.submissions[body.submissionId] != canonical:
                raise _failure(
                    "IDEMPOTENCY_CONFLICT", "同一提交标识不能替换答案。"
                )
            return {"accepted": True}
        if turn.terminal or turn.state != "waiting" or turn.interaction is None:
            raise _failure("RAG_TURN_CLOSED", "该轮当前不接受回答，请检查轮次是否已结束。")
        if body.interactionId != turn.interaction["interactionId"]:
            raise _failure("RAG_INTERACTION_EXPIRED", "该追问卡已失效，请使用当前追问卡。")
        questions = {item["questionId"]: item for item in turn.interaction["questions"]}
        if len(body.answers) != len(questions) or {a.questionId for a in body.answers} != set(questions):
            raise _failure("RAG_INVALID_ANSWERS", "回答必须逐项对应当前追问卡。", 422)
        supplements: list[str] = []
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
            raise _failure("RAG_QUEUE_FULL", "教材推理队列已满，请稍后重试。", 429, retryable=True)
        combined = ""
        if supplements:
            combined = (
                "原始题目：\n"
                + turn.question
                + "\n\n用户补充（用于纠正题意与讲解重点）：\n"
                + "\n".join([*turn.clarifications, *supplements])
            )
            if len(combined) > MAX_FOLLOW_UP_CHARS:
                raise _failure(
                    "RAG_INPUT_TOO_LONG",
                    f"原题与补充内容合计超过 {MAX_FOLLOW_UP_CHARS} 字符，请精简补充后重试。",
                    422,
                )
        turn.submissions[body.submissionId] = canonical
        self._emit(
            turn,
            "reply.accepted",
            interactionId=body.interactionId,
            submissionId=body.submissionId,
            answers=[answer.model_dump() for answer in body.answers],
        )
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
        self._end(turn, code="RAG_CANCELLED", message="本轮教材定位已取消。")
        return {"accepted": True}

    async def events(self, turn: Turn, after: int = 0) -> AsyncIterator[dict | None]:
        """重放已产生事件并继续等待；``None`` 表示 keep-alive，不是持久事件。"""
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
                yield None

    # ------------------------------------------------------------------ 详解

    async def explain(self, body: RagExplainRequest) -> AsyncIterator[tuple[str, dict]]:
        """普通聊天 SSE 语义：无事件游标；断开即关闭上游。"""
        preparation = await run_in_thread(self._prepare_explain, body)
        message_id = uuid.uuid4().hex
        identity = {
            "requestId": body.requestId,
            "sessionId": body.sessionId,
            "turnId": body.turnId,
            "messageId": message_id,
            "modelProfileId": body.modelProfileId,
        }
        yield ("message.start", dict(identity))
        explainer = self.explainer
        if explainer is None:  # pragma: no cover - _prepare_explain 已先行校验
            raise _failure("SERVICE_UNAVAILABLE", "所选模型详解未装配。", 503, retryable=True)
        stream = explainer.explain(body, evidence=preparation.evidence, model=preparation.model)
        finish = "unknown"
        try:
            async for delta in stream:
                kind = getattr(delta, "type", None)
                if kind == "text":
                    text = getattr(delta, "text", "") or ""
                    if text:
                        yield ("text.delta", {**identity, "text": text})
                elif kind == "end":
                    finish = getattr(delta, "finishReason", None) or "unknown"
        except AppError as exc:
            yield (
                "error",
                {
                    "requestId": body.requestId,
                    "messageId": message_id,
                    "code": exc.code,
                    "message": str(exc),
                    "retryable": exc.retryable,
                },
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 上游异常如实报错，不伪装成正常结束
            yield (
                "error",
                {
                    "requestId": body.requestId,
                    "messageId": message_id,
                    "code": "UPSTREAM_ERROR",
                    "message": "详解上游异常结束。",
                    "retryable": False,
                },
            )
            return
        finally:
            await stream.aclose()
        yield ("message.end", {**identity, "finishReason": finish})

    def _prepare_explain(self, body: RagExplainRequest) -> ExplainPreparation:
        """详解前准备（同步）：引用重建 + 模型冻结 + 预算校验，任一失败即 HTTP 错误。"""
        catalog = self._require_catalog()
        if self.explainer is None:
            raise _failure("SERVICE_UNAVAILABLE", "所选模型详解未装配。", 503, retryable=True)
        source = self._source()
        scope = verify_scope(catalog, body.scopeSnapshot)
        evidence = rebuild_evidence_refs(
            catalog=catalog, scope=scope, refs=body.evidenceRefs, texts=source
        )
        if not evidence:
            raise _failure("RAG_EVIDENCE_UNAVAILABLE", "引用证据为空，请重新定位后再试。", 409)
        model = self.explainer.freeze_model(body.modelProfileId)
        build_explanation_request(body=body, evidence=evidence, model=model)
        return ExplainPreparation(evidence=evidence, model=model)


__all__ = [
    "ExplainPreparation",
    "LocationJob",
    "RagV2Service",
    "Turn",
]
