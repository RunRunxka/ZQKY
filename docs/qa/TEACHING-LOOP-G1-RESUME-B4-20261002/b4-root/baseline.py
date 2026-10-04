"""Read-only B4 baseline; never imports app or reads credentials/business data."""
import hashlib
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

root = Path.cwd().resolve()
batch = root / 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
out = batch / 'b4-root'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
candidate = json.loads((batch / 'CANDIDATE-g1-resume-r5.json').read_text(encoding='utf-8'))
assert all(sha(root / p) == d for p, d in candidate['files'].items())
assert all(sha(root / p) == d for p, d in candidate['executableQaFiles'].items())
protected = json.loads((batch / 'PROTECTED-EVIDENCE.json').read_text(encoding='utf-8'))
assert all(sha(root / p) == d for p, d in protected.items())
for path in batch.rglob('*'):
    if path.is_file() and not any(part.startswith('b4-') for part in path.relative_to(batch).parts):
        protected[path.relative_to(root).as_posix()] = sha(path)
next_bytes = (root / 'apps/web/next-env.d.ts').read_bytes()
assert hashlib.sha256(next_bytes).hexdigest() == '0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc'
(out / 'next-env.original.bin').write_bytes(next_bytes)
(out / 'initial-git-status.txt').write_bytes(subprocess.check_output(['git', 'status', '--porcelain=v1']))
payload = dict(capturedAt=datetime.now(timezone.utc).isoformat(),
    branch=subprocess.check_output(['git', 'branch', '--show-current']).decode().strip(),
    head=subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
    sourceFiles=candidate['files'], executableG1Files=candidate['executableQaFiles'],
    protectedEvidence=protected, nextEnvSHA256=hashlib.sha256(next_bytes).hexdigest(),
    inheritedManifestSHA256=sha(batch / 'CANDIDATE-g1-resume-r5.json'),
    buildIdentity=json.loads((batch / 'BUILD-IDENTITY.json').read_text(encoding='utf-8')),
    g1='closed', b4='contract_preparation')
(out / 'BASELINE.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(branch=payload['branch'], head=payload['head'], sources=len(candidate['files']), protected=len(protected), g1='closed'), ensure_ascii=False))
