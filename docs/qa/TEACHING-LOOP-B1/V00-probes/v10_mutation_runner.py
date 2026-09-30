"""V10 变异实验（TEACHING-LOOP B1 / V00）。

在**自己的副本**里改 3 处关键实现，证明对应探针断言有牙齿：
  M1 删掉知识点环检测触发器 → V2 的「成环父 → 422 KNOWLEDGE_CYCLE」必须失败；
  M2 去掉 student 版答案/解析过滤 → V7 的「学生版不含答案与解析」必须失败；
  M3 把启动门控 REQUIRED_TABLES 扩成 B1 表 → V1 的「仅 B0 结构旧库通过门控」必须失败。
副本放在系统临时目录；候选工作区只读，跑完用 FROZEN-CANDIDATE.json 复算 95 文件 sha256 对账。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROBE_DIR.parents[3]
sys.path.insert(0, str(PROBE_DIR))
from _probe_common import EVIDENCE_DIR, Probe  # noqa: E402

p = Probe("v10_mutations")
BASELINE = EVIDENCE_DIR


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_check() -> tuple[bool, list[str]]:
    frozen = json.loads(
        (REPO_ROOT / "docs/qa/TEACHING-LOOP-B1/FROZEN-CANDIDATE.json").read_text(encoding="utf-8")
    )
    bad = []
    for rel, want in frozen["files"].items():
        target = REPO_ROOT / rel
        if not target.is_file() or sha256_file(target) != want:
            bad.append(rel)
    return not bad, bad


def run_probe(probe_file: str, env_extra: dict[str, str]) -> tuple[int, str]:
    env = dict(os.environ)
    env.update(env_extra)
    completed = subprocess.run(
        [sys.executable, str(PROBE_DIR / probe_file)],
        cwd=str(REPO_ROOT / "apps" / "api"),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def _prefix_pass(baseline: dict[str, bool], prefix: str) -> bool:
    """基线里同前缀断言是否全 pass（探针崩溃导致名字不同时用）。"""
    matches = [ok for name, ok in baseline.items() if name.startswith(prefix)]
    return bool(matches) and all(matches)


def load_results(path: Path) -> dict[str, bool]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["name"]: item["ok"] for item in payload["results"]}


MUTATIONS = [
    {
        "id": "M1-remove-cycle-trigger",
        "file": "app/core/migrations/knowledge.py",
        "marker": "BEFORE UPDATE OF parent_id ON knowledge_points WHEN NEW.parent_id IS NOT NULL",
        "replace": (
            "BEFORE UPDATE OF parent_id ON knowledge_points WHEN 0",
            "BEFORE UPDATE OF parent_id ON knowledge_points WHEN NEW.parent_id IS NOT NULL",
        ),
        "probe": "v2_knowledge_points_probe.py",
        "expect_fail_prefix": "v2.3g",
        "expect_fail_contains": "KNOWLEDGE_CYCLE",
    },
    {
        "id": "M2-answer-leak-to-student",
        "file": "app/services/rich_content/renderer_docx.py",
        "marker": 'if variant == "teacher":',
        "replace": ('if variant == "teacher" or True:', 'if variant == "teacher":'),
        "probe": "v7_rich_renderer_probe.py",
        "expect_fail_prefix": "v7.1b",
        "expect_fail_contains": "学生版不含答案",
    },
    {
        "id": "M3-gate-requires-b1-tables",
        "file": "app/repositories/knowledge/schema.py",
        "marker": 'REQUIRED_TABLES = ("knowledge_submissions", "knowledge_jobs")',
        "replace": (
            'REQUIRED_TABLES = ("knowledge_submissions", "knowledge_jobs", "knowledge_points")',
            'REQUIRED_TABLES = ("knowledge_submissions", "knowledge_jobs")',
        ),
        "probe": "v1_migrations_probe.py",
        "expect_fail_prefix": "v1.2c",
        "expect_fail_contains": "启动门控",
    },
]

for mutation in MUTATIONS:
    work = Path(tempfile.mkdtemp(prefix=f"zqky-v10-{mutation['id']}-"))
    app_copy = work / "app"
    shutil.copytree(REPO_ROOT / "apps" / "api" / "app", app_copy)
    target = app_copy / Path(mutation["file"]).relative_to("app")
    source = target.read_text(encoding="utf-8")
    marker = mutation["marker"]
    new_text, old_text = mutation["replace"]
    if marker not in source:
        p.check(f"{mutation['id']} 变异点存在", False, f"未找到 marker: {marker}")
        continue
    target.write_text(source.replace(old_text, new_text, 1), encoding="utf-8")
    p.check(
        f"{mutation['id']} 变异已注入副本（{mutation['file']}）",
        target.read_text(encoding="utf-8") != source,
        f"copy={work}",
    )
    evidence_dir = work / "evidence"
    env_extra = {
        "ZQKY_PROBE_APP_ROOT": str(work),
        "ZQKY_PROBE_EVIDENCE_DIR": str(evidence_dir),
        "PYTHONPATH": str(work),
    }
    code, output = run_probe(mutation["probe"], env_extra)
    mutated = load_results(evidence_dir / f"{mutation['probe'].split('_probe')[0]}.json")
    if not mutated:
        candidates = list(evidence_dir.glob("*.json"))
        mutated = load_results(candidates[0]) if candidates else {}
    baseline = load_results(BASELINE / f"{mutation['probe'].split('_probe')[0]}.json")
    hit = [
        name
        for name, ok in mutated.items()
        if name.startswith(mutation["expect_fail_prefix"]) and not ok
    ]
    if not hit:
        # 变异可能让探针在断言之前就崩（下游假设被破坏）：退化为解析 stdout 的 FAIL 行
        hit = [
            line.split("] ", 1)[1].split(" ::", 1)[0]
            for line in output.splitlines()
            if line.startswith("[FAIL] ") and mutation["expect_fail_prefix"] in line
        ]
    p.check(
        f"{mutation['id']} 变异后对应断言失败（证明有牙齿）",
        bool(hit),
        json.dumps(
            {
                "exit": code,
                "expected_failing_checks": hit,
                "baseline_pass": {name: baseline.get(name) for name in hit},
                "evidence": str(evidence_dir),
            },
            ensure_ascii=False,
        ),
    )
    if hit and all(baseline.get(name) is None for name in hit):
        # 基线证据里按前缀找同名断言（探针崩溃时名字可能带完整后缀）
        baseline = {
            **baseline,
            **{
                name: ok
                for name, ok in load_results(
                    BASELINE / f"{mutation['probe'].split('_probe')[0]}.json"
                ).items()
                if name.startswith(mutation["expect_fail_prefix"])
            },
        }
    p.check(
        f"{mutation['id']} 基线同名断言为 pass（对照）",
        bool(hit)
        and all(
            baseline.get(name, _prefix_pass(baseline, mutation["expect_fail_prefix"]))
            for name in hit
        ),
        json.dumps(
            {
                "hit": hit,
                "baseline_matching": {
                    name: ok
                    for name, ok in baseline.items()
                    if name.startswith(mutation["expect_fail_prefix"])
                },
            },
            ensure_ascii=False,
        ),
    )
    shutil.rmtree(work, ignore_errors=True)

ok, bad = frozen_check()
p.check(
    "v10.fingerprint 候选 95 文件 sha256 复算 0 差异（副本变异未污染候选）",
    ok,
    json.dumps(bad, ensure_ascii=False),
)
sys.exit(p.finish())
