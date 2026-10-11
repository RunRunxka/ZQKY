"""有状态扫描器与 alt 判定：保护区、引用定义、待清除区间。

这些用例锁住「不得用一个贪婪正则直接替换整篇 Markdown」所依赖的定位行为。
"""

from __future__ import annotations

import pytest

from app.services.text_projection import (
    PROTECTED_KIND_CODE_FENCE,
    PROTECTED_KIND_CODE_SPAN,
    PROTECTED_KIND_MATH_DISPLAY,
    PROTECTED_KIND_MATH_INLINE,
    normalize_label_key,
    project_readable,
    scan_code_and_math_ranges,
    scan_document,
    scan_reference_definitions,
)
from app.services.text_projection.alt_text import (
    looks_like_generic_placeholder,
    looks_like_hash,
    looks_like_path,
    meaningful_alt_text,
)

INLINE_SNIPPETS = {
    "`code`": PROTECTED_KIND_CODE_SPAN,
    "$a+b$": PROTECTED_KIND_MATH_INLINE,
}


def test_inline_protected_range_kinds() -> None:
    for snippet, kind in INLINE_SNIPPETS.items():
        raw = f"前 {snippet} 后"
        ranges = scan_code_and_math_ranges(raw)
        assert [span.kind for span in ranges] == [kind], snippet
        assert raw[ranges[0].start : ranges[0].end] == snippet


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fence_must_start_its_line(fence: str) -> None:
    """围栏必须独占行首（≤3 空格缩进），同行前面的文字会让它退化为行内代码/字面量。"""
    raw = f"{fence}\n![示例](images/a.png)\n{fence}\n后"
    ranges = scan_code_and_math_ranges(raw)
    assert [span.kind for span in ranges] == [PROTECTED_KIND_CODE_FENCE]
    assert raw[ranges[0].start : ranges[0].end] == f"{fence}\n![示例](images/a.png)\n{fence}"
    assert scan_document(raw).plans == ()

    inline_like = f"前 {fence} 后"
    assert all(
        span.kind != PROTECTED_KIND_CODE_FENCE for span in scan_code_and_math_ranges(inline_like)
    )


def test_unclosed_fence_protects_to_end_of_text() -> None:
    raw = "前\n```\n![示例](images/a.png)\n没有闭合"
    ranges = scan_code_and_math_ranges(raw)
    assert ranges[0].kind == PROTECTED_KIND_CODE_FENCE
    assert ranges[0].end == len(raw)
    assert scan_document(raw).plans == ()


def test_fence_requires_matching_length_and_char() -> None:
    raw = "~~~~\ncode\n~~~\n仍是代码\n~~~~\n结束"
    ranges = scan_code_and_math_ranges(raw)
    assert len(ranges) == 1
    assert raw[ranges[0].start : ranges[0].end].endswith("~~~~")


def test_code_span_must_match_run_length() -> None:
    raw = "``含 ` 反引号`` 与 `单` 结束"
    ranges = scan_code_and_math_ranges(raw)
    assert [span.kind for span in ranges] == [PROTECTED_KIND_CODE_SPAN, PROTECTED_KIND_CODE_SPAN]
    assert raw[ranges[0].start : ranges[0].end] == "``含 ` 反引号``"


def test_protected_ranges_do_not_cross_blank_line() -> None:
    raw = "`未闭合\n\n![真图](images/a.png) 之后 `"
    ranges = scan_code_and_math_ranges(raw)
    assert ranges == ()
    assert len(scan_document(raw).plans) == 1


def test_escaped_dollar_and_backtick_do_not_open_ranges() -> None:
    raw = "字面 \\$a\\$ 与 \\`b\\` 结束"
    assert scan_code_and_math_ranges(raw) == ()


def test_money_amounts_are_not_math() -> None:
    raw = "价格 $5 到 $10 元"
    assert scan_code_and_math_ranges(raw) == ()


def test_display_math_may_span_lines() -> None:
    raw = "$$\n\\frac{a}{b}\n![x](y)\n$$\n结束"
    ranges = scan_code_and_math_ranges(raw)
    assert [span.kind for span in ranges] == [PROTECTED_KIND_MATH_DISPLAY]
    assert scan_document(raw).plans == ()


def test_protected_ranges_are_sorted_and_disjoint() -> None:
    raw = "`a` 文字 $b$ ```\nc\n``` ![图](images/x.png)"
    ranges = scan_code_and_math_ranges(raw)
    for previous, current in zip(ranges, ranges[1:]):
        assert previous.start < previous.end <= current.start


# --------------------------------------------------------------- 引用定义


def test_reference_definition_is_detected() -> None:
    raw = "正文\n\n[fig1]: images/a.png \"图 1\"\n后续"
    definitions = scan_reference_definitions(raw)
    assert len(definitions) == 1
    definition = definitions[0]
    assert definition.label == "fig1"
    assert definition.destination == "images/a.png"
    assert raw[definition.start : definition.end] == '[fig1]: images/a.png "图 1"'


