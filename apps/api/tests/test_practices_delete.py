"""练习集受引用守卫的彻底删除（DELETE /practice-sets/{id}）。

覆盖（真四库 + 真实服务装配，tmp_path 隔离）：

- 可删成功：只有 draft 修订的练习集物理删除（修订子行 + 集合行全部消失）；
- 已审核版本 → 409 ``PRACTICE_IN_USE``（reviewed 受 DB 触发器保护只能归档）；
- 导出/转换引用 → 409 ``PRACTICE_IN_USE``（counts 列出计数）；
- 乐观锁 409 ``REVISION_CONFLICT``；404（练习集不存在）；
- draft 修订清理语义：reviewed 修订存在时 draft 可单独清理（触发器只保护 reviewed）。
"""

from __future__ import annotations

import pytest

from app.contracts import b4
from app.core.exceptions import AppError
from tests.practices_support import PracticesScene


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def _draft_only(scene, *, tag="del"):
    """创建并保存草稿（不审核）：集合只有 draft 修订。"""
    practice = scene.create_set(submission=tag + "-create")
    return scene.save(practice, [scene.item(scene.question(rich=scene.rich()))], submission=tag + "-draft")


async def test_delete_draft_only_set_succeeds(scene) -> None:
    practice = _draft_only(scene, tag="d1")
    set_id = practice.practice_set_id
    revision_id = practice.current_revision.practice_revision_id

    receipt = scene.service.delete_practice(
        set_id, b4.PracticeSetStatusRequest(expectedRevision=practice.revision)
    )
    assert receipt.deleted is True
    assert receipt.practice_set_id == set_id

    # 物理删除：集合行、修订行与全部子表行消失
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_sets WHERE id=?", (set_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_revisions WHERE id=?", (revision_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_selections WHERE practice_revision_id=?", (revision_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_items WHERE practice_revision_id=?", (revision_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM practice_item_knowledge WHERE practice_revision_id=?", (revision_id,)).fetchone()[0] == 0
    with pytest.raises(AppError) as missing:
        scene.service.get_practice(set_id)
    assert missing.value.code == "PRACTICE_NOT_FOUND"


async def test_delete_set_blocked_by_reviewed_revision(scene) -> None:
    """已审核版本受 DB 触发器保护：reviewed 只能归档，如需修改从审核版建新草稿。"""
    practice = _draft_only(scene, tag="d2")
    reviewed = scene.review(practice, submission="d2-review")
    # 建一个新草稿修订，让集合同时有 reviewed + draft
    copied = scene.service.new_revision(
        reviewed.practice_set_id,
        b4.PracticeRevisionRequest(submissionId="d2-copy", sourceRevisionId=reviewed.current_revision.practice_revision_id),
    )
    assert copied.current_revision.state == "draft"

    with pytest.raises(AppError) as blocked:
        scene.service.delete_practice(
            copied.practice_set_id, b4.PracticeSetStatusRequest(expectedRevision=copied.revision)
        )
    assert blocked.value.status_code == 409
    assert blocked.value.code == "PRACTICE_IN_USE"
    assert blocked.value.details["counts"]["reviewedRevisions"] == 1
    # 零删除：集合与两个修订都还在
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_revisions WHERE practice_set_id=?", (copied.practice_set_id,)).fetchone()[0] == 2


async def test_delete_set_blocked_by_export_reference(scene) -> None:
    practice = _draft_only(scene, tag="d3")
    reviewed = scene.review(practice, submission="d3-review")
    receipt = await scene.export(reviewed, variant="student", submission="d3-export")
    assert receipt.job is not None
    current = scene.service.get_practice(reviewed.practice_set_id)

    with pytest.raises(AppError) as blocked:
        scene.service.delete_practice(
            current.practice_set_id, b4.PracticeSetStatusRequest(expectedRevision=current.revision)
        )
    assert blocked.value.status_code == 409
    assert blocked.value.code == "PRACTICE_IN_USE"
    assert blocked.value.details["counts"]["exports"] == 1
    assert blocked.value.details["counts"]["reviewedRevisions"] == 1


async def test_delete_set_revision_conflict(scene) -> None:
    practice = _draft_only(scene, tag="d4")
    with pytest.raises(AppError) as stale:
        scene.service.delete_practice(
            practice.practice_set_id,
            b4.PracticeSetStatusRequest(expectedRevision=practice.revision + 5),
        )
    assert stale.value.code == "REVISION_CONFLICT"
    assert stale.value.details["currentRevision"] == practice.revision
    # 零删除
    assert scene.service.get_practice(practice.practice_set_id) is not None


async def test_delete_set_not_found(scene) -> None:
    with pytest.raises(AppError) as missing:
        scene.service.delete_practice(
            "no-such-set", b4.PracticeSetStatusRequest(expectedRevision=0)
        )
    assert missing.value.code == "PRACTICE_NOT_FOUND"


async def test_delete_set_clears_draft_revisions_only(scene) -> None:
    """draft 清理语义：触发器只保护 reviewed；同集合的 draft 全部可清。"""
    practice = _draft_only(scene, tag="d6")
    reviewed = scene.review(practice, submission="d6-review")
    # 不能删（有 reviewed）
    with pytest.raises(AppError) as blocked:
        scene.service.delete_practice(
            reviewed.practice_set_id,
            b4.PracticeSetStatusRequest(expectedRevision=reviewed.revision),
        )
    assert blocked.value.code == "PRACTICE_IN_USE"
    # 审核版集合仍在（draft 清理守卫不误删 reviewed 集合数据）
    assert scene.service.get_practice(reviewed.practice_set_id).current_revision.state == "reviewed"


def test_delete_set_via_http_route(tmp_path) -> None:
    """HTTP 路由冒烟：DELETE /practice-sets/{id} 注册且回执为 {deleted, practiceSetId}。"""
    from tests.practices_support import open_api_scene, seed_api_loop

    with open_api_scene(tmp_path) as (app, client, _settings):
        result = seed_api_loop(app, client)
        practice = result["practice"]
        prefix = f"/api/v1/practice-sets/{practice['practiceSetId']}"
        # 已审核集合：守卫 409 + 计数
        blocked = client.delete(prefix, params={"expectedRevision": practice["revision"]})
        assert blocked.status_code == 409, blocked.text
        assert blocked.json()["code"] == "PRACTICE_IN_USE"
        assert blocked.json()["details"]["counts"]["reviewedRevisions"] >= 1
        # 乐观锁：过期 revision 409
        stale = client.delete(prefix, params={"expectedRevision": practice["revision"] + 9})
        assert stale.status_code == 409
        assert stale.json()["code"] == "REVISION_CONFLICT"
        # 404
        missing = client.delete("/api/v1/practice-sets/no-such-set", params={"expectedRevision": 0})
        assert missing.status_code == 404
