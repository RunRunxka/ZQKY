"""Daily candidate/source/build audit; no application import or service lifecycle."""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[4]
batch = Path(__file__).resolve().parent.parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
baseline_path = batch / 'b4-root/BASELINE.json'
baseline_sha = sha(baseline_path)
assert baseline_sha == '5a8f4e507032767173d019f1a357a68331f0e6a03aaceccccd7c80d976ca7abf', 'Daily baseline identity changed'
baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
original_next_env = batch / 'b4-root/next-env.original.bin'
assert sha(original_next_env) == '0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc', 'Original next-env identity changed'
tick = time.perf_counter()
mode, version = sys.argv[1:3]
assert mode in ('freeze', 'audit')
assert version.replace('-', '').isalnum()

def sources():
    directories = [p for p in ('apps', 'tests', 'scripts', 'infra', 'assets', '.github') if (root / p).exists()]
    paths = subprocess.check_output(['rg', '--files', '--hidden', *directories], cwd=root).decode('utf-8').splitlines()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    paths += [p for p in tracked if p and ('/' not in p.replace('\\', '/') or p.split('/')[0] in directories)]
    value = {}
    for name in sorted(set(paths)):
        p = Path(name)
        if any((x.startswith('.env') and x != '.env.example') or x in
               ('.local-data', '__pycache__', '.venv', '.next', '.next-test', 'node_modules', '.pytest_cache') for x in p.parts):
            continue
        if p.suffix in ('.pyc', '.tsbuildinfo') or not (root / p).is_file():
            continue
        value[p.as_posix()] = sha(root / p)
    return value

def qa_sources():
    value = {p: sha(root / p) for p in baseline['oldExecutableQaBefore']}
    for p in sorted(batch.rglob('*')):
        if p.is_file() and (p.suffix in ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.ps1') or p.name == 'tsconfig.json'):
            value[p.relative_to(root).as_posix()] = sha(p)
    return value

def build_sources():
    build = root / 'apps/web/.next'
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(build.rglob('*')) if p.is_file()
            and 'cache' not in p.relative_to(build).parts and p.name not in ('trace', 'trace-build')}

branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=root).decode().strip()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()
assert (branch, head) == (baseline['branch'], baseline['head'])
protected = [p for p, d in baseline['protectedEvidence'].items() if not (root / p).is_file() or sha(root / p) != d]
source, qa, build = sources(), qa_sources(), build_sources()
contracts = {p: sha(root / p) for p in baseline['oldContractsBefore']}
next_env_matches = (root / 'apps/web/next-env.d.ts').read_bytes() == original_next_env.read_bytes()
manifest = json.loads((root / 'apps/web/.next/routes-manifest.json').read_text(encoding='utf-8'))
rewrites = manifest['rewrites']
entries = rewrites if isinstance(rewrites, list) else [r for group in rewrites.values() for r in group]
api = [r for r in entries if r.get('source', '').startswith('/api/')]
assert api and all(r['destination'].startswith('http://127.0.0.1:8001/') for r in api)
build_id = (root / 'apps/web/.next/BUILD_ID').read_text().strip()
path = batch / f'CANDIDATE-{version}.json'
if mode == 'freeze':
    assert not path.exists(), 'Never replace an earlier candidate'
    assert not protected and next_env_matches
    value = dict(capturedAt=datetime.now(timezone.utc).isoformat(), version=version, branch=branch, head=head,
                 baselineSHA256=sha(batch / 'b4-root/BASELINE.json'), files=source, count=len(source),
                 executableQaFiles=qa, executableQaCount=len(qa), sharedContractFiles=contracts,
                 protectedEvidenceCount=len(baseline['protectedEvidence']), buildFiles=build,
                 buildFileCount=len(build), buildId=build_id, actualApiRewrites=api,
                 nextEnvSHA256=sha(root / 'apps/web/next-env.d.ts'),
                 changedFromR17=[p for p, d in baseline['daySourceBefore'].items() if source.get(p) != d],
                 sourceAddedFromR17=[p for p in source if p not in baseline['daySourceBefore']],
                 businessBinding='QA and module-guide-only candidate; runtime/common-source identity separately audited')
    prior_paths = list(batch.glob('CANDIDATE-*.json')) + list(batch.glob('AUDIT-*.json'))
    prior_paths += list(batch.rglob('*.txt'))
    # Freeze completed first-run receipts and artifacts before the next candidate.
    prior_paths += [p for p in (batch / 'b4-root').iterdir() if p.is_file() and
                    p.suffix not in ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.ps1')]
    for directory in sorted(batch.glob('b4-v00-*')):
        if directory.is_dir():
            prior_paths += [p for p in directory.rglob('*') if p.is_file() and
                            p.suffix not in ('.py', '.ts', '.tsx', '.js', '.mjs', '.cjs', '.ps1')]
    for directory in sorted(batch.iterdir()):
        if directory.is_dir() and (directory.name.startswith('r14-') or
                                   directory.name.startswith('b4-chat-') or
                                   directory.name.startswith('b4-e2e-')):
            prior_paths += [p for p in directory.rglob('*') if p.is_file()]
    value['priorDailyEvidenceFiles'] = {p.relative_to(root).as_posix(): sha(p) for p in sorted(set(prior_paths))}
    value['priorDailyEvidenceCount'] = len(value['priorDailyEvidenceFiles'])
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(version=version, candidateSHA256=sha(path), sourceCount=len(source), qaCount=len(qa),
                         contractCount=len(contracts), buildCount=len(build), protectedCount=value['protectedEvidenceCount'], priorDailyCount=value['priorDailyEvidenceCount']), ensure_ascii=False))
