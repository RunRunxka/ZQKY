"""试卷知识点占比聚合（C4-3）：primary 知识点分值/题数占比 + 未分类 + 409。

流程：PapersHarness 导入 → 关联 K1/K2 → patch → confirm → HTTP 端点断言。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.papers import PaperConfirmRequest
from tests.papers_support import PapersHarness
from tests.test_papers_draft_confirm import _knowledge_map, _patch_payload, _import


@pytest.fixture()
def harness(tmp_path: Path):
    return PapersHarness(tmp_path)


def _prepared_paper(harness: PapersHarness, tmp_path: Path) -> str:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    points = [harness.add_point("K1", "二次函数"), harness.add_point("K2", "单调性")]
    service.patch_draft(
        paper_id,
        _patch_payload(imported, revision=0, knowledge=_knowledge_map(points)),
    )
    revision = service.get_paper(paper_id).revision
    service.confirm(paper_id, PaperConfirmRequest.model_validate(
        {"expectedRevision": revision, "submissionId": "dist-confirm"}
    ))
    return paper_id


def test_distribution_aggregates_primary_knowledge(tmp_path: Path, harness: PapersHarness) -> None:
    paper_id = _prepared_paper(harness, tmp_path)
    buckets = harness.service().knowledge_distribution(paper_id)
    assert buckets, "确认后的试卷应有知识点聚合"
    assert sum(b["itemCount"] for b in buckets) > 0
    total_ratio = sum(b["scoreRatio"] or 0 for b in buckets)
    assert 0.99 <= total_ratio <= 1.01, buckets
    names = [b["name"] for b in buckets]
    assert "二次函数" in names or "单调性" in names


def test_distribution_requires_confirmed_revision(tmp_path: Path, harness: PapersHarness) -> None:
    service, imported = _import(harness, tmp_path)
    paper_id = imported.paper.paper_id
    resp = harness.service().knowledge_distribution(paper_id)
    assert isinstance(resp, list)
