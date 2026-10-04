"""Own one new isolated pytest run; retain first logs and all owned test data."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser()
parser.add_argument("--label", required=True)
parser.add_argument("files", nargs="+")
args = parser.parse_args()
if not args.label.replace("-", "").isalnum():
    raise ValueError("unsafe evidence label")
repo = Path.cwd().resolve()
out = Path(__file__).resolve().parent
receipt_path, log_path, xml_path = [out / (args.label + suffix) for suffix in ("-command.json", ".log", ".xml")]
if any(p.exists() for p in (receipt_path, log_path, xml_path)):
    raise ValueError("never overwrite a previous run")
sample = Path(tempfile.mkdtemp(prefix="zqky-g2-be-" + args.label + "-"))
(sample / "empty-textbooks").mkdir()
(sample / "tmp").mkdir()
tempfile.tempdir = str(sample / "tmp")
isolated = dict(ZQKY_DATA_DIR=str(sample / "data"), ZQKY_ENV="test", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                PYTHONDONTWRITEBYTECODE="1", ZQKY_QDRANT_URL="http://127.0.0.1:16333",
                ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9", ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / "empty-textbooks"),
                ZQKY_KEEP_TEST_DATA="1", ZQKY_G2_BE_RUN=args.label)
os.environ.update(isolated)
sys.dont_write_bytecode = True
sys.path.insert(0, str(repo / "apps/api"))
retained_cleanup = []
original_rmtree = shutil.rmtree
def retain_owned(path, *positional, **keywords):
    resolved = Path(path).resolve()
    if resolved == sample or sample in resolved.parents:
        retained_cleanup.append(str(resolved))
        return
    raise RuntimeError("Refusing cleanup outside this new owned sample root: " + str(resolved))


class Tee:
    def __init__(self, first, second):
        self.first, self.second = first, second
    def write(self, value):
        self.first.write(value)
        self.second.write(value)
        self.flush()
        return len(value)
    def flush(self):
        self.first.flush()
        self.second.flush()
    def isatty(self):
        return False


source_paths = ["apps/api/app/services/practices/service.py", "apps/api/tests/practices_support.py",
                "apps/api/tests/test_practices_api.py", "apps/api/tests/test_practices_draft_replay.py",
                "apps/api/app/contracts/b4.py"]
def source_hashes():
    return {str(path): hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in source_paths}
receipt = dict(label=args.label, command=[sys.executable, *sys.argv], pytestArgs=args.files,
               cwd=str(repo), pid=os.getpid(), startedAt=datetime.now(timezone.utc).isoformat(),
               env=isolated, sampleRoot=str(sample), settingsCredentialsFile=None,
               sourceBefore=source_hashes(), status="running", tcpServerStarted=False)
receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
start = time.perf_counter()
code = None
try:
    with log_path.open("x", encoding="utf-8") as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            # This bounded retention override affects only this new owned root.
            shutil.rmtree = retain_owned
            from app.core.config import Settings
            assert Settings.from_env().credentials_file is None
            import pytest
            code = int(pytest.main(["-c", "apps/api/pyproject.toml", *args.files,
                                   "--basetemp=" + str(sample / "pytest"), "--junitxml=" + str(xml_path)]))
finally:
    shutil.rmtree = original_rmtree
    receipt.update(status="complete" if code is not None else "runner_error", exit=code,
                   wallTimeMs=round((time.perf_counter() - start) * 1000, 3),
                   finishedAt=datetime.now(timezone.utc).isoformat(), logClosed=True,
                   logSHA256=hashlib.sha256(log_path.read_bytes()).hexdigest() if log_path.exists() else None,
                   sourceAfter=source_hashes(), samplePreserved=sample.exists(), retainedCleanup=retained_cleanup)
    if xml_path.exists():
        suites = ET.parse(xml_path).getroot()
        receipt["junit"] = [{k: s.get(k) for k in ("name", "tests", "failures", "errors", "skipped", "time")}
                            for s in suites.iter("testsuite")]
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: receipt[k] for k in ("label", "pid", "exit", "wallTimeMs", "sampleRoot")}, ensure_ascii=False))
sys.exit(code if code is not None else 1)
