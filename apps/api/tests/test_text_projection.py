"""可读文本投影：清洗规则表逐条、版本分派、坐标平移与不变量。

样本全部在程序内构造，不读正式教材、不写 .local-data、不连 Ollama/Qdrant。
"""

from __future__ import annotations

import hashlib
import time

import pytest

from app.core.exceptions import AppError
from app.services.text_projection import (
    LEGACY_TEXT_PROJECTION_VERSION,
    READABLE_V1_TEXT_PROJECTION_VERSION,
    TEXT_PROJECTION_VERSION,
    known_projection_versions,
    project_by_version,
    project_readable,
)
from test_text_projection_support import assert_projection_invariants, reinsert_raw

# --------------------------------------------------------------- PLAN §3.1 逐行


def test_inline_image_with_empty_alt_is_deleted() -> None:
    """``![](images/hash.jpg)``：删除整个图片节点。"""
    raw = "前文![](images/1a2b3c4d5e6f7890.jpg)后文"
    projection = project_readable(raw)
    assert projection.text == "前文后文"
    assert projection.removed_image_count == 1
    assert "images" not in projection.text


def test_inline_image_keeps_meaningful_alt_and_drops_address() -> None:
    """``![加速度与力关系图](…)``：保留说明文字，删除地址。"""
    projection = project_readable("图前 ![加速度与力关系图](images/force.png) 图后")
    assert projection.text == "图前 加速度与力关系图 图后"
    assert projection.removed_image_count == 1
    assert [segment.kind for segment in projection.source_segments] == [
        "kept",
        "removed",
        "alt_kept",
        "removed",
        "kept",
    ]


def test_inline_image_with_title_drops_title_too() -> None:
    """标题与地址同属图片节点，一并删除。"""
    projection = project_readable('装置 ![实验装置图](images/e.png "图 1") 结束')
    assert projection.text == "装置 实验装置图 结束"
    assert projection.removed_image_count == 1


def test_reference_image_resolves_definition() -> None:
    """引用式图片：解析引用定义后按同样规则处理。"""
    raw = "[fig1]: images/buoyancy.png\n\n图 ![浮力实验装置图][fig1] 如下。"
    projection = project_readable(raw)
    assert projection.text == "图 浮力实验装置图 如下。"
    assert projection.removed_image_count == 1


def test_definition_used_only_by_image_is_deleted() -> None:
    """图片引用定义：仅被图片使用时删除。"""
    raw = "文字\n\n[fig1]: images/a.png\n\n![说明图][fig1]"
    projection = project_readable(raw)
    assert "fig1" not in projection.text
    assert "images/a.png" not in projection.text
    assert projection.text == "文字\n\n说明图"


def test_definition_used_by_text_link_is_kept() -> None:
    """普通文字链接仍使用定义时必须保留该定义原文。"""
    raw = "正文 ![图片说明][fig2] 与 [文字链接][fig2] 并列。\n\n[fig2]: images/mixed.png"
    projection = project_readable(raw)
    assert projection.text == (
        "正文 图片说明 与 [文字链接][fig2] 并列。\n\n[fig2]: images/mixed.png"
    )
    assert projection.removed_image_count == 1


def test_html_img_empty_alt_is_deleted() -> None:
    """``<img>``：删除图片元素与地址。"""
    projection = project_readable('前文<img src="images/a.png" alt="">后文')
    assert projection.text == "前文后文"
    assert projection.removed_image_count == 1


def test_html_img_keeps_meaningful_alt() -> None:
    raw = '前文<img src="images/b.png" alt="电路连接示意图" />后文'
    projection = project_readable(raw)
    assert projection.text == "前文电路连接示意图后文"
    assert projection.removed_image_count == 1


def test_html_picture_keeps_inner_img_alt() -> None:
    raw = (
        '<picture><source srcset="images/c.webp">'
        '<img src="images/c.png" alt="实验装置照片"></picture>后文'
    )
    projection = project_readable(raw)
    assert projection.text == "实验装置照片后文"
    assert projection.removed_image_count == 1


def test_outer_link_without_text_is_deleted_with_image() -> None:
    """包裹图片的外层链接：删除图片后无文字内容，空链接一并删除。"""
    raw = "文字 [![](images/thumb.jpg)](images/full.jpg) 结束"
    projection = project_readable(raw)
    assert projection.text == "文字  结束"
    assert "thumb" not in projection.text and "full" not in projection.text
    assert projection.removed_image_count == 1


