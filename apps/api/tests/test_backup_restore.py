"""备份 / 校验 / 恢复：离线一致性、内容寻址、隔离恢复与应用可读性。

全部在 pytest ``tmp_path`` 内构造真实布局（教材目录 + 题库 + 知识点库 + 教学库 +
受管资产 + staging 草稿产物），Qdrant 用 ``httpx.MockTransport`` 上的最小 REST 替身，
走**真实的** ``QdrantAdmin`` HTTP 代码路径；不连接正式 6333，也不读写正式 ``.local-data``。

v3 起备份覆盖四库与 ``assets/blobs``；v2（两库）与 legacy（无版本/1）清单一律手工构造，
只读兼容语义由专门用例锁定。
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.core.config import Settings
from app.core.data_lock import acquire_data_lock, require_data_root_ready, restore_state
from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.question_bank.catalog import QuestionBankCatalog
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.vector_store import InMemoryVectorStore
from app.repositories.vector_store.base import point_id_for
from app.services.assets.store import AssetStore
from app.services.document_parsing import chunk_document, parse_document
from app.services.question_bank.service import QuestionBankService
from app.services.textbook_ingest import IngestService
from tests.test_textbook_ingest import DIMENSIONS, METADATA, Harness, sample_text

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "rag" / "backup.py"


def _load_backup_module():
    spec = importlib.util.spec_from_file_location("zqky_rag_backup", BACKUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclass 需要模块在 sys.modules 里可见（importlib 官方配方）
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backup = _load_backup_module()


# --------------------------------------------------------------------------- Qdrant 替身


class FakeQdrantServer:
    """最小 Qdrant REST 替身：快照 / 计数 / scroll / 上传恢复。

    只实现备份与恢复实际用到的官方路径；用于在无容器、无网络的条件下覆盖真实
    ``QdrantAdmin`` 的请求与错误处理。
    """

    def __init__(self) -> None:
        self.collections: dict[str, dict] = {}
        self.snapshots: dict[tuple[str, str], bytes] = {}
        self.offline = False
        self.fail_upload = False
        self.deleted_snapshots: list[str] = []
        self.uploaded_collections: list[str] = []
        self._counter = 0

    # -------------------------------------------------------------- 数据准备

    def ensure_collection(self, name: str, *, dimensions: int, distance: str = "Cosine") -> None:
        self.collections[name] = {
            "dimensions": dimensions,
            "distance": distance,
            "points": self.collections.get(name, {}).get("points", {}),
        }

    def set_points(self, name: str, points: dict[str, dict]) -> None:
        self.collections[name]["points"] = dict(points)

    def snapshot_bytes(self, name: str) -> bytes:
        collection = self.collections[name]
        payload = {
            "dimensions": collection["dimensions"],
            "distance": collection["distance"],
            "points": [[point_id, collection["points"][point_id]] for point_id in sorted(collection["points"])],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")

    # -------------------------------------------------------------- HTTP

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    @staticmethod
    def _json(payload: dict, *, status_code: int = 200) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        if self.offline:
            raise httpx.ConnectError("connection refused（替身）", request=request)
        path = request.url.path.rstrip("/")
        parts = [item for item in path.split("/") if item]
        if request.method == "GET" and not parts:
            return self._json({"title": "qdrant-fake", "version": "0"})
        if parts[:1] != ["collections"]:
            return self._json({"status": {"error": f"unsupported {path}"}}, status_code=404)
        if len(parts) == 1 and request.method == "GET":
            return self._json(
                {
                    "result": {
                        "collections": [{"name": name} for name in sorted(self.collections)]
                    }
                }
            )
        name = parts[1]
        if len(parts) == 2 and request.method == "GET":
            collection = self.collections.get(name)
            if collection is None:
                return self._json({"status": {"error": "not found"}}, status_code=404)
            return self._json(
                {
                    "result": {
                        "config": {
                            "params": {
                                "vectors": {
                                    "size": collection["dimensions"],
                                    "distance": collection["distance"],
                                }
                            }
                        },
                        "points_count": len(collection["points"]),
                    }
                }
            )
        if parts[2:] == ["points", "count"] and request.method == "POST":
            collection = self.collections.get(name)
            if collection is None:
                return self._json({"status": {"error": "not found"}}, status_code=404)
            return self._json({"result": {"count": len(collection["points"])}})
        if parts[2:] == ["points", "scroll"] and request.method == "POST":
            collection = self.collections.get(name)
            if collection is None:
                return self._json({"status": {"error": "not found"}}, status_code=404)
            body = json.loads(request.content or b"{}")
            limit = int(body.get("limit") or 10)
            ids = sorted(collection["points"])
            offset = body.get("offset")
            start = ids.index(offset) + 1 if offset in ids else 0
            page = ids[start : start + limit]
            next_offset = None
            if start + limit < len(ids) and page:
                next_offset = page[-1]
            points = [
                {
                    "id": point_id,
                    "payload": dict(collection["points"][point_id]),
                }
                for point_id in page
            ]
            return self._json({"result": {"points": points, "next_page_offset": next_offset}})
        if parts[2:] == ["snapshots"] and request.method == "POST":
            if name not in self.collections:
                return self._json({"status": {"error": "not found"}}, status_code=404)
            self._counter += 1
            snapshot = f"{name}-{self._counter}.snapshot"
            self.snapshots[(name, snapshot)] = self.snapshot_bytes(name)
            return self._json({"result": {"name": snapshot}})
        if len(parts) == 4 and parts[2] == "snapshots" and request.method == "GET":
            data = self.snapshots.get((name, parts[3]))
            if data is None:
                return self._json({"status": {"error": "not found"}}, status_code=404)
            return httpx.Response(200, content=data)
        if len(parts) == 4 and parts[2] == "snapshots" and request.method == "DELETE":
            self.snapshots.pop((name, parts[3]), None)
            self.deleted_snapshots.append(parts[3])
            return self._json({"result": True})
        if parts[2:] == ["snapshots", "upload"] and request.method == "POST":
            if self.fail_upload:
                return self._json({"status": {"error": "upload refused"}}, status_code=500)
            payload = self._extract_multipart(request.content)
            if payload is None:
                return self._json({"status": {"error": "bad multipart"}}, status_code=400)
            data = json.loads(payload)
            self.collections[name] = {
                "dimensions": data["dimensions"],
                "distance": data["distance"],
                "points": {point[0]: point[1] for point in data["points"]},
            }
            self.uploaded_collections.append(name)
            return self._json({"result": True})
        return self._json({"status": {"error": f"unsupported {request.method} {path}"}}, status_code=404)

    @staticmethod
    def _extract_multipart(content: bytes) -> bytes | None:
        start = content.find(b"\r\n\r\n")
        if start < 0:
            return None
        end = content.rfind(b"\r\n--")
        if end < 0:
            return None
        return content[start + 4 : end]


# --------------------------------------------------------------------------- 测试环境


class BackupEnv:
    """真实布局的临时数据根：教材目录（含封存与草稿）+ 题库 + 替身 Qdrant。"""

    def __init__(
        self, tmp_path: Path, *, seed_draft: bool = True, seed_question: bool = True
    ) -> None:
        self.tmp = tmp_path
        self.harness = Harness(tmp_path)
        self.root = self.harness.settings.data_dir
        self.catalog = self.harness.catalog
        self.settings = self.harness.settings

        job = self.harness.commit_and_run(
            self.harness.import_with_metadata(sample_text("备份基线")),
            submission_id="backup-baseline-1",
        )
        self.document_id = job.documentId
        assert self.document_id
        self.revision = self.catalog.list_document_revisions(self.document_id)[-1]
        self.generation_id = self.catalog.catalog_state().active_generation_id
        assert self.generation_id
        generation = self.catalog.get_generation(self.generation_id)
        assert generation is not None
        self.collection_name = generation.collection_name
        self.chunk_set_id = self.catalog.list_generation_revisions(self.generation_id)[0].chunk_set_id

        self.draft = None
        if seed_draft:
            self.draft = self.harness.import_with_metadata(sample_text("草稿预览"))

        # 未完成临时文件：绝不能进备份，也不是有效草稿产物
        staging = self.root / "textbooks" / "staging"
        (staging / "tmp-deadbeef.part").write_bytes(b"half written")
        (staging / "abc123.tmp-9f0").write_bytes(b"half written")

        # 题库：真实导入路径写 blobs 与 question_imports 行
        self.question_catalog = QuestionBankCatalog(
            self.root / "question-bank" / "question-bank.sqlite3"
        )
        self.question_catalog.migrate()
        self.question_blob_id = None
        if seed_question:
            service = QuestionBankService(self.question_catalog, self.settings)
            detail = service.create_import(
                file_name="题库.md",
                data="# 题目\n\n下列集合运算正确的是（ ）。\nA. 并集\nB. 交集\n".encode("utf-8"),
                subject_id="math",
                grade_id="senior-1",
            )
            record = self.question_catalog.get_import(detail.importId)
            assert record is not None
            self.question_blob_id = record.original_blob_id
            assert self.question_blob_id

        # 知识点库与教学库：B0 迁移建库（四库备份必须都能取到 SQLite 快照）
        self.knowledge_catalog = KnowledgeCatalog(
            self.root / "knowledge" / "knowledge.sqlite3"
        )
        self.knowledge_catalog.migrate()
        self.teaching_catalog = TeachingCatalog(
            self.root / "teaching" / "teaching.sqlite3"
        )
        self.teaching_catalog.migrate()

        # 受管资产：真实文件（内容寻址）+ 教学库 file_assets 登记行
        self.asset_bytes = "受管资产基线：名单一行\n".encode("utf-8")
        self.asset_store = AssetStore(self.root / "assets")
        stored = self.asset_store.store_original(
            self.asset_bytes, media_type="text/csv", original_name="名单.csv"
        )
        self.asset_blob_key = stored.blob_key
        self.asset_sha256 = stored.sha256
        self.asset_repo = FileAssetsRepository(self.teaching_catalog)
        asset_record = self.asset_repo.create(
            kind="roster",
            blob_key=stored.blob_key,
            sha256=stored.sha256,
            media_type="text/csv",
            byte_size=stored.byte_size,
            original_name="名单.csv",
        )
        self.asset_id = asset_record.asset_id

        # 替身 Qdrant：按目录里的分块写入与索引器一致的 point
        self.server = FakeQdrantServer()
        self.admin = backup.QdrantAdmin("http://127.0.0.1:16333", transport=self.server.transport())
        self.point_count = self._populate_qdrant()

    # ------------------------------------------------------------------ 便捷

    def _populate_qdrant(self) -> int:
        points: dict[str, dict] = {}
        for record in self.catalog.list_generation_revisions(self.generation_id):
            if record.state != "ready":
                continue
            for chunk in self.catalog.list_chunks(record.chunk_set_id):
                point_id = point_id_for(
                    self.generation_id, record.chunk_set_id, chunk.ordinal, chunk.text_sha256
                )
                points[point_id] = {
                    "document_revision_id": record.document_revision_id,
                    "chunk_set_id": record.chunk_set_id,
                    "ordinal": chunk.ordinal,
                    "text_sha256": chunk.text_sha256,
                }
        self.server.ensure_collection(
            self.collection_name, dimensions=DIMENSIONS, distance="Cosine"
        )
        self.server.set_points(self.collection_name, points)
        return len(points)

    def create(self, target: Path, **kwargs):
        return backup.create_backup(
            data_dir=self.root,
            target=target,
            qdrant_client=kwargs.pop("qdrant_client", self.admin),
            **kwargs,
        )

    def draft_staging_files(self) -> list[str]:
        assert self.draft is not None
        artifacts = self.catalog.get_import(self.draft.importId).parsed_artifacts
        return [
            f"textbooks/staging/{artifacts[key]}"
            for key in ("normalizedBlobId", "sourceMapBlobId")
        ]


def make_env(tmp_path: Path, **kwargs) -> BackupEnv:
    return BackupEnv(tmp_path, **kwargs)


def _row_snapshot(db_path: Path, sql: str) -> list[tuple]:
    connection = sqlite3.connect(str(db_path))
    try:
        connection.row_factory = sqlite3.Row
        return [tuple(row) for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BACKUP_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(API_ROOT),
    )


# --------------------------------------------------------------------------- 备份


def test_backup_refuses_while_lock_held_and_writes_nothing(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    target = tmp_path / "backup-locked"
    holder = acquire_data_lock(env.root, exclusive=True, label="api")
    try:
        with pytest.raises(AppError) as excinfo:
            env.create(target)
        error = excinfo.value
        assert error.code == "DATA_LOCK_BUSY"
        assert error.status_code == 409
        assert error.retryable is True
        assert "排他锁" in str(error)
        assert not target.exists()

        result = _run_cli(
            "create", "--data-dir", str(env.root), "--into", str(target)
        )
        assert result.returncode == 2  # 非零退出：拒绝且未写任何文件
        assert "DATA_LOCK_BUSY" in result.stderr
        assert "排他锁" in result.stderr
        assert "备份完成" not in result.stdout
        assert not target.exists()
    finally:
        holder.close()

    # 释放后同一份数据可以正常备份
    manifest = env.create(target)
    assert manifest["status"] == "complete"


def test_backup_refuses_unfinished_jobs_without_touching_rows(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    textbook_db = env.root / "textbooks" / "catalog.sqlite3"
    question_db = env.root / "question-bank" / "question-bank.sqlite3"
    job = env.catalog.create_job(
        kind="ingest", idempotency_key="unfinished-1", request_fingerprint="fp"
    )
    env.catalog.set_rebuild_job(job.job_id)
    question_job = env.question_catalog.create_job(kind="organize", state="running")

    before_textbook = _row_snapshot(textbook_db, "SELECT * FROM index_jobs")
    before_state = _row_snapshot(textbook_db, "SELECT * FROM catalog_state")
    before_question = _row_snapshot(question_db, "SELECT * FROM question_jobs")
    target = tmp_path / "backup-unfinished"

    with pytest.raises(backup.BackupRefused) as excinfo:
        env.create(target)
    message = str(excinfo.value)
    assert job.job_id in message
    assert "重建指针" in message
    assert question_job.job_id in message
    assert not target.exists()

    # 备份只读任务状态：逐列逐字节未变（不擅自修改遗留任务）
    assert _row_snapshot(textbook_db, "SELECT * FROM index_jobs") == before_textbook
    assert _row_snapshot(textbook_db, "SELECT * FROM catalog_state") == before_state
    assert _row_snapshot(question_db, "SELECT * FROM question_jobs") == before_question

    result = _run_cli("create", "--data-dir", str(env.root), "--into", str(target))
    assert result.returncode != 0
    assert not target.exists()


def test_backup_manifest_shape_includes_draft_artifacts_and_excludes_temporary(
    tmp_path: Path,
) -> None:
    env = make_env(tmp_path)
    target = tmp_path / "backup"
    manifest = env.create(target)
    assert manifest["status"] == "complete", manifest["failures"]
    assert manifest["schemaVersion"] == 3
    assert manifest["createdAt"]
    assert manifest["activeGenerationId"] == env.generation_id

    restore_paths = {item["restorePath"] for item in manifest["files"]}
    # v3：四库都必须登记（缺任何一个都是 failure，不会悄悄少备份）
    assert "textbooks/catalog.sqlite3" in restore_paths
    assert "question-bank/question-bank.sqlite3" in restore_paths
    assert "knowledge/knowledge.sqlite3" in restore_paths
    assert "teaching/teaching.sqlite3" in restore_paths
    assert f"textbooks/blobs/{env.revision.original_blob_id}" in restore_paths
    assert f"textbooks/normalized/{env.revision.normalized_blob_id}" in restore_paths
    assert f"question-bank/blobs/{env.question_blob_id}" in restore_paths
    assert f"assets/{env.asset_blob_key}" in restore_paths
    for expected in env.draft_staging_files():
        assert expected in restore_paths, manifest["files"]
    assert all("tmp-" not in item["archivePath"] for item in manifest["files"])
    assert all("tmp-" not in item["restorePath"] for item in manifest["files"])
    assert all(".zqky-data.lock" not in item["archivePath"] for item in manifest["files"])
    assert not (target / "files" / "textbook-staging" / "tmp-deadbeef.part").exists()

    collection = manifest["collections"][0]
    assert collection["collectionName"] == env.collection_name
    assert collection["generationId"] == env.generation_id
    assert collection["dimensions"] == DIMENSIONS
    assert collection["pointCount"] == env.point_count
    assert collection["snapshotSha256"]
    assert collection["pointManifestSha256"]
    assert (target / collection["snapshotPath"]).is_file()
    assert env.server.snapshots == {}  # 导出后清理临时快照
    assert env.server.deleted_snapshots

    # 每个条目都能被 verify 复算
    failures, _notes = backup.verify_backup(target)
    assert failures == []


def test_backup_only_copies_referenced_files(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    orphan_blob = hashlib.sha256(b"orphan-blob").hexdigest()
    orphan_file = env.root / "textbooks" / "blobs" / orphan_blob
    orphan_file.write_bytes(b"orphan-blob")
    orphan_question = hashlib.sha256(b"orphan-question").hexdigest()
    (env.root / "question-bank" / "blobs" / orphan_question).write_bytes(b"orphan-question")
    orphan_asset = hashlib.sha256(b"orphan-asset").hexdigest()
    orphan_asset_file = env.root / "assets" / "blobs" / orphan_asset
    orphan_asset_file.write_bytes(b"orphan-asset")

    target = tmp_path / "backup"
    manifest = env.create(target)
    assert manifest["status"] == "complete", manifest["failures"]
    blob_ids = {Path(item["archivePath"]).name for item in manifest["files"]}
    assert orphan_blob not in blob_ids
    assert orphan_question not in blob_ids
    assert orphan_asset not in blob_ids
    assert env.asset_sha256 in blob_ids  # 被 file_assets 引用的资产必须收录
    assert not (target / "files" / "textbook-blob" / orphan_blob).exists()
    assert not (target / "files" / "question-bank-blob" / orphan_question).exists()
    assert not (target / "files" / "assets" / "blobs" / orphan_asset).exists()
    assert (target / "files" / "assets" / env.asset_blob_key).is_file()
    # 锁文件也不在归档里
    assert not list(target.rglob(".zqky-data.lock"))


def test_missing_referenced_file_fails_backup_and_cli_does_not_claim_success(
    tmp_path: Path,
) -> None:
    env = make_env(tmp_path)
    missing = env.root / "textbooks" / "normalized" / env.revision.normalized_blob_id
    missing.unlink()
    target = tmp_path / "backup-missing"

    manifest = env.create(target)
    assert manifest["status"] == "failed"
    assert any("规范化正文" in item for item in manifest["failures"])
    assert (target / "manifest.json").is_file()

    failures, _notes = backup.verify_backup(target)
    assert failures  # status 不是 complete，先被 verify 拒绝

    result = _run_cli("create", "--data-dir", str(env.root), "--into", str(tmp_path / "cli"))
    assert result.returncode == 1
    assert "备份完成" not in result.stdout
    assert "备份失败" in result.stderr


def test_verify_rejects_tampered_blob(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    target = tmp_path / "backup"
    manifest = env.create(target)
    assert manifest["status"] == "complete"

    entry = next(item for item in manifest["files"] if item["logicalRole"] == "textbook-blob")
    tampered = target / entry["archivePath"]
    tampered.write_bytes(tampered.read_bytes() + b"x")

    failures, _notes = backup.verify_backup(target)
    assert any("指纹不符" in item for item in failures)
    assert backup.main(["verify", "--path", str(target)]) == 1

    # 未被篡改时 verify 通过
    ok_target = tmp_path / "backup-ok"
    env.create(ok_target)
    assert backup.main(["verify", "--path", str(ok_target)]) == 0


def test_verify_reports_failed_status(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    (env.root / "textbooks" / "normalized" / env.revision.normalized_blob_id).unlink()
    target = tmp_path / "backup-failed"
    env.create(target)
    failures, _notes = backup.verify_backup(target)
    assert any("status=failed" in item for item in failures)
    assert backup.main(["verify", "--path", str(target)]) == 1


def test_missing_knowledge_catalog_fails_backup_and_cli_exit_1(tmp_path: Path) -> None:
    """四库缺任何一个都算失败：不得悄悄少备份一个库。"""
    env = make_env(tmp_path)
    (env.root / "knowledge" / "knowledge.sqlite3").unlink()
    target = tmp_path / "backup-missing-knowledge"

    manifest = env.create(target)
    assert manifest["status"] == "failed"
    assert any("知识点库缺失" in item for item in manifest["failures"])
    assert "knowledge/knowledge.sqlite3" not in {
        item["restorePath"] for item in manifest["files"]
    }
    assert (target / "manifest.json").is_file()

    failures, _notes = backup.verify_backup(target)
    assert any("status=failed" in item for item in failures)

    result = _run_cli(
        "create", "--data-dir", str(env.root), "--into", str(tmp_path / "cli-missing")
    )
    assert result.returncode == 1
    assert "备份完成" not in result.stdout
    assert "备份失败" in result.stderr
    assert "知识点库" in result.stderr


def test_backup_fails_when_referenced_asset_missing_or_tampered(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    asset_path = env.root / "assets" / env.asset_blob_key
    original = asset_path.read_bytes()

    # 源文件字节被篡改（同长度）→ 内容指纹不符
    asset_path.write_bytes(bytes([original[0] ^ 0xFF]) + original[1:])
    target = tmp_path / "backup-tampered-asset"
    manifest = env.create(target)
    assert manifest["status"] == "failed"
    assert any(
        "受管资产" in item and "指纹不符" in item for item in manifest["failures"]
    )

    # 源文件缺失 → 明确失败并指名文件
    asset_path.write_bytes(original)
    asset_path.unlink()
    target = tmp_path / "backup-missing-asset"
    manifest = env.create(target)
    assert manifest["status"] == "failed"
    assert any(
        "受管资产" in item and "缺失" in item for item in manifest["failures"]
    )


def test_verify_rejects_tampered_asset_blob(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    target = tmp_path / "backup"
    manifest = env.create(target)
    assert manifest["status"] == "complete", manifest["failures"]

    entry = next(item for item in manifest["files"] if item["logicalRole"] == "asset-blob")
    assert Path(entry["archivePath"]).name == env.asset_sha256  # 内容寻址
    tampered = target / entry["archivePath"]
    tampered.write_bytes(tampered.read_bytes() + b"x")

    failures, _notes = backup.verify_backup(target)
    assert any(
        "指纹不符" in item or "内容寻址不符" in item for item in failures
    ), failures
    assert backup.main(["verify", "--path", str(target)]) == 1


# --------------------------------------------------------------------------- 恢复


def test_restore_writes_runtime_layout_and_app_can_read(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)
    restored = tmp_path / "restored"
    original_collection_name = env.collection_name

    state = backup.restore_backup(source, restored, isolated_qdrant=env.admin)
    assert state["status"] == "ready"
    assert restore_state(restored)["status"] == "ready"
    require_data_root_ready(restored)

    # 应用运行布局：Settings(data_dir=恢复目录) 直接可读
    assert (restored / "textbooks" / "catalog.sqlite3").is_file()
    assert (restored / "textbooks" / "blobs").is_dir()
    assert (restored / "textbooks" / "normalized").is_dir()
    assert (restored / "textbooks" / "staging").is_dir()
    assert (restored / "question-bank" / "question-bank.sqlite3").is_file()
    # v3：知识点库、教学库与受管资产同样恢复为运行布局
    assert (restored / "knowledge" / "knowledge.sqlite3").is_file()
    assert (restored / "teaching" / "teaching.sqlite3").is_file()
    assert (restored / "assets" / env.asset_blob_key).is_file()
    assert not (restored / "sqlite").exists()
    assert not (restored / "files").exists()

    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=frozenset(),
        env="test",
        data_dir=restored,
    )
    catalog = TextbookCatalog(settings.textbooks_root / "catalog.sqlite3")
    catalog.migrate()
    assert catalog.catalog_state().active_generation_id == env.generation_id
    generation = catalog.get_generation(env.generation_id)
    assert generation is not None
    assert "__restored_" in generation.collection_name
    assert generation.collection_name != original_collection_name
    document = catalog.get_document(env.document_id)
    assert document is not None and document.title == METADATA["title"]
    revision = catalog.get_revision(env.revision.revision_id)
    assert revision is not None and revision.normalized_blob_id == env.revision.normalized_blob_id
    assert len(catalog.list_chunks(env.chunk_set_id)) == len(
        env.catalog.list_chunks(env.chunk_set_id)
    )

    # 未发布草稿的预览与提交能力在恢复目录里仍可用
    service = IngestService(
        catalog,
        parse_document,
        chunk_document,
        env.harness.embeddings,
        InMemoryVectorStore(),
        settings,
        sleep=lambda _seconds: None,
    )
    assert env.draft is not None
    view = service.get_import_view(env.draft.importId)
    assert view.parsed is not None
    assert view.parsed.chunkCount >= 1
    assert view.canCommit is True

    # 题库数据库同样可读
    question_catalog = QuestionBankCatalog(settings.question_bank_root / "question-bank.sqlite3")
    question_catalog.migrate()
    imports = question_catalog.list_imports()
    assert len(imports) == 1 and imports[0].original_blob_id == env.question_blob_id

    # 知识点库与教学库同样可读，应用侧能读出受管资产登记行
    knowledge_catalog = KnowledgeCatalog(settings.knowledge_root / "knowledge.sqlite3")
    knowledge_catalog.migrate()
    teaching_catalog = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
    teaching_catalog.migrate()
    asset_record = FileAssetsRepository(teaching_catalog).get(env.asset_id)
    assert asset_record is not None
    assert asset_record.blob_key == env.asset_blob_key
    assert asset_record.sha256 == env.asset_sha256
    assert asset_record.ref().byte_size == len(env.asset_bytes)
    asset_store = AssetStore(settings.assets_root)
    assert asset_store.read(env.asset_blob_key) == env.asset_bytes
    assert asset_store.verify(env.asset_blob_key) == len(env.asset_bytes)

    # 隔离实例上出现新 collection，点数与 payload 指纹已核对；原 collection 未被改写
    restored_record = state["restoredCollections"][0]
    assert restored_record["pointCount"] == env.point_count
    assert restored_record["restoredCollectionName"] in env.server.collections
    assert original_collection_name in env.server.collections
    assert env.server.collections[restored_record["restoredCollectionName"]]["points"] == (
        env.server.collections[original_collection_name]["points"]
    )

    # 原始数据根未被恢复过程改写
    original_catalog = TextbookCatalog(env.root / "textbooks" / "catalog.sqlite3")
    original_catalog.migrate()
    assert original_catalog.get_generation(env.generation_id).collection_name == (
        original_collection_name
    )
    assert (env.root / "assets" / env.asset_blob_key).read_bytes() == env.asset_bytes
    assert env.asset_repo.get(env.asset_id) is not None


def test_v3_backup_verify_restore_all_four_catalogs_and_assets(tmp_path: Path) -> None:
    """v3 全链路：create → verify → restore，四库可读、资产可校验。"""
    env = make_env(tmp_path)
    source = tmp_path / "backup-v3"

    manifest = env.create(source)
    assert manifest["status"] == "complete", manifest["failures"]
    assert manifest["schemaVersion"] == 3
    failures, _notes = backup.verify_backup(source)
    assert failures == []
    assert backup.main(["verify", "--path", str(source)]) == 0

    restored = tmp_path / "restored-v3"
    state = backup.restore_backup(source, restored, isolated_qdrant=env.admin)
    assert state["status"] == "ready"
    assert state["manifestSchemaVersion"] == 3
    assert restore_state(restored)["status"] == "ready"
    require_data_root_ready(restored)

    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=frozenset(),
        env="test",
        data_dir=restored,
    )
    for relative in (
        "textbooks/catalog.sqlite3",
        "question-bank/question-bank.sqlite3",
        "knowledge/knowledge.sqlite3",
        "teaching/teaching.sqlite3",
    ):
        assert (restored / relative).is_file(), relative
    assert not (restored / "sqlite").exists()
    assert not (restored / "files").exists()

    # 资产可校验：改名文件在运行布局里，内容与散列一致
    asset_store = AssetStore(settings.assets_root)
    assert asset_store.read(env.asset_blob_key) == env.asset_bytes
    assert asset_store.verify(env.asset_blob_key) == len(env.asset_bytes)

    # 应用侧：知识点库/教学库迁移幂等，教学库能读出 file_assets 行
    KnowledgeCatalog(settings.knowledge_root / "knowledge.sqlite3").migrate()
    teaching = TeachingCatalog(settings.teaching_root / "teaching.sqlite3")
    teaching.migrate()
    record = FileAssetsRepository(teaching).get(env.asset_id)
    assert record is not None
    assert record.kind == "roster"
    assert record.blob_key == env.asset_blob_key
    assert record.ref().sha256 == env.asset_sha256


def test_restore_refuses_existing_target(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)
    target = tmp_path / "restored"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("用户文件", encoding="utf-8")

    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(source, target, isolated_qdrant=env.admin)
    assert "已存在" in str(excinfo.value)
    assert marker.read_text(encoding="utf-8") == "用户文件"
    assert not (target / "restore-state.json").exists()
    assert not (target / "textbooks").exists()


def test_restore_refuses_path_traversal_in_manifest(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["files"] if item["logicalRole"] == "textbook-blob")
    entry["restorePath"] = "../evil"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    target = tmp_path / "restored"
    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(source, target, isolated_qdrant=env.admin)
    assert "越出数据根" in str(excinfo.value) or "restorePath" in str(excinfo.value)
    assert not target.exists()
    assert not (tmp_path / "evil").exists()

    # 绝对路径与带盘符的路径同样拒绝
    entry["restorePath"] = "C:/evil/blob"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(backup.BackupRefused):
        backup.restore_backup(source, tmp_path / "restored2", isolated_qdrant=env.admin)
    assert not (tmp_path / "restored2").exists()


def test_restore_requires_isolated_qdrant(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)

    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(source, tmp_path / "r1", isolated_qdrant=None)
    assert "隔离" in str(excinfo.value)
    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(source, tmp_path / "r2", isolated_qdrant="http://127.0.0.1:6333")
    assert "6333" in str(excinfo.value)
    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(source, tmp_path / "r3", isolated_qdrant="http://10.0.0.5:16333")
    assert "回环" in str(excinfo.value)
    for name in ("r1", "r2", "r3"):
        assert not (tmp_path / name).exists()

    assert backup.ensure_isolated_qdrant_url("http://127.0.0.1:16333") == (
        "http://127.0.0.1:16333"
    )
    assert backup.main(
        ["restore", "--path", str(source), "--into", str(tmp_path / "r4")]
    ) == 2
    assert not (tmp_path / "r4").exists()


def test_restore_failure_leaves_incomplete_state_and_gate_refuses(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)
    target = tmp_path / "restored-offline"
    env.server.offline = True
    try:
        with pytest.raises(AppError) as excinfo:
            backup.restore_backup(source, target, isolated_qdrant=env.admin)
        assert excinfo.value.code == "QDRANT_UNAVAILABLE"
    finally:
        env.server.offline = False

    state = restore_state(target)
    assert state is not None and state["status"] == "incomplete"
    assert state["failures"]
    assert (target / "textbooks" / "catalog.sqlite3").is_file()  # 文件已落盘但整体未完成
    with pytest.raises(AppError) as excinfo:
        require_data_root_ready(target)
    assert excinfo.value.code == "DATA_RESTORE_INCOMPLETE"
    assert not any("__restored_" in name for name in env.server.collections)

    # 修好隔离实例后，换新目录恢复成功
    ok_target = tmp_path / "restored-fixed"
    state = backup.restore_backup(source, ok_target, isolated_qdrant=env.admin)
    assert state["status"] == "ready"


def test_restore_cancellation_leaves_incomplete_state(tmp_path: Path) -> None:
    """取消（KeyboardInterrupt）也必须留下 incomplete，不伪装成可用目录。"""
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)
    target = tmp_path / "restored-cancelled"

    class Cancelled(RuntimeError):
        pass

    original = env.admin.restore_snapshot

    def cancel(**_kwargs):
        raise KeyboardInterrupt("用户取消")

    env.admin.restore_snapshot = cancel
    try:
        with pytest.raises(KeyboardInterrupt):
            backup.restore_backup(source, target, isolated_qdrant=env.admin)
    finally:
        env.admin.restore_snapshot = original

    state = restore_state(target)
    assert state is not None and state["status"] == "incomplete"
    assert any("KeyboardInterrupt" in item for item in state["failures"])
    with pytest.raises(AppError) as excinfo:
        require_data_root_ready(target)
    assert excinfo.value.code == "DATA_RESTORE_INCOMPLETE"


def test_restore_refuses_when_collection_dimensions_mismatch(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    manifest = env.create(source)
    assert manifest["status"] == "complete"
    # 模拟"快照内容维度与清单不符"：篡改清单声明的维度
    manifest_path = source / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["collections"][0]["dimensions"] = DIMENSIONS + 1
    manifest_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    target = tmp_path / "restored-mismatch"
    with pytest.raises(backup.BackupFailed) as excinfo:
        backup.restore_backup(source, target, isolated_qdrant=env.admin)
    assert "维度" in str(excinfo.value)
    state = restore_state(target)
    assert state is not None and state["status"] == "incomplete"


def test_restore_fails_when_teaching_asset_reference_missing(tmp_path: Path) -> None:
    """恢复后的教学库引用了未随归档恢复的资产 → 失败且 restore-state 留 incomplete。"""
    env = make_env(tmp_path)
    source = tmp_path / "backup"
    env.create(source)

    # 手工构造内部不一致的 v3 归档：教学库仍引用资产，但清单与归档都没有该资产
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    removed = [
        item for item in manifest["files"] if item.get("logicalRole") == "asset-blob"
    ]
    assert removed
    manifest["files"] = [
        item for item in manifest["files"] if item.get("logicalRole") != "asset-blob"
    ]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    for item in removed:
        (source / item["archivePath"]).unlink(missing_ok=True)

    target = tmp_path / "restored-missing-asset"
    with pytest.raises(backup.BackupFailed) as excinfo:
        backup.restore_backup(source, target, isolated_qdrant=env.admin)
    assert "受管资产" in str(excinfo.value)
    assert not (target / "assets" / env.asset_blob_key).exists()

    state = restore_state(target)
    assert state is not None and state["status"] == "incomplete"
    assert any("受管资产" in item for item in state["failures"])
    with pytest.raises(AppError) as excinfo:
        require_data_root_ready(target)
    assert excinfo.value.code == "DATA_RESTORE_INCOMPLETE"


# --------------------------------------------------------------------------- 旧清单


def _copy_legacy_layout(env: BackupEnv, archive: Path, *, include_snapshot: bool = True) -> dict:
    """把数据根的两库与 blob 摊成旧归档布局（sqlite/ + files/ + qdrant/），并写旧清单。"""
    (archive / "sqlite").mkdir(parents=True)
    (archive / "files" / "textbooks-blobs").mkdir(parents=True)
    (archive / "files" / "textbooks-normalized").mkdir(parents=True)
    (archive / "files" / "question-bank-blobs").mkdir(parents=True)
    entries: list[dict] = []

    catalog_copy = archive / "sqlite" / "catalog.sqlite3"
    shutil.copy2(env.root / "textbooks" / "catalog.sqlite3", catalog_copy)
    entries.append(
        {
            "kind": "sqlite",
            "name": "textbooks",
            "path": "sqlite/catalog.sqlite3",
            "sha256": hashlib.sha256(catalog_copy.read_bytes()).hexdigest(),
        }
    )
    question_copy = archive / "sqlite" / "question-bank.sqlite3"
    shutil.copy2(env.root / "question-bank" / "question-bank.sqlite3", question_copy)
    entries.append(
        {
            "kind": "sqlite",
            "name": "question-bank",
            "path": "sqlite/question-bank.sqlite3",
            "sha256": hashlib.sha256(question_copy.read_bytes()).hexdigest(),
        }
    )

    tree_sources = {
        "textbooks-blobs": env.root / "textbooks" / "blobs",
        "textbooks-normalized": env.root / "textbooks" / "normalized",
        "question-bank-blobs": env.root / "question-bank" / "blobs",
    }
    for name, source in tree_sources.items():
        target_dir = archive / "files" / name
        count = 0
        for item in source.iterdir():
            if not item.is_file():
                continue
            shutil.copy2(item, target_dir / item.name)
            count += 1
        entries.append({"kind": "tree", "name": name, "files": count})

    if include_snapshot:
        qdrant_dir = archive / "qdrant"
        qdrant_dir.mkdir()
        snapshot = env.server.snapshot_bytes(env.collection_name)
        snapshot_path = qdrant_dir / f"{env.collection_name}__legacy.snapshot"
        snapshot_path.write_bytes(snapshot)
        entries.append(
            {
                "kind": "qdrant",
                "name": env.collection_name,
                "path": f"qdrant/{snapshot_path.name}",
                "sha256": hashlib.sha256(snapshot).hexdigest(),
            }
        )

    manifest = {
        "createdAt": "2026-09-01T00:00:00Z",
        "label": "legacy",
        "dataDir": str(env.root),
        "activeGenerationId": env.generation_id,
        "qdrantUrl": "http://127.0.0.1:6333",
        "entries": entries,
        "note": "旧格式清单（无 schemaVersion）",
    }
    (archive / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def test_legacy_manifest_restore_maps_archive_layout(tmp_path: Path) -> None:
    env = make_env(tmp_path, seed_draft=False)
    archive = tmp_path / "legacy-archive"
    _copy_legacy_layout(env, archive)

    failures, notes = backup.verify_backup(archive)
    assert failures == []
    assert any("legacy_revalidated" in note for note in notes)

    target = tmp_path / "legacy-restored"
    state = backup.restore_backup(archive, target, isolated_qdrant=env.admin)
    assert state["status"] == "ready"
    assert state["legacyRevalidated"] is True
    assert (target / "textbooks" / "catalog.sqlite3").is_file()
    assert (target / "question-bank" / "question-bank.sqlite3").is_file()
    assert (target / "textbooks" / "blobs" / env.revision.original_blob_id).is_file()
    assert not (target / "sqlite").exists()

    catalog = TextbookCatalog(target / "textbooks" / "catalog.sqlite3")
    catalog.migrate()
    assert catalog.catalog_state().active_generation_id == env.generation_id
    generation = catalog.get_generation(env.generation_id)
    assert generation is not None and "__restored_" in generation.collection_name


def test_legacy_manifest_without_snapshot_refuses_before_writing(tmp_path: Path) -> None:
    env = make_env(tmp_path, seed_draft=False)
    archive = tmp_path / "legacy-archive"
    _copy_legacy_layout(env, archive, include_snapshot=False)
    target = tmp_path / "legacy-restored"
    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(archive, target, isolated_qdrant=env.admin)
    assert "快照" in str(excinfo.value)
    assert not target.exists()


def test_legacy_manifest_with_draft_artifacts_refuses_before_writing(tmp_path: Path) -> None:
    env = make_env(tmp_path, seed_draft=True)
    archive = tmp_path / "legacy-archive"
    _copy_legacy_layout(env, archive)
    target = tmp_path / "legacy-restored"
    with pytest.raises(backup.BackupRefused) as excinfo:
        backup.restore_backup(archive, target, isolated_qdrant=env.admin)
    assert "草稿" in str(excinfo.value)
    assert not target.exists()


# --------------------------------------------------------------------------- v2 兼容


def _downgrade_to_v2(source: Path, target: Path) -> None:
    """把 v3 归档裁剪成手工构造的 v2 两库清单（不依赖已经过时的真实创建路径）。

    只保留教材/题库的 restorePath 条目并删除对应归档里多余的库与资产文件，
    证明 v2 语义（两库必需、无知识点/教学/资产）仍然成立。
    """
    shutil.copytree(source, target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kept: list[dict] = []
    dropped: list[dict] = []
    for item in manifest["files"]:
        restore_path = str(item.get("restorePath") or "")
        bucket = (
            kept
            if restore_path.startswith(("textbooks/", "question-bank/"))
            else dropped
        )
        bucket.append(item)
    manifest["files"] = kept
    manifest["schemaVersion"] = 2
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    for item in dropped:
        archive_path = item.get("archivePath")
        if isinstance(archive_path, str):
            (target / archive_path).unlink(missing_ok=True)
    for stale in ("sqlite/knowledge.sqlite3", "sqlite/teaching.sqlite3"):
        (target / stale).unlink(missing_ok=True)
    shutil.rmtree(target / "files" / "assets", ignore_errors=True)


def test_v2_manifest_still_verifies_and_restores_two_catalogs(tmp_path: Path) -> None:
    env = make_env(tmp_path)
    source = tmp_path / "backup-v3"
    env.create(source)
    v2_archive = tmp_path / "backup-v2"
    _downgrade_to_v2(source, v2_archive)

    failures, notes = backup.verify_backup(v2_archive)
    assert failures == []
    assert any("旧 v2 清单只覆盖教材目录与题库" in note for note in notes)
    assert backup.main(["verify", "--path", str(v2_archive)]) == 0

    restored = tmp_path / "restored-v2"
    state = backup.restore_backup(v2_archive, restored, isolated_qdrant=env.admin)
    assert state["status"] == "ready"
    assert state["manifestSchemaVersion"] == 2
    require_data_root_ready(restored)
    assert (restored / "textbooks" / "catalog.sqlite3").is_file()
    assert (restored / "question-bank" / "question-bank.sqlite3").is_file()
    # v2 语义不变：知识库/教学库/资产目录不因 v3 扩展而被凭空要求
    assert not (restored / "knowledge").exists()
    assert not (restored / "teaching").exists()
    assert not (restored / "assets").exists()

    catalog = TextbookCatalog(restored / "textbooks" / "catalog.sqlite3")
    catalog.migrate()
    assert catalog.catalog_state().active_generation_id == env.generation_id
    question_catalog = QuestionBankCatalog(
        restored / "question-bank" / "question-bank.sqlite3"
    )
    question_catalog.migrate()
    assert question_catalog.list_imports()[0].original_blob_id == env.question_blob_id
