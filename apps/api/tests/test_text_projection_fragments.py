"""被截断的标签残片清洗：A1 r1 F2 的回归面（RAG-QUALITY v1.2 · B0）。

背景：真实教材里有单行 HTML 表格超过分块上限，B2 的切点落在 ``<img …>`` 标签内部，
于是块首是 ``src="images/….jpg"/></td>…``、块尾是 ``<td><img `` —— 残缺的标签片段。
清洗器必须把它们当作图片残片处理：**图片地址不进入清洗文本**，残片计入
``removedImageCount``；同时不得误删「看起来像属性的普通文本」。

同时锁住版本分派：``rag-readable-v2`` 走新规则，``rag-readable-v1`` 保持旧规则可读，
未知版本必须报错。
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.services.text_projection import (
    READABLE_V1_TEXT_PROJECTION_VERSION,
    TEXT_PROJECTION_VERSION,
    known_projection_versions,
    project_by_version,
    project_readable,
)
from test_text_projection_support import assert_projection_invariants

#: A1 r1 的原始最小复现（真实数据：人教版化学选修第二册 ord=80 块首）
A1_MINIMAL_REPRO = (
    'src="images/8a174688fc6ed863e59307200191e751eb0d34e753eb6f061a02b6796cd115e5.jpg"'
    "/></td><td>正四面体形</td></tr></table>"
)

HASH = "8a174688fc6ed863e59307200191e751eb0d34e753eb6f061a02b6796cd115e5"


# ------------------------------------------------- A1 最小复现（真实数据）


def test_a1_minimal_repro_no_longer_leaks_address() -> None:
    """A1 原始最小复现：修复后不含 ``images/``，且残片计入图片数。"""
    projection = project_readable(A1_MINIMAL_REPRO)
    assert "images/" not in projection.text
    assert "src=" not in projection.text
    assert projection.text == "</td><td>正四面体形</td></tr></table>"
    assert projection.removed_image_count == 1
    assert_projection_invariants(projection, A1_MINIMAL_REPRO)


@pytest.mark.parametrize(
    "ordinal,raw_prefix",
    [
        (80, f'src="images/{HASH}.jpg"/></td><td>正四面体形</td></tr></table>'),
        (97, 'src="images/88b2f9978e329bfa795189f325086f590a7ae0f0f4f2d5b7161be52ae967d7bc.jpg"/> 乙酸乙酯</td></tr></table>'),
    ],
)
def test_a1_real_head_fragments_are_cleaned(ordinal: int, raw_prefix: str) -> None:
    """A1 报的 3 个块首残片（此处取其中两条真实原文）都必须清洗干净。"""
    projection = project_readable(raw_prefix)
    assert "images/" not in projection.text
    assert "src=" not in projection.text
    assert projection.removed_image_count == 1
    assert_projection_invariants(projection, raw_prefix)


# ------------------------------------------------------- 残片矩阵（v1.2）


#: ``(名称, 原文, 期望清洗文本, 期望图片数)``
FRAGMENT_CASES = [
    # 块首残片：没有开尖括号的裸属性片段
    (
        "块首-无开尖括号",
        f'src="images/{HASH}.jpg"/></td><td>正四面体形</td></tr></table>',
        "</td><td>正四面体形</td></tr></table>",
        1,
    ),
    (
        "块首-单引号",
        "src='images/x.jpg'/> 乙酸乙酯</td></tr></table>",
        " 乙酸乙酯</td></tr></table>",
        1,
    ),
    (
        "块首-无引号",
        "src=images/x.jpg/> 乙酸乙酯",
        " 乙酸乙酯",
        1,
    ),
    (
        "块首-切在属性值内部",
        'images/x.jpg"/></td><td>正四面体形</td></tr></table>',
        "</td><td>正四面体形</td></tr></table>",
        1,
    ),
    (
        "行首-正文之后",
        '正文第一行\nsrc="images/y.jpg"/> 说明',
        "正文第一行\n 说明",
        1,
    ),
    (
        "块首-带说明文字 alt",
        'src="images/x.jpg" alt="实验装置示意图"/> 说明',
        "实验装置示意图 说明",
        1,
    ),
    (
        "块首-泛化 alt 不保留",
        'src="images/x.jpg" alt="图"/> 说明',
        " 说明",
        1,
    ),
    (
        "块首-未完成的 alt 不保留",
        'src="images/x.jpg" alt="实验装置',
        "",
        1,
    ),
    (
        "块首-未闭合的 src 值",
        'src="images/x.jpg',
        "",
        1,
    ),
    # 块尾残片：未闭合的媒体标签
    (
        "块尾-裸 img",
        "<td><img ",
        "<td>",
        1,
    ),
    (
        "块尾-img 带地址",
        '正文<tr><td><img src="images/x.jpg',
        "正文<tr><td>",
        1,
    ),
    (
        "块尾-img 带未完成 alt",
        '<table><tr><td><img src="images/x.jpg" alt="示意',
        "<table><tr><td>",
        1,
    ),
    (
        "块尾-img 带完整 alt",
        '<table><tr><td><img src="images/x.jpg" alt="正四面体示意图"/>',
        "<table><tr><td>正四面体示意图",
        1,
    ),
    # 完整形态作为对照
    (
        "完整标签-对照",
        '<td><img src="images/x.jpg"></td>',
        "<td></td>",
        1,
    ),
    (
        "完整标签-保留 alt",
        '<td><img src="images/x.jpg" alt="正四面体"></td>',
        "<td>正四面体</td>",
        1,
    ),
    (
        "块尾-picture 内 img 残片",
        '<picture><img src="images/x.jpg" alt=""',
        "<picture>",
        1,
    ),
    # 大写的属性名、data-src
    (
        "块首-大写属性名",
        'SRC="images/x.jpg"/> 说明',
        " 说明",
        1,
    ),
    (
        "块首-data-src",
        'data-src="images/x.jpg"/> 说明',
        " 说明",
        1,
    ),
]


@pytest.mark.parametrize(
    "raw,expected_text,expected_count",
    [(raw, text, count) for _, raw, text, count in FRAGMENT_CASES],
    ids=[name for name, _, _, _ in FRAGMENT_CASES],
)
def test_tag_fragment_cases(raw: str, expected_text: str, expected_count: int) -> None:
    projection = project_readable(raw)
    assert projection.text == expected_text
    assert projection.removed_image_count == expected_count
    assert "images/" not in projection.text
    assert "src=" not in projection.text
    assert_projection_invariants(projection, raw)
    assert project_readable(projection.text).text == projection.text


def test_fragment_does_not_swallow_following_paragraph() -> None:
    """残片收口在行尾/文末：不得吞掉后面的正文。"""
    for raw in [
        'src="images/x.jpg"/>\n\n下一段正文',
        '<td><img src="images/x.jpg"\n\n下一段正文',
        'src="images/x.jpg"/> 说明\n后续内容',
    ]:
        projection = project_readable(raw)
        assert "下一段正文" in projection.text or "后续内容" in projection.text
        assert "images/" not in projection.text


def test_link_fragment_is_removed_without_counting_as_image() -> None:
    """``<a href>`` 残片删除，但不计入 removedImageCount（它不是图片节点）。"""
    projection = project_readable('<a href="https://example.com/doc')
    assert "https://example.com" not in projection.text
    assert projection.removed_image_count == 0


# --------------------------------------------------------------- 负向用例


#: 不得误伤的「看起来像属性」的普通文本
NEGATIVE_CASES = [
    "src 是属性名，alt 是说明。",
    "正文说明：把 src=\"images/a.jpg\" 换成实际路径。",
    "images/a.jpg 是相对路径，务必替换。",
    "公式 $alt$ 与 $src$ 保留。",
    "行内写法 `src=\"images/a.jpg\"` 示意。",
    "```\nsrc=\"images/a.jpg\"\n```",
    "标签以 <img 开头，属性用 alt。",
    'alt="实验装置图" 是属性名。',
    "把 alt 与 title 都写成中文说明。",
    "比较 4x-5<3 与 a<b 的结果。",
    # v1.2 实测踩到过的过删（英文教材音标行，行首形如 /ˌɔːɡənaɪz'）
    "organise (NAmE -ize) /'ɔːɡənaɪz/\nvt. 组织；筹备；安排；组建",
    "/ˌɔːɡənaɪz'",
    "/flæʃ/ n. 光；信号",
    "路径写法 slug=/docs/intro 与通配 /* 都保留。",
]


@pytest.mark.parametrize("raw", NEGATIVE_CASES, ids=range(len(NEGATIVE_CASES)))
def test_negative_cases_are_not_touched(raw: str) -> None:
    projection = project_readable(raw)
    assert projection.text == raw
    assert projection.removed_image_count == 0
    assert_projection_invariants(projection, raw)


# --------------------------------------------------------- 版本分派（v1/v2）


def test_current_version_is_rag_readable_v2() -> None:
    assert TEXT_PROJECTION_VERSION == "rag-readable-v2"
    assert READABLE_V1_TEXT_PROJECTION_VERSION == "rag-readable-v1"
    assert known_projection_versions() == frozenset(
        {"rag-readable-v2", "rag-readable-v1", "raw-v0"}
    )


def test_v2_is_default_and_cleans_fragments() -> None:
    assert project_by_version(A1_MINIMAL_REPRO, "rag-readable-v2") == project_readable(
        A1_MINIMAL_REPRO
    )
    assert "images/" not in project_readable(A1_MINIMAL_REPRO).text


def test_v1_keeps_historical_rules_for_fragments() -> None:
    """历史数据按旧规则解释：v1 不清洗残片，行为与修复前一致（必须仍可读）。"""
    projection = project_by_version(A1_MINIMAL_REPRO, READABLE_V1_TEXT_PROJECTION_VERSION)
    assert projection.version == "rag-readable-v1"
    assert projection.text == A1_MINIMAL_REPRO
    assert projection.removed_image_count == 0
    assert "images/" in projection.text


def test_v1_and_v2_agree_on_complete_image_nodes() -> None:
    """v1 与 v2 的差别只在标签残片：完整图片节点的清洗结果必须一致。"""
    samples = [
        "前 ![说明](images/a.png) 后",
        "![](images/a.png)\n\n正文",
        '<picture><source srcset="images/c.webp"><img src="images/c.png" alt="装置照片"></picture>后文',
        "[fig1]: images/a.png\n\n图 ![说明][fig1] 结束",
    ]
    for raw in samples:
        old = project_by_version(raw, READABLE_V1_TEXT_PROJECTION_VERSION)
        new = project_by_version(raw, "rag-readable-v2")
        assert old.text == new.text, raw
        assert old.removed_image_count == new.removed_image_count, raw


def test_unknown_version_still_errors() -> None:
    with pytest.raises(AppError) as excinfo:
        project_by_version("正文", "rag-readable-v3")
    assert excinfo.value.code == "UNKNOWN_TEXT_PROJECTION_VERSION"
    assert excinfo.value.status_code == 422
