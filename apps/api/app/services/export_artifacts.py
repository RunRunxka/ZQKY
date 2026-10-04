"""Shared B4 managed artifact read/download. No export engine or rendering here."""
from __future__ import annotations

from typing import Any
from app.contracts.b4 import ExportArtifact
from app.core.exceptions import AppError


class ExportArtifactsService:
    def __init__(self, catalog: Any, *, assets: Any, file_assets: Any, owner_id: str = "local") -> None:
        self.catalog, self.assets, self.file_assets, self.owner_id = catalog, assets, file_assets, owner_id

    def get(self, artifact_id: str) -> ExportArtifact:
        with self.catalog.read_connection() as conn:
            row = conn.execute("""SELECT a.*,e.variant,e.assessment_id,j.state AS job_state FROM export_artifacts a
              JOIN practice_exports e ON e.id=a.export_id AND e.owner_id=a.owner_id AND e.practice_revision_id=a.practice_revision_id
              JOIN practice_revisions r ON r.id=a.practice_revision_id
              JOIN practice_sets s ON s.id=r.practice_set_id AND s.owner_id=a.owner_id
              JOIN workflow_jobs j ON j.id=e.job_id AND j.owner_id=e.owner_id
              WHERE a.id=? AND a.owner_id=? AND r.state='reviewed'""", (artifact_id, self.owner_id)).fetchone()
        if row is None:
            raise AppError("导出产物不存在。", code="EXPORT_ARTIFACT_NOT_FOUND", status_code=404)
        if row['job_state'] != 'succeeded':
            raise AppError("产物与任务终态不一致。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500)
        try:
            return ExportArtifact(artifactId=row['id'], exportId=row['export_id'], practiceRevisionId=row['practice_revision_id'],
                variant=row['variant'], assessmentId=row['assessment_id'], fileAssetId=row['file_asset_id'], filename=row['filename'],
                mediaType=row['media_type'], sha256=row['sha256'], byteSize=row['byte_size'],
                downloadUrl=f"/api/v1/export-artifacts/{row['id']}/download", createdAt=row['created_at'])
        except (ValueError, TypeError) as exc:
            raise AppError("导出产物记录损坏。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500) from exc

    def download(self, artifact_id: str) -> tuple[ExportArtifact, bytes]:
        artifact = self.get(artifact_id)
        asset = self.file_assets.get(artifact.file_asset_id)
        if asset is None or asset.owner_id != self.owner_id or asset.kind != 'export' or asset.sha256 != artifact.sha256 or asset.byte_size != artifact.byte_size or asset.media_type != artifact.media_type or asset.blob_key != f'blobs/{artifact.sha256}':
            raise AppError("导出产物与受管资产不一致。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500)
        data = self.assets.read(asset.blob_key)
        if len(data) != artifact.byte_size:
            raise AppError("导出产物大小不符。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500)
        return artifact, data
