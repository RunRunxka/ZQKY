"""F30-L v2 append-only opening preservation; no runtime/business imports."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
module = ROOT / 'apps/web/src/features/lesson-plan'
private = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(module.rglob('*')) if p.is_file()}
legacy = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'preserve_v2.py'}
for name in private:
    destination = OUT / 'before-v2-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream: stream.write((ROOT / name).read_bytes())
record = {'task': 'F30-L', 'version': 2, 'status': 'BEFORE_NARROW_FIX', 'atUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': private, 'preservedV1Evidence': legacy, 'approvedProductFiles': ['apps/web/src/features/lesson-plan/components/ProposalPanel.tsx', 'apps/web/src/features/lesson-plan/components/SourcePanel.tsx', 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'], 'sharedAndRootWrites': False}
with (OUT / 'BEFORE-v2.json').open('x', encoding='utf-8') as stream: json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({'privateFiles': len(private), 'v1EvidenceFiles': len(legacy), 'beforeSHA': sha(OUT / 'BEFORE-v2.json')}, ensure_ascii=False))
