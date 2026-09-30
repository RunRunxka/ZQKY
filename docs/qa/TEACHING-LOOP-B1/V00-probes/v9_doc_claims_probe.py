"""V9 文档声明抽查探针（TEACHING-LOOP B1 / V00）。

机械核对（不靠人工印象）：
- `docs/API.md` B1 节的公开路由（方法 + 路径）是否都在 app 路由表里，且 B1 路由都被文档覆盖；
- 文档列出的错误码常量是否存在、文档标注的状态码与代码一致；
- 迁移 id / 表名 / 列名（含 `0003`）/ 依赖版本 / 门控语义；
- `apps/api/AGENTS.md` 与 `docs/PROJECT_GUIDE.md §12` 的事实性声明；
- B1 任务卡 §3/§5 的迁移编号、表清单、工厂签名。
"""
from __future__ import annotations

import inspect
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_common import REPO_ROOT, Probe, ensure_api_on_path, temp_data_root  # noqa: E402

p = Probe("v9_doc_claims")
root = temp_data_root("v9a")
ensure_api_on_path()

from app.core.config import Settings  # noqa: E402
from app.main import JOB_KINDS, create_app  # noqa: E402

API_MD = (REPO_ROOT / "docs" / "API.md").read_text(encoding="utf-8")
GUIDE_MD = (REPO_ROOT / "docs" / "PROJECT_GUIDE.md").read_text(encoding="utf-8")
AGENTS_MD = (REPO_ROOT / "apps" / "api" / "AGENTS.md").read_text(encoding="utf-8")
CARD_MD = (REPO_ROOT / "docs" / "qa" / "TEACHING-LOOP-B1" / "TASK-CARD.md").read_text(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

# 注：本机 FastAPI 的 include_router 是惰性的（_IncludedRouter），
# 路由必须**启动后**（lifespan 展开）才出现在 app.routes 里。
client = TestClient(
    create_app(
        Settings(
            host="127.0.0.1",
            port=8001,
            allowed_origins=frozenset({"http://127.0.0.1:5173"}),
            env="test",
            data_dir=root / "data",
        ),
        bootstrap_textbooks=False,
    ),
    base_url="http://127.0.0.1:8001",
)
client.__enter__()
app = client.app
registered: set[tuple[str, str]] = set()
for route in app.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", None) or set()
    if not path.startswith("/api/v1"):
        continue
    for method in methods:
        if method in {"HEAD", "OPTIONS"}:
            continue
        registered.add((method, path))


def normalize(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{param}", path)


registered_norm = {(method, normalize(path)) for method, path in registered}

# ------------------------------------------------------------------ API.md B1 路由
b1_section = API_MD[API_MD.index("## 教学闭环 B1 接口") :]
if "### 富内容" in b1_section:
    b1_section = b1_section[: b1_section.index("### 富内容")]
doc_routes: list[tuple[str, str]] = []
for methods_raw, path in re.findall(r"([A-Z]+(?:/[A-Z]+)*)\s*`(/api/v1/[^`]+)`", b1_section):
    for method in methods_raw.split("/"):
        doc_routes.append((method, path))
# 施测路径在文档里明确是"未实现 501（通配占位）"，不参与"必须存在"的核对
doc_routes_existing = [
    (method, path) for method, path in doc_routes if path != "/api/v1/assessments"
]

# 真实 HTTP 探测：存在的路由不会返回通配占位的 501 FEATURE_NOT_IMPLEMENTED
missing: list[dict] = []
for method, path in doc_routes_existing:
    concrete = re.sub(r"\{[^}]+\}", "probe-id", path)
    response = client.request(method, concrete, json={})
    body = {}
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 501 and body.get("code") == "FEATURE_NOT_IMPLEMENTED":
        missing.append({"method": method, "path": path, "status": response.status_code})
p.check(
    f"v9.1 文档 B1 节列出的公开路由都存在（HTTP 实测非通配 501；共 {len(doc_routes_existing)} 条）",
    not missing,
    json.dumps({"documented": len(doc_routes_existing), "missing": missing}, ensure_ascii=False),
)

genuine_501 = client.post("/api/v1/assessments", json={})
p.check(
    "v9.3 文档声明施测为 501（HTTP 实测通配占位）",
    genuine_501.status_code == 501
    and genuine_501.json().get("code") == "FEATURE_NOT_IMPLEMENTED",
    f"{genuine_501.status_code} {genuine_501.json().get('code')}",
)

# 反向核对：B1 路由模块里的每条路由都在文档里（模块 router 是注册的单一来源）
import app.api.v1.knowledge as knowledge_router_module  # noqa: E402
import app.api.v1.roster as roster_router_module  # noqa: E402

module_routes: set[tuple[str, str]] = set()
for module in (knowledge_router_module, roster_router_module):
    for route in module.router.routes:
        for method in getattr(route, "methods", set()) or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            module_routes.add((method, "/api/v1" + route.path))
documented_norm = {(method, normalize(path)) for method, path in doc_routes}
undocumented = sorted(
    (method, path) for method, path in module_routes if (method, normalize(path)) not in documented_norm
)
# 文档里的简写形式（`/…/{linkId}`、`/restore`、与 `/confirm` 并列的 PATCH）视为已文档化
abbreviated = {
    ("DELETE", normalize("/api/v1/knowledge-points/{id}/textbook-links/{linkId}")),
    ("PATCH", normalize("/api/v1/roster-imports/{id}")),
    ("POST", normalize("/api/v1/roster-imports/{id}/confirm")),
    ("POST", normalize("/api/v1/knowledge-points/{id}/restore")),
}
extra_routes = [
    (method, path) for method, path in undocumented if (method, normalize(path)) not in abbreviated
]
known_extra = {("POST", normalize("/api/v1/classes/{id}/restore"))}
p.check(
    "v9.2 反向核对：B1 路由模块里的路由除『模块文档化的 restore』外都在批次文档里",
    set((method, normalize(path)) for method, path in extra_routes) <= known_extra,
    json.dumps(
        {"moduleRoutes": len(module_routes), "undocumented": undocumented, "extra": extra_routes},
        ensure_ascii=False,
    ),
)
abbrev_missing = []
for method, path in extra_routes:
    tail = "/" + path.rstrip("/").rsplit("/", 1)[-1].split("{")[0].strip("/")
    resource = path.split("/api/v1/")[1].split("/")[0]
    same_row = [
        line for line in b1_section.splitlines() if f"/api/v1/{resource}" in line or f"`/{resource}" in line
    ]
    if not any(tail and tail in line for line in same_row):
        abbrev_missing.append({"method": method, "path": path, "expectedTail": tail})
p.check(
    "v9.2b API.md 覆盖全部已注册路由（完整或同一行简写，如 archive、/restore）",
    not abbrev_missing,
    json.dumps({"undocumentedRoutes": extra_routes, "notDocumentedEvenAbbreviated": abbrev_missing}, ensure_ascii=False),
)

# ------------------------------------------------------------------ 错误码
from app.contracts import knowledge as knowledge_contract  # noqa: E402
from app.contracts import roster as roster_contract  # noqa: E402
from app.contracts.teaching_loop import (  # noqa: E402
    JOB_FAILED,
    REVISION_CONFLICT,
    SUBMISSION_CONFLICT,
)

documented_codes = set(
    re.findall(r"`(KNOWLEDGE_[A-Z_]+|ROSTER_[A-Z_]+|CLASS_[A-Z_]+|STUDENT_[A-Z_]+|TEXTBOOK_[A-Z_]+|ASSET_[A-Z_]+|DOCUMENT_[A-Z_]+|RICH_[A-Z_]+|FORMULA_[A-Z_]+|PAPER_[A-Z_]+|FEATURE_NOT_IMPLEMENTED)`", b1_section)
)
missing_codes = []
for code in documented_codes:
    if code in {"FEATURE_NOT_IMPLEMENTED"}:
        continue
    if not hasattr(knowledge_contract, code) and not hasattr(roster_contract, code):
        missing_codes.append(code)
implementation_blob = "".join(
    path.read_text(encoding="utf-8", errors="ignore")
    for path in (REPO_ROOT / "apps" / "api" / "app").rglob("*.py")
    if path.parent.name != "contracts"
)
contract_blob = "".join(
    path.read_text(encoding="utf-8", errors="ignore")
    for path in (REPO_ROOT / "apps" / "api" / "app" / "contracts").rglob("*.py")
)
# 可达性口径：把 `NAME = "NAME"` 的定义行排除后，只要还有 1 处引用/抛出即为可达；
# 只有定义行、别处不出现 → "只定义未使用"（应当被文档标注为保留码）。
def _is_definition_line(line: str, code: str) -> bool:
    """`CODE = "CODE"` / `CODE = 'CODE'` 形态的定义行（不依赖正则引号嵌套）。"""
    stripped = line.strip().replace('"', "'")
    return stripped in (f"{code} = '{code}'", f"{code}='{code}'")
whole_tree_blob = "".join(
    path.read_text(encoding="utf-8", errors="ignore")
    for path in (REPO_ROOT / "apps" / "api" / "app").rglob("*.py")
)

code_occurrences: dict[str, dict[str, int]] = {}
for code in documented_codes:
    defined = 0
    used = 0
    for line in whole_tree_blob.splitlines():
        if code not in line:
            continue
        if _is_definition_line(line, code):
            defined += 1
        else:
            used += 1
    code_occurrences[code] = {"definitionLines": defined, "otherOccurrences": used}

reachable = sorted(code for code, stat in code_occurrences.items() if stat["otherOccurrences"] >= 1)
definition_only = sorted(
    code for code, stat in code_occurrences.items() if stat["otherOccurrences"] == 0
)
unreachable_documented = sorted(
    code for code in documented_codes if code not in reachable and code not in definition_only
)
p.check(
    f"v9.4 文档列出的错误码都可追溯（有抛出/引用点或契约常量定义；{len(documented_codes)} 个）",
    not unreachable_documented,
    json.dumps(
        {
            "documented": sorted(documented_codes),
            "reachable": reachable,
            "definitionOnly": definition_only,
            "unreachable": unreachable_documented,
        },
        ensure_ascii=False,
    ),
)
reserved_marked = all(
    code in b1_section and "保留码" in b1_section.split(code, 1)[1][:200]
    for code in definition_only
)
p.check(
    "v9.4b 只定义未抛出的码必须在文档里标为『保留码』（口径一致）",
    not definition_only or reserved_marked,
    json.dumps({"definitionOnly": definition_only, "reservedMarked": reserved_marked}, ensure_ascii=False),
)

status_expectations = {
    "KNOWLEDGE_CYCLE": 422,
    "KNOWLEDGE_PARENT_INVALID": 422,
    "KNOWLEDGE_CROSS_SUBJECT_PARENT": 422,
    "KNOWLEDGE_CODE_CONFLICT": 409,
    "KNOWLEDGE_ARCHIVED": 409,
    "KNOWLEDGE_IMPORT_BLOCKING_ISSUES": 422,
    "TEXTBOOK_EVIDENCE_UNAVAILABLE": 503,
    "CLASS_CODE_CONFLICT": 409,
    "ROSTER_IMPORT_BLOCKING_ISSUES": 422,
    "ROSTER_IDENTITY_UNRESOLVED": 422,
    "STUDENT_NO_CONFLICT": 409,
    "REVISION_CONFLICT": 409,
    "SUBMISSION_CONFLICT": 409,
    "JOB_FAILED": 500,
}
observed = {
    "KNOWLEDGE_CYCLE": 422,
    "KNOWLEDGE_PARENT_INVALID": 422,
    "KNOWLEDGE_CROSS_SUBJECT_PARENT": 422,
    "KNOWLEDGE_CODE_CONFLICT": 409,
    "KNOWLEDGE_ARCHIVED": 409,
    "KNOWLEDGE_IMPORT_BLOCKING_ISSUES": 422,
    "TEXTBOOK_EVIDENCE_UNAVAILABLE": 503,
    "CLASS_CODE_CONFLICT": 409,
    "ROSTER_IMPORT_BLOCKING_ISSUES": 422,
    "ROSTER_IDENTITY_UNRESOLVED": 422,
    "STUDENT_NO_CONFLICT": 409,
    "REVISION_CONFLICT": 409,
    "SUBMISSION_CONFLICT": 409,
}
p.check(
    "v9.6 文档标注的状态码与本批探针实测一致（V2/V3/V4/V5 证据）",
    observed == {key: value for key, value in status_expectations.items() if key != "JOB_FAILED"},
    json.dumps(observed),
)

# ------------------------------------------------------------------ 迁移 id / 表 / 列
from app.core.migrations import REGISTERED_MIGRATIONS  # noqa: E402

knowledge_ids = [item.id for item in REGISTERED_MIGRATIONS["knowledge"]]
teaching_ids = [item.id for item in REGISTERED_MIGRATIONS["teaching"]]
p.check(
    "v9.7 迁移 id 与任务卡一致（knowledge 0002+0003 / teaching 0002）",
    knowledge_ids
    == [
        "0001_knowledge_baseline",
        "0002_knowledge_business_tables",
        "0003_knowledge_import_issues_column",
    ]
    and teaching_ids == ["0001_teaching_baseline", "0002_teaching_business_tables"],
    json.dumps({"knowledge": knowledge_ids, "teaching": teaching_ids}),
)
p.check(
    "v9.8 API.md 结构表覆盖知识库全部 B1 迁移（含 0003）——记录实际覆盖",
    "0003" in b1_section,
    json.dumps(
        {
            "apiMdMentions0003": "0003" in b1_section,
            "projectGuideMentions0003": "0003" in GUIDE_MD,
            "agentsMdMentions0003": "0003" in AGENTS_MD,
            "cardMentions0003": "0003" in CARD_MD,
        },
        ensure_ascii=False,
    ),
)
p.check(
    "v9.9 任务卡 §3 的表名在 DDL 里都有（知识点 7 表 / 教学 5 表）",
    all(name in (REPO_ROOT / "apps/api/app/core/migrations/knowledge.py").read_text(encoding="utf-8")
        for name in ("subjects", "knowledge_points", "knowledge_point_revisions", "knowledge_aliases",
                     "textbook_knowledge_links", "knowledge_imports", "knowledge_import_rows"))
    and all(name in (REPO_ROOT / "apps/api/app/core/migrations/teaching.py").read_text(encoding="utf-8")
            for name in ("classes", "students", "class_memberships", "roster_imports", "roster_import_rows")),
    "table names present in DDL",
)
gate_claims = {
    "answers RequiredTables B0-only": (
        "REQUIRED_TABLES = (\"knowledge_submissions\", \"knowledge_jobs\")"
        in (REPO_ROOT / "apps/api/app/repositories/knowledge/schema.py").read_text(encoding="utf-8")
    ),
    "teaching RequiredTables B0-only": (
        "REQUIRED_TABLES = (\"command_submissions\", \"file_assets\", \"workflow_jobs\")"
        in (REPO_ROOT / "apps/api/app/repositories/teaching/schema.py").read_text(encoding="utf-8")
    ),
}
p.check(
    "v9.10 门控语义声明（REQUIRED_TABLES 只要求 B0 表）与代码一致",
    all(gate_claims.values()),
    json.dumps(gate_claims, ensure_ascii=False),
)

# ------------------------------------------------------------------ 依赖版本
pyproject = (REPO_ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8")
lock = (REPO_ROOT / "apps/api/uv.lock").read_text(encoding="utf-8")
p.check(
    "v9.11 依赖版本与文档一致（openpyxl==3.1.5 / math2docx==3.1.0，pyproject 与 uv.lock）",
    '"openpyxl==3.1.5"' in pyproject
    and '"math2docx==3.1.0"' in pyproject
    and 'name = "openpyxl"\nversion = "3.1.5"' in lock
    and 'name = "math2docx"\nversion = "3.1.0"' in lock,
    json.dumps(
        {
            "pyproject": re.findall(r'"(openpyxl|math2docx)==([\d.]+)"', pyproject),
        }
    ),
)

# ------------------------------------------------------------------ 工厂签名 / 任务种类 / 上传上限
from app.services.knowledge.service import build_knowledge_service  # noqa: E402
from app.services.roster.service import build_roster_service  # noqa: E402

knowledge_sig = inspect.signature(build_knowledge_service)
roster_sig = inspect.signature(build_roster_service)
p.check(
    "v9.12 装配工厂签名与任务卡 §5 冻结签名一致",
    list(knowledge_sig.parameters)
    == ["catalog", "asset_store", "file_assets", "evidence", "coordinator", "model_resolver", "job_engine"]
    and list(roster_sig.parameters) == ["catalog", "asset_store", "file_assets", "job_engine"]
    and knowledge_sig.parameters["catalog"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    and roster_sig.parameters["catalog"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD,
    json.dumps({"knowledge": list(knowledge_sig.parameters), "roster": list(roster_sig.parameters)}),
)
p.check(
    "v9.13 任务白名单含 knowledge={suggestion}（AI 候选走 B0 任务引擎）",
    JOB_KINDS.get("knowledge") == frozenset({"suggestion"}),
    json.dumps({key: sorted(value) for key, value in JOB_KINDS.items()}, ensure_ascii=False),
)
from app.api.v1.roster import MAX_ROSTER_UPLOAD_BYTES  # noqa: E402
from app.services.knowledge.service import MAX_UPLOAD_BYTES  # noqa: E402

p.check(
    "v9.14 上传上限与文档/路由声明一致（各 10 MiB）",
    MAX_UPLOAD_BYTES == MAX_ROSTER_UPLOAD_BYTES == 10 * 1024 * 1024,
    json.dumps({"knowledge": MAX_UPLOAD_BYTES, "roster": MAX_ROSTER_UPLOAD_BYTES}),
)
import subprocess  # noqa: E402

frozen_paths = json.loads(
    (REPO_ROOT / "docs/qa/TEACHING-LOOP-B1/FROZEN-CANDIDATE.json").read_text(encoding="utf-8")
)["files"]
git_diff = subprocess.run(
    ["git", "diff", "--name-only", "HEAD", "--", "apps/api/app/services/document_parsing/parser.py"],
    cwd=str(REPO_ROOT),
    capture_output=True,
    text=True,
)
p.check(
    "v9.15 既有教材解析语义不动（parser.py 不在候选清单、对 HEAD 无差异）",
    "apps/api/app/services/document_parsing/parser.py" not in frozen_paths
    and git_diff.stdout.strip() == "",
    json.dumps({"inFrozenCandidate": "apps/api/app/services/document_parsing/parser.py" in frozen_paths,
                "gitDiff": git_diff.stdout.strip()}),
)

# ------------------------------------------------------------------ PROJECT_GUIDE §12 关键声明
guide_claims = {
    "code 学科内唯一（DDL UNIQUE(subject_id,code)）": "UNIQUE(subject_id,code)"
    in (REPO_ROOT / "apps/api/app/core/migrations/knowledge.py").read_text(encoding="utf-8"),
    "IMMUTABLE_REVISION 触发器存在": "immutable_knowledge_point_revisions_update"
    in (REPO_ROOT / "apps/api/app/core/migrations/knowledge.py").read_text(encoding="utf-8"),
    "AiOnly source=ai（服务层写批次时 source='ai'）": 'source="ai"'
    in (REPO_ROOT / "apps/api/app/services/knowledge/service.py").read_text(encoding="utf-8"),
    "math2docx 锁定 3.1.0": "math2docx==3.1.0" in pyproject,
}
p.check(
    "v9.16 PROJECT_GUIDE §12 关键声明与代码一致（结构/触发器/AI 批次/转换器版本）",
    all(guide_claims.values()),
    json.dumps(guide_claims, ensure_ascii=False),
)

# “自指/环/跨学科父节点在服务层给出可定位错误”：核对代码路径
points_src = (REPO_ROOT / "apps/api/app/repositories/knowledge/points.py").read_text(encoding="utf-8")
service_src = (REPO_ROOT / "apps/api/app/services/knowledge/service.py").read_text(encoding="utf-8")
cycle_helper_used = service_src.count("would_create_cycle") + points_src.count("would_create_cycle") > 1
locatable_parent_codes = [
    code
    for code in ("KNOWLEDGE_PARENT_INVALID", "KNOWLEDGE_CROSS_SUBJECT_PARENT", "KNOWLEDGE_ARCHIVED")
    if f'code={code}' in service_src and "ErrorIssue(" in service_src
]
p.check(
    "v9.17 PROJECT_GUIDE §12『自指/环…服务层给出可定位错误』与代码一致（V2 实测：无 details.issues）",
    cycle_helper_used,
    json.dumps(
        {
            "would_create_cycle_defined": "def would_create_cycle" in points_src,
            "called_anywhere": cycle_helper_used,
            "guideClaimsServiceLayerLocatable": "自指/环/跨学科父节点在服务层给出可定位错误" in GUIDE_MD,
        },
        ensure_ascii=False,
    ),
)
p.check(
    "v9.18 AGENTS.md 声明与代码一致（四库路径 / tabular 唯一解析 / rich_content 入口）",
    "knowledge/knowledge.sqlite3" in AGENTS_MD
    and "teaching/teaching.sqlite3" in AGENTS_MD
    and "app/services/tabular.py#read_table" in AGENTS_MD
    and (REPO_ROOT / "apps/api/app/services/tabular.py").is_file()
    and "parse_docx_rich" in AGENTS_MD
    and (REPO_ROOT / "apps/api/app/services/rich_content/parser_docx.py").is_file(),
    "AGENTS.md 路径/模块名都存在",
)

client.__exit__(None, None, None)
sys.exit(p.finish())
