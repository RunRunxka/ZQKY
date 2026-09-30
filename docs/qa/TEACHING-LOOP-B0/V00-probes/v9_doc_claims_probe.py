"""V9 声明抽查独立探针（V00 / TEACHING-LOOP B0，读代码 + 读文档 + 真库结构对照）。

抽查 5 条事实性声明（可机检的部分全部机检）：
  9.a API.md「教学闭环 B0」小节的四库路径 / 任务路由 / 并发上限 / 取消语义
  9.b API.md 备份小节：schemaVersion 3 四库 + 资产、缺库即 failed
  9.c apps/api/AGENTS.md：迁移登记纪律（每库 schema_migrations、清单文件、漂移拒绝）
  9.d PROJECT_GUIDE §11：并发上限、收敛范围、四库边界、类型单一来源
  9.e TASK-CARD §3.5/§3.6/§3.7 的 DDL 列清单 vs app/core/migrations 实际建表结果
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from _probe_common import REPO_ROOT, check, cleanup, observe, record, run_main, temp_root

from app.core.sqlite import connect
from app.repositories.knowledge.catalog import KnowledgeCatalog
from app.repositories.teaching.catalog import TeachingCatalog

PROBE = "v9_doc_claims_probe"
DOCS = REPO_ROOT / "docs"
API_MD = DOCS / "API.md"
GUIDE = DOCS / "PROJECT_GUIDE.md"
AGENTS = REPO_ROOT / "apps" / "api" / "AGENTS.md"
CARD = DOCS / "qa" / "TEACHING-LOOP-B0" / "TASK-CARD.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def card_block(card: str, heading: str, next_heading: str) -> str:
    start = card.index(heading)
    end = card.index(next_heading, start)
    section = card[start:end]
    match = re.search(r"```(?:sql)?\n(.*?)```", section, re.S)
    return match.group(1) if match else ""


def card_columns(block: str) -> list[str]:
    """从 §3.x 代码块抽出列名（第一段标识符），保持文档顺序。

    文档里既有"一行一列"也有"一行多列"写法，因此按顶层逗号切分；括号内的逗号不算。
    """
    columns: list[str] = []
    # 去掉结尾的"索引：…"说明行
    lines = [line for line in block.splitlines() if not line.strip().startswith("索引")]
    text = " ".join(line.strip() for line in lines).strip()
    # §3.6/§3.7 把整段字段列表包在一对圆括号里（PRIMARY KEY 也一样），先剥掉最外层
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    depth = 0
    current: list[str] = []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            entry = "".join(current).strip()
            current = []
            if entry:
                columns.append(entry)
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        columns.append(tail)

    names: list[str] = []
    for entry in columns:
        entry = entry.lstrip("( ").strip()
        entry = entry.rstrip(") ").strip()
        if not entry:
            continue
        name = re.split(r"[\s(]", entry, maxsplit=1)[0]
        if name.upper() in {"PRIMARY", "CHECK", "UNIQUE", "FOREIGN", "INDEX"}:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue
        names.append(name)
    return names


def table_columns(path: Path, table: str) -> list[str]:
    connection = connect(path)
    try:
        return [row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')]
    finally:
        connection.close()


def table_ddl(path: Path, table: str) -> str:
    connection = connect(path)
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        return str(row["sql"]) if row else ""
    finally:
        connection.close()


def table_indexes(path: Path, table: str) -> dict[str, list[str]]:
    connection = connect(path)
    try:
        result: dict[str, list[str]] = {}
        for row in connection.execute(f'PRAGMA index_list("{table}")'):
            name = row["name"]
            columns = [item["name"] for item in connection.execute(f'PRAGMA index_info("{name}")')]
            result[str(name)] = columns
        return result
    finally:
        connection.close()


def claim_a_routes_and_limits() -> None:
    api = read(API_MD)
    card = read(CARD)
    section = api[api.index("## 教学闭环 B0 公共契约与基础设施") :]
    for path, label in (
        ("GET `/api/v1/workflow-jobs/{jobId}?domain=knowledge\\|question\\|teaching`", "GET 路由"),
        ("POST `/api/v1/workflow-jobs/{jobId}/cancel`", "cancel 路由"),
        ("POST `/api/v1/workflow-jobs/{jobId}/retry`", "retry 路由"),
    ):
        check(f"v9.a1 API.md 声明 {label}", path in section, path)
    for needle, label in (
        ("404 `JOB_NOT_FOUND`", "404 JOB_NOT_FOUND"),
        ("域非法 422", "非法域 422"),
        ("域未装配 503", "未装配 503"),
        ("仅终态 `failed/interrupted/cancelled` 可重试", "重试仅终态"),
        ("`queued/running` → 409 `JOB_NOT_RETRYABLE`", "queued/running 409"),
        ("幂等", "取消幂等"),
        ("租约 90 秒、每 20 秒续租", "租约/心跳时间"),
        ("同时最多 2 个后台重任务，其中最多 1 个模型生成任务", "并发上限"),
    ):
        check(f"v9.a2 API.md 声明 {label}", needle in section, needle)

    # 代码事实
    from app.main import JOB_KINDS, RECONCILE_DOMAINS, _database_expectations
    from app.core.config import Settings
    from app.repositories.jobs.repository import JobStore

    settings = Settings(host="127.0.0.1", port=8000, allowed_origins=frozenset(), env="x", data_dir=Path("T:/probe-data"))
    paths = {
        expectation.database: expectation.path.relative_to(settings.data_dir).as_posix()
        for expectation in _database_expectations(settings)
    }
    check(
        "v9.a3 四库实际路径 = API.md 表格",
        paths
        == {
            "textbooks": "textbooks/catalog.sqlite3",
            "question_bank": "question-bank/question-bank.sqlite3",
            "knowledge": "knowledge/knowledge.sqlite3",
            "teaching": "teaching/teaching.sqlite3",
        },
        str(paths),
    )
    check(
        "v9.a4 资产根 = data_dir/assets",
        settings.assets_root == settings.data_dir / "assets",
        str(settings.assets_root),
    )
    check(
        "v9.a5 JobStore 默认租约 90 秒；引擎心跳上限 20 秒",
        (JobStore.__init__.__kwdefaults__ or {}).get("lease_seconds") == 90
        and JobStore(None, domain="teaching", table="workflow_jobs", kinds=frozenset({"k"})).lease_seconds == 90
        and "min(20" in (REPO_ROOT / "apps" / "api" / "app" / "services" / "jobs" / "engine.py").read_text(encoding="utf-8"),
        f"kwdefaults={JobStore.__init__.__kwdefaults__}",
    )
    check(
        "v9.a6 kinds 白名单在 app/main.py（TASK-CARD §6 声明）",
        set(JOB_KINDS) == {"question", "knowledge", "teaching"}
        and JOB_KINDS["knowledge"] == frozenset({"suggestion"})
        and JOB_KINDS["teaching"]
        == frozenset({"paper_import", "paper_mapping", "analysis", "lesson_generation", "export"})
        and "JOB_KINDS" in card,
        str({k: sorted(v) for k, v in JOB_KINDS.items()}),
    )
    check(
        "v9.a7 收敛范围（TASK-CARD §3.4.5 更新版）与代码一致",
        RECONCILE_DOMAINS == ("knowledge", "teaching") and "知识点库与教学库" in card,
        f"RECONCILE_DOMAINS={RECONCILE_DOMAINS}",
    )


def claim_b_backup() -> None:
    api = read(API_MD)
    section = api[api.index("### 备份与恢复"): api.index("### 运维命令补充")]
    for needle in (
        "清单 `schemaVersion: 3`",
        "`textbooks/catalog.sqlite3`",
        "`question-bank/question-bank.sqlite3`",
        "`knowledge/knowledge.sqlite3`",
        "`teaching/teaching.sqlite3`",
        "缺任一库/任一被引用原件即 `status:\"failed\"`",
        "`file_assets` 引用逐文件重算 sha256",
        "`integrity_check` + `foreign_key_check`",
    ):
        check(f"v9.b API.md 备份声明：{needle[:34]}", needle in section, needle)
    import importlib.util

    spec = importlib.util.spec_from_file_location("v9_backup", REPO_ROOT / "scripts" / "rag" / "backup.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["v9_backup"] = module
    spec.loader.exec_module(module)
    check(
        "v9.b2 代码事实：SCHEMA_VERSION=3 且必需恢复路径为四库",
        module.SCHEMA_VERSION == 3
        and module.CATALOG_RESTORE_PATHS
        == (
            "textbooks/catalog.sqlite3",
            "question-bank/question-bank.sqlite3",
            "knowledge/knowledge.sqlite3",
            "teaching/teaching.sqlite3",
        ),
        f"SCHEMA_VERSION={module.SCHEMA_VERSION} 必需={module.CATALOG_RESTORE_PATHS}",
    )
    check(
        "v9.b3 代码事实：受管资产归档前缀 files/assets/ + 恢复路径 assets/<blob_key>",
        module.ASSET_ARCHIVE_PREFIX == "files/assets/" and "assets/" in module.RESTORE_PATH_PREFIXES,
        f"{module.ASSET_ARCHIVE_PREFIX} / {module.RESTORE_PATH_PREFIXES}",
    )


def claim_c_agents() -> None:
    agents = read(AGENTS)
    for needle in (
        "每库 `schema_migrations`",
        "app/core/migrations/{textbooks,question_bank,knowledge,teaching}.py",
        "改动结构一律**新增迁移**，不得改写已登记 SQL",
        "散列漂移会拒绝启动",
    ):
        check(f"v9.c AGENTS.md 迁移纪律：{needle[:28]}", needle in agents, needle)
    check(
        "v9.c 迁移纪律在 AGENTS.md 的其余口径见 PROJECT_GUIDE §11（不得按空库重建）",
        "损坏的既有库不得按空库重建" in read(GUIDE),
        "该句在 PROJECT_GUIDE §11；AGENTS.md 未重复声明，属分工而非缺失",
    )
    migration_files = sorted(
        p.name for p in (REPO_ROOT / "apps" / "api" / "app" / "core" / "migrations").glob("*.py")
    )
    check(
        "v9.c2 迁移清单文件实际存在",
        {"textbooks.py", "question_bank.py", "knowledge.py", "teaching.py"} <= set(migration_files),
        str(migration_files),
    )


def claim_d_guide() -> None:
    guide = read(GUIDE)
    section = guide[guide.index("## 11. 教学闭环公共契约与基础设施") :]
    for needle in (
        "租约 90 秒 / 心跳 20 秒",
        "**并发上限 2 个重任务、其中 1 个模型任务**",
        "重启遗留 `running` 收敛为 `interrupted`",
        ".local-data/knowledge/knowledge.sqlite3",
        ".local-data/teaching/teaching.sqlite3",
        ".local-data/assets/blobs/<sha256>",
        "`app/contracts/teaching_loop.py`",
        "apps/web/src/contracts/teaching-loop.ts",
        "重试保留冻结输入与模型指纹",
        "取消只走接口且迟到结果不发布",
    ):
        check(f"v9.d PROJECT_GUIDE §11 声明：{needle[:26]}", needle in section, needle)
    # 收敛范围：§11 未点名"只含知识点库与教学库"（代码只收敛这两域）→ 记录为观察项
    if "知识点库与教学库" in section:
        check(
            "v9.d2 §11 收敛范围点名例外",
            True,
            "§11 已说明收敛范围",
        )
    else:
        observe(
            "v9.d2 PROJECT_GUIDE §11 收敛范围未点名例外",
            "§11 只说「重启遗留 running 收敛为 interrupted」，未说明题库任务不在启动收敛范围"
            "（RECONCILE_DOMAINS 只含 knowledge/teaching，见 app/main.py）；"
            "同一口径在 TASK-CARD §3.4.5（更新版）与批次 README §5 有明确说明，"
            "建议 §11 补一句以免读者以为三张任务表都会在启动时收敛。",
        )


def claim_e_ddl(root: Path) -> None:
    card = read(CARD)
    knowledge_db = root / "knowledge" / "knowledge.sqlite3"
    teaching_db = root / "teaching" / "teaching.sqlite3"
    question_db = root / "question-bank" / "question-bank.sqlite3"
    KnowledgeCatalog(knowledge_db).migrate()
    TeachingCatalog(teaching_db).migrate()
    from app.repositories.question_bank.catalog import QuestionBankCatalog

    QuestionBankCatalog(question_db).migrate()

    expected = card_columns(card_block(card, "### 3.5", "### 3.6"))
    check(
        "v9.e1 从 TASK-CARD §3.5 解析出 19 列",
        len(expected) == 19 and expected[0] == "id" and expected[-1] == "finished_at",
        str(expected),
    )
    for table, path in (
        ("knowledge_jobs", knowledge_db),
        ("workflow_jobs", teaching_db),
        ("question_jobs", question_db),
    ):
        columns = table_columns(path, table)
        check(
            f"v9.e2 {table} 列集合 = §3.5 列清单",
            set(columns) == set(expected),
            f"missing={sorted(set(expected) - set(columns))} extra={sorted(set(columns) - set(expected))}",
        )
        ddl = table_ddl(path, table)
        if table == "question_jobs":
            # §3.5 偏差记录：SQLite ALTER TABLE 不能加 CHECK，既有 question_jobs 以应用层枚举校验
            check(
                "v9.e3 question_jobs 无 CHECK（§3.5 偏差记录），由应用层校验",
                "CHECK" not in ddl
                and "应用层枚举校验" in read(REPO_ROOT / "apps" / "api" / "app" / "repositories" / "question_bank" / "schema.py")
                or "应用层枚举校验" in read(CARD),
                "见 app/repositories/question_bank/schema.py 与 TASK-CARD §3.5",
            )
        else:
            check(
                f"v9.e3 {table} state 有六态 CHECK",
                "CHECK" in ddl and "queued" in ddl and "interrupted" in ddl,
                "CHECK 六态存在",
            )
        check(
            f"v9.e4 {table} kind 不加 CHECK（§3.5 偏差记录）",
            not re.search(r"kind\s+TEXT\s+NOT\s+NULL\s+CHECK", ddl, re.I),
            "",
        )
        indexes = table_indexes(path, table)
        pairs = {tuple(cols) for cols in indexes.values()}
        # §3.5：索引 idx_*_jobs_state(state, created_at)、idx_*_jobs_kind(kind, state)
        check(
            f"v9.e5 {table} 具备 §3.5 声明的 (state, created_at) 与 (kind, state) 索引",
            ("state", "created_at") in pairs and ("kind", "state") in pairs,
            f"indexes={indexes}",
        )

    submits = card_columns(card_block(card, "### 3.6", "### 3.7"))
    for table, path in (
        ("knowledge_submissions", knowledge_db),
        ("command_submissions", teaching_db),
    ):
        columns = table_columns(path, table)
        check(
            f"v9.e6 {table} 列 = §3.6（复合身份）",
            set(columns) == set(submits) and "owner_id" in columns,
            f"doc={submits} actual={columns}",
        )
    assets_expected = card_columns(card_block(card, "### 3.7", "### 3.8"))
    assets_actual = table_columns(teaching_db, "file_assets")
    check(
        "v9.e7 file_assets 列 = §3.7",
        set(assets_actual) == set(assets_expected),
        f"doc={assets_expected} actual={assets_actual}",
    )
    ddl = table_ddl(teaching_db, "file_assets")
    check(
        "v9.e8 file_assets kind/sha256/byte_size 约束与 §3.7 一致",
        "roster" in ddl and "attachment" in ddl and "length(sha256) = 64" in ddl and "byte_size >= 0" in ddl,
        "",
    )


def main() -> None:
    root = temp_root("v9")
    try:
        claim_a_routes_and_limits()
        claim_b_backup()
        claim_c_agents()
        claim_d_guide()
        claim_e_ddl(root)
        print(f"临时数据根：{root}（探针结束后删除）")
    finally:
        cleanup(root)


if __name__ == "__main__":
    run_main(PROBE, main)
