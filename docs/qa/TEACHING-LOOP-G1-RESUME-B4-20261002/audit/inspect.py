"""Read-only G1R audit: files/config/build manifests only; no app imports."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
QA = REPO / 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
phase = sys.argv[1] if len(sys.argv) > 1 else 'initial'

def read(path):
    return json.loads((REPO / path).read_text(encoding='utf-8-sig'))

def audit(files):
    differences = []
    for name, expected in files.items():
        path = REPO / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'missing'
        if actual != expected:
            differences.append({'path': name, 'expected': expected, 'actual': actual})
    return {'count': len(files), 'mismatchCount': len(differences), 'differences': differences}

baseline = read('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/BASELINE.json')
g1 = read('docs/qa/TEACHING-LOOP-G1-B4-20261002/CANDIDATE-g1-r2.json')
prior = read('docs/qa/TEACHING-LOOP-G1-B4-20261002/BASELINE.json')['sourceFiles']
protected = read('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/PROTECTED-EVIDENCE.json')
build = read('docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/BUILD-IDENTITY.json')
product_changes = []
for name, expected in prior.items():
    if (('/app/' in name and name.startswith('apps/api/')) or ('/src/' in name and name.startswith('apps/web/'))) and '.test.' not in name:
        current = baseline['sourceFiles'].get(name)
        if current != expected:
            product_changes.append({'path': name, 'beforeG1': expected, 'current': current})
report = {'capturedAt': datetime.now(timezone.utc).isoformat(),
          'phase': phase,
          'branch': subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip(),
          'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          'g1-r2': audit(g1['files']),
          'resumeBaseline': audit(baseline['sourceFiles']),
          'protectedEvidence': audit(protected),
          'buildFiles': audit(build['files']),
          'buildId': (REPO/'apps/web/.next/BUILD_ID').read_text(encoding='utf-8').strip(),
          'expectedBuildId': build['buildId'],
          'rewrites': json.loads((REPO/'apps/web/.next/routes-manifest.json').read_text(encoding='utf-8'))['rewrites'],
          'g1ProductChanges': product_changes,
          'nextEnvMatchesOriginal': (REPO/'apps/web/next-env.d.ts').read_bytes()==(QA/'next-env.original.bin').read_bytes()}
report['newCandidates'] = {}
for path in QA.glob('CANDIDATE*.json'):
    candidate = json.loads(path.read_text(encoding='utf-8-sig'))
    changed = [{'path': name, 'before': expected, 'after': candidate['files'].get(name)}
               for name, expected in g1['files'].items() if candidate['files'].get(name) != expected]
    report['newCandidates'][path.name] = {
        'manifestSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source': audit(candidate['files']),
        'executableQa': audit(candidate.get('executableQaFiles', {})),
        'changesFromG1r2': changed,
        'sourceSetExactlySame': set(candidate['files']) == set(g1['files']),
        'metadata': {k:v for k,v in candidate.items() if k not in ('files', 'executableQaFiles')}}
(QA/f'audit/{phase}-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='g1ProductChanges'},ensure_ascii=False,indent=2))
print('G1 actual product changes:')
for item in product_changes:
    print(item['path'])
allowed = {'tests/e2e/assessments.spec.ts', 'tests/e2e/question-bank-real.spec.ts'}
failures = []
if {x['path'] for x in report['g1-r2']['differences']} - allowed:
    failures.append('unauthorized original source drift')
for key in ('protectedEvidence', 'buildFiles'):
    if report[key]['mismatchCount']:
        failures.append(key)
if report['buildId'] != report['expectedBuildId'] or not report['nextEnvMatchesOriginal']:
    failures.append('build identity / next-env')
for name, candidate in report['newCandidates'].items():
    if candidate['source']['mismatchCount'] or candidate['executableQa']['mismatchCount']:
        failures.append(name + ' SHA')
    if not candidate['sourceSetExactlySame'] or {x['path'] for x in candidate['changesFromG1r2']} != allowed:
        failures.append(name + ' exact allowed scope')
if failures:
    print('FAILURES:', failures)
    sys.exit(1)
