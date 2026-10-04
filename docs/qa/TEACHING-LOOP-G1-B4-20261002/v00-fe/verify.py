"""Read-only disk audit. No application/settings imports or database access."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[4]
QA = REPO / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'

def check(name, key=None):
    value = json.loads((QA / name).read_text(encoding='utf-8-sig'))
    files = value[key] if key else value
    mismatches = []
    for name, expected in files.items():
        path = REPO / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'missing'
        if actual != expected:
            mismatches.append({'path': name, 'expected': expected, 'actual': actual})
    return {'count': len(files), 'mismatchCount': len(mismatches), 'mismatches': mismatches}

report = {'capturedAt': datetime.now(timezone.utc).isoformat(),
          'g1-r1': check('CANDIDATE-g1-r1.json', 'files'),
          'g1-r2': check('CANDIDATE-g1-r2.json', 'files'),
          'oldEvidence': check('PROTECTED-EVIDENCE.json')}
current = (REPO / 'apps/web/next-env.d.ts').read_bytes()
original = (QA / 'next-env.original.bin').read_bytes()
report['nextEnv'] = {'matchesOriginalBytes': current == original,
                     'sha256': hashlib.sha256(current).hexdigest()}
out = QA / 'v00-fe/hash-after.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(1 if any(report[k]['mismatchCount'] for k in ('g1-r1','g1-r2','oldEvidence')) or current != original else 0)
