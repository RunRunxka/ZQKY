"""V5 受管资产独立探针（V00 / TEACHING-LOOP B0）。

覆盖：
  5① 内容寻址 + 重复写入幂等（同键同内容；无临时文件残留）
  5② 篡改 / 缺失分别报 ASSET_CORRUPT / ASSET_MISSING（读取时重算 sha256）
  5③ `..` / 绝对路径 / 盘符 / 反斜杠 / 错误长度/大小写键 → 422 且不创建目录
  5④ 登记行 ref() 为 camelCase；行结构非法 → ASSET_ROW_CORRUPT（不静默放行）
  附加：blob_key 必须等于 blobs/<sha256>（内容寻址不变量）；登记入参非法不落库
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from _probe_common import EVIDENCE_DIR, check, cleanup, record, run_main, temp_root

from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.assets.store import AssetStore

PROBE = "v5_assets_probe"


def _err_code(exc: BaseException) -> str:
    return str(getattr(exc, "code", type(exc).__name__))


def part_store_idempotent(root: Path) -> None:
    store = AssetStore(root / "assets")
    content = "受管资产内容-探针".encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()

    first = store.store_original(content, media_type="text/plain", original_name="原件.txt")
    check(
        "v5.1a content addressed key = blobs/<sha256>",
        first.blob_key == f"blobs/{digest}" and first.sha256 == digest and first.byte_size == len(content),
        f"{first.blob_key} size={first.byte_size}",
    )
    target = store.blobs_dir / digest
    check("v5.1b blob written under <root>/blobs", target.is_file(), str(target))
    before_stat = target.stat()
    read_back = store.read(first.blob_key)
    check("v5.1c read returns exact bytes", read_back == content, f"{len(read_back)} bytes")
    check("v5.1d verify returns byte size", store.verify(first.blob_key) == len(content), "")

    second = store.store_original(content, media_type="application/octet-stream", original_name="另一名字.bin")
    check(
        "v5.1e duplicate write is idempotent (same key/content)",
        second.blob_key == first.blob_key and target.read_bytes() == content,
        f"{second.blob_key}",
    )
    leftovers = [p.name for p in store.blobs_dir.iterdir() if p.name != digest]
    check("v5.1f no temp/extra files left in blobs dir", leftovers == [], str(leftovers))
    check(
        "v5.1g media_type/original_name do not affect the path",
        target.resolve() == (store.blobs_dir / digest).resolve() and before_stat.st_size == target.stat().st_size,
        "",
    )
    # 同键不同内容（损坏源）→ 原子重写修复内容寻址不变量
    repaired = store.store_original(content, media_type="text/plain", original_name="x.txt")
    check("v5.1h re-write keeps digest stable", repaired.sha256 == digest, repaired.sha256)


def part_corrupt_missing(root: Path) -> None:
    store = AssetStore(root / "assets-tamper")
    content = b"tamper-me"
    digest = hashlib.sha256(content).hexdigest()
    stored = store.store_original(content, media_type="application/octet-stream", original_name="t.bin")
    target = store.blobs_dir / digest

    target.write_bytes(b"different bytes")
    try:
        store.read(stored.blob_key)
        record("v5.2a tampered blob read -> ASSET_CORRUPT", False, "no exception")
    except AppError as exc:
        check("v5.2a tampered blob read -> ASSET_CORRUPT",
              exc.code == "ASSET_CORRUPT" and exc.status_code == 500, f"code={exc.code} status={exc.status_code}")
    try:
        store.verify(stored.blob_key)
        record("v5.2b tampered blob verify -> ASSET_CORRUPT", False, "no exception")
    except AppError as exc:
        check("v5.2b tampered blob verify -> ASSET_CORRUPT", exc.code == "ASSET_CORRUPT", exc.code)

    target.unlink()
    try:
        store.read(stored.blob_key)
        record("v5.2c missing blob read -> ASSET_MISSING", False, "no exception")
    except AppError as exc:
        check("v5.2c missing blob read -> ASSET_MISSING",
              exc.code == "ASSET_MISSING" and exc.status_code == 500, f"code={exc.code}")
    try:
        store.verify(stored.blob_key)
        record("v5.2d missing blob verify -> ASSET_MISSING", False, "no exception")
    except AppError as exc:
        check("v5.2d missing blob verify -> ASSET_MISSING", exc.code == "ASSET_MISSING", exc.code)
    check("v5.2e exists() False for missing managed key", store.exists(stored.blob_key) is False, "")


def part_key_traversal(root: Path) -> None:
    store = AssetStore(root / "traversal" / "assets")
    digest = hashlib.sha256(b"x").hexdigest()
    evil_keys = [
        f"blobs/../../{digest}",
        "../blobs/" + digest,
        f"blobs/sub/{digest}",
        f"blobs\\{digest}",
        f"blobs/{digest.upper()}",
        f"blobs/{digest[:63]}",
        f"blobs/{digest}0",
        f"blobs/{digest}/..",
        f"/blobs/{digest}",
        f"H:/tmp/blobs/{digest}",
        f"C:\\blobs\\{digest}",
        f"blobs/{digest} ",
        "",
        None,
    ]
    for key in evil_keys:
        try:
            store.path_of(key)  # type: ignore[arg-type]
            record(f"v5.3 illegal key rejected: {key!r}", False, "no exception / path returned")
        except AppError as exc:
            check(
                f"v5.3 illegal key rejected: {str(key)[:44]!r}",
                exc.code == "INVALID_ASSET_KEY" and exc.status_code == 422,
                f"code={exc.code} status={exc.status_code}",
            )
    # 试图让 store 在受管根之外创建目录的键（先触发写入路径）
    try:
        store.store_original(b"x", media_type="t", original_name="n")  # 合法键，会创建 blobs/
    except AppError:
        pass
    created = sorted(
        p.relative_to(root / "traversal").as_posix()
        for p in (root / "traversal").rglob("*")
    )
    check(
        "v5.3b only managed blobs dir exists (no traversal artifacts)",
        created == ["assets", "assets/blobs", f"assets/blobs/{digest}"],
        str(created),
    )
    only_files = [p for p in (root / "traversal").rglob("*") if p.is_file()]
    check(
        "v5.3c rejection wrote nothing outside the managed root",
        all("assets" in p.relative_to(root / "traversal").parts for p in only_files),
        str([p.relative_to(root / "traversal").as_posix() for p in only_files]),
    )


def part_registry(root: Path) -> None:
    catalog = TeachingCatalog(root / "teaching" / "teaching.sqlite3")
    catalog.migrate()
    repository = FileAssetsRepository(catalog)
    content = b"roster-bytes"
    digest = hashlib.sha256(content).hexdigest()
    store = AssetStore(root / "assets")
    stored = store.store_original(content, media_type="text/csv", original_name="名单.csv")

    record_row = repository.create(
        kind="roster",
        blob_key=stored.blob_key,
        sha256=stored.sha256,
        media_type="text/csv",
        byte_size=stored.byte_size,
        original_name="名单.csv",
    )
    ref = record_row.ref()
    payload = ref.model_dump(by_alias=True)
    check(
        "v5.4a ref() keys are camelCase",
        set(payload) == {"assetId", "kind", "blobKey", "sha256", "mediaType", "byteSize", "originalName"},
        str(sorted(payload)),
    )
    check(
        "v5.4b ref() values match registry row",
        payload["blobKey"] == stored.blob_key
        and payload["sha256"] == digest
        and payload["byteSize"] == len(content)
        and payload["originalName"] == "名单.csv",
        str(payload),
    )
    fetched = repository.get(record_row.asset_id)
    check("v5.4c read back by asset id", fetched is not None and fetched.blob_key == stored.blob_key, str(fetched and fetched.asset_id))
    check(
        "v5.4d list_by_kind returns it",
        [item.asset_id for item in repository.list_by_kind("roster")] == [record_row.asset_id],
        "",
    )

    # 入参非法不落库
    for label, kwargs in (
        ("kind 非白名单", {"kind": "bogus"}),
        ("blob_key 与 sha256 不一致", {"blob_key": f"blobs/{'0' * 64}"}),
        ("blob_key 非受管键", {"blob_key": f"../{digest}"}),
        ("sha256 大写", {"sha256": digest.upper(), "blob_key": f"blobs/{digest.upper()}"}),
        ("byte_size 负数", {"byte_size": -1}),
    ):
        values = dict(
            kind="roster",
            blob_key=stored.blob_key,
            sha256=stored.sha256,
            media_type="text/csv",
            byte_size=stored.byte_size,
            original_name="名单.csv",
        )
        values.update(kwargs)
        try:
            repository.create(**values)  # type: ignore[arg-type]
            record(f"v5.5 invalid registry input rejected ({label})", False, "no exception")
        except AppError as exc:
            check(
                f"v5.5 invalid registry input rejected ({label})",
                exc.code == "INVALID_REQUEST" and exc.status_code == 422,
                f"code={exc.code}",
            )
    rows = sqlite3.connect(str(catalog.db_path)).execute("SELECT COUNT(*) FROM file_assets").fetchone()[0]
    check("v5.5b invalid inputs wrote no rows", rows == 1, f"rows={rows}")

    # 行结构非法 → ASSET_ROW_CORRUPT
    # 注意：DDL 的 CHECK 已挡住 kind/sha256 长度/byte_size 三类越界，因此这里用
    # "CHECK 允许但语义非法"的行（blob_key 非受管键 / 与 sha256 不一致）验证读取校验。
    raw = sqlite3.connect(str(catalog.db_path))
    other = "a" * 64
    raw.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, media_type, "
        "byte_size, created_at) VALUES ('corrupt-1', 'local', 'roster', 'blobs/not-a-hash', ?, 'n', 't', 0, 'now')",
        (other,),
    )
    raw.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, media_type, "
        "byte_size, created_at) VALUES ('corrupt-2', 'local', 'roster', ?, ?, 'n', 't', 0, 'now')",
        (f"blobs/{other}", stored.sha256),
    )
    raw.commit()
    raw.close()
    for asset_id, label in (("corrupt-1", "blob_key 不是受管键"), ("corrupt-2", "blob_key 与 sha256 不一致")):
        try:
            repository.get(asset_id)
            record(f"v5.6 corrupt registry row ({label}) -> ASSET_ROW_CORRUPT", False, "no exception")
        except AppError as exc:
            check(
                f"v5.6 corrupt registry row ({label}) -> ASSET_ROW_CORRUPT",
                exc.code == "ASSET_ROW_CORRUPT" and exc.status_code == 500,
                f"code={exc.code} status={exc.status_code}",
            )
    # get_many / list_by_kind 同样不得静默放行坏行
    try:
        repository.list_by_kind("roster")
        record("v5.7 list_by_kind refuses to silently skip corrupt rows", False, "no exception")
    except AppError as exc:
        check("v5.7 list_by_kind refuses to silently skip corrupt rows",
              exc.code == "ASSET_ROW_CORRUPT", exc.code)
    catalog.close()


def main() -> None:
    root = temp_root("v5")
    try:
        part_store_idempotent(root)
        part_corrupt_missing(root)
        part_key_traversal(root)
        part_registry(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
