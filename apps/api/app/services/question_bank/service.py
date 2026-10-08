"""题库服务：导入拆题、校对编辑、拆分/合并、AI 整理建议、幂等确认入库与题目管理。

不变量：
- 解析、文件与模型调用一律在 SQL 写事务之外执行；SQL 一律经 ``anyio.to_thread`` 有界线程，
  事件循环里不跑同步数据库调用；
- 未归属原文块永久保留：拆题只记录 spans，从不删除 ``question_source_blocks``；
- AI 建议只落 ``pending``，应用前核对 ``base_draft_revision``，绝不直接覆盖人工草稿；
- 确认入库在单个事务内完成：同 submissionId 同载荷返回原结果，同键不同载荷 409；
- 任一草稿校验失败整体不确认，返回逐条 failures（HTTP 200 + ``ConfirmResult.failures``）；
- 题库没有任何指向教材索引与教材向量库的路径。

B2 增量（知识点关联 / AI 补题 / 统一任务引擎）：

- **知识点关联**：草稿可带 ``knowledgeLinks``（提供即整表替换）；知识点只经注入的
  ``knowledge_catalog`` **只读**校验（存在、未归档、与题目 ``metadata.subjectId`` 同学科），
  关联快照记录当时的 ``knowledgeRevisionId``/名称/学科；内容或关联一变 → ``revision+1``
  且回到 ``needs_review``。确认入库时草稿关联冻结为正式题修订关联；改题=追加新修订并
  复制旧关联（明确改关联时替换），旧修订旧关联不可改（DB 触发器）。
  跨库读取/发布经注入的 ``PublicationCoordinator``（进程内 RLock），
  锁内只做读取与本库短事务；
- **拆分/合并**：新草稿**不继承**知识点关联（拆/合后的题覆盖范围已变），
  明确写入"关联已清空、需重新校对"的警告；被替代的旧草稿行保留并继续携带原关联，
  供追溯，不静默宣称关联仍然有效；
- **AI 补题**（``question:generate``）：独立回复解析器在 ``question_bank.generation``，
  冻结允许知识点/证据/题型/数量与模型指纹；候选只落 ``needs_review`` 草稿 + ``source='ai'``
  草稿关联，批次/候选/来源/任务 succeeded 同库同事务；
- **统一任务引擎**：整理任务经 ``job_engine.store("question")`` 建任务并
  ``run_job(...)`` 执行（租约/心跳/attempt/取消/重试/重启 ``running → interrupted``），
  旧 ``pending_jobs``/``record_organize_batch`` 路径不再自己执行任务；
  ``recover_organize_jobs`` 改为**显式恢复**（只对 ``interrupted``/``failed`` 重跑），
  启动收敛由 ``main.py`` 的 ``RECONCILE_DOMAINS`` 负责，恢复路径绝不自动重叫模型。

模型语义（RAG-QUALITY v1.1，唯一一套）：
- AI 整理与 AI 补题都使用**点击时的当前聊天模型，本地或云端一视同仁**；
  ``modelProfileId`` 是聊天模型 profile id，解析委托注入的 ``model_resolver``（唯一实现
  在共享的 ``services.model_runtime.resolve_chat_model``）；本服务不解释 profile id、
  不列本机模型、不做默认模型回退；
- 未注入 ``model_resolver`` 时 ``organize``/``create_generation_job`` 抛 503
  ``SERVICE_UNAVAILABLE``（可重试），不建任务、不发上游；
- 建任务时把 ``modelProfileId`` 与非敏感 ``modelFingerprint`` 冻结进任务行；
  任务进行中用户切换聊天模型不影响已冻结任务；恢复时用同一 profile id 重新解析，
  配置已不存在或不可调用则任务失败并给可读原因；
- 旧语义 checkpoint（不是 profile id 形状）不自动恢复，标记 ``ORGANIZER_MODEL_RESELECT_REQUIRED``
  并要求重新选择模型，已产生的建议一条不动。

错误分类（详见 ``services.question_bank.organizer`` 模块 docstring）：
- 批级（内容问题，该批失败，原文保留、草稿不变，其余批次继续）：
  ``ORGANIZER_INVALID_JSON`` / ``ORGANIZER_OUTPUT_TRUNCATED``（截断，不生成可应用建议）/
  ``ORGANIZER_UNKNOWN_SOURCE_BLOCK`` / ``ORGANIZER_INVALID_CONTENT`` / ``ORGANIZE_DRAFT_CHANGED``；
- 任务级（模型服务问题，整条任务失败，文案指向模型服务，不记成批内容失败）：
  ``AUTH_REQUIRED`` / ``RATE_LIMITED`` / ``UPSTREAM_UNAVAILABLE`` / ``MODEL_NOT_CONFIGURED`` /
  ``MODEL_PROFILE_NOT_FOUND`` / ``MODEL_PURPOSE_MISMATCH`` / ``SERVICE_UNAVAILABLE``。
"""

from __future__ import annotations

import anyio
import functools
import logging
from collections.abc import Mapping
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMMessage, LLMRequest, LLMResponse
from app.providers.llm.registry import find_provider
from app.repositories.jobs.repository import JobStore
from app.repositories.question_bank.catalog import JobLeaseIdentity, QuestionBankCatalog
from app.repositories.question_bank.records import (
    DraftInput,
    DraftRecord,
    SourceBlockInput,
    SourceBlockRecord,
)
from app.schemas.question_bank import (
    QUESTION_MODEL_NOT_CLOUD,
    QUESTION_MODEL_NOT_CLOUD_MESSAGE,
    ConfirmFailure,
    ConfirmResult,
    DraftKnowledgeLinkInput,
    DraftPatchRequest,
    DraftSplitRequest,
    DraftMergeRequest,
    DraftView,
    GenerationJobView,
    OrganizeJobView,
    OrganizeRequest,
    QuestionConfirmRequest,
    QuestionDetail,
    QuestionGenerationRequest,
    QuestionImportDeleteResult,
    QuestionImportDetail,
    QuestionImportDiscardRequest,
    QuestionImportList,
    QuestionList,
    QuestionPatchRequest,
    SuggestionApplyRequest,
)
from app.schemas.textbook import MAX_UPLOAD_BYTES
from app.services.document_parsing.parser import (
    PARSER_VERSION,
    SUPPORTED_SUFFIXES,
    ParsedDocument,
    parse_document,
)
from app.services.jobs.engine import (
    FrozenJob,
    JobContext,
    JobEngine,
    JobOutcome,
)
from app.services.knowledge_refs import (
    KNOWLEDGE_REFERENCE_INVALID,
    KnowledgeReference,
    read_knowledge_snapshots,
    require_active_knowledge_references,
)
from app.services.model_runtime import (
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    ChatModelHandle,
    fingerprint_of_handle,
    resolve_frozen_model,
)
from app.services.assets.store import AssetStore, is_managed_blob_key, is_sha256_hex
from app.services.question_bank import fingerprint as fp
from app.services.question_bank import generation, rich, rules, validation, views
from app.services.question_bank.blobs import QuestionBlobStore
from app.services.question_bank.organizer import (
    BATCH_LEVEL_ORGANIZER_ERRORS,
    MAX_OUTPUT_TOKENS,
    ORGANIZE_CONTRACT_VERSION,
    ORGANIZE_INSTRUCTION,
    RESELECT_MODEL_CODE,
    RESELECT_MODEL_MESSAGE,
    ChatModelResolver,
    Batch,
    batch_from_snapshot,
    batch_snapshot,
    is_current_checkpoint,
    job_level_error_code,
    job_level_message,
    normalize_reply,
    output_truncated_error,
    pack_batches,
)

logger = logging.getLogger("zhiqikeyuan.question_bank")

DEFAULT_OWNER_ID = "local-user"
DEFAULT_IMPORT_LIMIT = 50
MAX_IMPORT_LIMIT = 200
DEFAULT_LIST_LIMIT = 20

#: 本题库域的任务类型（与 ``main.py`` 的 ``JOB_KINDS["question"]`` 一致）
QUESTION_JOB_KINDS = frozenset({"organize", "generate"})

#: 任务终态：已结束的任务不重复执行（``interrupted`` 也终态，等显式恢复）
TERMINAL_JOB_STATES = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
#: 显式恢复的候选状态：只重跑中断与失败，不碰已成功/已取消/排队中的任务
RECOVERABLE_JOB_STATES = frozenset({"interrupted", "failed"})

SPLIT_NOTE = "已按原文偏移拆分为两道草稿；本行仅保留，不再参与确认。"
MERGE_NOTE = "已与同批草稿合并；本行仅保留，不再参与确认。"
#: 拆/合后新草稿的关联口径：不继承（覆盖范围已变），明确提示而非静默
LINK_CLEARED_NOTE = "原知识点关联未继承（拆分/合并后题目覆盖范围已变），请重新校对关联。"

#: 知识点关联校验的错误码（服务层向知识点库只读校验的稳定对外码）
KNOWLEDGE_POINT_NOT_FOUND = "KNOWLEDGE_POINT_NOT_FOUND"
KNOWLEDGE_POINT_ARCHIVED = "KNOWLEDGE_POINT_ARCHIVED"
KNOWLEDGE_SUBJECT_MISMATCH = "KNOWLEDGE_SUBJECT_MISMATCH"
KNOWLEDGE_CATALOG_UNAVAILABLE = "KNOWLEDGE_CATALOG_UNAVAILABLE"


async def _threaded(fn, /, *args, **kwargs):
    """把同步的 SQL/仓储调用放到 anyio 有界线程执行（事件循环里不跑同步数据库调用）。"""
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _require_operable_import(record: Any, *, operation: str) -> None:
    """放弃（``cancelled``）/已确认的批次不再是可操作批次：拆分、合并一律拒绝。

    只收紧行为不放宽：``failed`` 等其它非终态的行为与既有实现一致，不在本守卫内。
    """
    if record.state == "cancelled":
        raise _conflict(f"该导入已放弃，不能{operation}。", code="IMPORT_CANCELLED")
    if record.state == "confirmed":
        raise _conflict(f"该导入已确认入库，不能{operation}。", code="IMPORT_ALREADY_CONFIRMED")


def _invalid(message: str, *, code: str = "INVALID_REQUEST") -> AppError:
    return AppError(message, code=code, status_code=422)


def _not_found(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=404)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


#: 缺可核对指纹 / 配置已漂移的可读文案（与共享 ``resolve_frozen_model`` 同一口径）
MODEL_FINGERPRINT_MISSING_MESSAGE = (
    "任务缺少可核对的冻结模型指纹；请重新发起任务（旧任务不自动重放）。"
)
MODEL_CONFIG_DRIFT_MESSAGE = (
    "模型配置自任务创建后已变化（同 profile 的模型/地址/格式与冻结指纹不一致）；"
    "本次调用已停止，请重新发起任务。"
)


def _frozen_snapshot_fields(snapshot: Any) -> dict[str, str]:
    """从冻结快照取 ``profileId`` + ``fingerprint``；任一缺失 → 422 明确失败。

    兼容历史行的 ``modelProfileId`` / ``modelFingerprint`` 写法：两者都是**创建任务时
    冻结**的值，不是重新解析出来的当前配置。旧任务没有可核对指纹时不静默放行。
    """
    payload = snapshot if isinstance(snapshot, Mapping) else {}
    profile_id = str(
        payload.get("profileId") or payload.get("modelProfileId") or ""
    ).strip()
    fingerprint = str(
        payload.get("fingerprint") or payload.get("modelFingerprint") or ""
    ).strip()
    if not profile_id or not fingerprint:
        raise AppError(
            MODEL_FINGERPRINT_MISSING_MESSAGE,
            code=MODEL_FINGERPRINT_MISSING,
            status_code=422,
        )
    return {"profileId": profile_id, "fingerprint": fingerprint}


def build_frozen_model_resolver(
    repo: Any | None, secrets: Any | None, auth_service: Any | None
):
    """共享 ``resolve_frozen_model`` 的注入适配（仓储 + 凭证齐备时返回可调用对象）。

    总控装配时把 ``app.state.model_config_repo`` / ``secret_store`` /
    ``model_auth_service`` 一并传进服务即可让生产路径走共享实现；缺失时服务用注入的
    ``model_resolver`` 解析后按 ``fingerprint_of_handle`` 核对（判定与错误码一致）。
    """
    if repo is None or secrets is None:
        return None

    def resolve(snapshot: Mapping[str, Any]) -> ChatModelHandle:
        return resolve_frozen_model(repo, secrets, snapshot, auth_service=auth_service)

    return resolve


