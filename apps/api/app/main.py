"""FastAPI 应用（最小骨架）：对话 + Agent 编排 + 模型配置。

推倒重做后的骨架：只保留
- 对话（/chat/stream，三协议 SSE）
- Agent 编排（LangGraph 内嵌，/agent/*，工具表为空骨架，随业务重建扩展）
- 模型配置（连接/档案/目录/授权）
- 数据底座（SecretStore、数据根排他锁、受管资产 AssetStore、任务引擎骨架）

未实现的 /api/v1 路由统一返回 501 FEATURE_NOT_IMPLEMENTED，不提供假成功响应。
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
from app.api.v1 import health as health_route
from app.api.v1 import model_connections as model_connections_route
from app.api.v1 import model_profiles as model_profiles_route
from app.api.v1 import model_catalog as model_catalog_route
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.http_safe import LocalAccessGuardMiddleware
from app.core.secrets import SecretStore
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.errors import error_response
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import ModelConfigService

logger = logging.getLogger("zhiqikeyuan.api")

_HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}

#: 装配失败的模块在 app.state 上留下的缺失键（None = 不可用，路由据此 503/501）
AGENT_STATE_KEYS = ("agent_service", "asset_store")


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


def create_app(
    settings: Settings | None = None,
    *,
    repository: ModelConfigRepository | None = None,
    secret_store: SecretStore | None = None,
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
    _build_agent_runtime(app, settings)
    app.add_middleware(LocalAccessGuardMiddleware, settings=settings)

    app.include_router(health_route.router, prefix="/api/v1")
    app.include_router(capabilities_route.router, prefix="/api/v1")
    app.include_router(model_connections_route.router, prefix="/api/v1")
    app.include_router(model_profiles_route.router, prefix="/api/v1")
    app.include_router(model_catalog_route.router, prefix="/api/v1")
    app.include_router(chat_route.router, prefix="/api/v1")
    app.include_router(agent_route.router, prefix="/api/v1")

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
