"""可读文本投影：清洗图片 Markdown 的派生文本与来源映射（RAG-QUALITY v1.1 · B0）。

对外只暴露冻结契约：两个版本常量、两个投影函数、版本清单与两个数据类。
扫描器与替换/归一工具一并导出，便于测试与审计，但**不得在别处再实现一份清洗规则**：

- 索引、检索上下文、概括、详解与来源展示都必须走 :func:`project_readable`；
- 历史 ``raw-v0`` 数据必须走 :func:`project_by_version`（原样返回，不改指纹）；
- 未知版本必须显式报错，绝不默认套用新规则。
"""

from app.services.text_projection.projection import (
    LEGACY_TEXT_PROJECTION_VERSION,
    READABLE_V1_TEXT_PROJECTION_VERSION,
    SEGMENT_KIND_ALT_KEPT,
    SEGMENT_KIND_KEPT,
    SEGMENT_KIND_REMOVED,
    SEGMENT_KINDS,
    TEXT_PROJECTION_VERSION,
    MappedText,
    Replacement,
    SourceSegment,
    TextProjection,
    apply_replacements_with_source_mapping,
    known_projection_versions,
    normalize_blank_lines,
    normalize_blank_lines_only,
    project_by_version,
    project_readable,
)
from app.services.text_projection.scanner import (
    IMAGE_KIND_HTML_IMG,
    IMAGE_KIND_HTML_PICTURE,
    IMAGE_KIND_MARKDOWN,
    PROTECTED_KIND_CODE_FENCE,
    PROTECTED_KIND_CODE_SPAN,
    PROTECTED_KIND_MATH_DISPLAY,
    PROTECTED_KIND_MATH_INLINE,
    ImageNode,
    ProtectedRange,
    ReferenceDefinition,
    RemovalPlan,
    ScanResult,
    normalize_label_key,
    scan_code_and_math_ranges,
    scan_document,
    scan_reference_definitions,
    scan_tag_fragments,
)

__all__ = [
    "IMAGE_KIND_HTML_IMG",
    "IMAGE_KIND_HTML_PICTURE",
    "IMAGE_KIND_MARKDOWN",
    "LEGACY_TEXT_PROJECTION_VERSION",
    "PROTECTED_KIND_CODE_FENCE",
    "PROTECTED_KIND_CODE_SPAN",
    "PROTECTED_KIND_MATH_DISPLAY",
    "PROTECTED_KIND_MATH_INLINE",
    "READABLE_V1_TEXT_PROJECTION_VERSION",
    "SEGMENT_KIND_ALT_KEPT",
    "SEGMENT_KIND_KEPT",
    "SEGMENT_KIND_REMOVED",
    "SEGMENT_KINDS",
    "TEXT_PROJECTION_VERSION",
    "ImageNode",
    "MappedText",
    "ProtectedRange",
    "ReferenceDefinition",
    "RemovalPlan",
    "Replacement",
    "ScanResult",
    "SourceSegment",
    "TextProjection",
    "apply_replacements_with_source_mapping",
    "known_projection_versions",
    "normalize_blank_lines",
    "normalize_blank_lines_only",
    "normalize_label_key",
    "project_by_version",
    "project_readable",
    "scan_code_and_math_ranges",
    "scan_document",
    "scan_reference_definitions",
    "scan_tag_fragments",
]
