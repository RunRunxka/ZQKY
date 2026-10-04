"""Freeze and audit full candidate sources without importing the application."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd().resolve()
BATCH = ROOT / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    (BATCH / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def source_files():
    dirs = [p for p in ('apps', 'tests', 'scripts', 'infra', 'assets', '.github') if (ROOT / p).exists()]
    paths = subprocess.check_output(['rg', '--files', '--hidden', *dirs], cwd=ROOT).decode('utf-8').splitlines()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    paths += [p for p in tracked if p and (
        '/' not in p.replace('\\', '/') or p.split('/')[0] in dirs
    )]
    result = {}
    for raw in sorted(set(paths)):
        path = Path(raw)
        if any((part.startswith('.env') and part != '.env.example') or part in ('.local-data', '__pycache__', '.venv', '.next', 'node_modules', '.pytest_cache') for part in path.parts):
            continue
        if path.suffix in ('.pyc', '.tsbuildinfo') or not (ROOT / path).is_file():
            continue
        result[path.as_posix()] = sha(ROOT / path)
    return result

mode, version = sys.argv[1:3]
if mode == 'restore-next-env':
    original = (BATCH / 'next-env.original.bin').read_bytes()
    (ROOT / 'apps/web/next-env.d.ts').write_bytes(original)
    print(json.dumps({'restored': True, 'sha256': sha(ROOT / 'apps/web/next-env.d.ts')}))
elif mode == 'freeze':
    files = source_files()
    baseline = json.loads((BATCH / 'BASELINE.json').read_text(encoding='utf-8-sig'))['sourceFiles']
    payload = {'version': version, 'capturedAt': datetime.now(timezone.utc).isoformat(),
               'branch': subprocess.check_output(['git', 'branch', '--show-current']).decode().strip(),
               'head': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
               'coverage': 'apps/tests/scripts/infra/assets/.github plus tracked root files; includes source/tests/contracts/migrations/configuration/locks; excludes credentials, data, caches and generated builds',
               'files': files, 'count': len(files),
               'changedFromBaseline': [p for p, h in files.items() if p in baseline and baseline[p] != h],
               'newOrExtendedCoverage': [p for p in files if p not in baseline]}
    write(f'CANDIDATE-{version}.json', payload)
    print(json.dumps({k: v for k, v in payload.items() if k != 'files'}, ensure_ascii=False))
elif mode == 'audit':
    expected = json.loads((BATCH / f'CANDIDATE-{version}.json').read_text(encoding='utf-8-sig'))['files']
    actual = source_files()
    drift = [{'path': p, 'expected': h, 'actual': actual.get(p)} for p, h in expected.items() if actual.get(p) != h]
    added = [p for p in actual if p not in expected]
    protected = json.loads((BATCH / 'PROTECTED-EVIDENCE.json').read_text(encoding='utf-8-sig'))
    old_drift = [p for p, h in protected.items() if not (ROOT / p).is_file() or sha(ROOT / p) != h]
    result = {'version': version, 'candidateCount': len(expected), 'drift': drift, 'added': added,
              'protectedCount': len(protected), 'protectedDrift': old_drift,
              'nextEnvMatchesOriginal': (ROOT / 'apps/web/next-env.d.ts').read_bytes() == (BATCH / 'next-env.original.bin').read_bytes()}
    write(f'AUDIT-{version}.json', result)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(bool(drift or added or old_drift or not result['nextEnvMatchesOriginal']))
else:
    raise ValueError(mode)
