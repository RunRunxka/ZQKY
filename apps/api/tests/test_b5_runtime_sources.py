"""CTRL integration: actual startup wiring and owner-scoped immutable selectors."""
from contextlib import closing
from app.core.sqlite import open_readonly
from app.contracts.teaching_loop import canonical_hash
from tests.practices_support import open_api_scene


def question(app, text, *, owner=None, subject="math"):
    content = dict(type="short_answer", stemMarkdown=text, options=[], assetIds=[], answer=None,
                   explanationMarkdown=None, richContent=None)
    with app.state.question_bank.write_transaction() as conn:
        return app.state.question_bank.insert_question_in(conn,
            owner_id=owner or app.state.question_bank_service.owner_id, content=content,
            metadata=dict(subjectId=subject, difficulty="easy"), answer_state="not_provided",
            content_fingerprint=canonical_hash(content), source_spans=[], import_id=None, knowledge_links=[])


def test_standard_runtime_has_real_lesson_services_registry_and_routes(tmp_path):
    with open_api_scene(tmp_path / "runtime") as (app, client, settings):
        assert settings.credentials_file is None
        service = app.state.lesson_plan_service
        generation = app.state.lesson_generation_service
        assert service.catalog is app.state.teaching
        assert service.generation is generation
        assert generation.evidence is app.state.rag_v2
        assert generation.questions is app.state.fixed_question_reader
        assert generation.practices is app.state.practice_service
        assert generation.question_owner_id == app.state.question_bank_service.owner_id
        spec = app.state.job_executors.spec_for("teaching", "lesson_generation")
        assert spec.uses_model is True and spec.factory == generation.executor_for
        response = client.get("/api/v1/lesson-plans")
        assert response.status_code == 200
        assert response.json() == dict(items=[], total=0, offset=0, limit=50)
        paths = app.openapi()["paths"]
        assert "/api/v1/lesson-plans/{lesson_id}/proposals/{proposal_id}/apply" in paths
        assert "/api/v1/confirmed-question-revisions" in paths


def test_http_selector_returns_owned_real_revisions_and_preserves_rows(tmp_path):
    with open_api_scene(tmp_path / "sources") as (app, client, _):
        owned = [question(app, text) for text in ("固定题甲", "固定题乙", "固定题丙")]
        foreign = question(app, "另一个归属不得显示", owner="other-owner")
        archived = question(app, "已归档不得显示")
        question(app, "不同学科不得显示", subject="chinese")
        with app.state.question_bank.write_transaction() as conn:
            conn.execute("UPDATE questions SET status='archived' WHERE id=?", (archived.question_id,))
        with closing(open_readonly(app.state.question_bank.db_path)) as conn:
            before = [tuple(row) for row in conn.execute("SELECT * FROM questions ORDER BY id")]
            revisions = [tuple(row) for row in conn.execute("SELECT * FROM question_revisions ORDER BY id")]
        items = []
        for offset in (0, 2):
            response = client.get("/api/v1/confirmed-question-revisions", params=dict(subjectId="math", offset=offset, limit=2))
            assert response.status_code == 200, response.text
            page = response.json()
            assert (page["total"], page["offset"], page["limit"]) == (3, offset, 2)
            items.extend(page["items"])
        assert {item["questionRevisionId"] for item in items} == {item.current_revision_id for item in owned}
        assert {item["questionId"] for item in items} == {item.question_id for item in owned}
        assert foreign.current_revision_id not in str(items)
        assert {item["stemMarkdown"] for item in items} == {"固定题甲", "固定题乙", "固定题丙"}
        assert all(set(item) == {"questionId", "questionRevisionId", "subjectId", "stemMarkdown"} for item in items)
        for params in (dict(subjectId=" math"), dict(subjectId="math", limit=201), dict(subjectId="math", offset=-1)):
            assert client.get("/api/v1/confirmed-question-revisions", params=params).status_code == 422
        empty = client.get("/api/v1/confirmed-question-revisions", params=dict(subjectId="unknown"))
        assert empty.status_code == 200 and empty.json()["items"] == []
        with closing(open_readonly(app.state.question_bank.db_path)) as conn:
            assert [tuple(row) for row in conn.execute("SELECT * FROM questions ORDER BY id")] == before
            assert [tuple(row) for row in conn.execute("SELECT * FROM question_revisions ORDER BY id")] == revisions
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_missing_selector_dependency_reports_unavailable_instead_of_empty(tmp_path):
    with open_api_scene(tmp_path / "unavailable") as (app, client, _):
        app.state.fixed_question_reader = None
        response = client.get("/api/v1/confirmed-question-revisions", params=dict(subjectId="math"))
        assert response.status_code == 503
        assert response.json()["code"] == "SERVICE_UNAVAILABLE"
