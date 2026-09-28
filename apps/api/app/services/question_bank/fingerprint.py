"""题库指纹：题目内容指纹（重复检测）与请求指纹（提交幂等）。

内容指纹的组成固定为 ``{type, 题干, 有序选项, 资产内容散列}``，**不含答案与解析**：
同一题干不同答案视为冲突，进入重复校对，而不是自动当成两道题。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_WHITESPACE_RUN = re.compile(r"[ \t\u3000]+")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_markdown(text: str) -> str:
    """稳定化文本：统一换行、逐行去首尾空白、压缩行内空白、去掉首尾空行。"""
    if not isinstance(text, str):
        raise TypeError("normalize_markdown 只接受字符串")
    lines = [
        _WHITESPACE_RUN.sub(" ", line.strip())
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def asset_content_hash(asset_id: str) -> str:
    """资产内容散列；资产存储尚未落地，暂以 assetId 的 sha256 作为稳定占位。

    资产落地后改为对内容字节计算，指纹组成与算法位置不变。
    """
    return sha256_text(asset_id)


def content_fingerprint(content: dict[str, Any]) -> str:
    payload = {
        "type": content.get("type"),
        "stem": normalize_markdown(str(content.get("stemMarkdown", ""))),
        "options": [
            {
                "key": str(option.get("key", "")).strip(),
                "text": normalize_markdown(str(option.get("textMarkdown", ""))),
            }
            for option in content.get("options") or []
        ],
        "assetHashes": [
            asset_content_hash(str(asset_id)) for asset_id in content.get("assetIds") or []
        ],
    }
    return sha256_text(canonical_json(payload))


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_fingerprint(payload: Any) -> str:
    """确认入库的请求指纹：只覆盖会影响结果的字段，保证同载荷重放命中同一条结果。"""
    return sha256_text(canonical_json(payload))
