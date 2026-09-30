"""V1 迁移与门控探针（TEACHING-LOOP B1 / V00 独立验收）。

不复用实现者 ``test_b1_migrations.py`` 的断言，独立复现：
  ① 新库应用 B1 迁移后新表齐备（知识点 7 表 / 教学 5 表 + 触发器 + 部分唯一索引）
  ② 「仅 B0 结构」的旧库通过启动门控（不判损坏），迁移后补齐
  ③ 重复应用幂等
  ④ 中途失败整体回滚（注入一条先建表后失败的迁移）
  ⑤ 0001 四条散列自算 + B0 证据交叉核对 + 正式库 schema_migrations 只读对比
  ⑥ 损坏 / 结构不符 / 散列漂移的库仍被拒
  ⑦ 反例：0003（裸 ALTER）的宽容性——注册表缺 0003 且列已存在时的行为
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import (  # noqa: E402
    EVIDENCE_DIR,
    REPO_ROOT,
    Probe,
    ensure_api_on_path,
    temp_data_root,
)

p = Probe("v1_migrations")
root = temp_data_root("v1")  # 必须先设 ZQKY_DATA_DIR 才能导入 app.*
ensure_api_on_path()

from app.core.database_gate import DatabaseExpectation, verify_existing_database  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.migrations import (  # noqa: E402
    REGISTERED_MIGRATIONS,
    apply_migrations,
    applied_migrations,
    pending_migrations,
    verify_migrations,
)
from app.core.migrations.base import Migration, statement_digest  # noqa: E402
from app.repositories.knowledge.catalog import KnowledgeCatalog  # noqa: E402
from app.repositories.knowledge.imports import (  # noqa: E402
    ImportRowInput,
    KnowledgeImportRepository,
)
from app.repositories.knowledge.schema import REQUIRED_TABLES as KNOWLEDGE_REQUIRED  # noqa: E402
from app.repositories.teaching.catalog import TeachingCatalog  # noqa: E402
from app.repositories.teaching.schema import REQUIRED_TABLES as TEACHING_REQUIRED  # noqa: E402

KNOWLEDGE_TABLES = (
    "subjects",
    "knowledge_points",
    "knowledge_point_revisions",
    "knowledge_aliases",
    "textbook_knowledge_links",
    "knowledge_imports",
    "knowledge_import_rows",
)
TEACHING_TABLES = (
    "classes",
    "students",
    "class_memberships",
    "roster_imports",
    "roster_import_rows",
)
KNOWLEDGE_TRIGGERS = (
    "kp_cycle_update",
    "kp_cycle_insert",
    "immutable_knowledge_point_revisions_update",
    "immutable_knowledge_point_revisions_delete",
)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _names(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
    }


def _logical_snapshot(path: Path) -> dict:
    """库的逻辑快照（表/索引/触发器 + 每张表的行数 + 迁移登记）。"""
    conn = _connect(path)
    try:
        tables = sorted(_names(conn, "table"))
        counts = {
            name: conn.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]
            for name in tables
            if not name.startswith("sqlite_")
        }
        return {
            "tables": tables,
            "indexes": sorted(_names(conn, "index")),
            "triggers": sorted(_names(conn, "trigger")),
            "counts": counts,
            "registry": sorted(applied_migrations(conn).items()),
        }
    finally:
        conn.close()


# --------------------------------------------------------------------------- ① 新库
kpath = root / "knowledge" / "knowledge.sqlite3"
tpath = root / "teaching" / "teaching.sqlite3"
kpath.parent.mkdir(parents=True, exist_ok=True)
tpath.parent.mkdir(parents=True, exist_ok=True)

kc = KnowledgeCatalog(kpath)
kc.migrate()
tc = TeachingCatalog(tpath)
tc.migrate()

conn = _connect(kpath)
ktables = _names(conn, "table")
missing_k = [name for name in KNOWLEDGE_TABLES if name not in ktables]
p.check("v1.1a 知识点库 7 张 B1 表齐备", not missing_k, f"missing={missing_k}")
ktriggers = _names(conn, "trigger")
missing_tr = [name for name in KNOWLEDGE_TRIGGERS if name not in ktriggers]
p.check("v1.1b 知识点库 4 个触发器齐备", not missing_tr, f"missing={missing_tr}")
kimports_cols = {row[1] for row in conn.execute("PRAGMA table_info(knowledge_imports)")}
p.check(
    "v1.1c knowledge_imports 含 issues_json（0003）",
    "issues_json" in kimports_cols,
    f"cols={sorted(kimports_cols)}",
)
p.check(
    "v1.1d 0001 只要求 B0 基础表（REQUIRED_TABLES 未被 B1 扩大）",
    tuple(KNOWLEDGE_REQUIRED) == ("knowledge_submissions", "knowledge_jobs"),
    f"REQUIRED_TABLES={KNOWLEDGE_REQUIRED}",
)
p.check(
    "v1.1e 知识点器登记 3 条迁移（0001/0002/0003）",
    [item[0] for item in sorted(applied_migrations(conn).items())]
    == ["0001_knowledge_baseline", "0002_knowledge_business_tables", "0003_knowledge_import_issues_column"],
    f"{sorted(applied_migrations(conn))}",
)
conn.close()

conn = _connect(tpath)
ttables = _names(conn, "table")
missing_t = [name for name in TEACHING_TABLES if name not in ttables]
p.check("v1.1f 教学库 5 张 B1 表齐备", not missing_t, f"missing={missing_t}")
partial_index = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='index' AND name='ux_active_membership'"
).fetchone()
sql = partial_index["sql"] if partial_index else None
p.check(
    "v1.1g ux_active_membership 是部分唯一索引（WHERE left_on IS NULL）",
    bool(sql) and "UNIQUE" in sql.upper() and "left_on IS NULL" in sql,
    f"sql={sql}",
)
p.check(
    "v1.1h 教学库 REQUIRED_TABLES 仍只含 B0 表",
    tuple(TEACHING_REQUIRED)
    == ("command_submissions", "file_assets", "workflow_jobs"),
    f"{TEACHING_REQUIRED}",
)
conn.close()

# --------------------------------------------------------------------------- ③ 重复应用幂等
before = _logical_snapshot(kpath)
again = apply_migrations(_connect(kpath), database="knowledge")
after = _logical_snapshot(kpath)
p.check("v1.3a 重复 apply 返回空列表（无待应用迁移）", again == [], f"returned={again}")
p.check("v1.3b 重复 apply 不改变库的逻辑状态", before == after, f"before==after is {before == after}")

# --------------------------------------------------------------------------- ② 仅 B0 结构的旧库
b0path = root / "legacy" / "knowledge.sqlite3"
b0path.parent.mkdir(parents=True, exist_ok=True)
full_registry = REGISTERED_MIGRATIONS["knowledge"]
try:
    REGISTERED_MIGRATIONS["knowledge"] = tuple(
        item for item in full_registry if item.id.startswith("0001")
    )
    b0conn = _connect(b0path)
    applied_b0 = apply_migrations(b0conn, database="knowledge")
    b0conn.close()
finally:
    REGISTERED_MIGRATIONS["knowledge"] = full_registry
p.check("v1.2a 仅 B0 结构旧库只登记 0001", applied_b0 == ["0001_knowledge_baseline"], f"{applied_b0}")

b0conn = _connect(b0path)
p.check(
    "v1.2b 旧库缺 0002 表（确为 B0 结构）",
    "knowledge_points" not in _names(b0conn, "table"),
    f"tables={sorted(_names(b0conn, 'table'))}",
)
b0conn.close()

gate_ok = True
gate_detail = ""
try:
    verify_existing_database(
        DatabaseExpectation(b0path, "knowledge", KNOWLEDGE_REQUIRED)
    )
except AppError as exc:
    gate_ok = False
    gate_detail = f"{exc.code}: {exc}"
p.check("v1.2c 仅 B0 结构旧库通过启动门控（不判损坏/结构不符）", gate_ok, gate_detail or "ok")

kc_legacy = KnowledgeCatalog(b0path)
kc_legacy.migrate()
legacy_snapshot = _logical_snapshot(b0path)
p.check(
    "v1.2d 旧库迁移后补齐 7 张 B1 表",
    all(name in legacy_snapshot["tables"] for name in KNOWLEDGE_TABLES),
    f"tables={legacy_snapshot['tables']}",
)
p.check(
    "v1.2e 旧库迁移后 0002/0003 均登记",
    [item[0] for item in legacy_snapshot["registry"]]
    == ["0001_knowledge_baseline", "0002_knowledge_business_tables", "0003_knowledge_import_issues_column"],
    f"{legacy_snapshot['registry']}",
)

# --------------------------------------------------------------------------- ④ 中途失败整体回滚
rollback_path = root / "rollback" / "knowledge.sqlite3"
rollback_path.parent.mkdir(parents=True, exist_ok=True)
broken = Migration(
    id="9999_probe_broken",
    description="探针注入：先建表后引用不存在的表（必须整体回滚）",
    statements=(
        "CREATE TABLE probe_rollback_marker (id TEXT PRIMARY KEY)",
        "SELECT * FROM probe_table_that_does_not_exist",
    ),
)
try:
    REGISTERED_MIGRATIONS["knowledge"] = (*full_registry, broken)
    rbconn = _connect(rollback_path)
    try:
        apply_migrations(rbconn, database="knowledge")
        p.check("v1.4a 注入失败迁移应抛错", False, "no exception")
    except Exception as exc:  # noqa: BLE001 - 任何异常都算"失败可见"
        p.check(
            "v1.4a 注入失败迁移抛错（未被吞掉）",
            True,
            f"{type(exc).__name__}: {exc}",
        )
    finally:
        rbconn.close()
finally:
    REGISTERED_MIGRATIONS["knowledge"] = full_registry

rbconn = _connect(rollback_path)
rb_tables = _names(rbconn, "table")
rb_registry = sorted(applied_migrations(rbconn))
rbconn.close()
p.check(
    "v1.4b 失败迁移的部分表被整体回滚（probe_rollback_marker 不存在）",
    "probe_rollback_marker" not in rb_tables,
    f"tables={sorted(rb_tables)}",
)
p.check(
    "v1.4c 失败迁移不写登记（0001/0002/0003 已登记，9999 未登记）",
    rb_registry
    == [
        "0001_knowledge_baseline",
        "0002_knowledge_business_tables",
        "0003_knowledge_import_issues_column",
    ],
    f"{rb_registry}",
)
rbconn = _connect(rollback_path)
p.check(
    "v1.4d 失败后重跑：注入迁移移走后无待应用项",
    pending_migrations(rbconn, database="knowledge") == [],
    f"{pending_migrations(rbconn, database='knowledge')}",
)
rbconn.close()

# --------------------------------------------------------------------------- ⑤ 0001 散列
digests = {
    db: next(item.sha256 for item in items if item.id.startswith("0001"))
    for db, items in REGISTERED_MIGRATIONS.items()
}
rec_digests = {
    db: next(item.sha256 for item in items if item.id.startswith("0001"))
    for db, items in REGISTERED_MIGRATIONS.items()
}
for db, items in REGISTERED_MIGRATIONS.items():
    declaration = next(item.statements for item in items if item.id.startswith("0001"))
    recomputed = statement_digest(declaration)
    p.check(
        f"v1.5a {db} 0001 声明散列自算一致",
        recomputed == rec_digests[db],
        f"{recomputed[:16]}… vs {rec_digests[db][:16]}…",
    )

b0_evidence = REPO_ROOT / "docs" / "qa" / "TEACHING-LOOP-B0" / "V00-probes" / "evidence"
b0_text = ""
for item in sorted(b0_evidence.glob("*")):
    if item.is_file():
        b0_text += item.read_text(encoding="utf-8", errors="ignore")
p.check(
    "v1.5b teaching 0001 散列与 B0 V00 证据逐字节一致",
    digests["teaching"] in b0_text,
    f"{digests['teaching'][:16]}…",
)

formed_read: list[dict] = []
for db, rel in (
    ("knowledge", ".local-data/knowledge/knowledge.sqlite3"),
    ("teaching", ".local-data/teaching/teaching.sqlite3"),
    ("question_bank", ".local-data/question-bank/question-bank.sqlite3"),
    ("textbooks", ".local-data/textbooks/catalog.sqlite3"),
):
    formal = REPO_ROOT / rel
    if not formal.is_file():
        formed_read.append({"db": db, "state": "缺失"})
        continue
    uri = "file:" + formal.as_posix() + "?mode=ro&immutable=1"
    try:
        fconn = sqlite3.connect(uri, uri=True)
        fconn.execute("PRAGMA query_only = ON")
        rows = {
            row[0]: row[1]
            for row in fconn.execute("SELECT id, sha256 FROM schema_migrations")
        }
        fconn.close()
    except Exception as exc:  # noqa: BLE001
        formed_read.append({"db": db, "state": f"读取失败：{type(exc).__name__}: {exc}"})
        continue
    found = next((key for key in rows if key.startswith("0001")), None)
    formed_read.append(
        {
            "db": db,
            "state": "ok",
            "recordedIds": sorted(rows),
            "recorded": (rows.get(found) or "")[:64],
            "expected": digests[db],
            "match": rows.get(found) == digests[db],
        }
    )
for item in formed_read:
    p.check(
        f"v1.5c 正式库 {item['db']} 0001 散列只读对比",
        item.get("match") is True,
        json.dumps(item, ensure_ascii=False),
    )
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
(EVIDENCE_DIR / "v1_formal_registry_readonly.json").write_text(
    json.dumps(formed_read, ensure_ascii=False, indent=2), encoding="utf-8"
)

# --------------------------------------------------------------------------- ⑥ 损坏库仍被拒
intact = root / "corrupt"
intact.mkdir(parents=True, exist_ok=True)
garbage = intact / "knowledge.sqlite3"
garbage.write_bytes(b"this is not a sqlite database at all" * 40)
try:
    verify_existing_database(DatabaseExpectation(garbage, "knowledge", KNOWLEDGE_REQUIRED))
    p.check("v1.6a 垃圾文件被拒（DATABASE_UNREADABLE）", False, "no exception")
except AppError as exc:
    p.expect_error("v1.6a 垃圾文件被拒（DATABASE_UNREADABLE）", exc, "DATABASE_UNREADABLE", 500)

empty_valid = intact / "empty.sqlite3"
sqlite3.connect(str(empty_valid)).close()
try:
    verify_existing_database(DatabaseExpectation(empty_valid, "knowledge", KNOWLEDGE_REQUIRED))
    p.check("v1.6b 合法但缺表的库被拒（DATABASE_SCHEMA_INCOMPLETE）", False, "no exception")
except AppError as exc:
    p.expect_error(
        "v1.6b 合法但缺表的库被拒（DATABASE_SCHEMA_INCOMPLETE）",
        exc,
        "DATABASE_SCHEMA_INCOMPLETE",
        500,
    )

drift = intact / "drift.sqlite3"
dconn = _connect(drift)
apply_migrations(dconn, database="knowledge")
dconn.execute(
    "UPDATE schema_migrations SET sha256 = ? WHERE id = '0002_knowledge_business_tables'",
    ("0" * 64,),
)
dconn.commit()
dconn.close()
try:
    verify_existing_database(DatabaseExpectation(drift, "knowledge", KNOWLEDGE_REQUIRED))
    p.check("v1.6c 散列漂移库被拒（SCHEMA_MIGRATION_DRIFT）", False, "no exception")
except AppError as exc:
    p.expect_error(
        "v1.6c 散列漂移库被拒（SCHEMA_MIGRATION_DRIFT）", exc, "SCHEMA_MIGRATION_DRIFT", 500
    )

drift2 = intact / "drift-apply.sqlite3"
d2 = _connect(drift2)
apply_migrations(d2, database="knowledge")
d2.execute(
    "UPDATE schema_migrations SET sha256 = ? WHERE id = '0001_knowledge_baseline'",
    ("f" * 64,),
)
d2.commit()
d2.close()
try:
    verify_migrations(_connect(drift2), database="knowledge")
    p.check("v1.6d verify_migrations 散列漂移必报错", False, "no exception")
except AppError as exc:
    p.expect_error("v1.6d verify_migrations 散列漂移必报错", exc, "SCHEMA_MIGRATION_DRIFT", 500)

# --------------------------------------------------------------------------- ⑦ 0003 宽容性反例
tol_path = root / "tolerance" / "knowledge.sqlite3"
tol_path.parent.mkdir(parents=True, exist_ok=True)
tconn = _connect(tol_path)
apply_migrations(tconn, database="knowledge")
repo = KnowledgeImportRepository()
tconn.execute("BEGIN IMMEDIATE")
tconn.execute(
    "INSERT OR IGNORE INTO subjects (id, code, name, status) VALUES ('probe','probe','probe','active')"
)
batch = repo.create_import(
    tconn,
    source="file",
    subject_id="probe",
    file_asset_id="asset-x",
    mapping={"code": "编码"},
    batch_issues=[{"field": "code", "code": "KNOWLEDGE_IMPORT_MISSING_COLUMN", "message": "缺列"}],
    warnings=["w"],
    rows=[
        ImportRowInput(row_no=1, name="n", code="c", parent_code=None, description="", aliases=(),
                       raw_cells={}, issues=[{"row": 1, "code": "KNOWLEDGE_ROW_MISSING_NAME", "message": "x"}])
    ],
    state="reviewing",
)
tconn.commit()
readable = repo.get_import(tconn, batch.import_id)
p.check(
    "v1.7a 列存在时批次级 issues 从 issues_json 读出",
    readable is not None and [item["code"] for item in readable.batch_issues]
    == ["KNOWLEDGE_IMPORT_MISSING_COLUMN"],
    f"{readable.batch_issues if readable else None}",
)

# (a) 列存在 + 注册表缺 0003 → r2 起应自愈（adjust 钩子跳过 ALTER 并补登记）
tconn.execute("DELETE FROM schema_migrations WHERE id = '0003_knowledge_import_issues_column'")
tconn.commit()
reraised = None
applied_after = None
try:
    applied_after = apply_migrations(tconn, database="knowledge")
except Exception as exc:  # noqa: BLE001
    reraised = exc
p.check(
    "v1.7b 注册表缺 0003 且列已存在 → apply 不再抛原始 sqlite3 异常（r2 修复）",
    reraised is None,
    f"raised={type(reraised).__name__ if reraised else None}: {reraised}",
)
p.check(
    "v1.7c 该路径补登记 0003 且列保留（自愈，非静默跳过）",
    reraised is None
    and applied_after == ["0003_knowledge_import_issues_column"]
    and "issues_json" in {row[1] for row in tconn.execute("PRAGMA table_info(knowledge_imports)")},
    json.dumps(
        {
            "applied": applied_after,
            "columns": [row[1] for row in tconn.execute("PRAGMA table_info(knowledge_imports)")],
        },
        ensure_ascii=False,
    ),
)
tconn.close()

# (b) 注册表缺 0003 且列被移除 → 是否重补？
tol2 = root / "tolerance2" / "knowledge.sqlite3"
tol2.parent.mkdir(parents=True, exist_ok=True)
t2 = _connect(tol2)
apply_migrations(t2, database="knowledge")
t2.close()
t2 = _connect(tol2)
# 手工把 knowledge_imports 重建成"无 issues_json"的旧形状（模拟列丢失），注册表保留 0003
t2.execute("PRAGMA foreign_keys = OFF")
t2.execute("BEGIN IMMEDIATE")
t2.execute("ALTER TABLE knowledge_imports RENAME TO knowledge_imports_old")
cols = [
    "id", "owner_id", "source", "subject_id", "file_asset_id", "state", "revision",
    "mapping_json", "warnings_json", "error_code", "created_at", "updated_at",
]
t2.execute(
    "CREATE TABLE knowledge_imports ("
    "id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local', "
    "source TEXT NOT NULL CHECK(source IN ('file','ai')), "
    "subject_id TEXT NOT NULL REFERENCES subjects(id), file_asset_id TEXT NOT NULL, "
    "state TEXT NOT NULL DEFAULT 'uploaded', revision INTEGER NOT NULL DEFAULT 0, "
    "mapping_json TEXT NOT NULL DEFAULT '{}', warnings_json TEXT NOT NULL DEFAULT '[]', "
    "error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
)
t2.execute(
    f"INSERT INTO knowledge_imports ({', '.join(cols)}) SELECT {', '.join(cols)} FROM knowledge_imports_old"
)
t2.execute("DROP TABLE knowledge_imports_old")
t2.commit()
t2.close()

t2 = _connect(tol2)
reapplied = apply_migrations(t2, database="knowledge")
cols_now = {row[1] for row in t2.execute("PRAGMA table_info(knowledge_imports)")}
t2.close()
p.check(
    "v1.7d 列被手工删除、注册表仍有 0003 → apply 不重补（记录为 observation）",
    "issues_json" not in cols_now and reapplied == [],
    f"reapplied={reapplied} cols={sorted(cols_now)}",
)

sys.exit(p.finish())
