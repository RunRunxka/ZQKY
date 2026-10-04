"""Read-only product audit; refresh only root final evidence records."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
BATCH = ROOT / 'docs/qa/TEACHING-LOOP-B3-FIX-20261002'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


full = read(BATCH / 'browser-full-r7/results.json')
summary = read(BATCH / 'FULL-E2E-SUMMARY.json')
scale_stdout = []
scale_annotations = []
stack = list(full['suites'])
while stack:
    suite = stack.pop()
    stack.extend(suite.get('suites', []))
    for spec in suite.get('specs', []):
        if '200' not in spec['title']:
            continue
        for test in spec['tests']:
            scale_annotations.extend(test.get('annotations', []))
            for result in test['results']:
                scale_stdout.extend(result.get('stdout', []))
assert scale_stdout, 'Scale measurements must be present in original full-run stdout'
summary['scaleStdout'] = scale_stdout
summary['scaleAnnotations'] = scale_annotations
summary['scaleEvidenceFormat'] = 'original Playwright result stdout and scale annotation; not a JSON attachment'
save(BATCH / 'FULL-E2E-SUMMARY.json', summary)

manifest = read(BATCH / 'FROZEN-CANDIDATE.json')
mismatches = [path for path, digest in manifest['files'].items() if sha(ROOT / path) != digest]
assert not mismatches
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == '6aeb57280f6a7e0d7391cad4d150745479ea58ec'
assert subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip() == 'main'
assert sha(ROOT / 'apps/web/next-env.d.ts') == '0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc'
verification = read(BATCH / 'FINAL-VERIFICATION.json')
verification['checkedAt'] = datetime.now(timezone.utc).isoformat()
verification['candidateMismatchCount'] = len(mismatches)
verification['finalEvidenceAudit'] = 'source/document closeout only; candidate 168 remains unchanged'
diff_check = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True)
(BATCH / 'logs/root-final-diff-check.txt').write_bytes(diff_check.stdout + diff_check.stderr)
assert diff_check.returncode == 0
save(BATCH / 'FINAL-VERIFICATION.json', verification)

post = read(BATCH / 'POST-ACCEPTANCE-DOCS.json')
post['checkedAt'] = datetime.now(timezone.utc).isoformat()
for record in post['files'] + post['rootEvidence']:
    record['diskSha256'] = sha(ROOT / record['path'])
save(BATCH / 'POST-ACCEPTANCE-DOCS.json', post)
delivery = read(BATCH / 'DELIVERY-FILES.json')
for record in delivery['files']:
    record['sha256'] = sha(ROOT / record['path'])
delivery['checkedAt'] = datetime.now(timezone.utc).isoformat()
save(BATCH / 'DELIVERY-FILES.json', delivery)
print(json.dumps({'hashCount': len(manifest['files']), 'mismatches': mismatches, 'scaleStdout': scale_stdout, 'scaleAnnotations': scale_annotations, 'fullE2E': full['stats'], 'diffCheckExit': diff_check.returncode}, ensure_ascii=False, indent=2))
