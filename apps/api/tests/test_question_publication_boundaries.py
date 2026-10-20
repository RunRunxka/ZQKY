"""Archived knowledge links remain readable but cannot enter a new formal revision.

归档/恢复公开端点已于 2026-10-20 移除；本文件保留“残留 archived 行”的防御性守卫回归，
测试通过仓储内部 ``archive_point`` 构造历史状态，不经过 HTTP 归档端点。
"""

from pathlib import Path

from tests.test_question_generation import GenerationHarness
from tests.test_question_subject_links import _confirmed_question, _patch_question


def test_archived_inherited_link_is_readable_but_cannot_enter_new_revision(tmp_path: Path) -> None:
    harness = GenerationHarness(tmp_path)
    try:
        point = harness.create_point()
        question_id, detail = _confirmed_question(harness, point)
        harness.archive_point(point["pointId"])
        rejected = _patch_question(harness, question_id, detail)
        assert rejected.status_code == 409, rejected.text
        assert rejected.json()["code"] == "KNOWLEDGE_ARCHIVED"
        assert harness.client.get(f"/api/v1/questions/{question_id}").json() == detail
        cleared = _patch_question(harness, question_id, detail, knowledgeLinks=[])
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["knowledgeLinks"] == []
    finally:
        harness.close()
