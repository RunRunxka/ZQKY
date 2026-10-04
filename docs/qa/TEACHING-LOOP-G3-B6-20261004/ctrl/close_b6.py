"""ROOT limited closure only after complete gates, independent materials and resources."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

R=Path(__file__).resolve().parents[4];B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'B6-CLOSE-v1.json';assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=B/'CANDIDATE-B6-r1.json';c=json.loads(cp.read_bytes())
assert all(sha(R/n)==h for key in ('sourceFiles','executableQaFiles','sharedContractFiles','buildFiles','frozenB6ArtifactFiles') for n,h in c[key].items())
full=json.loads((B/'e2e-b6-r01-r2-built-node24-first/results.json').read_bytes())
browser=json.loads((B/'v00/results/run-b6-r01-r2-built-node24/browser-results.json').read_bytes())
ui=json.loads((B/'b6-integration/browser-r9/browser-results.json').read_bytes())
for count,result in [(153,full),(14,browser),(1,ui)]:
 assert result['stats']['expected']==count and result['stats']['skipped']==0 and result['stats']['unexpected']==0 and result['stats']['flaky']==0 and not result['errors']
labels=['b6-check-r01-r2-qa3-first','b6-g3-boundary-eight-built','b6-g3-v00-fifteen-built',
        'b6-source-independent-built-r2','b6-g3-browser-r01-r2-first','b6-e2e-full-r01-r2-first']
commands={}
for label in labels:
 p=B/'ctrl'/(label+'-command.json');r=json.loads(p.read_bytes())
 assert r['exitCode']==0 and not r['changedSources'] and not r['changedQA'] and r['childClosed'] and r['logsClosed']
 assert all(r['sourceBefore'].get(n)==h==r['sourceAfter'].get(n) for n,h in c['sourceFiles'].items())
 commands[label]=dict(pid=r['pid'],elapsedMs=r['elapsedMs'],SHA=sha(p),singleCompleteRound=True)
auditp=B/'ctrl/B6-PRESERVATION-before-close-v1.json';audit=json.loads(auditp.read_bytes())
assert all(not x['drift'] for x in audit['groups'].values())
assert not audit['oldQAUnexpectedDrift'] and not audit['backend410Drift'] and audit['nextEnvOriginalExact']
resourcep=B/'ctrl/B6-RESOURCES-before-close-v2.json';resources=json.loads(resourcep.read_bytes())
assert resources['frontendStatus']=='closed' and resources['apiStatus']=='closed'
assert not resources['listeners'] and not resources['remainingOwnedProcesses'] and not resources['automationBrowsersObserved']
assert resources['apiTransportRestored'] and resources['apiSampleRetained']
planp=B/'ctrl/B6-PLAN-ORIGINAL-before-close-v2.json';plan=json.loads(planp.read_bytes())
assert plan['exactOriginalPreserved'] and plan['originalBytes']==65519
required=['b6-integration/RESULT-final-v1.md','b6-quality/RESULT-v1.md','b6-quality/RESULT-CORRIGENDUM-v1.md',
 'b6-quality/integration-export-independent-v2.md','b6-exports/review-quality/RESULT-v1.md',
 'b6-exports/review-source/RESULT-built-v2.md','b6-exports/review-source/UI-r9-REVIEW-v1.md',
 'b6-exports/review-source/G3-BROWSER-B6-REVIEW-v1.md','v00/B6-FINAL-GATE-REVIEW-v1.md',
 'v00/B6-FULL153-RECEIPT-REVIEW-v1.md','v00/B6-FULL153-RECEIPT-REVIEW-v1.json',
 'b6-quality/B6-CHECK-QA-WAIT-REVIEW-v1.md','b6-quality/B6-DOC-SCOPE-REVIEW-v1.md',
 'B6-RECOVERY-REFERENCE-v2.md','ctrl/B6-MATERIALS-SAME-SOURCE-v1.json',
 'ctrl/B6-SERVICE-SOURCE-ATTRIBUTION-v1.json','RAG-REL-REVIEW-CARD-v1.md']
assert all((B/n).exists() for n in required)
gatep=B/'v00/B6-FINAL-GATE-REVIEW-v1.json';gate=json.loads(gatep.read_bytes())
assert gate['result']=='PASS_LIMITED_B6_FINAL_GATES' and gate['candidateSHA']==sha(cp)
record=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(),task='LIMITED_B6_INTEGRATION_AND_QUALITY_PREPARATION',
 result='CLOSED_LIMITED_TECHNICAL_AND_PREPARATION',G3='CLOSED_HISTORICAL_RECEIPT_UNCHANGED',
 originalB6B7Overall='NOT_CLAIMED_CLOSED',candidate=cp.relative_to(R).as_posix(),candidateSHA=sha(cp),
 counts={k:c[k] for k in ('sourceCount','executableQaCount','sharedContractCount','buildCount','frozenB6ArtifactCount')},
 buildId=c['buildId'],actualRewrites=c['actualRewrites'],commands=commands,
 executed=dict(checkUnit=1286,newActualUI=1,actualFourViewportRegression=14,originalFullE2E=153,
               independentSource=8,originalIndependent=15,independentBoundary=8,anonymousQualityCases=15,
               DOCXActualSamples=4,PDFActualSamples=4,PDFActualPages=13,realModelCalls=0),
 evidence={n:sha(B/n) for n in required},independentFinalGate=dict(path=gatep.relative_to(R).as_posix(),SHA=sha(gatep)),
 preservation=dict(path=auditp.relative_to(R).as_posix(),SHA=sha(auditp)),
 resources=dict(path=resourcep.relative_to(R).as_posix(),SHA=sha(resourcep)),
 originalPlan=dict(path=planp.relative_to(R).as_posix(),SHA=sha(planp),originalTasksAndPseudocodePreserved=True),
 newVersusPrior='New endpoint/15 cases/four q84e exports/new built UI+14+153; unchanged backend410/exporter43/recovery exact same-source reuse, not new runs',
 quality='PREPARATION_COMPLETE; live_run awaiting explicit profile/model/case count/budget; teacher_review_pending',
 nativeWordWPS='not_run: bundled LibreOffice resolver unavailable; structure/PDF do not prove native layout',
 otherNotRun=['real6333','formalMigration','extraHeavyPressure','chat14SpecialThisBatch_noChatOrShellImpact'],
 retained=['RAG-REL OPEN','CV01-03','cross-batch R14','OBS-LP-MODE-LABEL','all first failures','all temporary data'],
 oldRejectedExtraHTTP='not_run_no_retry',gitWrites=False,deployment=False,nextBatchStarted=False)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=record['at'],result=record['result'],SHA=sha(out),counts=record['counts']),ensure_ascii=False))
