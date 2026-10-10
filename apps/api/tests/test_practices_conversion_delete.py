"""练习转换记录删除（DELETE /practice-sets/{id}/revisions/{rid}/conversion）。

覆盖（真四库 + 真实服务装配，tmp_path 隔离；不触碰正式 .local-data）：

- 404：该审核修订没有转换记录（``PRACTICE_CONVERSION_NOT_FOUND``）；
- 成功：``practice_conversions`` 行与 ``practice_paper_item_mappings`` 子行全清，
  ``assessments``/``paper_revisions``/``practice_revisions`` 行原样保留；
- 计数联动：施测 ``ASSESSMENT_IN_USE`` 的 ``practiceConversions`` 与练习
  ``PRACTICE_IN_USE`` 的 ``conversions`` 计数归零（既有 ``count_references_in`` 断言）；
- 触发器恢复：删除后直接 SQL 删另一行 ``practice_conversions`` → 被拒
  （``IMMUTABLE_REVISION`` 兜底仍生效，先例 test_knowledge_delete.py）；
- 守卫链联动：删除转换后施测可走 ``ASSESSMENT_IN_USE`` 全链删除；
  练习集删除守卫不再因 conversions 被挡（只剩 reviewedRevisions）；
- HTTP 路由层（TestClient）回执与 404。
"""

from __future__ import annotations

import sqlite3

import pytest

from app.contracts import b4
from app.contracts.assessments import AssessmentRevisionRequest
from app.core.exceptions import AppError
from app.repositories.teaching.assessments import AssessmentRepository
from app.repositories.teaching.practices import PracticeRepository
from tests.practices_support import PracticesScene


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def reviewed(scene):
    return scene.review(scene.save(scene.create_set(), [scene.item(scene.question(rich=scene.rich()))]))


async def test_delete_conversion_missing_returns_404(scene) -> None:
    """该 set+revision 无转换记录 → 404 PRACTICE_CONVERSION_NOT_FOUND；不静默成功。"""
    practice = reviewed(scene)
    revision_id = practice.current_revision.practice_revision_id
    with pytest.raises(AppError) as missing:
        scene.service.delete_conversion(practice.practice_set_id, revision_id)
    assert missing.value.status_code == 404
    assert missing.value.code == "PRACTICE_CONVERSION_NOT_FOUND"
    # 练习集不存在 / 修订归属不符 → 既有 404 语义，不进入删除
    with pytest.raises(AppError) as no_set:
        scene.service.delete_conversion("no-such-set", revision_id)
    assert no_set.value.code == "PRACTICE_NOT_FOUND"
    with pytest.raises(AppError) as no_revision:
        scene.service.delete_conversion(practice.practice_set_id, "no-such-revision")
    assert no_revision.value.code == "PRACTICE_NOT_FOUND"


