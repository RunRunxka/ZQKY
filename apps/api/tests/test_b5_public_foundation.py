"""CTRL-owned production readers and version-aware B5 startup structure."""
import copy

import pytest

from app.core.database_gate import DatabaseExpectation, verify_existing_database
from app.core.exceptions import AppError
from app.core.lesson_schema_gate import verify_registered_lesson_schema
from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations, applied_migrations
from app.core.sqlite import connect, transaction
from app.repositories.teaching.schema import REQUIRED_TABLES
from tests.practices_support import PracticesScene
from tests.test_rag_v2_support import RagEnv, textbook_text


def test_populated_b4_gate_accepts_then_appends_b5_without_old_hash_drift(tmp_path, monkeypatch):
    path = tmp_path / "teaching.sqlite3"
    connection = connect(path)
    registered = REGISTERED_MIGRATIONS["teaching"]
    # 0010（B5）及其后追加的迁移一律视为"本次升级范围"；老散列逐条对比不变
    b5_plus = tuple(m for m in registered if m.id == "0010" or m.id > "0010")
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", tuple(m for m in registered if m not in b5_plus))
        apply_migrations(connection, database="teaching")
        with transaction(connection, immediate=True):
            connection.execute("INSERT INTO classes(id,code,name,school_year,grade_id) VALUES('retained','OLD','保留班','2026','grade-8')")
        old_hashes = dict(applied_migrations(connection))
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", registered)
        verify_existing_database(DatabaseExpectation(path, "teaching", REQUIRED_TABLES))
        assert all(m.id not in applied_migrations(connection) for m in b5_plus)
        assert apply_migrations(connection, database="teaching") == [m.id for m in b5_plus]
        assert apply_migrations(connection, database="teaching") == []
        assert all(applied_migrations(connection)[key] == sha for key, sha in old_hashes.items())
        assert connection.execute("SELECT name FROM classes WHERE id='retained'").fetchone()[0] == "保留班"
        verify_registered_lesson_schema(connection)
        verify_existing_database(DatabaseExpectation(path, "teaching", REQUIRED_TABLES))
    finally:
        connection.close()


@pytest.mark.parametrize("sql", [
    "DROP TRIGGER lesson_revision_sequence",
    "DROP INDEX ix_lesson_owner_updated",
    "DROP TABLE lesson_proposal_decisions",
])
def test_registered_b5_missing_structure_fails_closed(tmp_path, sql):
    path = tmp_path / "teaching.sqlite3"
    connection = connect(path)
    try:
        apply_migrations(connection, database="teaching")
        verify_registered_lesson_schema(connection)
        connection.execute(sql)
        with pytest.raises(AppError) as caught:
            verify_registered_lesson_schema(connection)
        assert caught.value.code == "DATABASE_SCHEMA_INCOMPLETE"
        assert applied_migrations(connection)["0010"] == next(m for m in REGISTERED_MIGRATIONS["teaching"] if m.id == "0010").sha256
    finally:
        connection.close()


async def test_selected_evidence_uses_production_original_scope_and_ref_validation(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="真实封存示例教材", text=textbook_text())
    service = env.make_service()
    try:
        chunk = document.first_body_chunk()
        span = dict(documentRevisionId=document.revision_id, charStart=chunk.char_start, charEnd=chunk.char_end)
        selected = service.prepare_selected_evidence(env.selection(document), [span])
        raw = document.normalized_text
        assert selected.evidence[0].text == raw[chunk.char_start:chunk.char_end]
        assert selected.evidence[0].readable is not None
        assert selected.evidence[0].locator.kind == "markdown"
        rebuilt = service.verify_selected_evidence(selected.scope_snapshot, selected.evidence_refs)
        assert rebuilt == selected.evidence
        tampered = selected.evidence_refs[0].model_dump()
        tampered["normalizedTextSha256"] = "0" * 64
        with pytest.raises(AppError) as caught:
            service.verify_selected_evidence(selected.scope_snapshot, [tampered])
        assert caught.value.code == "RAG_EVIDENCE_UNAVAILABLE"
        changed = selected.scope_snapshot.model_dump()
        changed["scopeHash"] = "0" * 64
        with pytest.raises(AppError) as caught:
            service.verify_selected_evidence(changed, selected.evidence_refs)
        assert caught.value.code == "RAG_SCOPE_CHANGED"
        with pytest.raises(AppError) as caught:
            service.verify_selected_evidence(selected.scope_snapshot, [dict(tampered, charStart=True)])
        assert caught.value.status_code == 422
    finally:
        await service.close()
        env.catalog.close()


async def test_selected_evidence_rejects_exercise_region_and_duplicate_spans(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="区间教材", text=textbook_text())
    service = env.make_service()
    try:
        chunk = document.first_body_chunk()
        span = dict(documentRevisionId=document.revision_id, charStart=chunk.char_start, charEnd=chunk.char_end)
        with pytest.raises(AppError) as caught:
            service.prepare_selected_evidence(env.selection(document), [span, span])
        assert caught.value.status_code == 422
        exercise = next(item for item in document.chunks if item.region != "body")
        with pytest.raises(AppError) as caught:
            service.prepare_selected_evidence(env.selection(document), [dict(documentRevisionId=document.revision_id, charStart=exercise.char_start, charEnd=exercise.char_end)])
        assert caught.value.code == "RAG_EVIDENCE_UNAVAILABLE"
    finally:
        await service.close()
        env.catalog.close()


async def test_read_reviewed_revision_is_fixed_owner_scoped_and_does_not_touch_current(tmp_path):
    scene = await PracticesScene.create(tmp_path)
    try:
        draft = scene.save(scene.create_set(), [scene.item(scene.question())])
        rid = draft.current_revision.practice_revision_id
        with pytest.raises(AppError) as caught:
            scene.service.read_reviewed_revision(rid)
        assert caught.value.status_code == 422
        reviewed = scene.review(draft)
        frozen = copy.deepcopy(reviewed.current_revision.model_dump(by_alias=True))
        result = scene.service.read_reviewed_revision(rid, owner_id="local")
        assert result.model_dump(by_alias=True) == frozen
        for owner, revision_id in (("foreign", rid), ("local", "missing")):
            with pytest.raises(AppError) as caught:
                scene.service.read_reviewed_revision(revision_id, owner_id=owner)
            assert (caught.value.code, caught.value.status_code) == ("NOT_FOUND", 404)
        assert scene.service.owner_id == "local"
        assert scene.service.get_practice(reviewed.practice_set_id).current_revision.model_dump(by_alias=True) == frozen
        scene.integrity()
    finally:
        for catalog in (scene.catalog, scene.knowledge, scene.questions, scene.textbooks):
            catalog.close()


@pytest.mark.parametrize("old,new", [
    ("'ai_applied'", "'AI_APPLIED'"),
    ("'$.subjectId'", "'$.subjectid'"),
])
def test_b5_gate_rejects_semantic_literal_mutation_despite_registered_hash_and_valid_fk(tmp_path, old, new):
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        registered = dict(applied_migrations(connection))
        original = connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name='lesson_revision_sequence'").fetchone()[0]
        assert old in original
        connection.execute("DROP TRIGGER lesson_revision_sequence")
        connection.execute(original.replace(old, new))
        assert dict(applied_migrations(connection)) == registered
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(AppError) as caught:
            verify_registered_lesson_schema(connection)
        assert caught.value.code == "DATABASE_SCHEMA_INCOMPLETE"
    finally:
        connection.close()
