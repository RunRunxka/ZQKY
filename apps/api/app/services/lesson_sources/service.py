"""教师上传的学情材料（教案生成来源）：受管资产登记 + 文本提取。

2026-10-13 补齐：前端「上传学情文件」此前调用 ``POST /lesson-plans/source-uploads``，
但该端点从未实现（落 ``FEATURE_NOT_IMPLEMENTED`` 501），且生成流声明「不消费
``sourceAssetRef``」——即上传本身与上传结果都不成立。本模块把这一环做实。

范围与红线口径（只做能如实做到的）：
- **只接收可提取文本的文档**（``.docx``/``.pdf``/``.txt``/``.md``）：教师自写的学情说明、
  或由本产品导出的学情分析报告（学生已是代称）。
- **表格类（``.xlsx``/``.xls``/``.csv``）不接收**：这类文件通常是含学号/姓名的原始成绩表，
  直接送进模型会破坏「学生个人信息不进模型」的红线；成绩数据的脱敏聚合在本产品里有既定
  入口（学情分析：导入 → 确认 → 生成学情报告，学生以代称进模型），这里不发明第二套口径。
  上传该类型文件时给出可操作指引（去生成/选择分析报告），而不是静默降级。
- 提取文本按上限截断并**明确标注**截断（不静默丢内容）；扫描件 PDF（无文本层）如实报错。

资产沿用全站同一套受管资产机制：``AssetStore`` 落 blob（内容寻址）+
``FileAssetsRepository`` 登记 ``file_assets`` 行（``kind="attachment"``）；``assetRef`` 即
资产 id，生成流按 id 归属校验后读回。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.assets.store import AssetStore

#: 上传字节上限（与 agent/upload 同一量级；教案材料是短文档，10 MiB 足够）。
MAX_SOURCE_BYTES = 10 * 1024 * 1024

#: 注入模型的材料正文上限（字符）：超出按上限截断并在文中标注。
MAX_MATERIAL_CHARS = 6000

#: 可接收的文件后缀（文档类；表格类在这里明确不接收，见模块 docstring）。
DOCUMENT_SUFFIXES: frozenset[str] = frozenset({".docx", ".pdf", ".txt", ".md"})

#: 表格类后缀：给出「去学情分析 → 生成报告」的指引，而不是含糊的格式错误。
SPREADSHEET_SUFFIXES: frozenset[str] = frozenset({".xlsx", ".xls", ".csv"})

TRUNCATION_NOTE = "（此处起内容超过上限已截断）"

_GUIDANCE = (
    "可上传的文件：.docx / .pdf / .txt / .md 的学情说明或学情分析报告；"
    "若你手头是成绩表（.xlsx/.xls/.csv）：请先在「学情分析」导入并确认成绩、生成学情报告，"
    "再回到本面板把来源选成「分析报告」——学生以代称进模型，原始姓名/学号不会发给模型。"
)


@dataclass(frozen=True)
class LessonSourceAsset:
    """上传结果（对外 camelCase 视图由契约模型序列化）。"""

    asset_ref: str
    file_name: str
    media_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class LessonSourceMaterial:
    """生成流可用的材料：文件名 + 已截断标注的正文。"""

    file_name: str
    text: str
    truncated: bool


def _suffix_of(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def _invalid(message: str, *, code: str, status_code: int) -> AppError:
    return AppError(message, code=code, status_code=status_code)


class LessonSourceService:
    """上传/读回教师学情材料；注入已迁移的教学库 + 受管资产存储。"""

    def __init__(
        self,
        *,
        asset_store: AssetStore,
        file_assets: FileAssetsRepository,
        owner_id: str = "local",
    ) -> None:
        self._assets = asset_store
        self._file_assets = file_assets
        self._owner_id = owner_id

    # ------------------------------------------------------------ 上传

    def upload(self, *, data: bytes, file_name: str, media_type: str) -> LessonSourceAsset:
        """校验 → 落 blob → 登记资产；任一步失败如实抛出，不产生半成品登记。"""
        name = (file_name or "").strip()
        if not name:
            raise _invalid("上传文件缺少文件名。", code="INVALID_REQUEST", status_code=422)
        if not data:
            raise _invalid("上传文件为空。", code="INVALID_REQUEST", status_code=422)
        if len(data) > MAX_SOURCE_BYTES:
            raise _invalid(
                f"上传文件超过 {MAX_SOURCE_BYTES // (1024 * 1024)} MiB 上限。",
                code="UPLOAD_TOO_LARGE",
                status_code=413,
            )
        suffix = _suffix_of(name)
        if suffix in SPREADSHEET_SUFFIXES:
            raise _invalid(
                f"成绩表类文件（{suffix}）不直接接收：避免把含学号/姓名的原始表格发给模型。{_GUIDANCE}",
                code="LESSON_SOURCE_UNSUPPORTED",
                status_code=422,
            )
        if suffix not in DOCUMENT_SUFFIXES:
            raise _invalid(
                f"不支持的文件类型「{suffix or name}」。{_GUIDANCE}",
                code="LESSON_SOURCE_UNSUPPORTED",
                status_code=422,
            )
        stored = self._assets.store_original(
            data, media_type=media_type or "application/octet-stream", original_name=name
        )
        record = self._file_assets.create(
            kind="attachment",
            blob_key=stored.blob_key,
            sha256=stored.sha256,
            media_type=media_type or "application/octet-stream",
            byte_size=stored.byte_size,
            original_name=name,
            owner_id=self._owner_id,
        )
        return LessonSourceAsset(
            asset_ref=record.asset_id,
            file_name=record.original_name,
            media_type=record.media_type,
            byte_size=record.byte_size,
            sha256=record.sha256,
        )

    # ------------------------------------------------------------ 读回

    def read_material(self, asset_ref: str) -> LessonSourceMaterial:
        """按 ``assetRef`` 读回材料正文（归属校验 + 指纹校验），失败给出可读原因。"""
        reference = (asset_ref or "").strip()
        if not reference:
            raise _invalid("缺少 sourceAssetRef。", code="INVALID_REQUEST", status_code=422)
        record = self._file_assets.get(reference)
        if record is None or record.owner_id != self._owner_id:
            raise _invalid(
                "学情材料不存在或不属于当前教师：请重新上传后再生成（不静默忽略该来源）。",
                code="LESSON_SOURCE_NOT_FOUND",
                status_code=404,
            )
        # AssetStore 自身核对文件存在与 sha256 指纹（缺失/不符按其错误码 500 抛出）
        self._assets.read(record.blob_key)
        text = self._extract_text(record.original_name, record.blob_key)
        if not text.strip():
            raise _invalid(
                f"「{record.original_name}」没有可提取的文本"
                "（例如扫描件 PDF 没有文本层）。请上传含可复制文本的文件，或改用「分析报告」来源。",
                code="LESSON_SOURCE_EMPTY",
                status_code=422,
            )
        truncated = len(text) > MAX_MATERIAL_CHARS
        if truncated:
            text = text[:MAX_MATERIAL_CHARS] + TRUNCATION_NOTE
        return LessonSourceMaterial(
            file_name=record.original_name, text=text, truncated=truncated
        )

    def _extract_text(self, file_name: str, blob_key: str) -> str:
        """按后缀提取正文：``parse_document`` 直接读受管 blob 路径（后缀取原文件名）。

        解析器只读文件、不做 OCR；扫描件 PDF 返回空文（调用方按 ``LESSON_SOURCE_EMPTY``
        如实拒绝），不复制第二份临时文件。
        """
        from pathlib import Path

        from app.services.document_parsing import parse_document

        suffix = _suffix_of(file_name)
        if suffix not in DOCUMENT_SUFFIXES:  # pragma: no cover - upload 已拦，防御性兜底
            raise _invalid(
                f"不支持的文件类型「{suffix or file_name}」。{_GUIDANCE}",
                code="LESSON_SOURCE_UNSUPPORTED",
                status_code=422,
            )
        parsed = parse_document(
            path=Path(self._assets.path_of(blob_key)),
            file_name=file_name,
            allow_empty_text=True,
        )
        return parsed.normalized_text


__all__ = [
    "DOCUMENT_SUFFIXES",
    "SPREADSHEET_SUFFIXES",
    "LessonSourceAsset",
    "LessonSourceMaterial",
    "LessonSourceService",
    "MAX_MATERIAL_CHARS",
    "MAX_SOURCE_BYTES",
    "TRUNCATION_NOTE",
]
