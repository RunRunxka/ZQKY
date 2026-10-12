"""FastAPI 应用（最小骨架 + 教材域）：对话 + Agent 编排 + 模型配置 + 教材导入索引。

推倒重做后的骨架：只保留
- 对话（/chat/stream，三协议 SSE）
- Agent 编排（LangGraph 内嵌，/agent/*，工具表为空骨架，随业务重建扩展）
- 模型配置（连接/档案/目录/授权）
- 数据底座（SecretStore、数据根排他锁、受管资产 AssetStore、任务引擎骨架）
- 教材域（R2 恢复）：导入草稿/入库任务/书册/受控原文/索引代/Embedding 配置

未实现的 /api/v1 路由统一返回 501 FEATURE_NOT_IMPLEMENTED，不提供假成功响应。
教材服务缺失时对应路由返回 503 SERVICE_UNAVAILABLE，同样不假成功。
历史完整产品（教学闭环全量）已归档为 git tag ``archive-full-v1-20261011``。
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
from app.api.v1 import agent as agent_route
from app.api.v1 import chat as chat_route
from app.api.v1 import embedding_models as embedding_models_route
from app.api.v1 import health as health_route
from app.api.v1 import model_connections as model_connections_route
from app.api.v1 import model_profiles as model_profiles_route
from app.api.v1 import model_catalog as model_catalog_route
from app.api.v1 import textbook_index as textbook_index_route
from app.api.v1 import textbooks as textbooks_route
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.http_safe import LocalAccessGuardMiddleware
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.errors import error_response
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import ModelConfigService
from app.services.publication import PublicationCoordinator

logger = logging.getLogger("zhiqikeyuan.api")

_HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}

#: 装配失败的模块在 app.state 上留下的缺失键（None = 不可用，路由据此 503/501）
AGENT_STATE_KEYS = ("agent_service", "asset_store")

#: 逐批回归的业务域装配模块：每个模块提供 ``assemble(app, settings)``（服务挂 app.state +
#: 注册自己的路由）。模块尚不存在时跳过（未实现路由由 501 兜底）；装配失败按域降级并记录
#: 原因，不阻断其余服务、不假成功。共享件约定：``publication_coordinator`` 由核心装配；
#: JobEngine 经 ``app.services.jobs.assembly.register_job_store`` 逐域登记（装配期重建全集）。
#:
#: 顺序即依赖顺序（后装配的域可复用先装配的键），但**跨域构造期捕获有环**——
#: knowledge 需要 teaching 的 file_assets、papers（teaching 第一批）需要 knowledge 目录；
#: 该环由 knowledge 侧的晚绑定代理打破（`services/knowledge/assembly.py::_LateFileAssets`），
#: 因此 teaching 仍排在 knowledge 之后。
_DOMAIN_ASSEMBLIES: tuple[str, ...] = (
    "app.services.knowledge.assembly",
    "app.services.question_bank.assembly",
    "app.services.teaching.assembly_roster_papers",
    "app.services.teaching.assembly_scores_analysis",
    "app.services.teaching.assembly_practices",
    "app.services.lesson_plans.assembly",
)

#: 教材域在 app.state 上的装配键（沿用归档约定）；None = 不可用，路由据此 503。
#: rag_v2/RAG 会话属于 RAG 恢复卡，本卡只装配教材入库/索引链路必需的键。
TEXTBOOK_STATE_KEYS = (
    "catalog",
    "embedding_provider",
    "vector_store",
    "ingest_service",
    "index_service",
    "textbook_search",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    if app.state.load_env_credentials and settings.credentials_file:
        # **就地**加载 .env 凭证：装配期已把同一个 store 注入各域服务，替换实例会让它们
        # 一直看到启动前的空凭证、任务执行时报 MODEL_NOT_CONFIGURED。原地绑定即可。
        app.state.secret_store.bind_env_file(settings.credentials_file)
    logger.info("后端服务启动：%s:%s（env=%s）", settings.host, settings.port, settings.env)
    # 数据根闸门：恢复目录处于 incomplete 时必须拒绝启动，避免静默新建空库掩盖恢复失败。
    from app.core.data_lock import acquire_data_lock, require_data_root_ready

    require_data_root_ready(settings.data_dir)
    # 服务生命周期内持有数据根排他锁（OS 级，进程退出自动释放）
    with acquire_data_lock(settings.data_dir, exclusive=True, label="api"):
        agent_service = getattr(app.state, "agent_service", None)
        if agent_service is not None:
            try:
                await agent_service.setup()
            except Exception:  # pragma: no cover - 装配失败不阻断其余服务
                logger.exception("Agent checkpointer 装配失败")
                app.state.agent_service = None
                agent_service = None
        try:
            yield
        finally:
            if agent_service is not None:
                try:
                    await agent_service.close()
                except Exception:  # pragma: no cover - 收尾失败不覆盖正常退出
                    logger.exception("关闭 Agent 服务失败")
            _shutdown_textbook_runtime(app)
            logger.info("后端服务已停止")


def _build_model_handle_resolver(app: FastAPI):
    """按 profileId 解析聊天模型的唯一入口（chat 与 Agent 共用）。

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


