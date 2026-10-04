"""Owned launcher: environment isolation precedes pytest and every app import."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[3]
data_root = Path(tempfile.mkdtemp(prefix="zqky-g1-v00-jobs-"))
environment = dict(os.environ)
environment.update({"ZQKY_DATA_DIR": str(data_root), "ZQKY_ENV": "test", "PYTHONUTF8": "1",
                    "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "apps" / "api")})
run_name = sys.argv[1] if len(sys.argv) > 1 else "independent-first"
arguments = [str(ROOT / "apps/api/.venv/Scripts/python.exe"), "-m", "pytest", "-c", "apps/api/pyproject.toml",
             str(DIRECTORY / "test_independent_jobs.py"), "-q", "-s", "-o", "addopts=", "--maxfail=1",
             "--basetemp=" + str(data_root / "pytest"), "--junitxml=" + str(DIRECTORY / (run_name + ".xml"))]
started = datetime.now(UTC).isoformat()
before = time.perf_counter()
print("Running isolated independent probes: " + str(data_root), flush=True)
result = subprocess.run(arguments, cwd=ROOT, env=environment, text=True, encoding="utf-8",
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
elapsed = time.perf_counter() - before
(DIRECTORY / (run_name + ".log")).write_text(result.stdout, encoding="utf-8")
metadata = {"startedAt": started, "finishedAt": datetime.now(UTC).isoformat(), "elapsedSeconds": elapsed,
            "exitCode": result.returncode, "commandArguments": arguments, "cwd": str(ROOT),
            "isolatedDataRoot": str(data_root), "environment": {key: environment[key] for key in
            ("ZQKY_DATA_DIR", "ZQKY_ENV", "PYTHONUTF8", "PYTHONIOENCODING", "PYTHONPATH")},
            "pythonVersion": platform.python_version(), "credentialsFile": None, "listenerStarted": False}
(DIRECTORY / (run_name + "-run.json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(result.stdout[-10000:], flush=True)
print(json.dumps({key: value for key, value in metadata.items() if key not in ("environment", "commandArguments")}, ensure_ascii=False), flush=True)
sys.exit(result.returncode)
