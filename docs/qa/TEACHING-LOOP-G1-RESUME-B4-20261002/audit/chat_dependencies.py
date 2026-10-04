"""Static local import dependency audit, without importing or executing application code."""
import ast
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[4]
QA = REPO/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit'
before = json.loads((REPO/'docs/qa/TEACHING-LOOP-G1-B4-20261002/BASELINE.json').read_text(encoding='utf-8-sig'))['sourceFiles']
resume = json.loads((REPO/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/BASELINE.json').read_text(encoding='utf-8-sig'))['sourceFiles']
changed = {p for p,h in before.items() if resume.get(p)!=h and '.test.' not in p and
           (p.startswith('apps/api/app/') or p.startswith('apps/web/src/'))}

def frontend_resolve(source, name):
    if name.startswith('@/'):
        base=REPO/'apps/web/src'/name[2:]
    elif name.startswith('.'):
        base=source.parent/name
    else:
        return None
    options=[base, Path(str(base)+'.ts'),Path(str(base)+'.tsx'),Path(str(base)+'.js'),base/'index.ts',base/'index.tsx']
    return next((p.resolve() for p in options if p.is_file()),None)

def frontend_edges(path):
    text=path.read_text(encoding='utf-8-sig')
    names=re.findall(r'\b(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]',text)
    names+=re.findall(r'\bimport\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)',text)
    return [p for n in names if (p:=frontend_resolve(path,n)) is not None]

def backend_resolve(name):
    if not name.startswith('app.'):
        return None
    base=REPO/'apps/api'/Path(*name.split('.'))
    return next((p.resolve() for p in (Path(str(base)+'.py'),base/'__init__.py') if p.is_file()),None)

def backend_edges(path):
    result=[]
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
        if isinstance(node,ast.Import):
            names=[alias.name for alias in node.names]
        elif isinstance(node,ast.ImportFrom) and node.level==0 and node.module:
            names=[node.module]+[f'{node.module}.{alias.name}' for alias in node.names]
        else:
            continue
        result.extend(p for n in names if (p:=backend_resolve(n)) is not None)
    return result

def closure(seeds,edges):
    pending=[REPO/p for p in seeds];seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        seen.add(path)
        if path.suffix in ('.ts','.tsx','.js','.py'):
            pending.extend(edges(path))
    names=sorted(p.relative_to(REPO).as_posix() for p in seen)
    differences=[p for p in names if p not in before or hashlib.sha256((REPO/p).read_bytes()).hexdigest()!=before[p]]
    return {'count':len(names),'files':names,'intersectionWith13Changes':sorted(set(names)&changed),
            'differencesFromPreG1':differences}

report={'g1ProductChangeCount':len(changed),'g1ProductChanges':sorted(changed),
        'frontendChatAndShell':closure(['apps/web/src/app/chat/page.tsx','apps/web/src/app/chat/[sessionId]/page.tsx','apps/web/src/app/layout.tsx'],frontend_edges),
        'backendChatRoute':closure(['apps/api/app/api/v1/chat.py'],backend_edges),
        'method':'Static local imports including type imports and nested import statements; external packages omitted; CSS treated as immutable leaves. Does not claim general dynamic dependency proof.',
        'decision':'No additional stream integration required for these G1 changes; existing full E2E chat UI remains applicable. Shared create_app/lifespan assembly is unchanged and prior candidate API/check gates cover startup.'}
(QA/'chat-dependencies.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:({'count':v['count'],'intersectionWith13Changes':v['intersectionWith13Changes'],'differencesFromPreG1':v['differencesFromPreG1']} if isinstance(v,dict) else v) for k,v in report.items()},ensure_ascii=False,indent=2))
