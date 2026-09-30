"""受管资产：内容寻址、幂等、篡改/缺失检测、路径穿越拒绝与教学库登记。

全部在 pytest ``tmp_path`` 内构造（``<root>/assets`` + 临时教学库），不联网、
不读正式 ``.local-data``。对应任务卡 §3.7 与验收 A8。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.repositories.assets.file_assets import FileAssetsRepository
from app.repositories.teaching.catalog import TeachingCatalog
from app.services.assets.store import AssetStore, sha256_bytes

PAYLOAD = "受管资产原文：第一行\n第二行\n".encode("utf-8")


def make_store(tmp_path: Path, *, area: str = "assets") -> AssetStore:
    return AssetStore(tmp_path / area)


def make_repo(tmp_path: Path) -> tuple[TeachingCatalog, FileAssetsRepository]:
    catalog = TeachingCatalog(tmp_path / "teaching" / "teaching.sqlite3")
    catalog.migrate()
    return catalog, FileAssetsRepository(catalog)


# --------------------------------------------------------------------------- 本体


def test_store_original_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    digest = sha256_bytes(PAYLOAD)

    stored = store.store_original(
        PAYLOAD, media_type="text/markdown", original_name="名单.md"
    )
    assert stored.blob_key == f"blobs/{digest}"
    assert stored.sha256 == digest
    assert stored.byte_size == len(PAYLOAD)

    target = store.path_of(stored.blob_key)
    assert target == store.blobs_dir / digest
    assert target.parent == store.blobs_dir
    assert target.is_file()
    assert target.read_bytes() == PAYLOAD
    assert store.read(stored.blob_key) == PAYLOAD
    assert store.verify(stored.blob_key) == len(PAYLOAD)
    assert store.exists(stored.blob_key) is True

    # 同内容重复写入幂等：同键、字节数不变、目录里只有一个文件
    again = store.store_original(
        PAYLOAD, media_type="application/octet-stream", original_name="另一个名字.bin"
    )
    assert again == stored
    assert [item.name for item in store.blobs_dir.iterdir()] == [digest]

    # 不同内容得到不同键，互不影响
    other = store.store_original(b"other", media_type="text/plain", original_name="o.txt")
    assert other.blob_key != stored.blob_key
    assert sorted(item.name for item in store.blobs_dir.iterdir()) == sorted(
        [digest, other.sha256]
    )

    # media_type / original_name 只做登记校验，不参与路径拼接
    with pytest.raises(AppError) as excinfo:
        store.store_original(PAYLOAD, media_type="", original_name="x")
    assert excinfo.value.code == "INVALID_REQUEST"
    assert excinfo.value.status_code == 422
    with pytest.raises(AppError) as excinfo:
        store.store_original(PAYLOAD, media_type="text/plain", original_name="   ")
    assert excinfo.value.code == "INVALID_REQUEST"
    with pytest.raises(AppError) as excinfo:
        store.store_original("不是字节", media_type="text/plain", original_name="x")  # type: ignore[arg-type]
    assert excinfo.value.code == "INVALID_REQUEST"


def test_read_and_verify_detect_tampered_blob(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    stored = store.store_original(PAYLOAD, media_type="text/plain", original_name="a.txt")
    target = store.path_of(stored.blob_key)

    # 同长度篡改与追加字节都必须被读取/校验发现
    target.write_bytes(bytes([PAYLOAD[0] ^ 0xFF]) + PAYLOAD[1:])
    assert store.exists(stored.blob_key) is True
    with pytest.raises(AppError) as excinfo:
        store.read(stored.blob_key)
    assert excinfo.value.code == "ASSET_CORRUPT"
    assert excinfo.value.status_code == 500
    with pytest.raises(AppError) as excinfo:
        store.verify(stored.blob_key)
    assert excinfo.value.code == "ASSET_CORRUPT"

    target.write_bytes(PAYLOAD + b"x")
    with pytest.raises(AppError) as excinfo:
        store.read(stored.blob_key)
    assert excinfo.value.code == "ASSET_CORRUPT"

    # 重新写入同内容会修复被篡改的同名文件（内容寻址的幂等语义）
    repaired = store.store_original(
        PAYLOAD, media_type="text/plain", original_name="a.txt"
    )
    assert repaired == stored
    assert store.read(stored.blob_key) == PAYLOAD


def test_read_and_verify_report_missing_blob(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    absent_key = f"blobs/{'b' * 64}"

    with pytest.raises(AppError) as excinfo:
        store.read(absent_key)
    assert excinfo.value.code == "ASSET_MISSING"
    assert excinfo.value.status_code == 500
    with pytest.raises(AppError) as excinfo:
        store.verify(absent_key)
    assert excinfo.value.code == "ASSET_MISSING"
    assert store.exists(absent_key) is False


def test_path_of_rejects_traversal_and_invalid_keys_without_creating_dirs(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    digest = "a" * 64
    invalid_keys = [
        "",
        "blobs",
        "blobs/",
        "blobs//" + digest,
        "blobs/../" + digest,
        "blobs/" + digest + "/x",
        "../" + digest,
        "/blobs/" + digest,
        "C:/blobs/" + digest,
        "C:\\blobs\\" + digest,
        "blobs\\" + digest,
        "blobs/" + digest.upper(),
        "blobs/" + "a" * 63,
        "blobs/" + "a" * 65,
        "blobs/" + "g" * 64,
        " blobs/" + digest,
        "blobs/" + digest + " ",
    ]
    for blob_key in invalid_keys:
        with pytest.raises(AppError) as excinfo:
            store.path_of(blob_key)
        assert excinfo.value.code == "INVALID_ASSET_KEY", blob_key
        assert excinfo.value.status_code == 422, blob_key
        with pytest.raises(AppError):
            store.exists(blob_key)

    with pytest.raises(AppError) as excinfo:
        store.path_of(123)  # type: ignore[arg-type]
    assert excinfo.value.code == "INVALID_ASSET_KEY"

    # 非法键不得创建任何目录或文件，也不得写出受管根之外
    assert not (tmp_path / "assets").exists()
    assert not (tmp_path / "evil").exists()

    # 合法键可以在尚未落盘时解析（不创建目录）
    assert store.path_of(f"blobs/{digest}") == tmp_path / "assets" / "blobs" / digest
    assert not (tmp_path / "assets").exists()


# --------------------------------------------------------------------------- 登记


def test_repository_create_persists_fields_and_ref_is_camel_case(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    stored = store.store_original(
        PAYLOAD, media_type="text/csv", original_name="名单.csv"
    )
    catalog, repo = make_repo(tmp_path)

    record = repo.create(
        kind="roster",
        blob_key=stored.blob_key,
        sha256=stored.sha256,
        media_type="text/csv",
        byte_size=stored.byte_size,
        original_name="名单.csv",
    )
    assert record.asset_id
    assert record.owner_id == "local"
    assert record.kind == "roster"
    assert record.blob_key == stored.blob_key
    assert record.sha256 == stored.sha256
    assert record.media_type == "text/csv"
    assert record.byte_size == len(PAYLOAD)
    assert record.original_name == "名单.csv"
    assert record.created_at.endswith("Z")

    loaded = repo.get(record.asset_id)
    assert loaded == record
    assert repo.get("not-there") is None

    ref = record.ref()
    assert ref.model_dump(by_alias=True) == {
        "assetId": record.asset_id,
        "kind": "roster",
        "blobKey": stored.blob_key,
        "sha256": stored.sha256,
        "mediaType": "text/csv",
        "byteSize": len(PAYLOAD),
        "originalName": "名单.csv",
    }

    # 落库字段逐列核对（snake_case 列名与记录一一对应）
    connection = sqlite3.connect(str(catalog.db_path))
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM file_assets WHERE id = ?", (record.asset_id,)
        ).fetchone()
    finally:
        connection.close()
    assert dict(row) == {
        "id": record.asset_id,
        "owner_id": "local",
        "kind": "roster",
        "blob_key": stored.blob_key,
        "sha256": stored.sha256,
        "original_name": "名单.csv",
        "media_type": "text/csv",
        "byte_size": len(PAYLOAD),
        "created_at": record.created_at,
    }

    # 批量读取与按类别列举
    second = repo.create(
        kind="paper",
        blob_key=stored.blob_key,
        sha256=stored.sha256,
        media_type="text/csv",
        byte_size=stored.byte_size,
        original_name="原卷.csv",
        owner_id="teacher-1",
        asset_id="asset-fixed-id",
    )
    assert second.asset_id == "asset-fixed-id"
    assert set(repo.get_many([record.asset_id, "asset-fixed-id", "missing"])) == {
        record.asset_id,
        "asset-fixed-id",
    }
    assert repo.get_many([]) == {}
    assert [item.asset_id for item in repo.list_by_kind("roster")] == [record.asset_id]
    assert repo.list_by_kind("paper")[0].asset_id == "asset-fixed-id"
    assert repo.list_by_kind("export") == []


def test_repository_rejects_invalid_input_without_writing(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    stored = store.store_original(PAYLOAD, media_type="text/plain", original_name="a.txt")
    _catalog, repo = make_repo(tmp_path)
    base = {
        "kind": "attachment",
        "blob_key": stored.blob_key,
        "sha256": stored.sha256,
        "media_type": "text/plain",
        "byte_size": stored.byte_size,
        "original_name": "a.txt",
    }

    overrides = [
        {"kind": "scores"},
        {"kind": ""},
        {"sha256": "a" * 63},
        {"sha256": "A" * 64},
        {"sha256": "not-a-hash"},
        {"blob_key": "../evil"},
        {"blob_key": "blobs/../" + stored.sha256},
        {"blob_key": "blobs/" + "B" * 64},
        {"blob_key": f"blobs/{'c' * 64}"},  # 形状合法但与 sha256 不一致
        {"byte_size": -1},
        {"media_type": "  "},
        {"original_name": ""},
        {"owner_id": ""},
    ]
    for override in overrides:
        with pytest.raises(AppError) as excinfo:
            repo.create(**{**base, **override})
        assert excinfo.value.code == "INVALID_REQUEST", override
        assert excinfo.value.status_code == 422, override

    with pytest.raises(AppError) as excinfo:
        repo.list_by_kind("bogus")
    assert excinfo.value.code == "INVALID_REQUEST"
    with pytest.raises(AppError):
        repo.list_by_kind("roster", limit=0)
    with pytest.raises(AppError):
        repo.list_by_kind("roster", limit=10_000)
    assert repo.list_by_kind("attachment") == []


def test_create_in_rolls_back_with_domain_transaction(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    stored = store.store_original(PAYLOAD, media_type="text/plain", original_name="a.txt")
    catalog, repo = make_repo(tmp_path)
    kwargs = {
        "kind": "attachment",
        "blob_key": stored.blob_key,
        "sha256": stored.sha256,
        "media_type": "text/plain",
        "byte_size": stored.byte_size,
        "original_name": "a.txt",
    }

    # 外层域事务在 create_in 之后抛错：资产行必须一起回滚
    with pytest.raises(RuntimeError, match="域写入失败"):
        with catalog.write_transaction() as conn:
            repo.create_in(conn, asset_id="asset-rollback", **kwargs)
            count = conn.execute(
                "SELECT COUNT(*) FROM file_assets WHERE id = 'asset-rollback'"
            ).fetchone()[0]
            assert count == 1  # 事务内（同一连接）可见
            raise RuntimeError("域写入失败")
    assert repo.get("asset-rollback") is None

    # 非法输入在事务内抛出也不留下任何行
    with pytest.raises(AppError):
        with catalog.write_transaction() as conn:
            repo.create_in(conn, **{**kwargs, "kind": "bogus"})
    assert repo.list_by_kind("attachment") == []

    # 正常提交路径：create_in 随外层事务一起生效
    with catalog.write_transaction() as conn:
        record = repo.create_in(conn, asset_id="asset-committed", **kwargs)
    assert record.asset_id == "asset-committed"
    assert repo.get("asset-committed") == record

    connection = sqlite3.connect(str(catalog.db_path))
    try:
        total = connection.execute("SELECT COUNT(*) FROM file_assets").fetchone()[0]
    finally:
        connection.close()
    assert total == 1


def test_corrupt_rows_raise_asset_row_corrupt(tmp_path: Path) -> None:
    """绕过 CHECK 直接写入非法行：读取必须报 ASSET_ROW_CORRUPT，不得静默放行。"""
    catalog, repo = make_repo(tmp_path)
    connection = sqlite3.connect(str(catalog.db_path))
    try:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "bad-kind",
                "local",
                "bogus",
                f"blobs/{'a' * 64}",
                "a" * 64,
                "x.txt",
                "text/plain",
                1,
                "2026-09-30T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "bad-hash",
                "local",
                "roster",
                f"blobs/{'b' * 64}",
                "abc",
                "x.txt",
                "text/plain",
                1,
                "2026-09-30T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "bad-addressing",
                "local",
                "roster",
                f"blobs/{'d' * 64}",
                f"{'b' * 64}",
                "x.txt",
                "text/plain",
                1,
                "2026-09-30T00:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    for asset_id in ("bad-kind", "bad-hash", "bad-addressing"):
        with pytest.raises(AppError) as excinfo:
            repo.get(asset_id)
        assert excinfo.value.code == "ASSET_ROW_CORRUPT", asset_id
        assert excinfo.value.status_code == 500, asset_id
    with pytest.raises(AppError) as excinfo:
        repo.list_by_kind("roster")
    assert excinfo.value.code == "ASSET_ROW_CORRUPT"
