"""F30-L v5 opening preservation, append-only and no application imports."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
card = OUT.parent / 'B5-F30-L-v5-TASK.md'
expected = '3584f751e6ddda871e3316ebc05c4fdfd89d3cf266cb369d0616e3a37f2fbfa1'
if sha(card) != expected:
    raise ValueError('Unexpected v5 task card bytes')
module = ROOT / 'apps/web/src/features/lesson-plan'
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(module.rglob('*')) if path.is_file()}
prior = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'preserve_v5.py'}
for name in private:
    destination = OUT / 'before-v5-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write((ROOT / name).read_bytes())
record = {'task': 'F30-L', 'version': 5, 'status': 'BEFORE_NARROW_FIX', 'atUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': private, 'preservedPriorEvidence': prior, 'approvedProductFiles': ['apps/web/src/features/lesson-plan/components/LeaveProtection.tsx', 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'], 'taskCardSha256': expected, 'sharedAndRootWrites': False, 'authorization': 'CTRL OPEN F30-L v5 after all full153 first runs and own services ended; R07 local writer flush leave protection only'}
with (OUT / 'BEFORE-v5.json').open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({'privateFiles': len(private), 'priorEvidenceFiles': len(prior), 'beforeSHA': sha(OUT / 'BEFORE-v5.json')}, ensure_ascii=False))
