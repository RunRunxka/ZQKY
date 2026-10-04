"""Exact same-source reuse; no application import, HTTP or claim of a fresh run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'ctrl/B6-MATERIALS-SAME-SOURCE-v1.json'
assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
oldp=B/'CANDIDATE-G3-r2-qa5.json'
newp=B/'CANDIDATE-B6-R01-r2-built.json'
old=json.loads(oldp.read_bytes()); new=json.loads(newp.read_bytes())
changed=[n for n,h in old['sourceFiles'].items() if new['sourceFiles'].get(n)!=h]
assert changed==['apps/web/src/features/lesson-plan/components/SourcePanel.tsx',
 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'],changed
assert all(sha(R/n)==h for n,h in new['sourceFiles'].items())
binding=json.loads((B/'ctrl/G3-API-UNCHANGED-BINDING-v1.json').read_bytes())
backend=binding['backendFiles']
assert len(backend)==410 and all(new['sourceFiles'].get(n)==h==sha(R/n) for n,h in backend.items())
export_prefix='apps/web/src/features/lesson-plan/'
export_sources={n:h for n,h in old['sourceFiles'].items()
 if (n.startswith(export_prefix) and n!='apps/web/src/features/lesson-plan/components/SourcePanel.tsx' and '.test.' not in n)
 or n.startswith('apps/web/src/styles/') or n.startswith('assets/templates/')
 or n.startswith('apps/web/public/templates/') or n.startswith('scripts/template')
 or n=='教师备课教案模板.docx'}
assert export_sources and all(sha(R/n)==h==new['sourceFiles'].get(n) for n,h in export_sources.items())
chat_shell={n:h for n,h in old['sourceFiles'].items() if n.startswith((
 'apps/web/src/features/chat/','apps/web/src/components/layout/')) or n in (
 'apps/web/src/services/navigation-guard.tsx','apps/web/src/services/navigation-guard.ts')}
assert chat_shell and all(sha(R/n)==h==new['sourceFiles'].get(n) for n,h in chat_shell.items())
receipts=['b6-integration/endpoint-r4/COMMAND.json','b6-integration/endpoint-r4/probe/RESULT.json',
 'b6-quality/offline-third-command.json','b6-quality/runs/offline-third/SUMMARY.json',
 'b6-quality/RESULT-v1.md','b6-quality/RESULT-CORRIGENDUM-v1.md','b6-exports/browser-r3-command.json',
 'b6-exports/offline-r1-command.json','b6-exports/RESULT-v1.md',
 'B6-RECOVERY-REFERENCE-v2.md','ctrl/B6-RECOVERY-EXACT-REFERENCE-v2.json']
assert all((B/n).exists() for n in receipts)
record=dict(at=datetime.now(timezone.utc).isoformat(),oldProduct=oldp.relative_to(R).as_posix(),
 oldProductSHA=sha(oldp),newProduct=newp.relative_to(R).as_posix(),newProductSHA=sha(newp),
 currentSourceCount=len(new['sourceFiles']),declaredChangedOldSource=changed,
 declaredAddedTest=new['addedTestsFromG3'],backend410=backend,
 unchangedLessonExportAndStyles=export_sources,
 unchangedChatAndSharedShell=chat_shell,
 sourceImpact='Only SourcePanel product read ownership plus original local dialog test synchronization; backend/provider/DDL/recovery/exporter/templates/styles/chat/shared shell unchanged',
 chat14='not_run this batch: no chat/shared shell impact; exact historical same-source reference, full153 basic chat is separate',
 references={n:sha(B/n) for n in receipts},
 endpointAnd15Cases='B6 new actual prior run on identical backend; not rerun after frontend metadata fix',
 exports='Four new actual q84e exports; same-source reuse after new build, not fresh new-build exports',
 originalRecovery='Exact prior source/retained sample binding v2; not this batch new restore',
 modelQuality='live_run awaiting inputs; teacher_review_pending; RAG-REL OPEN',
 WordWPS='not_run',networkRequests=0,mainImported=False,gitWrites=False)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=out.relative_to(R).as_posix(),SHA=sha(out),backendCount=len(backend),
 exportSourceCount=len(export_sources),changed=changed),ensure_ascii=False))
