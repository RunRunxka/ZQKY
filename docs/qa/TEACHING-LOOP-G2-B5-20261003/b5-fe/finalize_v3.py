"""F30-L v3 append-only author handoff with complete prior and final source hashes."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODULE = ROOT / 'apps/web/src/features/lesson-plan'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
opening = json.loads((OUT / 'BEFORE-v3.json').read_text(encoding='utf-8'))
prior_drift = [name for name, value in opening['preservedPriorEvidence'].items() if sha(ROOT / name) != value]
if prior_drift:
    raise ValueError(f'Prior evidence changed: {prior_drift}')
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(MODULE.rglob('*')) if path.is_file()}
changed = [name for name, value in private.items() if opening['source'].get(name) != value]
if set(changed) != set(opening['approvedProductFiles']):
    raise ValueError(f'Unexpected scope: {changed}')
frozen_path = OUT.parent / 'ctrl/B5-CONTRACT-FROZEN-v1.json'
expected = '8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db'
if sha(frozen_path) != expected:
    raise ValueError('Frozen manifest changed')
frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
drift = [name for name, value in frozen['files'].items() if sha(ROOT / name) != value]
if drift:
    raise ValueError(f'Frozen contracts changed: {drift}')
labels = ['f30-v3-unit-r2', 'f30-v3-types-r2', 'f30-v3-lint-r2']
latest = [json.loads((OUT / f'{label}-command.json').read_text(encoding='utf-8')) for label in labels]
for record in latest:
    if record['exitCode'] or record['changedSources'] or record['uncaughtExceptionRecords']:
        raise ValueError('Latest source-bound checks failed or drifted')
    for name, value in record['sourceAfter'].items():
        if sha(ROOT / name) != value:
            raise ValueError(f'Post-check drift: {name}')
history = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(OUT.glob('f30-v3-*-command.json'))]
for record in history:
    for name, value in record['sourceBefore'].items():
        if sha(OUT / f"{record['label']}-source" / name) != value:
            raise ValueError(f'Original input snapshot changed: {record["label"]} {name}')
first = next(record for record in history if record['label'] == 'f30-v3-unit-r1')
current = latest[0]
qa_delta = [name for name, value in first['sourceAfter'].items() if current['sourceBefore'][name] != value]
if qa_delta != ['apps/web/src/features/lesson-plan/lesson-workspace.test.tsx']:
    raise ValueError(f'Unexpected first-failure QA correction delta: {qa_delta}')
stopped = dt.datetime.now(dt.timezone.utc).isoformat()
manifest = {
    'task': 'F30-L', 'version': 3, 'owner': 'g2_fe', 'status': 'AUTHOR_VERIFIED_PENDING_INDEPENDENT',
    'productWritesStoppedAtUtc': stopped, 'files': private, 'changedProductFiles': changed,
    'beforeManifestSha256': sha(OUT / 'BEFORE-v3.json'),
    'previousManifestSha256': sha(OUT / 'PRIVATE-MANIFEST-v2.json'),
    'preservedPriorEvidenceCount': len(opening['preservedPriorEvidence']), 'priorEvidenceDrift': [],
    'contractManifestSha256': expected, 'contractFileCount': len(frozen['files']), 'contractDrift': [],
    'publicReadOnlyInputs': {name: value for name, value in current['sourceAfter'].items() if not name.startswith('apps/web/src/features/lesson-plan/')},
    'scopeAuthorization': 'CTRL OPEN_WRITE F30-L v3; roster, analysis-runs and practice-sets complete pagination included; all independent first runs finished before writes',
    'sharedAndRootWrites': False,
}
target = OUT / 'PRIVATE-MANIFEST-v3.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
result = {
    'task': 'F30-L', 'version': 3, 'owner': 'g2_fe', 'status': manifest['status'],
    'productWritesStoppedAtUtc': stopped, 'manifest': target.relative_to(ROOT).as_posix(), 'manifestSha256': sha(target),
    'scope': changed, 'contractManifestSha256': expected, 'contractFileCount': 33, 'contractDrift': [],
    'preservedPriorEvidenceCount': manifest['preservedPriorEvidenceCount'], 'priorEvidenceDrift': [],
    'latestChecks': latest,
    'coverage': {'finalSingleRunTests': 95, 'v2TestsRetained': 73, 'newV3Tests': 22, 'files': 5, 'failed': 0, 'skipped': 0, 'crossRunAggregation': False},
    'allRounds': [{k: record.get(k) for k in ['label', 'mode', 'argv', 'environment', 'pid', 'exitCode', 'elapsedMs', 'actual', 'failedCases', 'changedSources', 'firstFailurePreservedIn', 'logSha256', 'sampleRoot', 'sampleRetained', 'childClosed', 'logClosed']} for record in history],
    'firstFailureAttribution': [{'label': 'f30-v3-unit-r1', 'actual': first['actual'], 'kind': 'author unknown-state UI oracle mismatch', 'cause': 'The new status=0 unknown table row incorrectly waited for its specific thrown ApiError message. The public frozen-submission hook intentionally exposes the unknown original-package retry state with error=null. The first DOM already had the retry button and stale disabled old candidate. The revised author QA waits for the actual visible retry state; all checked/disabled/stale/apply-HTTP0, original body/metadata cache and full replay equality assertions and timeout budgets remain and ran in the complete final 95-test run.', 'originalInputs': 'f30-v3-unit-r1-source', 'originalLog': 'f30-v3-unit-r1.log', 'sourceSnapshotSHAVerified': True, 'onlyChangedBetweenRuns': qa_delta, 'productChangeForThisFailure': False}],
    'implementation': {
        'R04': 'Each actually accepted fixed proposal stores a clone of its own original full GenerationRecord. Pending-proposal freshness is based on that fixed job/operation/selection/sourceEpoch/edit/load/base identity. New generate known errors, unknown or recovery-cache failure never retag an old selected proposal. Old stale candidate remains readonly; known failure permits explicit reject. Unknown replay and late GET epoch guard retain exact first identity.',
        'R05': 'Private readPages uses limit200 and complete total-based offsets for active classes, analysis-runs, practice-sets and existing class-report rows. It checks per-page alive/request epoch, safe/stable total, offset, overrun and empty non-progress; only complete lists are adopted. Ready/reviewed filters are applied after all pages. Model/textbook array ports and fixed-question explicit50 continuation unchanged.',
    },
    'newCoverage': [
        'Existing selected M1 candidate -> M2 new generation -> explicit422, explicit503, status0 unknown or source-cache failure: old candidate stays stale/readonly/selected, APPLY HTTP0, original editor unchanged; known failure supports explicit rejection.',
        'Unknown M2 retry deep-equals original full HTTP request and full operation cache.',
        '241 active classes, 241 reports with ready target in final page, and 241 practice sets with reviewed target in final page; strict fake rejects limit>200; actual UI selects all three last objects and checks class eligibility/fixed revision identity.',
        'Each of the three paginated source lists: later-page read error, empty non-progress, illegal total, changed total and wrong offset -> visible error and no adoption of partial source (15 cases).',
        'Late old class page after explicit refresh cannot replace new list; page completion after unmount causes no further reads.',
    ],
    'notRun': ['Independent V00 acceptance', 'Real FastAPI/RAG/model/jobs/Next/browser integration and three-size visual checks', 'Full check/build/fullAPI/e2e/chat gates (CTRL owner)', 'Actual Word/WPS manual layout', 'Formal .env/data/credentials/browser drafts and Git/push/deploy'],
    'resources': {'servicesStartedOrStopped': 0, 'browserContextsOpened': 0, 'realHTTPConnectionsOpened': 0, 'checkChildrenClosed': all(record['childClosed'] for record in history), 'logsClosed': all(record['logClosed'] for record in history), 'sampleRootsRetained': [record['sampleRoot'] for record in history]},
    'writableScopeReleased': True,
}
with (OUT / 'RESULT-v3.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
lines = [
    '# F30-L v3 作者结果卡 — 待独立验收', '',
    f'负责人 g2_fe；停止产品写入 {stopped}。状态 AUTHOR_VERIFIED_PENDING_INDEPENDENT；不关闭 B5。', '',
    f'`PRIVATE-MANIFEST-v3.json` SHA `{sha(target)}`；`BEFORE-v3.json` SHA `{sha(OUT / "BEFORE-v3.json")}`。v1/v2 等全部 1593 项前序证据逐项 SHA 核对无漂移，旧73单轮及全部首败原件保持；冻结33件及清单 SHA `{expected}` 无漂移。只改授权三件，ROOT AGENTS/types/contracts/client/router/其它产品与旧QA不写。', '',
    '| 最新完整窄检查 | 实际结果 | PID | 时间 | 源漂移 |', '| --- | --- | --- | --- | --- |',
    *[f"| {record['label']} | {'95/95；0 failed/0 skipped' if record['mode']=='unit' else 'exit0；0 warnings' if record['mode']=='lint' else 'exit0'} | {record['pid']} | {record['elapsedMs']} ms | 0 |" for record in latest], '',
    '最终一轮5文件、95例 = 原v2保留73 + 新v3 22，不跨轮拼绿。Node24固定路径与 NODE_OPTIONS=--no-experimental-webstorage；各最新轮 uncaughtExceptionRecords=0。完整argv/env/PID/exit/ms/sourceBefore/sourceAfter、原输入快照SHA、日志SHA与保留TEMP见 RESULT-v3.json/各command.json。', '',
    'R04：实际GET接受候选时，保存该固定候选自己的完整首次generation identity clone，同固定job/operation/sourceEpoch与原编辑/加载/基线；stale从该身份判断。新的M2操作422/503/unknown/缓存写入失败不会使已有M1候选借M2签名复活。旧勾选保留但只读，APPLY HTTP为0；明确失败可拒绝旧候选，unknown仍只能恢复原操作。原包深等重放与旧job/GET迟到guard保留。', '',
    'R05：统一私有完整分页，active classes、analysis-runs、practice-sets与原classesReport每页最多200，按total与真实items offset读完再采用；ready/reviewed过滤在读完后执行。每页校验epoch/unmount、safe/stable total、offset、越界、空页无进展；失败可见且不采用半份列表。真实UI选择第241班、第241 ready报告、第241 reviewed固定练习，核班级eligibility与真实固定revision；15项后页错误矩阵和refresh/unmount迟到也通过。教材/模型完整array端口与confirmed固定题50行显式继续保持。', '',
    '首轮 f30-v3-unit-r1 94/95：新增unknown作者用例错误等待具体 ApiError 文本。公共status0语义展示“重试原生成包”并令error=null，首败DOM中旧候选已过期且采用禁用。新QA revision仅改等待真实unknown入口；所有旧候选/selected/APPLY0、M2首次缓存与原包深等断言、用例和时间预算保留。产品不因该首败改动；r1原testbytes/log/JSON保全，r1→r2唯一源delta为测试文件，最终完整95另新单轮实跑，不拼94+窄例。', '',
    '未执行：独立V00、真实API/RAG/model/jobs/Next浏览器链及三视口、全check/build/API/e2e/chat、Word/WPS人工版式。原因：本卡仅作者私有验证，CTRL负责稳定候选/服务与最终门禁。未接触正式.env/数据/凭证/真实草稿，未起停服务、打开浏览器、真实HTTP或执行Git。', '',
    '全部子进程与日志已关闭，隔离TEMP保留。产品可写范围已释放；等CTRL稳定候选及独立验收，不把替身单测当真实闭环通过。', '',
    '## 修改范围', '', *[f'- `{name}`' for name in changed], '',
]
with (OUT / 'RESULT-v3.md').open('x', encoding='utf-8') as stream:
    stream.write('\n'.join(lines))
print(json.dumps({'status': result['status'], 'productFiles': len(changed), 'priorEvidenceFilesVerified': len(opening['preservedPriorEvidence']), 'contractDrift': [], 'manifestSha256': result['manifestSha256'], 'resultSha256': sha(OUT / 'RESULT-v3.json'), 'productWritesStoppedAtUtc': stopped}, ensure_ascii=False))
