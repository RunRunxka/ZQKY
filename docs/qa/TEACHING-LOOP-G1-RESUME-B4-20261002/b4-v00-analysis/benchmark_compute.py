"""Cold/warm production computation timing only; NEVER an expected-output oracle."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

if os.environ.get("ZQKY_ENV") != "test" or os.environ.get("PYTHONUTF8") != "1":
    raise RuntimeError("isolated test/UTF8 environment required before app imports")
repo = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repo / "apps/api"))
from app.core.config import Settings
assert Settings.from_env().credentials_file is None
from app.services.analysis.aggregate import aggregate

input_path, output_path = map(Path, sys.argv[1:3])
facts = json.loads(input_path.read_text(encoding="utf-8"))
timings = {"pid": os.getpid(), "python": sys.executable, "inputSha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
           "coldDefinition": "first aggregate call in this newly spawned Python process",
           "expectationsProduced": False}
for phase in ("cold", "warm"):
    start = time.perf_counter()
    aggregate(facts)
    timings[phase + "AggregateMs"] = round((time.perf_counter() - start) * 1000, 3)
output_path.write_text(json.dumps(timings, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(timings, ensure_ascii=False), flush=True)
