"""CTRL offline four-DB recovery with real saved/applied/rejected lesson rows."""
import hashlib
import json
import shutil
from contextlib import closing

from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.secrets import SecretStore
from app.contracts import lesson_plans as lp
from app.core.lesson_schema_gate import verify_registered_lesson_schema
from app.core.migrations import REGISTERED_MIGRATIONS, applied_migrations
from app.core.sqlite import connect, open_readonly
from app.repositories.vector_store.base import point_id_for
from tests.lesson_plans_support import LessonScene
from tests.test_backup_restore import backup, FakeQdrantServer


LESSON_TABLES = ("lesson_plans", "lesson_plan_revisions", "lesson_revision_reviews",
                 "lesson_generation_inputs", "lesson_ai_proposals", "lesson_proposal_decisions")


def rows(path):
    with closing(open_readonly(path)) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: sorted([tuple(row) for row in conn.execute('SELECT * FROM "'+name+'"')], key=repr) for name in names}


def clone(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    with closing(open_readonly(source)) as original, closing(connect(target)) as destination:
        original.backup(destination)
        assert destination.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert destination.execute("PRAGMA foreign_key_check").fetchall() == []


async def test_full_offline_backup_restores_all_six_populated_b5_tables_assets_and_fixed_refs(tmp_path):
    scene = await LessonScene.create(tmp_path / "source-fixture")
    admin = None
    try:
        created = scene.be.create_lesson(scene.create_request(context=scene.context(), submission="backup-create"))
        proposal, _ = await scene.proposal(created, submission="backup-generate-1")
        applied = await scene.be.apply_proposal(created["lessonPlanId"], proposal["proposalId"],
            scene.apply_request(proposal, fields=("process", "teachingDesign"), submission="backup-apply"))
        assert applied["revision"] == created["revision"] + 1
        for field in ("title", "totalLessons", "currentLessonNo", "lessonTypes", "otherTypeText", "reflection"):
            assert applied["currentRevision"]["data"][field] == created["currentRevision"]["data"][field]
        second, _ = await scene.proposal(applied, submission="backup-generate-2")
        rejected = scene.be.reject_proposal(applied["lessonPlanId"], second["proposalId"], lp.LessonRejectRequest(submissionId="backup-reject"))
        assert rejected["state"] == "rejected"
        await scene.engine.shutdown()
        await scene.ai.engine.shutdown()

        root = tmp_path / "canonical-data"
        source_catalogs = dict(teaching=scene.catalog, knowledge=scene.ai.practice_scene.knowledge,
                               questions=scene.ai.practice_scene.questions, textbooks=scene.ai.rag_env.catalog)
        relative = dict(teaching="teaching/teaching.sqlite3", knowledge="knowledge/knowledge.sqlite3",
                        questions="question-bank/question-bank.sqlite3", textbooks="textbooks/catalog.sqlite3")
        for key, catalog in source_catalogs.items():
            clone(catalog.db_path, root / relative[key])
        for area in ("blobs", "normalized", "staging"):
            shutil.copytree(scene.ai.rag_env.settings.textbooks_root / area, root / "textbooks" / area)
        shutil.copytree(scene.ai.root / "assets", root / "assets")
        (root / "question-bank" / "blobs").mkdir()
        before = {key: rows(root / path) for key, path in relative.items()}
        assert all(before["teaching"][table] for table in LESSON_TABLES)
        with closing(open_readonly(root / relative["teaching"])) as conn:
            old_hashes = {key: value for key, value in applied_migrations(conn).items() if key not in ("0010", "0011_analysis_runs_archived_at")}
            assert len(old_hashes) == 9
            verify_registered_lesson_schema(conn)
            assert applied_migrations(conn)["0010"] == next(m for m in REGISTERED_MIGRATIONS["teaching"] if m.id == "0010").sha256
            assets = [dict(row) for row in conn.execute("SELECT blob_key,sha256,byte_size FROM file_assets")]
        for asset in assets:
            data = (root / "assets" / asset["blob_key"]).read_bytes()
            assert len(data) == asset["byte_size"] and hashlib.sha256(data).hexdigest() == asset["sha256"]

        server = FakeQdrantServer()
        rag = scene.ai.rag_env
        points = {}
        for record in rag.catalog.list_generation_revisions(rag.generation.generation_id):
            for chunk in rag.catalog.list_chunks(record.chunk_set_id):
                points[point_id_for(rag.generation.generation_id, record.chunk_set_id, chunk.ordinal, chunk.text_sha256)] = dict(
                    document_revision_id=record.document_revision_id, chunk_set_id=record.chunk_set_id,
                    ordinal=chunk.ordinal, text_sha256=chunk.text_sha256)
        server.ensure_collection(rag.collection, dimensions=rag.embeddings.dimensions, distance="Cosine")
        server.set_points(rag.collection, points)
        admin = backup.QdrantAdmin("http://127.0.0.1:16333", transport=server.transport())
        archive, restored = tmp_path / "backup-new", tmp_path / "restored-new"
        manifest = backup.create_backup(data_dir=root, target=archive, label="B5-six-tables-real-rows", qdrant_client=admin)
        assert manifest["status"] == "complete", manifest
        failures, _ = backup.verify_backup(archive, qdrant_client=admin)
        assert failures == []
        state = backup.restore_backup(archive, restored, isolated_qdrant=admin)
        assert state["status"] == "ready"
        after = {key: rows(restored / path) for key, path in relative.items()}
        assert after["teaching"] == before["teaching"]
        assert after["knowledge"] == before["knowledge"]
        assert after["questions"] == before["questions"]
        for table in ("document_revisions", "documents", "chunks", "generation_revisions"):
            assert after["textbooks"][table] == before["textbooks"][table]
        for key, path in relative.items():
            with closing(open_readonly(restored / path)) as conn:
                assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
                if key == "teaching":
                    verify_registered_lesson_schema(conn)
                    assert {k: v for k, v in applied_migrations(conn).items() if k not in ("0010", "0011_analysis_runs_archived_at")} == old_hashes
        for asset in assets:
            assert (restored / "assets" / asset["blob_key"]).read_bytes() == (root / "assets" / asset["blob_key"]).read_bytes()
        from app.main import create_app
        settings = Settings(host="127.0.0.1", port=8001, allowed_origins=frozenset(), env="test", data_dir=restored,
                            credentials_file=None, textbook_source_dir=tmp_path / "empty-books",
                            qdrant_url="http://127.0.0.1:16333", embedding_base_url="http://127.0.0.1:9")
        settings.textbook_source_dir.mkdir()
        app = create_app(settings, secret_store=SecretStore())
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            response = client.get("/api/v1/lesson-plans/" + applied["lessonPlanId"])
            assert response.status_code == 200 and response.json() == applied
            assert app.state.job_executors.has("teaching", "lesson_generation")
            evidence = app.state.rag_v2.verify_selected_evidence(scene.body.scope_snapshot, scene.body.evidence_refs)
            assert evidence == scene.ai.verified.evidence
        proof = dict(catalogs=relative, newTableRows={table: len(after["teaching"][table]) for table in LESSON_TABLES},
                     oldMigrationHashes=old_hashes, managedAssets=assets, vectorPointCount=len(points), restoreStatus=state["status"],
                     fixtureScope="isolated real catalogs/services/providers with declared MockTransport and embeddings",
                     formalDataTouched=False, samplesRetained=True)
        (tmp_path / "B5-RECOVERY-PROOF.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    finally:
        # QdrantAdmin opens/closes a bounded HTTP client inside each call.
        await scene.close()
