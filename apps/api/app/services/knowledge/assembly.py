"""知识点域装配（R3-BE）：库迁移 → 服务构建 → 任务引擎接线 → 路由注册。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 逐批调用（``assemble(app, settings)``）；
装配失败由 main 记录原因并降级该域（路由 501/503），不阻断其余服务、不假成功。

app.state 键名沿用归档约定（本域写入的键）：

- ``knowledge``：``KnowledgeCatalog``（知识点库唯一读写入口）；
- ``knowledge_service``：``KnowledgeService`` 门面（Agent 读工具经
  ``app.state.knowledge_service`` 自动通电，见 ``services/agent/tools.py``）；
- ``knowledge_error``：装配失败原因（None = 正常）；
- ``job_stores`` / ``job_engine``：经 ``register_job_store`` 登记 ``("knowledge", …)``；
- ``job_executors``：``JobExecutorRegistry``（取或建；本域注册 ``suggestion`` 执行器）；
- ``workflow_jobs_registered``：``/workflow-jobs`` 公共路由幂等注册标志。

共享依赖（缺失时对应键留 None / 能力 503，不假成功）：

- ``app.state.teaching``（教学库，R5-BE 装配）：受管文件登记 ``file_assets`` 的库；
  缺失时 AI 候选无法登记原始输出资产——本域降级为无资产候选能力不可用；
- ``app.state.catalog``（教材目录，R2 装配）：教材证据/提取/范围解析；
- ``app.state.question_bank``（题库，R4 装配）：跨库引用计数；
- 模型：``resolve_agent_chat_model``（LangChain 官方包、显式凭证、env 断言）。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings
from app.repositories.knowledge.schema import REQUIRED_TABLES as KNOWLEDGE_TABLES

logger = logging.getLogger("zhiqikeyuan.api.knowledge")

#: 知识点任务种类白名单（任务种类是契约的一部分；与归档 JOB_KINDS 的 knowledge 段一致）
KNOWLEDGE_JOB_KINDS = frozenset({"suggestion"})


def assemble(app: FastAPI, settings: Settings) -> None:
    """知识点域装配入口（main 逐域调用；单域失败不阻断其余服务）。"""
    app.state.knowledge = None
    app.state.knowledge_service = None
    app.state.knowledge_error = None

    try:
        from app.core.database_gate import DatabaseExpectation, verify_existing_databases

        knowledge_root = settings.knowledge_root
        knowledge_root.mkdir(parents=True, exist_ok=True)
        verify_existing_databases(
            [DatabaseExpectation(knowledge_root / "knowledge.sqlite3", "knowledge", KNOWLEDGE_TABLES)]
        )
    except Exception as exc:  # pragma: no cover - 体检失败拒绝知识点域但不阻断其余服务
        app.state.knowledge_error = f"知识点库体检未通过：{exc}"
        logger.error("知识点库体检未通过，知识点域按未装配处理：%s", exc)
        return

    try:
        from app.repositories.knowledge.catalog import KnowledgeCatalog

        catalog = KnowledgeCatalog(settings.knowledge_root / "knowledge.sqlite3")
        catalog.migrate()
    except Exception as exc:  # pragma: no cover - 迁移失败如实报告，不静默重建
        app.state.knowledge = None
        app.state.knowledge_error = f"知识点库迁移失败：{exc}"
        logger.error("知识点库迁移失败，知识点域按未装配处理：%s", exc)
        return
    app.state.knowledge = catalog

    # 任务引擎：登记 knowledge 域 JobStore（engine 以当前全集重建；装配期互不并发）
    _register_jobs(app, catalog)

    _build_knowledge_service(app, settings)

    service = app.state.knowledge_service
    if service is not None:
        _register_executors(app, service)

    _include_workflow_jobs(app)
    _include_knowledge_routes(app)


def _register_jobs(app: FastAPI, catalog: Any) -> None:
    """knowledge 域 JobStore 登记（``register_job_store`` 重建引擎全集）。"""
    try:
        from app.repositories.jobs.repository import JobStore
        from app.services.jobs.assembly import register_job_store

        store = JobStore(catalog, domain="knowledge", table="knowledge_jobs", kinds=KNOWLEDGE_JOB_KINDS)
        engine = register_job_store(app, "knowledge", store)
        # 启动收敛：遗留 running 一律转 interrupted（不自动重跑模型任务）
        interrupted = store.reconcile_interrupted()
        if interrupted:
            logger.info("知识点域启动任务收敛（running → interrupted）：%s", interrupted)
        _ = engine
    except Exception as exc:  # pragma: no cover - 任务引擎缺失时 AI 候选 503
        app.state.knowledge_error = f"知识点任务引擎未装配：{exc}"
        logger.warning("知识点任务引擎未装配：%s", exc)


def _build_knowledge_service(app: FastAPI, settings: Settings) -> None:
    """知识点服务：知识点库 + 受管资产 + 发布协调器 + 任务引擎 + 教材证据（都按缺省降级）。"""
    try:
        from app.repositories.assets.file_assets import FileAssetsRepository
        from app.services.assets.store import AssetStore
        from app.services.knowledge.service import build_knowledge_service
        from app.services.publication import PublicationCoordinator
    except ImportError as exc:  # pragma: no cover - 实现未落地
        app.state.knowledge_error = f"知识点服务实现缺失：{exc}"
        logger.warning("知识点服务未装配：%s", exc)
        return

    asset_store = getattr(app.state, "asset_store", None)
    teaching = getattr(app.state, "teaching", None)
    file_assets = FileAssetsRepository(teaching) if teaching is not None else None
    if asset_store is None or file_assets is None:
        # R3 适配：教学库（R5-BE 批次）未装配时知识点 CRUD/树生成/教材依据仍可用，
        # 依赖受管资产的入口（表格导入/AI 候选）在服务层 503（_require_assets）。
        logger.info(
            "知识点受管资产未装配（asset_store / teaching 缺失）；"
            "表格导入与 AI 候选将在调用时 503。"
        )

    # 教材证据读取（R2 教材目录 + rag_v2 不可变原文）：缺失时 textbookEvidence 503
    evidence = _build_evidence_reader(app)

    # 任务①②端口：跨库引用计数（题库缺失按 0 处理）与教材范围解析（教材目录缺失 503）
    reference_checker = _build_reference_checker(app)
    scope_reader = _build_scope_reader(app)

    coordinator = getattr(app.state, "publication_coordinator", None) or PublicationCoordinator()
    app.state.knowledge_service = build_knowledge_service(
        app.state.knowledge,
        asset_store=asset_store,
        file_assets=file_assets,
        evidence=evidence,
        coordinator=coordinator,
        # R3 LangChain 模型工厂（显式凭证 + env 断言）；仓储/凭证齐备时执行器走冻结指纹核对
        model_resolver=_build_model_resolver(app),
        job_engine=getattr(app.state, "job_engine", None),
        model_config_repo=app.state.model_config_repo,
        secret_store=app.state.secret_store,
        model_auth_service=getattr(app.state, "model_auth_service", None),
        reference_checker=reference_checker,
        scope_reader=scope_reader,
    )


def _build_evidence_reader(app: FastAPI) -> Any | None:
    """教材证据读取器（教材目录 + 不可变原文）；教材目录缺失时 None（503 口径）。"""
    catalog = getattr(app.state, "catalog", None)
    if catalog is None:
        return None
    try:
        from app.services.knowledge.evidence import TextbookEvidenceReader
        from app.services.rag_v2.source_text import ImmutableSource
    except ImportError as exc:  # pragma: no cover - 实现未落地
        logger.warning("教材证据读取器未装配：%s", exc)
        return None
    # blobs_root 由 catalog 自动派生（ImmutableSource.blob_root_for），显式传会与教材根脱钩
    source = ImmutableSource(catalog=catalog)
    reader = TextbookEvidenceReader(catalog, source=source)
    # 归档键名：教材证据读取器挂 app.state.textbook_evidence（提取/依据共用）
    app.state.textbook_evidence = reader
    return reader


def _build_reference_checker(app: FastAPI) -> Any | None:
    """跨库引用计数（删除守卫）；教学库/题库缺失按无引用处理，知识点库必在。"""
    try:
        from app.services.knowledge.references import CrossLibraryReferenceChecker
    except ImportError as exc:  # pragma: no cover - 实现未落地
        logger.warning("知识点引用检查实现缺失：%s", exc)
        return None
    return CrossLibraryReferenceChecker(
        knowledge_catalog=app.state.knowledge,
        teaching_catalog=getattr(app.state, "teaching", None),
        question_bank_catalog=getattr(app.state, "question_bank", None),
    )


def _build_scope_reader(app: FastAPI) -> Any | None:
    """教材范围查询（scope=taught / gradeId）；教材目录缺失时 None（带 scope 的调用 503）。"""
    catalog = getattr(app.state, "catalog", None)
    if catalog is None:
        return None
    try:
        from app.services.knowledge.textbook_scope import CatalogTextbookScopeReader
    except ImportError as exc:  # pragma: no cover - 实现未落地
        logger.warning("知识点范围查询实现缺失：%s", exc)
        return None
    return CatalogTextbookScopeReader(catalog)


def _build_model_resolver(app: FastAPI):
    """LangChain 模型解析器（R3）：``resolve_agent_chat_model`` 的注入适配。

    仓储/凭证缺失时返回 None（AI 候选 503，不假成功）。
    """
    repo = getattr(app.state, "model_config_repo", None)
    secrets = getattr(app.state, "secret_store", None)
    if repo is None or secrets is None:
        return None

    def resolver(profile_id: str):
        from app.services.agent.model import resolve_agent_chat_model

        return resolve_agent_chat_model(repo, secrets, profile_id)

    return resolver


def _register_executors(app: FastAPI, service: Any) -> None:
    """本域执行器工厂注册进公共注册表（取或建；retry 调度依赖）。"""
    try:
        from app.services.jobs.registry import JobExecutorRegistry

        registry = getattr(app.state, "job_executors", None)
        if registry is None:
            registry = JobExecutorRegistry()
        service.register_job_executors(registry)
        app.state.job_executors = registry
    except Exception as exc:  # pragma: no cover - 注册失败只降级 retry 调度
        app.state.knowledge_error = f"知识点执行器注册失败：{exc}"
        logger.warning("知识点执行器注册失败：%s", exc)


def _include_workflow_jobs(app: FastAPI) -> None:
    """/workflow-jobs 公共路由：幂等注册（首个装配域负责挂载）。"""
    if getattr(app.state, "workflow_jobs_registered", False):
        return
    from app.api.v1 import workflow_jobs as workflow_jobs_route

    app.include_router(workflow_jobs_route.router, prefix="/api/v1")
    app.state.workflow_jobs_registered = True


def _include_knowledge_routes(app: FastAPI) -> None:
    """知识点路由注册（服务缺失时路由仍挂载，按 503/501 兜底口径报错）。"""
    from app.api.v1 import knowledge as knowledge_route

    app.include_router(knowledge_route.router, prefix="/api/v1")


__all__ = ["assemble"]
