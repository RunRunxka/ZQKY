import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
QA = Path(__file__).resolve().parent
candidate_path = QA.parent / (sys.argv[2] if len(sys.argv) > 2 else 'CANDIDATE-g1-r1.json')
candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
actual = {}
drift = []
for name, expected in candidate['files'].items():
    source = ROOT / name
    digest = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    actual[name] = digest
    if digest != expected:
        drift.append({'path': name, 'expected': expected, 'actual': digest})
record = {'candidate': candidate['version'], 'checkedAt': datetime.now(timezone.utc).isoformat(),
          'count': len(actual), 'drift': drift, 'files': actual}
(QA / ('sha-' + sys.argv[1] + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'candidate': candidate['version'], 'count': len(actual), 'drift': drift}, ensure_ascii=False))
sys.exit(bool(drift))