async def test_delete_conversion_clears_rows_and_keeps_assessment(scene) -> None:
    """成功删除：conversion 与 mappings 全清；assessments / paper_revisions / practice_revisions 仍在。"""
    practice = reviewed(scene)
    receipt = scene.conversion(practice)
    revision_id = practice.current_revision.practice_revision_id
    with scene.catalog.read_connection() as conn:
        paper_revision_id = conn.execute(
            "SELECT paper_revision_id FROM practice_conversions WHERE id=?", (receipt.conversion_id,)
        ).fetchone()[0]
    # scene.count 白名单不含练习本体表；这里用直接 SQL 计数对照本体表不被触碰
    tables = ("assessments", "papers", "paper_revisions", "paper_items", "practice_revisions", "practice_sets")
    with scene.catalog.read_connection() as conn:
        baseline = {t: conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in tables}

    result = scene.service.delete_conversion(practice.practice_set_id, revision_id)

    assert result.deleted is True
    assert result.conversion_id == receipt.conversion_id
    assert result.assessment_id == receipt.assessment_id
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_conversions WHERE id=?",
                            (receipt.conversion_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_paper_item_mappings WHERE conversion_id=?",
                            (receipt.conversion_id,)).fetchone()[0] == 0
    # 关联行清零，但施测/原卷/练习本体不动（显式范围：只删关联行与映射子行）
    with scene.catalog.read_connection() as conn:
        assert {t: conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in tables} == baseline
        assert conn.execute("SELECT COUNT(*) FROM assessments WHERE id=?",
                            (receipt.assessment_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT state FROM paper_revisions WHERE id=?",
                            (paper_revision_id,)).fetchone()[0] == "confirmed"
        assert conn.execute("SELECT state FROM practice_revisions WHERE id=?",
                            (revision_id,)).fetchone()[0] == "reviewed"
    # 施测本体仍可读
    detail = scene.assessments.get_assessment(receipt.assessment_id)
    assert detail.assessment.assessment_id == receipt.assessment_id
    # 同一修订再删一次：已无转换 → 404
    with pytest.raises(AppError) as missing:
        scene.service.delete_conversion(practice.practice_set_id, revision_id)
    assert missing.value.code == "PRACTICE_CONVERSION_NOT_FOUND"


async def test_delete_conversion_zeroes_guard_counts(scene) -> None:
    """计数联动：删除后施测 practiceConversions 与练习 conversions 计数归零。"""
    practice = reviewed(scene)
    receipt = scene.conversion(practice)
    set_id = practice.practice_set_id
    assessments = AssessmentRepository(scene.catalog)
    practices = PracticeRepository(scene.catalog)
    with scene.catalog.read_connection() as conn:
        assert assessments.count_references_in(conn, receipt.assessment_id)["practiceConversions"] == 1
        assert practices.count_references_in(conn, set_id)["conversions"] == 1

    scene.service.delete_conversion(set_id, practice.current_revision.practice_revision_id)

    with scene.catalog.read_connection() as conn:
        assert assessments.count_references_in(conn, receipt.assessment_id)["practiceConversions"] == 0
        assert practices.count_references_in(conn, set_id)["conversions"] == 0


async def test_triggers_restored_after_delete(scene) -> None:
    """删除后逐字恢复不可变触发器：再删另一行 practice_conversions → 被拒（先例 test_knowledge_delete.py）。"""
    practice = reviewed(scene)
    first = scene.conversion(practice)
    second = scene.conversion(practice, submission="conversion-second")
    assert first.conversion_id != second.conversion_id

    # 删除的是最新一条（created_at DESC, rowid DESC）；首条仍在
    result = scene.service.delete_conversion(practice.practice_set_id,
                                             practice.current_revision.practice_revision_id)
    assert result.conversion_id == second.conversion_id
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_conversions WHERE id=?",
                            (first.conversion_id,)).fetchone()[0] == 1
    scene.integrity()

    # 触发器已逐字恢复：绕过服务直接 SQL 删剩余行 → IMMUTABLE_REVISION 兜底仍生效
    connection = sqlite3.connect(scene.catalog.db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError) as excinfo:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            connection.execute("DELETE FROM practice_conversions WHERE id=?", (first.conversion_id,))
            connection.execute("ROLLBACK")
        assert "IMMUTABLE_REVISION" in str(excinfo.value)
        # 两个触发器对象都回到 schema（b4 0008 声明逐字恢复）
        for name in ("immutable_practice_conversions_delete", "immutable_practice_paper_item_mappings_delete"):
            row = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name=?",
                                     (name,)).fetchone()
            assert row is not None, name
    finally:
        connection.close()
    scene.integrity()


async def test_delete_conversion_unblocks_assessment_full_delete(scene) -> None:
    """删除转换后，施测自身的 ASSESSMENT_IN_USE 守卫链不再被 practiceConversions 挡，可全链删除。"""
    practice = reviewed(scene)
    receipt = scene.conversion(practice)
    detail = scene.assessments.get_assessment(receipt.assessment_id)
    with scene.catalog.read_connection() as conn:
        counts = AssessmentRepository(scene.catalog).count_references_in(conn, receipt.assessment_id)
    assert counts == {"scoreRevisions": 0, "scoreImports": 0, "analysisRuns": 0, "practiceConversions": 1}

    scene.service.delete_conversion(practice.practice_set_id, practice.current_revision.practice_revision_id)
    outcome = scene.assessments.delete_assessment(
        receipt.assessment_id, AssessmentRevisionRequest(expectedRevision=detail.assessment.revision))
    assert outcome["deleted"] is True and outcome["assessmentId"] == receipt.assessment_id
    with pytest.raises(AppError) as gone:
        scene.assessments.get_assessment(receipt.assessment_id)
    assert gone.value.code == "ASSESSMENT_NOT_FOUND"


async def test_delete_conversion_unblocks_practice_guard_conversions(scene) -> None:
    """删除转换后再删练习集：不再因 conversions 被挡（counts 只剩 reviewedRevisions）。"""
    practice = reviewed(scene)
    set_id = practice.practice_set_id
    scene.conversion(practice)
    with pytest.raises(AppError) as blocked:
        scene.service.delete_practice(set_id, b4.PracticeSetStatusRequest(expectedRevision=practice.revision))
    assert blocked.value.code == "PRACTICE_IN_USE"
    assert blocked.value.details["counts"]["conversions"] == 1

    scene.service.delete_conversion(set_id, practice.current_revision.practice_revision_id)
    with pytest.raises(AppError) as still_blocked:
        scene.service.delete_practice(set_id, b4.PracticeSetStatusRequest(expectedRevision=practice.revision))
    # reviewed 修订受触发器保护，只能归档：守卫仍在；counts 只列 >0 的键，conversions 已归零不出现
    assert still_blocked.value.code == "PRACTICE_IN_USE"
    assert still_blocked.value.details["counts"] == {"reviewedRevisions": 1}
    # 仓储计数口径下 conversions 明确为 0
    with scene.catalog.read_connection() as conn:
        assert PracticeRepository(scene.catalog).count_references_in(conn, set_id)["conversions"] == 0


