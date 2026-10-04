"""Independent full-coverage r2 addendum; previous behavioral evidence stays intact."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[3]
BATCH = DIRECTORY.parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


first_path, second_path = BATCH / "CANDIDATE-g1-r1.json", BATCH / "CANDIDATE-g1-r2.json"
first, second = [json.loads(path.read_text(encoding="utf-8")) for path in (first_path, second_path)]
common = set(first["files"]) & set(second["files"])
new_paths = sorted(set(second["files"]) - set(first["files"]))
removed_paths = sorted(set(first["files"]) - set(second["files"]))
changed_common = sorted(path for path in common if first["files"][path] != second["files"][path])
assert len(first["files"]) == first["count"] == len(common) == 825
assert len(second["files"]) == second["count"] == 826
assert new_paths == ["apps/api/.env.example"] and not removed_paths and not changed_common
actual = {name: sha((ROOT / name).read_bytes()) for name in second["files"]}
drift = sorted(name for name in second["files"] if second["files"][name] != actual[name])
assert not drift
protected = json.loads((BATCH / "PROTECTED-EVIDENCE.json").read_text(encoding="utf-8"))
protected_actual = {name: sha((ROOT / name).read_bytes()) for name in protected}
protected_drift = sorted(name for name in protected if protected[name] != protected_actual[name])
assert len(protected) == 629 and not protected_drift
new_name = new_paths[0]
working_diff = git("diff", "--name-only", "--", new_name).decode("utf-8").strip()
index_diff = git("diff", "--cached", "--name-only", "--", new_name).decode("utf-8").strip()
tracked = git("ls-files", "--error-unmatch", "--", new_name).decode("utf-8").strip()
head_bytes = git("show", "HEAD:" + new_name)
head_sha = sha(head_bytes)
assert tracked == new_name and not working_diff and not index_diff
# Git normalizes the tracked example's CRLF working-copy bytes to LF.
normalized_local_sha = sha((ROOT / new_name).read_bytes().replace(b"\r\n", b"\n"))
assert normalized_local_sha == sha(head_bytes.replace(b"\r\n", b"\n"))
assert not (ROOT / new_name).is_symlink()
branch, head = [git(*args).decode("utf-8").strip() for args in
                (("rev-parse", "--abbrev-ref", "HEAD"), ("rev-parse", "HEAD"))]
assert branch == "main" and head == "6aeb57280f6a7e0d7391cad4d150745479ea58ec"
result = {
    "task": "G1-V00-JOBS r2 coverage addendum", "status": "pass", "capturedAt": datetime.now(UTC).isoformat(),
    "branch": branch, "head": head,
    "manifestR1Sha256": sha(first_path.read_bytes()), "manifestR2Sha256": sha(second_path.read_bytes()),
    "r1Count": 825, "r2Count": 826, "commonCount": 825, "commonHashChanges": changed_common,
    "newPaths": new_paths, "removedPaths": removed_paths, "actualHashes": actual, "actualHashChanges": drift,
    "protectedCount": 629, "protectedActualHashes": protected_actual, "protectedHashChanges": protected_drift,
    "example": {"path": new_name, "tracked": tracked, "workingDiff": working_diff, "indexDiff": index_diff,
                "workingSha256": actual[new_name], "headBlobSha256": head_sha,
                "normalizedWorkingSha256": normalized_local_sha, "normalizedEqualsHead": True},
    "behaviorProbeRerun": False,
    "reason": "All 825 r1 behavior source/test/config/lock hashes are unchanged; r2 only adds the already tracked unchanged safe example configuration to coverage.",
    "preservedBehaviorRun": {"artifact": "independent-first.xml", "passed": 52, "exitCode": 0,
                             "newRuns": 0},
}
(DIRECTORY / "r2-coverage-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
report = f"""# G1-V00-JOBS r2 覆盖审计补充

仅追加审计，原 RESULT.md、52 个行为探针及原首跑证据保持原样。结论 **pass**。

- r1 原 825 项与 r2 共同 825 项逐项 SHA 完全相同，0 改变、0 删除；r1 清单本体 SHA `{result['manifestR1Sha256']}`。
- r2 完整 826 项与实际工作区逐项 SHA 完全相同，0 漂移；r2 清单本体 SHA `{result['manifestR2Sha256']}`。
- 旧 629 份证据全部逐字节 SHA 相同，0 漂移。
- 唯一新增覆盖项为 `apps/api/.env.example`。它已被 Git 跟踪，工作区与暂存区均无 Git diff；当前文件按 Git 换行规范归一化后与 HEAD blob 完全相同。这是覆盖过滤器补漏，没有新增产品行为或配置修改。没有读取正式 `.env`。
- 分支仍为 `main`，HEAD 仍为 `{head}`；产品、原 RESULT 与原行为证据零写入。

行为候选未变，**未重复执行 52 个探针**。原首跑 `52 passed / exit 0` 继续适用于共同 825 项；本补充实际新行为运行次数为 0，不能把这次 SHA 审计计作再次运行 52 例。

实际命令（PowerShell 根目录，exit 0）：

```powershell
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/audit_r2_addendum.py
```

完整 826 项实际 SHA、629 项证据 SHA、r1/r2 对比和新增项 Git 校验收据见 r2-coverage-audit.json。脚本仅使用标准库与只读 Git 命令，未导入 app 模块、未创建业务数据、未监听端口、未构建。只写本目录此补充与独立脚本，完成后再次停写。
"""
(DIRECTORY / "ADDENDUM-r2.md").write_text(report, encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key not in
                 ("actualHashes", "protectedActualHashes")}, ensure_ascii=False, indent=2))
