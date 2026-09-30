"""V6 四库备份/校验/恢复独立探针（V00 / TEACHING-LOOP B0）。

覆盖：
  6① 四库 + 受管资产 create→verify→restore 全链路（恢复目录四库可读、
       require_data_root_ready 通过、资产逐文件散列对账；含教材/题库 blob）
  6② 缺一个库 → create 失败（清单 status:"failed"、说明缺哪个库、CLI 非 0、
       stdout 无"备份完成"）
  6③ 篡改归档里的资产字节 → verify 失败
  6④ 恢复时教学库引用的 blob 不在归档 → restore 失败且 restore-state.json=incomplete
  6⑤ 旧 schemaVersion:2 / legacy 清单仍可 verify/restore（自建旧清单夹具）
  附加反例：删除 v3 归档里的教学库（文件 + 清单条目）→ verify 必须失败

独立构造：自建四库夹具与 Fake Qdrant 替身（不联网、不连 6333、不注入候选测试的替身）；
所有目录在系统临时区；CLI 只传 --data-dir/--into 指向临时目录。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from _probe_common import API_ROOT, EVIDENCE_DIR, REPO_ROOT, check, cleanup, record, run_main, temp_root

# --- 载入候选备份脚本（scripts/rag/backup.py，只读） -------------------------
_BACKUP_SPEC = importlib.util.spec_from_file_location(
    "zqky_backup_probe", REPO_ROOT / "scripts" / "rag" / "backup.py"
)
assert _BACKUP_SPEC is not None and _BACKUP_SPEC.loader is not None
backup = importlib.util.module_from_spec(_BACKUP_SPEC)
sys.modules["zqky_backup_probe"] = backup
_BACKUP_SPEC.loader.exec_module(backup)

from app.core.data_lock import require_data_root_ready  # noqa: E402
from app.repositories.knowledge.catalog import KnowledgeCatalog  # noqa: E402
from app.repositories.question_bank.catalog import QuestionBankCatalog  # noqa: E402
from app.repositories.teaching.catalog import TeachingCatalog  # noqa: E402
from app.repositories.textbook_catalog.catalog import TextbookCatalog  # noqa: E402

PROBE = "v6_backup_restore_probe"
FOUR = (
    "textbooks/catalog.sqlite3",
    "question-bank/question-bank.sqlite3",
    "knowledge/knowledge.sqlite3",
    "teaching/teaching.sqlite3",
)


class FakeQdrant:
    """独立替身：record 全部调用；本轮归档没有 collection，调用即视为异常。"""

    base_url = "http://127.0.0.1:16333"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _called(self, name: str):
        self.calls.append(name)
        raise AssertionError(f"探针替身被意外调用：{name}")

    def collection_exists(self, name):  # noqa: D102
        self._called("collection_exists")

    def collection_info(self, name):  # noqa: D102
        self._called("collection_info")

    def count_points(self, name, *, exact=True):  # noqa: D102
        self._called("count_points")

    def point_manifest(self, name):  # noqa: D102
        self._called("point_manifest")

    def create_snapshot(self, name):  # noqa: D102
        self._called("create_snapshot")

    def download_snapshot(self, name, snapshot):  # noqa: D102
        self._called("download_snapshot")

    def restore_snapshot(self, **kwargs):  # noqa: D102
        self._called("restore_snapshot")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_blob(path: Path, content: bytes) -> str:
    digest = hashlib.sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return digest


def build_data_root(root: Path) -> dict:
    """建四库 + 教材/题库/受管资产 blob + 各类引用行的临时数据根。"""
    root.mkdir(parents=True, exist_ok=True)
    textbook_db = root / FOUR[0]
    question_db = root / FOUR[1]
    knowledge_db = root / FOUR[2]
    teaching_db = root / FOUR[3]

    TextbookCatalog(textbook_db).migrate()
    QuestionBankCatalog(question_db).migrate()
    KnowledgeCatalog(knowledge_db).migrate()
    TeachingCatalog(teaching_db).migrate()

    original = b"textbook original bytes"
    normalized = "规范化正文".encode("utf-8")
    source_map = b'{"map":1}'
    orig_sha = _write_blob(root / "textbooks" / "blobs" / "placeholder", original)
    norm_sha = _write_blob(root / "textbooks" / "normalized" / "placeholder", normalized)
    smap_sha = _write_blob(root / "textbooks" / "normalized" / "placeholder", source_map)
    for stale in list((root / "textbooks").rglob("placeholder")):
        stale.unlink()
    (root / "textbooks" / "blobs" / orig_sha).write_bytes(original)
    (root / "textbooks" / "normalized" / norm_sha).write_bytes(normalized)
    (root / "textbooks" / "normalized" / smap_sha).write_bytes(source_map)

    question_blob = b"question bank original"
    qb_sha = _write_blob(root / "question-bank" / "blobs" / "placeholder", question_blob)
    (root / "question-bank" / "blobs" / "placeholder").unlink()
    (root / "question-bank" / "blobs" / qb_sha).write_bytes(question_blob)

    asset_bytes = "受管资产：名单".encode("utf-8")
    asset_sha = _write_blob(root / "assets" / "blobs" / "placeholder", asset_bytes)
    (root / "assets" / "blobs" / "placeholder").unlink()
    (root / "assets" / "blobs" / asset_sha).write_bytes(asset_bytes)

    raw = sqlite3.connect(str(textbook_db))
    try:
        raw.execute(
            "INSERT INTO document_metadata_revisions (id, document_id, title, stage_id, "
            "grade_ids_json, subject_id, edition_id, publication_label, volume_label, created_at) "
            "VALUES ('meta-1', 'doc-1', '数学上册', 'stage-1', '[]', 'math', 'rj', '', '', "
            "'2026-09-30T00:00:00Z')"
        )
        raw.execute(
            "INSERT INTO document_revisions (id, document_id, original_file_sha256, "
            "normalized_text_sha256, parser_version, original_blob_id, normalized_blob_id, "
            "source_map_blob_id, char_count, created_at) VALUES "
            "('rev-1', 'doc-1', ?, ?, 'parser-v1', ?, ?, ?, ?, '2026-09-30T00:00:00Z')",
            (orig_sha, norm_sha, orig_sha, norm_sha, smap_sha, len(normalized)),
        )
        raw.execute(
            "INSERT INTO documents (id, owner_id, origin_key, current_revision_id, "
            "current_metadata_revision_id, revision, deleted_at) VALUES "
            "('doc-1', 'local', 'origin-1', 'rev-1', 'meta-1', 0, NULL)"
        )
        raw.execute(
            "INSERT INTO libraries (id, kind, owner_id, grade_id, subject_id, edition_id, "
            "display_name, revision, deleted_at) VALUES "
            "('lib-1', 'textbook', 'local', NULL, 'math', 'rj', '人教版数学', 0, NULL)"
        )
        raw.execute("INSERT INTO library_documents (library_id, document_id) VALUES ('lib-1','doc-1')")
        raw.commit()
    finally:
        raw.close()

    raw = sqlite3.connect(str(question_db))
    try:
        raw.execute(
            "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
            "uploaded_file_name, uploaded_bytes, state, revision, warnings_json, error_code, "
            "created_at, updated_at) VALUES ('imp-1','local',?,?,'题库原件.docx',?, 'ready', 0, "
            "'[]', NULL, '2026-09-30T00:00:00Z', '2026-09-30T00:00:00Z')",
            (qb_sha, qb_sha, len(question_blob)),
        )
        raw.commit()
    finally:
        raw.close()

    raw = sqlite3.connect(str(teaching_db))
    try:
        raw.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES "
            "('asset-1','local','roster',?,?,'名单.csv','text/csv',?,'2026-09-30T00:00:00Z')",
            (f"blobs/{asset_sha}", asset_sha, len(asset_bytes)),
        )
        raw.commit()
    finally:
        raw.close()

    return {
        "original_sha": orig_sha,
        "normalized_sha": norm_sha,
        "source_map_sha": smap_sha,
        "question_sha": qb_sha,
        "asset_sha": asset_sha,
    }


def _db_sanity(path: Path) -> bool:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        return True
    finally:
        connection.close()


# --------------------------------------------------------------------------- 6① 全链路


def part_full_chain(root: Path) -> None:
    data_root = root / "data"
    fixture = build_data_root(data_root)
    archive = root / "archive"
    manifest = backup.create_backup(
        data_dir=data_root,
        target=archive,
        label="v00-probe",
        qdrant_client=FakeQdrant(),
    )
    (EVIDENCE_DIR / "v6_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    check("v6.1a create status complete", manifest["status"] == "complete", f"failures={manifest['failures']}")
    roles = {item["logicalRole"] for item in manifest["files"]}
    check(
        "v6.1b all four catalogs + assets + blobs captured",
        {
            "textbook-catalog",
            "question-bank-catalog",
            "knowledge-catalog",
            "teaching-catalog",
            "asset-blob",
            "textbook-blob",
            "textbook-normalized",
            "question-bank-blob",
        }
        <= roles,
        str(sorted(roles)),
    )
    hashes_ok = all(
        sha256_file(archive / item["archivePath"]) == item["sha256"] for item in manifest["files"]
    )
    check("v6.1c every archived file hash matches the manifest", hashes_ok, "")

    failures, notes = backup.verify_backup(archive)
    check("v6.1d verify passes on a complete archive", failures == [], str(failures))
    check("v6.1e verify adds no legacy/v2 notes", notes == [], str(notes))

    new_root = root / "restored"
    fake = FakeQdrant()
    state = backup.restore_backup(archive, new_root, isolated_qdrant=fake)
    check("v6.1f restore ends ready", state.get("status") == "ready", str(state.get("status")))
    check("v6.1g restore touched no Qdrant collection", fake.calls == [], str(fake.calls))
    try:
        require_data_root_ready(new_root)
        record("v6.1h require_data_root_ready passes on restored dir", True)
    except Exception as exc:  # noqa: BLE001
        record("v6.1h require_data_root_ready passes on restored dir", False, repr(exc))
    restored_dbs = [rel for rel in FOUR if (new_root / rel).is_file() and _db_sanity(new_root / rel)]
    check("v6.1i all four restored databases readable", len(restored_dbs) == 4, str(restored_dbs))
    archive_pairs = {
        "textbooks/catalog.sqlite3": "sqlite/textbooks-catalog.sqlite3",
        "question-bank/question-bank.sqlite3": "sqlite/question-bank.sqlite3",
        "knowledge/knowledge.sqlite3": "sqlite/knowledge.sqlite3",
        "teaching/teaching.sqlite3": "sqlite/teaching.sqlite3",
    }
    identical = all(
        sha256_file(new_root / rel) == sha256_file(archive / arch)
        for rel, arch in archive_pairs.items()
    )
    check("v6.1j restored catalogs byte-identical to archived snapshots", identical, "")

    restored_asset = new_root / "assets" / "blobs" / fixture["asset_sha"]
    check(
        "v6.1k managed asset restored and hash matches registry",
        restored_asset.is_file()
        and sha256_file(restored_asset) == fixture["asset_sha"]
        and restored_asset.stat().st_size == len("受管资产：名单".encode("utf-8")),
        str(restored_asset),
    )
    for rel, digest in (
        ("textbooks/blobs", fixture["original_sha"]),
        ("textbooks/normalized", fixture["normalized_sha"]),
        ("textbooks/normalized", fixture["source_map_sha"]),
        ("question-bank/blobs", fixture["question_sha"]),
    ):
        target = new_root / rel / digest
        check(f"v6.1l blob restored: {rel}/{digest[:8]}", target.is_file() and sha256_file(target) == digest, str(target))

    # 恢复目录里的教学库，其 file_assets 引用可被应用侧仓储读出（逐文件对账）
    from app.repositories.assets.file_assets import FileAssetsRepository

    teaching = TeachingCatalog(new_root / FOUR[3])
    teaching._migrated = True  # 只读打开已迁移的恢复副本
    record_row = FileAssetsRepository(teaching).get("asset-1")
    check(
        "v6.1m restored teaching registry row readable via repository",
        record_row is not None and record_row.blob_key == f"blobs/{fixture['asset_sha']}",
        str(record_row and record_row.blob_key),
    )
    teaching.close()


# --------------------------------------------------------------------------- 6② 缺库（CLI）


def part_missing_library_cli(root: Path) -> None:
    data_root = root / "data-missing"
    build_data_root(data_root)
    (data_root / "teaching" / "teaching.sqlite3").unlink()
    target = root / "archive-missing"
    env = os.environ.copy()
    env["ZQKY_DATA_DIR"] = str(data_root)
    cmd = [
        "uv",
        "run",
        "python",
        "../../scripts/rag/backup.py",
        "create",
        "--data-dir",
        str(data_root),
        "--into",
        str(target),
        "--label",
        "v00-missing",
    ]
    proc = subprocess.run(
        cmd, cwd=str(API_ROOT), env=env, capture_output=True, text=True, timeout=300
    )
    (EVIDENCE_DIR / "v6_cli_missing_library.txt").write_text(
        f"$ {' '.join(cmd)}\n[exit {proc.returncode}]\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}",
        encoding="utf-8",
    )
    check("v6.2a CLI exits non-zero", proc.returncode == 1, f"exit={proc.returncode}")
    check(
        "v6.2b CLI stdout does not claim success",
        "备份完成" not in proc.stdout,
        proc.stdout.strip().replace("\n", " | ")[:200],
    )
    check(
        "v6.2c CLI stderr names the missing library",
        "教学业务库缺失" in proc.stderr,
        proc.stderr.strip().replace("\n", " | ")[:300],
    )
    manifest_path = target / "manifest.json"
    check("v6.2d manifest written for the failure", manifest_path.is_file(), str(manifest_path))
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        check("v6.2e manifest status failed", manifest.get("status") == "failed", str(manifest.get("status")))
        check(
            "v6.2f manifest lists the missing library",
            any("教学业务库缺失" in item for item in manifest.get("failures", [])),
            str(manifest.get("failures")),
        )
        declared = {item["restorePath"] for item in manifest["files"]}
        check(
            "v6.2g missing library not silently declared as present",
            "teaching/teaching.sqlite3" not in declared,
            str(sorted(declared)),
        )
    failures, _notes = backup.verify_backup(target)
    check("v6.2h verify rejects the failed archive", any("status=failed" in item for item in failures), str(failures[:3]))


# --------------------------------------------------------------------------- 6③ 篡改


def part_tamper(root: Path) -> None:
    data_root = root / "data-tamper"
    build_data_root(data_root)
    archive = root / "archive-tamper"
    backup.create_backup(data_dir=data_root, target=archive, qdrant_client=FakeQdrant())
    asset_files = sorted((archive / "files" / "assets" / "blobs").iterdir())
    check("v6.3a archived asset blob present", len(asset_files) == 1, str(asset_files))
    victim = asset_files[0]
    payload = bytearray(victim.read_bytes())
    payload[0] ^= 0xFF
    victim.write_bytes(bytes(payload))
    failures, _notes = backup.verify_backup(archive)
    check(
        "v6.3b tampered asset bytes -> verify fails",
        any("受管" in item or "指纹不符" in item or "内容寻址不符" in item for item in failures),
        str(failures),
    )
    # 恢复也必须拒绝被篡改的归档（写文件前）
    new_root = root / "restored-tamper"
    try:
        backup.restore_backup(archive, new_root, isolated_qdrant="http://127.0.0.1:16333")
        record("v6.3c restore refuses tampered archive before writing", False, "no exception")
    except backup.BackupRefused as exc:
        record("v6.3c restore refuses tampered archive before writing", True, str(exc)[:160])
    except Exception as exc:  # noqa: BLE001
        record("v6.3c restore refuses tampered archive before writing", False, f"{type(exc).__name__}: {exc}"[:160])
    check("v6.3d refused restore wrote nothing", not new_root.exists(), str(new_root.exists()))


# --------------------------------------------------------------------------- 附加反例：删库再 verify


def part_removed_catalog(root: Path) -> None:
    data_root = root / "data-removed"
    build_data_root(data_root)
    archive = root / "archive-removed"
    backup.create_backup(data_dir=data_root, target=archive, qdrant_client=FakeQdrant())

    # 变体 A：只删文件，清单仍声明 → 缺失文件
    victim = archive / "sqlite" / "teaching.sqlite3"
    shutil.copy2(victim, root / "teaching-kept.sqlite3")
    victim.unlink()
    failures_a, _ = backup.verify_backup(archive)
    check(
        "v6.3e deleted archived teaching db -> verify fails (missing file)",
        any("缺失文件" in item and "teaching" in item for item in failures_a),
        str(failures_a),
    )
    shutil.copy2(root / "teaching-kept.sqlite3", victim)

    # 变体 B：同时删文件与清单条目 → 必须报"完整清单缺少必需文件"
    archive_b = root / "archive-removed-entry"
    shutil.copytree(archive, archive_b)
    (archive_b / "sqlite" / "teaching.sqlite3").unlink()
    manifest_path = archive_b / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = len(manifest["files"])
    manifest["files"] = [item for item in manifest["files"] if item.get("restorePath") != "teaching/teaching.sqlite3"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    failures_b, _ = backup.verify_backup(archive_b)
    check(
        "v6.3f teaching db removed from manifest too -> verify still fails",
        len(manifest["files"]) == before - 1
        and any("完整清单缺少必需文件：teaching/teaching.sqlite3" in item for item in failures_b),
        str(failures_b),
    )


# --------------------------------------------------------------------------- 6④ 缺资产恢复


def part_missing_asset_restore(root: Path) -> None:
    data_root = root / "data-missing-asset"
    build_data_root(data_root)
    archive = root / "archive-missing-asset"
    backup.create_backup(data_dir=data_root, target=archive, qdrant_client=FakeQdrant())

    # 往归档的教学库里加一条引用"归档里不存在的 blob"的资产行，并同步清单指纹
    teaching_archive = archive / "sqlite" / "teaching.sqlite3"
    ghost_sha = hashlib.sha256(b"never-archived").hexdigest()
    raw = sqlite3.connect(str(teaching_archive))
    try:
        raw.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES "
            "('asset-ghost','local','paper',?,?,'缺件.pdf','application/pdf',13,'2026-09-30T00:00:00Z')",
            (f"blobs/{ghost_sha}", ghost_sha),
        )
        raw.commit()
    finally:
        raw.close()
    manifest_path = archive / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if item.get("archivePath") == "sqlite/teaching.sqlite3":
            item["bytes"] = teaching_archive.stat().st_size
            item["sha256"] = sha256_file(teaching_archive)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    failures, _notes = backup.verify_backup(archive)
    check(
        "v6.4a crafted archive still passes verify (missing blob only derivable from teaching db)",
        failures == [],
        str(failures),
    )

    new_root = root / "restored-missing-asset"
    try:
        backup.restore_backup(archive, new_root, isolated_qdrant=FakeQdrant())
        record("v6.4b restore fails when a referenced asset is absent", False, "no exception")
    except backup.BackupFailed as exc:
        record("v6.4b restore fails when a referenced asset is absent", True, str(exc)[:200].replace("\n", " "))
    except Exception as exc:  # noqa: BLE001
        record("v6.4b restore fails when a referenced asset is absent", False, f"{type(exc).__name__}: {exc}"[:200])
    state_path = new_root / "restore-state.json"
    check("v6.4c restore-state.json exists", state_path.is_file(), str(state_path))
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        check("v6.4d restore-state stays incomplete", state.get("status") == "incomplete", str(state.get("status")))
        check(
            "v6.4e incomplete state records the missing asset",
            any("受管资产" in item for item in state.get("failures", [])),
            str(state.get("failures")),
        )
    try:
        require_data_root_ready(new_root)
        record("v6.4f incomplete restored root refuses startup", False, "no exception")
    except Exception as exc:  # noqa: BLE001
        check("v6.4f incomplete restored root refuses startup", getattr(exc, "code", "") == "DATA_RESTORE_INCOMPLETE", str(getattr(exc, "code", type(exc).__name__)))


# --------------------------------------------------------------------------- 6⑤ v2 / legacy


def _copy_catalogs(source_root: Path, target: Path, names: tuple[str, ...]) -> dict[str, str]:
    target.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    mapping = {
        "textbooks/catalog.sqlite3": "sqlite/textbooks-catalog.sqlite3",
        "question-bank/question-bank.sqlite3": "sqlite/question-bank.sqlite3",
    }
    for name in names:
        src = source_root / name
        dst = target / mapping[name]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[name] = sha256_file(dst)
    return hashes


def part_v2(root: Path) -> None:
    data_root = root / "data-v2"
    fixture = build_data_root(data_root)
    archive = root / "archive-v2"
    hashes = _copy_catalogs(data_root, archive, tuple(FOUR[:2]))
    files = [
        {
            "logicalRole": "textbook-catalog",
            "archivePath": "sqlite/textbooks-catalog.sqlite3",
            "restorePath": "textbooks/catalog.sqlite3",
            "bytes": (archive / "sqlite" / "textbooks-catalog.sqlite3").stat().st_size,
            "sha256": hashes["textbooks/catalog.sqlite3"],
        },
        {
            "logicalRole": "question-bank-catalog",
            "archivePath": "sqlite/question-bank.sqlite3",
            "restorePath": "question-bank/question-bank.sqlite3",
            "bytes": (archive / "sqlite" / "question-bank.sqlite3").stat().st_size,
            "sha256": hashes["question-bank/question-bank.sqlite3"],
        },
    ]
    # v2 语义：两库 + 各自 blob 树（无知识点库/教学库/受管资产）
    blob_plan = (
        ("textbook-blob", data_root / "textbooks" / "blobs" / fixture["original_sha"], "textbooks/blobs"),
        ("textbook-normalized", data_root / "textbooks" / "normalized" / fixture["normalized_sha"], "textbooks/normalized"),
        ("textbook-normalized", data_root / "textbooks" / "normalized" / fixture["source_map_sha"], "textbooks/normalized"),
        ("question-bank-blob", data_root / "question-bank" / "blobs" / fixture["question_sha"], "question-bank/blobs"),
    )
    for role, source, restore_dir in blob_plan:
        digest = sha256_file(source)
        archive_path = f"files/{role}/{digest}"
        target = archive / archive_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append(
            {
                "logicalRole": role,
                "archivePath": archive_path,
                "restorePath": f"{restore_dir}/{digest}",
                "bytes": target.stat().st_size,
                "sha256": digest,
            }
        )
    manifest = {
        "schemaVersion": 2,
        "status": "complete",
        "createdAt": "2026-09-29T00:00:00Z",
        "dataDir": str(data_root),
        "activeGenerationId": None,
        "qdrantUrl": "http://127.0.0.1:6333",
        "files": files,
        "collections": [],
        "failures": [],
    }
    (archive / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    failures, notes = backup.verify_backup(archive)
    check("v6.5a v2 manifest verifies", failures == [], str(failures))
    check(
        "v6.5b v2 verify notes it does not cover four libraries",
        any("不含知识点库/教学库" in item for item in notes),
        str(notes),
    )

    new_root = root / "restored-v2"
    state = backup.restore_backup(archive, new_root, isolated_qdrant=FakeQdrant())
    check("v6.5c v2 restore ends ready", state.get("status") == "ready", str(state.get("status")))
    restored = sorted(p.relative_to(new_root).as_posix() for p in new_root.rglob("*.sqlite3"))
    check(
        "v6.5d v2 restore writes exactly the two legacy databases",
        restored == ["question-bank/question-bank.sqlite3", "textbooks/catalog.sqlite3"],
        str(restored),
    )
    check(
        "v6.5d2 v2 restore copies its blob trees",
        (new_root / "textbooks" / "blobs" / fixture["original_sha"]).is_file()
        and (new_root / "question-bank" / "blobs" / fixture["question_sha"]).is_file(),
        "",
    )
    require_data_root_ready(new_root)

    # 负例：v2 清单缺少题库条目 → verify 失败
    archive_bad = root / "archive-v2-bad"
    shutil.copytree(archive, archive_bad)
    manifest_bad = json.loads((archive_bad / "manifest.json").read_text(encoding="utf-8"))
    manifest_bad["files"] = [item for item in manifest_bad["files"] if item["restorePath"] != "question-bank/question-bank.sqlite3"]
    (archive_bad / "manifest.json").write_text(json.dumps(manifest_bad, ensure_ascii=False, indent=2), encoding="utf-8")
    failures_bad, _ = backup.verify_backup(archive_bad)
    check(
        "v6.5e v2 without the question bank entry fails verify",
        any("完整清单缺少必需文件：question-bank/question-bank.sqlite3" in item for item in failures_bad),
        str(failures_bad),
    )


def part_legacy(root: Path) -> None:
    data_root = root / "data-legacy"
    fixture = build_data_root(data_root)
    archive = root / "archive-legacy"
    (archive / "sqlite").mkdir(parents=True, exist_ok=True)
    shutil.copy2(data_root / FOUR[0], archive / "sqlite" / "catalog.sqlite3")
    shutil.copy2(data_root / FOUR[1], archive / "sqlite" / "question-bank.sqlite3")
    (archive / "files" / "textbooks-blobs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        data_root / "textbooks" / "blobs" / fixture["original_sha"],
        archive / "files" / "textbooks-blobs" / fixture["original_sha"],
    )
    (archive / "files" / "textbooks-normalized").mkdir(parents=True, exist_ok=True)
    for digest in (fixture["normalized_sha"], fixture["source_map_sha"]):
        shutil.copy2(
            data_root / "textbooks" / "normalized" / digest,
            archive / "files" / "textbooks-normalized" / digest,
        )
    (archive / "files" / "question-bank-blobs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        data_root / "question-bank" / "blobs" / fixture["question_sha"],
        archive / "files" / "question-bank-blobs" / fixture["question_sha"],
    )
    legacy = {
        "createdAt": "2026-09-20T00:00:00Z",
        "dataDir": str(data_root),
        "entries": [
            {"kind": "sqlite", "name": "教材目录", "path": "sqlite/catalog.sqlite3"},
            {"kind": "sqlite", "name": "题库", "path": "sqlite/question-bank.sqlite3"},
            {"kind": "tree", "name": "textbooks-blobs"},
            {"kind": "tree", "name": "textbooks-normalized"},
            {"kind": "tree", "name": "question-bank-blobs"},
        ],
    }
    (archive / "manifest.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

    failures, notes = backup.verify_backup(archive)
    check("v6.6a legacy manifest verifies (read-only compatibility)", failures == [], str(failures))
    check(
        "v6.6b legacy verify notes legacy_revalidated",
        any("legacy_revalidated" in item for item in notes),
        str(notes),
    )

    new_root = root / "restored-legacy"
    state = backup.restore_backup(archive, new_root, isolated_qdrant=FakeQdrant())
    check("v6.6c legacy restore ends ready", state.get("status") == "ready", str(state.get("status")))
    check(
        "v6.6d legacy restore keeps the old layout paths",
        (new_root / "textbooks" / "catalog.sqlite3").is_file()
        and (new_root / "question-bank" / "question-bank.sqlite3").is_file(),
        str(sorted(p.relative_to(new_root).as_posix() for p in new_root.rglob("*.sqlite3"))),
    )
    check(
        "v6.6e legacy restore copied the content-addressed blob trees",
        (new_root / "textbooks" / "blobs" / fixture["original_sha"]).is_file()
        and (new_root / "question-bank" / "blobs" / fixture["question_sha"]).is_file(),
        "",
    )
    try:
        require_data_root_ready(new_root)
        record("v6.6f legacy restored dir passes the startup gate", True)
    except Exception as exc:  # noqa: BLE001
        record("v6.6f legacy restored dir passes the startup gate", False, repr(exc))


def main() -> None:
    root = temp_root("v6")
    try:
        part_full_chain(root)
        part_missing_library_cli(root)
        part_tamper(root)
        part_removed_catalog(root)
        part_missing_asset_restore(root)
        part_v2(root)
        part_legacy(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
