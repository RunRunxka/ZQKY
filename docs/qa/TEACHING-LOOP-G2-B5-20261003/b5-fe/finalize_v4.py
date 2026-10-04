"""Append-only F30-L v4 author handoff; no runtime imports or services."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODULE = ROOT / 'apps/web/src/features/lesson-plan'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
opening = json.loads((OUT / 'BEFORE-v4.json').read_text(encoding='utf-8'))
prior_drift = [name for name, value in opening['preservedPriorEvidence'].items() if sha(ROOT / name) != value]
if prior_drift:
    raise ValueError(f'Prior evidence drift: {prior_drift}')
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(MODULE.rglob('*')) if path.is_file()}
if set(private) != set(opening['source']):
    raise ValueError('Private file set changed')
changed = [name for name, value in private.items() if opening['source'][name] != value]
if set(changed) != set(opening['approvedProductFiles']):
    raise ValueError(f'Unexpected scope: {changed}')
for name, value in opening['source'].items():
    if sha(OUT / 'before-v4-source' / name) != value:
        raise ValueError(f'Opening source snapshot changed: {name}')
frozen_path = OUT.parent / 'ctrl/B5-CONTRACT-FROZEN-v1.json'
expected = '8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db'
if sha(frozen_path) != expected:
    raise ValueError('Frozen manifest changed')
frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
drift = [name for name, value in frozen['files'].items() if sha(ROOT / name) != value]
if drift:
    raise ValueError(f'Frozen contract drift: {drift}')
history = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(OUT.glob('f30-v4-*-command.json'))]
for record in history:
    if record['changedSources'] or record['uncaughtExceptionRecords'] or not record['childClosed'] or not record['logClosed']:
        raise ValueError(f'Run drift or resource failure: {record["label"]}')
    for name, value in record['sourceBefore'].items():
        if sha(OUT / f"{record['label']}-source" / name) != value:
            raise ValueError(f'Run source snapshot changed: {record["label"]} {name}')
    if sha(OUT / f"{record['label']}.log") != record['logSha256']:
        raise ValueError(f'Run log changed: {record["label"]}')
    if record.get('resultSha256') and sha(OUT / f"{record['label']}-results.json") != record['resultSha256']:
        raise ValueError(f'Run result changed: {record["label"]}')
labels = ['f30-v4-unit-r1', 'f30-v4-types-r1', 'f30-v4-lint-r1']
latest = [next(record for record in history if record['label'] == label) for label in labels]
for record in latest:
    if record['exitCode']:
        raise ValueError(f'Latest run failed: {record["label"]}')
    for name, value in record['sourceAfter'].items():
        if sha(ROOT / name) != value:
            raise ValueError(f'Post-check source drift: {name}')
first = next(record for record in history if record['label'] == 'f30-v4-unit-before')
if first['actual']['numTotalTests'] != 106 or first['actual']['numFailedTests'] != 5 or latest[0]['actual']['numPassedTests'] != 106:
    raise ValueError('Unexpected test counts')
delta = [name for name, value in first['sourceAfter'].items() if latest[0]['sourceBefore'][name] != value]
if delta != ['apps/web/src/features/lesson-plan/components/SourcePanel.tsx']:
    raise ValueError(f'Unexpected before-fix -> final delta: {delta}')
test_name = 'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'
old_test = (OUT / 'before-v4-source' / test_name).read_bytes()
current_test = (ROOT / test_name).read_bytes()
old_prefix = current_test.split(b'function sourceProfile(', 1)[0]
model_import = b"import type { ModelProfileView } from '@/contracts/model-settings';"
old_prefix = old_prefix.replace(model_import + b'\r\n', b'').replace(model_import + b'\n', b'')
if old_prefix.rstrip(b'\r\n') != old_test.rstrip(b'\r\n'):
    raise ValueError('Original author test definitions changed')
stopped = dt.datetime.now(dt.timezone.utc).isoformat()
manifest = {
    'task': 'F30-L', 'version': 4, 'owner': 'g2_fe', 'issue': 'B5R-R06',
    'status': 'AUTHOR_VERIFIED_PENDING_INDEPENDENT', 'productWritesStoppedAtUtc': stopped,
    'files': private, 'changedProductFiles': changed, 'beforeManifestSha256': sha(OUT / 'BEFORE-v4.json'),
    'previousManifestSha256': sha(OUT / 'PRIVATE-MANIFEST-v3.json'),
    'preservedPriorEvidenceCount': len(opening['preservedPriorEvidence']), 'priorEvidenceDrift': [],
    'contractManifestSha256': expected, 'contractFileCount': len(frozen['files']), 'contractDrift': [],
    'publicReadOnlyInputs': {name: value for name, value in latest[0]['sourceAfter'].items() if not name.startswith('apps/web/src/features/lesson-plan/')},
    'scopeAuthorization': 'CTRL OPEN F30-L v4 after independent B5-r2 full8 first run ended and its API stopped; only SourcePanel and lesson-workspace.test may change',
    'sharedAndRootWrites': False,
}
target = OUT / 'PRIVATE-MANIFEST-v4.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
result = {
    'task': 'F30-L', 'version': 4, 'owner': 'g2_fe', 'issue': 'B5R-R06',
    'status': manifest['status'], 'productWritesStoppedAtUtc': stopped,
    'manifest': target.relative_to(ROOT).as_posix(), 'manifestSha256': sha(target), 'scope': changed,
    'contractManifestSha256': expected, 'contractFileCount': len(frozen['files']), 'contractDrift': [],
    'preservedPriorEvidenceCount': len(opening['preservedPriorEvidence']), 'priorEvidenceDrift': [],
    'latestChecks': latest,
    'coverage': {'finalSingleRunTests': 106, 'v3TestsRetained': 95, 'newV4Tests': 11, 'files': 5, 'failed': 0, 'skipped': 0, 'crossRunAggregation': False, 'originalTestDefinitionsPreserved': True},
    'allRounds': [{k: record.get(k) for k in ['label', 'mode', 'argv', 'environment', 'pid', 'exitCode', 'elapsedMs', 'actual', 'failedCases', 'changedSources', 'firstFailurePreservedIn', 'logSha256', 'resultSha256', 'sampleRoot', 'sampleRetained', 'childClosed', 'logClosed']} for record in history],
    'firstFailureAttribution': [{
        'label': first['label'], 'actual': first['actual'], 'kind': 'product R06 late captured value overwrites current teacher model',
        'cause': 'Initial run completion replaced selected model-b with empty value; same-source refresh paused at classes/report/practices and selected M1 candidate refresh replaced current model-b with captured model-a. Each failed at the actual model DOM assertion, so subsequent duration/requirements/fixed choices/evidence assertions in those five cases were not executed in the before-fix run. Existing 95 tests passed; all eleven complete new assertions executed in the final106 single run.',
        'originalInputs': 'f30-v4-unit-before-source', 'originalLog': 'f30-v4-unit-before.log',
        'sourceSnapshotSHAVerified': True, 'onlyChangedBetweenRuns': delta, 'authorQACorrection': False,
    }],
    'implementation': {
        'R06': 'All current input edits use a synchronous latest-input patch before invoking controlled onChange. Async load and selectRun adopt against latest selection and latest teacher input only after existing alive/epoch/complete-read guards. Same logical source retains verified evidence and legal fixed question/practice selection; actual class/KP/report/subject changes still clear matching invalid evidence and choices. Fresh report checks use current subject/class. Explicit generation source/job/operation cache and ProposalPanel remain byte-identical.',
        'unchangedGuards': 'Per-page <=200 complete pagination, total/offset/no-progress failure visibility, same-subject ready report, class eligibility, valid KP filtering, async epoch/unmount, and exact evidence captured-signature rejection remain. Late evidence verification cannot refill after teacher inputs change. Model change keeps prior fixed candidate visibly stale, selected readonly and APPLY HTTP0.',
    },
    'newCoverage': [
        'Initial report pending while teacher explicitly selects M1 then M2, duration43 and new requirements; late source adopts with all latest values intact.',
        'Same-source refresh paused separately at class list, fixed report, and reviewed practice list; late read keeps M2/43/current requirements, current two fixed questions/two fixed practice IDs and verified evidence.',
        'Late source read fails with status0 unknown or503: visible error, newest teacher inputs and prior complete source remain.',
        'Explicit source cancellation switches to new report; old response cannot replace current report or inputs.',
        'Genuine report or subject switch preserves teacher inputs while clearing invalid practice/evidence; same-subject questions stay, different-subject questions clear.',
        'Late verified evidence after new teacher input is rejected, evidence remains null without input rollback.',
        'Existing selected M1 candidate while source refresh is pending -> explicit M2/43/new requirements -> late ACK preserves M2 and keeps old candidate stale/selected/apply disabled/HTTP0.',
    ],
    'notRun': ['Independent V00/static acceptance', 'Real FastAPI/RAG/model/jobs/Next/browser source chain and four viewports', 'Full check/build/fullAPI/e2e/chat gates (CTRL owner)', 'Word/WPS manual layout', 'Formal .env/data/credentials/browser drafts and Git/push/deploy'],
    'resources': {'servicesStartedOrStopped': 0, 'browserContextsOpened': 0, 'realHTTPConnectionsOpened': 0, 'checkChildrenClosed': all(record['childClosed'] for record in history), 'logsClosed': all(record['logClosed'] for record in history), 'sampleRootsRetained': [record['sampleRoot'] for record in history]},
    'writableScopeReleased': True,
}
with (OUT / 'RESULT-v4.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
lines = [
    '# F30-L v4 作者结果卡 — 待独立验收', '',
    f'负责人 g2_fe；B5R-R06；停止产品及可执行作者QA/runner写入 {stopped}。状态 AUTHOR_VERIFIED_PENDING_INDEPENDENT；不关闭 B5。', '',
    f'`PRIVATE-MANIFEST-v4.json` SHA `{sha(target)}`；`BEFORE-v4.json` SHA `{sha(OUT / "BEFORE-v4.json")}`。全部 {len(opening["preservedPriorEvidence"])} 项前序证据逐项 SHA 无漂移，v1/v2/v3、95作者场景及全部首败原件保持；冻结33件与清单 SHA `{expected}` 无漂移。仅改 SourcePanel 与 lesson-workspace.test；ProposalPanel、ROOT AGENTS、types/contracts/client/router/其余产品及旧QA不写。', '',
    '| 最新完整窄检查 | 实际结果 | PID | 时间 | 源漂移 |', '| --- | --- | --- | --- | --- |',
    *[f"| {record['label']} | {'106/106；0 failed/0 skipped' if record['mode']=='unit' else 'exit0；0 warnings' if record['mode']=='lint' else 'exit0'} | {record['pid']} | {record['elapsedMs']} ms | 0 |" for record in latest], '',
    '最终完整单轮5文件106例 = 原95 + 新11；不跨轮拼绿。旧测试定义逐字节核对保持（仅新增ModelProfileView类型import及尾部新用例）。Node24固定路径 + NODE_OPTIONS=--no-experimental-webstorage；完整argv/env/PID/exit/ms/sourceBefore/sourceAfter、原输入快照、日志SHA、首败及隔离TEMP见RESULT-v4.json/各command.json。', '',
    'R06修复：来源异步采用读取latest selection与当前教师inputs，保留模型/时长/要求；granular patch先同步latest ref再回传onChange，避免同轮迟到闭包用旧整体值覆盖。相同来源刷新保留合法固定题/练习与已核验证据；真实班级/KP/报告/学科变化按意义清除失效证据和选项。每次await后的alive/epoch、同学科ready/班级/KP、完整分页及错误不采用半份均保持。教材核验仍精确比对捕获signature，教师新inputs期间迟到核验拒绝回填。生成原包/幂等/cache/ProposalPanel不变，新模型使既有M1候选过期且不能采用。', '',
    '修前完整f30-v4-unit-before：101/106，exit1，PID24400，11466.86ms，source0；原95全部通过。新增5例真实产品首败：首次固定报告晚读把M2擦为空，classes/report/practices晚读及旧候选刷新把M2倒退M1。失败都发生在模型实际DOM断言，其后的时长/要求/选项/证据断言在该轮未执行，最终完整106全部实跑。新增另外6例unknown/503、取消读取、真正换来源及过期核验在修前已通过。修前源码/testbytes/log/JSON保全，修前→最终唯一变化SourcePanel，作者QA未修改、断言与预算未削弱。', '',
    '新11用例覆盖：首次固定报告晚读；class/report/practice三种刷新晚读；status0/503来源失败；取消后旧响应；真正换报告/学科；教师新输入后核验证据晚到；既有M1勾选候选在刷新期间换M2仍过期/APPLY0。全部使用实际控件、固定期望值和受控API替身，不调用生产merge作oracle。', '',
    '未执行：独立V00/静态审查、真实API/RAG/model/jobs/Next浏览器及四视口、全check/build/API/e2e/chat、Word/WPS人工版式。原因：本卡只作者私有验证，CTRL持有服务与稳定候选最终门禁。未接触正式.env/数据/凭证/真实浏览器草稿，未起停服务、打开浏览器、真实HTTP或执行Git。', '',
    '全部检查子进程及日志已关闭，新隔离TEMP保留。产品/可执行作者QA/私有runner范围已STOP释放，等待CTRL冻结及独立验收；不以替身单测代表真实闭环通过。', '',
    '## 修改范围', '', *[f'- `{name}`' for name in changed], '',
]
with (OUT / 'RESULT-v4.md').open('x', encoding='utf-8') as stream:
    stream.write('\n'.join(lines))
print(json.dumps({'status': result['status'], 'productFiles': len(changed), 'priorEvidenceFilesVerified': len(opening['preservedPriorEvidence']), 'contractDrift': [], 'manifestSha256': sha(target), 'resultSha256': sha(OUT / 'RESULT-v4.json'), 'productWritesStoppedAtUtc': stopped}, ensure_ascii=False))
