"""Shared B4 managed artifact read/download. No export engine or rendering here.

R6 适配（学情分析报告产物）：归档把导出产物元数据落 ``export_artifacts`` 表，但该表
被 ``FOREIGN KEY(export_id,owner_id) → practice_exports(id,owner_id)`` 表级外键锁死，
``practice_exports`` 行又被 ``export_source`` 触发器锁死在「已 reviewed 的练习修订」上
——学情分析报告没有练习链路（练习域归后续批次），不伪造练习占位行。R6 分析报告产物
改为**纯受管资产**形态：``file_assets``（kind='export'，内容寻址 blob、指纹/大小/
media_type/原名齐备），``artifactId`` = 资产 id。

读取分派（``get``）：

- ``export_artifacts`` 表命中 → 练习产物：保持归档语义逐字不变（JOIN
  practice_exports/practice_revisions/workflow_jobs，任务必须 succeeded）；
- 表未命中且 ``file_assets`` 命中同 id 的 kind='export' 资产 → 分析报告产物：
  核对资产与 blob 一致后返回练习契约形状（``variant`` 落 ``'student'`` 占位、
  ``assessmentId``/``exportId`` 落产物自身标识；下载端点与前端只消费
  ``artifactId``/``filename``/``mediaType``/字节，无语义依赖）；
- 都未命中 → 404。

下载路径对两类产物共用同一受管资产核对（kind='export'、指纹/大小/media_type/键一致）。
"""
from __future__ import annotations

from typing import Any
from app.contracts.b4 import ExportArtifact
from app.core.exceptions import AppError

ANALYSIS_REPORT_MEDIA_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


class ExportArtifactsService:
    def __init__(self, catalog: Any, *, assets: Any, file_assets: Any, owner_id: str = "local") -> None:
        self.catalog, self.assets, self.file_assets, self.owner_id = catalog, assets, file_assets, owner_id

    def get(self, artifact_id: str) -> ExportArtifact:
        with self.catalog.read_connection() as conn:
            row = conn.execute("SELECT * FROM export_artifacts WHERE id=? AND owner_id=?",
                               (artifact_id, self.owner_id)).fetchone()
        if row is not None:
            return self._get_practice_export(artifact_id, row)
        return self._get_analysis_report_asset(artifact_id)

    def _get_practice_export(self, artifact_id: str, row: Any) -> ExportArtifact:
        with self.catalog.read_connection() as conn:
            joined = conn.execute("""SELECT a.*,e.variant,e.assessment_id,j.state AS job_state FROM export_artifacts a
              JOIN practice_exports e ON e.id=a.export_id AND e.owner_id=a.owner_id AND e.practice_revision_id=a.practice_revision_id
              JOIN practice_revisions r ON r.id=a.practice_revision_id
              JOIN practice_sets s ON s.id=r.practice_set_id AND s.owner_id=a.owner_id
              JOIN workflow_jobs j ON j.id=e.job_id AND j.owner_id=e.owner_id
              WHERE a.id=? AND a.owner_id=? AND r.state='reviewed'""", (artifact_id, self.owner_id)).fetchone()
        if joined is None:
            raise AppError("导出产物不存在。", code="EXPORT_ARTIFACT_NOT_FOUND", status_code=404)
        if joined['job_state'] != 'succeeded':
            raise AppError("产物与任务终态不一致。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500)
        try:
            return ExportArtifact(artifactId=joined['id'], exportId=joined['export_id'], practiceRevisionId=joined['practice_revision_id'],
                variant=joined['variant'], assessmentId=joined['assessment_id'], fileAssetId=joined['file_asset_id'], filename=joined['filename'],
                mediaType=joined['media_type'], sha256=joined['sha256'], byteSize=joined['byte_size'],
                downloadUrl=f"/api/v1/export-artifacts/{joined['id']}/download", createdAt=joined['created_at'])
        except (ValueError, TypeError) as exc:
            raise AppError("导出产物记录损坏。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500) from exc

    def _get_analysis_report_asset(self, artifact_id: str) -> ExportArtifact:
        """分析报告产物视图：``artifactId`` = ``file_assets`` 行（kind='export'）。

        核对同 owner + kind + 内容寻址键一致；无任务行可核（同步产物，无任务）。
        ``variant``/``exportId``/``practiceRevisionId`` 是练习契约的必填字段，分析报告
        无练习语义：``variant`` 落 ``'student'`` 占位、``exportId`` 落资产 id、
        ``practiceRevisionId`` 落空串形状值（前端与下载端点均不消费）。
        """
        asset = self.file_assets.get(artifact_id)
        if asset is None or asset.owner_id != self.owner_id or asset.kind != "export":
            raise AppError("导出产物不存在。", code="EXPORT_ARTIFACT_NOT_FOUND", status_code=404)
        if asset.blob_key != f"blobs/{asset.sha256}":
            raise AppError("导出产物与受管资产不一致。", code="EXPORT_ARTIFACT_CORRUPT", status_code=500)
        try:
            return ExportArtifact(artifactId=asset.asset_id, exportId=asset.asset_id, practiceRevisionId="",
                variant='student', assessmentId=None, fileAssetId=asset.asset_id, filename=asset.original_name,
                mediaType=asset.media_type, sha256=asset.sha256, byteSize=asset.byte_size,
                downloadUrl=f"/api/v1/export-artifacts/{asset.asset_id}/download", createdAt=asset.created_at)
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
