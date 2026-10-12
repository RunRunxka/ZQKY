"""题库指纹：题目内容指纹（重复检测）与请求指纹（提交幂等）。

内容指纹的组成固定为 ``{type, 题干, 有序选项, 资产内容散列}``，**不含答案与解析**：
同一题干不同答案视为冲突，进入重复校对，而不是自动当成两道题。

派生指纹（B2，版本化）与旧 ``content_fingerprint`` **并存、互不改写**：

- ``content_fingerprint`` 是历史事实，算法与组成一个字不动；旧 Markdown 题在新版本里
  照样可读、可确认、可检索；
- ``derived_content_fingerprint`` 是新事实，算法版本常量 ``derived-v1``，组成 =
  旧内容指纹 + 共享材料（按序规范化文本）+ 富内容 JSON + 每份资产的**真实字节 sha256**；
  写入 ``question_content_fingerprints``（``(question_revision_id, algorithm_version)`` 唯一），
  重复计算幂等，补算绝不改写旧列；
- **富内容权威规则**：当题目携带富内容（``rich_content`` 非空）时，**富内容是权威内容**，
  Markdown 只是它的派生展示；派生指纹以富内容 JSON 为准，因此"富内容变了、Markdown 没变"
  与"Markdown 变了、富内容没变"是两种不同变化。B2 只落地这条规则与指纹组成，
  富内容的存储与渲染属后续批次；
- 资产散列：``assetIds`` 里的 ``blobs/<64 位小写 hex>`` 键是内容寻址键，**键值本身即
  写入时校验过的真实字节散列**（题库 blob 与受管资产存储都在写入/读取时重算）；
  旧形状 id（非 ``blobs/`` 键，历史上无字节可读）沿用 ``asset_content_hash`` 占位散列，
  不伪造真实字节。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

#: 派生指纹算法版本；改变组成必须换版本号，历史行保留供比对
DERIVED_ALGORITHM_VERSION = "derived-v1"

# 去重只比较题面，不能复用含答案、来源和随机块 ID 的 derived-v1。
# 新版本追加登记，历史 content_fingerprint / derived-v1 不改写。
DUPLICATE_ALGORITHM_VERSION = "question-surface-v1"

_BLOB_ASSET_PATTERN = re.compile(r"blobs/([0-9a-f]{64})")

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


def asset_byte_hash(asset_id: str) -> str:
    """资产**真实字节** sha256：``blobs/<hex>`` 是内容寻址键，hex 即写入时校验过的散列。

    非 ``blobs/`` 形状的旧 id 没有可读字节，退回 ``asset_content_hash`` 占位，
    绝不把占位值冒充成真实字节散列（由调用方按需拒绝这类引用）。
    """
    match = _BLOB_ASSET_PATTERN.fullmatch(str(asset_id))
    if match is not None:
        return match.group(1)
    return asset_content_hash(asset_id)


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


def derived_content_fingerprint(
    content: Mapping[str, Any],
    *,
    rich_content: Any = None,
    materials: Sequence[str] = (),
    asset_hashes: Mapping[str, str] | None = None,
) -> str:
    """版本化派生指纹（``derived-v1``）：旧内容指纹 + 共享材料 + 富内容 + 资产真实字节散列。

    - ``content``：题库题面（Markdown 形状）；旧指纹 ``content_fingerprint(content)`` 是
      派生输入之一，保证"只改题干/选项"同样改变派生值；
    - ``rich_content``：存在即权威（见模块 docstring 的富内容权威规则），按规范 JSON 入散列；
    - ``materials``：共享材料的**按序**规范化文本（同一材料重复出现也保留顺序）；
    - ``asset_hashes``：``assetId -> 真实字节 sha256`` 的覆盖表；覆盖表里没有的 id 按
      ``asset_byte_hash`` 解析（``blobs/<hex>`` 键即散列，其余为兼容占位）。
      调用方拿到的是"已经校验过真实字节"的映射时应显式传入，避免二次读取。
    """
    asset_ids = [str(item) for item in content.get("assetIds") or []]
    overrides = asset_hashes or {}
    assets = [
        {
            "assetId": asset_id,
            "sha256": str(overrides.get(asset_id) or asset_byte_hash(asset_id)),
        }
        for asset_id in asset_ids
    ]
    payload = {
        "algorithmVersion": DERIVED_ALGORITHM_VERSION,
        "contentFingerprint": content_fingerprint(dict(content)),
        "richContent": rich_content if rich_content not in (None, {}, [], "") else None,
        "materials": [
            normalize_markdown(str(material)) for material in materials
        ],
        "assets": assets,
    }
    return sha256_text(canonical_json(payload))


def request_fingerprint(payload: Any) -> str:
    """确认入库的请求指纹：只覆盖会影响结果的字段，保证同载荷重放命中同一条结果。"""
    return sha256_text(canonical_json(payload))


def duplicate_content_fingerprint(
    content: Mapping[str, Any], *, asset_hashes: Mapping[str, str] | None = None
) -> str:
    """权威题面身份（question-surface-v1），纯计算、无文件或数据库 IO。

    富内容存在时按有序材料/题干/选项的真实结构计算；块/材料 ID、来源、
    答案、解析与教师专用图片不参与。图片取预检真实字节散列，历史修订取
    已冻结声明/内容寻址键。普通段落投影与旧 Markdown 可比较；含表格、
    公式、图片的权威结构不能被降级成旧 plain 文本后判为重复。
    不同算法版本的散列不直接比较，缺新版本的旧题从冻结 content 只读重算。
    """
    overrides = asset_hashes or {}
    rich = content.get("richContent")
    rich = rich if isinstance(rich, Mapping) else None

    def field(value: Mapping[str, Any], alias: str, default: Any = None) -> Any:
        # 内部 QuestionContent.model_dump 的 RichContentV2 为 snake_case；HTTP 为 camelCase。
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", alias).lower()
        return value[alias] if alias in value else value.get(snake, default)

    declarations = {
        str(field(asset, "assetId")): str(asset.get("sha256"))
        for asset in (rich.get("assets") or []) if isinstance(asset, Mapping)
    } if rich else {}

    def image_hash(asset_id: str) -> str:
        if asset_id in overrides:
            return str(overrides[asset_id])
        if asset_id in declarations:
            return declarations[asset_id]
        if re.fullmatch(r"[0-9a-f]{64}", asset_id):
            return asset_id
        return asset_byte_hash(asset_id)

    def blocks_identity(blocks: Sequence[Mapping[str, Any]]) -> Any:
        # 等价普通段落保留旧 Markdown 判重语义，不让随机分块身份造新题。
        if all(block.get("kind") == "paragraph" for block in blocks):
            return {"kind": "markdown", "text": normalize_markdown(
                "\n\n".join(str(block.get("text", "")) for block in blocks)
            )}
        result = []
        for block in blocks:
            kind = block.get("kind")
            if kind == "paragraph":
                result.append({"kind": kind, "text": normalize_markdown(str(block.get("text", "")))})
            elif kind == "table":
                result.append({"kind": kind, "columnCount": field(block, "columnCount"), "cells": [
                    {"text": normalize_markdown(str(cell.get("text", ""))),
                     "isHeader": bool(field(cell, "isHeader", False)),
                     "rowSpan": field(cell, "rowSpan", 1), "colSpan": field(cell, "colSpan", 1)}
                    for cell in block.get("cells") or []
                ]})
            elif kind == "formula":
                result.append({"kind": kind, "latex": str(block.get("latex") or "").strip(),
                               "ommlXml": str(field(block, "ommlXml") or "").strip()})
            elif kind == "image":
                result.append({"kind": kind, "sha256": image_hash(str(field(block, "assetId", ""))),
                               "width": block.get("width", 0), "height": block.get("height", 0)})
            else:
                raise ValueError("未知权威题面块类型，不能降级为空内容判重")
        return {"kind": "blocks", "blocks": result}

    def markdown_identity(text: Any) -> dict[str, str]:
        return {"kind": "markdown", "text": normalize_markdown(str(text or ""))}

    options = content.get("options") or []
    payload = {
        "algorithmVersion": DUPLICATE_ALGORITHM_VERSION,
        "type": content.get("type"),
        "materials": [blocks_identity(material.get("blocks") or [])
                      for material in field(rich, "sharedMaterials") or []] if rich else [],
        "stem": blocks_identity(field(rich, "stemBlocks") or []) if rich
                else markdown_identity(content.get("stemMarkdown")),
        "options": [{"key": str(option.get("key", "")).strip(),
                     "content": blocks_identity((field(rich, "optionBlocks") or {}).get(option.get("key")) or [])
                     if rich else markdown_identity(option.get("textMarkdown"))}
                    for option in options],
        # rich 中图片已在实际题面块对应位置参与；答案/解析图不影响题面。
        "plainAssets": [] if rich else [image_hash(str(asset_id))
                                         for asset_id in content.get("assetIds") or []],
    }
    return sha256_text(canonical_json(payload))