else:
    expected = json.loads(path.read_text(encoding='utf-8'))
    baseline_identity_matches = expected['baselineSHA256'] == baseline_sha
    protected_count_matches = expected['protectedEvidenceCount'] == len(baseline['protectedEvidence'])
    next_env_sha_matches = expected['nextEnvSHA256'] == sha(root / 'apps/web/next-env.d.ts') == sha(original_next_env)
    prior_daily = expected.get('priorDailyEvidenceFiles', {})
    prior_daily_drift = [p for p, digest in prior_daily.items() if not (root / p).is_file() or sha(root / p) != digest]
    drift = lambda old, now: [p for p, d in old.items() if now.get(p) != d]
    added = lambda old, now: [p for p in now if p not in old]
    value = dict(capturedAt=datetime.now(timezone.utc).isoformat(), version=version, candidateSHA256=sha(path),
                 branch=branch, head=head, sourceCount=len(source), qaCount=len(qa), contractCount=len(contracts),
                 buildCount=len(build), protectedCount=len(baseline['protectedEvidence']),
                 sourceDrift=drift(expected['files'], source), sourceAdded=added(expected['files'], source),
                 qaDrift=drift(expected['executableQaFiles'], qa), qaAdded=added(expected['executableQaFiles'], qa),
                 sharedContractDrift=drift(expected['sharedContractFiles'], contracts),
                 buildDrift=drift(expected['buildFiles'], build), buildAdded=added(expected['buildFiles'], build),
                 protectedDrift=protected, nextEnvMatchesOriginal=next_env_matches,
                 baselineIdentityMatches=baseline_identity_matches, protectedCountMatches=protected_count_matches,
                 nextEnvFrozenSHAMatches=next_env_sha_matches, priorDailyEvidenceCount=len(prior_daily),
                 priorDailyEvidenceDrift=prior_daily_drift,
                 buildIdentityMatches=(build_id == expected['buildId'] and api == expected['actualApiRewrites']),
                 elapsedMs=round((time.perf_counter() - tick) * 1000, 3))
    failed = any(value[k] for k in ('sourceDrift', 'sourceAdded', 'qaDrift', 'qaAdded', 'sharedContractDrift',
                                  'buildDrift', 'buildAdded', 'protectedDrift', 'priorDailyEvidenceDrift')) or not all((
                                      next_env_matches, value['buildIdentityMatches'], baseline_identity_matches,
                                      protected_count_matches, next_env_sha_matches))
    value['exit'] = int(failed)
    if len(sys.argv) > 3:
        label = sys.argv[3]
        assert label.replace('-', '').isalnum()
        target = batch / f'AUDIT-{version}-{label}.json'
        assert not target.exists(), 'Never replace an earlier audit'
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False))
    sys.exit(int(failed))
