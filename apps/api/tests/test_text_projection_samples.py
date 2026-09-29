"""跨语言样例一致性：``tests/fixtures/text-projection-samples.json`` 逐组断言。

样例是 F0 前端实现的唯一对照；任何一组与后端不一致即失败，防止两端清洗规则漂移。
"""

from __future__ import annotations

import pytest

from app.services.text_projection import (
    READABLE_V1_TEXT_PROJECTION_VERSION,
    TEXT_PROJECTION_VERSION,
    project_by_version,
)
from test_text_projection_support import (
    SAMPLES_PATH,
    assert_projection_invariants,
    load_samples,
    segment_tuples,
)

VERSION, CASES = load_samples()

#: 样例组必须同时通过 v1（历史规则）与 v2（当前规则）：这 24 组不含标签残片，
#: 两个版本的期望值一致，是「历史版本仍可解释」的证据。
SAMPLE_VERSIONS = [READABLE_V1_TEXT_PROJECTION_VERSION, TEXT_PROJECTION_VERSION]

REQUIRED_SITUATIONS = {
    "inline-empty-alt",
    "inline-chinese-alt",
    "reference-image-definition-removed",
    "reference-definition-kept-for-text-link",
    "shortcut-reference-image",
    "html-img-empty-alt",
    "html-img-chinese-alt",
    "html-picture-with-source",
    "outer-link-empty-content",
    "outer-link-with-alt",
    "nested-parentheses-url",
    "escaped-image-marker",
    "code-fence-literal",
    "inline-code-literal",
    "display-math-protected",
    "inline-math-protected",
    "empty-alt-with-hash-name",
    "generic-alt-placeholders",
    "image-with-caption-below",
    "consecutive-images",
    "only-images-becomes-empty",
    "emoji-and-combining-codepoints",
}

#: 这些样例里的图片写法**按规则要求逐字保留**：转义、代码围栏、行内代码、公式保护区，
#: 以及仍被普通文字链接使用的引用定义。
LITERAL_PRESERVING_CASES = {
    "escaped-image-marker",
    "code-fence-literal",
    "inline-code-literal",
    "display-math-protected",
    "inline-math-protected",
    "reference-definition-kept-for-text-link",
}


def test_samples_file_exists_and_is_versioned() -> None:
    assert SAMPLES_PATH.exists(), f"缺少跨语言样例：{SAMPLES_PATH}"
    assert VERSION == TEXT_PROJECTION_VERSION, "样例文件必须标注当前清洗版本"
    assert len(CASES) >= 14, "样例必须覆盖至少 14 组情形"


def test_sample_names_are_unique() -> None:
    names = [case["name"] for case in CASES]
    assert len(names) == len(set(names))


def test_required_situations_are_covered() -> None:
    names = {case["name"] for case in CASES}
    missing = sorted(REQUIRED_SITUATIONS - names)
    assert not missing, f"样例缺少情形：{missing}"


@pytest.mark.parametrize("version", SAMPLE_VERSIONS)
@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_sample_matches_implementation(case: dict, version: str) -> None:
    raw = case["raw"]
    projection = project_by_version(raw, version)
    assert projection.text == case["expectedText"], case["name"]
    assert projection.removed_image_count == case["expectedRemovedImageCount"], case["name"]
    assert segment_tuples(projection.source_segments) == case["expectedSegments"], case["name"]
    assert_projection_invariants(projection, raw)
    assert project_by_version(projection.text, version).text == projection.text


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_sample_segments_are_self_consistent(case: dict) -> None:
    """样例文件自身也要能回填：原文区间铺满 raw，清洗区间铺满 expectedText。"""
    raw = case["raw"]
    text = case["expectedText"]
    raw_cursor = 0
    clean_cursor = 0
    for segment in case["expectedSegments"]:
        assert segment["kind"] in {"kept", "alt_kept", "removed"}, case["name"]
        assert segment["rawStart"] == raw_cursor, case["name"]
        assert segment["cleanStart"] == clean_cursor, case["name"]
        raw_cursor = segment["rawEnd"]
        clean_cursor = segment["cleanEnd"]
        if segment["kind"] == "removed":
            assert segment["cleanStart"] == segment["cleanEnd"], case["name"]
        else:
            assert raw[segment["rawStart"] : segment["rawEnd"]] == text[
                segment["cleanStart"] : segment["cleanEnd"]
            ], case["name"]
    assert raw_cursor == len(raw), case["name"]
    assert clean_cursor == len(text), case["name"]


def test_samples_do_not_leak_image_addresses_in_cleaned_text() -> None:
    """除「按规则要求逐字保留」的样例外，清洗文本不得再出现图片地址或图片语法。"""
    for case in CASES:
        if case["name"] in LITERAL_PRESERVING_CASES:
            continue
        assert "images/" not in case["expectedText"], case["name"]
        assert "<img" not in case["expectedText"], case["name"]
        assert "![" not in case["expectedText"], case["name"]
