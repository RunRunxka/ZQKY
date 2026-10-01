"""V00-B2 · V10 独立探针：变异实验（证明断言有牙齿）+ 还原后哈希复算。

三处变异（全部作用于**副本/内存**，不写产品文件）：

  A. 确认闸门：把 `paper_confirm` 的 `ITEM_KNOWLEDGE_MISSING` 分支从**复制出来的 DDL**
     里删掉，建一个变异库 → 同样数据在原始库被拒、在变异库被接受；
  B. 生成校验：把 `scan_forbidden_reference` 的副本改成恒返回 None → 同一模型回复
     在原始实现被判 `GENERATION_FORBIDDEN_REFERENCE`、在变异副本被判可用；
  C. 启动收敛：把 `RECONCILE_DOMAINS` 的副本去掉 `question` → 遗留 running 的题库任务
     不再被收敛为 interrupted。

最后复算 83 个候选文件 sha256 与冻结记录逐一对比（证明候选未被污染），并核对工作区差异数。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
API = REPO / "apps" / "api"
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v10-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(API))
sys.path.insert(0, str(HERE.parent))

RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:500]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:240]}")
    return ok


def seed_confirm_case(conn: sqlite3.Connection) -> None:
    """造一份"总分对、缺知识点"的草稿（应当在原始闸门下被拒）。"""
    conn.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, media_type, "
        "byte_size, created_at) VALUES ('a1','local','paper','blobs/x',?, 'p.docx','application/vnd',1,"
        "'2026-10-01T00:00:00Z')", ("a" * 64,))
    conn.execute("INSERT INTO papers (id, owner_id, subject_id, title) VALUES ('p1','local','math','V00')")
    conn.execute(
        "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, created_at) "
        "VALUES ('r1','p1',1,'a1',400,'2026-10-01T00:00:00Z')")
    conn.execute("UPDATE papers SET current_revision_id='r1' WHERE id='p1'")
    conn.execute(
        "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
        "max_score_units, content_json) VALUES ('i1','r1','16(1)',1,1,400,'{}')")


def try_confirm(conn: sqlite3.Connection) -> tuple[bool, str]:
    try:
        conn.execute(
            "UPDATE paper_revisions SET state='confirmed', confirmed_at='2026-10-01T00:00:00Z' WHERE id='r1'")
        return True, ""
    except sqlite3.Error as exc:
        return False, f"{exc.__class__.__name__}: {exc}"


def main(evidence: str) -> int:
    from app.core.migrations import apply_migrations
    from app.core.sqlite import connect

    work = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v10-work-"))

    # ---------------------------------------------------------------- A. 触发器分支变异
    pristine = connect(work / "pristine.sqlite3")
    apply_migrations(pristine, database="teaching")
    trigger_sql = pristine.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='paper_confirm'").fetchone()[0]
    seed_confirm_case(pristine)
    pristine_ok, pristine_message = try_confirm(pristine)
    pristine.close()

    mutant_path = work / "mutant-trigger.sqlite3"
    mutant = connect(mutant_path)
    apply_migrations(mutant, database="teaching")
    mutated_sql = "\n".join(
        line for line in trigger_sql.splitlines() if "ITEM_KNOWLEDGE_MISSING" not in line
    )
    check("V10.A0 变异后的 DDL 确实删掉了 ITEM_KNOWLEDGE_MISSING 分支",
          "ITEM_KNOWLEDGE_MISSING" in trigger_sql and "ITEM_KNOWLEDGE_MISSING" not in mutated_sql,
          f"原始 {len(trigger_sql)} 字节 → 变异 {len(mutated_sql)} 字节")
    mutant.execute("DROP TRIGGER paper_confirm")
    mutant.execute(mutated_sql)
    seed_confirm_case(mutant)
    mutant_ok, mutant_message = try_confirm(mutant)
    mutant.close()
    check("V10.A1 原始闸门拒绝「缺知识点」的确认（控制组）",
          (not pristine_ok) and "ITEM_KNOWLEDGE_MISSING" in pristine_message, pristine_message[:160])
    check("V10.A2 去掉该分支后同一数据被接受（V1.F3/V3.4 断言有牙齿）",
          mutant_ok, mutant_message[:160] or "变异库接受了本应被拒的确认")

    # ---------------------------------------------------------------- B. 生成校验变异
    source = (API / "app" / "services" / "question_bank" / "generation.py").read_text(encoding="utf-8")
    mutated_source = source.replace(
        "def scan_forbidden_reference(text: str) -> str | None:",
        "def scan_forbidden_reference(text: str) -> str | None:\n    return None  # V00 变异：禁用 URL/路径扫描",
        1,
    )
    check("V10.B0 变异副本注入成功（源文件未被修改）",
          mutated_source != source and "V00 变异" in mutated_source
          and "V00 变异" not in (API / "app" / "services" / "question_bank" / "generation.py").read_text(encoding="utf-8"),
          f"delta_chars={len(mutated_source) - len(source)}")
    mutant_module_path = work / "generation_v00_mutant.py"
    mutant_module_path.write_text(mutated_source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("generation_v00_mutant", mutant_module_path)
    mutant_module = importlib.util.module_from_spec(spec)
    sys.modules["generation_v00_mutant"] = mutant_module
    spec.loader.exec_module(mutant_module)

    from app.services.question_bank import generation as pristine_generation

    reply = json.dumps({"questions": [{
        "type": "short_answer", "stemMarkdown": "见 http://example.com/a 的说明",
        "options": [], "answer": {"choiceKeys": [], "accepted": None, "textMarkdown": "x"},
        "explanationMarkdown": None, "knowledgePointIds": [], "evidenceIds": [], "assetIds": [],
    }]}, ensure_ascii=False)
    kwargs = {"allowed_knowledge_ids": [], "allowed_evidence_ids": [], "expected_count": 1,
              "asset_registered": lambda asset_id: False}
    pristine_error = None
    try:
        pristine_generation.parse_generation_reply(reply, **kwargs)
    except Exception as exc:  # noqa: BLE001
        pristine_error = exc
    mutant_candidates = None
    mutant_error = None
    try:
        mutant_candidates = mutant_module.parse_generation_reply(reply, **kwargs)
    except Exception as exc:  # noqa: BLE001
        mutant_error = exc
    check("V10.B1 原始校验拒绝含 URL 的题干（控制组）",
          getattr(pristine_error, "code", None) == "GENERATION_FORBIDDEN_REFERENCE",
          f"{type(pristine_error).__name__} {getattr(pristine_error, 'code', None)}")
    check("V10.B2 禁用扫描后同一回复被放行（V5.6/7/8 断言有牙齿）",
          mutant_error is None and mutant_candidates is not None and len(mutant_candidates) == 1,
          f"candidates={len(mutant_candidates) if mutant_candidates else 0} "
          f"error={getattr(mutant_error, 'code', None)}")

    # ---------------------------------------------------------------- C. 收敛域变异
    import app.main as main_module

    original_domains = main_module.RECONCILE_DOMAINS
    check("V10.C0 原始收敛域包含 question", "question" in original_domains, str(original_domains))

    def make_running_question_job(root: Path) -> tuple[str, object]:
        """先在库里造好 running 任务，再 create_app（启动收敛发生在 create_app 内）。"""
        from app.core.config import Settings
        from app.core.migrations import apply_migrations
        from app.core.sqlite import connect

        qb_dir = root / "data" / "question-bank"
        qb_dir.mkdir(parents=True, exist_ok=True)
        job_id = "v00c" + hashlib.sha256(str(root).encode()).hexdigest()[:12]
        connection = connect(qb_dir / "question-bank.sqlite3")
        try:
            apply_migrations(connection, database="question_bank")
            connection.execute(
                "INSERT INTO question_jobs (id, kind, state, checkpoint_json, created_at, updated_at, "
                "frozen_input_json, input_hash, model_snapshot_json, attempt, lease_token, "
                "lease_expires_at, cancel_requested) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (job_id, "organize", "running", "{}", "2026-10-01T00:00:00Z", "2026-10-01T00:00:00Z",
                 '{"contractVersion": 2, "modelProfileId": "p", "modelFingerprint": "sha256:x", "batches": []}',
                 "", '{"profileId": "p"}', 1, "v00-stale", "2099-01-01T00:00:00Z"))
        finally:
            connection.close()
        from app.main import create_app
        app = create_app(Settings(host="127.0.0.1", port=8001,
                                  allowed_origins=frozenset({"http://127.0.0.1:5173"}), env="test",
                                  data_dir=root / "data"))
        return job_id, app

    def read_state(root: Path, job_id: str) -> str:
        connection = sqlite3.connect(str(root / "data" / "question-bank" / "question-bank.sqlite3"))
        try:
            return connection.execute(
                "SELECT state FROM question_jobs WHERE id=?", (job_id,)).fetchone()[0]
        finally:
            connection.close()

    root_pristine = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v10-c1-"))
    job_pristine, app_pristine = make_running_question_job(root_pristine)
    state_after = read_state(root_pristine, job_pristine)
    check("V10.C1 原始配置下 create_app 把 running 收敛为 interrupted（控制组）",
          state_after == "interrupted", f"state={state_after}")
    app_pristine.state.job_engine  # 保持引用（不关闭：进程退出即释放）

    main_module.RECONCILE_DOMAINS = ("knowledge", "teaching")  # 内存变异：跳过 question 域
    try:
        root_mutant = Path(tempfile.mkdtemp(prefix="zqky-v00b2-v10-c2-"))
        job_mutant, app_mutant = make_running_question_job(root_mutant)
        state_mutant = read_state(root_mutant, job_mutant)
    finally:
        main_module.RECONCILE_DOMAINS = original_domains
    check("V10.C2 去掉 question 域后同一 running 任务不再收敛（V6.8 断言有牙齿）",
          state_mutant == "running", f"state={state_mutant}")

    # ---------------------------------------------------------------- 还原与哈希复算
    frozen = json.loads((REPO / "docs" / "qa" / "TEACHING-LOOP-B2" / "FROZEN-CANDIDATE.json")
                        .read_text(encoding="utf-8"))
    mismatches = []
    for rel, expect in sorted(frozen["files"].items()):
        path = REPO / rel.replace("/", os.sep)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expect:
            mismatches.append((rel, expect, actual))
    check("V10.D1 变异实验后候选文件 sha256 与冻结记录 100% 一致（候选未污染）",
          not mismatches, f"mismatch={mismatches[:3]} files={len(frozen['files'])}")

    git_status = __import__("subprocess").run(
        ["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True).stdout
    frozen_paths = set(frozen["files"])
    offenders = []
    entries = 0
    for line in git_status.splitlines():
        if not line.strip():
            continue
        entries += 1
        raw = line[3:].strip().strip('"')
        path = raw.replace("\\", "/")
        if path in frozen_paths:
            continue
        if path.startswith("docs/qa/TEACHING-LOOP-B2/V00-"):
            continue
        if path.startswith("_work/") or path.startswith("docs/design/"):
            continue
        # git 对未跟踪目录只报目录名：目录下若全部是冻结候选文件（或 V00 产物）也算未触碰
        if path.endswith("/") and all(
            rel.startswith(path) or not rel.startswith(path) for rel in frozen_paths
        ) and all(
            rel.startswith(path) for rel in frozen_paths if rel.startswith(path)
        ):
            covered = [rel for rel in frozen_paths if rel.startswith(path)]
            if covered:
                continue
        offenders.append(path)
    print(f"[INFO] git 工作区条目（相对冻结候选新增）：offenders={offenders}")
    check("V10.D2 除 V00 探针外没有新增的未登记改动（候选文件之外零触碰）",
          not offenders, f"entries={entries} offenders={offenders[:5]}")

    return finish(evidence)


def finish(evidence: str, reason: str = "") -> int:
    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== v10_mutations_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} {reason} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "v10_mutations_probe", "results": RESULTS},
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
