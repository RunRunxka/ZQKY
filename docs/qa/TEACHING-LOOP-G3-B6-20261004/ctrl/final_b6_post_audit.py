"""Final read-only product/material/document receipt after independent doc acceptance."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import subprocess

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'ctrl/B6-FINAL-POST-AUDIT-v1.json'
assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=B/'CANDIDATE-B6-r1.json';candidate=json.loads(cp.read_bytes())
groups={}
for key in ('sourceFiles','executableQaFiles','sharedContractFiles','buildFiles','frozenB6ArtifactFiles'):
    drift=[n for n,h in candidate[key].items() if not (R/n).is_file() or sha(R/n)!=h]
    assert not drift, (key,drift)
    groups[key]=dict(count=len(candidate[key]),drift=drift)
receipt=B/'B6-CLOSE-v1.json';closed=json.loads(receipt.read_bytes())
assert closed['result']=='CLOSED_LIMITED_TECHNICAL_AND_PREPARATION'
assert closed['originalB6B7Overall']=='NOT_CLAIMED_CLOSED'
assert closed['candidateSHA']==sha(cp)
assert all(sha(B/n)==h for n,h in closed['evidence'].items())
proof_names=['ctrl/B6-PRESERVATION-after-final-docs-v1.json',
 'ctrl/B6-PLAN-ORIGINAL-final-v1.json','ctrl/B6-RESOURCES-after-final-docs-v1.json']
preservation,plan,resource=[json.loads((B/n).read_bytes()) for n in proof_names]
assert all(not v['drift'] for v in preservation['groups'].values())
assert not preservation['oldQAUnexpectedDrift'] and not preservation['backend410Drift']
assert preservation['nextEnvOriginalExact'] and plan['exactOriginalPreserved']
assert plan['originalBytes']==65519
assert resource['frontendStatus']==resource['apiStatus']=='closed'
assert not resource['listeners'] and not resource['remainingOwnedProcesses'] and not resource['automationBrowsersObserved']
assert resource['apiSampleRetained'] and resource['apiTransportRestored']
stable={}
for name in ('docs/PROJECT_GUIDE.md','docs/API.md','docs/ROUTES.md'):
    original=B/'ctrl/opening-documents'/name
    assert original.read_bytes()==(R/name).read_bytes(), name
    stable[name]=sha(R/name)
docs=['docs/CURRENT_STATUS.md','docs/NEXT_SESSION_START.md','docs/README.md','docs/qa/README.md',
 'docs/design/teaching-loop-v1/README.md','docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md',
 'docs/qa/TEACHING-LOOP-G3-B6-20261004/README.md',
 'docs/qa/TEACHING-LOOP-G3-B6-20261004/B6-CLOSE-MATRIX-v1.md']
reviews=['v00/B6-FINAL-GATE-REVIEW-v1.md','v00/B6-FINAL-GATE-REVIEW-v1.json',
 'v00/B6-FINAL-DOC-AUDIT-v1.md','v00/B6-FINAL-DOC-AUDIT-v1.json']
assert all((B/n).is_file() for n in reviews)
doc_review=json.loads((B/reviews[-1]).read_bytes())
assert doc_review['result']=='PASS_FINAL_DOC_SCOPE'
assert all(sha(R/n)==h for n,h in doc_review['documentSHAs'].items())
record=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
 result='PASS_FINAL_POST_AUDIT_LIMITED_SCOPE',candidateSHA=sha(cp),closureSHA=sha(receipt),groups=groups,
 proofs={n:sha(B/n) for n in proof_names},stableDocumentsExact=stable,
 currentDocuments={n:sha(R/n) for n in docs},independentReports={n:sha(B/n) for n in reviews},
 independentDocumentResult=doc_review,
 immutableHistory={n:sha(B/n) for n in ('G3-CLOSE-v1.md','G3-CLOSE-v1.json','CANDIDATE-G3-r2-qa5.json')},
 originalB5CandidateSHA=sha(R/'docs/qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-B5-r8.json'),
 nextEnvOriginalExact=True,originalPlanOnlyStatusAdded=True,temporaryDataRetained=True,
 originalB6B7Overall='NOT_CLAIMED_CLOSED',liveRun='awaiting inputs',teacherReview='pending',
 nativeWordWPS='not_run',RAG_REL='OPEN',oldPolicyHTTP='not_run_no_retry',
 actualHead=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),
 actualBranch=subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip(),
 gitWrites=False,deployment=False,nextBatchStarted=False)
assert record['originalB5CandidateSHA']=='c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007'
assert record['actualHead']=='6cb6a40db890390f0261d547213e319040f64785' and record['actualBranch']=='main'
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(at=record['at'],result=record['result'],SHA=sha(out),groups=groups),ensure_ascii=False))
