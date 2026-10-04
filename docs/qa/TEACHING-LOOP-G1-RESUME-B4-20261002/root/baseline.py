"""Capture this continuation without importing application or opening business data."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd().resolve()
batch = root / 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
old_batch = root / 'docs/qa/TEACHING-LOOP-G1-B4-20261002'
manifest_path = old_batch / 'CANDIDATE-g1-r2.json'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, data):
    (batch / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
drift = [p for p, digest in manifest['files'].items() if not (root / p).is_file() or sha(root / p) != digest]
assert sha(manifest_path) == '9471f43eb5ba9cde9d79ab65b84f5cf1fcd607729b1ad2388d2bfde5c78a072b'
assert not drift, drift
branch = subprocess.check_output(['git', 'branch', '--show-current']).decode().strip()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
status = subprocess.check_output(['git', 'status', '--porcelain=v1']).decode('utf-8')
(batch / 'initial-git-status.txt').write_text(status, encoding='utf-8')
next_bytes = (root / 'apps/web/next-env.d.ts').read_bytes()
assert hashlib.sha256(next_bytes).hexdigest() == '0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc'
(batch / 'next-env.original.bin').write_bytes(next_bytes)
protected = {}
for name in ('TEACHING-LOOP-B3-FIX-20261002', 'TEACHING-LOOP-B3-FIX-REVIEW-20261002', 'TEACHING-LOOP-G1-B4-20261002', 'TEACHING-LOOP-G1-REVIEW-20261002'):
    for path in sorted((root / 'docs/qa' / name).rglob('*')):
        if path.is_file():
            protected[path.relative_to(root).as_posix()] = sha(path)
write('PROTECTED-EVIDENCE.json', protected)
build_root = root / 'apps/web/.next'
build_files = {}
for path in sorted(build_root.rglob('*')):
    if path.is_file() and not any(part in ('cache', 'trace') for part in path.relative_to(build_root).parts):
        build_files[path.relative_to(root).as_posix()] = sha(path)
routes = json.loads((build_root / 'routes-manifest.json').read_text(encoding='utf-8'))
rewrites = routes['rewrites']
assert any(entry['destination'] == 'http://127.0.0.1:8001/api/v1/:path*' for entries in rewrites.values() for entry in entries)
write('BUILD-IDENTITY.json', {'buildId': (build_root / 'BUILD_ID').read_text().strip(), 'rewrites': rewrites, 'files': build_files, 'count': len(build_files)})
current_docs = {}
for path in sorted((root / 'docs').rglob('*.md')):
    relative = path.relative_to(root)
    if 'qa' not in relative.parts and 'archive' not in relative.parts:
        current_docs[relative.as_posix()] = sha(path)
write('BASELINE.json', {'capturedAt': datetime.now(timezone.utc).isoformat(), 'branch': branch, 'head': head,
    'sourceFiles': manifest['files'], 'sourceCount': len(manifest['files']), 'sourceDrift': drift,
    'inheritedCandidate': manifest_path.relative_to(root).as_posix(), 'inheritedManifestSHA256': sha(manifest_path),
    'protectedEvidenceCount': len(protected), 'nextEnvSHA256': hashlib.sha256(next_bytes).hexdigest(),
    'authorityDocumentFiles': current_docs, 'buildId': (build_root / 'BUILD_ID').read_text().strip(),
    'newUserDocuments': ['docs/design/teaching-loop-v1/G1续验与B4启动提示词_20261002.md', 'docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/'],
    'B4': 'not_started', 'frontendReadyReportedByUser': False})
print(json.dumps({'branch': branch, 'head': head, 'sourceCount': len(manifest['files']), 'drift': drift, 'protectedEvidenceCount': len(protected), 'buildFileCount': len(build_files), 'buildId': (build_root / 'BUILD_ID').read_text().strip()}, ensure_ascii=False))
