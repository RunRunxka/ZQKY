"""F30-L v4 append-only opening preservation; no application imports."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
card = OUT.parent / 'B5-F30-L-v4-TASK.md'
expected = '400ee220aa10249f719bc2b9113e3229c162d268dca90e4512929886103534d0'
if sha(card) != expected:
    raise ValueError('Unexpected v4 task card bytes')
module = ROOT / 'apps/web/src/features/lesson-plan'
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(module.rglob('*')) if path.is_file()}
prior = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(OUT.rglob('*')) if path.is_file() and path.name != 'preserve_v4.py'}
for name in private:
    destination = OUT / 'before-v4-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write((ROOT / name).read_bytes())
record = {'task': 'F30-L', 'version': 4, 'status': 'BEFORE_NARROW_FIX', 'atUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': private, 'preservedPriorEvidence': prior, 'approvedProductFiles': ['apps/web/src/features/lesson-plan/components/SourcePanel.tsx', 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'], 'taskCardSha256': expected, 'sharedAndRootWrites': False, 'authorization': 'CTRL OPEN F30-L v4 after stable r2 browser first run ended, R06 only; source inputs and original95 tests preserved'}
with (OUT / 'BEFORE-v4.json').open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({'privateFiles': len(private), 'priorEvidenceFiles': len(prior), 'beforeSHA': sha(OUT / 'BEFORE-v4.json')}, ensure_ascii=False))
