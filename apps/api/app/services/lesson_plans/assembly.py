"""教案后端（lesson_plans 域）装配（R7-BE）：教学库复用 + 服务 + 执行器 + 路由。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 调用（``assemble(app, settings)``）；
main.py 不感知本域内部结构。装配内容（沿归档 main.py 的教案段迁移到分域装配）：

1. **依赖只读复用，不重建**：``app.state.teaching``（教学库，R5 已装配）、
   ``asset_store`` / ``file_assets``（R5）、``publication_coordinator``（核心）、
   ``job_engine``（R5 登记 teaching JobStore 后重建）——任一缺失时本域整体
   不装配（键留 None），路由按 503 处理，不假成功；
2. ``LessonGenerationService`` → ``app.state.lesson_generation_service``；
   模型解析适配 ``resolve_agent_chat_model``（LangChain 官方包、显式凭证、
   env 断言），``frozen_model_resolver`` 按**冻结指纹**重解析（漂移在执行期核对）；
3. ``LessonPlanService`` → ``app.state.lesson_plan_service``（归档键名不变）；
   教材证据读取器复用 ``app.state.textbook_evidence``（R3 装配的
   ``TextbookEvidenceReader``，以本域证据适配器补齐归档 ``RagV2Service`` 的
   ``prepare_selected_evidence``/``verify_selected_evidence`` 口径）；
4. 执行器注册：``(teaching, lesson_generation)`` 工厂注册进 ``app.state.job_executors``
   （R5 已建 registry 与 ``(teaching, paper_mapping)``；R6 追加 ``(teaching, analysis)``；
   本域追加，不覆盖）；
5. 路由注册：lesson_plans / lesson_stream / lesson_sources + ``/workflow-jobs``
   幂等守卫（try-import；文件缺失就跳过）。

挂 app.state 键名（沿用归档）：
``lesson_plan_service`` / ``lesson_generation_service`` / ``fixed_question_reader``。
``export`` 类本卡不产生任务行（教案导出是同步产物），不注册执行器。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger("zhiqikeyuan.api.lesson_plans")

#: 教材证据区间上限（与归档 LessonEvidenceRequest 契约一致）。
_EVIDENCE_MAX_SLICES = 6


def assemble(app: FastAPI, settings: Settings) -> None:
    """R7-BE 域装配入口（main.py 逐批调用；失败由 main 按域降级记录）。"""
    # 0) 键位预置：None = 未装配，路由据此 503/501（不假成功）
    for key in (
        "lesson_plan_service",
        "lesson_generation_service",
        "lesson_source_service",
        "fixed_question_reader",
        "lesson_export_ready",
    ):
        if not hasattr(app.state, key):
            setattr(app.state, key, None)

    # 1) 前置依赖（R5/核心装配）：缺失时本域整体不装配，不重建他人键
    catalog = getattr(app.state, "teaching", None)
    asset_store = getattr(app.state, "asset_store", None)
    file_assets = getattr(app.state, "file_assets", None)
    coordinator = getattr(app.state, "publication_coordinator", None)
    job_engine = getattr(app.state, "job_engine", None)
    analysis_service = getattr(app.state, "analysis_service", None)
    knowledge_catalog = getattr(app.state, "knowledge", None)
    missing = [
        name
        for name, value in (
            ("teaching", catalog),
            ("asset_store", asset_store),
            ("file_assets", file_assets),
            ("publication_coordinator", coordinator),
            ("job_engine", job_engine),
            ("analysis_service", analysis_service),
        )
        if value is None
    ]
    if missing:
        logger.warning(
            "教案域未装配（缺少前置服务：%s）；相关路由按 503 处理。", "、".join(missing)
        )
        return

    # 2) 教材证据读取器：复用 R3 的 app.state.textbook_evidence（缺失时本域 503——
    #    教案生成的教材依据与证据校验都依赖它，不假成功）
    evidence_reader = getattr(app.state, "textbook_evidence", None)
    if evidence_reader is not None:
        evidence_reader = LessonEvidenceAdapter(evidence_reader)

    # 3) 模型解析（LangChain）：resolve_agent_chat_model 注入适配
    model_resolver = _build_model_resolver(app)
    frozen_resolver = _build_frozen_model_resolver(app) if model_resolver is not None else None

    # 4) 固定题库读取（R4 题库目录只读）；题库域缺失时固定题来源 503（生成准备阶段拒绝）
    from app.services.question_bank.fixed import FixedQuestionReader

    fixed_question_reader = None
    question_bank = getattr(app.state, "question_bank", None)
    if question_bank is not None:
        fixed_question_reader = FixedQuestionReader(question_bank)
    app.state.fixed_question_reader = fixed_question_reader

    # 5) 生成服务（执行器经 LessonPlanService.register_job_executors 注册）
    from app.services.lesson_generation import LessonGenerationService

    # 练习读取器（R6-PH 练习域装配 ``app.state.practice_service``，只读复用）；
    # 缺失时练习引用路径按 503/404 如实失败，不伪造练习能力。
    practice_reader = getattr(app.state, "practice_service", None)
    generation_service = LessonGenerationService(
        catalog,
        analysis_reader=analysis_service,
        knowledge_catalog=knowledge_catalog,
        evidence_reader=evidence_reader,
        fixed_question_reader=fixed_question_reader,
        practice_reader=practice_reader,
        model_resolver=model_resolver,
        frozen_model_resolver=frozen_resolver,
        question_owner_id=_question_owner_id(app),
    )
    app.state.lesson_generation_service = generation_service

    # 6) 教案服务（工作台门面）
    from app.services.lesson_plans import LessonPlanService

    app.state.lesson_plan_service = LessonPlanService(
        catalog,
        analysis_reader=analysis_service,
        knowledge_catalog=knowledge_catalog,
        coordinator=coordinator,
        job_engine=job_engine,
        generation_service=generation_service,
        evidence_reader=evidence_reader,
        asset_store=asset_store,
        file_assets=file_assets,
    )
    registry = getattr(app.state, "job_executors", None)
    register = getattr(app.state.lesson_plan_service, "register_job_executors", None)
    if callable(register) and registry is not None:
        register(registry)

    # 6b) 学情材料服务（2026-10-13 补齐）：上传学情文件 → 受管资产 → 生成流读回。
    #     只依赖教学库 + 受管资产（R5 已装配），不依赖模型/任务引擎。
    from app.services.lesson_sources import LessonSourceService

    app.state.lesson_source_service = LessonSourceService(
        asset_store=asset_store,
        file_assets=file_assets,
    )

    # 7) 路由：lesson_plans / lesson_stream / lesson_sources 本卡；/workflow-jobs
    #    归 R3-BE（try-import 幂等注册；文件缺失就跳过，不新建/不改写）。
    from app.api.v1 import lesson_plans as lesson_plans_route
    from app.api.v1 import lesson_sources as lesson_sources_route
    from app.api.v1 import lesson_stream as lesson_stream_route

    _include_router_once(app, lesson_plans_route.router)
    _include_router_once(app, lesson_stream_route.router)
    _include_router_once(app, lesson_sources_route.router)
    try:  # 并行批次（R3-BE）可能尚未落盘：缺失即跳过
        from app.api.v1 import workflow_jobs as workflow_jobs_route

        _include_router_once(app, workflow_jobs_route.router)
    except ImportError:  # pragma: no cover - R3-BE 未落盘时
        logger.info("workflow_jobs 路由未注册（模块缺失，归 R3-BE 批次）")

    app.state.lesson_export_ready = True
    logger.info("教案域（lesson_plans）装配完成")


def _question_owner_id(app: FastAPI) -> str:
    """题库归属：题库域的本地单教师归属（``local-user``，与 R6 练习服务同源）。

    优先读题库服务的 ``owner_id``（R4 服务重建后已挂该属性）；缺失时按
    ``question_bank.fixed`` 的默认归属兜底。题读不到按 404 如实报错。
    """
    question_service = getattr(app.state, "question_bank_service", None)
    owner_id = getattr(question_service, "owner_id", None)
    if isinstance(owner_id, str) and owner_id.strip():
        return owner_id
    from app.services.question_bank.service import DEFAULT_OWNER_ID

    return DEFAULT_OWNER_ID


def _build_model_resolver(app: FastAPI):
    """LangChain 模型解析器（``resolve_agent_chat_model`` 注入适配）。

    仓储/凭证缺失时返回 None（生成准备阶段 503，不假成功）。
    """
    repo = getattr(app.state, "model_config_repo", None)
    secrets = getattr(app.state, "secret_store", None)
    if repo is None or secrets is None:
        return None

    def resolver(profile_id: str):
        from app.services.agent.model import resolve_agent_chat_model

        return resolve_agent_chat_model(repo, secrets, profile_id)

    return resolver


def _build_frozen_model_resolver(app: FastAPI):
    """冻结模型解析器：按任务快照（profileId + fingerprint）重解析并核对指纹。

    与归档语义一致：解析出的句柄指纹必须与冻结值一致（漂移 409 在执行器核对，
    这里只做解析；句柄缺失/解析失败如实上抛，不换模型、不回退默认）。
    """
    base = _build_model_resolver(app)
    if base is None:
        return None

    def frozen_resolver(snapshot: dict):
        profile_id = ""
        if isinstance(snapshot, dict):
            profile_id = str(
                snapshot.get("profileId") or snapshot.get("modelProfileId") or ""
            ).strip()
        if not profile_id:
            from app.core.exceptions import AppError

            raise AppError(
                "任务缺少冻结模型配置，请重新发起。",
                code="MODEL_PROFILE_NOT_FOUND",
                status_code=404,
            )
        return base(profile_id)

    return frozen_resolver


class LessonEvidenceAdapter:
    """教材证据读取的归档口径适配器（包装 R3 的 ``TextbookEvidenceReader``）。

    归档教案域依赖 ``RagV2Service.prepare_selected_evidence`` /
    ``verify_selected_evidence``（封存原文 + 范围核验 + 引用重建）。R2/R3 重建后
    这些方法落在 ``services.rag_v2``（retrieval/scope/source_text）与
    ``services.knowledge.evidence``，本适配器**组合现有真实实现**补齐同口径，
    不复制第二套证据语义：

    - ``prepare_selected_evidence(selection, slices)``：``resolve_scope`` 冻结范围
      → 区间唯一/总量 ≤16000 核验 → 引用重建（``rebuild_evidence_refs`` 同源
      校验链：范围成员/修订存活/散列/区间/正文区）→ ``LessonEvidenceView``；
    - ``verify_selected_evidence(scope_snapshot, evidence_refs)``：重算范围 →
      逐条重建引用（1..6 条、单段 ≤6000、合计 ≤16000）→ ``TextbookEvidence`` 列表。
    """

    def __init__(self, reader: Any) -> None:
        # reader 是 R3 装配的 TextbookEvidenceReader（catalog + ImmutableSource）
        self._reader = reader
        self.catalog = getattr(reader, "_catalog", None)

    def _source(self) -> Any:
        return getattr(self._reader, "_source", None)

    def prepare_selected_evidence(self, selection: Any, slices: Any) -> Any:
        from app.contracts.lesson_plans import LessonEvidenceRequest
        from app.contracts.lesson_plans import LessonEvidenceView
        from app.schemas.rag_v2 import EvidenceRef
        from app.services.rag_v2.evidence import rebuild_evidence_refs
        from app.services.rag_v2.scope import resolve_scope

        request = LessonEvidenceRequest.model_validate({"selection": selection, "slices": list(slices or [])})
        catalog = self._require_catalog()
        source = self._require_source()
        snapshot = resolve_scope(catalog, request.selection)
        identities = [(item.document_revision_id, item.char_start, item.char_end) for item in request.slices]
        if len(set(identities)) != len(identities) or sum(end - start for _, start, end in identities) > 16000:
            raise _lesson_invalid("教材区间需唯一且总量不超过16000字符。")
        allowed = {item.documentRevisionId for item in snapshot.documents}
        refs: list[EvidenceRef] = []
        for item in request.slices:
            if item.document_revision_id not in allowed:
                raise _lesson_invalid("所选区间不属于已核实教材范围。", "RAG_EVIDENCE_UNAVAILABLE")
            revision = catalog.get_revision(item.document_revision_id)
            if revision is None:
                raise _lesson_invalid("所选教材修订不可用。", "RAG_EVIDENCE_UNAVAILABLE")
            text = source.read_normalized_text(revision)
            if item.char_end > len(text):
                raise _lesson_invalid("所选区间超出教材原文范围。", "RAG_EVIDENCE_UNAVAILABLE")
            refs.append(
                EvidenceRef(
                    evidenceId=evidence_id(revision.revision_id, item.char_start, item.char_end),
                    documentRevisionId=revision.revision_id,
                    normalizedTextSha256=revision.normalized_text_sha256,
                    charStart=item.char_start,
                    charEnd=item.char_end,
                )
            )
        evidence = self.verify_selected_evidence(snapshot, refs)
        return LessonEvidenceView(scopeSnapshot=snapshot, evidenceRefs=refs, evidence=evidence)

    def verify_selected_evidence(self, scope_snapshot: Any, evidence_refs: Any) -> list:
        from app.schemas.rag_v2 import EvidenceRef, ScopeSnapshot
        from app.services.rag_v2.evidence import rebuild_evidence_refs
        from app.services.rag_v2.scope import verify_scope

        snapshot = ScopeSnapshot.model_validate(scope_snapshot)
        raw_refs = list(evidence_refs or [])
        if not 1 <= len(raw_refs) <= _EVIDENCE_MAX_SLICES:
            raise _lesson_invalid("请选择1至6段已核实教材依据。", "LESSON_INVALID")
        for ref in raw_refs:
            if isinstance(ref, dict) and any(
                type(ref.get(key)) is not int for key in ("charStart", "charEnd")
            ):
                raise _lesson_invalid("教材区间坐标须为整数。", "LESSON_INVALID")
        refs = [EvidenceRef.model_validate(ref) for ref in raw_refs]
        identities = [(ref.documentRevisionId, ref.charStart, ref.charEnd) for ref in refs]
        if (
            len(set(identities)) != len(identities)
            or any(ref.charEnd > 9007199254740991 or ref.charEnd - ref.charStart > 6000 for ref in refs)
            or sum(ref.charEnd - ref.charStart for ref in refs) > 16000
        ):
            raise _lesson_invalid("教材依据需唯一、单段≤6000、合计≤16000字符。", "LESSON_INVALID")
        catalog = self._require_catalog()
        scope = verify_scope(catalog, snapshot)
        evidence = rebuild_evidence_refs(catalog=catalog, scope=scope, refs=refs, texts=self._require_source())
        if any(
            not (item.readable.text if item.readable is not None else item.text).strip()
            for item in evidence
        ):
            raise _lesson_invalid("所选教材区间没有可读正文。", "RAG_EVIDENCE_UNAVAILABLE")
        return evidence

    def _require_catalog(self) -> Any:
        if self.catalog is None:
            from app.core.exceptions import AppError

            raise AppError(
                "教材目录未装配，无法定位教材内容。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True
            )
        return self.catalog

    def _require_source(self) -> Any:
        source = self._source()
        if source is None:
            from app.core.exceptions import AppError

            raise AppError(
                "教材原文访问未装配，无法读取教材原文。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True
            )
        return source


def evidence_id(document_revision_id: str, char_start: int, char_end: int) -> str:
    """稳定引用 id（与 ``services.rag_v2.evidence.evidence_id`` 同一公式）。"""
    import hashlib

    digest = hashlib.sha256(f"{document_revision_id}:{char_start}:{char_end}".encode("utf-8")).hexdigest()
    return f"ev-{digest[:16]}"


def _lesson_invalid(message: str, code: str = "LESSON_INVALID"):
    from app.core.exceptions import AppError

    return AppError(message, code=code, status_code=409 if code == "RAG_EVIDENCE_UNAVAILABLE" else 422)


def _include_router_once(app: FastAPI, router: Any) -> None:
    """幂等注册（重复装配/测试重复挂载不产生重复路由）；通配 501 占位留在最后。"""
    existing = {getattr(route, "path", None) for route in app.router.routes}
    if any(getattr(route, "path", None) in existing for route in router.routes):
        return
    app.include_router(router, prefix="/api/v1")
    routes = list(app.router.routes)
    catch = [route for route in routes if getattr(route, "name", "") == "feature_not_implemented"]
    if catch:
        app.router.routes[:] = [route for route in routes if route not in catch] + catch


__all__ = ["assemble"]
