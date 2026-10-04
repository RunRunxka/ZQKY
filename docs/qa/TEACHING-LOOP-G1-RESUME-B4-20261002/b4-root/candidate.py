"""B4 stable source/QA inventory with immutable G1 evidence protection."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root = Path.cwd().resolve()
batch = root/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
baseline = json.loads((batch/'b4-root/BASELINE.json').read_text(encoding='utf-8'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()

def sources():
    directories = [p for p in ('apps','tests','scripts','infra','assets','.github') if (root/p).exists()]
    paths = subprocess.check_output(['rg','--files','--hidden',*directories]).decode('utf-8').splitlines()
    tracked = subprocess.check_output(['git','ls-files','-z']).decode('utf-8').split('\0')
    paths += [p for p in tracked if p and ('/' not in p.replace('\\','/') or p.split('/')[0] in directories)]
    result = {}
    for raw in sorted(set(paths)):
        p = Path(raw)
        if any((part.startswith('.env') and part != '.env.example') or part in
               ('.local-data','__pycache__','.venv','.next','.next-test','node_modules','.pytest_cache') for part in p.parts):
            continue
        if p.suffix in ('.pyc','.tsbuildinfo') or not (root/p).is_file():
            continue
        result[p.as_posix()] = sha(root/p)
    return result

def qa_sources(scope='all'):
    paths = [p for p in batch.rglob('*') if p.is_file() and (p.suffix in ('.py','.ts','.tsx','.js','.mjs','.cjs','.ps1') or p.name=='tsconfig.json')
             and any(part.startswith('b4-') for part in p.relative_to(batch).parts)]
    if scope != 'all':
        paths = [p for p in paths if not any(part.startswith('b4-v00-') and part != scope
                    for part in p.relative_to(batch).parts)]
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(paths)}

mode, version = sys.argv[1:3]
scope = sys.argv[3] if len(sys.argv)>3 else 'all'
if mode=='audit':
    scope=json.loads((batch/f'CANDIDATE-{version}.json').read_text(encoding='utf-8')).get('qaScope','all')
source, qa = sources(), qa_sources(scope)
branch = subprocess.check_output(['git','branch','--show-current']).decode().strip()
head = subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()
assert (branch,head)==(baseline['branch'],baseline['head'])
protected = {p:d for p,d in baseline['protectedEvidence'].items()
             if not (root/p).is_file() or sha(root/p)!=d}
assert not protected, protected
path = batch/f'CANDIDATE-{version}.json'
if mode=='freeze':
    assert not path.exists(), 'never replace an earlier candidate'
    value = dict(capturedAt=datetime.now(timezone.utc).isoformat(),version=version,branch=branch,head=head,
        baselineSHA256=sha(batch/'b4-root/BASELINE.json'), files=source,count=len(source),
        executableQaFiles=qa,executableQaCount=len(qa),qaScope=scope,
        changedFromG1=[p for p,d in baseline['sourceFiles'].items() if source.get(p)!=d],
        newSourceFiles=[p for p in source if p not in baseline['sourceFiles']],
        sharedContractFiles={p.relative_to(root).as_posix():sha(p) for p in sorted(batch.glob('B4-CONTRACT*.md'))},
        protectedEvidenceCount=len(baseline['protectedEvidence']),nextEnvSHA256=sha(root/'apps/web/next-env.d.ts'))
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(version=version,sha256=sha(path),sourceCount=len(source),qaCount=len(qa)),ensure_ascii=False))
elif mode=='audit':
    expected=json.loads(path.read_text(encoding='utf-8'))
    value=dict(version=version,candidateSHA256=sha(path),sourceDrift=[p for p,d in expected['files'].items() if source.get(p)!=d],
        sourceAdded=[p for p in source if p not in expected['files']],qaDrift=[p for p,d in expected['executableQaFiles'].items() if qa.get(p)!=d],
        qaAdded=[p for p in qa if p not in expected['executableQaFiles']],protectedDrift=protected,
        sharedContractDrift=[p for p,d in expected['sharedContractFiles'].items() if not (root/p).is_file() or sha(root/p)!=d],
        nextEnvMatchesOriginal=(root/'apps/web/next-env.d.ts').read_bytes()==(batch/'b4-root/next-env.original.bin').read_bytes())
    print(json.dumps(value,ensure_ascii=False))
    sys.exit(bool(value['sourceDrift'] or value['sourceAdded'] or value['qaDrift'] or value['qaAdded'] or value['sharedContractDrift'] or protected or not value['nextEnvMatchesOriginal']))
else:
    raise ValueError(mode)
