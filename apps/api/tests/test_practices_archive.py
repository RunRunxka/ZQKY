"""练习归档功能移除后的语义（B3，2026-10-20 用户裁定「全局移除归档，只留删除」）。

覆盖：

- ``POST /practice-sets/{id}/archive`` 与 ``/restore`` 不再存在（404，路由已移除）；
- 服务层 ``set_archived`` 已删除；列表 ``status`` 过滤不再接受 ``archived`` 之外的
  新值语义（旧库残留 archived 行仍可见可读，写入路径被只读兜底拒绝）；
- ``DELETE /practice-sets/{id}`` 仍是唯一清理出口（守卫语义归既有删除测试）。
"""

import pytest
from app.contracts import b4
from app.core.exceptions import AppError
from tests.practices_support import PracticesScene, open_api_scene, seed_api_loop


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


def reviewed(scene, *, tag="review"):
    # practice.create 的提交身份全局唯一：同一场景创建多个练习集必须用不同 tag。
    practice = scene.create_set(submission=tag + "-create")
    saved = scene.save(practice, [scene.item(scene.question(rich=scene.rich()))], submission=tag + "-draft")
    return scene.review(saved, submission=tag + "-review")


async def test_archive_restore_routes_are_gone(tmp_path):
    """真实 HTTP：归档/恢复路由 404，数据零变化；删除仍可用。"""
    with open_api_scene(tmp_path) as (app, client, settings):
        result = seed_api_loop(app, client)
        practice = result["practice"]
        set_id = practice["practiceSetId"]
        prefix = f"/api/v1/practice-sets/{set_id}"
        assert client.get(prefix).json()["status"] == "active"
        archived = client.post(prefix + "/archive", json={"expectedRevision": practice["revision"]})
        assert archived.status_code == 404, archived.text
        restored = client.post(prefix + "/restore", json={"expectedRevision": practice["revision"]})
        assert restored.status_code == 404, restored.text
        assert client.get(prefix).json()["status"] == "active"
        assert client.get(prefix).json()["revision"] == practice["revision"]


async def test_list_status_filter_rejects_new_semantics(scene):
    first = reviewed(scene, tag="first")
    second = reviewed(scene, tag="second")
    everything = scene.service.list_practices()
    assert everything.total == 2 and {x.status for x in everything.items} == {"active", "active"}
    active = scene.service.list_practices(status="active")
    assert active.total == 2
    with pytest.raises(AppError) as error:
        scene.service.list_practices(status="archived")
    assert error.value.code == "PRACTICE_INVALID"
    with pytest.raises(AppError) as error2:
        scene.service.list_practices(status="bogus")
    assert error2.value.code == "PRACTICE_INVALID"
    _ = first, second


async def test_stale_archived_row_stays_readable_but_not_writable(scene):
    """旧库残留 archived 行（模拟）：可读、写入被只读兜底拒绝、删除仍可用。"""
    practice = reviewed(scene, tag="stale")
    with scene.catalog.write_transaction() as conn:
        conn.execute(
            "UPDATE practice_sets SET status='archived' WHERE id=?",
            (practice.practice_set_id,),
        )
    current = scene.service.get_practice(practice.practice_set_id)
    assert current.status == "archived"
    # 写路径被只读兜底拒绝（PRACTICE_ARCHIVED 409）
    with pytest.raises(AppError) as error:
        scene.service.save_draft(
            practice.practice_set_id,
            b4.PracticeDraftPatch(submissionId="stale-arch-draft-1", expectedRevision=current.revision,
                items=[], constraints=current.current_revision.constraints),
        )
    assert error.value.code == "PRACTICE_ARCHIVED" and error.value.status_code == 409
    # 删除仍是出口：includeHistory 跳过守卫（纯草稿/已审核历史一并删）
    removed = scene.service.delete_practice(
        practice.practice_set_id,
        b4.PracticeSetStatusRequest(expectedRevision=current.revision),
        include_history=True,
    )
    assert removed.deleted is True
    with pytest.raises(AppError) as missing:
        scene.service.get_practice(practice.practice_set_id)
    assert missing.value.code == "PRACTICE_NOT_FOUND"
