"""性能与规模守卫：真实教材规模的清洗必须线性有界（RAG-QUALITY v1.1 修复卡）。

背景：v1.0 的扫描器在「不等式 ``4x-5<3`` + 图片节点」的真实教材写法上死循环——正式重建
在第一册卡住 21 分钟、checkpoint 仍 0/58。本文件把当时的最小复现、不完整构造矩阵与
规模预算固定下来，防止再退化成循环或超线性。

阈值取实测值的 10 倍以上留白，避免机器负载造成假失败；实测数字见结果卡「v1.1 修复」小节。
"""

from __future__ import annotations

import time

import pytest

from app.services.text_projection import TEXT_PROJECTION_VERSION, project_readable
from test_text_projection_support import assert_projection_invariants

#: 单篇上限（字符）：覆盖真实 32 万字教材并留出余量
LARGE_DOCUMENT_MIN_CHARS = 300_000
#: 构造样本的段数：每段约 144 字符（含分隔空行），2400 段 ≈ 34.5 万字
BLOCK_COUNT = 2400
#: 整篇清洗预算（秒）：实测真实教材约 0.15 秒，这里留 30 倍以上余量
LARGE_DOCUMENT_BUDGET_SECONDS = 5.0
#: 单条真实写法（不等式 + 图片）的毫秒级预算
SMALL_CASE_BUDGET_SECONDS = 0.2

BLOCK = (
    "段落正文：解不等式 4x-5<3 得 x<2，见图 1。\n"
    "第二行含 a<b 与 $v = \\frac{s}{t}$ 公式，另有 <b>粗体</b> 与 [课标](https://example.com) 链接。\n"
    "![](images/fig_(1)_a.png)\n"
    "图 1 实验装置示意"
)

#: 正式重建卡住时的三条最小复现（原样保留，作为永久回归用例）
MINIMAL_REPROS = [
    "4x-5<3\n\n![](images/abc)",
    "x<3\n![](images/abc)",
    "(3) 不等式 4x-5<3 的解集.\n\n![](images/abc)",
]

ADVERSARIAL_CASES = {
    "连续图片起始符": "![" * 500,
    "连续未闭合尖括号": "<" * 2000,
    "连续未闭合方括号": "[" * 2000,
    "连续缺目标引用定义": "[f]:\n" * 500,
    "不等式密排": "a<b " * 500,
    "未闭合围栏含图片": "```\n" + "x<3 ![a](images/b.png)\n" * 200,
    "未闭合注释含图片": "<!-- ![a](images/b.png)\n" * 200,
}


def build_document(blocks: int) -> str:
    return "\n\n".join([BLOCK] * blocks)


def timed_project(raw: str, budget: float) -> tuple[object, float]:
    start = time.perf_counter()
    projection = project_readable(raw)
    elapsed = time.perf_counter() - start
    assert elapsed < budget, f"投影超出预算：{elapsed:.3f}s > {budget}s（字符数 {len(raw)}）"
    return projection, elapsed


def test_minimal_repros_no_longer_hang() -> None:
    """v1.1 修复卡的三条最小复现：毫秒级完成，且图片节点照常清洗。"""
    for raw in MINIMAL_REPROS:
        projection, elapsed = timed_project(raw, SMALL_CASE_BUDGET_SECONDS)
        assert elapsed < SMALL_CASE_BUDGET_SECONDS
        assert projection.removed_image_count == 1, raw
        assert "images/abc" not in projection.text, raw
        assert "<3" in projection.text, "不等式写法必须按字面保留"
        assert_projection_invariants(projection, raw)


def test_large_document_projection_finishes_within_budget() -> None:
    """≥30 万字符整篇清洗：预算内完成，映射可回原、幂等、图片全部清除。"""
    document = build_document(BLOCK_COUNT)
    assert len(document) >= LARGE_DOCUMENT_MIN_CHARS, f"样本仅 {len(document)} 字符"
    projection, elapsed = timed_project(document, LARGE_DOCUMENT_BUDGET_SECONDS)
    assert projection.version == TEXT_PROJECTION_VERSION
    assert projection.removed_image_count == BLOCK_COUNT
    assert "images/" not in projection.text
    assert_projection_invariants(projection, document)
    second = project_readable(projection.text)
    assert second.text == projection.text
    assert second.removed_image_count == 0
    assert elapsed < LARGE_DOCUMENT_BUDGET_SECONDS


def test_large_document_matches_per_block_projection() -> None:
    """整篇清洗结果必须等于逐段清洗后按空行拼接（无跨段隐藏状态）。

    样本的每一段都是「非空且无首尾空行」的自足段落，段间只有一个空行；
    归一化只在本段内生效，因此整篇结果与逐段拼接严格相等。
    """
    blocks = [BLOCK] * BLOCK_COUNT
    document = "\n\n".join(blocks)
    whole = project_readable(document)
    parts = [project_readable(block).text for block in blocks]
    assert "\n\n".join(parts) == whole.text
    assert all(part.strip() for part in parts), "每段清洗后都必须非空，否则拼接语义不同"


def test_inequality_with_image_is_millisecond_scale() -> None:
    """真实教材高频写法（不等式 + 图片）必须是毫秒级；慢于此即可能是循环回归。"""
    for raw in MINIMAL_REPROS + ["x < 3\n\n![](images/abc)", "![说明](images/a.png)\n4x-5<3"]:
        _, elapsed = timed_project(raw, SMALL_CASE_BUDGET_SECONDS)
        assert elapsed < SMALL_CASE_BUDGET_SECONDS, f"{raw!r} 用时 {elapsed:.3f}s"


@pytest.mark.parametrize("name", sorted(ADVERSARIAL_CASES))
def test_adversarial_repetition_stays_bounded(name: str) -> None:
    """不完整/异常构造重复出现时不得停住，必须是可终止且有界的。"""
    raw = ADVERSARIAL_CASES[name]
    projection, elapsed = timed_project(raw, 1.0)
    assert elapsed < 1.0, name
    assert_projection_invariants(projection, raw)


def test_cursor_always_advances_on_unfinished_html_tag() -> None:
    """根因回归：``<`` 后不是 ``>`` 时标签扫描必须严格前进，不得原地打转。

    v1.0 在 ``_parse_html_tag`` 的属性循环里遇到不成对的 ``/``（如 ``images/abc``）
    会原地循环：``<`` 未被当作字面量，游标不前进 → 永不终止。
    """
    for raw in [
        "4x-5<3\n\n![](images/abc)",
        "x<3 ![](images/a.png)",
        "a/b<3 ![](images/a.png)",
        "<3 images/a.png",
        "<a/b",
    ]:
        projection, elapsed = timed_project(raw, SMALL_CASE_BUDGET_SECONDS)
        assert elapsed < SMALL_CASE_BUDGET_SECONDS
        assert_projection_invariants(projection, raw)
