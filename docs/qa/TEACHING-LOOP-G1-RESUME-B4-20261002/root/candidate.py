"""Freeze product sources plus this run's executable browser/config/fixture sources."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
batch = root / 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
baseline = json.loads((batch / 'BASELINE.json').read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_files():
    directories = [name for name in ('apps', 'tests', 'scripts', 'infra', 'assets', '.github') if (root / name).exists()]
    paths = subprocess.check_output(['rg', '--files', '--hidden', *directories]).decode('utf-8').splitlines()
    tracked = subprocess.check_output(['git', 'ls-files', '-z']).decode('utf-8').split('\0')
    paths += [p for p in tracked if p and ('/' not in p.replace('\\', '/') or p.split('/')[0] in directories)]
    result = {}
    for raw in sorted(set(paths)):
        path = Path(raw)
        if any((part.startswith('.env') and part != '.env.example') or part in ('.local-data', '__pycache__', '.venv', '.next', 'node_modules', '.pytest_cache') for part in path.parts):
            continue
        if path.suffix in ('.pyc', '.tsbuildinfo') or not (root / path).is_file():
            continue
        result[path.as_posix()] = sha(root / path)
    return result

def executable_qa_files():
    files = [batch / 'e2e.external.config.ts']
    for name in ('v00-browser', 'adapt-e2e', 'audit'):
        files.extend(path for path in (batch / name).rglob('*') if path.is_file() and path.suffix in ('.ts', '.py', '.mjs', '.cjs'))
    return {path.relative_to(root).as_posix(): sha(path) for path in sorted(files)}

def write(name, value):
    (batch / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

mode, version = sys.argv[1:3]
current = source_files()
current_qa = executable_qa_files()
if mode == 'freeze':
    changed = [p for p, digest in baseline['sourceFiles'].items() if current.get(p) != digest]
    payload = {
        'capturedAt': datetime.now(timezone.utc).isoformat(), 'version': version,
        'branch': subprocess.check_output(['git', 'branch', '--show-current']).decode().strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
        'inheritedCandidate': baseline['inheritedCandidate'], 'inheritedManifestSHA256': baseline['inheritedManifestSHA256'],
        'files': current, 'count': len(current), 'changedFromInheritedCandidate': changed,
        'newSourceFiles': [p for p in current if p not in baseline['sourceFiles']],
        'executableQaFiles': current_qa, 'executableQaCount': len(current_qa),
        'coverage': 'Full product/test/contracts/migrations/config/locks inventory; plus executable continuation browser fixtures/config/resource probes. Receipt writer scripts and output logs are evidence, not behavior sources.',
    }
    write(f'CANDIDATE-{version}.json', payload)
    print(json.dumps({key: payload[key] for key in ('version', 'count', 'changedFromInheritedCandidate', 'newSourceFiles', 'executableQaCount')}, ensure_ascii=False))
elif mode == 'audit':
    expected = json.loads((batch / f'CANDIDATE-{version}.json').read_text(encoding='utf-8-sig'))
    protected = json.loads((batch / 'PROTECTED-EVIDENCE.json').read_text(encoding='utf-8-sig'))
    product_drift = [p for p, digest in expected['files'].items() if current.get(p) != digest]
    added = [p for p in current if p not in expected['files']]
    qa_drift = [p for p, digest in expected['executableQaFiles'].items() if current_qa.get(p) != digest]
    qa_added = [p for p in current_qa if p not in expected['executableQaFiles']]
    protected_drift = [p for p, digest in protected.items() if not (root / p).is_file() or sha(root / p) != digest]
    result = {'version': version, 'count': len(expected['files']), 'productDrift': product_drift, 'added': added,
        'executableQaCount': len(expected['executableQaFiles']), 'qaDrift': qa_drift, 'qaAdded': qa_added,
        'protectedEvidenceCount': len(protected), 'protectedDrift': protected_drift,
        'nextEnvMatchesOriginal': (root / 'apps/web/next-env.d.ts').read_bytes() == (batch / 'next-env.original.bin').read_bytes()}
    write(f'AUDIT-{version}.json', result)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(bool(product_drift or added or qa_drift or qa_added or protected_drift or not result['nextEnvMatchesOriginal']))
else:
    raise ValueError(mode)
