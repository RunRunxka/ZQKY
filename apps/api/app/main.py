"""FastAPI 应用：生命周期、路由注册、统一错误与本机访问防护。

现有模型、对话与本地教材路由共用此应用；未实现的 /api/v1 路由返回
501 FEATURE_NOT_IMPLEMENTED，不提供假成功响应。
"""

from __future__ import annotations

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
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.http_safe import LocalAccessGuardMiddleware
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.errors import error_response
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import ModelConfigService
from app.services.rag_sessions import RagSessionService

logger = logging.getLogger("zhiqikeyuan.api")

_HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}

# 教材/题库运行时在 app.state 上的装配键；缺服务时统一为 None，路由据此报 501/503
TEXTBOOK_STATE_KEYS = (
    "catalog", "embedding_provider", "vector_store",
    "ingest_service", "index_service", "question_bank", "question_bank_service", "rag_v2",
)


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
    try:
        yield
    finally:
        await app.state.rag_service.close()
        _shutdown_textbook_runtime(app)
        logger.info("后端服务已停止")


def _build_explainer_factory(app: FastAPI):
    """把既有「模型配置 → 连接 → Provider」链路包成详解用的模型句柄工厂。

    详解在用户点击时冻结模型：工厂只按 profileId 解析，失败重试沿用同一 id，
    不因为默认模型后来变化而换模型。
    """
    from app.api.v1.chat import DEFAULT_CHAT_MAX_OUTPUT_TOKENS
    from app.services.model_readiness import callable_state
    from app.services.model_runtime import build_llm_config, build_provider
    from app.services.rag_v2.explain import ChatModelHandle

    def factory(model_profile_id: str) -> ChatModelHandle:
        repo = app.state.model_config_repo
        secrets = app.state.secret_store
        profile = repo.get_profile(model_profile_id)
        connection = repo.get_connection(profile.connectionId)
        state = callable_state(connection, secrets)
        if not state.ready:
            raise AppError(
                state.reason or "该模型连接当前不可调用。",
                code="MODEL_NOT_CONFIGURED",
                status_code=400,
            )
        config = build_llm_config(connection, profile, secrets)
        provider = build_provider(
            connection, config, auth_service=app.state.model_auth_service
        )
        return ChatModelHandle(
            profile_id=profile.id,
            model_id=profile.modelId,
            provider=provider,
            config=config,
            max_output_tokens=profile.maxOutputTokens or DEFAULT_CHAT_MAX_OUTPUT_TOKENS,
        )

    return factory


def _build_textbook_runtime(app: FastAPI, settings: Settings) -> None:
    """装配教材目录/入库/索引/题库服务；缺模块或缺本机依赖时留 None 并记录原因。

    这里不做任何假成功：服务为 None 时对应路由返回 501/503，而不是空列表。
    每个子服务独立装配，一个未落地不影响其他已落地的服务。
    """
    for key in TEXTBOOK_STATE_KEYS:
        setattr(app.state, key, getattr(app.state, key, None))
    app.state.textbooks_error = None

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
        explainer=Explainer(_build_explainer_factory(app)),
    )
    # 教材定位与追问的唯一生产入口；旧四科 rag_engine 保留但不再被 /rag/* 调用。
    app.state.rag_service = app.state.rag_v2

    if app.state.question_bank is not None:
        try:
            from app.services.question_bank.service import (
                OllamaOrganizerModel, build_question_bank_service,
            )
        except ImportError:  # pragma: no cover - 实现落地前
            pass
        else:
            app.state.question_bank_service = build_question_bank_service(
                app.state.question_bank,
                settings,
                organizer=OllamaOrganizerModel(settings.embedding_base_url),
            )


def _shutdown_textbook_runtime(app: FastAPI) -> None:
    for key in (
        "ingest_service", "index_service", "question_bank_service",
        "question_bank", "catalog",
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
        _build_textbook_runtime(app, settings)
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
            exc.status_code, exc.code, str(exc), retryable=exc.retryable
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
