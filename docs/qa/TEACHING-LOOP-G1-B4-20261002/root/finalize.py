"""Record the incomplete G1 checkpoint without importing app or touching business data."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
batch = root / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, payload):
    (batch / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

manifest_path = batch / 'CANDIDATE-g1-r2.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
protected = json.loads((batch / 'PROTECTED-EVIDENCE.json').read_text(encoding='utf-8-sig'))
drift = [p for p, digest in manifest['files'].items() if not (root / p).is_file() or sha(root / p) != digest]
old_drift = [p for p, digest in protected.items() if not (root / p).is_file() or sha(root / p) != digest]
next_matches = (root / 'apps/web/next-env.d.ts').read_bytes() == (batch / 'next-env.original.bin').read_bytes()
assert not drift and not old_drift and next_matches
branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=root).decode().strip()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()
assert branch == manifest['branch'] and head == manifest['head']
status = subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=root).decode('utf-8')
(batch / 'final-git-status.txt').write_text(status, encoding='utf-8')
staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=root).decode('utf-8').splitlines()

documents = {}
for path in sorted((root / 'docs').rglob('*.md')):
    relative = path.relative_to(root)
    if 'archive' in relative.parts or 'qa' in relative.parts:
        continue
    documents[relative.as_posix()] = sha(path)
documents['docs/qa/README.md'] = sha(root / 'docs/qa/README.md')
write('AUTHORITY-DOCUMENTS.json', {
    'capturedAt': datetime.now(timezone.utc).isoformat(),
    'coverage': 'Current docs Markdown excluding archive and batch QA; plus docs/qa/README.md',
    'count': len(documents), 'files': documents,
})

independent = []
for relative, expected in (
    ('v00-jobs/independent-first.xml', 52),
    ('v00-score-qb/accepted-v2.xml', 53),
    ('v00-fe/component-third.xml', 20),
    ('v00-fe/real-api-third.xml', 1),
):
    cases = list(ET.parse(batch / relative).iter('testcase'))
    failures = sum(len(list(case.iter('failure'))) for case in cases)
    errors = sum(len(list(case.iter('error'))) for case in cases)
    skipped = sum(len(list(case.iter('skipped'))) for case in cases)
    assert len(cases) == expected and not failures and not errors and not skipped
    independent.append({'xml': relative, 'passed': len(cases), 'failed': failures, 'errors': errors, 'skipped': skipped})

report_path = batch / 'REPORT.md'
summary = {
    'capturedAt': datetime.now(timezone.utc).isoformat(),
    'status': 'incomplete_awaiting_frontend_external_state',
    'objectiveComplete': False,
    'branch': branch, 'head': head, 'stagedFiles': staged,
    'candidateVersion': 'g1-r2', 'candidateCount': manifest['count'],
    'candidateManifestSHA256': sha(manifest_path), 'sourceDrift': drift,
    'protectedEvidenceCount': len(protected), 'protectedEvidenceDrift': old_drift,
    'nextEnvMatchesOriginal': next_matches,
    'nextEnvSHA256': sha(root / 'apps/web/next-env.d.ts'),
    'productFilesChangedFromStart': 13, 'testFilesChangedFromStart': 8,
    'G1': {'eightIndependentCorrectBehaviors': 'pass', 'overallGate': 'incomplete',
           'check': {'exitCode': 0, 'unitFiles': 109, 'unitPassed': 1088},
           'api': {'exitCode': 0, 'passed': 1599, 'skipped': 1},
           'scoreSpecialist': {'passed': 169, 'skipped': 0, 'scale200x100': 'pass'},
           'independentSingleRuns': independent,
           'actualBrowser': 'not_run', 'e2e': 'not_run', 'affectedChatBrowserRegression': 'not_run'},
    'B4': 'not_started',
    'approvalRejection': {'action': 'Start isolated Next frontend on 127.0.0.1:5174',
                          'reason': 'blocked by policy', 'bypassed': False},
    'resources': 'RESOURCES.json',
    'report': 'REPORT.md', 'reportSHA256': sha(report_path),
    'authorityDocuments': 'AUTHORITY-DOCUMENTS.json',
    'gitWriteOperations': 'none',
}
write('FINAL-SUMMARY.json', summary)
print(json.dumps({key: summary[key] for key in ('status', 'objectiveComplete', 'candidateCount', 'candidateManifestSHA256', 'nextEnvMatchesOriginal', 'reportSHA256')}, ensure_ascii=False))