async def test_delete_conversion_archived_set_allowed(scene) -> None:
    """归档不影响解除回流关联（与 delete_practice 同口径）：归档练习集 → 删除成功，回执正常。"""
    practice = reviewed(scene)
    receipt = scene.conversion(practice)
    scene.service.set_archived(practice.practice_set_id,
                               b4.PracticeSetStatusRequest(expectedRevision=practice.revision), archived=True)
    result = scene.service.delete_conversion(practice.practice_set_id,
                                             practice.current_revision.practice_revision_id)
    assert result.deleted is True
    assert result.conversion_id == receipt.conversion_id
    assert result.assessment_id == receipt.assessment_id
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_conversions WHERE id=?",
                            (receipt.conversion_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_paper_item_mappings WHERE conversion_id=?",
                            (receipt.conversion_id,)).fetchone()[0] == 0
        # 施测本体仍在：只解除回流关联
        assert conn.execute("SELECT COUNT(*) FROM assessments WHERE id=?",
                            (receipt.assessment_id,)).fetchone()[0] == 1


async def test_revision_view_converted_assessment_id_lifecycle(scene) -> None:
    """只读派生字段：转换建立后有值；删除后为 null；无转换修订为 null（读路径实时取最新）。"""
    practice = reviewed(scene)
    revision_id = practice.current_revision.practice_revision_id
    # 无转换 → null
    assert scene.service.get_revision(practice.practice_set_id, revision_id).converted_assessment_id is None

    receipt = scene.conversion(practice)
    view = scene.service.get_revision(practice.practice_set_id, revision_id)
    assert view.converted_assessment_id == receipt.assessment_id
    # 集合视图（currentRevision 与 revisions 列表）同口径
    assert scene.service.get_practice(practice.practice_set_id).current_revision.converted_assessment_id == receipt.assessment_id

    # 多条转换取最新（与 delete_conversion_in 同排序口径）
    second = scene.conversion(practice, submission="conversion-view-second")
    assert scene.service.get_revision(practice.practice_set_id, revision_id).converted_assessment_id == second.assessment_id

    # 删除逐条解除：先删最新一条，剩余首条成为"最新"继续展示
    scene.service.delete_conversion(practice.practice_set_id, revision_id)
    assert scene.service.get_revision(practice.practice_set_id, revision_id).converted_assessment_id == receipt.assessment_id
    # 再删一次：无转换 → null
    scene.service.delete_conversion(practice.practice_set_id, revision_id)
    assert scene.service.get_revision(practice.practice_set_id, revision_id).converted_assessment_id is None


def test_delete_conversion_via_http_route(tmp_path) -> None:
    """HTTP 路由冒烟：DELETE conversion 注册；回执 {deleted, conversionId, assessmentId}；再删 404。"""
    from tests.practices_support import open_api_scene, seed_api_loop

    with open_api_scene(tmp_path) as (app, client, _settings):
        result = seed_api_loop(app, client)
        conversion = result["conversion"]
        practice = result["practice"]
        revision_id = practice["currentRevision"]["practiceRevisionId"]
        prefix = f"/api/v1/practice-sets/{practice['practiceSetId']}/revisions/{revision_id}/conversion"

        # HTTP GET 修订视图：转换已建立 → convertedAssessmentId 实时可见（刷新页面后仍可展示与解除）
        before = client.get(f"/api/v1/practice-sets/{practice['practiceSetId']}/revisions/{revision_id}")
        assert before.status_code == 200, before.text
        assert before.json()["convertedAssessmentId"] == conversion["assessmentId"]

        deleted = client.delete(prefix)
        assert deleted.status_code == 200, deleted.text
        body = deleted.json()
        assert body == {"deleted": True, "conversionId": conversion["conversionId"],
                        "assessmentId": conversion["assessmentId"]}
        # 删除后修订视图的回流字段归 null
        after = client.get(f"/api/v1/practice-sets/{practice['practiceSetId']}/revisions/{revision_id}")
        assert after.status_code == 200, after.text
        assert after.json()["convertedAssessmentId"] is None
        # 再删一次：无转换 → 404 PRACTICE_CONVERSION_NOT_FOUND
        again = client.delete(prefix)
        assert again.status_code == 404, again.text
        assert again.json()["code"] == "PRACTICE_CONVERSION_NOT_FOUND"
        # 施测本体仍在（只解除回流关联）
        kept = client.get(f"/api/v1/assessments/{conversion['assessmentId']}")
        assert kept.status_code == 200, kept.text
        # 不存在的练习集 → 404
        missing = client.delete("/api/v1/practice-sets/no-such-set/revisions/x/conversion")
        assert missing.status_code == 404
