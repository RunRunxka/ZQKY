"""F30-L v3 append-only opening preservation; no application imports."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
module = ROOT / 'apps/web/src/features/lesson-plan'
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(module.rglob('*')) if path.is_file()}
legacy = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'preserve_v3.py'}
for name in private:
    destination = OUT / 'before-v3-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write((ROOT / name).read_bytes())
record = {'task': 'F30-L', 'version': 3, 'status': 'BEFORE_NARROW_FIX', 'atUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': private, 'preservedPriorEvidence': legacy, 'approvedProductFiles': ['apps/web/src/features/lesson-plan/components/ProposalPanel.tsx', 'apps/web/src/features/lesson-plan/components/SourcePanel.tsx', 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'], 'sharedAndRootWrites': False, 'authorization': 'CTRL OPEN_WRITE v3 after independent v4 complete first run, including roster/classes, analysis runs and practices complete pagination'}
with (OUT / 'BEFORE-v3.json').open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({'privateFiles': len(private), 'priorEvidenceFiles': len(legacy), 'beforeSHA': sha(OUT / 'BEFORE-v3.json')}, ensure_ascii=False))
