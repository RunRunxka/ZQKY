"""Read finalized actual trace; preserve the failed UI sequence without rerunning."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
run = HERE / 'browser-r8'
out = HERE / 'r8-classification'
out.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
trace = next((run / 'artifacts').rglob('trace.zip'))
with zipfile.ZipFile(trace) as archive:
    rows = [json.loads(line) for name in archive.namelist() if name.endswith('.network')
        for line in archive.read(name).decode('utf-8').splitlines() if line]
    events = [json.loads(line) for name in archive.namelist() if name.endswith('.trace')
        for line in archive.read(name).decode('utf-8').splitlines() if line]
calls = []
for row in rows:
    value = row.get('snapshot', {})
    request, response = value.get('request', {}), value.get('response', {})
    if '/api/v1/' in request.get('url', ''):
        calls.append(dict(method=request.get('method'), url=request.get('url'), status=response.get('status'),
            startedAt=value.get('startedDateTime')))
source = [item for item in calls if '/source?' in item['url'] or 'evidence/verify' in item['url'] or 'confirmed-revisions' in item['url'] or '/proposals' in item['url']]
selectors = [dict(method=e.get('method'), params=e.get('params')) for e in events
    if e.get('type') == 'before' and any(word in str(e.get('params')) for word in ['核验教材', '固定题', '生成 AI'])]
generate = [item for item in calls if item['method'] == 'POST' and item['url'].endswith('/proposals')]
evidence = [item for item in calls if item['url'].endswith('/lesson-plans/evidence/verify')]
original_spec = run / 'qa-source/five-fields.spec.ts'
(out / 'five-fields.original.bin').write_bytes(original_spec.read_bytes())
record = dict(status='FAILED_UI_SEQUENCE_AWAIT_CLASSIFICATION_NOT_ACCEPTANCE',
    commandSHA=sha(run / 'COMMAND.json'), originalSpecSHA=sha(original_spec), traceSHA=sha(trace),
    exactBusinessCalls=source, relevantActions=selectors, generatePostCount=len(generate), evidenceVerifyCalls=evidence,
    providerCallsByThisUI=0 if not generate else None,
    providerAttribution='No POST proposal in actual business trace; no provider generation initiated by this UI. This is not a global wire count.',
    expectationNotWeakened=True, productWritten=False, qaWrittenDuringRun=False)
(out / 'CLASSIFICATION-v1.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(calls=source, generatePostCount=len(generate), evidenceVerifyCalls=evidence), ensure_ascii=False))