def test_outer_link_with_alt_keeps_alt_and_drops_link() -> None:
    """外层链接的目标仍属图片展示，不进入文本；说明文字照图片规则保留。"""
    raw = "文字 [![滑轮组示意图](images/thumb.jpg)](images/full.jpg) 结束"
    projection = project_readable(raw)
    assert projection.text == "文字 滑轮组示意图 结束"
    assert "jpg" not in projection.text
    assert projection.removed_image_count == 1


def test_html_anchor_wrapping_only_image_is_deleted() -> None:
    raw = '文字<a href="images/full.jpg"><img src="images/t.png" alt=""></a>结束'
    projection = project_readable(raw)
    assert projection.text == "文字结束"
    assert "images" not in projection.text
    assert projection.removed_image_count == 1


def test_link_with_text_content_is_kept() -> None:
    """普通文字链接保留（同时包含图片与外层文字时不整体删除）。"""
    raw = "见 [放大示意图 ![局部](images/z.png)](https://example.com/doc) 说明"
    projection = project_readable(raw)
    assert "[放大示意图 局部](https://example.com/doc)" in projection.text
    assert "images/z.png" not in projection.text


@pytest.mark.parametrize(
    "alt",
    [
        "",
        "   ",
        "images/force.png",
        "force.png",
        "../assets/fig 1.jpeg",
        "1f2e3d4c5b6a79887766554433221100",
        "3f2504e04f8911d39a0c0305e82c3301",
        "9F8E7D6C5B4A39281706F5E4D3C2B1A0",
        "图",
        "图片",
        "图1",
        "image",
        "IMG_0231",
        "pic",
        "photo 2",
        "figure 1",
    ],
)
def test_alt_without_information_is_not_kept(alt: str) -> None:
    """空 alt、文件名、路径、长哈希、泛化占位词：不作为说明文字保留。"""
    projection = project_readable(f"前|![{alt}](images/x.png)|后")
    assert projection.text == "前||后"
    assert projection.removed_image_count == 1


def test_caption_below_image_is_kept() -> None:
    """图片下方正文图注保留（不是图片语法）。"""
    raw = "![](images/fig-3.png)\n图 3 实验装置示意"
    projection = project_readable(raw)
    assert projection.text == "图 3 实验装置示意"


def test_math_table_body_and_text_link_are_kept() -> None:
    """公式、表格、正文、普通文字链接保留。"""
    raw = "| 量 | 值 |\n| --- | --- |\n| 速度 | $v = \\frac{s}{t}$ |\n见 [课标](https://example.com/kb)。"
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0


def test_code_fence_literal_is_not_an_image_node() -> None:
    """代码围栏中的字面示例不误当成真实图片节点。"""
    raw = "示例：\n\n```markdown\n![示例图片](images/demo.png)\n```\n\n正文"
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0


def test_inline_code_literal_is_not_an_image_node() -> None:
    raw = "写作 `![图片](images/e.png)` 即可，正文 ![真的图](images/real.png) 结束"
    projection = project_readable(raw)
    assert "`![图片](images/e.png)`" in projection.text
    assert "images/real.png" not in projection.text
    assert projection.removed_image_count == 1


def test_display_math_protects_image_syntax() -> None:
    raw = "计算 $$a_i = ![b](images/g.png)$$ 结束"
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0


def test_inline_math_protects_image_syntax() -> None:
    raw = "公式 $a![b](c)$ 结束"
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0


def test_currency_dollar_is_not_math_protection() -> None:
    """``$5 … $10`` 不是公式：中间的真实图片仍要清洗。"""
    raw = "价格 $5 到 $10，见 ![价目表](images/price.png) 说明"
    projection = project_readable(raw)
    assert "images/price.png" not in projection.text
    assert "$5 到 $10" in projection.text
    assert projection.removed_image_count == 1


def test_escaped_image_marker_is_literal() -> None:
    """转义 ``\\![`` 不是图片节点，按字面保留。"""
    raw = "字面写法 \\![不是图片](images/x.png) 保留"
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0


