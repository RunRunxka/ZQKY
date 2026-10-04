"""Freeze/audit this batch only; no application imports or business data reads."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
BATCH = Path(__file__).resolve().parent.parent
BASE_PATH = BATCH / 'ctrl/BASELINE.json'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(BASE_PATH) == '834cc083063e9cf484f46e0787ed199728ca5f39a48ecc57652fab349287342e'
BASE = json.loads(BASE_PATH.read_text(encoding='utf-8'))
sys.stdout.reconfigure(encoding='utf-8')
mode, version = sys.argv[1:3]
assert mode in ('freeze', 'audit') and version.replace('-', '').isalnum()
started = time.perf_counter()

def sources():
    folders = [name for name in ('apps', 'tests', 'scripts', 'infra', 'assets', '.github') if (ROOT/name).exists()]
    names = subprocess.check_output(['rg', '--files', '--hidden', *folders], cwd=ROOT).decode('utf-8').splitlines()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    names += [name for name in tracked if name and ('/' not in name.replace('\\', '/') or name.split('/')[0] in folders)]
    result = {}
    for name in sorted(set(names)):
        path = Path(name)
        if any((part.startswith('.env') and part != '.env.example') or part in
            ('.local-data', '__pycache__', '.venv', '.next', '.next-test', 'node_modules', '.pytest_cache') for part in path.parts):
            continue
        if path.suffix in ('.pyc', '.tsbuildinfo') or not (ROOT/path).is_file():
            continue
        result[path.as_posix()] = sha(ROOT/path)
    return result

def qa_sources():
    result = {name: sha(ROOT/name) for name in BASE['executableQaBefore']}
    for path in sorted(BATCH.rglob('*')):
        if path.is_file() and (path.suffix in ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.ps1') or path.name.endswith('tsconfig.json')):
            result[path.relative_to(ROOT).as_posix()] = sha(path)
    return result

def build_sources():
    directory = ROOT / 'apps/web/.next'
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(directory.rglob('*')) if path.is_file()
        and 'cache' not in path.relative_to(directory).parts and path.name not in ('trace', 'trace-build')}

def differences(old, new):
    return [name for name, digest in old.items() if new.get(name) != digest]

def additions(old, new):
    return [name for name in new if name not in old]

branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
assert (branch, head) == (BASE['branch'], BASE['head'])
protected_drift = [name for name, digest in BASE['historicalEvidence'].items() if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
source, qa, build = sources(), qa_sources(), build_sources()
contract_names = ['apps/api/app/contracts/teaching_loop.py', 'apps/api/app/contracts/scores.py', 'apps/api/app/contracts/b4.py',
    'apps/web/src/contracts/teaching-loop.ts', 'apps/web/src/contracts/b4.ts']
contracts = {name: sha(ROOT/name) for name in contract_names}
contracts['docs/qa/TEACHING-LOOP-G2-B5-20261003/G2-CONTRACT-v1.md'] = sha(BATCH/'G2-CONTRACT-v1.md')
old_contracts = json.loads((ROOT/'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r21.json').read_text(encoding='utf-8'))['sharedContractFiles']
assert not [name for name, digest in old_contracts.items() if sha(ROOT/name) != digest]
next_matches = (ROOT/'apps/web/next-env.d.ts').read_bytes() == (BATCH/'ctrl/next-env.original.bin').read_bytes()
manifest = json.loads((ROOT/'apps/web/.next/routes-manifest.json').read_text(encoding='utf-8'))
rewrites = manifest['rewrites']
entries = rewrites if isinstance(rewrites, list) else [entry for group in rewrites.values() for entry in group]
api = [entry for entry in entries if entry.get('source', '').startswith('/api/')]
assert api and all(entry['destination'].startswith('http://127.0.0.1:8001/') for entry in api)
build_id = (ROOT/'apps/web/.next/BUILD_ID').read_text().strip()
candidate_path = BATCH / ('CANDIDATE-' + version + '.json')
if mode == 'freeze':
    assert not candidate_path.exists() and not protected_drift and next_matches
    prior = {}
    active = set()
    for path in BATCH.rglob('*-command.json'):
        if json.loads(path.read_text(encoding='utf-8-sig')).get('status') == 'running':
            active.add((path.parent, path.name.removesuffix('-command.json')))
    for path in BATCH.rglob('*-service.json'):
        if json.loads(path.read_text(encoding='utf-8-sig')).get('status') != 'closed':
            active.add((path.parent, path.name.removesuffix('-service.json')))
    for directory in ('g2-be', 'g2-fe', 'ctrl', 'g2-v00'):
        for path in sorted((BATCH/directory).rglob('*')):
            if any(path.parent == folder and path.name.startswith(label) for folder, label in active):
                continue  # Open process receipts/logs are bound after actual closure.
            if path.is_file() and path.suffix not in ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.ps1'):
                prior[path.relative_to(ROOT).as_posix()] = sha(path)
    for path in sorted([*BATCH.glob('CANDIDATE-*.json'), *BATCH.glob('AUDIT-*.json')]):
        prior[path.relative_to(ROOT).as_posix()] = sha(path)
    value = dict(capturedAtUtc=datetime.now(timezone.utc).isoformat(), version=version, branch=branch, head=head,
        baselineSHA=sha(BASE_PATH), sourceFiles=source, sourceCount=len(source), executableQaFiles=qa, executableQaCount=len(qa),
        sharedContractFiles=contracts, buildFiles=build, buildCount=len(build), buildId=build_id, actualApiRewrites=api,
        historicalCount=len(BASE['historicalEvidence']), priorEvidence=prior, priorCount=len(prior),
        activeEvidenceExcluded=[str(folder.relative_to(ROOT)/label) for folder,label in sorted(active)],
        changedFromOpening=differences(BASE['sourceBefore'], source), addedFromOpening=additions(BASE['sourceBefore'], source),
        nextEnvSHA=sha(ROOT/'apps/web/next-env.d.ts'), elapsedMs=round((time.perf_counter()-started)*1000, 3))
    with candidate_path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(dict(version=version, SHA=sha(candidate_path), source=len(source), qa=len(qa), contracts=len(contracts), build=len(build), prior=len(prior), historical=len(BASE['historicalEvidence'])), ensure_ascii=False))
else:
    expected = json.loads(candidate_path.read_text(encoding='utf-8'))
    prior_drift = [name for name, digest in expected['priorEvidence'].items() if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
    value = dict(capturedAtUtc=datetime.now(timezone.utc).isoformat(), version=version, candidateSHA=sha(candidate_path),
        sourceDrift=differences(expected['sourceFiles'], source), sourceAdded=additions(expected['sourceFiles'], source),
        qaDrift=differences(expected['executableQaFiles'], qa), qaAdded=additions(expected['executableQaFiles'], qa),
        contractDrift=differences(expected['sharedContractFiles'], contracts), buildDrift=differences(expected['buildFiles'], build),
        buildAdded=additions(expected['buildFiles'], build), protectedDrift=protected_drift, priorDrift=prior_drift,
        baselineMatches=expected['baselineSHA'] == sha(BASE_PATH), nextEnvMatches=next_matches,
        buildIdentityMatches=build_id == expected['buildId'] and api == expected['actualApiRewrites'],
        sourceCount=len(source), qaCount=len(qa), buildCount=len(build), historicalCount=len(BASE['historicalEvidence']),
        elapsedMs=round((time.perf_counter()-started)*1000, 3))
    failed = any(value[key] for key in ('sourceDrift','sourceAdded','qaDrift','qaAdded','contractDrift','buildDrift','buildAdded','protectedDrift','priorDrift')) or not all(value[key] for key in ('baselineMatches','nextEnvMatches','buildIdentityMatches'))
    value['exitCode'] = int(failed)
    label = sys.argv[3]
    assert label.replace('-', '').isalnum()
    with (BATCH / ('AUDIT-' + version + '-' + label + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(value, ensure_ascii=False))
    raise SystemExit(int(failed))
