"""Capture a single isolated generation-only narrow regression execution."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

here = Path(__file__).resolve().parent
label = sys.argv[1] if len(sys.argv) > 1 else "first"
assert label in {"first", "second"}
repo = here.parents[3]
api = repo / "apps" / "api"
tmp = Path(tempfile.mkdtemp(prefix="zqky-b5-generation-review-"))
environment = dict(os.environ, ZQKY_DATA_DIR=str(tmp / "data"), ZQKY_ENV="test", PYTHONUTF8="1")
args = [sys.executable, "-m", "pytest", "-q", str(here / "test_review_generation.py"),
        "tests/test_lesson_generation_sources.py", "tests/test_lesson_generation_jobs.py",
        "tests/test_lesson_generation_privacy.py::test_real_provider_serialized_wire_only_anonymous_target_counts"]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = subprocess.run(args, cwd=api, env=environment, text=True, encoding="utf-8", capture_output=True)
(here / f"narrow-{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
receipt = dict(startedAt=started, completedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               argv=args, cwd=str(api), tempRoot=str(tmp), returncode=result.returncode,
               log=f"narrow-{label}.log", appMainImportedByExistingConftest=True, realNetwork=False,
               formalData=False, credentials=False)
(here / f"narrow-{label}-command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False))
print(result.stdout[-4000:])
sys.exit(result.returncode)