def test_nested_parentheses_url_is_handled() -> None:
    """URL 里的成对括号不提前截断节点。"""
    raw = "公式 ![力与加速度关系图](images/fig_(1)_final.png) 结束"
    projection = project_readable(raw)
    assert projection.text == "公式 力与加速度关系图 结束"
    assert projection.removed_image_count == 1


def test_angle_bracket_destination_with_spaces() -> None:
    raw = "装置 ![实验台示意](<images/fig 2.png>) 说明"
    projection = project_readable(raw)
    assert projection.text == "装置 实验台示意 说明"
    assert projection.removed_image_count == 1


def test_consecutive_images_are_all_removed() -> None:
    raw = "前缀![](images/a.png)![](images/b.png)后缀"
    projection = project_readable(raw)
    assert projection.text == "前缀后缀"
    assert projection.removed_image_count == 2


def test_only_images_project_to_empty_text() -> None:
    """清洗后仅剩空白的片段：文本为空串，调用方据此跳过。"""
    raw = "![](images/a.png)\n\n![图](images/b.png)\n"
    projection = project_readable(raw)
    assert projection.text == ""
    assert projection.text.strip() == ""
    assert projection.removed_image_count == 2


def test_shortcut_reference_image_is_resolved() -> None:
    """简写式引用图片：有同名定义时按引用式图片处理。"""
    raw = "[浮力示意图]: images/f.png\n\n![浮力示意图]"
    projection = project_readable(raw)
    assert projection.text == "浮力示意图"
    assert projection.removed_image_count == 1


def test_shortcut_like_image_without_definition_is_literal() -> None:
    """没有同名定义时 ``![说明]`` 只是字面文字，不得当图片删除。"""
    raw = "正文 ![说明] 与 ![图片](images/x.png) 结束"
    projection = project_readable(raw)
    assert "![说明]" in projection.text
    assert "images/x.png" not in projection.text
    assert projection.removed_image_count == 1


# ------------------------------------------------------------------ 有限归一


def test_blank_lines_collapse_without_touching_body_whitespace() -> None:
    raw = "第一段\n\n\n\n第二段"
    assert project_readable(raw).text == "第一段\n\n第二段"


def test_line_trailing_whitespace_is_stripped_only_at_line_end() -> None:
    raw = "文字   \n第二行\t\n"
    assert project_readable(raw).text == "文字\n第二行"


def test_image_removal_leaves_no_blank_line_residue() -> None:
    raw = "第一段\n\n![](images/a.png)\n\n第二段"
    assert project_readable(raw).text == "第一段\n\n第二段"


def test_interior_spaces_are_not_compressed() -> None:
    """不得压缩正文空白：删除图片后留下的行内空格保持原样。"""
    raw = "前 ![图](images/g1.png) 后"
    assert project_readable(raw).text == "前  后"


def test_control_characters_are_not_touched() -> None:
    raw = "制表符\t保留\u3000全角空格 ![说明](images/a.png)"
    assert project_readable(raw).text == "制表符\t保留\u3000全角空格 说明"


# ------------------------------------------------------------------ 版本分派


def test_known_projection_versions() -> None:
    assert known_projection_versions() == frozenset(
        {TEXT_PROJECTION_VERSION, READABLE_V1_TEXT_PROJECTION_VERSION, "raw-v0"}
    )


def test_project_by_version_readable_matches_project_readable() -> None:
    raw = "前 ![说明](images/a.png) 后"
    assert project_by_version(raw, TEXT_PROJECTION_VERSION) == project_readable(raw)


def test_legacy_version_returns_raw_untouched() -> None:
    """``raw-v0`` 原样返回：不归一、不删除、不影响历史指纹。"""
    raw = "![](images/a.png)\n\n\n\n 尾随空格 \t\n"
    projection = project_by_version(raw, LEGACY_TEXT_PROJECTION_VERSION)
    assert projection.version == LEGACY_TEXT_PROJECTION_VERSION
    assert projection.text == raw
    assert projection.removed_image_count == 0
    assert len(projection.source_segments) == 1
    assert projection.source_segments[0].kind == "kept"
    assert (projection.source_segments[0].raw_start, projection.source_segments[0].raw_end) == (
        0,
        len(raw),
    )


