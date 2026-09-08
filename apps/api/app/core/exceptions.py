"""服务层异常：由统一错误处理转换为错误信封。"""

from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "REQUEST_FAILED"
    retryable = False

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None, retryable: bool | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        if retryable is not None:
            self.retryable = retryable


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class RevisionConflictError(AppError):
    status_code = 409
    code = "REVISION_CONFLICT"
    retryable = False


class InvalidRequestError(AppError):
    status_code = 422
    code = "INVALID_REQUEST"


class ConfigCorruptedError(AppError):
    status_code = 500
    code = "CONFIG_CORRUPTED"
