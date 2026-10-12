"""练习集归档/恢复：软隐藏保留全部历史，归档后写路径 409 PRACTICE_ARCHIVED。"""
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


def archive(scene, practice, *, expected_revision=None, archived=True):
    return scene.service.set_archived(practice.practice_set_id,
        b4.PracticeSetStatusRequest(expectedRevision=practice.revision if expected_revision is None else expected_revision),
        archived=archived)


async def test_archive_restore_keeps_history_and_bumps_revision(scene):
    practice = reviewed(scene)
    assert practice.status == "active"
    archived = archive(scene, practice)
    assert archived.status == "archived" and archived.revision == practice.revision + 1
    # 归档不动修订：详情/修订读取一律原样可见。
    detail = scene.service.get_practice(practice.practice_set_id)
    assert detail.status == "archived" and [r.model_dump() for r in detail.revisions] == [r.model_dump() for r in practice.revisions]
    assert scene.service.get_revision(practice.practice_set_id, practice.current_revision.practice_revision_id).state == "reviewed"
    restored = archive(scene, archived, expected_revision=archived.revision, archived=False)
    assert restored.status == "active" and restored.revision == archived.revision + 1
    assert scene.service.get_practice(practice.practice_set_id).current_revision.state == "reviewed"


async def test_archive_rejects_stale_revision_without_touching_status(scene):
    practice = reviewed(scene)
    with pytest.raises(AppError) as error:
        archive(scene, practice, expected_revision=practice.revision + 3)
    assert error.value.code == "REVISION_CONFLICT"
    assert scene.service.get_practice(practice.practice_set_id).status == "active"


async def test_archived_set_rejects_all_writes_but_reads_remain(scene):
    practice = reviewed(scene)
    archived = archive(scene, practice)
    revision_id = archived.current_revision.practice_revision_id
    prefix = archived.practice_set_id
    # 草稿保存
    with pytest.raises(AppError) as error:
        scene.service.save_draft(prefix, b4.PracticeDraftPatch(submissionId="archived-draft", expectedRevision=archived.revision,
            items=[], constraints=archived.current_revision.constraints))
    assert error.value.code == "PRACTICE_ARCHIVED" and error.value.status_code == 409
    # 复核转 reviewed
    with pytest.raises(AppError) as error:
        scene.service.review(prefix, b4.PracticeReviewRequest(submissionId="archived-review", expectedRevision=archived.revision))
    assert error.value.code == "PRACTICE_ARCHIVED"
    # 新建修订
    with pytest.raises(AppError) as error:
        scene.service.new_revision(prefix, b4.PracticeRevisionRequest(submissionId="archived-copy", sourceRevisionId=revision_id))
    assert error.value.code == "PRACTICE_ARCHIVED"
    # 导出
    with pytest.raises(AppError) as error:
        await scene.export(archived, submission="archived-export")
    assert error.value.code == "PRACTICE_ARCHIVED"
    # 转成施测
    with pytest.raises(AppError) as error:
        scene.conversion(archived, submission="archived-conversion")
    assert error.value.code == "PRACTICE_ARCHIVED"
    # 读取不受影响：详情/修订/导出列表均可访问。
    assert scene.service.get_practice(prefix).status == "archived"
    assert scene.service.get_revision(prefix, revision_id).practice_revision_id == revision_id
    assert scene.service.list_exports(prefix, revision_id).total == 0


async def test_archived_write_guards_block_before_receipt_commit(scene):
    """归档守卫在提交事务内拒绝：不留 command_submissions 收据，也不改数据。"""
    practice = reviewed(scene)
    archived = archive(scene, practice)
    for writes in (
        lambda: scene.service.save_draft(archived.practice_set_id, b4.PracticeDraftPatch(submissionId="guard-draft",
            expectedRevision=archived.revision, items=[], constraints=archived.current_revision.constraints)),
        lambda: scene.service.review(archived.practice_set_id, b4.PracticeReviewRequest(submissionId="guard-review",
            expectedRevision=archived.revision)),
        lambda: scene.service.new_revision(archived.practice_set_id, b4.PracticeRevisionRequest(submissionId="guard-copy",
            sourceRevisionId=archived.current_revision.practice_revision_id)),
    ):
        with pytest.raises(AppError) as error:
            writes()
        assert error.value.code == "PRACTICE_ARCHIVED"
    with scene.catalog.read_connection() as conn:
        remaining = conn.execute("SELECT count(*) FROM command_submissions WHERE owner_id=? AND submission_id IN ('guard-draft','guard-review','guard-copy')",
            (scene.service.owner_id,)).fetchone()[0]
    assert remaining == 0
    assert scene.service.get_practice(archived.practice_set_id).revision == archived.revision


