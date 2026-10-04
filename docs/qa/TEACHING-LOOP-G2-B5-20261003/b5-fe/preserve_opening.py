"""F30 private opening bytes; no application imports or services."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

repo = Path.cwd()
qa = repo / "docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-fe"
target = qa / "opening-v1.json"
if target.exists():
    raise SystemExit("Refusing to replace opening evidence")
manifest_path = repo / "docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/B5-CONTRACT-FROZEN-v1.json"
manifest_bytes = manifest_path.read_bytes()
expected = "8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db"
assert hashlib.sha256(manifest_bytes).hexdigest() == expected
manifest = json.loads(manifest_bytes)
assert len(manifest["files"]) == 33
for name, sha in manifest["files"].items():
    assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == sha, name
sources = {}
for source in (repo / "apps/web/src/features/lesson-plan").rglob("*"):
    if not source.is_file():
        continue
    name = source.relative_to(repo).as_posix()
    raw = source.read_bytes()
    sources[name] = hashlib.sha256(raw).hexdigest()
    copy = qa / "opening-source" / name
    copy.parent.mkdir(parents=True, exist_ok=True)
    with copy.open("xb") as stream:
        stream.write(raw)
with target.open("x", encoding="utf-8") as stream:
    json.dump({"task": "F30-L-v1", "at": datetime.now(timezone.utc).isoformat(),
               "contractSHA": expected, "contractCount": 33, "contractDrift": [],
               "sources": sources}, stream, ensure_ascii=False, indent=2)
print(json.dumps({"contractCount": 33, "drift": 0, "privateSources": len(sources)}))
