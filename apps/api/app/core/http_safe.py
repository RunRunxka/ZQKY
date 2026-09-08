"""本机访问防护：校验 Host 与 Origin，拒绝非回环主机和未允许的浏览器来源。

浏览器经 Next 同源代理访问时 Origin 为前端地址；本机工具直连（无 Origin 头）放行。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import LOCAL_HOSTNAMES, Settings
from app.schemas.errors import error_response, new_request_id

ASGIAppType = Callable[[Scope, Receive, Send], Awaitable[None]]


def _host_allowed(host: str) -> bool:
    hostname = host.strip()
    if hostname.startswith("["):
        end = hostname.find("]")
        if end == -1:
            return False
        hostname = hostname[1:end]
    elif ":" in hostname:
        hostname = hostname.rsplit(":", 1)[0]
    return hostname in LOCAL_HOSTNAMES


class LocalAccessGuardMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if not _host_allowed(headers.get("host", "")):
            await self._reject(
                scope,
                receive,
                send,
                status_code=400,
                code="INVALID_HOST",
                message="请求 Host 不是本机回环地址，已拒绝。",
            )
            return
        origin = headers.get("origin")
        if origin is not None and origin not in self.settings.allowed_origins:
            await self._reject(
                scope,
                receive,
                send,
                status_code=403,
                code="FORBIDDEN_ORIGIN",
                message="请求来源不在允许列表中。",
                details={"origin": origin},
            )
            return
        await self.app(scope, receive, send)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        response = error_response(
            status_code,
            code,
            message,
            details=details,
            request_id=new_request_id(),
        )
        await response(scope, receive, send)
