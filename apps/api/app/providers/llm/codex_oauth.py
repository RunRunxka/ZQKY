"""Codex OAuth（授权码 + PKCE + 本机回环回调）状态机（D11/D16）。

设计对齐参考 `deeptutor/services/codex_auth/{oauth,service,constants}.py` 的**流程**，
但按 D16 使用智启课源**自有**的 OAuth 应用与受管令牌存储：
- 不在源码里硬编码参考的 client_id / scope 冒充 Codex CLI 身份。
- 不读取任何第三方 CLI/IDE 的登录文件。
- client_id 与回调端口由部署配置提供（`ZQKY_CODEX_CLIENT_ID` 等）；未配置时
  明确返回 `OAUTH_APP_NOT_CONFIGURED`，**不伪造授权地址**。

令牌只在服务端 SecretStore 中，响应与日志不回显。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

AUTH_ISSUER = os.environ.get("ZQKY_CODEX_AUTH_ISSUER", "https://auth.openai.com")
CODEX_DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_CALLBACK_PORTS = (1455, 1457)
LOGIN_TIMEOUT_SECONDS = 300
TOKEN_REFRESH_SKEW_SECONDS = 300

# 状态词表（与 model_auth 的四态对齐）
OP_WAITING = "waiting"
OP_COMPLETED = "completed"
OP_CANCELLED = "cancelled"
OP_EXPIRED = "expired"
OP_FAILED = "failed"

_ERROR_REASONS = {
    "callback_unavailable": "本机回环回调端口被占用，无法开始授权。",
    "login_timeout": "授权超时，请重新开始。",
    "login_cancelled": "授权已取消。",
    "state_mismatch": "回调状态校验失败，请重新开始授权。",
    "authorization_denied": "用户在授权页拒绝了本次请求。",
    "token_exchange_failed": "令牌交换失败，请重试。",
    "token_response_invalid": "令牌响应格式不正确。",
    "authentication_required": "尚未完成登录，请先开始授权流程。",
    "oauth_app_not_configured": "尚未配置 Codex OAuth 应用凭据，无法发起真实登录。",
}


def _client_id() -> str | None:
    value = os.environ.get("ZQKY_CODEX_CLIENT_ID", "").strip()
    return value or None


def _scope() -> str:
    return os.environ.get(
        "ZQKY_CODEX_SCOPE", "openid profile email offline_access"
    ).strip()


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


@dataclass
class CodexLoginOperation:
    operation_id: str
    state: str
    connection_id: str
    code_verifier: str
    callback_port: int
    redirect_uri: str
    authorize_url: str
    started_at: float
    expires_at: float
    operation_state: str = OP_WAITING
    error_code: str | None = None
    cancelled: bool = False
    code: str | None = None
    server: Any = None
    task: Any = None

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


@dataclass
class CodexTokens:
    access_token: str
    refresh_token: str | None = None
    account_id: str | None = None
    expires_at: float = 0.0

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "account_id": self.account_id,
                "expires_at": self.expires_at,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> "CodexTokens | None":
        try:
            data = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(data, dict) or not data.get("access_token"):
            return None
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            account_id=data.get("account_id"),
            expires_at=float(data.get("expires_at") or 0.0),
        )


@dataclass
class _CallbackResult:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    future: asyncio.Future | None = None


class CodexOAuthService:
    """每连接一个授权操作的轻量状态机；令牌经注入的 SecretStore 持久化。"""

    def __init__(self, secret_store) -> None:  # noqa: ANN001 - 避免耦合具体类型
        self._secrets = secret_store
        self._operations: dict[str, CodexLoginOperation] = {}
        self._lock = asyncio.Lock()

    # --- 能力探测 -------------------------------------------------------
    @property
    def app_configured(self) -> bool:
        return bool(_client_id())

    def unavailable_reason(self) -> str | None:
        if not self.app_configured:
            return _ERROR_REASONS["oauth_app_not_configured"]
        return None

    def _tokens_key(self, connection_id: str) -> str:
        return f"codex-tokens:{connection_id}"

    def load_tokens(self, connection_id: str) -> CodexTokens | None:
        raw = self._secrets.resolve(self._tokens_key(connection_id))
        return CodexTokens.from_json(raw) if raw else None

    def store_tokens(self, connection_id: str, tokens: CodexTokens) -> None:
        self._secrets.put(self._tokens_key(connection_id), tokens.to_json())

    def clear_tokens(self, connection_id: str) -> None:
        self._secrets.delete(self._tokens_key(connection_id))

    # --- 状态 -----------------------------------------------------------
    def status(self, connection_id: str) -> dict[str, Any]:
        operation = self._operations.get(connection_id)
        tokens = self.load_tokens(connection_id)
        if operation is not None and operation.operation_state == OP_WAITING:
            if operation.expired:
                operation.operation_state = OP_EXPIRED
                operation.error_code = "login_timeout"
            elif operation.cancelled:
                operation.operation_state = OP_CANCELLED
                operation.error_code = "login_cancelled"
        connected = bool(tokens and tokens.access_token)
        operation_state = operation.operation_state if operation else None
        if operation_state is None and connected:
            operation_state = OP_COMPLETED

        if operation_state == OP_WAITING:
            connection_state = "authorizing"
        elif connected:
            connection_state = "connected"
        elif operation_state in (OP_FAILED, OP_EXPIRED, OP_CANCELLED):
            connection_state = "error"
        else:
            connection_state = "disconnected"

        payload: dict[str, Any] = {
            "connection": connection_state,
            "authMode": "oauth",
            "provider": "openai_codex",
        }
        if operation is not None:
            payload.update(
                {
                    "operationId": operation.operation_id,
                    "operationState": operation.operation_state,
                    "authorizeUrl": operation.authorize_url if operation.operation_state == OP_WAITING else None,
                    "expiresIn": max(0, int(operation.expires_at - time.time())),
                    "errorCode": operation.error_code,
                }
            )
        if connected and tokens is not None:
            payload["accountId"] = tokens.account_id
            payload["userLabel"] = tokens.account_id or "已登录"
        if payload["connection"] != "connected":
            reason = self.unavailable_reason()
            if reason:
                payload["available"] = False
                payload["unavailableReason"] = reason
        return payload

    # --- 授权流程 -------------------------------------------------------
    async def start_login(self, connection_id: str) -> dict[str, Any]:
        if not self.app_configured:
            return {
                "ok": False,
                "errorCode": "OAUTH_APP_NOT_CONFIGURED",
                "message": _ERROR_REASONS["oauth_app_not_configured"],
                "nextSteps": [
                    "在服务端配置 ZQKY_CODEX_CLIENT_ID（智启课源自有 OAuth 应用）后重启 API。",
                    "本机回环回调端口默认 1455/1457，可由部署配置覆盖。",
                ],
            }
        async with self._lock:
            existing = self._operations.get(connection_id)
            if existing is not None and existing.operation_state == OP_WAITING and not existing.expired:
                return {"ok": True, "status": self.status(connection_id)}

            verifier, challenge = _pkce_pair()
            state = secrets.token_urlsafe(24)
            operation_id = secrets.token_hex(16)

            server, port = await self._bind_callback_server()
            if server is None:
                return {
                    "ok": False,
                    "errorCode": "callback_unavailable",
                    "message": _ERROR_REASONS["callback_unavailable"],
                }
            redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
            params = {
                "response_type": "code",
                "client_id": _client_id(),
                "redirect_uri": redirect_uri,
                "scope": _scope(),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
            authorize_url = f"{AUTH_ISSUER}/oauth/authorize?{urllib.parse.urlencode(params)}"
            operation = CodexLoginOperation(
                operation_id=operation_id,
                state=state,
                connection_id=connection_id,
                code_verifier=verifier,
                callback_port=port,
                redirect_uri=redirect_uri,
                authorize_url=authorize_url,
                started_at=time.time(),
                expires_at=time.time() + LOGIN_TIMEOUT_SECONDS,
                server=server,
            )
            self._operations[connection_id] = operation
            operation.task = asyncio.create_task(self._await_callback(operation))
            return {"ok": True, "status": self.status(connection_id)}

    async def _bind_callback_server(self) -> tuple[Any, int]:
        for port in DEFAULT_CALLBACK_PORTS:
            try:
                server = await asyncio.start_server(
                    lambda r, w, s=self: self._handle_callback(r, w),  # noqa: ARG005
                    host="127.0.0.1",
                    port=port,
                )
            except OSError:
                continue
            return server, port
        return None, 0

    async def _handle_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
            request_line = raw.split(b"\r\n", 1)[0].decode("latin-1")
            parts = request_line.split(" ")
            query = urllib.parse.urlparse(parts[1] if len(parts) > 1 else "").query
            params = urllib.parse.parse_qs(query)
            code = (params.get("code") or [None])[0]
            state = (params.get("state") or [None])[0]
            error = (params.get("error") or [None])[0]
            for operation in list(self._operations.values()):
                if operation.state == state:
                    if operation.cancelled or operation.operation_state != OP_WAITING:
                        break
                    if error:
                        operation.operation_state = OP_FAILED
                        operation.error_code = "authorization_denied" if error == "access_denied" else "oauth_callback_failed"
                    elif not code:
                        operation.operation_state = OP_FAILED
                        operation.error_code = "oauth_callback_failed"
                    else:
                        operation.code = code
                        operation.operation_state = OP_COMPLETED
                    break
            body = b"<html><body><p>Authorization received. This window can be closed.</p></body></html>"
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            await writer.drain()
        except Exception:  # noqa: BLE001 - 回调解析失败不应影响主流程
            pass
        finally:
            writer.close()

    async def _await_callback(self, operation: CodexLoginOperation) -> None:
        # 等待回调状态机到达终态或超时，然后交换令牌
        try:
            deadline = operation.started_at + LOGIN_TIMEOUT_SECONDS
            while time.time() < deadline:
                if operation.cancelled:
                    operation.operation_state = OP_CANCELLED
                    operation.error_code = "login_cancelled"
                    return
                if operation.operation_state in (OP_COMPLETED, OP_FAILED):
                    break
                await asyncio.sleep(0.25)
            else:
                operation.operation_state = OP_EXPIRED
                operation.error_code = "login_timeout"
                return
            if operation.operation_state != OP_COMPLETED:
                return
            code = operation.code
            if not code:
                operation.operation_state = OP_FAILED
                operation.error_code = "state_mismatch"
                return
            tokens = await self._exchange_code(operation, code)
            if tokens is None:
                operation.operation_state = OP_FAILED
                operation.error_code = "token_exchange_failed"
                return
            self.store_tokens(operation.connection_id, tokens)
        finally:
            await self._close_server(operation)

    async def _exchange_code(self, operation: CodexLoginOperation, code: str) -> CodexTokens | None:
        payload = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "client_id": _client_id(),
                "code": code,
                "code_verifier": operation.code_verifier,
                "redirect_uri": operation.redirect_uri,
            }
        ).encode("ascii")
        data = await asyncio.to_thread(self._post_token, payload)
        if not data or not data.get("access_token"):
            return None
        return CodexTokens(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            account_id=data.get("account_id"),
            expires_at=time.time() + float(data.get("expires_in") or 3600),
        )

    def _post_token(self, payload: bytes) -> dict[str, Any] | None:
        request = urllib.request.Request(
            f"{AUTH_ISSUER}/oauth/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - 固定 https 常量
                return json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return None

    async def cancel_login(self, connection_id: str) -> dict[str, Any]:
        operation = self._operations.get(connection_id)
        if operation is None:
            return {"ok": False, "errorCode": "login_not_active", "message": "当前没有进行中的授权。"}
        if operation.operation_state == OP_WAITING:
            operation.cancelled = True
            operation.operation_state = OP_CANCELLED
            operation.error_code = "login_cancelled"
        await self._close_server(operation)
        return {"ok": True, "status": self.status(connection_id)}

    async def logout(self, connection_id: str) -> dict[str, Any]:
        operation = self._operations.get(connection_id)
        if operation is not None and operation.operation_state == OP_WAITING:
            operation.cancelled = True
            operation.operation_state = OP_CANCELLED
            await self._close_server(operation)
        tokens = self.load_tokens(connection_id)
        self.clear_tokens(connection_id)
        if tokens and tokens.access_token:
            await asyncio.to_thread(self._revoke, tokens.access_token)
        return {"ok": True, "status": self.status(connection_id)}

    def _revoke(self, token: str) -> None:
        payload = urllib.parse.urlencode({"token": token}).encode("ascii")
        request = urllib.request.Request(
            f"{AUTH_ISSUER}/oauth/revoke",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):  # noqa: S310
                pass
        except Exception:  # noqa: BLE001 - 撤销失败静默，本地凭据已清理
            pass

    async def _close_server(self, operation: CodexLoginOperation) -> None:
        server = operation.server
        if server is not None:
            server.close()
            try:
                await server.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            operation.server = None

    def has_token(self, connection_id: str) -> bool:
        tokens = self.load_tokens(connection_id)
        return bool(tokens and tokens.access_token)


__all__ = [
    "CODEX_DEFAULT_MODEL",
    "CodexOAuthService",
    "CodexTokens",
    "OP_CANCELLED",
    "OP_COMPLETED",
    "OP_EXPIRED",
    "OP_FAILED",
    "OP_WAITING",
]
