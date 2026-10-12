"""Practice-only validation; no IO or shared mutable state."""
import json
import re
from typing import Any
from app.core.exceptions import AppError


def invalid(message: str, field: str = "items", code: str = "PRACTICE_INVALID") -> AppError:
    return AppError(message, code=code, status_code=422,
                    details={"issues": [{"field": field, "code": code, "message": message}]})


def stale(revision: int) -> AppError:
    return AppError("草稿已更新，请核对后重试。", code="REVISION_CONFLICT", status_code=409,
                    details={"currentRevision": revision, "fields": ["expectedRevision"]})


def units(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d{1,2})?", value.strip()):
        raise invalid("满分必须是最多两位小数的十进制文本。", "maxScore")
    whole, _, fraction = value.strip().partition(".")
    if len(whole) > 14:
        raise invalid("满分超出支持范围。", "maxScore")
    result = int(whole) * 100 + int((fraction + "00")[:2])
    if result <= 0:
        raise invalid("计分叶满分必须大于零。", "maxScore")
    return result


def unique(values: list, field: str) -> None:
    if len(values) != len(set(values)):
        raise invalid("不允许重复身份。", field)


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode(value: str, expected: type = dict):
    try:
        result = json.loads(value)
        if not isinstance(result, expected):
            raise ValueError()
        return result
    except (TypeError, ValueError) as exc:
        raise AppError("练习封存数据损坏。", code="PRACTICE_DATA_CORRUPT", status_code=500) from exc


def page(offset: int, limit: int) -> None:
    if isinstance(offset, bool) or isinstance(limit, bool) or offset < 0 or not 1 <= limit <= 200:
        raise invalid("分页参数非法。", "limit")
