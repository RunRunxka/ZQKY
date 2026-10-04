"""Read-only, complete SHA audit for the frozen G1 candidate."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DIRECTORY = Path(__file__).resolve().parent
candidate_path = DIRECTORY.parent / "CANDIDATE-g1-r1.json"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
actual = {}
missing = []
different = []
for relative, expected in candidate["files"].items():
    path = ROOT / relative
    if not path.is_file():
        missing.append(relative)
        continue
    actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual[relative] != expected:
        different.append({"path": relative, "expected": expected, "actual": actual[relative]})
result = {
    "candidate": candidate["version"],
    "candidateManifestSha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
    "capturedAt": datetime.now(UTC).isoformat(),
    "expectedCount": candidate["count"],
    "checkedCount": len(actual),
    "missing": missing,
    "different": different,
    "actual": actual,
}
assert len(candidate["files"]) == candidate["count"] == 825
destination = DIRECTORY / sys.argv[1]
destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "actual"}, ensure_ascii=False))
sys.exit(1 if missing or different else 0)
