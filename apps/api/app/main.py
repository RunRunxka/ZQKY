"""FastAPI 应用：生命周期、路由注册、统一错误与本机访问防护。

现有模型、对话与本地教材路由共用此应用；未实现的 /api/v1 路由返回
501 FEATURE_NOT_IMPLEMENTED，不提供假成功响应。
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import capabilities as capabilities_route
from app.api.v1 import chat as chat_route
from app.api.v1 import embedding_models as embedding_models_route
from app.api.v1 import question_bank as question_bank_route
from app.api.v1 import rag as rag_route
from app.api.v1 import health as health_route
from app.api.v1 import model_connections as model_connections_route
from app.api.v1 import model_profiles as model_profiles_route
from app.api.v1 import model_catalog as model_catalog_route
from app.api.v1 import textbook_index as textbook_index_route
from app.api.v1 import textbooks as textbooks_route
from app.api.v1 import workflow_jobs as workflow_jobs_route
from app.core.config import Settings
from app.core.database_gate import DatabaseExpectation, verify_existing_databases
from app.core.exceptions import AppError
from app.core.http_safe import LocalAccessGuardMiddleware
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.repositories.knowledge.schema import REQUIRED_TABLES as KNOWLEDGE_TABLES
from app.repositories.question_bank.schema import REQUIRED_TABLES as QUESTION_BANK_TABLES
from app.repositories.teaching.schema import REQUIRED_TABLES as TEACHING_TABLES
from app.repositories.textbook_catalog.schema import REQUIRED_TABLES as TEXTBOOK_TABLES
from app.schemas.errors import error_response
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import ModelConfigService
from app.services.rag_sessions import RagSessionService

logger = logging.getLogger("zhiqikeyuan.api")

_HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}

# 本地数据库运行时在 app.state 上的装配键；缺服务时统一为 None，路由据此报 501/503
TEXTBOOK_STATE_KEYS = (
    "catalog", "embedding_provider", "vector_store",
    "ingest_service", "index_service", "question_bank", "question_bank_service", "rag_v2",
    "knowledge", "teaching", "job_engine",
    "asset_store", "file_assets", "publication_coordinator", "textbook_evidence",
    "knowledge_service", "roster_service", "paper_service", "confirmed_paper_reader",
    "assessment_service", "score_service", "job_executors",
)

#: 可选路由（模块缺失时只记录原因，不影响其他模块；并行开发期与裁剪部署都安全）
OPTIONAL_ROUTERS = (
    ("app.api.v1.knowledge", "知识点"),
    ("app.api.v1.roster", "名单"),
    ("app.api.v1.papers", "原卷"),
    ("app.api.v1.assessments", "施测"),
    ("app.api.v1.scores", "成绩"),
)


def _include_optional_routers(app: FastAPI) -> None:
    for module_path, label in OPTIONAL_ROUTERS:
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:  # pragma: no cover - 实现落地前
            logger.warning("%s 路由未注册：%s", label, exc)
            continue
        app.include_router(module.router, prefix="/api/v1")

#: 任务白名单：任务种类是契约的一部分；新增 kind 属总控级变更（改这里 + 文档）。
#: 知识点候选与 AI 补题分别落在知识点库与题库；原卷/学情/教案/导出落在教学库。
JOB_KINDS: dict[str, frozenset[str]] = {
    "question": frozenset({"organize", "generate"}),
    "knowledge": frozenset({"suggestion"}),
    "teaching": frozenset({"paper_import", "paper_mapping", "analysis", "lesson_generation", "export"}),
}

#: 启动时执行"遗留 running → interrupted"收敛的任务域（见 _build_job_engine 说明）。
#: B2/T50 起题库任务已接入统一引擎（六态 + retry），因此一并收敛；不自动重叫模型。
RECONCILE_DOMAINS: tuple[str, ...] = ("knowledge", "teaching", "question")


def _database_expectations(settings: Settings) -> list[DatabaseExpectation]:
    """四库期望清单：启动体检与迁移登记共用同一份路径/结构定义。"""
    return [
        DatabaseExpectation(
            settings.textbooks_root / "catalog.sqlite3", "textbooks", TEXTBOOK_TABLES
        ),
        DatabaseExpectation(
            settings.question_bank_root / "question-bank.sqlite3",
            "question_bank",
            QUESTION_BANK_TABLES,
        ),
        DatabaseExpectation(
            settings.knowledge_root / "knowledge.sqlite3", "knowledge", KNOWLEDGE_TABLES
        ),
        DatabaseExpectation(
            settings.teaching_root / "teaching.sqlite3", "teaching", TEACHING_TABLES
        ),
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if app.state.load_env_credentials and settings.credentials_file:
        # 启动时重建凭证存储；服务层必须一并重建，否则会写入启动前的内存存储，
        # 导致 .env 落盘与读取不一致。
        app.state.secret_store = SecretStore(settings.credentials_file)
        app.state.model_config_service = ModelConfigService(
            app.state.model_config_repo, app.state.secret_store
        )
        app.state.model_auth_service = ModelAuthService(
            app.state.model_config_repo, app.state.secret_store
        )
    logger.info(
        "后端服务启动：%s:%s（env=%s）",
        settings.host,
        settings.port,
        settings.env,
    )
    # 数据根闸门：恢复目录处于 incomplete 时必须拒绝启动，避免静默新建空库掩盖恢复失败。
    from app.core.data_lock import acquire_data_lock, require_data_root_ready

    require_data_root_ready(settings.data_dir)
    # 服务生命周期内持有数据根排他锁（OS 级，进程退出自动释放）：
    # 离线一致性备份拿不到锁会返回 DATA_LOCK_BUSY，而不会去停用户进程。
    with acquire_data_lock(settings.data_dir, exclusive=True, label="api"):
        try:
            yield
        finally:
            engine = getattr(app.state, "job_engine", None)
            shutdown = getattr(engine, "shutdown", None)
            if callable(shutdown):
                try:
                    # 停止本进程持有的任务 worker：在跑的任务留 running，
                    # 下次启动由 reconcile 转 interrupted（不自动重跑）。
                    await shutdown()
                except Exception:  # pragma: no cover - 收尾失败不覆盖正常退出
                    logger.exception("停止任务引擎失败")
            await app.state.rag_service.close()
            _shutdown_textbook_runtime(app)
            logger.info("后端服务已停止")


def _build_model_handle_resolver(app: FastAPI):
    """按 profileId 解析聊天模型的唯一入口（详解与题库 AI 整理共用）。

    解析逻辑在共享的 `services.model_runtime.resolve_chat_model`；
    这里只把 `app.state` 上的仓储/凭证/认证服务注入进去。
    """

    def resolver(model_profile_id: str, *, purpose: str | None = "chat"):
        from app.services.model_runtime import resolve_chat_model

        return resolve_chat_model(
            app.state.model_config_repo,
            app.state.secret_store,
            model_profile_id,
            auth_service=app.state.model_auth_service,
            purpose=purpose,
        )

    return resolver


def _build_local_runtime(app: FastAPI, settings: Settings) -> None:
    """装配本地数据库运行时（四库 + 任务引擎）与教材/题库/RAG 服务。

    启动顺序（TEACHING-LOOP B0）：恢复状态闸门 → 既有库体检（损坏不重建）→
    四库迁移登记 → 任务收敛（遗留 running → interrupted）。缺模块或缺本机依赖时
    留 None 并记录原因：服务为 None 时对应路由返回 501/503，而不是空列表。
    """
    for key in TEXTBOOK_STATE_KEYS:
        setattr(app.state, key, getattr(app.state, key, None))
    app.state.textbooks_error = None

    # 恢复未完成的数据根拒绝启动（避免在未恢复目录里建库）；体检拒绝损坏/结构不符的既有库。
    from app.core.data_lock import require_data_root_ready

    require_data_root_ready(settings.data_dir)
    verify_existing_databases(_database_expectations(settings))

    try:
        from app.repositories.textbook_catalog.catalog import TextbookCatalog
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.textbooks_error = f"教材目录实现缺失：{exc}"
    else:
        app.state.catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
        app.state.catalog.migrate()

    try:
        from app.repositories.question_bank.catalog import QuestionBankCatalog
    except ImportError:  # pragma: no cover - 实现落地前
        pass
    else:
        app.state.question_bank = QuestionBankCatalog(
            settings.question_bank_root / "question-bank.sqlite3"
        )
        app.state.question_bank.migrate()

    try:
        from app.repositories.knowledge.catalog import KnowledgeCatalog
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.textbooks_error = f"知识点库实现缺失：{exc}"
    else:
        app.state.knowledge = KnowledgeCatalog(
            settings.knowledge_root / "knowledge.sqlite3"
        )
        app.state.knowledge.migrate()

    try:
        from app.repositories.teaching.catalog import TeachingCatalog
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.textbooks_error = f"教学库实现缺失：{exc}"
    else:
        app.state.teaching = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
        app.state.teaching.migrate()

    _build_job_engine(app)
    _build_shared_services(app, settings)
    _build_knowledge_runtime(app)
    _build_roster_runtime(app)
    _build_paper_runtime(app)
    _build_assessment_runtime(app)
    _build_score_runtime(app)
    _build_question_bank_runtime(app, settings)
    # 执行器注册必须在所有域服务构造之后：域服务在这里注册自己的 (domain, kind)
    _build_executor_registry(app)

    if app.state.catalog is None:
        return
    try:
        from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider
        from app.repositories.vector_store.qdrant import HttpQdrantStore
        from app.services.document_parsing.chunking import chunk_document
        from app.services.document_parsing.parser import parse_document
        from app.services.rag_v2.explain import Explainer
        from app.services.rag_v2.retrieval import HybridRetriever
        from app.services.rag_v2.service import RagV2Service
        from app.services.rag_v2.summary import KnowledgeSummarizer
        from app.services.textbook_ingest.service import IngestService
        from app.services.textbook_index.service import IndexService
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.textbooks_error = f"教材入库/索引/RAG 实现缺失：{exc}"
        return

    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    vectors = HttpQdrantStore(settings.qdrant_url)
    app.state.embedding_provider = provider
    app.state.vector_store = vectors
    # 入库与重建各自持有 worker；两者共用同一 SQLite 权威与同一向量库。
    app.state.ingest_service = IngestService(
        app.state.catalog, parse_document, chunk_document, provider, vectors, settings
    )
    app.state.index_service = IndexService(app.state.catalog, provider, vectors, settings)

    app.state.rag_v2 = RagV2Service(
        catalog=app.state.catalog,
        retrieval=HybridRetriever(app.state.catalog, vectors, provider),
        summarizer=KnowledgeSummarizer(settings.embedding_base_url),
        explainer=Explainer(_build_model_handle_resolver(app)),
    )
    # 教材定位与追问的唯一生产入口；旧四科 rag_engine 保留但不再被 /rag/* 调用。
    app.state.rag_service = app.state.rag_v2


def _build_executor_registry(app: FastAPI) -> None:
    """任务执行器注册表（B3/G0 · B2-RV01）：公共 retry 的唯一调度路径。

    域服务在装配后把自己已实现的 (domain, kind) 执行器注册进来；未注册的类型
    保持 `queued`（用户可再次 retry），不伪造执行。
    """
    from app.services.jobs.registry import JobExecutorRegistry

    registry = JobExecutorRegistry()
    app.state.job_executors = registry
    for key in (
        "question_bank_service",
        "knowledge_service",
        "paper_service",
        "assessment_service",
    ):
        service = getattr(app.state, key, None)
        register = getattr(service, "register_job_executors", None)
        if callable(register):
            try:
                register(registry)
            except Exception:  # pragma: no cover - 注册失败不影响启动，但如实记录
                logger.exception("%s 注册任务执行器失败", key)


def _build_shared_services(app: FastAPI, settings: Settings) -> None:
    """受管资产、文件登记、发布协调器与教材证据读取器（跨域共享，CTRL 独占装配）。

    缺依赖时留 None：调用方按 503 处理，不降级成假成功。
    """
    try:
        from app.services.publication import PublicationCoordinator
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.publication_coordinator = None
        logger.warning("发布协调器缺失：%s", exc)
    else:
        app.state.publication_coordinator = PublicationCoordinator()

    if app.state.teaching is None:
        return
    try:
        from app.repositories.assets.file_assets import FileAssetsRepository
        from app.services.assets.store import AssetStore
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("受管资产实现缺失：%s", exc)
        return
    app.state.asset_store = AssetStore(settings.assets_root)
    app.state.file_assets = FileAssetsRepository(app.state.teaching)

    if app.state.catalog is None:
        return
    try:
        from app.services.knowledge.evidence import TextbookEvidenceReader
        from app.services.rag_v2.source_text import ImmutableSource
    except ImportError:  # pragma: no cover - 实现落地前
        return
    # blobs_root 由 catalog 自动派生（ImmutableSource.blob_root_for），显式传会与教材根脱钩
    source = ImmutableSource(catalog=app.state.catalog)
    app.state.textbook_evidence = TextbookEvidenceReader(app.state.catalog, source=source)


def _build_knowledge_runtime(app: FastAPI) -> None:
    """知识点服务：依赖知识点库 + 受管资产登记 + 发布协调器 + 任务引擎。"""
    if app.state.knowledge is None or app.state.asset_store is None or app.state.file_assets is None:
        return
    try:
        from app.services.knowledge.service import build_knowledge_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("知识点服务缺失：%s", exc)
        return
    app.state.knowledge_service = build_knowledge_service(
        app.state.knowledge,
        asset_store=app.state.asset_store,
        file_assets=app.state.file_assets,
        evidence=app.state.textbook_evidence,
        coordinator=app.state.publication_coordinator,
        model_resolver=_build_model_handle_resolver(app),
        job_engine=app.state.job_engine,
        model_config_repo=app.state.model_config_repo,
        secret_store=app.state.secret_store,
        model_auth_service=app.state.model_auth_service,
    )


def _build_roster_runtime(app: FastAPI) -> None:
    """名单服务：班级/学生/归属历史与名单导入（施测真实创建属 T30-b）。"""
    if app.state.teaching is None or app.state.asset_store is None or app.state.file_assets is None:
        return
    try:
        from app.services.roster.service import build_roster_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("名单服务缺失：%s", exc)
        return
    app.state.roster_service = build_roster_service(
        app.state.teaching,
        asset_store=app.state.asset_store,
        file_assets=app.state.file_assets,
        job_engine=app.state.job_engine,
    )


def _build_question_bank_runtime(app: FastAPI, settings: Settings) -> None:
    """题库存量服务（T50 起接入共享知识点库、发布协调器与统一任务引擎）。

    必须在 ``_build_shared_services`` 之后装配：knowledge_catalog / coordinator 由那里提供；
    缺任一依赖时服务仍可构造（对应能力返回 503），不伪造成功。
    """
    if app.state.question_bank is None:
        return
    try:
        from app.services.question_bank.service import build_question_bank_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("题库服务缺失：%s", exc)
        return
    app.state.question_bank_service = build_question_bank_service(
        app.state.question_bank,
        settings,
        model_resolver=_build_model_handle_resolver(app),
        knowledge_catalog=app.state.knowledge,
        coordinator=app.state.publication_coordinator,
        job_engine=app.state.job_engine,
        model_config_repo=app.state.model_config_repo,
        secret_store=app.state.secret_store,
        model_auth_service=app.state.model_auth_service,
    )


def _build_paper_runtime(app: FastAPI) -> None:
    """原卷服务：教学库 + 受管资产 + 知识点库（跨库只读校验）+ 发布协调器 + 任务引擎。

    同时暴露 ``confirmed_paper_reader``（T30-b 只用已确认修订的端口实现）。
    """
    if app.state.teaching is None or app.state.asset_store is None or app.state.file_assets is None:
        return
    try:
        from app.services.papers.service import build_paper_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("原卷服务缺失：%s", exc)
        return
    app.state.paper_service = build_paper_service(
        app.state.teaching,
        asset_store=app.state.asset_store,
        file_assets=app.state.file_assets,
        knowledge_catalog=app.state.knowledge,
        coordinator=app.state.publication_coordinator,
        model_resolver=_build_model_handle_resolver(app),
        job_engine=app.state.job_engine,
        model_config_repo=app.state.model_config_repo,
        secret_store=app.state.secret_store,
        model_auth_service=app.state.model_auth_service,
    )
    app.state.confirmed_paper_reader = app.state.paper_service.confirmed_reader()


def _build_assessment_runtime(app: FastAPI) -> None:
    """施测服务（T30-b）：依赖原卷的真实 reader（未装配则留 None，路由 503）。"""
    if app.state.teaching is None or app.state.confirmed_paper_reader is None:
        return
    try:
        from app.services.assessments.service import build_assessment_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("施测服务缺失：%s", exc)
        return
    app.state.assessment_service = build_assessment_service(
        app.state.teaching, reader=app.state.confirmed_paper_reader
    )


def _build_score_runtime(app: FastAPI) -> None:
    """成绩服务（T60）：依赖施测服务、已确认原卷 reader、受管资产与发布协调器。"""
    if (
        app.state.teaching is None
        or app.state.asset_store is None
        or app.state.file_assets is None
        or app.state.assessment_service is None
        or app.state.confirmed_paper_reader is None
    ):
        return
    try:
        from app.services.scores import build_score_service
    except ImportError as exc:  # pragma: no cover - 实现落地前
        logger.warning("成绩服务缺失：%s", exc)
        return
    app.state.score_service = build_score_service(
        app.state.teaching,
        asset_store=app.state.asset_store,
        file_assets=app.state.file_assets,
        assessment_service=app.state.assessment_service,
        paper_reader=app.state.confirmed_paper_reader,
        publication_coordinator=app.state.publication_coordinator,
    )


def _build_job_engine(app: FastAPI) -> None:
    """按已装配的库构造任务引擎，并做启动收敛（遗留 running → interrupted）。

    ``reconcile`` 不重新调用模型：中断的模型任务保持 interrupted，等教师显式重试。

    B0 的收敛范围**只含知识点库与教学库**：题库的组织任务仍在既有流程里管理
    （其状态枚举与前端视图尚未迁移到六态），B2 迁移题库任务时一并纳入，
    避免在旧界面上出现它不认识的状态。
    """
    try:
        from app.repositories.jobs.repository import JobStore
        from app.services.jobs.engine import JobEngine
    except ImportError as exc:  # pragma: no cover - 实现落地前
        app.state.job_engine = None
        if app.state.textbooks_error is None:
            app.state.textbooks_error = f"任务引擎实现缺失：{exc}"
        return

    bindings = (
        ("question", app.state.question_bank, "question_jobs"),
        ("knowledge", app.state.knowledge, "knowledge_jobs"),
        ("teaching", app.state.teaching, "workflow_jobs"),
    )
    stores = {
        domain: JobStore(catalog, domain=domain, table=table, kinds=JOB_KINDS[domain])
        for domain, catalog, table in bindings
        if catalog is not None
    }
    engine = JobEngine(stores, heavy_limit=2, model_limit=1)
    app.state.job_engine = engine

    interrupted: dict[str, list[str]] = {}
    for domain in RECONCILE_DOMAINS:
        try:
            store = engine.store(domain)
        except AppError as exc:
            if exc.code == "INVALID_REQUEST":  # 该域未装配（隔离测试）
                continue
            raise
        interrupted[domain] = store.reconcile_interrupted()
    if any(interrupted.values()):
        logger.info("启动任务收敛（running → interrupted）：%s", interrupted)


def _shutdown_textbook_runtime(app: FastAPI) -> None:
    for key in (
        "ingest_service", "index_service", "question_bank_service",
        "question_bank", "catalog", "knowledge", "teaching",
    ):
        service = getattr(app.state, key, None)
        close = getattr(service, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover - 关闭失败不覆盖正常退出
                logger.exception("关闭 %s 失败", key)


def create_app(
    settings: Settings | None = None,
    *,
    repository: ModelConfigRepository | None = None,
    secret_store: SecretStore | None = None,
    rag_service: RagSessionService | None = None,
    bootstrap_textbooks: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(title="智启课源 API", version="0.3.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.rag_service = rag_service or RagSessionService(
        settings.data_dir / "rag", settings.data_dir / "rag-state",
    )
    app.state.model_config_repo = repository or ModelConfigRepository(
        settings.data_dir / "model-config.json"
    )
    # 只在实际启动本应用时读凭证；导入 create_app 的隔离测试不会读取用户 .env。
    app.state.secret_store = secret_store or SecretStore()
    app.state.load_env_credentials = secret_store is None
    # 服务层由应用持有：同一实例保证跨 .env/JSON 补偿与认证状态机的单一写入者
    app.state.model_config_service = ModelConfigService(
        app.state.model_config_repo, app.state.secret_store
    )
    app.state.model_auth_service = ModelAuthService(
        app.state.model_config_repo, app.state.secret_store
    )
    if bootstrap_textbooks:
        _build_local_runtime(app, settings)
    else:
        app.state.textbooks_error = "教材目录未装配（隔离测试）"
        for key in TEXTBOOK_STATE_KEYS:
            setattr(app.state, key, None)
    app.add_middleware(LocalAccessGuardMiddleware, settings=settings)

    app.include_router(health_route.router, prefix="/api/v1")
    app.include_router(capabilities_route.router, prefix="/api/v1")
    app.include_router(model_connections_route.router, prefix="/api/v1")
    app.include_router(model_profiles_route.router, prefix="/api/v1")
    app.include_router(model_catalog_route.router, prefix="/api/v1")
    app.include_router(chat_route.router, prefix="/api/v1")
    app.include_router(rag_route.router, prefix="/api/v1")
    app.include_router(embedding_models_route.router, prefix="/api/v1")
    app.include_router(textbooks_route.router, prefix="/api/v1")
    app.include_router(textbook_index_route.router, prefix="/api/v1")
    app.include_router(question_bank_route.router, prefix="/api/v1")
    app.include_router(workflow_jobs_route.router, prefix="/api/v1")
    _include_optional_routers(app)

    @app.api_route(
        "/api/v1/{rest:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        include_in_schema=False,
    )
    async def feature_not_implemented(rest: str) -> JSONResponse:
        return error_response(
            501,
            "FEATURE_NOT_IMPLEMENTED",
            f"接口 /api/v1/{rest} 尚未实现，请勿当作可用能力调用。",
        )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            exc.status_code,
            exc.code,
            str(exc),
            retryable=exc.retryable,
            details=getattr(exc, "details", None),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_ERROR_CODES.get(exc.status_code, "REQUEST_FAILED")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 只输出字段位置，不回显请求内容
        fields = [str(error.get("loc", ())[1:]) for error in exc.errors() if error.get("loc")]
        return error_response(
            422,
            "INVALID_REQUEST",
            "请求参数不合法。",
            details={"fields": [field for field in fields if field]},
        )

    return app


app = create_app()
