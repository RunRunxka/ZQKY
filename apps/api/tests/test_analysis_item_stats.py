"""item_stats 图表聚合（C2）：按题号的全班得分率（匿名）。

用 AnalysisScene 夹具（4 人 × 3 题，max=[200,300,500]，含 recorded/missing/absent）：
- 口径：score_rate = Σrecorded / (recorded_count × max)，missing/absent 不进分母；
- i000: 200+200+0 / (3×200) = 2/3；i001: 200+300+300 / (3×300) = 8/9；i002: 500+500 / (2×500) = 1.0；
- 报告未就绪 → 409 REPORT_NOT_READY。
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from tests.analysis_support import AnalysisScene


@pytest.mark.asyncio
async def test_item_stats_aggregates_per_item(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.ready()
    stats = scene.service.item_stats(receipt.run_id)
    assert [s.item_path for s in stats] == ["Q1", "Q2", "Q3"]
    by_path = {s.item_path: s for s in stats}
    q1, q2, q3 = by_path["Q1"], by_path["Q2"], by_path["Q3"]
    # Q1: 3 人有效（200/200/0），率 400/600
    assert (q1.recorded_count, q1.total_score_units, q1.max_score_units) == (3, 400, 200)
    assert q1.score_rate == pytest.approx(400 / 600)
    # Q2: 3 人有效（200/300/300），率 800/900
    assert (q2.recorded_count, q2.total_score_units) == (3, 800)
    assert q2.score_rate == pytest.approx(800 / 900)
    # Q3: 2 人有效（500/500；missing/absent 不进分母），率 1.0
    assert (q3.recorded_count, q3.total_score_units) == (2, 1000)
    assert q3.score_rate == pytest.approx(1.0)
    # 匿名聚合：不含个人身份字段
    dumped = stats[0].model_dump(by_alias=True)
    assert set(dumped) == {"itemId", "itemPath", "maxScoreUnits", "recordedCount", "totalScoreUnits", "scoreRate"}


@pytest.mark.asyncio
async def test_item_stats_requires_ready_report(tmp_path):
    scene = AnalysisScene(tmp_path)
    receipt = await scene.accept()
    with pytest.raises(AppError) as excinfo:
        scene.service.item_stats(receipt.run_id)
    assert excinfo.value.code == "REPORT_NOT_READY"
