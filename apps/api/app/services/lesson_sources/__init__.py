"""教案来源域：教师上传的学情材料（受管资产 + 文本提取）。"""

from app.services.lesson_sources.service import (
    DOCUMENT_SUFFIXES,
    MAX_MATERIAL_CHARS,
    MAX_SOURCE_BYTES,
    SPREADSHEET_SUFFIXES,
    TRUNCATION_NOTE,
    LessonSourceAsset,
    LessonSourceMaterial,
    LessonSourceService,
)

__all__ = [
    "DOCUMENT_SUFFIXES",
    "MAX_MATERIAL_CHARS",
    "MAX_SOURCE_BYTES",
    "SPREADSHEET_SUFFIXES",
    "TRUNCATION_NOTE",
    "LessonSourceAsset",
    "LessonSourceMaterial",
    "LessonSourceService",
]