@pytest.mark.parametrize(
    "line",
    [
        "[fig1]:",
        "[fig1] images/a.png",
        "   [fig1]: images/a.png 后面还有正文",
        "4 空格缩进不是定义：    [fig1]: images/a.png",
        "]]: images/a.png",
    ],
)
def test_invalid_definition_lines_are_not_definitions(line: str) -> None:
    assert scan_reference_definitions(f"正文\n{line}\n结束") == ()


def test_definition_inside_code_fence_is_literal() -> None:
    raw = "```\n[fig1]: images/a.png\n```"
    assert scan_reference_definitions(raw, scan_code_and_math_ranges(raw)) == ()


def test_label_key_normalization_matches_case_and_whitespace() -> None:
    raw = "正文 ![说明][FIG 1] 结束\n\n[fig   1]: images/a.png"
    result = scan_document(raw)
    assert result.definitions[0].label_key == normalize_label_key("FIG 1")
    assert len(result.plans) == 2


# ----------------------------------------------------------------- 待清除区间


def test_plans_are_sorted_and_disjoint() -> None:
    raw = "![](images/a.png) 文字 [![](images/b.png)](images/c.png) ![说明](images/d.png)"
    for plan in scan_document(raw).plans:
        assert plan.start < plan.end
    plans = scan_document(raw).plans
    for previous, current in zip(plans, plans[1:]):
        assert previous.end <= current.start


def test_plan_keeps_only_meaningful_alt_span() -> None:
    raw = "前 ![加速度与力关系图](images/a.png) 后"
    plan = scan_document(raw).plans[0]
    assert plan.image_count == 1
    assert len(plan.kept_spans) == 1
    kept_start, kept_end = plan.kept_spans[0]
    assert raw[kept_start:kept_end] == "加速度与力关系图"


def test_plan_for_meaningless_alt_has_no_kept_span() -> None:
    raw = "前 ![](images/a.png) 后"
    plan = scan_document(raw).plans[0]
    assert plan.kept_spans == ()
    assert plan.image_count == 1


def test_standalone_source_tag_is_removed_without_counting_as_image() -> None:
    raw = '前<source srcset="images/a.webp" type="image/webp">后'
    result = scan_document(raw)
    assert result.plans[0].image_count == 0
    assert project_readable(raw).text == "前后"
    assert project_readable(raw).removed_image_count == 0


def test_unclosed_picture_is_not_a_single_node() -> None:
    raw = '<picture><img src="images/a.png" alt="">后文'
    plans = scan_document(raw).plans
    assert plans and plans[0].image_count == 1


def test_escaped_bang_is_not_a_node() -> None:
    raw = "\\![说明](images/a.png)"
    assert scan_document(raw).plans == ()


def test_image_with_newline_in_alt_is_not_a_node() -> None:
    """Markdown 图片节点不跨行；跨行写法按字面保留，不做整段删除。"""
    raw = "![说明\n继续](images/a.png)"
    assert scan_document(raw).plans == ()


def test_unbalanced_bracket_stays_literal() -> None:
    raw = "![说明(images/a.png)"
    assert scan_document(raw).plans == ()


# ------------------------------------------------------------------- alt 判定


@pytest.mark.parametrize(
    "text",
    ["images/a.png", "a/b", "C:\\img\\a.jpg", "https://example.com/a.png", "fig-1.jpeg"],
)
def test_path_like_alt(text: str) -> None:
    assert looks_like_path(text)


@pytest.mark.parametrize(
    "text",
    ["1f2e3d4c5b6a79887766554433221100", "3F2504E0-4F89-11D3-9A0C-0305E82C3301", "a" * 32],
)
def test_hash_like_alt(text: str) -> None:
    assert looks_like_hash(text)


@pytest.mark.parametrize("text", ["图", "图片", "图 12", "image", "IMG_0231", "pic", "figure 2"])
def test_generic_placeholder_alt(text: str) -> None:
    assert looks_like_generic_placeholder(text)


@pytest.mark.parametrize(
    "text",
    [
        "加速度与力关系图",
        "电路连接示意",
        "实验装置照片",
        "浮力实验装置图",
        "对比曲线（甲、乙）",
    ],
)
def test_meaningful_alt_is_kept_verbatim(text: str) -> None:
    assert meaningful_alt_text(f"  {text}  ") == text


def test_meaningful_alt_rejects_placeholder_but_not_compound_words() -> None:
    assert meaningful_alt_text("图") == ""
    assert meaningful_alt_text("示意图 2") == ""
    assert meaningful_alt_text("图 3 实验装置示意") == "图 3 实验装置示意"