def test_unknown_version_raises_dedicated_error() -> None:
    with pytest.raises(AppError) as excinfo:
        project_by_version("正文", "rag-readable-v3")
    assert excinfo.value.code == "UNKNOWN_TEXT_PROJECTION_VERSION"
    assert excinfo.value.status_code == 422
    assert excinfo.value.retryable is False


@pytest.mark.parametrize("version", ["", "raw", "RAG-READABLE-V1", "rag-readable-v1 ", "rag-readable-v9"])
def test_unknown_or_miscased_versions_never_fall_back(version: str) -> None:
    """未知或大小写不符的版本必须报错，绝不默认套用新规则。"""
    with pytest.raises(AppError) as excinfo:
        project_by_version("正文", version)
    assert excinfo.value.code == "UNKNOWN_TEXT_PROJECTION_VERSION"


# --------------------------------------------------------------- 坐标与不变量


def test_absolute_start_shifts_every_raw_offset() -> None:
    raw = "前 ![说明](images/a.png) 后"
    shifted = project_readable(raw, absolute_start=1000)
    baseline = project_readable(raw)
    assert shifted.text == baseline.text
    for left, right in zip(shifted.source_segments, baseline.source_segments):
        assert left.clean_start == right.clean_start and left.clean_end == right.clean_end
        assert left.raw_start == right.raw_start + 1000
        assert left.raw_end == right.raw_end + 1000
    assert reinsert_raw(shifted, raw, 1000) == raw


def test_legacy_absolute_start_shifts_identity_segment() -> None:
    projection = project_by_version("正文", LEGACY_TEXT_PROJECTION_VERSION, absolute_start=42)
    segment = projection.source_segments[0]
    assert (segment.raw_start, segment.raw_end) == (42, 44)
    assert (segment.clean_start, segment.clean_end) == (0, 2)


def test_negative_absolute_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        project_readable("正文", absolute_start=-1)


def test_non_string_raw_is_rejected() -> None:
    with pytest.raises(TypeError):
        project_readable(b"bytes")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw",
    [
        "正文开始。\n\n![](images/1a2b3c4d5e6f7890.jpg)\n\n正文结束。",
        "图前文字 ![加速度与力关系图](images/force.png) 图后文字",
        "图 ![浮力实验装置图][fig1] 如下：\n\n[fig1]: images/buoyancy.png",
        "前 ![图](images/g1.png) 后 ![image](images/g2.png) 完",
        '<picture><source srcset="images/c.webp"><img src="images/c.png" alt="实验装置照片"></picture>后文',
        "文字 [![](images/thumb.jpg)](images/full.jpg) 结束",
        "计算 $$a_i = ![b](images/g.png)$$ 结束",
        "转义 \\![不是图片](images/x.png) 保留",
        "```\n![示例](images/d.png)\n```\n\n正文",
        "行内 `![图片](images/e.png)` 保留",
        "| a | b |\n| - | - |\n| ![表内图](images/t.png) | 值 |",
        "![](images/a.png)",
        "",
        "   \n\n  ",
        "混合 😀 与 e\u0301 组合字符 ![图示](images/mix.png) 结束",
    ],
)
def test_projection_invariants_hold(raw: str) -> None:
    """原文不可变、映射可回原、区间铺满、幂等。"""
    sha_before = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    raw_before = str(raw)
    projection = project_readable(raw)
    assert raw == raw_before, "原文在投影过程中不得被修改"
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == sha_before, "原文哈希必须不变"
    assert_projection_invariants(projection, raw)
    assert project_readable(projection.text).text == projection.text
    assert project_readable(projection.text).removed_image_count == 0


def test_projection_is_deterministic() -> None:
    raw = "前 ![说明](images/a.png) 中 ![](images/b.png) 后\n\n[fig]: images/c.png"
    assert project_readable(raw) == project_readable(raw)


def test_codepoint_offsets_with_emoji_and_combining_marks() -> None:
    """索引口径是 Python 码点：emoji 与组合字符都按码点计数。"""
    raw = "😀 ![组合字符图示](images/e.png) 👨\u200d👩\u200d👧 e\u0301"
    projection = project_readable(raw)
    assert projection.text == "😀 组合字符图示 👨\u200d👩\u200d👧 e\u0301"
    assert len("😀") == 1
    assert len("👨\u200d👩\u200d👧") == 5
    kept_alt = next(s for s in projection.source_segments if s.kind == "alt_kept")
    assert raw[kept_alt.raw_start : kept_alt.raw_end] == "组合字符图示"
    assert projection.text[kept_alt.clean_start : kept_alt.clean_end] == "组合字符图示"
    assert_projection_invariants(projection, raw)


