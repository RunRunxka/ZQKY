"""Root-only final evidence and document closeout; no app imports or business writes."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
BATCH = ROOT / "docs/qa/TEACHING-LOOP-B3-FIX-20261002"
BASE_HEAD = "6aeb57280f6a7e0d7391cad4d150745479ea58ec"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(name: str, value) -> None:
    (BATCH / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


full = read_json(BATCH / "browser-full-r7/results.json")
assert full["stats"]["expected"] == 153
assert all(full["stats"][key] == 0 for key in ("unexpected", "flaky", "skipped"))
assert not full.get("errors")
assert git("rev-parse", "HEAD").decode().strip() == BASE_HEAD
assert git("branch", "--show-current").decode().strip() == "main"

real_tests = []
full_scale = []


def walk(suites):
    for suite in suites:
        walk(suite.get("suites", []))
        for spec in suite.get("specs", []):
            if Path(spec.get("file", "")).name not in ("assessments.spec.ts", "question-bank-real.spec.ts"):
                continue
            for test in spec["tests"]:
                assert test["status"] == "expected", spec["title"]
                real_tests.append({"file": spec["file"], "title": spec["title"], "status": test["status"], "durationMs": sum(result["duration"] for result in test["results"])})
                for result in test["results"]:
                    for attachment in result.get("attachments", []):
                        if attachment.get("body") and "json" in attachment.get("contentType", ""):
                            value = json.loads(base64.b64decode(attachment["body"]).decode("utf-8"))
                            if "scale" in attachment["name"]:
                                full_scale.append({"name": attachment["name"], "data": value})


walk(full["suites"])
assert len(real_tests) == 6, real_tests
write_json("FULL-E2E-SUMMARY.json", {"exitCode": 0, "stats": full["stats"], "realChainTests": real_tests, "scaleAttachments": full_scale, "scope": "153 full browser regressions; six batch chains connect isolated FastAPI; older mock/error tests are not expanded into real API acceptance"})

replace(BATCH / "REPORT.md", "# TEACHING-LOOP B3 总控交付报告（全量E2E收口中）", "# TEACHING-LOOP B3 总控交付报告（已完成）")
replace(BATCH / "REPORT.md", "2026-10-02，总控 `/root`。用户授权的B3实施与独立技术验收完成；全量API、check/build与六项真实浏览器门禁已通过，153项全量E2E正在运行，最终结论待该轮收口。没有启动B4，没有提交/推送/部署。", "2026-10-02，总控 `/root`。用户授权的B3实施、独立验收与适用全量门禁均完成，无遗留本批阻塞fail。全量API1523项、单测1069项及check/build、全量E2E153项均通过；完整真实链、规模与三视口独立复核通过。已停止本批工作，没有启动B4，没有提交/推送/部署。")
replace(BATCH / "REPORT.md", "| 全量E2E，r7 | **正在运行153项，待收口** | logs/root-e2e-full-r7.txt |", "| 全量E2E，r7 | **153 passed，exit0，361.327s（6.0m）**，0unexpected/0flaky/0skip | logs/root-e2e-full-r7.txt，browser-full-r7/results.json，FULL-E2E-SUMMARY.json |")
replace(BATCH / "REPORT.md", "root权威文档在产品候选之外，后验单独登记。", "r4成绩验收跟进期间root并行修改两browser spec，独立r4后验如实记录该两项漂移；随后r5重冻结且167项前后零漂移。r7独立前端与G0后验168项零漂移。root权威文档在产品候选之外，后验单独登记。")
replace(BATCH / "REPORT.md", "时间是本机一次基线，不是性能承诺；超限定位拒绝，无截断。全量E2E再跑的时间另记录最终日志。", "时间是本机一次基线，不是性能承诺；超限定位拒绝，无截断。全量E2E再次执行200×100并通过，原始测量附件保存在FULL-E2E-SUMMARY.json；两次结果不相加为测试数。")
replace(BATCH / "REPORT.md", "最终资源/hash/用户next-env原字节复核与权威文档后验将在全量E2E结束后落盘；没有提交、推送、部署、切换分支或停止未知进程。", "最终产品168项SHA零漂移、main/HEAD未变、旧B2/B3证据未改；用户next-env原字节已恢复（SHA 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc）。权威文档后验见POST-ACCEPTANCE-DOCS.json，精确变动清单见DELIVERY-FILES.json，最终核验见FINAL-VERIFICATION.json。\n\n8001/5174/16333均无监听，本批IAB页关闭且viewport reset，未停止用户/未知进程。删除六个有记录的root临时数据目录的命令被工具自动审批拒绝，仅返回blocked by policy；未请求重复批准或改用其他删除方式，六目录保留，绝对路径见RESOURCE-CLEANUP.json。浏览器临时API由fixture正常退出并清理；测试资源释放与临时文件保留分开记录。没有提交、推送、部署或切换分支。")

status = ROOT / "docs/CURRENT_STATUS.md"
replace(status, "**本轮 TEACHING-LOOP B3 修复与补齐已完成独立技术验收，正在收口全量 E2E。**", "**本轮 TEACHING-LOOP B3 修复与补齐已完成，独立验收与适用全量门禁通过。**")
replace(status, "全量E2E 153项运行中；最终门禁/资源记录见", "全量E2E 153项通过（0失败/跳过/间歇）；原next-env已恢复，测试端口释放，六个临时数据目录因工具删除审批拒绝而保留。最终门禁/资源记录见")
replace(status, "完整真实链与规模通过，全量E2E收口中", "完整真实链与规模通过；API1523/check1069/E2E153全过，r7后验168项零漂移")

replace(BATCH / "EVIDENCE-COMMANDS.md", "最新r7 check/build及真实/全量E2E的最终结果在REPORT收口后登记；运行中不提前记pass。", "最终r7门禁如下（没有重跑产品API，因为r3后端至r7不变）：\n\n| 最终命令 | 实际结果 | 证据 |\n| --- | --- | --- |\n| `npm.cmd run check`，r7，构建前代理8001 | typecheck/lint0警告/108文件1069单测/build通过，exit0；单测81.28s | logs/root-check-final-r7.txt |\n| `npm.cmd run test:e2e -- assessments.spec.ts question-bank-real.spec.ts --trace=off`，r7 | 6passed/0fail/0skip，exit0，24.6s | logs/root-browser-final-r7.txt，browser-final-r7/results.json，real-chain-receipts-r7/ |\n| `npm.cmd run test:e2e`，r7，默认trace策略 | 153passed/0unexpected/0flaky/0skip，exit0，361.327s | logs/root-e2e-full-r7.txt，browser-full-r7/results.json，FULL-E2E-SUMMARY.json |\n\n原件同时保留旧模块后端不可用错误路径的日志；这些通过的错误/替身测试不能扩大成所有旧业务真实服务验收。")
replace(BATCH / "README.md", "- [任务与文件归属]", "- [最终交付报告](REPORT.md)、[真实命令与退出码](EVIDENCE-COMMANDS.md)、[最终核验](FINAL-VERIFICATION.json)、[文档后验](POST-ACCEPTANCE-DOCS.json)、[资源释放/保留](RESOURCE-CLEANUP.json)。\n- [任务与文件归属]")

history_1440 = list((BATCH / "browser-final-r7").rglob("complete-history-1440.png"))
assert len(history_1440) == 1
shutil.copyfile(history_1440[0], BATCH / "final-history-1440.png")

frozen = read_json(BATCH / "FROZEN-CANDIDATE.json")
hash_checks = [{"path": path, "expected": expected, "actual": sha((ROOT / path).read_bytes())} for path, expected in frozen["files"].items()]
assert len(hash_checks) == 168
assert all(item["actual"] == item["expected"] for item in hash_checks)
protected_paths = ["docs/qa/TEACHING-LOOP-B2", "docs/qa/TEACHING-LOOP-B2-REVIEW-20261001", "docs/qa/TEACHING-LOOP-B3", "docs/qa/TEACHING-LOOP-B3-REVIEW-20261001"]
protected_changes = git("diff", "--name-only", "HEAD", "--", *protected_paths).decode().splitlines()
assert not protected_changes
assert sha((ROOT / "apps/web/next-env.d.ts").read_bytes()) == "0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc"
diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True)
(BATCH / "logs/root-final-diff-check.txt").write_bytes(diff_check.stdout + diff_check.stderr)
assert diff_check.returncode == 0
resource = read_json(BATCH / "RESOURCE-CLEANUP.json")
assert not resource["listenersAfter"]
write_json("FINAL-VERIFICATION.json", {"checkedAt": datetime.now(timezone.utc).isoformat(), "branch": "main", "head": BASE_HEAD, "candidateRevision": "r7", "candidateCount": 168, "candidateMismatchCount": 0, "candidateFiles": hash_checks, "protectedHistoricalPaths": protected_paths, "historicalTrackedChanges": protected_changes, "originalNextEnvExactBytesRestored": True, "gitDiffCheckExitCode": diff_check.returncode, "listenersAfter": [], "temporaryDataRetention": "six recorded roots retained after tool approval rejection", "b4Started": False, "gitCommitPushDeploy": False})

docs = ["docs/API.md", "docs/CURRENT_STATUS.md", "docs/NEXT_SESSION_START.md", "docs/PROJECT_GUIDE.md", "docs/ROUTES.md", "docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md"]
write_json("POST-ACCEPTANCE-DOCS.json", {"checkedAt": datetime.now(timezone.utc).isoformat(), "scope": "root-owned authoritative docs outside 168 product candidate; after product and full gates; no product mutation", "files": [{"path": path, "headSha256": sha(git("show", "HEAD:" + path)), "diskSha256": sha((ROOT / path).read_bytes())} for path in docs], "rootEvidence": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "diskSha256": sha(path.read_bytes())} for path in (BATCH / "REPORT.md", BATCH / "EVIDENCE-COMMANDS.md", BATCH / "G0-CLOSE-MATRIX.md", BATCH / "README.md", BATCH / "TASK-CARD.md")]})

modified = git("diff", "--name-only", "-z", "HEAD").decode("utf-8").split("\0")
untracked = git("ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
source_paths = sorted(path for path in modified + untracked if path and not path.startswith("docs/qa/TEACHING-LOOP-B3-FIX-20261002/"))
write_json("DELIVERY-FILES.json", {"initialUserChange": "apps/web/next-env.d.ts: restored exactly; excluded from root source ownership", "taskCard": "TASK-CARD.md exact ownership and v1-v7", "sourceAndAuthorityFileCountIncludingUserFile": len(source_paths), "files": [{"path": path, "sha256": sha((ROOT / path).read_bytes()), "origin": "preserved_user_change" if path == "apps/web/next-env.d.ts" else ("modified" if path in modified else "new")} for path in source_paths], "newBatchEvidence": "docs/qa/TEACHING-LOOP-B3-FIX-20261002/; root and independent evidence preserved", "oldEvidenceModified": False})
print(json.dumps({"candidate": "r7", "hashCount": 168, "mismatches": 0, "fullE2E": full["stats"], "realChains": len(real_tests), "scaleAttachments": full_scale, "sourceAndAuthorityFiles": len(source_paths), "gitDiffCheckExit": 0}, ensure_ascii=False, indent=2))
