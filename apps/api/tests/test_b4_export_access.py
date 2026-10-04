"""Shared download boundary: completed fixed artifacts, owner isolation and real bytes."""
import pytest
from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.services.export_artifacts import ExportArtifactsService
from tests.practices_support import PracticesScene


async def completed_artifact(root):
    scene = await PracticesScene.create(root)
    question = scene.question()
    practice = scene.review(scene.save(scene.create_set(), [scene.item(question)]))
    receipt = await scene.export(practice)
    job = await scene.finish(receipt)
    assert job.state == "succeeded", job.error
    artifact = next(a for a in scene.service.list_exports(practice.practice_set_id,
        practice.current_revision.practice_revision_id).items if a.export_id == receipt.export_id)
    service = ExportArtifactsService(scene.catalog, assets=scene.assets,
        file_assets=FileAssetsRepository(scene.catalog))
    return scene, artifact, service


@pytest.mark.asyncio
async def test_shared_download_real_bytes_and_foreign_owner_hidden(tmp_path):
    scene, artifact, service = await completed_artifact(tmp_path)
    view, data = service.download(artifact.artifact_id)
    assert data[:2] == b"PK" and view == artifact
    foreign = ExportArtifactsService(scene.catalog, assets=scene.assets,
        file_assets=FileAssetsRepository(scene.catalog), owner_id="another-owner")
    with pytest.raises(AppError) as exc:
        foreign.download(artifact.artifact_id)
    assert exc.value.status_code == 404 and exc.value.code == "EXPORT_ARTIFACT_NOT_FOUND"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.export_artifacts import router
    app = FastAPI()
    app.state.export_artifacts_service = service
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as client:
        response = client.get(view.download_url)
        assert response.status_code == 200 and response.content == data
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-disposition"].startswith("attachment; filename*=UTF-8''")
        assert "\r" not in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_completed_artifact_rejects_inconsistent_job_and_corrupt_managed_blob(tmp_path):
    scene, artifact, service = await completed_artifact(tmp_path)
    with scene.catalog.write_transaction() as conn:
        job_id = conn.execute("SELECT job_id FROM practice_exports WHERE id=?", (artifact.export_id,)).fetchone()[0]
        conn.execute("UPDATE workflow_jobs SET state='failed' WHERE id=?", (job_id,))
    with pytest.raises(AppError) as exc:
        service.get(artifact.artifact_id)
    assert exc.value.code == "EXPORT_ARTIFACT_CORRUPT"
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE workflow_jobs SET state='succeeded' WHERE id=?", (job_id,))
    asset = scene.service.file_assets.get(artifact.file_asset_id)
    blob = scene.assets.root / asset.blob_key
    original = blob.read_bytes()
    blob.write_bytes(b"!" + original[1:])
    with pytest.raises(AppError):
        service.download(artifact.artifact_id)
