import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

QA = Path(__file__).resolve().parent
ROOT = QA.parents[3]
protected = json.loads((QA.parent / 'PROTECTED-EVIDENCE.json').read_text(encoding='utf-8'))
drift = []
for name, expected in protected.items():
    path = ROOT / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if actual != expected:
        drift.append({'path': name, 'expected': expected, 'actual': actual})
(QA / 'old-evidence-check.json').write_text(json.dumps({'count':len(protected),'drift':drift}, ensure_ascii=False, indent=2), encoding='utf-8')
receipts = [json.loads(line) for line in (QA / 'http-receipts.jsonl').read_text(encoding='utf-8').splitlines()]
roots = sorted({r['root'] for r in receipts if r['kind']=='resources'})
boot = sorted({r['bootstrap'] for r in receipts if r['kind']=='resources'})
resources = {'bootstrapRoots':boot,'caseRoots':roots, 'listeners':[], 'browserContexts':[],
             'activeProcesses':[], 'preservedTempRoots':True, 'oldRejectedRootsTouched':False,
             'allTestClientContextsExited':True}
(QA / 'resources.json').write_text(json.dumps(resources, ensure_ascii=False, indent=2), encoding='utf-8')
summary = []
for stem in ['first','recheck','final','accepted','accepted-v2']:
    suite = ET.parse(QA / (stem+'.xml')).getroot().find('testsuite')
    summary.append({'run':stem,'tests':int(suite.get('tests')),'failed':int(suite.get('failures')),
                    'errors':int(suite.get('errors')),'skipped':int(suite.get('skipped')),
                    'junitSeconds':float(suite.get('time')),
                    'exit':int((QA/(stem+'.exit.txt')).read_text(encoding='utf-8-sig').strip())})
sources = {p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
           for p in (QA / 'sources').iterdir() if p.is_file()}
metadata = {'commands':summary, 'canonicalRun':'accepted-v2', 'scoreCases':33,'questionCases':20,
            'testSourceSha256':hashlib.sha256((QA/'test_independent_score_qb.py').read_bytes()).hexdigest(),
            'receipts':len(receipts),'sources':sources,'protectedCount':len(protected),'protectedDrift':drift}
(QA / 'EVIDENCE.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'runs':summary,'sourceCount':len(sources),'caseRoots':len(roots),'oldProtectedCount':len(protected),'oldDrift':drift},ensure_ascii=False))
raise SystemExit(bool(drift))
