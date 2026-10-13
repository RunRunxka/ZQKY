"""原卷彻底删除（DELETE /papers/{id}，R10-BE 拆开交叉引用）。

覆盖（真 HTTP API + 真教学库 + tmp_path 隔离）：

- 可删成功：无施测引用的原卷（含多版本草稿）物理删除，全部子表行消失；
- R10-BE：已确认修订**不再阻断**删除——修订链属原卷自身，同事务摘除
  ``immutable_paper_revisions_delete`` 与 ``freeze_paper_*_delete`` 后级联删除；
  兜底在删除后恢复（直连 DELETE 仍被拒）；
- 被施测引用 → 409 ``PAPER_IN_USE``（``details.counts.assessments`` 附施测数）：
  施测是成绩链锚点，先删施测再删原卷；
- 乐观锁 409 ``PAPER_REVISION_STALE``；
- 404（原卷不存在）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.assessments_support import AssessmentsHarness


@pytest.fixture()
def harness(tmp_path: Path):
    with AssessmentsHarness(tmp_path) as running:
        yield running


def test_delete_paper_with_draft_only_succeeds(harness: AssessmentsHarness) -> None:
    draft = harness.import_draft_paper(tag="pd1", title="误上传的草稿卷")
    paper_id = draft["paperId"]

    deleted = harness.client.delete(
        f"/api/v1/papers/{paper_id}", params={"expectedRevision": draft["revision"]}
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True, "paperId": paper_id}

    # 物理删除：主行与全部子表行都不存在
    assert harness.count("papers", "id = ?", (paper_id,)) == 0
    assert harness.count("paper_revisions", "paper_id = ?", (paper_id,)) == 0
    assert harness.count("paper_items") == 0
    assert harness.count("paper_source_blocks") == 0
    assert harness.count("paper_issues") == 0
    fetched = harness.client.get(f"/api/v1/papers/{paper_id}")
    assert fetched.status_code == 404


def test_delete_paper_removes_multiple_draft_versions(harness: AssessmentsHarness) -> None:
    """已确认修订触发 fork 的多版本场景改用：草稿 PATCH 多次仍只有一个修订；
    这里验证删除对"修订 + 子行"的整卷清理。"""
    draft = harness.import_draft_paper(tag="pd2", title="多块草稿卷")
    paper_id = draft["paperId"]
    # 草稿改名（revision 递增）
    patched = harness.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={"expectedRevision": draft["revision"], "title": "改名后的草稿卷"},
    )
    assert patched.status_code == 200, patched.text

    deleted = harness.client.delete(
        f"/api/v1/papers/{paper_id}", params={"expectedRevision": draft["revision"] + 1}
    )
    assert deleted.status_code == 200, deleted.text
    assert harness.count("papers", "id = ?", (paper_id,)) == 0
    assert harness.count("paper_revisions", "paper_id = ?", (paper_id,)) == 0
    assert harness.count("paper_items") == 0


def test_delete_paper_cascades_confirmed_revision_chain(harness: AssessmentsHarness) -> None:
    """R10-BE：无施测引用时，已确认修订随原卷级联删除（不再 409；无归档替代）。

    删除后兜底触发器必须恢复：对另一张已确认原卷修订的直连 DELETE 仍被拒。
    """
    confirmed = harness.create_confirmed_paper(tag="pd3")
    paper_id = confirmed.paper_id
    # 另一张已确认原卷：用于断言兜底触发器在删除后仍生效
    other = harness.create_confirmed_paper(tag="pd3-other")
    current = harness.client.get(f"/api/v1/papers/{paper_id}")
    assert current.status_code == 200
    revision = current.json()["revision"]
    revision_id = current.json()["currentRevisionId"]

    deleted = harness.client.delete(
        f"/api/v1/papers/{paper_id}", params={"expectedRevision": revision}
    )
    assert deleted.status_code == 200, deleted.text
    # 级联：原卷、修订、原文块/小题/知识点/处置问题全部消失（另一张卷不受影响）
    assert harness.count("papers", "id = ?", (paper_id,)) == 0
    assert harness.count("paper_revisions", "paper_id = ?", (paper_id,)) == 0
    assert harness.count("paper_items", "paper_revision_id = ?", (revision_id,)) == 0
    assert harness.count("paper_item_knowledge", "paper_revision_id = ?", (revision_id,)) == 0
    assert harness.count("paper_source_blocks", "paper_revision_id = ?", (revision_id,)) == 0

    # 兜底恢复：另一张已确认原卷仍不可直连删除（触发器逐字恢复）
    import sqlite3

    connection = sqlite3.connect(str(harness.db_path))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            connection.execute("DELETE FROM paper_revisions WHERE id = ?", (other.revision_id,))
    finally:
        connection.close()


def test_delete_paper_blocked_by_assessment_reference(harness: AssessmentsHarness) -> None:
    """任一 assessments.paper_revision_id 指向本卷修订 → 409 PAPER_IN_USE + 施测数。"""
    paper = harness.create_confirmed_paper(tag="pd4")
    klass = harness.create_class(code="C-pd4")
    student = harness.create_student(name="张三", student_no="0012", class_id=klass["id"])
    body = AssessmentsHarness.create_body(
        paper,
        submission_id="as-pd4",
        class_ids=[klass["id"]],
        participants=[AssessmentsHarness.participant(student["id"], klass["id"])],
    )
    created = harness.client.post("/api/v1/assessments", json=body)
    assert created.status_code == 201, created.text

    current = harness.client.get(f"/api/v1/papers/{paper.paper_id}")
    revision = current.json()["revision"]
    blocked = harness.client.delete(
        f"/api/v1/papers/{paper.paper_id}", params={"expectedRevision": revision}
    )
    assert blocked.status_code == 409, blocked.text
    payload = blocked.json()
    assert payload["code"] == "PAPER_IN_USE"
    assert payload["details"]["counts"]["assessments"] == 1
    # 零删除：原卷与施测都还在
    assert harness.count("papers", "id = ?", (paper.paper_id,)) == 1
    assert harness.count("assessments") == 1


def test_delete_paper_revision_conflict(harness: AssessmentsHarness) -> None:
    draft = harness.import_draft_paper(tag="pd5", title="冲突卷")
    paper_id = draft["paperId"]
    # PATCH 后 revision+1，用旧 revision 删除
    patched = harness.client.patch(
        f"/api/v1/papers/{paper_id}/draft",
        json={"expectedRevision": draft["revision"], "title": "改名"},
    )
    assert patched.status_code == 200, patched.text

    stale = harness.client.delete(
        f"/api/v1/papers/{paper_id}", params={"expectedRevision": draft["revision"]}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "PAPER_REVISION_STALE"
    assert stale.json()["details"]["currentRevision"] == draft["revision"] + 1


def test_delete_paper_not_found(harness: AssessmentsHarness) -> None:
    missing = harness.client.delete("/api/v1/papers/no-such-paper", params={"expectedRevision": 0})
    assert missing.status_code == 404
    assert missing.json()["code"] == "PAPER_NOT_FOUND"
