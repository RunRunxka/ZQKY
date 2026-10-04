"""Read-only byte audit; never import the application or modify an old receipt."""
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import os

ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / 'docs/qa/TEACHING-LOOP-G3-B6-20261004'
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate', default='CANDIDATE-G3-r2-qa5.json')
args = parser.parse_args()
assert args.label.replace('-', '').isalnum()
target = BATCH / 'ctrl' / (args.label + '.json')
assert not target.exists()
started = time.perf_counter()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
candidate_path = BATCH / args.candidate
candidate = json.loads(candidate_path.read_bytes())
baseline = json.loads((BATCH / 'BASELINE-v1.json').read_bytes())
binding = json.loads((BATCH / 'ctrl/G3-API-UNCHANGED-BINDING-v1.json').read_bytes())
drift = lambda files: [{'path': name, 'expected': value, 'actual': sha(ROOT / name)}
                       for name, value in files.items() if sha(ROOT / name) != value]
record = dict(startedAt=now(), pid=os.getpid(), candidate=args.candidate,
              candidateSHA=sha(candidate_path), groups={})
for group in ('sourceFiles', 'executableQaFiles', 'sharedContractFiles', 'buildFiles'):
    record['groups'][group] = dict(count=len(candidate[group]), drift=drift(candidate[group]))
old = drift(baseline['oldQaFiles'])
record.update(oldQAOpeningCount=len(baseline['oldQaFiles']),
    oldQAAllowedCurrentIndexDelta=[item for item in old if item['path'] == 'docs/qa/README.md'],
    oldQAUnexpectedDrift=[item for item in old if item['path'] != 'docs/qa/README.md'],
    backend410Drift=drift(binding['backendFiles']),
    nextEnvSHA=sha(ROOT / 'apps/web/next-env.d.ts'),
    nextEnvOriginalExact=(ROOT / 'apps/web/next-env.d.ts').read_bytes() ==
                         (BATCH / 'ctrl/next-env.opening.bin').read_bytes(),
    actualHead=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    actualBranch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip(),
    oldPolicyHTTP='not_run_no_retry', gitWrites=False, appMainImported=False,
    finishedAt=now(), elapsedMs=round((time.perf_counter() - started) * 1000, 3))
target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
assert all(not value['drift'] for value in record['groups'].values())
assert not record['oldQAUnexpectedDrift'] and not record['backend410Drift']
assert record['nextEnvOriginalExact'] and record['actualHead'] == baseline['head']
