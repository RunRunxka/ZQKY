"""教材与题库的本地备份 / 恢复。

原则（与 docs/PLAN.md §10.3 一致）：
- SQLite 用 ``VACUUM INTO`` 做一致性备份，**不直接复制正在写入的 WAL 文件**；
- Qdrant 用官方 snapshot 接口导出，恢复时先写新 collection 再校验点数；
- 恢复**只写新目录**，不覆盖正在使用的数据；已存在同名目标时拒绝执行；
- 备份清单记录每个文件的 sha256 与当前索引代，凭证（apps/api/.env）**不入清单**。

用法::

    uv run --directory apps/api python ../../scripts/rag/backup.py create --label pre-migration
    uv run --directory apps/api python ../../scripts/rag/backup.py verify --path <备份目录>
    uv run --directory apps/api python ../../scripts/rag/backup.py restore --path <备份目录> --into <新目录>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import httpx  # noqa: E402

from app.core.config import Settings  # noqa: E402

BACKUP_ROOT = REPO_ROOT / "_work" / "rag-backups"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sqlite_backup(source: Path, target: Path) -> None:
    """用 VACUUM INTO 生成一致性快照（WAL 中已提交的数据一并包含）。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    connection = sqlite3.connect(str(source))
    try:
        connection.execute("VACUUM INTO ?", (str(target),))
    finally:
        connection.close()


def copy_tree(source: Path, target: Path) -> int:
    if not source.exists():
        return 0
    count = 0
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        count += 1
    return count


def qdrant_snapshots(base_url: str, target: Path) -> dict:
    """对每个 collection 取 snapshot 并下载；返回 {collection: 文件相对路径}。"""
    target.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    with httpx.Client(base_url=base_url, timeout=300) as client:
        collections = client.get("/collections").json()["result"]["collections"]
        for entry in collections:
            name = entry["name"]
            if not name.startswith("textbooks_"):
                # 只备份教材 collection；其他服务的集合不归本批
                continue
            created = client.post(f"/collections/{name}/snapshots").json()["result"]
            snapshot_name = created["name"]
            response = client.get(f"/collections/{name}/snapshots/{snapshot_name}")
            response.raise_for_status()
            file_path = target / f"{name}__{snapshot_name}"
            file_path.write_bytes(response.content)
            result[name] = str(file_path.relative_to(target))
            client.delete(f"/collections/{name}/snapshots/{snapshot_name}")
    return result


def active_generation(catalog_path: Path) -> str | None:
    if not catalog_path.exists():
        return None
    connection = sqlite3.connect(str(catalog_path))
    try:
        row = connection.execute(
            "SELECT active_generation_id FROM catalog_state WHERE id = 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def create_backup(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.data_dir:
        settings = settings.__class__(**{**settings.__dict__, "data_dir": Path(args.data_dir)})
    stamp = time.strftime("%Y%m%d-%H%M%S")
    label = f"-{args.label}" if args.label else ""
    target = Path(args.into) if args.into else BACKUP_ROOT / f"rag-{stamp}{label}"
    if target.exists():
        print(f"备份目录已存在，拒绝覆盖：{target}", file=sys.stderr)
        return 2
    target.mkdir(parents=True)

    textbooks = settings.textbooks_root
    question_bank = settings.question_bank_root
    entries: list[dict] = []

    for name, db_path, relative in (
        ("textbooks", textbooks / "catalog.sqlite3", "sqlite/catalog.sqlite3"),
        ("question-bank", question_bank / "question-bank.sqlite3", "sqlite/question-bank.sqlite3"),
    ):
        if not db_path.exists():
            entries.append({"kind": "sqlite", "name": name, "skipped": "数据库不存在"})
            continue
        destination = target / relative
        sqlite_backup(db_path, destination)
        entries.append(
            {"kind": "sqlite", "name": name, "path": relative, "sha256": sha256_file(destination)}
        )

    for name, source_root in (
        ("textbooks-blobs", textbooks / "blobs"),
        ("textbooks-normalized", textbooks / "normalized"),
        ("question-bank-blobs", question_bank / "blobs"),
    ):
        count = copy_tree(source_root, target / "files" / name)
        entries.append({"kind": "tree", "name": name, "files": count})

    try:
        snapshots = qdrant_snapshots(settings.qdrant_url, target / "qdrant")
    except Exception as exc:  # Qdrant 不可用不阻断 SQLite/原件备份，但如实记录
        snapshots = {}
        entries.append({"kind": "qdrant", "error": f"{type(exc).__name__}: {exc}"})
    for name, relative in snapshots.items():
        entries.append(
            {
                "kind": "qdrant",
                "name": name,
                "path": f"qdrant/{relative}",
                "sha256": sha256_file(target / "qdrant" / relative),
            }
        )

    manifest = {
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "label": args.label or "",
        "dataDir": str(settings.data_dir),
        "activeGenerationId": active_generation(textbooks / "catalog.sqlite3"),
        "qdrantUrl": settings.qdrant_url,
        "entries": entries,
        "note": "凭证（apps/api/.env）不在本清单内；恢复只写新目录。",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"备份完成：{target}")
    for entry in entries:
        print("  ", entry)
    return 0


def verify_backup(args: argparse.Namespace) -> int:
    root = Path(args.path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    for entry in manifest["entries"]:
        relative = entry.get("path")
        if not relative:
            continue
        target = root / relative
        if not target.exists():
            failures.append(f"缺失：{relative}")
            continue
        if "sha256" in entry and sha256_file(target) != entry["sha256"]:
            failures.append(f"指纹不符：{relative}")
    print(f"清单条目：{len(manifest['entries'])}；失败：{len(failures)}")
    for item in failures:
        print("  -", item)
    return 0 if not failures else 1


def restore_backup(args: argparse.Namespace) -> int:
    root = Path(args.path)
    into = Path(args.into)
    if into.exists():
        print(f"恢复目标已存在，拒绝覆盖：{into}", file=sys.stderr)
        return 2
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    into.mkdir(parents=True)
    shutil.copytree(root / "sqlite", into / "sqlite")
    for name in ("textbooks-blobs", "textbooks-normalized", "question-bank-blobs"):
        source = root / "files" / name
        if source.exists():
            shutil.copytree(source, into / "files" / name)
    if (root / "qdrant").exists():
        shutil.copytree(root / "qdrant", into / "qdrant")
    (into / "restore-manifest.json").write_text(
        json.dumps(
            {
                "restoredFrom": str(root),
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "activeGenerationId": manifest.get("activeGenerationId"),
                "note": "已恢复到新目录；把 --data-dir 指向该目录即可用，正式数据未被覆盖。",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"已恢复到新目录：{into}")
    print("Qdrant 需按 snapshot 单独恢复（见目录内 qdrant/），本命令不写正式 collection。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="教材/题库备份与恢复")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="创建备份")
    create.add_argument("--label", help="备份标签（写入目录名与清单）")
    create.add_argument("--into", help="指定备份目录（默认 _work/rag-backups/…）")
    create.add_argument("--data-dir", help="数据根目录")
    create.set_defaults(func=create_backup)
    verify = sub.add_parser("verify", help="校验备份指纹")
    verify.add_argument("--path", required=True)
    verify.set_defaults(func=verify_backup)
    restore = sub.add_parser("restore", help="恢复到新目录")
    restore.add_argument("--path", required=True)
    restore.add_argument("--into", required=True)
    restore.set_defaults(func=restore_backup)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
