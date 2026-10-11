"""文本投影测试的公共断言：映射不变量、回填重建、逐组样例加载。

单独放一个模块，避免在每个测试文件里复制同一份不变量检查（本项目禁止第二套规则实现）。
本文件不包含业务规则，只做断言工具。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.text_projection import (
    SEGMENT_KIND_REMOVED,
    SourceSegment,
    TextProjection,
    known_projection_versions,
)

SAMPLES_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "text-projection-samples.json"
)


def load_samples() -> tuple[str, list[dict]]:
    """读取前后端共用样例；返回 (清洗版本, 用例列表)。"""
    payload = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["version"] in known_projection_versions(), "样例文件必须标注已知清洗版本"
    return payload["version"], list(payload["cases"])


def reinsert_raw(projection: TextProjection, raw: str, absolute_start: int = 0) -> str:
    """把被删区间按原文坐标填回去：结果必须与原文逐字相同。"""
    return "".join(
        raw[segment.raw_start - absolute_start : segment.raw_end - absolute_start]
        for segment in projection.source_segments
    )


def reinsert_clean(projection: TextProjection, absolute_start: int = 0) -> str:
    """把被删区间按清洗坐标填回去：结果必须与清洗文本逐字相同。"""
    text = projection.text
    return "".join(text[segment.clean_start : segment.clean_end] for segment in projection.source_segments)


def assert_projection_invariants(
    projection: TextProjection, raw: str, *, absolute_start: int = 0
) -> None:
    """校验 RAG-QUALITY v1.1 规定的全部投影不变量。"""
    assert reinsert_raw(projection, raw, absolute_start) == raw, "原文坐标必须能填回原文"
    assert reinsert_clean(projection, absolute_start) == projection.text, "清洗坐标必须能填回清洗文本"

    raw_cursor = absolute_start
    clean_cursor = 0
    for segment in projection.source_segments:
        assert segment.references_original_codepoint_offsets(), f"段未锚定原文码点：{segment}"
        assert segment.raw_start == raw_cursor, f"原文区间不连续：{segment}"
        assert segment.clean_start == clean_cursor, f"清洗区间不连续：{segment}"
        raw_cursor = segment.raw_end
        clean_cursor = segment.clean_end
        if segment.kind == SEGMENT_KIND_REMOVED:
            assert segment.clean_start == segment.clean_end
        else:
            assert (
                projection.text[segment.clean_start : segment.clean_end]
                == raw[
                    segment.raw_start - absolute_start : segment.raw_end - absolute_start
                ]
            ), f"保留段必须逐字来自原文：{segment}"
    assert raw_cursor == absolute_start + len(raw), "原文区间必须铺满原文"
    assert clean_cursor == len(projection.text), "清洗区间必须铺满清洗文本"


def segment_tuples(segments: tuple[SourceSegment, ...]) -> list[dict]:
    """转成样例文件的 camelCase 形式，便于与 fixture 直接比对。"""
    return [
        {
            "cleanStart": segment.clean_start,
            "cleanEnd": segment.clean_end,
            "rawStart": segment.raw_start,
            "rawEnd": segment.raw_end,
            "kind": segment.kind,
        }
        for segment in segments
    ]
