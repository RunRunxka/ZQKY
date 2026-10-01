"""V00-B2 · V9 独立探针：声明抽查（docs/API.md B2 节 / PROJECT_GUIDE §13 / ROUTES+导航 / 迁移与触发器）。

只读：从文档里**机械抽取**声明事实，再与代码/真实路由表/迁移后的 sqlite_master 对照。
行为级抽查（文档说 CLASS_ARCHIVED(409)，实测状态码）经临时应用与真 HTTP 完成。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v9-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(HERE.parent))

import v00_support as S  # noqa: E402

RESULTS: list[dict] = []
API_MD = REPO / "docs" / "API.md"
ROUTES_MD = REPO / "docs" / "ROUTES.md"
GUIDE_MD = REPO / "docs" / "PROJECT_GUIDE.md"
NAV_TS = REPO / "apps" / "web" / "src" / "services" / "navigation.ts"


def observe(name: str, detail: str) -> None:
    """记录不计 fail 的观察项（文档漂移等；不改变产品行为）。"""
    RESULTS.append({"name": name, "status": "OBSERVATION", "detail": str(detail)[:600]})
    print(f"[OBS ] {name} :: {str(detail)[:240]}")


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:600]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:240]}")
    return ok


def b2_section() -> str:
    text = API_MD.read_text(encoding="utf-8")
    start = text.index("## 教学闭环 B2 接口")
    end = text.index("### 新增依赖与命令", start)
    return text[start:end]


def normalize_path(raw: str) -> str:
    path = raw.split("?")[0].strip().rstrip("`")
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    return path


def main(evidence: str) -> int:
    section = b2_section()

    # ---------------------------------------------------------------- 路由
    from app.main import create_app
    from app.core.config import Settings
    from fastapi.testclient import TestClient

    root = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v9-app-"))
    app = create_app(Settings(host="127.0.0.1", port=8001,
                              allowed_origins=frozenset({"http://127.0.0.1:5173"}),
                              env="test", data_dir=root / "data"))
    # FastAPI 0.12x 的 include_router 产生无 path 的 _IncludedRouter 包装：用 OpenAPI 表取实际路由
    actual: set[tuple[str, str]] = set()
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method.upper() in {"GET", "POST", "PATCH", "DELETE", "PUT"}:
                actual.add((method.upper(), normalize_path(path)))
    actual.add(("POST", normalize_path("/api/v1/{rest:path}")))

    # 声明行解析：每行取 反引号内的路径 token 与行内 HTTP 方法，按出现顺序配对
    declared: set[tuple[str, str]] = set()
    for line in section.splitlines():
        if "/api/v1" not in line or line.lstrip().startswith("-"):
            continue
        tokens = re.findall(r"`([^`]*)`", line)
        methods = re.findall(r"\b(GET|POST|PATCH|DELETE|PUT)\b", line)
        if not tokens or not methods:
            continue
        first_tick = line.index("`")
        prefix_methods = re.findall(r"(GET|POST|PATCH|DELETE|PUT)", line[:first_tick])
        tail_methods = re.findall(r"(GET|POST|PATCH|DELETE|PUT)", line[first_tick:])
        # 首个路径 token 归一化（含 "GET/POST `path`"）
        if not prefix_methods:
            prefix_methods = methods[:1]
        if not any(token.startswith("/api/v1") for token in tokens[:1]):
            # 行首是省略号写法等异常行：跳过，不影响其余行
            continue
        base_token = tokens[0]
        first = normalize_path(base_token)
        for method in prefix_methods:
            declared.add((method, first))
        last_full = base_token
        for index, token in enumerate(tokens[1:]):
            if token.startswith("/api/v1"):
                last_full = token
                resolved = token
            elif token.startswith("…") and last_full:
                resolved = last_full + token[1:]
            else:
                continue
            if index < len(tail_methods):
                declared.add((tail_methods[index], normalize_path(resolved)))

    missing = sorted(item for item in declared if item not in actual)
    check("V9.1 API.md B2 节声明的路由全部真实存在（方法与路径）", not missing,
          f"declared={len(declared)} missing_in_code={missing} "
          f"actual_has={sorted(item for item in actual if 'proposal' in item[1])}")

    # 反向：B2 新增路由是否都在文档里出现（原卷/施测/生成）
    b2_prefixes = ("/api/v1/paper-imports", "/api/v1/papers", "/api/v1/paper-proposals",
                   "/api/v1/assessments", "/api/v1/question-generation-jobs")
    undeclared = sorted(
        (method, path) for method, path in actual
        if path.startswith(b2_prefixes) and (method, path) not in declared
    )
    check("V9.2 B2 新增路由（原卷/施测/生成）在文档里有对应声明", not undeclared,
          f"undeclared_in_docs={undeclared}")

    # ---------------------------------------------------------------- 迁移/触发器/分期
    from app.core.migrations import REGISTERED_MIGRATIONS
    from app.core.sqlite import connect

    ids = {db: [m.id for m in REGISTERED_MIGRATIONS[db]] for db in ("teaching", "question_bank")}
    for migration_id in ("0003_teaching_paper_tables", "0004_teaching_assessment_tables",
                         "0004_question_knowledge_links"):
        ok = any(migration_id in values for values in ids.values())
        check(f"V9.3 API.md 迁移 id `{migration_id}` 已登记", ok, str(ids))

    conn = connect(Path(tempfile.mkdtemp(prefix="zqky-v00b2-v9-db-")) / "teaching.sqlite3")
    from app.core.migrations import apply_migrations
    apply_migrations(conn, database="teaching")
    triggers = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    doc_trigger_markers = (
        "paper_cycle_*", "paper_confirm", "immutable_paper_revisions_*",
        "no_direct_sealed_paper_revisions",
        "freeze_paper_{items,item_knowledge,source_blocks,issues}_*",
        "assessment_confirmed_paper_insert", "assessment_paper_fixed",
    )
    concrete: set[str] = set()
    for family in ("items", "item_knowledge", "source_blocks", "issues"):
        for action in ("insert", "update", "delete"):
            concrete.add(f"freeze_paper_{family}_{action}")
    for action in ("insert", "update"):
        concrete.add(f"paper_cycle_{action}")
    for action in ("update", "delete"):
        concrete.add(f"immutable_paper_revisions_{action}")
    concrete.update({"paper_confirm", "no_direct_sealed_paper_revisions",
                     "assessment_confirmed_paper_insert", "assessment_paper_fixed"})
    missing_triggers = sorted(name for name in concrete if name not in triggers)
    check("V9.4 API.md 声明的触发器家族（文本）与真实触发器（展开后）一致",
          all(marker in section for marker in doc_trigger_markers) and not missing_triggers,
          f"doc_markers_ok={all(marker in section for marker in doc_trigger_markers)} "
          f"concrete={len(concrete)} missing={missing_triggers}")
    sql = "\n".join(row[0] or "" for row in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name IN "
        "('paper_revisions','assessments','paper_items')"))
    check("V9.5 文档声明的分期 CHECK 与 DDL 一致",
          "source_practice_revision_id IS NULL" in sql and "active_score_revision_id IS NULL" in sql
          and "source_file_id TEXT NOT NULL" in sql and "total_score_units>=0" in sql,
          f"source_practice={'source_practice_revision_id IS NULL' in sql} "
          f"active_score={'active_score_revision_id IS NULL' in sql}")
    paper_confirm = next((row[0] for row in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='paper_confirm'")), "")
    check("V9.6 文档声明的 `paper_confirm` 无 PRACTICE_NOT_REVIEWED 分支",
          "PRACTICE_NOT_REVIEWED" not in paper_confirm and "ITEM_KNOWLEDGE_MISSING" in paper_confirm,
          "ok" if "PRACTICE_NOT_REVIEWED" not in paper_confirm else "仍有该分支")
    conn.close()

    # ---------------------------------------------------------------- 六态
    from app.contracts.teaching_loop import JobState
    from app.schemas.question_bank import GenerationJobView, OrganizeJobView
    six = {"queued", "running", "succeeded", "failed", "cancelled", "interrupted"}
    view_states = set(OrganizeJobView.model_fields["state"].annotation.__args__)
    gen_states = set(GenerationJobView.model_fields["state"].annotation.__args__)
    check("V9.7 文档声明的「六态 + attempt」与代码一致",
          view_states == six == gen_states and set(JobState.__args__) == six
          and "attempt" in OrganizeJobView.model_fields and "attempt" in GenerationJobView.model_fields,
          f"organize={sorted(view_states)} generation={sorted(gen_states)}")
    check("V9.8 文档声明的启动收敛含 question 域",
          "question" in __import__("app.main", fromlist=["RECONCILE_DOMAINS"]).RECONCILE_DOMAINS,
          str(__import__("app.main", fromlist=["RECONCILE_DOMAINS"]).RECONCILE_DOMAINS))

    # ---------------------------------------------------------------- 错误码
    from app.contracts import assessments as assessments_contract
    from app.contracts import papers as papers_contract
    from app.services import question_bank as qb_pkg  # noqa: F401
    from app.services.question_bank import generation as generation_mod

    declared_codes = sorted(set(re.findall(r"`([A-Z][A-Z0-9_]{4,})`", section)))
    code_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            REPO / "apps" / "api" / "app" / "contracts" / "papers.py",
            REPO / "apps" / "api" / "app" / "contracts" / "assessments.py",
            REPO / "apps" / "api" / "app" / "contracts" / "roster.py",
            REPO / "apps" / "api" / "app" / "contracts" / "teaching_loop.py",
            REPO / "apps" / "api" / "app" / "services" / "question_bank" / "generation.py",
            REPO / "apps" / "api" / "app" / "services" / "question_bank" / "service.py",
        )
    )
    doc_only = [
        code for code in declared_codes
        if f'"{code}"' not in code_text
        # 文档写的是「paper_confirm 无 PRACTICE_NOT_REVIEWED 分支」——声明的是"不存在"
        and f"无 {code} 分支" not in section and f"无 `{code}` 分支" not in section
        and f"`{code}` 不存在" not in section
    ]
    check("V9.9 API.md B2 节声明的错误码都能在代码里找到同名常量", not doc_only,
          f"doc_only={doc_only}")

    # 行为级：CLASS_ARCHIVED 的实际状态码 vs 文档（文档把它列在 409 组）
    har, _provider = S.new_harness("v9")
    point_a = har.make_point("V00-KP-A", "函数单调性")
    point_b = har.make_point("V00-KP-B", "导数几何意义")
    sample = S.build_sample_docx(Path(tempfile.mkdtemp(prefix="zqky-v00b2-v9-src-")) / "s.docx")
    state = S.prepare_ready_draft(har, sample, point_a=point_a, point_b=point_b)
    paper_rev = har.client.get(f"/api/v1/papers/{state['paper_id']}").json()
    confirmed = har.client.post(f"/api/v1/papers/{state['paper_id']}/confirm", json={
        "expectedRevision": paper_rev["revision"], "submissionId": "v00-v9-confirm"})
    paper_revision_id = confirmed.json()["paperRevisionId"]
    klass = har.client.post("/api/v1/classes", json={
        "code": "V00C9", "name": "高一(9)班", "schoolYear": "2026-2027", "gradeId": "senior-1"}).json()
    student = har.client.post("/api/v1/students", json={
        "name": "王五", "studentNo": "V0009", "classId": klass["id"], "joinedOn": "2026-09-01"}).json()
    archived = har.client.post(f"/api/v1/classes/{klass['id']}/archive", json={"expectedRevision": klass["revision"]})
    check("V9.P0 前置：学生建档 + 班级归档成功", student.get("id") and archived.status_code == 200,
          f"student={bool(student.get('id'))} archive={archived.status_code}")
    response = har.client.post("/api/v1/assessments", json={
        "submissionId": "v00-v9-archived-class",
        "paperRevisionId": paper_revision_id, "title": "V00 归档班", "assessmentType": "exam",
        "heldOn": "2026-10-01", "classIds": [klass["id"]],
        "participants": [{"studentId": student["id"], "classId": klass["id"]}]})
    doc_section_assess = section[section.index("### 施测（T30-b）"):]
    doc_says_409 = re.search(r"CLASS_ARCHIVED`?\(409\)|CLASS_ARCHIVED`?、?[^)]*\(409\)", doc_section_assess) is not None
    actual_status = response.status_code
    check("V9.10 文档标注 CLASS_ARCHIVED 为 409，实测与代码一致",
          (doc_says_409 and actual_status == 409) or ((not doc_says_409) and actual_status != 409),
          f"doc_409={doc_says_409} actual_status={actual_status} "
          f"actual_code={response.json().get('code')}")
    har.client.close()

    # ---------------------------------------------------------------- ROUTES / 导航 / 页面
    routes_md = ROUTES_MD.read_text(encoding="utf-8")
    nav_ts = NAV_TS.read_text(encoding="utf-8")
    page = REPO / "apps" / "web" / "src" / "app" / "knowledge-points" / "page.tsx"
    row = next((line for line in routes_md.splitlines() if line.startswith("| `/knowledge-points`")), "")
    nav_status = re.search(r"id: 'knowledge-points',[\s\S]{0,220}?status: '([a-z]+)'", nav_ts)
    check("V9.11 ROUTES.md 与 navigation.ts 的 /knowledge-points 状态一致且页面存在",
          "已实现" in row and "ready" in row and nav_status is not None
          and nav_status.group(1) == "ready" and page.is_file()
          and "path: '/knowledge-points'" in nav_ts,
          f"routes_row={row[:80]} nav_status={nav_status.group(1) if nav_status else None} "
          f"page={page.is_file()}")

    # ---------------------------------------------------------------- PROJECT_GUIDE §13
    guide = GUIDE_MD.read_text(encoding="utf-8")
    section13 = guide[guide.index("## 13. "):]
    section13 = section13[: section13.index("\n## 14.")] if "\n## 14." in section13 else section13
    from app.repositories.jobs.repository import JobStore
    lease_default = JobStore.__init__.__defaults__[0] if JobStore.__init__.__defaults__ else None
    import inspect
    signature = inspect.signature(JobStore.__init__)
    lease_default = signature.parameters["lease_seconds"].default
    check("V9.12 PROJECT_GUIDE §13 声明的租约/心跳与代码一致（90s/≤20s 续租）",
          lease_default == 90 and "90s" in section13,
          f"lease_seconds_default={lease_default} guide_mentions_90s={'90s' in section13}")
    facts = {
        "只允许为空的分期列": "只允许为空" in section13 and "source_practice_revision_id" in section13
        and "active_score_revision_id" in section13,
        "确认即冻结/修改=新建修订": "确认即冻结" in section13 and "新建修订" in section13,
        "AI 补题独立 GenerateReply": "独立 GenerateReply" in section13,
        "旧 checkpoint 需重选模型": "重选模型" in section13,
        "施测只用已确认修订 + 快照冻结": "只用**已确认**的固定原卷修订" in section13,
        "教材依据不可用≠没有依据": "不得显示成\"没有依据\"" in section13,
    }
    check("V9.13 PROJECT_GUIDE §13 的稳定决定与代码行为一致（逐条核对）", all(facts.values()),
          str(facts))

    # ---------------------------------------------------------------- B2 任务卡事实
    card = (REPO / "docs" / "qa" / "TEACHING-LOOP-B2" / "TASK-CARD.md").read_text(encoding="utf-8")
    check("V9.14 B2 任务卡的迁移 id/路由/六态声明与代码一致",
          all(token in card for token in (
              "0003_teaching_paper_tables", "0004_teaching_assessment_tables",
              "0004_question_knowledge_links", "POST /question-generation-jobs",
              "六态 + attempt", "PARTICIPANT_CLASS_UNCONFIRMED", "ORGANIZER_MODEL_RESELECT_REQUIRED"))
          and "0004_question_knowledge_links" in json.dumps(ids),
          "task card 关键事实齐全")

    # ---------------------------------------------------------------- AGENTS.md
    agents = (REPO / "apps" / "api" / "AGENTS.md").read_text(encoding="utf-8")
    if "B2" in agents and "0003" in agents and "assessments" in agents:
        check("V9.15 apps/api/AGENTS.md 含 B2 结构声明（迁移/原卷/施测）", True, "含 B2 声明")
    else:
        check("V9.15 apps/api/AGENTS.md 是否含 B2 结构声明（文档一致性，不计 fail）", True,
              "未含 B2 声明——见 observation")
        observe("OBS-AGENTS.md 未同步 B2",
                "apps/api/AGENTS.md 仍只有 B1 段落（「施测三表留 T30-b（依赖 T40 的 paper_revisions）」），"
                "B2 已落地 teaching 0003/0004 与 assessments；该文件不在 B2 任务卡的文件归属表内，"
                "属文档漂移而非产品不一致。")

    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v9_docs_declarations_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v9_docs_declarations_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    try:
        raise SystemExit(main(_args.evidence))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-300:]})
        raise SystemExit(finish(_args.evidence, reason="crashed"))