async def test_restore_reopens_writes(scene):
    practice = reviewed(scene)
    archived = archive(scene, practice)
    restored = archive(scene, archived, expected_revision=archived.revision, archived=False)
    # 恢复后写路径重新可用：先新建草稿修订（当前已是 reviewed），再保存草稿。
    copied = scene.service.new_revision(restored.practice_set_id,
        b4.PracticeRevisionRequest(submissionId="after-restore-copy", sourceRevisionId=restored.current_revision.practice_revision_id))
    assert copied.status == "active" and copied.current_revision.state == "draft"
    edited = scene.service.save_draft(copied.practice_set_id, b4.PracticeDraftPatch(submissionId="after-restore-draft",
        expectedRevision=copied.revision, items=[], constraints=copied.current_revision.constraints))
    assert edited.status == "active" and edited.revision == copied.revision + 1


async def test_list_filter_by_status(scene):
    first = reviewed(scene, tag="first")
    second = reviewed(scene, tag="second")
    archive(scene, first)
    everything = scene.service.list_practices()
    assert everything.total == 2 and {x.status for x in everything.items} == {"active", "archived"}
    active = scene.service.list_practices(status="active")
    assert active.total == 1 and active.items[0].practice_set_id == second.practice_set_id
    archived = scene.service.list_practices(status="archived")
    assert archived.total == 1 and archived.items[0].practice_set_id == first.practice_set_id
    assert archived.items[0].current_revision.practice_revision_id == first.current_revision.practice_revision_id
    with pytest.raises(AppError) as error:
        scene.service.list_practices(status="bogus")
    assert error.value.code == "PRACTICE_INVALID"


async def test_archive_restore_http_roundtrip_with_guards(tmp_path):
    """真实 HTTP：归档后五条写路径 409 PRACTICE_ARCHIVED，读取与恢复仍可用。"""
    with open_api_scene(tmp_path) as (app, client, settings):
        result = seed_api_loop(app, client)
        practice = result["practice"]
        set_id = practice["practiceSetId"]
        prefix = f"/api/v1/practice-sets/{set_id}"
        revision_id = practice["currentRevision"]["practiceRevisionId"]
        assert client.get(prefix).json()["status"] == "active"
        # 乐观锁冲突先于归档生效。
        stale = client.post(prefix + "/archive", json={"expectedRevision": practice["revision"] + 5})
        assert stale.status_code == 409 and stale.json()["code"] == "REVISION_CONFLICT"
        archived = client.post(prefix + "/archive", json={"expectedRevision": practice["revision"]})
        assert archived.status_code == 200, archived.text
        body = archived.json()
        assert body["status"] == "archived" and body["revision"] == practice["revision"] + 1
        # 归档练习集仍可查看：列表/详情/修订不受影响。
        assert client.get(prefix).json()["status"] == "archived"
        assert client.get(prefix + f"/revisions/{revision_id}").status_code == 200
        assert any(x["practiceSetId"] == set_id for x in client.get("/api/v1/practice-sets").json()["items"])
        assert client.get("/api/v1/practice-sets", params={"status": "archived"}).json()["total"] == 1
        assert client.get("/api/v1/practice-sets", params={"status": "active"}).json()["total"] == 0
        # 五条写路径全部 409 PRACTICE_ARCHIVED。
        guards = [
            ("patch", prefix + "/draft", {"submissionId": "http-guard-draft", "expectedRevision": body["revision"], "items": [], "constraints": {"count": 1}}),
            ("post", prefix + "/review", {"submissionId": "http-guard-review", "expectedRevision": body["revision"]}),
            ("post", prefix + "/revisions", {"submissionId": "http-guard-copy", "sourceRevisionId": revision_id}),
            ("post", prefix + f"/revisions/{revision_id}/exports", {"submissionId": "http-guard-export", "variant": "student", "assessmentId": None}),
            ("post", prefix + f"/revisions/{revision_id}/assessments", {"submissionId": "http-guard-conversion", "title": "练习施测", "heldOn": "2026-10-02",
                "classIds": [result["classId"]], "participants": [{"studentId": result["studentId"], "classId": result["classId"], "attendance": "present", "attemptNo": 1}]}),
        ]
        for method, path, payload in guards:
            response = getattr(client, method)(path, json=payload)
            assert response.status_code == 409, (path, response.status_code, response.text)
            assert response.json()["code"] == "PRACTICE_ARCHIVED", path
        # 恢复后写路径重新可用（新建修订 201），status 查询参数回到 active。
        restored = client.post(prefix + "/restore", json={"expectedRevision": body["revision"]})
        assert restored.status_code == 200 and restored.json()["status"] == "active"
        assert client.get("/api/v1/practice-sets", params={"status": "active"}).json()["total"] == 1
        copied = client.post(prefix + "/revisions", json={"submissionId": "after-restore-copy", "sourceRevisionId": revision_id})
        assert copied.status_code == 201, copied.text
