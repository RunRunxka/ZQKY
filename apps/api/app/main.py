"""FastAPI 应用：生命周期、路由注册、统一错误与本机访问防护。

本期（D02）只实现 /api/v1/health 与 /api/v1/capabilities；
其余 /api/v1 路由一律返回 501 FEATURE_NOT_IMPLEMENTED，不提供假成功响应。
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

logger = logging.getLogger("zhiqikeyuan.api")

_HTTP_ERROR_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "后端服务启动：%s:%s（env=%s）",
        settings.host,
        settings.port,
        settings.env,
    )
    yield
    logger.info("后端服务已停止")


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
    app = FastAPI(title="智启课源 API", version="0.3.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.model_config_repo = repository or ModelConfigRepository(
        settings.data_dir / "model-config.json"
    )
    app.state.secret_store = secret_store or SecretStore()
    app.add_middleware(LocalAccessGuardMiddleware, settings=settings)

    app.include_router(health_route.router, prefix="/api/v1")
    app.include_router(capabilities_route.router, prefix="/api/v1")
    app.include_router(model_connections_route.router, prefix="/api/v1")
    app.include_router(model_profiles_route.router, prefix="/api/v1")
    app.include_router(model_catalog_route.router, prefix="/api/v1")
    app.include_router(chat_route.router, prefix="/api/v1")

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
