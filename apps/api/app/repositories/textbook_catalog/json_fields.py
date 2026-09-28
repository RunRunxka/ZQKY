"""教材目录 JSON 列的唯一读写入口：写前规范化，读回校验，损坏不覆盖。

约束：
- 存储层里 JSON 列是 TEXT；损坏或结构不符一律抛 ``CATALOG_CORRUPT``（500），
  禁止当空值/默认值静默继续，也禁止自动改写原行。
- 调用方传参不合法属于请求错误（422 ``INVALID_REQUEST``），与数据损坏区分开。
- 写入使用固定分隔符与键序，保证同一逻辑内容产生同一字节串（便于指纹比较）。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.core.exceptions import AppError


def corrupt(field: str, detail: str = "") -> AppError:
    suffix = f"（{detail}）" if detail else ""
    return AppError(
        f"教材目录数据损坏：{field} 不是合法 JSON 或结构不符{suffix}；读取已停止，不会自动覆盖。",
        code="CATALOG_CORRUPT",
        status_code=500,
    )


def invalid(field: str, detail: str) -> AppError:
    return AppError(f"{field} 不合法：{detail}", code="INVALID_REQUEST", status_code=422)


def _decode(raw: object, *, field: str) -> Any:
    if not isinstance(raw, str):
        raise corrupt(field, "不是文本列")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise corrupt(field, "JSON 解析失败") from exc


def read_object(raw: object, *, field: str, allow_none: bool = False) -> dict[str, Any] | None:
    """读回 JSON 对象列；``allow_none`` 仅用于本身可空的列（如 import 草稿的中间产物）。"""
    if raw is None:
        if allow_none:
            return None
        raise corrupt(field, "缺列值")
    value = _decode(raw, field=field)
    if not isinstance(value, dict):
        raise corrupt(field, "期望 JSON 对象")
    return value


def read_string_list(raw: object, *, field: str, allow_empty: bool = True) -> list[str]:
    """读回字符串数组列；元素必须是非空字符串。"""
    value = _decode(raw, field=field)
    if not isinstance(value, list):
        raise corrupt(field, "期望 JSON 数组")
    if not allow_empty and not value:
        raise corrupt(field, "数组为空")
    if any(not isinstance(item, str) or not item for item in value):
        raise corrupt(field, "数组元素不是非空字符串")
    return list(value)


def _coerce_object(value: object, *, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    parsed: object = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            raise invalid(field, "不是合法 JSON") from exc
    if not isinstance(parsed, dict):
        raise invalid(field, "期望 JSON 对象")
    return parsed


def write_object(value: object, *, field: str, allow_none: bool = False) -> str | None:
    """写前规范化：接受 dict、JSON 对象字符串或 None（仅可空列）。"""
    parsed = _coerce_object(value, field=field)
    if parsed is None:
        if allow_none:
            return None
        raise invalid(field, "不能为空")
    return json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_string_list(value: object, *, field: str, allow_none: bool = False) -> str | None:
    """写前规范化：接受字符串序列、JSON 数组字符串或 None（仅可空列）。"""
    if value is None:
        if allow_none:
            return None
        raise invalid(field, "不能为空")
    parsed: object = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            raise invalid(field, "不是合法 JSON") from exc
    if isinstance(parsed, (str, bytes)) or not isinstance(parsed, Sequence):
        raise invalid(field, "期望字符串序列")
    items = list(parsed)
    if any(not isinstance(item, str) or not item for item in items):
        raise invalid(field, "元素必须是非空字符串")
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))
