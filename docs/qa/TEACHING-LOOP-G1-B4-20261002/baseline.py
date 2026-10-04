"""Capture inherited source/evidence without importing app or opening business stores."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
batch = root / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'
batch.mkdir(parents=True, exist_ok=True)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, data):
    (batch / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

next_bytes = (root / 'apps/web/next-env.d.ts').read_bytes()
(batch / 'next-env.original.bin').write_bytes(next_bytes)
paths = subprocess.check_output(['rg', '--files', 'apps', 'tests', 'scripts'], cwd=root).decode('utf-8').splitlines()
paths += [p for p in git('ls-files', '-z').decode('utf-8').split('\0') if p and '/' not in p.replace('\\', '/')]
source = {}
for raw in sorted(set(paths)):
    path = Path(raw)
    relative = path.as_posix()
    if any(part.startswith('.env') or part in ('.local-data', '__pycache__', '.venv', '.next', 'node_modules') for part in path.parts):
        continue
    if (root / path).is_file():
        source[relative] = digest(root / path)
previous = json.loads((root / 'docs/qa/TEACHING-LOOP-B3-FIX-20261002/FROZEN-CANDIDATE-r7.json').read_text(encoding='utf-8-sig'))
previous_drift = [{'path': p, 'expected': h, 'actual': digest(root / p)} for p, h in previous['files'].items() if digest(root / p) != h]
protected = {}
for directory in ('TEACHING-LOOP-B2', 'TEACHING-LOOP-B2-REVIEW-20261001', 'TEACHING-LOOP-B3', 'TEACHING-LOOP-B3-REVIEW-20261001', 'TEACHING-LOOP-B3-FIX-20261002', 'TEACHING-LOOP-B3-FIX-REVIEW-20261002'):
    for path in sorted((root / 'docs/qa' / directory).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            protected[path.relative_to(root).as_posix()] = digest(path)
authority = {p.relative_to(root).as_posix(): digest(p) for p in (root / 'docs').rglob('*.md') if '/qa/' not in p.as_posix() and '/archive/' not in p.as_posix()}
save('BASELINE.json', {'capturedAt': datetime.now(timezone.utc).isoformat(), 'branch': git('branch', '--show-current').decode().strip(), 'head': git('rev-parse', 'HEAD').decode().strip(), 'statusPorcelain': git('-c', 'core.quotepath=false', 'status', '--short').decode('utf-8').splitlines(), 'sourceFiles': source, 'authorityDocuments': authority, 'nextEnvOriginalSha256': hashlib.sha256(next_bytes).hexdigest(), 'inheritedB3R7': {'count': len(previous['files']), 'drift': previous_drift}, 'protectedEvidenceFileCount': len(protected)})
save('PROTECTED-EVIDENCE.json', protected)
(batch / 'initial-git-status.txt').write_bytes(git('-c', 'core.quotepath=false', 'status', '--short'))
print(json.dumps({'branch': git('branch', '--show-current').decode().strip(), 'head': git('rev-parse', 'HEAD').decode().strip(), 'sourceCount': len(source), 'protectedCount': len(protected), 'inheritedB3R7Drift': previous_drift, 'nextEnvSha': hashlib.sha256(next_bytes).hexdigest()}, ensure_ascii=False))
