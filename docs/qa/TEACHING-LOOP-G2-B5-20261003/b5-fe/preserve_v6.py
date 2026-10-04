"""Append-only F30-L v6 opening source/evidence preservation."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
expected = 'd99ade2fe66963dd3217dc167d1d6be195eaded690df01254e0d1f0423470a5d'
if sha(OUT.parent / 'B5-F30-L-v6-TASK.md') != expected:
    raise ValueError('Unexpected v6 task card')
module = ROOT / 'apps/web/src/features/lesson-plan'
private = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(module.rglob('*')) if p.is_file()}
prior = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'preserve_v6.py'}
for name in private:
    destination = OUT / 'before-v6-source' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write((ROOT / name).read_bytes())
record = {'task': 'F30-L', 'version': 6, 'status': 'BEFORE_NARROW_FIX', 'atUtc': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': private, 'preservedPriorEvidence': prior, 'approvedProductFiles': ['apps/web/src/features/lesson-plan/model/DocumentContext.tsx', 'apps/web/src/features/lesson-plan/components/DocumentGateway.tsx', 'apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx', 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'], 'taskCardSha256': expected, 'sharedAndRootWrites': False, 'authorization': 'CTRL OPEN F30-L v6 after full27 diagnostic runtime ended; document-owned private operation notification, immediate ref and R07 LeaveProtection unchanged'}
with (OUT / 'BEFORE-v6.json').open('x', encoding='utf-8') as stream:
    json.dump(record, stream, ensure_ascii=False, indent=2)
print(json.dumps({'privateFiles': len(private), 'priorEvidenceFiles': len(prior), 'beforeSHA': sha(OUT / 'BEFORE-v6.json')}, ensure_ascii=False))
