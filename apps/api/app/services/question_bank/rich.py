"""题库富内容的权威投影与只读资产核验；文件读取必须在 SQL 写事务外。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.teaching_loop import ContentBlock, ErrorIssue, RichContentV2, error_details
from app.core.exceptions import AppError
from app.schemas.question_bank import QuestionContent
from app.services.assets.store import AssetStore, is_managed_blob_key, is_sha256_hex
from app.services.question_bank.blobs import QuestionBlobStore
from app.services.question_bank.fingerprint import normalize_markdown


def _invalid(message: str, *, field: str, code: str = "QUESTION_RICH_CONTENT_INVALID") -> AppError:
    return AppError(message, code=code, status_code=422, details=error_details(issues=[
        ErrorIssue(field=field, code=code, message=message),
    ]))


def blocks_of(rich: RichContentV2) -> list[ContentBlock]:
    """遍历全部教师/学生内容，共享材料按其声明顺序只遍历一次。"""
    return [
        *[block for material in rich.shared_materials for block in material.blocks],
        *rich.stem_blocks,
        *[block for blocks in rich.option_blocks.values() for block in blocks],
        *rich.answer_blocks, *rich.explanation_blocks,
    ]


def project_blocks(blocks: Sequence[ContentBlock]) -> str:
    """确定性派生文本：块间空行；表格按原 cells 次序用 | 拼接；原结构仍在 rich。

    LaTeX = $$...$$；只有 OMML = [原始公式]；图片 = ![图片](assetId)。
    此文本用于兼容旧 Markdown、检索与校验，结构化渲染仍使用 rich 本体。
    """
    parts: list[str] = []
    for block in blocks:
        if block.kind == "paragraph":
            parts.append(block.text)
        elif block.kind == "table":
            parts.append("[表格]\n" + " | ".join(cell.text for cell in block.cells))
        elif block.kind == "formula":
            if block.latex and block.latex.strip():
                parts.append("$$" + block.latex.strip() + "$$")
            elif block.omml_xml and block.omml_xml.strip():
                parts.append("[原始公式]")
            else:
                raise _invalid("公式块必须有 LaTeX 或原始 OMML。", field="content.richContent")
        elif block.kind == "image":
            parts.append(f"![图片]({block.asset_id})")
    return normalize_markdown("\n\n".join(parts))


def image_ids(rich: RichContentV2) -> set[str]:
    return {block.asset_id for block in blocks_of(rich) if block.kind == "image"}


def validate_projection(content: QuestionContent, *, previous: Mapping[str, Any] | None = None) -> None:
    """富内容存在时 Markdown 必须等于明确投影；移除旧 rich 必须显式 null。"""
    rich = content.richContent
    if previous and previous.get("richContent") is not None and rich is None:
        if "richContent" not in content.model_fields_set:
            raise _invalid("当前题目含富内容；转为 Markdown 必须明确提供 richContent=null。",
                           field="content.richContent", code="QUESTION_RICH_CONTENT_CLEAR_REQUIRED")
    if rich is None:
        return
    all_blocks = blocks_of(rich)
    block_ids = [block.id for block in all_blocks]
    material_ids = [material.id for material in rich.shared_materials]
    if len(set(block_ids)) != len(block_ids) or len(set(material_ids)) != len(material_ids):
        raise _invalid("富内容块或共享材料 ID 重复。", field="content.richContent")
    expected: list[tuple[str, str, str]] = [
        ("content.stemMarkdown", content.stemMarkdown, project_blocks(rich.stem_blocks)),
        ("content.explanationMarkdown", content.explanationMarkdown or "", project_blocks(rich.explanation_blocks)),
    ]
    if set(rich.option_blocks) != {option.key for option in content.options}:
        raise _invalid("富内容选项 key 必须与 Markdown 选项集合一致。", field="content.options")
    for option in content.options:
        expected.append((f"content.options.{option.key}.textMarkdown", option.textMarkdown,
                         project_blocks(rich.option_blocks[option.key])))
    answer = content.answer
    answer_text = ""
    if answer is not None:
        if content.type in {"single_choice", "multiple_choice"} and answer.choiceKeys:
            answer_text = ", ".join(answer.choiceKeys)
        elif content.type == "true_false" and answer.accepted is not None:
            answer_text = "true" if answer.accepted else "false"
        elif answer.textMarkdown and answer.textMarkdown.strip():
            answer_text = answer.textMarkdown
        elif answer.choiceKeys:
            answer_text = ", ".join(answer.choiceKeys)
        elif answer.accepted is not None:
            answer_text = "true" if answer.accepted else "false"
    expected.append(("content.answer", answer_text, project_blocks(rich.answer_blocks)))
    for field, supplied, projection in expected:
        if normalize_markdown(supplied) != projection:
            raise _invalid("Markdown 与富内容的确定性投影不一致；请同步编辑富内容，或明确转为 Markdown。",
                           field=field, code="QUESTION_RICH_CONTENT_MISMATCH")
    if answer is not None and answer.textMarkdown and answer.textMarkdown.strip():
        if normalize_markdown(answer.textMarkdown) != project_blocks(rich.answer_blocks):
            raise _invalid("答案文本与富内容答案投影不一致；请同步编辑富内容，或明确转为 Markdown。",
                           field="content.answer.textMarkdown", code="QUESTION_RICH_CONTENT_MISMATCH")
    # 材料/答案等未进入 stem 投影的块也要校验公式语义。
    project_blocks(all_blocks)
    referenced = image_ids(rich)
    declared = [asset.asset_id for asset in rich.assets]
    if len(declared) != len(set(declared)) or set(declared) != referenced:
        raise _invalid("富内容 assets 必须恰好声明所有图片块引用，不能重复或声明未引用资产。",
                       field="content.richContent.assets")
    if len(content.assetIds) != len(set(content.assetIds)) or set(content.assetIds) != referenced:
        raise _invalid("assetIds 必须与富内容图片块的资产集合一致。", field="content.assetIds")


def image_media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    return "application/octet-stream"


def read_asset(asset_id: str, *, assets: AssetStore, blobs: QuestionBlobStore) -> tuple[bytes, str]:
    """只允许严格 managed key 或兼容题库 bare SHA；坏 managed 文件不能靠 fallback 掩盖。"""
    if is_managed_blob_key(asset_id):
        if assets.exists(asset_id):
            data = assets.read(asset_id)
        else:
            data = blobs.read(asset_id.split("/", 1)[1])
        digest = asset_id.split("/", 1)[1]
    elif is_sha256_hex(asset_id):
        data = blobs.read(asset_id)
        digest = asset_id
    else:
        raise _invalid("图片资产只允许 blobs/<64位小写sha256> 或兼容题库64位sha256。",
                       field="assetId", code="INVALID_ASSET_KEY")
    if hashlib.sha256(data).hexdigest() != digest:  # 两个 store 已核验，再守适配边界。
        raise AppError("题库图片字节散列不符。", code="QUESTION_ASSET_CORRUPT", status_code=500)
    return data, image_media_type(data)


def verify_assets(content: QuestionContent, *, assets: AssetStore, blobs: QuestionBlobStore) -> dict[str, str]:
    """新 rich 的所有图片都必须有真实字节；旧 Markdown 资产组成保持兼容。"""
    rich = content.richContent
    if rich is None:
        return {}
    hashes: dict[str, str] = {}
    for declaration in rich.assets:
        try:
            data, media_type = read_asset(declaration.asset_id, assets=assets, blobs=blobs)
        except AppError as exc:
            if exc.code in {"ASSET_MISSING", "QUESTION_BLOB_MISSING"}:
                raise _invalid("富内容引用的图片没有已登记真实字节。", field="content.richContent.assets",
                               code="QUESTION_ASSET_NOT_FOUND") from exc
            raise
        digest = hashlib.sha256(data).hexdigest()
        if declaration.sha256 != digest:
            raise _invalid("富内容声明的图片散列与真实字节不一致。", field="content.richContent.assets",
                           code="QUESTION_ASSET_DIGEST_MISMATCH")
        if media_type == "application/octet-stream" or declaration.media_type != media_type:
            raise _invalid("富内容图片类型与真实字节魔数不一致或无法识别。", field="content.richContent.assets",
                           code="QUESTION_ASSET_MEDIA_INVALID")
        hashes[declaration.asset_id] = digest
    return hashes
