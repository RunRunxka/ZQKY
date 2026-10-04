"""Independent B5 storage oracles; no sockets, credentials or formal data.

Four-catalog setup is reused, while assertions and command packages are authored
for this review. They do not call a production merge function to build expected
documents. All roots are supplied by the isolated pytest runner.
"""
import copy
import sqlite3

import pytest

from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from app.core.lesson_schema_gate import verify_registered_lesson_schema
from app.core.migrations import applied_migrations
from tests.lesson_plans_support import LessonScene


@pytest.fixture
async def scene(tmp_path):
    value = await LessonScene.create(tmp_path)
    try:
        yield value
    finally:
        await value.close()


async def test_selective_apply_terminates_without_touching_unselected_fields(scene):
    base = scene.be.get_lesson("lesson")
    before = copy.deepcopy(base["currentRevision"]["data"])
    proposal, _ = await scene.proposal(submission="rv-independent-generate")
    body = lp.LessonApplyRequest(submissionId="rv-independent-apply", expectedRevision=base["revision"],
        baseRevisionId=base["currentRevisionId"], selectedFields=["teachingDesign"])
    result = await scene.be.apply_proposal("lesson", proposal["proposalId"], body)
    expected = copy.deepcopy(before)
    expected["teachingDesign"] = proposal["patch"]["teachingDesign"]
    assert result["currentRevision"]["data"] == expected
    assert result["currentRevision"]["processMetadata"] == []
    assert result["revision"] == base["revision"] + 1
    assert scene.be.get_revision("lesson", base["currentRevisionId"])["data"] == before
    with pytest.raises(AppError) as caught:
        await scene.be.apply_proposal("lesson", proposal["proposalId"], body.model_copy(update={"submission_id":"rv-second", "selected_fields":["process"]}))
    assert caught.value.code == "LESSON_PROPOSAL_TERMINATED"


def test_original_receipt_is_fixed_and_cannot_rewind_after_later_context(scene):
    first = scene.be.create_lesson(scene.create_request(submission="rv-create", context=scene.context(("k1",))))
    first_body = copy.deepcopy(first["currentRevision"]["data"])
    first_body["title"] = "独立教师标题"
    command = lp.LessonSaveRequest(submissionId="rv-save-original", expectedRevision=first["revision"],
        data=first_body, context=scene.context(("k1",)), source="manual")
    saved = scene.be.save_draft(first["lessonPlanId"], command)
    later_body = copy.deepcopy(first_body)
    later_body["reflection"] = "后来教师反思"
    later = scene.be.save_draft(first["lessonPlanId"], lp.LessonSaveRequest(submissionId="rv-save-later",
        expectedRevision=saved["revision"], data=later_body, context=scene.context(("k2",)), source="rule"))
    replay = scene.be.save_draft(first["lessonPlanId"], command)
    assert replay == {**saved, "replayed":True}
    assert scene.be.get_lesson(first["lessonPlanId"])["currentRevisionId"] == later["currentRevisionId"]
    assert scene.be.get_revision(first["lessonPlanId"], saved["currentRevisionId"])["data"] == first_body
    with pytest.raises(AppError) as caught:
        scene.be.save_draft(first["lessonPlanId"], command.model_copy(update={"source":"rule"}))
    assert caught.value.code == "SUBMISSION_CONFLICT"


def test_failed_receipt_rolls_back_revision_and_history_pointer(scene):
    base = scene.be.create_lesson(scene.create_request(submission="rv-rollback-create"))
    lid = base["lessonPlanId"]
    before = scene.be.list_revisions(lid)
    with scene.catalog.write_transaction() as conn:
        conn.execute("""CREATE TRIGGER rv_fail_receipt BEFORE INSERT ON command_submissions
            WHEN NEW.submission_id='rv-failed-receipt' BEGIN SELECT RAISE(ABORT,'rv-injected'); END""")
    data = copy.deepcopy(base["currentRevision"]["data"])
    data["exercises"] = "这次事务应整体回滚"
    with pytest.raises(sqlite3.IntegrityError):
        scene.be.save_draft(lid, lp.LessonSaveRequest(submissionId="rv-failed-receipt", expectedRevision=base["revision"],
            data=data, context=None, source="manual"))
    assert scene.be.get_lesson(lid) == base
    assert scene.be.list_revisions(lid) == before
    with scene.catalog.read_connection() as conn:
        assert conn.execute("SELECT count(*) FROM command_submissions WHERE submission_id='rv-failed-receipt'").fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_metadata_context_and_schema_remain_fixed(scene):
    created = scene.be.create_lesson(scene.create_request(submission="rv-context", context=scene.context(("k2","k1"))))
    with scene.catalog.read_connection() as conn:
        registered = dict(applied_migrations(conn))
        verify_registered_lesson_schema(conn)
    same = scene.be.save_draft(created["lessonPlanId"], lp.LessonSaveRequest(submissionId="rv-context-same",
        expectedRevision=created["revision"], data=created["currentRevision"]["data"], context=scene.context(("k2","k1")), source="manual"))
    assert same["revision"] == created["revision"]
    assert same["currentRevisionId"] == created["currentRevisionId"]
    changed = scene.be.save_draft(created["lessonPlanId"], lp.LessonSaveRequest(submissionId="rv-context-order",
        expectedRevision=same["revision"], data=created["currentRevision"]["data"], context=scene.context(("k1","k2")), source="manual"))
    assert changed["revision"] == same["revision"] + 1
    assert changed["currentRevision"]["data"] == created["currentRevision"]["data"]
    assert changed["currentRevision"]["contentHash"] != created["currentRevision"]["contentHash"]
    with scene.catalog.read_connection() as conn:
        assert dict(applied_migrations(conn)) == registered
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

