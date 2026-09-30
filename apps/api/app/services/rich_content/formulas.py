"""LaTeX → OMML 转换（只用于**新题导出**；不做 OMML→LaTeX 反向转换）。

- 使用 ``math2docx`` 的转换链（``latex2mathml.converter`` → ``mathml2omml``），返回
  **自洽**的 ``<m:oMath xmlns:m="…">…</m:oMath>`` XML 字符串：字符串本身带命名空间声明，
  调用方可直接 ``lxml`` / ``parse_xml`` 解析，无需再补包装元素；
- 空串、纯空白、非法 LaTeX、转换器缺失一律 ``FORMULA_CONVERSION_FAILED``（422），
  **绝不返回空文本**，也不返回"看起来成功"的占位公式；
- 本模块**不**做 OMML→LaTeX 反向转换（本批不支持）：原卷/原件里的 OMML 一律原样保留
  （``FormulaBlock.ommlXml``），不经过 LaTeX 往返改写 —— 公式结构一旦往返就会失真，
  原件不具有可再生的等价表示。
"""

from __future__ import annotations

from lxml import etree

from app.core.exceptions import AppError

#: OOXML 数学命名空间（与 ``FormattedFormula``/``m:oMath`` 一致）
MATH_NAMESPACE = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_OMML_WRAPPER = f'<omml-wrapper xmlns:m="{MATH_NAMESPACE}">{{}}</omml-wrapper>'


def _failed(message: str) -> AppError:
    return AppError(message, code="FORMULA_CONVERSION_FAILED", status_code=422)


def omml_from_latex(latex: str) -> str:
    """把 LaTeX 转成原始 ``m:oMath`` XML 字符串；失败一律 422 ``FORMULA_CONVERSION_FAILED``。"""
    if not isinstance(latex, str) or not latex.strip():
        raise _failed("公式 LaTeX 为空，无法转换为 OMML。")
    try:
        import math2docx
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        raise AppError(
            "公式转换依赖 math2docx 未安装，无法把 LaTeX 转换为 OMML。",
            code="FORMULA_CONVERTER_UNAVAILABLE",
            status_code=500,
        ) from exc

    try:
        mathml = math2docx.latex2mathml.converter.convert(latex)
        fragment = math2docx.mathml2omml.convert(mathml)
    except Exception as exc:  # noqa: BLE001 - latex2mathml 对非法输入抛多种异常
        raise _failed(f"LaTeX 公式转换失败：{exc.__class__.__name__}。") from exc

    if not isinstance(fragment, str) or "oMath" not in fragment:
        raise _failed("LaTeX 公式转换没有产出 OMML 内容。")
    try:
        wrapper = etree.fromstring(_OMML_WRAPPER.format(fragment).encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise _failed("LaTeX 公式转换产出的 OMML 不是合法 XML。") from exc
    element = wrapper[0] if len(wrapper) else None
    if element is None or element.tag != f"{{{MATH_NAMESPACE}}}oMath":
        raise _failed("LaTeX 公式转换没有产出 m:oMath 根节点。")
    return etree.tostring(element, encoding="unicode")
