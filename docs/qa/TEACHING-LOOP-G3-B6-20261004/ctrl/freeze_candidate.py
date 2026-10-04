"""Freeze a stopped product/QA candidate. Build is added only after actual check."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / 'docs/qa/TEACHING-LOOP-G3-B6-20261004'
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--with-build', action='store_true')
args = parser.parse_args()
assert args.label.replace('-', '').isalnum()
target = BATCH / ('CANDIDATE-' + args.label + '.json')
assert not target.exists()
baseline = json.loads((BATCH / 'BASELINE-v1.json').read_bytes())
sha = lambda data: hashlib.sha256(data).hexdigest()
hashes = lambda names: {name: sha((ROOT / name).read_bytes()) for name in sorted(names)}
source_names = set(baseline['groups']['sourceFiles']['files'])
source_names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'apps/web/src/features/lesson-plan').rglob('g3-*.test.tsx'))
sources = hashes(source_names)
new_qa = {p.relative_to(ROOT).as_posix() for p in BATCH.rglob('*')
    if p.is_file() and p.suffix in ('.py', '.ts', '.tsx', '.mjs', '.ps1')}
new_qa.add('docs/qa/TEACHING-LOOP-G3-B6-20261004/v00/seed-v1.json')
qa_names = set(baseline['groups']['executableQaFiles']['files']) | new_qa
qa = hashes(qa_names)
shared = hashes(baseline['groups']['sharedContractFiles']['files'])
assert shared == baseline['groups']['sharedContractFiles']['files']
next_env = sha((ROOT / 'apps/web/next-env.d.ts').read_bytes())
assert next_env == baseline['nextEnvSHA']
record = dict(version=args.label, capturedAtUtc=datetime.now(timezone.utc).isoformat(),
    branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip(),
    head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
    oldCandidateHead=baseline['oldCandidateHead'], sourceFiles=sources, sourceCount=len(sources),
    executableQaFiles=qa, executableQaCount=len(qa), sharedContractFiles=shared,
    sharedContractCount=len(shared), nextEnvSHA=next_env,
    stoppedProduct=True, originalTaskStatus='G3_PENDING_INDEPENDENT_ACCEPTANCE_B6_NOT_STARTED',
    openingBaselineSHA=sha((BATCH / 'BASELINE-v1.json').read_bytes()),
    openingDevCacheDifferenceCount=73, oldQaOpeningCount=baseline['oldQaCount'],
    changedSourceFromOpening=[name for name, digest in baseline['groups']['sourceFiles']['files'].items() if sources[name] != digest],
    addedSourceFromOpening=sorted(source_names - set(baseline['groups']['sourceFiles']['files'])),
    qaFilesAreNotTestCounts=True, gitWrites=False)
if args.with_build:
    build_names = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'apps/web/.next').rglob('*')
        if p.is_file() and 'cache' not in p.relative_to(ROOT / 'apps/web/.next').parts}
    record['buildFiles'] = hashes(build_names)
    record['buildCount'] = len(build_names)
    record['buildId'] = (ROOT / 'apps/web/.next/BUILD_ID').read_text().strip()
    record['actualRewrites'] = json.loads((ROOT / 'apps/web/.next/routes-manifest.json').read_bytes())['rewrites']
target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: record.get(k) for k in ('version', 'head', 'sourceCount', 'executableQaCount', 'sharedContractCount', 'changedSourceFromOpening', 'addedSourceFromOpening', 'buildId', 'buildCount')}, ensure_ascii=False))
print(json.dumps({'candidate': str(target.relative_to(ROOT)), 'SHA': sha(target.read_bytes())}, ensure_ascii=False))
