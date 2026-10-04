"""Freeze complete stopped B6 author inputs, QA and product for independent acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'CANDIDATE-B6-r1.json'
assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
product_path=B/'CANDIDATE-B6-R01-r2-built.json'
product=json.loads(product_path.read_bytes())
assert all(sha(R/n)==h for k in ('sourceFiles','sharedContractFiles','buildFiles') for n,h in product[k].items())
assert (R/'apps/web/next-env.d.ts').read_bytes()==(B/'ctrl/next-env.opening.bin').read_bytes()
required=['b6-integration/RESULT-final-v1.md','b6-quality/RESULT-v1.md','b6-exports/RESULT-v1.md']
assert all((B/n).exists() for n in required), 'All three author STOP reports required'
independent_required=['b6-quality/B6-DOC-SCOPE-REVIEW-v1.md',
 'b6-exports/review-source/RESULT-built-v2.md',
 'b6-exports/review-source/UI-r9-REVIEW-v1.md',
 'b6-exports/review-source/G3-BROWSER-B6-REVIEW-v1.md',
 'b6-exports/review-source/G3-BROWSER-B6-REVIEW-v1.json']
assert all((B/n).exists() for n in independent_required), 'Three-lane independent materials must also STOP before freeze'
qa=set(product['executableQaFiles'])|{p.relative_to(R).as_posix() for p in B.rglob('*')
 if p.is_file() and p.suffix in ('.py','.ts','.tsx','.mjs','.cjs','.ps1')}
inputs={p.relative_to(R).as_posix():sha(p) for directory in ('b6-integration','b6-quality','b6-exports')
 for p in (B/directory).rglob('*') if p.is_file()}
record={k:product[k] for k in ('sourceFiles','sourceCount','sharedContractFiles','sharedContractCount',
 'buildFiles','buildCount','buildId','actualRewrites','nextEnvSHA','productionChangesFromG3','addedTestsFromG3',
 'existingQASynchronizationChanges','originalAssertionsPreserved')}
record.update(task='B6-r1',at=datetime.now(timezone.utc).isoformat(),
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip(),
 productOrigin=product_path.relative_to(R).as_posix(),productOriginSHA=sha(product_path),
 executableQaFiles={n:sha(R/n) for n in sorted(qa)},executableQaCount=len(qa),
 frozenB6ArtifactFiles=inputs,frozenB6ArtifactCount=len(inputs),stoppedProduct=True,stoppedThreeLanes=True,
 G3='CLOSED_HISTORICAL_RECEIPT_PRESERVED',B6='PENDING_INDEPENDENT_LIMITED_TECHNICAL_AND_PREPARATION_ACCEPTANCE',
 live_run='awaiting explicit profile/model/count/budget',teacher_review='pending',
 originalPlanB6B7Overall='not_claimed_closed',gitWrites=False,
 authorStopEvidence={n:sha(B/n) for n in required},
 independentStoppedMaterialEvidence={n:sha(B/n) for n in independent_required},
 requirementMatrixSHA=sha(B/'B6-REMAINDER-MATRIX-v1.md'),taskCardsSHA=sha(B/'B6-TASK-CARDS-v1.md'),
 addedRepairTaskSHA=sha(B/'B6-R01-TASK-v1.md'),addedRepairTaskV2SHA=sha(B/'B6-R01-TASK-v2.md'),
 qaSynchronizationTaskSHA=sha(B/'B6-CHECK-QA-TASK-v1.md'))
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(candidate=str(out.relative_to(R)),SHA=sha(out),sourceCount=record['sourceCount'],
 executableQaCount=len(qa),artifactCount=len(inputs),buildId=record['buildId']),ensure_ascii=False))
