"""Private B5 serialization and visible validation errors; no app assembly imports."""
from __future__ import annotations

import json
from app.core.exceptions import AppError


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshot(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True, mode="json")
    return json.loads(dump(value))


def invalid(field: str, message: str, code="LESSON_PROPOSAL_INVALID") -> AppError:
    return AppError(message, code=code, status_code=422,
                    details={"issues": [{"field": field, "code": code, "message": message}]})


def exact_keys(value, keys, field):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise invalid(field, "对象字段不符合冻结结构。")


def parse_output(text: str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, TypeError, RecursionError) as exc:
        raise invalid("response", "模型必须返回完整、无重复字段的严格 JSON 对象。") from exc
    if not isinstance(value, dict):
        raise invalid("response", "模型必须返回 JSON 对象。")
    return value