def _build_agent_runtime(app: FastAPI, settings: Settings) -> None:
    """装配 Agent 编排服务（LangGraph 内嵌）与受管资产。缺失依赖时留 None，路由 503。

    checkpointer 落数据根下的独立库；setup/close 由 lifespan 驱动。
    Agent 只是编排层：工具表当前为空骨架（随业务重建在 tools 中扩展），
    模型凭证经 SecretStore 显式注入。
    """
    app.state.agent_service = None
    app.state.asset_store = None
    try:
        from app.services.agent.service import AgentService
        from app.services.assets.store import AssetStore
    except ImportError as exc:  # pragma: no cover - 依赖未装（langgraph 等）
        logger.warning("Agent 服务未装配：%s", exc)
        return
    app.state.asset_store = AssetStore(settings.assets_root)
    app.state.agent_service = AgentService(
        checkpoint_db=settings.data_dir / "agent" / "agent_checkpoints.sqlite3",
        repo=app.state.model_config_repo,
        secrets=app.state.secret_store,
        app_state=app.state,
    )


def _shutdown_textbook_runtime(app: FastAPI) -> None:
    """教材域收尾：目录与各服务都保留 close() 方法（无长连接也要统一调用）。"""
    for key in TEXTBOOK_STATE_KEYS:
        service = getattr(app.state, key, None)
        close = getattr(service, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # pragma: no cover - 关闭失败不覆盖正常退出
                logger.exception("关闭 %s 失败", key)


def _build_textbook_runtime(app: FastAPI, settings: Settings) -> None:
    """装配教材域运行时（R2-BE2）：目录库 + Ollama Embedding + Qdrant + 入库/索引服务。

    归档口径（archive-full-v1-20261011 ``_build_local_runtime`` 的教材段）：
    - 先对既有教材库做结构体检（损坏/缺表/迁移漂移拒绝启动，不按空库重建）；
    - ``TextbookCatalog.migrate()`` 幂等，未迁移的新库按冻结迁移建表；
    - ``OllamaEmbeddingProvider``/``HttpQdrantStore`` 地址来自 settings
      （``embedding_base_url`` / ``qdrant_url``，不新增配置项）；
    - ``IngestService``/``IndexService`` 各自持有 worker，共用同一 SQLite 权威与同一向量库。

    缺依赖时对应键留 None 并记录原因：路由返回 503 SERVICE_UNAVAILABLE，不假成功。
    空库首启不自动建索引代（ensure_empty_generation 需真实探测 Embedding 模型，
    归档口径由 scripts/rag/migrate_textbooks.py 或教师在设置页完成首次配置）。
    """
    for key in TEXTBOOK_STATE_KEYS:
        setattr(app.state, key, getattr(app.state, key, None))
    app.state.textbooks_error = None

    try:
        from app.repositories.textbook_catalog.catalog import TextbookCatalog
    except ImportError as exc:  # pragma: no cover - 实现未落地
        app.state.textbooks_error = f"教材目录实现缺失：{exc}"
        logger.warning("教材目录未装配：%s", exc)
        return

    try:
        # 既有库先体检（损坏/缺表/迁移漂移都拒绝启动）；新库不存在时由 migrate 创建。
        from app.core.database_gate import DatabaseExpectation, verify_existing_databases
        from app.repositories.textbook_catalog.schema import REQUIRED_TABLES as TEXTBOOK_TABLES

        verify_existing_databases(
            [DatabaseExpectation(settings.textbooks_root / "catalog.sqlite3", "textbooks", TEXTBOOK_TABLES)]
        )
    except Exception as exc:  # pragma: no cover - 体检失败拒绝教材域但不阻断其余服务
        app.state.textbooks_error = f"教材库体检未通过：{exc}"
        logger.error("教材库体检未通过，教材域按未装配处理：%s", exc)
        return

    try:
        app.state.catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
        app.state.catalog.migrate()
    except Exception as exc:  # pragma: no cover - 迁移失败如实报告，不静默重建
        app.state.catalog = None
        app.state.textbooks_error = f"教材库迁移失败：{exc}"
        logger.error("教材库迁移失败，教材域按未装配处理：%s", exc)
        return

    try:
        from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider
        from app.repositories.vector_store.qdrant import HttpQdrantStore
        from app.services.document_parsing.chunking import chunk_document
        from app.services.document_parsing.parser import parse_document
        from app.services.textbook_index.service import IndexService
        from app.services.textbook_ingest.service import IngestService
    except ImportError as exc:  # pragma: no cover - 实现未落地
        app.state.textbooks_error = f"教材入库/索引实现缺失：{exc}"
        logger.warning("教材入库/索引服务未装配：%s", exc)
        return

    # Embedding 与向量库地址沿用核心配置（本机 Ollama 11434 / Qdrant 6333）。
    provider = OllamaEmbeddingProvider(settings.embedding_base_url)
    vectors = HttpQdrantStore(settings.qdrant_url)
    app.state.embedding_provider = provider
    app.state.vector_store = vectors
    # 入库与重建各自持有 worker；两者共用同一 SQLite 权威与同一向量库。
    app.state.ingest_service = IngestService(
        app.state.catalog, parse_document, chunk_document, provider, vectors, settings
    )
    app.state.index_service = IndexService(app.state.catalog, provider, vectors, settings)

    # 检索服务（R2-BE3）：学习问答 Agent 的 search_textbooks 工具经它检索教材。
    # 沿用同一目录/向量库/Embedding 适配器；失败只降级该键（工具不注册），不影响入库链路。
    try:
        from app.services.textbook_search import TextbookSearchService

        app.state.textbook_search = TextbookSearchService(app.state.catalog, vectors, provider)
    except Exception as exc:  # pragma: no cover - 依赖缺失时工具不注册，不假成功
        app.state.textbook_search = None
        app.state.textbooks_error = f"教材检索服务未装配：{exc}"
        logger.warning("教材检索服务未装配：%s", exc)


def _install_domain_assemblies(app: FastAPI, settings: Settings) -> None:
    """逐批回归业务域的装配入口（模块存在即装配；缺失跳过，501 兜底）。"""
    for module_name in _DOMAIN_ASSEMBLIES:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            logger.info("业务域未装配（模块缺失，路由 501）：%s（%s）", module_name, exc)
            continue
        assemble = getattr(module, "assemble", None)
        if not callable(assemble):
            logger.warning("业务域模块缺少 assemble(app, settings)：%s", module_name)
            continue
        try:
            assemble(app, settings)
        except Exception:  # pragma: no cover - 单域失败不阻断其余服务
            logger.exception("业务域装配失败（该域路由不可用，不假成功）：%s", module_name)


def create_app(
    settings: Settings | None = None,
    *,
    repository: ModelConfigRepository | None = None,
    secret_store: SecretStore | None = None,
    bootstrap_textbooks: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = FastAPI(title="智启课源 API", version="0.4.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.model_config_repo = repository or ModelConfigRepository(
        settings.data_dir / "model-config.json"
    )
    # 只在实际启动本应用时读凭证；导入 create_app 的隔离测试不会读取用户 .env。
    app.state.secret_store = secret_store or SecretStore()
    app.state.load_env_credentials = secret_store is None
    app.state.model_config_service = ModelConfigService(
        app.state.model_config_repo, app.state.secret_store
    )
    app.state.model_auth_service = ModelAuthService(
        app.state.model_config_repo, app.state.secret_store
    )
    app.state.model_handle_resolver = _build_model_handle_resolver(app)
    # 跨库发布协调器（知识域/试卷域等共享）：进程内互斥，装配期创建一次。
    app.state.publication_coordinator = PublicationCoordinator()
    if bootstrap_textbooks:
        _build_textbook_runtime(app, settings)
    else:
        # 隔离测试/裁剪部署：教材域整体按未装配处理，路由统一 503。
        app.state.textbooks_error = "教材域未装配（bootstrap_textbooks=False）"
        for key in TEXTBOOK_STATE_KEYS:
            setattr(app.state, key, None)
    _build_agent_runtime(app, settings)
    app.add_middleware(LocalAccessGuardMiddleware, settings=settings)

    app.include_router(health_route.router, prefix="/api/v1")
    app.include_router(capabilities_route.router, prefix="/api/v1")
    app.include_router(model_connections_route.router, prefix="/api/v1")
    app.include_router(model_profiles_route.router, prefix="/api/v1")
    app.include_router(model_catalog_route.router, prefix="/api/v1")
    app.include_router(chat_route.router, prefix="/api/v1")
    app.include_router(agent_route.router, prefix="/api/v1")
    app.include_router(embedding_models_route.router, prefix="/api/v1")
    app.include_router(textbooks_route.router, prefix="/api/v1")
    app.include_router(textbook_index_route.router, prefix="/api/v1")
    _install_domain_assemblies(app, settings)

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
            details={"fields": fields} if fields else None,
        )

    return app


app = create_app()
