"""原卷归档/恢复（误上传清理）的真实装配测试。

覆盖（真 HTTP API + 真教学库）：

- 未确认草稿可归档：归档后草稿编辑/确认被既有守卫拒绝（409 ``PAPER_NOT_EDITABLE``）；
- 已确认原卷可归档：默认列表仍可读、``status=active`` 过滤后隐藏；
- 归档原卷不能用于**新建施测/补录人次**（409 ``PAPER_ARCHIVED``）；恢复后可再用；
- 归档/恢复走 ``expectedRevision`` 乐观锁（旧 revision → 409 ``PAPER_REVISION_STALE``，
  冲突只改状态、不产生内容变化）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.papers import PAPER_ARCHIVED, PAPER_NOT_EDITABLE, PAPER_REVISION_STALE
from tests.assessments_support import (
    AssessmentsHarness,
    SAMPLE_TOTAL_UNITS,
    items_payload_from_json,
)


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


def _archive(harness: AssessmentsHarness, paper_id: str, revision: int):
    return harness.client.post(
        f"/api/v1/papers/{paper_id}/archive", json={"expectedRevision": revision}
    )


def _restore(harness: AssessmentsHarness, paper_id: str, revision: int):
    return harness.client.post(
        f"/api/v1/papers/{paper_id}/restore", json={"expectedRevision": revision}
    )


def test_archive_unconfirmed_draft_blocks_editing_until_restore(
    harness: AssessmentsHarness,
) -> None:
    draft = harness.import_draft_paper(tag="pa1", title="误上传的草稿卷")

    archived = _archive(harness, draft["paperId"], draft["revision"])
    assert archived.status_code == 200, archived.text
    body = archived.json()
    assert body["status"] == "archived"
    assert body["revision"] == draft["revision"] + 1

    # 归档后草稿编辑与确认都被既有守卫拒绝（内容零变化）
    content = harness.client.get(
        f"/api/v1/papers/{draft['paperId']}/revisions/{draft['paperRevisionId']}/content"
    ).json()
    patch = harness.client.patch(
        f"/api/v1/papers/{draft['paperId']}/draft",
        json={
            "expectedRevision": body["revision"],
            "items": items_payload_from_json(content["items"], knowledge={}),
        },
    )
    assert patch.status_code == 409, patch.text
    assert patch.json()["code"] == PAPER_NOT_EDITABLE

    confirmed = harness.client.post(
        f"/api/v1/papers/{draft['paperId']}/confirm",
        json={"expectedRevision": body["revision"], "submissionId": "confirm-archived"},
    )
    assert confirmed.status_code == 409, confirmed.text
    assert confirmed.json()["code"] == PAPER_NOT_EDITABLE

    # 恢复后可继续编辑（同一草稿修订仍在）
    restored = _restore(harness, draft["paperId"], body["revision"])
    assert restored.status_code == 200, restored.text
    reopened = restored.json()
    assert reopened["status"] == "active"
    patch_ok = harness.client.patch(
        f"/api/v1/papers/{draft['paperId']}/draft",
        json={
            "expectedRevision": reopened["revision"],
            "items": items_payload_from_json(content["items"], knowledge={}),
        },
    )
    assert patch_ok.status_code == 200, patch_ok.text


def test_archived_confirmed_paper_blocks_new_assessments(harness: AssessmentsHarness) -> None:
    paper = harness.create_confirmed_paper(tag="pa2")
    klass = harness.create_class(code="C-pa2")
    student = harness.create_student(name="张三", student_no="0012", class_id=klass["id"])
    current = harness.client.get(f"/api/v1/papers/{paper.paper_id}").json()

    archived = _archive(harness, paper.paper_id, current["revision"])
    assert archived.status_code == 200, archived.text
    revision = archived.json()["revision"]

    body = AssessmentsHarness.create_body(
        paper,
        submission_id="as-after-archive",
        class_ids=[klass["id"]],
        participants=[AssessmentsHarness.participant(student["id"], klass["id"])],
    )
    rejected = harness.client.post("/api/v1/assessments", json=body)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == PAPER_ARCHIVED
    assert harness.count("assessments") == 0

    # 归档仍可读：详情与 status=active 过滤（列表默认不过滤，仍能看到并恢复）
    detail = harness.client.get(f"/api/v1/papers/{paper.paper_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"
    active_only = harness.client.get("/api/v1/papers", params={"status": "active"})
    assert active_only.json()["total"] == 0
    archived_only = harness.client.get("/api/v1/papers", params={"status": "archived"})
    assert archived_only.json()["total"] == 1

    # 恢复后可创建施测
    restored = _restore(harness, paper.paper_id, revision)
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"
    ok = harness.client.post("/api/v1/assessments", json=body)
    assert ok.status_code == 201, ok.text
    assert ok.json()["assessment"]["paperRevisionId"] == paper.revision_id
    assert ok.json()["assessment"]["paperTitle"] == paper.title


def test_paper_archive_revision_conflict_and_missing(harness: AssessmentsHarness) -> None:
    draft = harness.import_draft_paper(tag="pa3", title="并发归档")

    stale = _archive(harness, draft["paperId"], draft["revision"] + 3)
    assert stale.status_code == 409
    assert stale.json()["code"] == PAPER_REVISION_STALE
    assert stale.json()["details"]["currentRevision"] == draft["revision"]
    # 冲突不改状态
    assert harness.client.get(f"/api/v1/papers/{draft['paperId']}").json()["status"] == "active"

    missing = _archive(harness, "missing-paper", 0)
    assert missing.status_code == 404


def test_paper_archive_twice_and_restore_and_revision_guards(harness: AssessmentsHarness) -> None:
    """重复归档/恢复：每次都是显式状态写入（幂等由 CAS 决定，不静默跳过）。"""
    draft = harness.import_draft_paper(tag="pa4", title="重复归档")
    first = _archive(harness, draft["paperId"], draft["revision"])
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "archived"

    # 已归档再归档（带新 revision）仍是合法写入：状态不变、revision 再 +1
    second = _archive(harness, draft["paperId"], first.json()["revision"])
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "archived"
    assert second.json()["revision"] == first.json()["revision"] + 1

    restored = _restore(harness, draft["paperId"], second.json()["revision"])
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "active"


def test_paper_archive_keeps_confirmed_revision_readable(harness: AssessmentsHarness) -> None:
    """归档只隐藏入口：已确认修订内容仍可读取（历史与既有施测不受影响）。"""
    paper = harness.create_confirmed_paper(tag="pa5")
    current = harness.client.get(f"/api/v1/papers/{paper.paper_id}").json()
    archived = _archive(harness, paper.paper_id, current["revision"])
    assert archived.status_code == 200, archived.text

    content = harness.client.get(
        f"/api/v1/papers/{paper.paper_id}/revisions/{paper.revision_id}/content"
    )
    assert content.status_code == 200, content.text
    assert content.json()["totalScoreUnits"] == SAMPLE_TOTAL_UNITS
