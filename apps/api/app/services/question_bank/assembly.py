"""题库域装配（R4-BE）：库迁移 → 服务构建 → 任务引擎接线 → 路由注册。

由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 逐批调用（``assemble(app, settings)``）；
main.py 不感知本域内部结构。装配失败由 main 记录原因并降级该域（路由 501/503），
不阻断其余服务、不假成功。

app.state 键名沿用归档约定（本域写入的键）：

- ``question_bank``：``QuestionBankCatalog``（题库 SQLite 唯一读写入口）；
- ``question_bank_service``：``QuestionBankService`` 门面；
- ``question_bank_error``：装配失败原因（None = 正常）；
- ``job_stores`` / ``job_engine``：经 ``register_job_store`` 登记 ``("question", …)``；
- ``job_executors``：``JobExecutorRegistry``（取或建；本域注册 organize/generate 执行器）；
- ``workflow_jobs_registered``：``/workflow-jobs`` 公共路由幂等注册标志。

共享依赖（缺失时对应能力 503，不假成功）：

- ``app.state.publication_coordinator``：跨库发布协调器（核心装配，缺省时服务自建兜底）；
- ``app.state.knowledge``：知识点库只读入口（R3-BE 装配；缺失时知识点关联/补题按
  归档 503/拒绝语义，不假成功）；
- 模型：``resolve_agent_chat_model``（LangChain 官方包、显式凭证、env 断言）；
- ``from-textbook`` 提取（需求 4）：经 ``app.state.catalog``（教材目录，R2 装配）与
  ``app.state.textbook_evidence``（R3 装配的封存正文读取器），只读 SQLite chunks，
  不需要 Qdrant。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings
from app.repositories.question_bank.schema import REQUIRED_TABLES as QUESTION_BANK_TABLES

logger = logging.getLogger("zhiqikeyuan.api.question_bank")

#: 题库任务种类白名单（任务种类是契约的一部分；与归档 JOB_KINDS 的 question 段一致）
QUESTION_JOB_KINDS = frozenset({"organize", "generate"})


def assemble(app: FastAPI, settings: Settings) -> None:
    """题库域装配入口（main 逐域调用；单域失败不阻断其余服务）。"""
    app.state.question_bank = None
    app.state.question_bank_service = None
    app.state.question_bank_error = None

    try:
        from app.core.database_gate import DatabaseExpectation, verify_existing_databases

        question_bank_root = settings.question_bank_root
        question_bank_root.mkdir(parents=True, exist_ok=True)
        verify_existing_databases(
            [
                DatabaseExpectation(
                    question_bank_root / "question-bank.sqlite3",
                    "question_bank",
                    QUESTION_BANK_TABLES,
                )
            ]
        )
    except Exception as exc:  # pragma: no cover - 体检失败拒绝题库域但不阻断其余服务
        app.state.question_bank_error = f"题库库体检未通过：{exc}"
        logger.error("题库库体检未通过，题库域按未装配处理：%s", exc)
        return

    try:
        from app.repositories.question_bank.catalog import QuestionBankCatalog

        catalog = QuestionBankCatalog(question_bank_root / "question-bank.sqlite3")
        catalog.migrate()
    except Exception as exc:  # pragma: no cover - 迁移失败如实报告，不静默重建
        app.state.question_bank = None
        app.state.question_bank_error = f"题库库迁移失败：{exc}"
        logger.error("题库库迁移失败，题库域按未装配处理：%s", exc)
        return
    app.state.question_bank = catalog

    # 任务引擎：登记 question 域 JobStore（engine 以当前全集重建；装配期互不并发）。
    # 先登记再建服务，服务注入共享引擎（模型/重活名额跨域共享）。
    _register_jobs(app, catalog)

    _build_question_bank_service(app, settings)

    service = app.state.question_bank_service
    if service is not None:
        _register_executors(app, service)

    _include_workflow_jobs(app)
    _include_question_bank_routes(app)
    logger.info("题库域装配完成")


def _build_question_bank_service(app: FastAPI, settings: Settings) -> None:
    """题库服务：目录 + 知识点库（只读）+ 发布协调器 + 统一任务引擎 + LangChain 模型适配。"""
    try:
        from app.services.question_bank.service import build_question_bank_service
    except ImportError as exc:  # pragma: no cover - 实现未落地
        app.state.question_bank_error = f"题库服务实现缺失：{exc}"
        logger.warning("题库服务未装配：%s", exc)
        return

    try:
        app.state.question_bank_service = build_question_bank_service(
            app.state.question_bank,
            settings,
            # R4 LangChain：模型解析适配（resolve_agent_chat_model；测试可整体替换）
            model_resolver=_build_model_resolver(app),
            knowledge_catalog=getattr(app.state, "knowledge", None),
            coordinator=getattr(app.state, "publication_coordinator", None),
            job_engine=getattr(app.state, "job_engine", None),
            model_config_repo=app.state.model_config_repo,
            secret_store=app.state.secret_store,
            model_auth_service=getattr(app.state, "model_auth_service", None),
        )
    except Exception as exc:  # pragma: no cover - 服务构建失败如实降级
        app.state.question_bank_service = None
        app.state.question_bank_error = f"题库服务构建失败：{exc}"
        logger.error("题库服务构建失败，题库域按未装配处理：%s", exc)


def _build_model_resolver(app: FastAPI):
    """LangChain 模型解析器（R4）：``resolve_agent_chat_model`` 的注入适配。

    仓储/凭证缺失时返回 None（``organize``/补题 503，不假成功）。
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
        if not isinstance(registry, JobExecutorRegistry):
            registry = JobExecutorRegistry()
        service.register_job_executors(registry)
        app.state.job_executors = registry
    except Exception as exc:  # pragma: no cover - 注册失败只降级 retry 调度
        app.state.question_bank_error = f"题库执行器注册失败：{exc}"
        logger.warning("题库执行器注册失败：%s", exc)


def _register_jobs(app: FastAPI, catalog: Any) -> None:
    """question 域 JobStore 登记（``register_job_store`` 重建引擎全集）。"""
    try:
        from app.repositories.jobs.repository import JobStore
        from app.services.jobs.assembly import register_job_store

        store = JobStore(
            catalog, domain="question", table="question_jobs", kinds=QUESTION_JOB_KINDS
        )
        engine = register_job_store(app, "question", store)
        # 启动收敛：遗留 running 一律转 interrupted（不自动重跑模型任务）
        interrupted = store.reconcile_interrupted()
        if interrupted:
            logger.info("题库域启动任务收敛（running → interrupted）：%s", interrupted)
        _ = engine
    except Exception as exc:  # pragma: no cover - 任务引擎缺失时 AI 能力 503
        app.state.question_bank_error = f"题库任务引擎未装配：{exc}"
        logger.warning("题库任务引擎未装配：%s", exc)


def _include_workflow_jobs(app: FastAPI) -> None:
    """/workflow-jobs 公共路由：幂等注册（首个装配域负责挂载；不改共享路由文件）。"""
    if getattr(app.state, "workflow_jobs_registered", False):
        return
    from app.api.v1 import workflow_jobs as workflow_jobs_route

    app.include_router(workflow_jobs_route.router, prefix="/api/v1")
    app.state.workflow_jobs_registered = True


def _include_question_bank_routes(app: FastAPI) -> None:
    """题库路由注册（服务缺失时路由仍挂载，按 503/501 兜底口径报错）。"""
    from app.api.v1 import question_bank as question_bank_route

    app.include_router(question_bank_route.router, prefix="/api/v1")


__all__ = ["assemble"]
