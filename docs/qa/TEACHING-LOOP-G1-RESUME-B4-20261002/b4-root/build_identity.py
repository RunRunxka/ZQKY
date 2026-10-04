"""Read-only production build binding; no frontend launch or credential access."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd().resolve()
batch=root/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
build=root/'apps/web/.next'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
label=sys.argv[1]
destination=batch/f'BUILD-IDENTITY-b4-{label}.json'
assert not destination.exists(), 'never replace build identity'
manifest=json.loads((build/'routes-manifest.json').read_text(encoding='utf-8'))
rewrites=manifest['rewrites']
entries=rewrites if isinstance(rewrites,list) else [r for group in rewrites.values() for r in group]
api=[r for r in entries if r.get('source','').startswith('/api/')]
assert api and all(r['destination'].startswith('http://127.0.0.1:8001/') for r in api), api
files={p.relative_to(root).as_posix():sha(p) for p in sorted(build.rglob('*')) if p.is_file()
    and 'cache' not in p.relative_to(build).parts and p.name not in ('trace','trace-build')}
value=dict(capturedAt=datetime.now(timezone.utc).isoformat(),label=label,buildId=(build/'BUILD_ID').read_text().strip(),
    files=files,fileCount=len(files),rewrites=api,nextEnvSHA256=sha(root/'apps/web/next-env.d.ts'),
    coverage='All built files except mutable cache/trace; API rewrite explicitly verified 8001.')
destination.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(buildId=value['buildId'],fileCount=len(files),identitySHA256=sha(destination),rewrites=api),ensure_ascii=False))
