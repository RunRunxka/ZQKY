"""统一错误模型：code、message、requestId、retryable、details。

details 只允许携带脱敏、适合前端展示的内容；本模块不输出任何环境或配置信息。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.responses import JSONResponse


def new_request_id() -> str:
    return uuid.uuid4().hex


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "requestId": request_id or new_request_id(),
        "retryable": retryable,
    }
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers={"X-Request-Id": body["requestId"]})
