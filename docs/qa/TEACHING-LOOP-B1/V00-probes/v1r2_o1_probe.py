"""V1r2 O1 窄复验探针（TEACHING-LOOP B1 r2 / V00）。

O1 修复复验（`0003` 补 `adjust` 钩子）：
  1. 列**已存在**但注册表缺 0003（手工加列/部分恢复）→ `apply_migrations` 不再抛原始
     sqlite3 错误，且能补登记 0003；
  2. 列**缺失**且注册表缺 0003（真该补列）→ 钩子不得误跳过：必须 ADD COLUMN 并登记；
  3. 0003 的 `sha256` 与 r1 记录逐字节一致（声明集合不变 → 散列不变）；
  4. 声明的 `statements` 仍只有那一条 ALTER（adjust 不得改变声明集合）；
  5. 常规路径（新库全量 apply）与 r2 迁移后 `issues_json` 列/默认值仍正确。
r1 的 0003 散列取自 r1 证据（`evidence/v1_migrations.json` v1.2e）。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import EVIDENCE_DIR, Probe, ensure_api_on_path, temp_data_root  # noqa: E402

#: r1（V00-REPORT-01 时点）知识库 0003 登记散列
R1_0003_SHA256 = "ec0fdc9abcc7009ebe7a801927f21814c4fdeed809fda27c26e1f6873f76bb09"

p = Probe("v1r2_o1")
root = temp_data_root("v1r2")
ensure_api_on_path()

from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations, applied_migrations  # noqa: E402
from app.core.migrations.base import statement_digest  # noqa: E402

LATEST = REGISTERED_MIGRATIONS["knowledge"][-1]
p.check(
    "v1r2.0 知识库末条迁移仍是 0003（id 未变）",
    LATEST.id == "0003_knowledge_import_issues_column",
    LATEST.id,
)
p.check(
    "v1r2.1 0003 声明集合未变（单条 ALTER，散列与 r1 一致）",
    len(LATEST.statements) == 1
    and "ADD COLUMN issues_json" in LATEST.statements[0]
    and LATEST.sha256 == R1_0003_SHA256
    and statement_digest(LATEST.statements) == R1_0003_SHA256,
    json.dumps(
        {"len": len(LATEST.statements), "sha256": LATEST.sha256, "r1": R1_0003_SHA256,
         "match": LATEST.sha256 == R1_0003_SHA256},
        ensure_ascii=False,
    ),
)
p.check(
    "v1r2.2 0003 已挂 adjust 钩子",
    LATEST.adjust is not None,
    f"adjust={LATEST.adjust}",
)
p.check(
    "v1r2.3 0002 声明散列未变（B0/B1 冻结面未动）",
    REGISTERED_MIGRATIONS["knowledge"][1].sha256
    == "6389e7c456b614059df2e3d96b695d963ee460237286747f857b0582b828c6d6",
    REGISTERED_MIGRATIONS["knowledge"][1].sha256,
)


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _columns(path: Path, table: str = "knowledge_imports") -> list[str]:
    conn = _connect(path)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


full_registry = REGISTERED_MIGRATIONS["knowledge"]

# ------------------------------------------------------------------ 场景 A：列已存在 + 0003 未登记
path_a = root / "a" / "knowledge.sqlite3"
path_a.parent.mkdir(parents=True, exist_ok=True)
conn = _connect(path_a)
apply_migrations(conn, database="knowledge")  # 全量：列与 0003 都到位
conn.execute("DELETE FROM schema_migrations WHERE id = '0003_knowledge_import_issues_column'")
conn.commit()
conn.close()
p.check(
    "v1r2.4 场景 A 构造：列已存在、注册表缺 0003",
    "issues_json" in _columns(path_a)
    and "0003_knowledge_import_issues_column" not in applied_migrations(_connect(path_a)),
    json.dumps({"columns": _columns(path_a), "registry": sorted(applied_migrations(_connect(path_a)))}),
)
raised_a = None
applied_a = None
try:
    conn_a = _connect(path_a)
    applied_a = apply_migrations(conn_a, database="knowledge")
    conn_a.close()
except Exception as exc:  # noqa: BLE001 - r1 时这里是原始 sqlite3.OperationalError
    raised_a = exc
p.check(
    "v1r2.5 场景 A：apply 不再抛错（O1 修复）",
    raised_a is None,
    f"raised={type(raised_a).__name__ if raised_a else None}: {raised_a}",
)
p.check(
    "v1r2.6 场景 A：本次补登记 0003 且列保留",
    raised_a is None
    and applied_a == ["0003_knowledge_import_issues_column"]
    and "issues_json" in _columns(path_a)
    and applied_migrations(_connect(path_a)).get("0003_knowledge_import_issues_column")
    == R1_0003_SHA256,
    json.dumps({"applied": applied_a, "columns": _columns(path_a)}, ensure_ascii=False),
)
conn_a2 = _connect(path_a)
p.check(
    "v1r2.7 场景 A：重复 apply 幂等（再跑返回空）",
    apply_migrations(conn_a2, database="knowledge") == [],
    "second apply -> []",
)
conn_a2.close()

# ------------------------------------------------------------------ 场景 B：列缺失 + 0003 未登记（真该补列）
path_b = root / "b" / "knowledge.sqlite3"
path_b.parent.mkdir(parents=True, exist_ok=True)
try:
    REGISTERED_MIGRATIONS["knowledge"] = tuple(
        item for item in full_registry if not item.id.startswith("0003")
    )
    conn_b = _connect(path_b)
    apply_migrations(conn_b, database="knowledge")
    conn_b.close()
finally:
    REGISTERED_MIGRATIONS["knowledge"] = full_registry
p.check(
    "v1r2.8 场景 B 构造：列缺失（0002 无 issues_json）、0003 未登记",
    "issues_json" not in _columns(path_b),
    json.dumps(_columns(path_b)),
)
conn_b = _connect(path_b)
applied_b = apply_migrations(conn_b, database="knowledge")
conn_b.close()
p.check(
    "v1r2.9 场景 B：钩子未误跳过 —— ADD COLUMN 执行并登记 0003",
    applied_b == ["0003_knowledge_import_issues_column"]
    and "issues_json" in _columns(path_b),
    json.dumps({"applied": applied_b, "columns": _columns(path_b)}, ensure_ascii=False),
)
conn_b2 = _connect(path_b)
default_row = conn_b2.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='knowledge_imports'"
).fetchone()[0]
conn_b2.close()
p.check(
    "v1r2.10 场景 B：列定义仍为 NOT NULL DEFAULT '[]'",
    "issues_json TEXT NOT NULL DEFAULT '[]'" in default_row,
    json.dumps([line.strip() for line in default_row.splitlines() if "issues_json" in line], ensure_ascii=False),
)

# ------------------------------------------------------------------ 场景 C：adjust 钩子直接行为（两态）
import app.core.migrations.knowledge as knowledge_migrations  # noqa: E402

(root / "c").mkdir(parents=True, exist_ok=True)
conn_c = _connect(root / "c" / "knowledge.sqlite3")
apply_migrations(conn_c, database="knowledge")
present_out = knowledge_migrations._skip_existing_issues_column(conn_c)
conn_c.execute("ALTER TABLE knowledge_imports RENAME TO knowledge_imports_keep")
conn_c.execute(
    "CREATE TABLE knowledge_imports (id TEXT PRIMARY KEY NOT NULL, owner_id TEXT NOT NULL DEFAULT 'local',"
    " source TEXT NOT NULL, subject_id TEXT NOT NULL, file_asset_id TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'uploaded',"
    " revision INTEGER NOT NULL DEFAULT 0, mapping_json TEXT NOT NULL DEFAULT '{}', warnings_json TEXT NOT NULL DEFAULT '[]',"
    " error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
)
conn_c.commit()
missing_out = knowledge_migrations._skip_existing_issues_column(conn_c)
conn_c.close()
p.check(
    "v1r2.11 钩子两态：列存在 → 空；列缺失 → 原 ALTER",
    list(present_out) == [] and list(missing_out) == list(knowledge_migrations._IMPORT_ISSUES_COLUMN),
    json.dumps({"present": list(present_out), "missing": list(missing_out)}, ensure_ascii=False),
)

# ------------------------------------------------------------------ 场景 D：常规新库全量路径
path_d = root / "d" / "knowledge.sqlite3"
path_d.parent.mkdir(parents=True, exist_ok=True)
conn_d = _connect(path_d)
applied_d = apply_migrations(conn_d, database="knowledge")
registry_d = applied_migrations(conn_d)
conn_d.close()
p.check(
    "v1r2.12 新库全量：0001/0002/0003 依次登记且散列与 r1 一致",
    applied_d
    == [
        "0001_knowledge_baseline",
        "0002_knowledge_business_tables",
        "0003_knowledge_import_issues_column",
    ]
    and registry_d["0003_knowledge_import_issues_column"] == R1_0003_SHA256,
    json.dumps({"applied": applied_d, "0003": registry_d.get("0003_knowledge_import_issues_column")}),
)

(EVIDENCE_DIR / "v1r2_o1_digests.json").write_text(
    json.dumps(
        {
            "r1_0003_sha256": R1_0003_SHA256,
            "r2_0003_sha256": LATEST.sha256,
            "match": LATEST.sha256 == R1_0003_SHA256,
            "0002_sha256": REGISTERED_MIGRATIONS["knowledge"][1].sha256,
            "adjusted_scenarios": {"A": applied_a, "B": applied_b, "D": applied_d},
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

sys.exit(p.finish())
