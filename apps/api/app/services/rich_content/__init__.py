"""富内容 v2：DOCX 解析（块流 + 图片资产 + 可见问题）、分组组装与 DOCX 渲染。

对外入口：

- ``parse_docx_rich``：DOCX → ``ParsedRichDocument``（``ContentBlock`` 流、来源定位、
  抽取的图片资产、可见问题）；图片真实字节写入 ``AssetStore``，``assetId`` 为 ``blob_key``，
  登记教学库 ``file_assets`` 由调用方完成；
- ``group_shared_materials`` / ``rich_content_from_blocks``：共同材料分组与
  ``RichContentV2`` 组装（纯函数，T40/T50 复用）；
- ``render_rich_document``：``RichContentV2`` → ``.docx`` 字节（学生版 / 教师版）；
- ``omml_from_latex``：LaTeX → 原始 ``m:oMath`` XML（只用于新题导出，不做反向转换）。

契约来自 ``app.contracts.teaching_loop``（冻结，不在此复制第二份）。
"""

from app.services.rich_content.blocks import (
    MATERIAL_PREFIXES,
    QUESTION_NUMBER_PATTERN,
    group_shared_materials,
    is_material_heading_block,
    is_question_number_block,
    rich_content_from_blocks,
)
from app.services.rich_content.formulas import MATH_NAMESPACE, omml_from_latex
from app.services.rich_content.parser_docx import (
    EMU_PER_PIXEL,
    UNSUPPORTED_OBJECT,
    ParsedRichDocument,
    RichIssue,
    parse_docx_rich,
)
from app.services.rich_content.renderer_docx import (
    RENDER_VARIANTS,
    RenderVariant,
    render_rich_document,
)

__all__ = [
    "EMU_PER_PIXEL",
    "MATH_NAMESPACE",
    "MATERIAL_PREFIXES",
    "QUESTION_NUMBER_PATTERN",
    "RENDER_VARIANTS",
    "UNSUPPORTED_OBJECT",
    "ParsedRichDocument",
    "RenderVariant",
    "RichIssue",
    "group_shared_materials",
    "is_material_heading_block",
    "is_question_number_block",
    "omml_from_latex",
    "parse_docx_rich",
    "render_rich_document",
    "rich_content_from_blocks",
]