class QuestionBankService:
    """题库业务入口；目录（SQLite）与模型解析器都由构造参数注入，测试可整体替换。

    AI 整理的模型语义（RAG-QUALITY v1.1）：使用**点击时的当前聊天模型**，本地或云端均可。
    ``model_resolver`` 是唯一注入点（``(profileId) -> ChatModelHandle``，由总控在 ``main.py``
    装配共享的 ``resolve_chat_model``）；未注入时 ``organize`` 直接 503，不建任务、不发上游。
    本服务不解释 profile id、不读本机模型清单、没有默认模型回退。

    B2 注入点（都可选，缺省时对应能力如实 503，不返回假成功）：

    - ``knowledge_catalog``：知识点库**只读**入口（草稿/正式关联校验与补题知识点解析）；
    - ``coordinator``：跨库发布协调器（关联校验 + 本库短事务）；
    - ``job_engine``：统一任务引擎；缺省时用同一 ``JobStore``/``JobEngine`` 代码在本进程
      自建一个只含 question 域的引擎（行为一致，但并发名额不与其它域共享；
      ``main.py`` 应注入 ``app.state.job_engine`` 以共享名额）。

    B3/G0 注入点（可选）：

    - ``model_config_repo`` + ``secret_store``（+ ``model_auth_service``）：让恢复/重试路径
      走共享 ``resolve_frozen_model`` 核对冻结指纹（B2-RV04）；缺省时用注入的
      ``model_resolver`` 解析后按 ``fingerprint_of_handle`` 核对（同一判定与错误码）。
    """

    def __init__(
        self,
        catalog: QuestionBankCatalog,
        settings: Any,
        *,
        model_resolver: ChatModelResolver | None = None,
        parser: Callable[..., ParsedDocument] = parse_document,
        owner_id: str = DEFAULT_OWNER_ID,
        knowledge_catalog: Any | None = None,
        coordinator: Any | None = None,
        job_engine: JobEngine | None = None,
        model_config_repo: Any | None = None,
        secret_store: Any | None = None,
        model_auth_service: Any | None = None,
    ) -> None:
        self.catalog = catalog
        self.settings = settings
        self.owner_id = owner_id
        self.parser = parser
        self.blobs = QuestionBlobStore(settings.question_bank_root)
        self.assets = AssetStore(settings.assets_root)
        # 模型解析器由外部注入；None 表示未装配（organize 直接 503，不建任务）
        self.model_resolver: ChatModelResolver | None = model_resolver
        self.knowledge_catalog = knowledge_catalog
        self.coordinator = coordinator
        self.job_engine: JobEngine = job_engine or self._private_engine(catalog)
        # RV04：仓储 + 凭证齐备时走共享 resolve_frozen_model；否则用注入的 resolver
        # 解析后按同一指纹算法核对（见 _resolve_frozen_handle）
        self._frozen_model_resolver = build_frozen_model_resolver(
            model_config_repo, secret_store, model_auth_service
        )

    def close(self) -> None:
        """无长连接需要关闭；保留方法以便统一生命周期调用。"""
        return None

    # ------------------------------------------------------- 任务引擎与知识点

    @staticmethod
    def _private_engine(catalog: QuestionBankCatalog) -> JobEngine:
        """缺省引擎（仅 question 域）：与共享引擎同一套 JobStore/租约/心跳语义。"""
        store = JobStore(
            catalog,
            domain="question",
            table="question_jobs",
            kinds=QUESTION_JOB_KINDS,
        )
        return JobEngine({"question": store}, heavy_limit=2, model_limit=1)

    def _store(self) -> JobStore:
        """本题库域的任务表入口；引擎未装配该域时如实 503。"""
        try:
            return self.job_engine.store("question")
        except AppError as exc:
            if exc.code == "INVALID_REQUEST":
                raise AppError(
                    "题库任务引擎未装配 question 域，无法执行任务；请检查后端启动配置。",
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    retryable=True,
                ) from exc
            raise

    def register_job_executors(self, registry: Any) -> None:
        """把本题库域已实现的执行器注册进公共注册表（B3/G0 · B2-RV01）。

        公共 ``POST /workflow-jobs/{id}/retry`` 经此调度；注册的 factory 只依赖任务行
        （``frozen_input`` / ``checkpoint`` / ``model_snapshot``），重试**不重新冻结**：

        - ``question:organize``：复用 ``run_organize_job`` 的执行体（``model=None`` →
          按冻结输入的 profile id + 指纹重新解析并核对，B2-RV04）；每批建议仍在
          单事务内带租约 CAS 提交（B2-RV05）；
        - ``question:generate``：复用生成执行器（同样按冻结快照核对后调用）。

        未注册的类型由注册表返回 ``False``：任务保持 ``queued``，用户可再次 retry。
        """
        registry.register(
            "question",
            "organize",
            uses_model=True,
            factory=lambda _record: self._organize_executor_factory(model=None),
        )
        registry.register(
            "question",
            "generate",
            uses_model=True,
            factory=lambda _record: self._generation_executor(),
        )

    @contextmanager
    def _publication(self, operation: str) -> Iterator[None]:
        """跨库阶段串行化：有协调器就进锁，没有（隔离测试）则直接执行。"""
        if self.coordinator is None:
            with nullcontext():
                yield
            return
        with self.coordinator.publication(operation=operation):
            yield

    def _require_knowledge_catalog(self) -> Any:
        if self.knowledge_catalog is None:
            raise AppError(
                "知识点库未装配（knowledge_catalog），无法校验或读取知识点；"
                "请检查后端启动配置。",
                code=KNOWLEDGE_CATALOG_UNAVAILABLE,
                status_code=503,
                retryable=True,
            )
        return self.knowledge_catalog

    def _knowledge_records(self, point_ids: Sequence[str]) -> dict[str, Any]:
        """按 id 只读知识点（含归档者，交由调用方给出定位错误）。

        空集合直接返回空表：不因"没有引用任何知识点"而要求知识点库必须装配。
        """
        if not point_ids:
            return {}
        catalog = self._require_knowledge_catalog()
        from app.repositories.knowledge.points import KnowledgePointRepository

        repository = KnowledgePointRepository()
        records: dict[str, Any] = {}
        with catalog.read_connection() as conn:
            for point_id in point_ids:
                record = repository.get_point(conn, point_id)
                if record is not None:
                    records[record.point_id] = record
        return records

    def _knowledge_snapshots(
        self, point_ids: Sequence[str]
    ) -> dict[str, generation.KnowledgeSnapshot]:
        """只读快照（只含未归档知识点）：补题发布前重读，取当前修订与名称。"""
        records = self._knowledge_records(point_ids)
        return {
            point_id: generation.KnowledgeSnapshot(
                point_id=record.point_id,
                subject_id=record.subject_id,
                code=record.code,
                name=record.name,
                revision_id=record.revision_id,
            )
            for point_id, record in records.items()
            if record.status == "active"
        }

    async def _resolve_knowledge_snapshots(
        self, point_ids: Sequence[str]
    ) -> dict[str, generation.KnowledgeSnapshot]:
        """补题执行器注入点：发布前（事务外、协调器内、有界线程）重读知识点。"""
        with self._publication("question.generation.knowledge"):
            return await _threaded(self._knowledge_snapshots, point_ids)

    def _link_rows(
        self,
        links: Sequence[tuple[str, str]],
        *,
        subject_id: str,
        source: str,
    ) -> list[dict[str, str]]:
        """把 ``[(pointId, role)]`` 解析成完整关联快照行（同学科、未归档、修订一致）。"""
        if not links:
            return []
        with self._publication("question.knowledge_links"):
            records = self._knowledge_records([point_id for point_id, _role in links])
            rows: list[dict[str, str]] = []
            for point_id, role in links:
                record = records.get(point_id)
                if record is None:
                    raise AppError(
                        f"知识点不存在：{point_id}。",
                        code=KNOWLEDGE_POINT_NOT_FOUND,
                        status_code=404,
                    )
                if record.status != "active":
                    raise AppError(
                        f"知识点已归档，不能建立新的关联：{point_id}。",
                        code=KNOWLEDGE_POINT_ARCHIVED,
                        status_code=422,
                    )
                if record.subject_id != subject_id:
                    raise AppError(
                        f"知识点 {point_id} 属于学科 {record.subject_id}，"
                        f"与题目学科（{subject_id or '未填写'}）不一致。",
                        code=KNOWLEDGE_SUBJECT_MISMATCH,
                        status_code=422,
                    )
                rows.append(
                    {
                        "knowledgePointId": record.point_id,
                        "knowledgeRevisionId": record.revision_id,
                        "subjectIdSnapshot": record.subject_id,
                        "knowledgeNameSnapshot": record.name,
                        "role": role,
                        "source": source,
                    }
                )
            return rows

    def _require_subject_change_links(
        self, *, links: Sequence[Any], new_subject_id: str, what: str
    ) -> None:
        """学科变化时不得继承与**新学科**冲突的旧知识点关联（B2-RV07）。

        - 无旧关联 → 直接通过（学科改了也无需知识点库）；
        - 有旧关联 → 经公共 ``require_active_knowledge_references`` 只读核验
          （存在、修订归属、学科、未归档）：学科冲突 → 422
          ``KNOWLEDGE_REFERENCE_INVALID``，``details.issues`` 指向冲突知识点，
          文案要求显式替换或清空；已归档 → 409 ``KNOWLEDGE_ARCHIVED``
          （不把失效引用悄悄带进新修订）。
        """
        refs = [
            KnowledgeReference(
                knowledge_point_id=link.knowledge_point_id,
                knowledge_revision_id=link.knowledge_revision_id,
            )
            for link in links
        ]
        if not refs:
            return
        catalog = self._require_knowledge_catalog()
        try:
            require_active_knowledge_references(
                catalog, refs, expected_subject_id=new_subject_id or None
            )
        except AppError as exc:
            if exc.code != KNOWLEDGE_REFERENCE_INVALID:
                raise
            raise AppError(
                f"改{what}学科后不能继承与新学科不一致的旧知识点关联；"
                "请显式提供 knowledgeLinks（替换为新学科知识点或清空）后再提交。",
                code=KNOWLEDGE_REFERENCE_INVALID,
                status_code=422,
                details=error_details(
                    issues=self._subject_conflict_issues(
                        catalog,
                        refs,
                        new_subject_id=new_subject_id,
                        code=exc.code,
                    )
                ),
            ) from exc

    @staticmethod
    def _subject_conflict_issues(
        knowledge_catalog: Any,
        refs: Sequence[KnowledgeReference],
        *,
        new_subject_id: str,
        code: str,
    ) -> list[ErrorIssue]:
        """逐条列出与新学科冲突的关联（错误路径的只读补充，定位到具体知识点）。"""
        if not new_subject_id:
            return []
        snapshots = read_knowledge_snapshots(knowledge_catalog, refs)
        issues: list[ErrorIssue] = []
        for index, ref in enumerate(refs):
            snapshot = snapshots.get(ref.knowledge_point_id)
            if snapshot is None or snapshot.subject_id == new_subject_id:
                continue
            issues.append(
                ErrorIssue(
                    field=f"knowledgeLinks[{index}].knowledgePointId",
                    code=code,
                    message=(
                        f"知识点 {snapshot.knowledge_point_id}（{snapshot.name}）属于学科 "
                        f"{snapshot.subject_id}，与新学科 {new_subject_id} 不一致；"
                        "请显式替换或清空该关联。"
                    ),
                )
            )
            if len(issues) >= 8:  # details 不刷屏：最多列 8 条，其余同类
                break
        return issues

    def _draft_link_rows(
        self, links: Sequence[tuple[str, str]], *, subject_id: str
    ) -> list[dict[str, str]]:
        return self._link_rows(links, subject_id=subject_id, source="human")

    async def _resolve_handle(self, model_profile_id: str) -> ChatModelHandle:
        """解析聊天模型句柄；未装配解析器一律 503（可重试），不建任务。

        解析器内部的 profile 存在性/用途/连接可调用性校验由共享实现完成，
        失败原因（404/400/422）原样上抛，消息可读且不含凭证。

        解析出句柄后即做**云端闸门**（2026-10-07 用户裁定：题库 AI 不使用本机模型）：
        ``organize`` 与 ``create_generation_job`` 都在建任务之前先经此处，
        本机供应商（Ollama/vLLM/LM Studio 等）在受理阶段一律 422
        ``QUESTION_MODEL_NOT_CLOUD``——不建任务、不发起任何上游请求。
        判定照抄教案生成（``services.lesson_generation.preparation``）：
        ``find_provider(handle.config.providerId).is_local``；providerId 无法识别时
        不做本机假设，放行由后续连接校验处理。
        """
        if self.model_resolver is None:
            raise AppError(
                "题库 AI 整理未装配模型解析器（model_resolver），无法调用聊天模型；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        profile_id = (model_profile_id or "").strip()
        if not profile_id:
            raise AppError(
                "请先选择用于整理的聊天模型（modelProfileId 不能为空）。",
                code="MODEL_PROFILE_NOT_FOUND",
                status_code=404,
            )
        handle = await _threaded(self.model_resolver, profile_id)
        if not isinstance(handle, ChatModelHandle):
            raise AppError(
                "模型解析器返回的句柄不符合契约，已停止整理。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
            )
        # 题库 AI 只允许云端模型：本机部署不参与整理与补题（与教案生成同口径）
        spec = find_provider(handle.config.providerId) if handle.config.providerId else None
        if spec is not None and spec.is_local:
            raise AppError(
                QUESTION_MODEL_NOT_CLOUD_MESSAGE,
                code=QUESTION_MODEL_NOT_CLOUD,
                status_code=422,
                details={"issues": [{
                    "field": "modelProfileId",
                    "code": QUESTION_MODEL_NOT_CLOUD,
                    "message": QUESTION_MODEL_NOT_CLOUD_MESSAGE,
                }]},
            )
        return handle

    async def _resolve_frozen_handle(self, snapshot: Any) -> ChatModelHandle:
        """按**冻结快照**（profileId + fingerprint）解析并核对真实配置指纹（B2-RV04）。

        - 生产装配注入模型仓储 + 凭证时走共享 ``resolve_frozen_model``（唯一实现）；
          隔离装配只注入 ``model_resolver`` 时，用它解析后按 ``fingerprint_of_handle``
          重算比对（缺指纹 422 / 漂移 409 与共享实现同一判定与错误码）；
        - 无论哪条路径都在**模型调用前**完成核对：漂移时零调用、零发布，
          调用与来源记录使用同一个模型（不把新模型的输出记成旧指纹）。
        """
        frozen = _frozen_snapshot_fields(snapshot)
        if self._frozen_model_resolver is not None:
            return await _threaded(self._frozen_model_resolver, frozen)
        if self.model_resolver is None:
            raise AppError(
                "题库模型解析器（model_resolver）未装配，无法恢复任务；"
                "请检查后端启动配置。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        handle = await _threaded(self.model_resolver, frozen["profileId"])
        if not isinstance(handle, ChatModelHandle):
            raise AppError(
                "模型解析器返回的句柄不符合契约，已停止任务。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
            )
        if fingerprint_of_handle(handle) != frozen["fingerprint"]:
            raise AppError(
                MODEL_CONFIG_DRIFT_MESSAGE,
                code=MODEL_CONFIG_DRIFT,
                status_code=409,
            )
        return handle

    async def _require_current_lease(self, frozen: FrozenJob) -> JobLeaseIdentity:
        """本执行轮开始时的租约身份（B2-RV05）；失权/过期/收敛 → 409 且不写任何结果。

        执行器必须把这份身份带进每一次中间批提交：它证明"这批结果属于我这一轮"，
        不能在每个批次前重读当前行租约（重读会拿到接管者的凭据）。
        """
        lease = await _threaded(self.catalog.job_lease_identity, frozen.job_id)
        if lease is None or lease.attempt != frozen.attempt:
            raise AppError(
                "任务租约已失效（被接管、过期或已收敛），本次执行不写入任何结果。",
                code="LEASE_LOST",
                status_code=409,
            )
        return lease

    async def _ensure_lease(self, job_id: str, lease: JobLeaseIdentity) -> None:
        """批次之间的只读预检：租约已被接管/过期时立即停止，不做无谓模型调用。"""
        current = await _threaded(self.catalog.job_lease_identity, job_id)
        if current != lease:
            raise AppError(
                "任务租约已失效（被接管、过期或已收敛），本次执行不写入任何结果。",
                code="LEASE_LOST",
                status_code=409,
            )

    # ------------------------------------------------------------------ 导入

    def create_import(
        self,
        *,
        file_name: str,
        data: bytes,
        subject_id: str = "",
        grade_id: str = "",
        owner_id: str | None = None,
    ) -> QuestionImportDetail:
        name = (file_name or "").strip()
        if not name:
            raise _invalid("上传文件名不能为空。")
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise _invalid(
                f"不支持的题目文件类型「{suffix or name}」：仅支持 .md / .txt / .pdf / .docx。",
                code="UNSUPPORTED_DOCUMENT_FORMAT",
            )
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppError(
                f"单个文件不得超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB。",
                code="DOCUMENT_TOO_LARGE",
                status_code=413,
            )
        # 文件落盘在事务外：内容寻址写入 blobs/<sha256>
        blob_id, size = self.blobs.write(data)
        record = self.catalog.create_import(
            owner_id=owner_id or self.owner_id,
            file_sha256=blob_id,
            original_blob_id=blob_id,
            uploaded_file_name=name,
            uploaded_bytes=size,
            state="extracting",
        )
        warnings: list[str] = []
        try:
            parsed = self.parser(
                path=self.blobs.path_of(blob_id),
                file_name=name,
                parser_version=PARSER_VERSION,
                allow_empty_text=True,
            )
        except AppError as exc:
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code=exc.code,
                warnings=[str(exc)],
            )
            return self.get_import_detail(record.import_id)
        except Exception as exc:  # noqa: BLE001 - 解析层未预期异常也要留痕，不伪装成功
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code="DOCUMENT_PARSE_FAILED",
                warnings=[f"解析失败：{exc.__class__.__name__}"],
            )
            return self.get_import_detail(record.import_id)

        warnings.extend(parsed.warnings)
        blocks = self._parsed_blocks(parsed)
        if not any(block.text.strip() for block in blocks):
            # 扫描件与空文档都走这一支：不产生任何草稿，也不假装完成
            if parsed.needs_ocr:
                code = "DOCUMENT_NEEDS_OCR"
                warnings.append("该文件没有文本层（疑似扫描件），需要 OCR 后才能拆题。")
            else:
                code = "DOCUMENT_EMPTY"
                warnings.append("该文件没有可提取的文本内容，无法拆题。")
            if blocks:
                self.catalog.add_source_blocks(record.import_id, blocks)
            self.catalog.update_import(
                record.import_id,
                expected_revision=record.revision,
                state="failed",
                error_code=code,
                warnings=warnings,
            )
            return self.get_import_detail(record.import_id)

        stored = self.catalog.add_source_blocks(record.import_id, blocks)
        split = rules.split_questions(rules.blocks_from_records(stored))
        drafts = [
            self._draft_input(
                draft.content,
                draft.source_spans,
                metadata=self._default_metadata(subject_id=subject_id, grade_id=grade_id),
                warnings=draft.warnings,
                extraction_method="rule",
            )
            for draft in split
        ]
        if drafts:
            self.catalog.create_drafts(record.import_id, drafts)
        else:
            warnings.append("未识别到任何题号起始行，原文已全部保留为未归属块，请人工整理。")
        self.catalog.update_import(
            record.import_id,
            expected_revision=record.revision,
            state="needs_review",
            warnings=warnings,
        )
        return self.get_import_detail(record.import_id)

    def get_import_detail(self, import_id: str) -> QuestionImportDetail:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        drafts = self.catalog.list_drafts(import_id)
        blocks = self.catalog.list_source_blocks(import_id)
        links = self.catalog.draft_knowledge_links_by_import(import_id)
        unassigned = [block for block in blocks if not self._is_assigned(block, drafts)]
        detail = views.import_detail(
            record, drafts=drafts, unassigned=unassigned, links_by_draft=links
        )
        return detail.model_copy(update={
            "drafts": [self._duplicate_preview(draft) for draft in detail.drafts],
        })

    def list_imports(self, *, limit: int = DEFAULT_IMPORT_LIMIT) -> QuestionImportList:
        if limit < 1 or limit > MAX_IMPORT_LIMIT:
            raise _invalid(f"limit 必须在 1..{MAX_IMPORT_LIMIT} 之间。")
        summaries = []
        for record in self.catalog.list_imports(limit=limit):
            drafts = self.catalog.list_drafts(record.import_id)
            blocks = self.catalog.list_source_blocks(record.import_id)
            summaries.append(
                views.import_summary(
                    record,
                    draft_count=len(drafts),
                    reviewed_count=sum(1 for draft in drafts if draft.review_state == "reviewed"),
                    unassigned_count=sum(
                        1 for block in blocks if not self._is_assigned(block, drafts)
                    ),
                )
            )
        return QuestionImportList(imports=summaries)

    def discard_import(self, import_id: str, body: QuestionImportDiscardRequest) -> QuestionImportDetail:
        """放弃未确认批次（误上传清理）：状态置 ``cancelled``，批次/原文/草稿行保留。

        与名单批次 ``discard_roster_import`` 语义一致：已确认批次不可放弃（历史与已入库
        题目不动）；重复放弃按幂等返回当前状态；``expectedRevision`` 不符走既有 409 冲突。
        """
        with self.catalog.write_transaction() as conn:
            record = self.catalog.import_in(conn, import_id)
            if record is None:
                raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
            if record.state == "confirmed":
                raise _conflict(
                    "该导入已确认入库，不能放弃；已入库的题目保留。",
                    code="IMPORT_ALREADY_CONFIRMED",
                )
            if record.revision != body.expectedRevision:
                raise _conflict(
                    f"导入已被其他操作更新（当前 revision={record.revision}），请刷新后重试。",
                    code="REVISION_CONFLICT",
                )
            if record.state != "cancelled":
                self.catalog.set_import_state_in(conn, import_id, state="cancelled")
        return self.get_import_detail(import_id)

    def delete_import(self, import_id: str) -> QuestionImportDeleteResult:
        """彻底删除一个导入批次及其解析产物（与「放弃」的语义区分见下）。

        - **放弃**（``discard_import``）：保留批次/原文/草稿行，状态置 ``cancelled``，
          供审计与追溯；本方法则把批次与解析产物从库里移除；
        - 守卫在**同一写事务内**判定（与删除原子，杜绝守卫通过后并发确认入库）：
          已确认批次（正式题源自它）→ 409 ``IMPORT_ALREADY_CONFIRMED``；
          草稿被正式题引用（``question_sources.import_id`` 指向本批次或草稿带有
          并入记录）→ 409 ``IMPORT_IN_USE``，``details`` 带引用计数；
        - 通过后按 FK 顺序删除：建议 → 草稿关联 → 原文块 → 草稿 → 来源登记 → 批次行；
          触发器核对：题库仅 ``question_knowledge_links``（题目修订关联）带不可变
          触发器，本路径不触碰该表；
        - **受管原件（``blobs/<sha256>``）不物理删除**：内容寻址、可能被其他批次复用，
          回执只声明删除了库行；原件清理属于独立策略，不在本接口承诺范围内。
        """
        counts = self.catalog.delete_import(import_id)
        logger.info(
            "彻底删除题库导入批次 %s：%s；受管原件（blobs）保留待清理策略。",
            import_id,
            counts,
        )
        return QuestionImportDeleteResult(deleted=True, importId=import_id)

    # ------------------------------------------------------------------ 草稿

    def patch_draft(self, draft_id: str, body: DraftPatchRequest) -> DraftView:
        record = self.catalog.get_draft(draft_id)
        if record is None:
            raise _not_found("草稿不存在。", code="DRAFT_NOT_FOUND")
        rich.validate_projection(body.content, previous=record.content)
        self._verify_new_assets(body.content, previous=record.content)
        content = body.content.model_dump(mode="json")
        link_rows: list[dict[str, str]] | None = None
        if body.knowledgeLinks is not None:
            # 提供即整表替换：[] 清空；知识点只读校验走公共发布路径（同学科/未归档/修订一致）
            link_rows = self._draft_link_rows(
                validation.parse_knowledge_links(body.knowledgeLinks),
                subject_id=body.metadata.subjectId,
            )
        elif body.metadata.subjectId != str((record.metadata or {}).get("subjectId") or ""):
            # 学科变化且未显式给关联：不得无条件继承与新学科冲突的旧关联（B2-RV07）
            self._require_subject_change_links(
                links=self.catalog.draft_knowledge_links(draft_id),
                new_subject_id=body.metadata.subjectId,
                what="草稿",
            )
        updated = self.catalog.update_draft(
            draft_id,
            expected_revision=body.expectedRevision,
            content=content,
            metadata=body.metadata.model_dump(mode="json"),
            review_state=body.reviewState,
            missing_answer_acknowledged=body.missingAnswerAcknowledged,
            content_fingerprint=fp.content_fingerprint(content),
            knowledge_links=link_rows,
        )
        return self._draft_view(updated)

    def _draft_view(self, record: DraftRecord) -> DraftView:
        links = self.catalog.draft_knowledge_links(record.draft_id)
        return self._duplicate_preview(views.draft_view(record, links=links))

    def _duplicate_questions(self, content: Mapping[str, Any], *, conn: Any = None) -> list[Any]:
        """预览与确认共用权威题面口径；历史候选仅从冻结内容纯计算。"""
        identity = fp.duplicate_content_fingerprint(content)
        if conn is None:
            candidates = self.catalog.find_questions_by_surface(
                self.owner_id, algorithm_version=fp.DUPLICATE_ALGORITHM_VERSION, fingerprint=identity
            )
        else:
            candidates = self.catalog.questions_by_surface_in(
                conn, self.owner_id, algorithm_version=fp.DUPLICATE_ALGORITHM_VERSION, fingerprint=identity
            )
        return [question for question in candidates
                if fp.duplicate_content_fingerprint(question.content) == identity]

    def _duplicate_preview(self, draft: DraftView) -> DraftView:
        # 已消费草稿保留其来源合并事实；其余草稿不沿用过时的 duplicate 指针。
        if draft.reviewState == "excluded":
            return draft
        content = draft.content.model_dump(mode="json")
        duplicates = self._duplicate_questions(content)
        warnings = list(draft.warnings)
        if duplicates:
            warning = "权威题面与已有题目相同；答案和解析不作为新题条件，请复核后选择跳过或合并来源。"
            if warning not in warnings:
                warnings.append(warning)
            if any(fp.canonical_json(question.content.get("answer")) != fp.canonical_json(content.get("answer"))
                   for question in duplicates):
                warnings.append("重复题的答案不同，需教师复核；已有题答案不会被本次确认覆盖，候选答案保留在草稿。")
        return draft.model_copy(update={
            "duplicateOfQuestionId": duplicates[0].question_id if duplicates else None,
            "warnings": warnings,
        })

    def split_draft(
        self,
        import_id: str,
        body: DraftSplitRequest,
        *,
        draft_id: str | None = None,
    ) -> QuestionImportDetail:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        _require_operable_import(record, operation="拆分草稿")
        drafts = self.catalog.list_drafts(import_id)
        target = self._resolve_split_target(drafts, draft_id=draft_id, char_offset=body.charOffset)
        if target.review_state == "excluded":
            raise _conflict("已排除的草稿不能拆分。", code="DRAFT_EXCLUDED")
        if target.revision != body.expectedRevision:
            raise _conflict(
                f"草稿已被其他操作更新（当前 revision={target.revision}），请刷新后重试。",
                code="REVISION_CONFLICT",
            )
        self._require_markdown_operation(target, operation="拆分")
        blocks = self.catalog.list_source_blocks(import_id)
        lines = [
            line
            for line in rules.lines_from_blocks(rules.blocks_from_records(blocks))
            if rules.line_touches_spans(line, target.source_spans)
        ]
        if not lines:
            raise _invalid("草稿没有可定位的原文区间，无法拆分。", code="DRAFT_SPAN_EMPTY")
        start = min(line.char_start for line in lines)
        end = max(line.char_end for line in lines)
        if not start < body.charOffset < end:
            raise _invalid(
                f"charOffset 必须落在草稿原文区间内（{start}..{end}）。"
            )
        left_lines, right_lines = rules.cut_lines(lines, body.charOffset)
        left = self._split_half(left_lines)
        right = self._split_half(right_lines)
        # 关联口径：拆出的两道草稿**不继承**原关联（覆盖范围已变），一律明确提示；
        # 被替代的旧草稿行保留原关联，供追溯。
        note = (LINK_CLEARED_NOTE,)
        self.catalog.replace_draft_set(
            import_id,
            excluded=[(target.draft_id, target.revision, SPLIT_NOTE)],
            created=[
                self._draft_input(
                    left.content,
                    left.source_spans,
                    metadata=dict(target.metadata),
                    warnings=(*left.warnings, *note),
                    extraction_method="manual",
                ),
                self._draft_input(
                    right.content,
                    right.source_spans,
                    metadata=dict(target.metadata),
                    warnings=(*right.warnings, *note),
                    extraction_method="manual",
                ),
            ],
        )
        return self.get_import_detail(import_id)

    def merge_drafts(self, import_id: str, body: DraftMergeRequest) -> QuestionImportDetail:
        record = self.catalog.get_import(import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        _require_operable_import(record, operation="合并草稿")
        by_id = {draft.draft_id: draft for draft in self.catalog.list_drafts(import_id)}
        if len(body.expectedRevisions) < 2:
            raise _invalid("合并至少需要两道草稿。")
        chosen: list[DraftRecord] = []
        for draft_id, expected_revision in body.expectedRevisions.items():
            draft = by_id.get(draft_id)
            if draft is None:
                raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
            if draft.review_state == "excluded":
                raise _conflict("已排除的草稿不能参与合并。", code="DRAFT_EXCLUDED")
            if draft.revision != expected_revision:
                raise _conflict(
                    f"草稿已被其他操作更新（当前 revision={draft.revision}），请刷新后重试。",
                    code="REVISION_CONFLICT",
                )
            self._require_markdown_operation(draft, operation="合并")
            chosen.append(draft)
        chosen.sort(key=lambda draft: self._draft_start(draft))
        merged_content = self._merge_content([draft.content for draft in chosen])
        merged_spans = self._merge_spans([draft.source_spans for draft in chosen])
        # 同拆分口径：合并后的草稿不继承任何一方的关联（覆盖范围已变），一律明确提示
        warnings = ["已由多道草稿合并，需重新校对。", LINK_CLEARED_NOTE]
        self.catalog.replace_draft_set(
            import_id,
            excluded=[(draft.draft_id, draft.revision, MERGE_NOTE) for draft in chosen],
            created=[
                self._draft_input(
                    merged_content,
                    merged_spans,
                    metadata=dict(chosen[0].metadata),
                    warnings=tuple(warnings),
                    extraction_method="manual",
                )
            ],
        )
        return self.get_import_detail(import_id)

    # ------------------------------------------------------------- AI 整理

    async def organize(self, import_id: str, body: OrganizeRequest) -> OrganizeJobView:
        """建任务并立即执行：模型在「点击整理」这一刻解析并冻结进 checkpoint。

        顺序：① 导入状态闸门；② **模型闸门**（未注入 resolver / profile 不存在 / 不可调用
        → 立即失败，不建任务、0 次上游调用）；③ 取目标草稿与原文块；④ 按输入预算打包；
        ⑤ 建任务并逐批执行。全程 SQL 走有界线程，模型调用在 SQL 写事务之外。
        """
        record = await _threaded(self.catalog.get_import, import_id)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        if record.state == "failed":
            raise _invalid("该导入解析失败，不能进行 AI 整理。", code="IMPORT_PARSE_FAILED")
        if record.state == "cancelled":
            raise _conflict("该导入已取消，不能进行 AI 整理。", code="IMPORT_CANCELLED")
        if record.state == "confirmed":
            raise _conflict(
                "该导入已确认入库，不能再次发起 AI 整理。", code="IMPORT_ALREADY_CONFIRMED"
            )
        # 模型闸门先于取草稿：配置不对时立即失败，不建任务、不发上游、不回显请求原文
        handle = await self._resolve_handle(body.modelProfileId)
        all_drafts = await _threaded(self.catalog.list_drafts, import_id)
        selected = self._select_drafts(all_drafts, body.draftIds)
        blocks = await _threaded(self.catalog.list_source_blocks, import_id)
        draft_blocks = {
            draft.draft_id: [block for block in blocks if self._intersects(draft, block)]
            for draft in selected
        }
        if body.includeUnassigned:
            self._attach_unassigned(draft_blocks, selected, all_drafts, blocks)
        batches: list[Batch] = []
        for draft in selected:
            chunk = [(block.block_id, block.text) for block in draft_blocks[draft.draft_id]]
            if not chunk:
                continue
            batches.extend(pack_batches(draft.draft_id, chunk, start_index=len(batches)))
        if not batches:
            raise _invalid(
                "所选草稿没有可整理的原文块；请检查草稿来源区间。",
                code="ORGANIZE_TARGET_EMPTY",
            )
        frozen_input = self._new_checkpoint(handle, body=body, selected=selected, batches=batches)
        store = self._store()
        job = await _threaded(
            store.create,
            kind="organize",
            frozen_input=frozen_input,
            model_snapshot={
                "profileId": handle.profile_id,
                "fingerprint": str(frozen_input["modelFingerprint"]),
            },
            owner_id=self.owner_id,
        )
        # 同步执行并返回终态视图（既有 URL 与响应形状不变）；模型名额经统一引擎
        final = await self._run_engine_job(
            job.job_id, self._organize_executor_factory(model=handle)
        )
        return await _threaded(self._job_view, final)

    def _new_checkpoint(
        self,
        model: ChatModelHandle,
        *,
        body: OrganizeRequest,
        selected: Sequence[DraftRecord],
        batches: Sequence[Batch],
    ) -> dict[str, Any]:
        """冻结本次任务的模型身份与批次快照；只写 profile id 与**非敏感**指纹。"""
        return {
            "contractVersion": ORGANIZE_CONTRACT_VERSION,
            "modelProfileId": model.profile_id,
            "modelFingerprint": fingerprint_of_handle(model),
            "includeUnassigned": bool(body.includeUnassigned),
            "instruction": ORGANIZE_INSTRUCTION,
            "drafts": [
                {"draftId": draft.draft_id, "revision": draft.revision} for draft in selected
            ],
            "batches": batch_snapshot(batches),
            "nextBatchIndex": 0,
            "suggestionIds": [],
            "failedBatches": [],
        }

    @staticmethod
    def _output_budget(model: ChatModelHandle) -> int:
        """输出预算 = min(组织者上限, 所选模型的输出上限)。"""
        limit = model.max_output_tokens
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return MAX_OUTPUT_TOKENS
        return min(MAX_OUTPUT_TOKENS, limit)

    async def _call_model(
        self,
        model: ChatModelHandle,
        instruction: str,
        batch: Batch,
        max_output_tokens: int,
    ) -> LLMResponse:
        """一次非流式模型调用；未开始任何 SQL 写事务，取消可直接传播。"""
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=instruction),
                LLMMessage(role="user", content=batch.input_text),
            ],
            maxOutputTokens=max_output_tokens,
            params={},
        )
        return await model.provider.complete(model.config, request)

    async def _record_task_level_failure(
        self, job_id: str, code: str, *, lease: JobLeaseIdentity,
        message: str | None = None
    ) -> None:
        """任务级失败落库**前**的可读原因：写进 checkpoint 的 ``jobError``（旧界面语义）。

        统一引擎仍会把同一 ``code``/``message`` 落 ``error_json``（``JobView.error``）；
        两处同源，视图 ``errorCode`` 取引擎的错误码，界面文案不丢。
        ``message`` 由调用方给出时原样落库（如模型漂移的明确说明）。
        """
        await _threaded(
            self.catalog.record_organize_failure, job_id,
            code=code, message=message or job_level_message(code),
            lease_attempt=lease.attempt, lease_token=lease.token,
        )

    def _organize_contract(
        self, frozen: FrozenJob, checkpoint: dict[str, Any]
    ) -> dict[str, Any] | None:
        """本次执行使用的整理契约：优先**冻结输入**，兼容落在 checkpoint 里的历史行。"""
        if is_current_checkpoint(frozen.input):
            return dict(frozen.input)
        if is_current_checkpoint(checkpoint):
            return dict(checkpoint)
        return None

    async def _run_engine_job(self, job_id: str, executor: Any) -> Any:
        """发布异常由唯一引擎用原 JobLease 收敛；域服务不冒用当前行租约。"""
        return await self.job_engine.run_job(
            "question", job_id, executor, uses_model=True
        )

    def _organize_executor_factory(self, *, model: ChatModelHandle | None):
        """构造执行器：``model`` 非空 = 点击时冻结的句柄；恢复路径传 ``None`` 重新解析。"""

        async def executor(frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
            # 本执行轮的租约身份（B2-RV05）：之后每一批提交都带它做 CAS；失权即停
            lease = await self._require_current_lease(frozen)
            job = await _threaded(self.catalog.get_job, frozen.job_id)
            if job is None:
                raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
            checkpoint = dict(job.checkpoint)
            contract = self._organize_contract(frozen, checkpoint)
            if contract is None:
                # 旧语义 checkpoint：不猜模型、不伪造指纹；已产生的建议一条不动
                raise AppError(
                    RESELECT_MODEL_MESSAGE,
                    code=RESELECT_MODEL_CODE,
                    status_code=409,
                )
            handle = model
            if handle is None:
                # 恢复/重试：用**冻结输入**里的 profile id + 指纹重新解析并核对（RV04）；
                # 漂移时在模型调用前失败，来源与执行不会不一致
                try:
                    handle = await self._resolve_frozen_handle(
                        {
                            "profileId": contract.get("modelProfileId"),
                            "fingerprint": contract.get("modelFingerprint"),
                        }
                    )
                except AppError as exc:
                    if exc.code in (MODEL_CONFIG_DRIFT, MODEL_FINGERPRINT_MISSING):
                        await self._record_task_level_failure(
                            frozen.job_id, exc.code, lease=lease, message=str(exc)
                        )
                        raise AppError(
                            str(exc), code=exc.code, status_code=exc.status_code
                        ) from exc
                    code = job_level_error_code(exc.code)
                    await self._record_task_level_failure(frozen.job_id, code, lease=lease)
                    raise AppError(
                        job_level_message(code), code=code, status_code=exc.status_code
                    ) from exc
            batches = [batch_from_snapshot(item) for item in contract.get("batches", [])]
            drafts_snapshot = {
                str(item.get("draftId")): int(item.get("revision", 0))
                for item in contract.get("drafts", [])
            }
            instruction = str(contract.get("instruction") or ORGANIZE_INSTRUCTION)
            start = int(checkpoint.get("nextBatchIndex", 0))
            max_output_tokens = self._output_budget(handle)
            for index in range(start, len(batches)):
                if await ctx.cancellation_requested():
                    # 取消优先：不调用模型、不写建议；引擎随后置 cancelled
                    return JobOutcome(result={"cancelled": True, "suggestionCount": 0})
                # 失权预检：已失权/过期时不继续消耗模型，也不产生"零写入的批次"
                await self._ensure_lease(frozen.job_id, lease)
                batch = batches[index]
                base_revision = drafts_snapshot.get(batch.draft_id, 0)
                try:
                    response = await self._call_model(
                        handle, instruction, batch, max_output_tokens
                    )
                    if response.finishReason == FINISH_LENGTH:
                        raise output_truncated_error()
                    parsed = normalize_reply(response.text, batch.block_ids)
                except AppError as exc:
                    if exc.code in BATCH_LEVEL_ORGANIZER_ERRORS:
                        await self._write_organize_batch(
                            frozen.job_id,
                            index=index,
                            batch=batch,
                            base_revision=base_revision,
                            lease=lease,
                            failure={"index": index, "code": exc.code, "message": str(exc)},
                        )
                        continue
                    # 模型服务问题（认证/限流/网络/协议/配置）：整条任务失败
                    code = job_level_error_code(exc.code)
                    await self._record_task_level_failure(frozen.job_id, code, lease=lease)
                    raise AppError(
                        job_level_message(code), code=code, status_code=exc.status_code
                    ) from exc
                if await ctx.cancellation_requested():
                    return JobOutcome(result={"cancelled": True, "suggestionCount": 0})
                await self._ensure_lease(frozen.job_id, lease)
                await self._write_organize_batch(
                    frozen.job_id,
                    index=index,
                    batch=batch,
                    base_revision=base_revision,
                    lease=lease,
                    proposed_content=parsed["content"],
                    source_block_ids=parsed["source_block_ids"],
                )
                if await ctx.cancellation_requested():
                    # 取消发生在写入窗口内：该批已按事务语义落库，但不再继续后续批次
                    return JobOutcome(result={"cancelled": True, "suggestionCount": 0})
            settled = await _threaded(self.catalog.get_job, frozen.job_id)
            if settled is None:
                raise _not_found("整理任务不存在。", code="JOB_NOT_FOUND")
            suggestions = list(settled.checkpoint.get("suggestionIds") or [])
            failures = list(settled.checkpoint.get("failedBatches") or [])
            if suggestions:
                return JobOutcome(
                    result={
                        "suggestionCount": len(suggestions),
                        "failedBatches": len(failures),
                    }
                )
            # 一条可应用建议都没有：整条任务按失败收尾（错误码取最后一类批级失败）
            code = str(failures[-1].get("code")) if failures else "ORGANIZE_NO_SUGGESTION"
            if failures:
                message = (
                    f"全部批次整理失败（{code}）：原文保留、草稿不变；"
                    "请检查原文或改选模型后重试。"
                )
            else:
                message = "整理未产生任何可应用建议；原文保留、草稿不变。"
            raise AppError(message, code=code, status_code=422)

        return executor

    async def _write_organize_batch(
        self,
        job_id: str,
        *,
        index: int,
        batch: Batch,
        base_revision: int,
        lease: JobLeaseIdentity,
        proposed_content: dict[str, Any] | None = None,
        source_block_ids: Sequence[str] = (),
        failure: dict[str, Any] | None = None,
    ) -> None:
        """短事务写入一批：建议 + checkpoint 进度；取消/失权时一个字节都不写。

        ``lease`` 是本执行轮开始时取得的租约身份（B2-RV05）：仓储在同一事务里核对
        任务状态、attempt/token 与租约过期时间，旧 attempt 与迟到批次零写入。
        """
        _job_now, _created, _effective = await _threaded(
            self.catalog.record_organize_batch,
            job_id,
            batch_index=index,
            next_batch_index=index + 1,
            draft_id=batch.draft_id,
            base_draft_revision=base_revision,
            proposed_content=proposed_content,
            source_block_ids=source_block_ids,
            failure=failure,
            lease_attempt=lease.attempt,
            lease_token=lease.token,
        )

    async def run_organize_job(
        self, job_id: str, *, model: ChatModelHandle | None = None
    ) -> OrganizeJobView:
        """执行/续跑一个整理任务；崩溃后从 checkpoint 续跑，不重复已提交的批次。

        - ``model`` 由 ``organize`` 传入（点击时冻结的句柄）；恢复路径传 ``None``，
          用冻结输入里的 ``modelProfileId`` 重新解析（配置失效 → 任务失败并给可读原因）；
        - 每批的模型调用在 SQL 写事务之外；建议写入与进度推进在**同一个短事务**内完成；
        - 任务级失败（认证/限流/网络）整条任务失败，不记成「批内容失败」；
        - 旧语义 checkpoint（``contractVersion`` 不是 2 / 缺 profile 与指纹）不自动恢复。
        """
        record = await _threaded(self._store().get, job_id)
        if record.state in TERMINAL_JOB_STATES and record.state not in RECOVERABLE_JOB_STATES:
            # succeeded（结果已发布）与 cancelled（取消是显式决定）不复活
            return await _threaded(self._job_view, record)
        contract = self._organize_contract_from_record(record)
        if contract is None:
            stale = await _threaded(
                self.catalog.fail_organize_job,
                job_id,
                error_code=RESELECT_MODEL_CODE,
                message=RESELECT_MODEL_MESSAGE,
                checkpoint={**record.checkpoint, "needsModelReselection": True},
            )
            return await _threaded(self._job_view, stale)
        final = await self._run_engine_job(
            job_id, self._organize_executor_factory(model=model)
        )
        return await _threaded(self._job_view, final)

    def _organize_contract_from_record(self, record: Any) -> dict[str, Any] | None:
        """从统一引擎记录里取整理契约（冻结输入优先，兼容历史 checkpoint）。"""
        if is_current_checkpoint(record.frozen_input):
            return dict(record.frozen_input)
        if is_current_checkpoint(record.checkpoint):
            return dict(record.checkpoint)
        return None

    async def recover_organize_jobs(self, *, max_jobs: int = 8) -> int:
        """**显式恢复**：只对 ``interrupted``/``failed`` 的任务重跑；不自动重叫模型。

        - 启动收敛（遗留 ``running → interrupted``）由 ``main.py`` 的
          ``RECONCILE_DOMAINS`` 负责，本入口只在教师显式点「重试」时调用；
        - 旧语义 checkpoint 不重跑：标记需重新选择模型，已产生的建议一条不动；
        - 每次恢复都经 ``JobStore.retry`` → ``engine.run_job``（保留冻结输入与模型指纹，
          ``claim`` 递增 attempt）；单条恢复失败不影响其他任务。
        """
        store = self._store()
        records = await _threaded(store.list_recent, limit=max_jobs * 4)
        candidates = [
            record
            for record in records
            if record.kind == "organize" and record.state in RECOVERABLE_JOB_STATES
        ][:max_jobs]
        recovered = 0
        for record in candidates:
            if self._organize_contract_from_record(record) is None:
                await _threaded(
                    self.catalog.fail_organize_job,
                    record.job_id,
                    error_code=RESELECT_MODEL_CODE,
                    message=RESELECT_MODEL_MESSAGE,
                    checkpoint={**record.checkpoint, "needsModelReselection": True},
                )
                recovered += 1
                continue
            try:
                await _threaded(store.retry, record.job_id)
                await self.run_organize_job(record.job_id)
            except Exception:  # noqa: BLE001 - 单条恢复失败不影响其他任务
                logger.exception("恢复题库整理任务 %s 失败", record.job_id)
            recovered += 1
        return recovered

    def cancel_organize_job(self, job_id: str) -> OrganizeJobView:
        """协作式取消：``queued`` 立即 ``cancelled``；``running`` 只置标志（批间停）。"""
        record = self._store().request_cancel(job_id)
        return self._job_view(record)

    def get_organize_job(self, job_id: str) -> OrganizeJobView:
        record = self._store().get(job_id)
        return self._job_view(record)

    def job_record(self, job_id: str) -> Any:
        """统一引擎的任务记录（冻结输入/checkpoint/attempt/error），
        供恢复入口与测试检查；对外视图请用 ``get_organize_job`` /
        ``GET /workflow-jobs/{id}?domain=question``。"""
        return self._store().get(job_id)

    def list_suggestions(self, *, job_id: str | None = None, draft_id: str | None = None):
        records = self.catalog.list_suggestions(
            organization_job_id=job_id, target_draft_id=draft_id
        )
        return [views.suggestion_view(record) for record in records]

    def apply_suggestion(
        self, suggestion_id: str, body: SuggestionApplyRequest
    ) -> DraftView:
        if body.accept:
            suggestion = self.catalog.get_suggestion(suggestion_id)
            draft = self.catalog.get_draft(suggestion.target_draft_id) if suggestion else None
            if (
                suggestion is not None and suggestion.state == "pending" and draft is not None
                and draft.revision == body.expectedDraftRevision == suggestion.base_draft_revision
            ):
                self._require_markdown_operation(draft, operation="应用 AI 建议")
        warning = f"已应用 AI 建议 {suggestion_id}：内容需重新校对。"
        _suggestion, draft = self.catalog.apply_suggestion(
            suggestion_id,
            expected_draft_revision=body.expectedDraftRevision,
            accept=body.accept,
            warning=warning,
        )
        return self._draft_view(draft)

    # ------------------------------------------------------------- AI 补题

    async def create_generation_job(
        self, body: QuestionGenerationRequest
    ) -> GenerationJobView:
        """建 ``question:generate`` 任务并**后台调度**（202 语义：接受任务，不等结果）。

        顺序：① 知识点闸门（知识点库只读解析 + 同学科/未归档校验，失败不建任务）；
        ② 材料闸门（形状/预算/引用扫描）；③ **模型闸门**（解析 profile 并冻结非敏感指纹；
        未注入 resolver / profile 不存在 → 立即失败，不建任务、0 次上游调用）；
        ④ 建任务（冻结输入 + 模型快照）→ ⑤ ``schedule`` 执行；结果经
        ``GET /workflow-jobs/{id}?domain=question`` 观察。
        """
        subject_id = (body.subjectId or "").strip()
        knowledge: list[generation.KnowledgeSnapshot] = []
        if body.knowledgePointIds:
            records = await _threaded(
                self._knowledge_records, list(body.knowledgePointIds)
            )
            for point_id in body.knowledgePointIds:
                record = records.get(point_id)
                if record is None:
                    raise AppError(
                        f"知识点不存在：{point_id}。",
                        code=KNOWLEDGE_POINT_NOT_FOUND,
                        status_code=404,
                    )
                if record.status != "active":
                    raise AppError(
                        f"知识点已归档，不能用于补题：{point_id}。",
                        code=KNOWLEDGE_POINT_ARCHIVED,
                        status_code=422,
                    )
                knowledge.append(
                    generation.KnowledgeSnapshot(
                        point_id=record.point_id,
                        subject_id=record.subject_id,
                        code=record.code,
                        name=record.name,
                        revision_id=record.revision_id,
                    )
                )
            subjects = {item.subject_id for item in knowledge}
            if len(subjects) > 1:
                raise _invalid(
                    "一次补题不能跨学科选知识点；请只保留同一学科的知识点。",
                    code=KNOWLEDGE_SUBJECT_MISMATCH,
                )
            derived_subject = next(iter(subjects))
            if subject_id and subject_id != derived_subject:
                raise _invalid(
                    f"所选知识点属于学科 {derived_subject}，与 subjectId={subject_id} 不一致。",
                    code=KNOWLEDGE_SUBJECT_MISMATCH,
                )
            subject_id = subject_id or derived_subject
        materials = generation.material_entries(list(body.materials))
        # 模型闸门先于建任务：配置不对时立即失败，不建任务、不发上游
        handle = await self._resolve_handle(body.modelProfileId)
        store = self._store()
        record = await _threaded(
            store.create,
            kind="generate",
            frozen_input=generation.build_frozen_input(
                model_profile_id=handle.profile_id,
                subject_id=subject_id,
                knowledge=knowledge,
                question_types=list(body.questionTypes),
                difficulty=body.difficulty,
                count=body.count,
                instructions=(body.instructions or "").strip(),
                materials=materials,
                owner_id=self.owner_id,
            ),
            model_snapshot=generation.build_model_snapshot(handle),
            owner_id=self.owner_id,
        )
        self.job_engine.schedule(
            "question", record.job_id, self._generation_executor(), uses_model=True
        )
        return self._generation_view(record)

    async def run_generation_job(self, job_id: str) -> GenerationJobView:
        """执行/续跑一条补题任务（显式重试入口；发布仍与任务终态同事务）。"""
        record = await _threaded(self._store().get, job_id)
        if record.state == "succeeded":
            return self._generation_view(record)
        final = await self._run_engine_job(job_id, self._generation_executor())
        return self._generation_view(final)

    def generation_job_view(self, job_id: str) -> GenerationJobView:
        return self._generation_view(self._store().get(job_id))

    def _generation_executor(self) -> Callable[..., Any]:
        runner = generation.QuestionGenerationRunner(
            catalog=self.catalog,
            blobs=self.blobs,
            # 执行前按冻结快照核对真实配置指纹（RV04）：漂移 → 明确失败、零调用、零发布
            resolve_frozen_model=self._resolve_frozen_handle,
            resolve_knowledge=self._resolve_knowledge_snapshots,
            owner_id=self.owner_id,
        )
        return runner

    @staticmethod
    def _generation_view(record: Any) -> GenerationJobView:
        """六态 + attempt；``importId``/``candidateCount`` 只在发布成功后从结果读出。"""
        result = record.result if isinstance(record.result, dict) else {}
        import_id = result.get("importId")
        candidate_count = result.get("candidateCount")
        return GenerationJobView(
            jobId=record.job_id,
            state=record.state,  # type: ignore[arg-type]
            attempt=record.attempt,
            importId=import_id if isinstance(import_id, str) and import_id else None,
            candidateCount=(
                candidate_count
                if isinstance(candidate_count, int) and not isinstance(candidate_count, bool)
                else 0
            ),
            errorCode=record.error_code,
        )

    # ------------------------------------------------------------- 确认入库

    def confirm(self, body: QuestionConfirmRequest) -> ConfirmResult:
        """幂等确认入库；B2-RV06：新发布关联在发布协调器内**先复核再写**。

        顺序：跨库只读复核待冻结的草稿关联（存在、修订归属、同学科、未归档）→
        域内单事务（计划校验、题目/来源/关联冻结、submission、导入状态）。
        复核拒绝时不写任何一行；历史已确认关联的读取路径不变（不回溯重核）。
        """
        record = self.catalog.get_import(body.importId)
        if record is None:
            raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
        request_fingerprint = fp.request_fingerprint(
            {
                "importId": body.importId,
                "items": [
                    {
                        "draftId": item.draftId,
                        "expectedDraftRevision": item.expectedDraftRevision,
                    }
                    for item in body.items
                ],
                "duplicateResolutions": sorted(
                    (
                        {
                            "draftId": resolution.draftId,
                            "action": resolution.action,
                            "existingQuestionId": resolution.existingQuestionId,
                        }
                        for resolution in body.duplicateResolutions
                    ),
                    key=lambda item: item["draftId"],
                ),
            }
        )
        existing = self.catalog.get_submission(body.submissionId)
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise _conflict("同一提交键已登记不同载荷的确认请求。", code="IDEMPOTENCY_CONFLICT")
            return ConfirmResult.model_validate(existing.result)
        # 已放弃的批次不在可操作状态集合内；幂等重放在此之前返回，不受影响
        if record.state == "cancelled":
            raise _conflict("该导入已放弃，不能确认入库。", code="IMPORT_CANCELLED")
        # 真实字节与投影预检在发布锁和 SQL 写事务外；事务内只消费同一草稿版本的结果。
        prepared: dict[str, tuple[int, tuple[str, str] | AppError]] = {}
        for item in body.items:
            draft = self.catalog.get_draft(item.draftId)
            if draft is None or draft.import_id != body.importId or draft.revision != item.expectedDraftRevision:
                continue
            try:
                prepared[draft.draft_id] = (draft.revision, self._derived_fingerprint(draft.content))
            except AppError as exc:
                prepared[draft.draft_id] = (draft.revision, exc)
        with self._publication("question.confirm"):
            # 幂等重放优先：同一 submissionId 的记录是既有事实，不再要求当时引用的
            # 知识点仍活跃（历史已确认关联不回溯重核）；只有真正要写的新确认才复核。
            existing = self.catalog.get_submission(body.submissionId)
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise _conflict(
                        "同一提交键已登记不同载荷的确认请求，拒绝复用原结果。",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return ConfirmResult.model_validate(existing.result)
            self._recheck_confirm_links(body)
            return self._confirm_in_transaction(body, request_fingerprint, prepared)

    def _confirm_in_transaction(
        self, body: QuestionConfirmRequest, request_fingerprint: str,
        prepared: Mapping[str, tuple[int, tuple[str, str] | AppError]],
    ) -> ConfirmResult:
        """确认入库的域内短事务（必须在 ``_publication`` 内、关联复核之后调用）。"""
        with self.catalog.write_transaction() as conn:
            current = self.catalog.import_in(conn, body.importId)
            if current is None:
                raise _not_found("导入不存在。", code="IMPORT_NOT_FOUND")
            # 事务内复核：放弃与确认并发时，以事务内读到的状态为准
            if current.state == "cancelled":
                raise _conflict("该导入已放弃，不能确认入库。", code="IMPORT_CANCELLED")
            existing = self.catalog.submission_in(conn, body.submissionId)
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise _conflict(
                        "同一提交键已登记不同载荷的确认请求，拒绝复用原结果。",
                        code="IDEMPOTENCY_CONFLICT",
                    )
                return ConfirmResult.model_validate(existing.result)

            plan, failures = self._plan_confirm(conn, body, prepared)
            if failures:
                # 任一草稿不合法 -> 整体不确认；不写 submission，修正后可用同一提交键重试
                return ConfirmResult(
                    confirmedQuestionIds=[],
                    linkedQuestionIds=[],
                    skippedDraftIds=[],
                    failures=failures,
                )

            confirmed: list[str] = []
            linked: list[str] = []
            skipped: list[str] = []
            created_by_draft: dict[str, str] = {}
            for step in plan:
                draft = step["draft"]
                if step["duplicateDraftId"] is not None:
                    target_id = created_by_draft[step["duplicateDraftId"]]
                    self.catalog.mark_draft_duplicate_in(
                        conn, draft.draft_id, question_id=target_id,
                        warning=f"已跳过：与本次先确认的题目 {target_id} 权威题面相同（不含答案与解析）。",
                    )
                    skipped.append(draft.draft_id)
                    continue
                if step["action"] in ("skip", "none") and step["duplicates"]:
                    target = step["duplicates"][0]["question"]
                    self.catalog.mark_draft_duplicate_in(
                        conn,
                        draft.draft_id,
                        question_id=target.question_id,
                        warning=(
                            f"已跳过：与已有题目 {target.question_id} 内容相同"
                            "（指纹不含答案与解析）。"
                        ),
                    )
                    skipped.append(draft.draft_id)
                    continue
                if step["action"] == "link_existing":
                    target_id = step["targetQuestionId"]
                    added = self.catalog.add_question_sources_in(
                        conn,
                        target_id,
                        source_spans=draft.source_spans,
                        import_id=body.importId,
                    )
                    self.catalog.mark_draft_duplicate_in(
                        conn,
                        draft.draft_id,
                        question_id=target_id,
                        warning=(
                            f"已并入已有题目 {target_id}（新增 {added} 条来源，"
                            "未修改已有题内容）。"
                        ),
                        review_state="excluded",
                    )
                    if target_id not in linked:
                        linked.append(target_id)
                    continue
                question = self.catalog.insert_question_in(
                    conn,
                    owner_id=self.owner_id,
                    content=draft.content,
                    metadata=draft.metadata,
                    answer_state=validation.answer_state_of(step["content"]),
                    content_fingerprint=step["fingerprint"],
                    source_spans=draft.source_spans,
                    import_id=body.importId,
                    knowledge_links=self._frozen_link_rows(
                        self.catalog.draft_knowledge_links_in(conn, draft.draft_id)
                    ),
                    derived_fingerprint=step["derivedFingerprint"],
                )
                self.catalog.save_derived_fingerprint_in(
                    conn, question_revision_id=question.current_revision_id,
                    algorithm_version=fp.DUPLICATE_ALGORITHM_VERSION,
                    fingerprint=fp.duplicate_content_fingerprint(draft.content),
                )
                confirmed.append(question.question_id)
                created_by_draft[draft.draft_id] = question.question_id

            result = ConfirmResult(
                confirmedQuestionIds=confirmed,
                linkedQuestionIds=linked,
                skippedDraftIds=skipped,
                failures=[],
            )
            self.catalog.save_submission_in(
                conn,
                submission_id=body.submissionId,
                request_fingerprint=request_fingerprint,
                result=result.model_dump(mode="json"),
            )
            if confirmed or linked:
                self.catalog.set_import_state_in(conn, body.importId, state="confirmed")
            return result

    def _recheck_confirm_links(self, body: QuestionConfirmRequest) -> None:
        """复核本次确认**将要冻结**的草稿关联（B2-RV06，跨库只读，锁内、写之前）。

        - 只检查请求里存在、属于该导入、且未显式选择 ``skip`` / ``link_existing``
          （这两类不会发布新关联）的草稿；草稿的其它校验失败由域内计划返回 failures；
        - 无关联的草稿不要求知识点库装配（历史"无关联确认"路径不受影响）；
        - 引用集合按题目学科分组核验：不存在/修订不符/学科不符 → 422 可定位；
          已归档 → 409 ``KNOWLEDGE_ARCHIVED``（旧草稿绑定活跃、确认前被归档的场景）。
        """
        resolutions = {item.draftId: item.action for item in body.duplicateResolutions}
        by_subject: dict[str, list[KnowledgeReference]] = {}
        for item in body.items:
            action = resolutions.get(item.draftId)
            if action in ("skip", "link_existing"):
                continue  # 显式处置：不发布新关联，无需复核
            draft = self.catalog.get_draft(item.draftId)
            if draft is None or draft.import_id != body.importId:
                continue  # 域内计划会以 failures 如实报告
            links = self.catalog.draft_knowledge_links(draft.draft_id)
            if not links:
                continue
            subject_id = str((draft.metadata or {}).get("subjectId") or "")
            bucket = by_subject.setdefault(subject_id, [])
            for link in links:
                bucket.append(
                    KnowledgeReference(
                        knowledge_point_id=link.knowledge_point_id,
                        knowledge_revision_id=link.knowledge_revision_id,
                    )
                )
        if not by_subject:
            return
        catalog = self._require_knowledge_catalog()
        for subject_id, refs in by_subject.items():
            require_active_knowledge_references(
                catalog, refs, expected_subject_id=subject_id or None
            )

    # ---------------------------------------------------------------- 题目

    def list_questions(
        self,
        *,
        subject_id: str | None = None,
        grade_id: str | None = None,
        edition_id: str | None = None,
        status: str | None = None,
        query: str | None = None,
        knowledge_point_id: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_LIST_LIMIT,
        owner_id: str | None = None,
    ) -> QuestionList:
        records, total = self.catalog.list_questions(
            owner_id=owner_id or self.owner_id,
            subject_id=subject_id,
            grade_id=grade_id,
            edition_id=edition_id,
            status=status,
            query=query,
            knowledge_point_id=knowledge_point_id,
            offset=offset,
            limit=limit,
        )
        return QuestionList(
            questions=[views.question_summary(record) for record in records],
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_question(self, question_id: str) -> QuestionDetail:
        record = self.catalog.get_question(question_id)
        if record is None or record.owner_id != self.owner_id:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        return views.question_detail(
            record, links=self.catalog.question_knowledge_links(question_id)
        )

    def get_content_asset(self, kind: str, entity_id: str, asset_id: str) -> tuple[bytes, str]:
        """只读该 owner 的当前草稿/题目修订实际引用的图片；不接受任意路径。"""
        if not (is_managed_blob_key(asset_id) or is_sha256_hex(asset_id)):
            raise AppError("资产键必须是受管 key 或兼容题库 SHA-256。", code="INVALID_ASSET_KEY", status_code=422)
        if kind == "draft":
            record = self.catalog.get_draft(entity_id)
            imported = self.catalog.get_import(record.import_id) if record is not None else None
            if imported is None or imported.owner_id != self.owner_id:
                raise _not_found("草稿不存在。", code="DRAFT_NOT_FOUND")
        elif kind == "question":
            record = self.catalog.get_question(entity_id)
            if record is None or record.owner_id != self.owner_id:
                raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        else:
            raise _invalid("资产引用范围只能是 draft 或 question。")
        content = validation.parse_content(record.content)
        referenced = rich.image_ids(content.richContent) if content.richContent else set(content.assetIds)
        if asset_id not in referenced:
            raise _not_found("当前内容没有引用该图片。", code="QUESTION_ASSET_NOT_FOUND")
        data, media_type = rich.read_asset(asset_id, assets=self.assets, blobs=self.blobs)
        if content.richContent:
            # 存储时已核验；每次只读再次核实际字节与当前修订的冻结声明。
            declaration = next(item for item in content.richContent.assets if item.asset_id == asset_id)
            digest = fp.asset_byte_hash(asset_id) if is_managed_blob_key(asset_id) else asset_id
            if media_type == "application/octet-stream" or declaration.sha256 != digest or declaration.media_type != media_type:
                raise AppError("当前修订的资产声明与真实字节不一致。", code="QUESTION_ASSET_CORRUPT", status_code=500)
        return data, media_type

    def patch_question(
        self,
        question_id: str,
        body: QuestionPatchRequest,
        *,
        knowledge_links: Sequence[DraftKnowledgeLinkInput] | None = None,
    ) -> QuestionDetail:
        """改题 = 追加新修订。

        - 缺省（``knowledge_links=None``）：复制旧正式关联；
        - 显式提供 ``knowledge_links``：整表替换（空序列 = 清空），旧修订旧关联不动；
        - **学科变化**（``metadata.subjectId`` 与旧值不同，B2-RV07）：继承的旧关联必须与
          新学科一致；存在冲突且未显式给 ``knowledge_links`` → 422
          ``KNOWLEDGE_REFERENCE_INVALID``（要求显式替换或清空），不产生跨学科题。

        HTTP 契约 ``QuestionPatchRequest`` 已有 ``knowledgeLinks`` 字段，路由原样透传。
        """
        record = self.catalog.get_question(question_id)
        if record is None or record.owner_id != self.owner_id:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        rich.validate_projection(body.content, previous=record.content)
        self._verify_new_assets(body.content, previous=record.content)
        content = body.content.model_dump(mode="json")
        # 文件字节/派生指纹预检不持跨库发布锁；仅关联复核与域内提交在同一临界区。
        derived_fingerprint = self._derived_fingerprint(body.content)
        content_fingerprint = fp.content_fingerprint(content)
        link_rows: list[dict[str, str]] | None = None
        with self._publication("question.patch"):
            if knowledge_links is not None:
                parsed = validation.parse_knowledge_links(knowledge_links)
                link_rows = self._link_rows(
                    parsed, subject_id=body.metadata.subjectId, source="human"
                )
            else:
                # 继承关联也会写入新修订，必须在提交前复核活跃状态与学科。
                self._require_subject_change_links(
                    links=self.catalog.question_knowledge_links(question_id),
                    new_subject_id=body.metadata.subjectId,
                    what="题目",
                )
            updated = self.catalog.patch_question(
                question_id,
                expected_revision=body.expectedRevision,
                content=content,
                metadata=body.metadata.model_dump(mode="json"),
                answer_state=validation.answer_state_of(body.content),
                content_fingerprint=content_fingerprint,
                knowledge_links=link_rows,
                derived_fingerprint=derived_fingerprint,
                duplicate_fingerprint=(fp.DUPLICATE_ALGORITHM_VERSION,
                                       fp.duplicate_content_fingerprint(content)),
            )
        return views.question_detail(
            updated, links=self.catalog.question_knowledge_links(question_id)
        )

    def backfill_derived_fingerprints(self, *, limit: int = 100) -> int:
        """显式补算派生指纹（只写 ``question_content_fingerprints``，不改旧指纹列）。"""
        missing = self.catalog.revisions_missing_derived(
            algorithm_version=fp.DERIVED_ALGORITHM_VERSION, limit=limit
        )
        written = 0
        for revision_id, content in missing:
            _, value = self._derived_fingerprint(content)
            with self.catalog.write_transaction() as conn:
                self.catalog.save_derived_fingerprint_in(
                    conn,
                    question_revision_id=revision_id,
                    algorithm_version=fp.DERIVED_ALGORITHM_VERSION,
                    fingerprint=value,
                )
            written += 1
        return written

    def delete_question(self, question_id: str, *, expected_revision: int | None = None) -> None:
        record = self.catalog.get_question(question_id)
        if record is None or record.owner_id != self.owner_id:
            raise _not_found("题目不存在。", code="QUESTION_NOT_FOUND")
        with self._publication("question.archive"):
            self.catalog.archive_question(question_id, expected_revision=expected_revision)

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _frozen_link_rows(links: Sequence[Any]) -> list[dict[str, str]]:
        """草稿关联记录 → 正式题修订关联行（确认入库时冻结，含学科/名称快照）。"""
        return [
            {
                "knowledgePointId": link.knowledge_point_id,
                "knowledgeRevisionId": link.knowledge_revision_id,
                "subjectIdSnapshot": link.subject_id_snapshot,
                "knowledgeNameSnapshot": link.knowledge_name_snapshot,
                "role": link.role,
            }
            for link in links
        ]

    @staticmethod
    def _require_markdown_operation(record: DraftRecord, *, operation: str) -> None:
        if record.content.get("richContent") is not None:
            code = "QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED"
            message = f"当前{operation}流程按原文 Markdown 工作；请先明确 richContent=null 转为 Markdown，再执行{operation}。"
            raise AppError(message, code=code, status_code=422, details=error_details(issues=[
                ErrorIssue(field="content.richContent", code=code, message=message),
            ]))

    def _verify_new_assets(self, content: Any, *, previous: Mapping[str, Any]) -> None:
        if content.richContent is not None:
            rich.verify_assets(content, assets=self.assets, blobs=self.blobs)
            return
        old_ids = set(previous.get("assetIds") or [])
        for asset_id in set(content.assetIds) - old_ids:
            try:
                _, media_type = rich.read_asset(asset_id, assets=self.assets, blobs=self.blobs)
            except AppError as exc:
                if exc.code in {"ASSET_MISSING", "QUESTION_BLOB_MISSING"}:
                    raise AppError("新增图片必须引用已有真实字节。", code="QUESTION_ASSET_NOT_FOUND", status_code=422) from exc
                raise
            if media_type == "application/octet-stream":
                raise AppError("新增图片字节类型无法识别。", code="QUESTION_ASSET_MEDIA_INVALID", status_code=422)

    def _derived_fingerprint(self, content: Any) -> tuple[str, str]:
        """事务外核验真实字节，既有 derived-v1 组成与旧内容指纹算法均保持不变。"""
        payload = content.model_dump(mode="json") if hasattr(content, "model_dump") else content
        validated = validation.parse_content(payload)
        asset_hashes = rich.verify_assets(validated, assets=self.assets, blobs=self.blobs)
        if validated.richContent is None:
            for asset_id in validated.assetIds:
                if is_managed_blob_key(asset_id) or is_sha256_hex(asset_id):
                    rich.read_asset(asset_id, assets=self.assets, blobs=self.blobs)
                    asset_hashes[asset_id] = asset_id.split("/", 1)[-1]
        rich_payload = validated.richContent.model_dump(mode="json", by_alias=True) if validated.richContent else None
        materials = [rich.project_blocks(material.blocks) for material in validated.richContent.shared_materials] if validated.richContent else []
        return (
            fp.DERIVED_ALGORITHM_VERSION,
            fp.derived_content_fingerprint(payload, rich_content=rich_payload, materials=materials, asset_hashes=asset_hashes),
        )

    def _plan_confirm(
        self, conn, body: QuestionConfirmRequest,
        prepared: Mapping[str, tuple[int, tuple[str, str] | AppError]],
    ) -> tuple[list[dict[str, Any]], list[ConfirmFailure]]:
        resolutions = {item.draftId: item for item in body.duplicateResolutions}
        plan: list[dict[str, Any]] = []
        failures: list[ConfirmFailure] = []
        seen: set[str] = set()
        new_surfaces: dict[str, str] = {}
        for item in body.items:
            draft_id = item.draftId
            if draft_id in seen:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_DUPLICATED_IN_REQUEST",
                        message="同一草稿在一次确认请求里出现多次。",
                    )
                )
                continue
            seen.add(draft_id)
            draft = self.catalog.draft_in(conn, draft_id)
            if draft is None:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_NOT_FOUND",
                        message="草稿不存在。",
                    )
                )
                continue
            if draft.import_id != body.importId:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DRAFT_IMPORT_MISMATCH",
                        message="草稿不属于该导入。",
                    )
                )
                continue
            if draft.revision != item.expectedDraftRevision:
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="REVISION_CONFLICT",
                        message=(
                            f"草稿已被更新（当前 revision={draft.revision}），请刷新后重试。"
                        ),
                    )
                )
                continue
            try:
                content = validation.parse_content(draft.content)
            except AppError as exc:
                failures.append(
                    ConfirmFailure(draftId=draft_id, code=exc.code, message=str(exc))
                )
                continue
            checked = prepared.get(draft_id)
            if checked is None or checked[0] != draft.revision:
                failures.append(ConfirmFailure(draftId=draft_id, code="REVISION_CONFLICT",
                                               message="草稿已变化；本次资产预检结果不再适用，请刷新后重试。"))
                continue
            if isinstance(checked[1], AppError):
                failures.append(ConfirmFailure(draftId=draft_id, code=checked[1].code, message=str(checked[1])))
                continue
            issue = validation.validate_for_confirm(
                content=content,
                review_state=draft.review_state,
                missing_answer_acknowledged=draft.missing_answer_acknowledged,
            )
            if issue is not None:
                failures.append(
                    ConfirmFailure(draftId=draft_id, code=issue.code, message=issue.message)
                )
                continue

            content_payload = content.model_dump(mode="json")
            fingerprint = fp.content_fingerprint(content_payload)
            duplicates = [{"question": question} for question in
                          self._duplicate_questions(content_payload, conn=conn)]
            surface_fingerprint = fp.duplicate_content_fingerprint(content_payload)
            duplicate_draft_id = new_surfaces.get(surface_fingerprint) if not duplicates else None
            resolution = resolutions.get(draft_id)
            action = resolution.action if resolution is not None else "none"
            target_question_id: str | None = None
            if resolution is not None and resolution.existingQuestionId is not None:
                target_question_id = resolution.existingQuestionId
            if action == "link_existing":
                candidate_ids = {entry["question"].question_id for entry in duplicates}
                if not candidate_ids:
                    failures.append(
                        ConfirmFailure(
                            draftId=draft_id,
                            code="DUPLICATE_RESOLUTION_INVALID",
                            message="没有可关联的重复题目，link_existing 无法执行。",
                        )
                    )
                    continue
                if target_question_id is None:
                    target_question_id = duplicates[0]["question"].question_id
                elif target_question_id not in candidate_ids:
                    failures.append(
                        ConfirmFailure(
                            draftId=draft_id,
                            code="DUPLICATE_RESOLUTION_INVALID",
                            message="existingQuestionId 与内容指纹不匹配的重复题不一致。",
                        )
                    )
                    continue
            if action == "edit_as_new" and (duplicates or duplicate_draft_id):
                failures.append(
                    ConfirmFailure(
                        draftId=draft_id,
                        code="DUPLICATE_UNRESOLVED",
                        message=(
                            "权威题面与已有题目或本次其它题目相同（指纹不含答案与解析）；"
                            "edit_as_new 需要内容确实不同。"
                        ),
                    )
                )
                continue
            plan.append(
                {
                    "draft": draft,
                    "content": content,
                    "fingerprint": fingerprint,
                    "derivedFingerprint": checked[1],
                    "duplicates": duplicates,
                    "duplicateDraftId": duplicate_draft_id,
                    "action": action,
                    "targetQuestionId": target_question_id,
                }
            )
            if not duplicates and duplicate_draft_id is None:
                new_surfaces[surface_fingerprint] = draft_id
        return plan, failures

    def _parsed_blocks(self, parsed: ParsedDocument) -> list[SourceBlockInput]:
        blocks: list[SourceBlockInput] = []
        for index, block in enumerate(parsed.source_map):
            text = parsed.normalized_text[block.char_start : block.char_end]
            blocks.append(
                SourceBlockInput(ordinal=index, text=text, locator=block.to_json())
            )
        return blocks

    @staticmethod
    def _default_metadata(*, subject_id: str, grade_id: str) -> dict[str, Any]:
        return {
            "stageId": "",
            "gradeId": grade_id or "",
            "subjectId": subject_id or "",
            "editionId": "",
            "knowledgeTags": [],
            "difficulty": "unspecified",
        }

    def _draft_input(
        self,
        content: dict[str, Any],
        source_spans: list[dict[str, Any]],
        *,
        metadata: dict[str, Any],
        warnings: Sequence[str] = (),
        extraction_method: str = "rule",
    ) -> DraftInput:
        validated = validation.parse_content(content).model_dump(mode="json")
        return DraftInput(
            content=validated,
            metadata=metadata,
            source_spans=source_spans,
            extraction_method=extraction_method,
            review_state="needs_review",
            warnings=tuple(warnings),
            content_fingerprint=fp.content_fingerprint(validated),
        )

    @staticmethod
    def _block_range(block: SourceBlockRecord) -> tuple[int, int]:
        locator = block.locator
        start = locator.get("charStart")
        end = locator.get("charEnd")
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            start = 0
        if not isinstance(end, int) or isinstance(end, bool) or end < start:
            end = start + len(block.text)
        return start, end

    def _intersects(self, draft: DraftRecord, block: SourceBlockRecord) -> bool:
        start, end = self._block_range(block)
        for span in draft.source_spans:
            if span.get("blockId") != block.block_id:
                continue
            span_start = span.get("charStart")
            span_end = span.get("charEnd")
            if not isinstance(span_start, int) or not isinstance(span_end, int):
                continue
            if span_start < end and span_end > start:
                return True
        return False

    def _is_assigned(self, block: SourceBlockRecord, drafts: Sequence[DraftRecord]) -> bool:
        return any(self._intersects(draft, block) for draft in drafts)

    @staticmethod
    def _draft_start(draft: DraftRecord) -> int:
        starts = [
            span.get("charStart")
            for span in draft.source_spans
            if isinstance(span.get("charStart"), int)
        ]
        return min(starts) if starts else 0

    def _resolve_split_target(
        self,
        drafts: Sequence[DraftRecord],
        *,
        draft_id: str | None,
        char_offset: int,
    ) -> DraftRecord:
        if not drafts:
            raise _invalid("该导入还没有草稿，无法拆分。", code="IMPORT_HAS_NO_DRAFT")
        if draft_id is not None:
            for draft in drafts:
                if draft.draft_id == draft_id:
                    return draft
            raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
        # 契约缺口：DraftSplitRequest 没有 draftId 字段；缺省时按 charOffset 唯一命中草稿，
        # 命中不唯一一律 422，不猜测用户意图（变更建议见结果卡）。
        candidates = [
            draft
            for draft in drafts
            if draft.review_state != "excluded" and self._covers_offset(draft, char_offset)
        ]
        if len(candidates) == 1:
            return candidates[0]
        raise _invalid(
            "无法唯一确定要拆分的草稿：请在查询参数 draftId 中显式给出草稿 id。",
            code="DRAFT_ID_REQUIRED",
        )

    def _covers_offset(self, draft: DraftRecord, char_offset: int) -> bool:
        for span in draft.source_spans:
            start = span.get("charStart")
            end = span.get("charEnd")
            if isinstance(start, int) and isinstance(end, int) and start < char_offset < end:
                return True
        return False

    @staticmethod
    def _split_half(lines: Sequence[rules.RuleLine]) -> rules.SplitDraft:
        parsed = rules.drafts_from_lines(lines)
        if parsed:
            return parsed[0]
        return rules.fallback_draft(lines)

    def _select_drafts(
        self, all_drafts: Sequence[DraftRecord], draft_ids: Sequence[str]
    ) -> list[DraftRecord]:
        if draft_ids:
            by_id = {draft.draft_id: draft for draft in all_drafts}
            selected: list[DraftRecord] = []
            for draft_id in draft_ids:
                draft = by_id.get(draft_id)
                if draft is None:
                    raise _not_found("草稿不存在或不属于该导入。", code="DRAFT_NOT_FOUND")
                if draft.review_state == "excluded":
                    raise _conflict("已排除的草稿不能参与 AI 整理。", code="DRAFT_EXCLUDED")
                selected.append(draft)
        else:
            selected = [
                draft for draft in all_drafts if draft.review_state != "excluded"
            ]
        if not selected:
            raise _invalid("没有可整理的草稿。", code="ORGANIZE_TARGET_EMPTY")
        return selected

    def _attach_unassigned(
        self,
        draft_blocks: dict[str, list[SourceBlockRecord]],
        selected: Sequence[DraftRecord],
        all_drafts: Sequence[DraftRecord],
        blocks: Sequence[SourceBlockRecord],
    ) -> None:
        """``includeUnassigned``：把未归属块挂到其前一道所选草稿（无前驱则挂第一道）。"""
        ordered = list(selected)
        for block in blocks:
            if self._is_assigned(block, all_drafts):
                continue
            if not block.text.strip():
                continue
            start, _end = self._block_range(block)
            host = ordered[0]
            for draft in ordered:
                if self._draft_start(draft) <= start:
                    host = draft
                else:
                    break
            draft_blocks.setdefault(host.draft_id, []).append(block)

    def _job_view(self, job: Any) -> OrganizeJobView:
        """建议明细只给仍可处理的 ``pending`` 项；``suggestionCount`` 与 ``failedBatches``
        始终是任务的累计事实，便于前端显示「已处理 N/M」。

        ``job`` 可以是题库目录记录（历史路径）或统一引擎记录（``attempt`` 来自后者）。
        """
        all_suggestions = self.catalog.list_suggestions(organization_job_id=job.job_id)
        pending = [item for item in all_suggestions if item.state == "pending"]
        return views.organize_job_view(
            job,
            suggestions=pending,
            suggestion_count=len(all_suggestions),
        )

    @staticmethod
    def _merge_spans(groups: Sequence[Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
        merged: dict[str, list[int]] = {}
        order: list[str] = []
        for spans in groups:
            for span in spans:
                block_id = span.get("blockId")
                start = span.get("charStart")
                end = span.get("charEnd")
                if not isinstance(block_id, str) or not isinstance(start, int) or not isinstance(end, int):
                    continue
                if block_id not in merged:
                    merged[block_id] = [start, end]
                    order.append(block_id)
                else:
                    merged[block_id][0] = min(merged[block_id][0], start)
                    merged[block_id][1] = max(merged[block_id][1], end)
        return [
            {"blockId": block_id, "charStart": merged[block_id][0], "charEnd": merged[block_id][1]}
            for block_id in order
        ]

    def _merge_content(self, contents: Sequence[dict[str, Any]]) -> dict[str, Any]:
        stems = [str(content.get("stemMarkdown", "")).strip() for content in contents]
        stem = "\n\n".join(item for item in stems if item) or "（合并草稿）"
        options: list[dict[str, str]] = []
        used: set[str] = set()
        for content in contents:
            for option in content.get("options") or []:
                key = str(option.get("key", "")).strip()
                text = str(option.get("textMarkdown", "")).strip()
                if not key or not text:
                    continue
                if key in used:
                    key = self._next_option_key(used)
                used.add(key)
                options.append({"key": key, "textMarkdown": text})
        choice_keys: list[str] = []
        accepted: bool | None = None
        answer_texts: list[str] = []
        for content in contents:
            answer = content.get("answer") or {}
            for key in answer.get("choiceKeys") or []:
                if key not in choice_keys:
                    choice_keys.append(str(key))
            if accepted is None and answer.get("accepted") is not None:
                accepted = bool(answer["accepted"])
            text = answer.get("textMarkdown")
            if isinstance(text, str) and text.strip():
                answer_texts.append(text.strip())
        answer: dict[str, Any] | None = None
        if choice_keys or accepted is not None or answer_texts:
            answer = {
                "choiceKeys": choice_keys,
                "accepted": accepted,
                "textMarkdown": "\n".join(answer_texts) if answer_texts else None,
            }
        explanations = [
            str(content.get("explanationMarkdown")).strip()
            for content in contents
            if content.get("explanationMarkdown")
        ]
        asset_ids: list[str] = []
        for content in contents:
            for asset_id in content.get("assetIds") or []:
                if asset_id not in asset_ids:
                    asset_ids.append(str(asset_id))
        types = {str(content.get("type")) for content in contents}
        question_type = types.pop() if len(types) == 1 else "other"
        payload = {
            "type": question_type,
            "stemMarkdown": stem,
            "options": options,
            "answer": answer,
            "explanationMarkdown": "\n".join(explanations) if explanations else None,
            "assetIds": asset_ids,
        }
        return validation.parse_content(payload).model_dump(mode="json")

    @staticmethod
    def _next_option_key(used: set[str]) -> str:
        for code in range(ord("A"), ord("Z") + 1):
            candidate = chr(code)
            if candidate not in used:
                return candidate
        return f"X{len(used) + 1}"


def build_question_bank_service(
    catalog: QuestionBankCatalog,
    settings: Any,
    *,
    model_resolver: ChatModelResolver | None = None,
    parser: Callable[..., ParsedDocument] = parse_document,
    owner_id: str = DEFAULT_OWNER_ID,
    knowledge_catalog: Any | None = None,
    coordinator: Any | None = None,
    job_engine: JobEngine | None = None,
    model_config_repo: Any | None = None,
    secret_store: Any | None = None,
    model_auth_service: Any | None = None,
) -> QuestionBankService:
    """装配入口：总控在 ``main.py`` 里用 ``settings.question_bank_root`` 构造目录与本服务。

    ``model_resolver`` 是模型解析注入点（``(profileId) -> ChatModelHandle``，
    内部走共享的 ``services.model_runtime.resolve_chat_model``）；测试注入替身。
    ``model_resolver`` 为 ``None`` 时服务仍可装配，但 ``organize``/``create_generation_job``
    直接 503 ``SERVICE_UNAVAILABLE``——不返回假成功、不偷偷换模型。

    B2 追加注入：``knowledge_catalog``（知识点库只读）、``coordinator``（跨库发布协调器）、
    ``job_engine``（统一任务引擎，共享 model/heavy 名额）。三者缺省时相关能力如实 503，
    或使用同代码路径的私有引擎；总控应把 ``app.state.{knowledge,job_engine,publication_coordinator}``
    注入进来以共享名额与串行化。

    B3/G0 追加注入（RV04）：``model_config_repo`` + ``secret_store``（+ ``model_auth_service``）
    使恢复/重试路径走共享 ``resolve_frozen_model``；总控可把
    ``app.state.{model_config_repo,secret_store,model_auth_service}`` 一并传入，
    缺省时用 ``model_resolver`` + ``fingerprint_of_handle`` 核对（同一判定与错误码）。
    """
    return QuestionBankService(
        catalog,
        settings,
        model_resolver=model_resolver,
        parser=parser,
        owner_id=owner_id,
        knowledge_catalog=knowledge_catalog,
        coordinator=coordinator,
        job_engine=job_engine,
        model_config_repo=model_config_repo,
        secret_store=secret_store,
        model_auth_service=model_auth_service,
    )