def test_removed_image_count_counts_nodes_not_segments() -> None:
    raw = "![](images/a.png)[![](images/b.png)](images/c.jpg)![说明图](images/d.png)"
    projection = project_readable(raw)
    assert projection.removed_image_count == 3
    assert "images" not in projection.text
    assert projection.text == "说明图"


# ------------------------------------------------ 不完整构造（v1.1 死循环回归）

#: ``(名称, 原文, 期望清洗文本, 期望图片数)``——每条都是「不完整构造 + 后续图片节点」。
#: 共同约束：必须终止、按字面继续前进、映射不变量成立。
INCOMPLETE_CONSTRUCT_CASES = [
    ("未闭合尖括号", "4x-5<3 与 a<b\n\n![](images/a.png)", "4x-5<3 与 a<b", 1),
    ("未闭合图片起始", "前 ![说明\n\n![](images/a.png)", "前 ![说明", 1),
    ("未闭合链接目标", "见 [文字](images/a.png\n\n![](images/b.png)", "见 [文字](images/a.png", 1),
    ("引用定义缺目标", "[fig1]:\n\n正文 ![说明](images/a.png)", "[fig1]:\n\n正文 说明", 1),
    ("未闭合围栏含图片", "```\n![示例](images/a.png)\n正文", "```\n![示例](images/a.png)\n正文", 0),
    ("注释内含图片", "<!-- ![说明](images/a.png) -->\n\n正文", "<!-- 说明 -->\n\n正文", 1),
    ("未闭合注释含图片", "<!-- ![说明](images/a.png)", "<!-- 说明", 1),
    (
        "未闭合 picture",
        '<picture><img src="images/a.png" alt="装置图">后文',
        "<picture>装置图后文",
        1,
    ),
    ("未闭合行内代码", "行内 `未闭合 ![说明](images/a.png)", "行内 `未闭合 说明", 1),
    ("未闭合公式", "公式 $$a ![说明](images/a.png)", "公式 $$a 说明", 1),
    ("引用用法无定义", "![浮力示意图][fig1]\n\n正文", "![浮力示意图][fig1]\n\n正文", 0),
    ("未闭合尖括号+路径斜杠", "4x-5<3 images/abc 说明", "4x-5<3 images/abc 说明", 0),
]


@pytest.mark.parametrize(
    "raw,expected_text,expected_count",
    [(raw, text, count) for _, raw, text, count in INCOMPLETE_CONSTRUCT_CASES],
    ids=[name for name, _, _, _ in INCOMPLETE_CONSTRUCT_CASES],
)
def test_incomplete_constructs_keep_scanning_forward(
    raw: str, expected_text: str, expected_count: int
) -> None:
    """未完成构造只按字面跳过一个字符继续前进，绝不原地打转或整段吞掉。"""
    start = time.perf_counter()
    projection = project_readable(raw)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.2, f"未完成构造不得拖慢扫描：{elapsed:.3f}s"
    assert projection.text == expected_text
    assert projection.removed_image_count == expected_count
    assert_projection_invariants(projection, raw)
    assert project_readable(projection.text).text == projection.text


def test_unclosed_html_tag_does_not_stall_on_slash() -> None:
    """根因回归：标签属性扫描遇到不成对的 ``/``（如 ``images/abc``）必须前进。

    v1.0 在这里原地循环：``_parse_html_tag`` 的属性循环既没有读到属性名、也没有移动游标，
    于是 ``4x-5<3 … images/abc`` 这类「不等式 + 图片路径」文本永久卡死。
    """
    for raw in [
        "4x-5<3\n\n![](images/abc)",
        "x<3 ![](images/a.png)",
        "a/b<3 ![](images/a.png)",
        "<3 images/a.png",
        "<a/b",
    ]:
        start = time.perf_counter()
        projection = project_readable(raw)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"{raw!r} 用时 {elapsed:.3f}s"
        assert_projection_invariants(projection, raw)
