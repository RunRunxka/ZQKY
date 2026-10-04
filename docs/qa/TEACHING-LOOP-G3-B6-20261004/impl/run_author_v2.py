"""Isolated Node author checks; preserve each command and its exact pre-run sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FILES = [
    "apps/web/src/features/lesson-plan/model/useServerPersistence.ts",
    "apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx",
    "apps/web/src/features/lesson-plan/components/SourcePanel.tsx",
    "apps/web/src/features/lesson-plan/g3-source-session.test.tsx",
    "apps/web/src/features/lesson-plan/model/g3-persistence.test.tsx",
    "apps/web/src/features/lesson-plan/g3-history-copy.test.tsx",
]
CHECKS = {
    "unit": "npm.cmd run test:unit -- apps/web/src/features/lesson-plan/model/g3-persistence.test.tsx apps/web/src/features/lesson-plan/g3-history-copy.test.tsx apps/web/src/features/lesson-plan/g3-source-session.test.tsx apps/web/src/features/lesson-plan/model/server-session.test.tsx apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx apps/web/src/features/lesson-plan/lesson-workspace.test.tsx --reporter=verbose",
    "typecheck": "node node_modules/typescript/bin/tsc --noEmit --project apps/web/tsconfig.json",
    "lint": "npm.cmd run lint",
}

def main() -> int:
    label, check = sys.argv[1:3]
    path = HERE / label
    path.mkdir(exist_ok=False)
    hashes = {}
    for name in FILES:
        source = ROOT / name
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        target = path / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--no-experimental-webstorage"
    env["PYTHONUTF8"] = "1"
    receipt = {"task": "G3-IMPL-v2", "check": check, "command": CHECKS[check], "cwd": str(ROOT), "startedAt": datetime.now(timezone.utc).isoformat(), "sources": hashes, "servicesStarted": False, "apiTests": False, "gitWrites": False}
    started = time.perf_counter()
    with (path / "output.log").open("wb") as output:
        process = subprocess.Popen(["cmd.exe", "/d", "/s", "/c", CHECKS[check]], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
        receipt["pid"] = process.pid
        (path / "COMMAND.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        result = process.wait()
    receipt.update(exitCode=result, finishedAt=datetime.now(timezone.utc).isoformat(), durationMs=round((time.perf_counter() - started) * 1000, 3), afterSources={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES})
    (path / "RESULT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"label": label, "exitCode": result, "pid": process.pid, "durationMs": receipt["durationMs"], "log": str(path / "output.log")}, ensure_ascii=False))
    return result

if __name__ == "__main__":
    raise SystemExit(main())
