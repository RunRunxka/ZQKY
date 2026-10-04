"""Append-only F30-L v2 author result; validate first evidence and final source identity."""
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODULE = ROOT / 'apps/web/src/features/lesson-plan'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
opening = json.loads((OUT / 'BEFORE-v2.json').read_text(encoding='utf-8'))
old_drift = [name for name, value in opening['preservedV1Evidence'].items() if sha(ROOT / name) != value]
if old_drift:
    raise ValueError(f'Historical evidence changed: {old_drift}')
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(MODULE.rglob('*')) if path.is_file()}
changed = [name for name, value in private.items() if opening['source'].get(name) != value]
product = opening['approvedProductFiles'] + ['apps/web/src/features/lesson-plan/components/DocumentGateway.tsx']
root_owned = ['apps/web/src/features/lesson-plan/AGENTS.md']
if set(changed) - set(product + root_owned):
    raise ValueError(f'Unexpected private changes: {changed}')
frozen_path = OUT.parent / 'ctrl/B5-CONTRACT-FROZEN-v1.json'
frozen_sha = '8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db'
if sha(frozen_path) != frozen_sha:
    raise ValueError('Frozen manifest changed')
frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
contract_drift = [name for name, value in frozen['files'].items() if sha(ROOT / name) != value]
if contract_drift:
    raise ValueError(f'Frozen contracts changed: {contract_drift}')
labels = ['f30-v2-unit-r6', 'f30-v2-types-r4', 'f30-v2-lint-r4']
latest = [json.loads((OUT / f'{label}-command.json').read_text(encoding='utf-8')) for label in labels]
for record in latest:
    if record['exitCode'] or record['changedSources'] or record['uncaughtExceptionRecords']:
        raise ValueError('Latest checks failed or drifted')
    for name, value in record['sourceAfter'].items():
        if sha(ROOT / name) != value:
            raise ValueError(f'Post-check source changed: {name}')
history = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(OUT.glob('f30-v2-*-command.json'))]
for record in history:
    snapshot = OUT / f"{record['label']}-source"
    for name, value in record['sourceBefore'].items():
        if sha(snapshot / name) != value:
            raise ValueError(f'Original run inputs changed: {record["label"]} {name}')
stopped = dt.datetime.now(dt.timezone.utc).isoformat()
manifest = {
    'task': 'F30-L', 'version': 2, 'owner': 'g2_fe', 'status': 'AUTHOR_VERIFIED_PENDING_INDEPENDENT',
    'productWritesStoppedAtUtc': stopped, 'files': private,
    'changedProductFiles': [name for name in changed if name in product],
    'rootOwnedReadOnlyChanges': {name: private[name] for name in changed if name in root_owned},
    'beforeManifest': 'BEFORE-v2.json', 'beforeManifestSha256': sha(OUT / 'BEFORE-v2.json'),
    'previousManifest': 'PRIVATE-MANIFEST-v1.json', 'previousManifestSha256': sha(OUT / 'PRIVATE-MANIFEST-v1.json'),
    'historicalEvidenceFilesVerified': len(opening['preservedV1Evidence']), 'historicalEvidenceDrift': old_drift,
    'contractManifestSha256': frozen_sha, 'contractFileCount': len(frozen['files']), 'contractDrift': contract_drift,
    'publicReadOnlyInputs': {name: value for name, value in latest[0]['sourceAfter'].items() if not name.startswith('apps/web/src/features/lesson-plan/')},
    'additionalScopeAuthorization': 'CTRL explicitly authorized DocumentGateway pendingCopy target ownership after root route-key remount fix; AGENTS remains CTRL-owned.'
}
target = OUT / 'PRIVATE-MANIFEST-v2.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
causes = [
    {'labels': ['f30-v2-unit-r1'], 'kind': 'author test setup', 'cause': 'Three unknown-replay table rows reached all body/record/stale/disabled assertions, then attempted to assert calls on the unchanged real applyLessonProposal function. Added an explicit typed spy; no assertion or timeout budget removed.', 'sourceSnapshot': 'f30-v2-unit-r1-source'},
    {'labels': ['f30-v2-lint-r1'], 'kind': 'author harness ref alias', 'cause': 'Context ref assignment through doc.leave.current triggered react-hooks/immutability. The dedicated test harness now aliases leaveRef, matching the explicit mutable-ref contract.', 'sourceSnapshot': 'f30-v2-lint-r1-source'},
    {'labels': ['f30-v2-unit-r3'], 'kind': 'private implementation', 'cause': 'New real initial-props A-to-B test reproduced a late A leave confirmation installing an A copy intent and navigating away from B. Gateway now checks alive/sequence after awaiting leave; successful navigation advances sequence before changing state.', 'sourceSnapshot': 'f30-v2-unit-r3-source'},
    {'labels': ['f30-v2-unit-r5'], 'kind': 'private implementation', 'cause': 'A recovery source record with the same operation ID but different original metadata was not rejected. Compare the complete frozen operation against the server operation and set restored=false on any read failure; both original cache strings are preserved.', 'sourceSnapshot': 'f30-v2-unit-r5-source'},
]
not_run = [
    'Independent V00 acceptance and real FastAPI/RAG/model/job HTTP/browser paths',
    'Full check/build/full API/e2e/chat and actual Next route/native Back gates (CTRL-owned)',
    'Desktop/tablet/mobile visual acceptance and actual Word/WPS manual layout',
    'Formal .env/credentials/data/browser storage and Git operations/push/deploy',
]
result = {
    'task': 'F30-L', 'version': 2, 'owner': 'g2_fe', 'status': manifest['status'],
    'productWritesStoppedAtUtc': stopped, 'manifest': target.relative_to(ROOT).as_posix(), 'manifestSha256': sha(target),
    'scope': manifest['changedProductFiles'], 'rootOwnedReadOnlyChanges': manifest['rootOwnedReadOnlyChanges'],
    'historicalEvidenceFilesVerified': manifest['historicalEvidenceFilesVerified'], 'historicalEvidenceDrift': [],
    'contractManifestSha256': frozen_sha, 'contractFileCount': 33, 'contractDrift': [],
    'latestChecks': latest,
    'allRounds': [{k: record.get(k) for k in ['label', 'mode', 'argv', 'pid', 'exitCode', 'elapsedMs', 'actual', 'failedCases', 'changedSources', 'firstFailurePreservedIn', 'logSha256', 'sampleRoot', 'sampleRetained', 'childClosed', 'logClosed']} for record in history],
    'firstFailureAttribution': causes, 'originalInputSnapshotSHAVerified': True,
    'coverage': {'finalSingleRunTests': 73, 'v1TestsRetained': 50, 'newV2Tests': 23, 'files': 5, 'failed': 0, 'skipped': 0},
    'recordSchema': {'key': 'zhiqikeyuan:lesson-plan:generation:v1:<encoded documentId>', 'value': '{schemaVersion:1,operation:<complete FrozenSubmission including metadata>,selectionKey:string,sourceEpoch:number|null,receipt:LessonGenerationReceipt|null}', 'beforeHTTP': True, 'unknownRetainsFirst': True, 'legacyWithoutEpoch': 'read-only conservative stale; original load identity also prevents applying after reload'},
    'notRun': not_run,
    'resources': {'servicesStartedOrStopped': 0, 'browserContextsOpened': 0, 'checkChildrenClosed': all(record['childClosed'] for record in history), 'logsClosed': all(record['logClosed'] for record in history), 'sampleRootsRetained': [record['sampleRoot'] for record in history]},
    'writableScopeReleased': True,
}
with (OUT / 'RESULT-v2.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
lines = [
    '# F30-L v2 作者结果卡 — 待独立验收', '',
    f'负责人 g2_fe；产品停止写入 {stopped}。本结果仅为作者窄回归，不关闭 B5。', '',
    f'私有清单 `PRIVATE-MANIFEST-v2.json` SHA `{sha(target)}`；`BEFORE-v2.json` SHA `{sha(OUT / "BEFORE-v2.json")}`。v1 的 834 项原证据逐项 SHA 核对零漂移；B5 冻结 33 件及冻结清单 SHA `{frozen_sha}` 均零漂移。ROOT 独占更新模块 AGENTS，已只读采用最新实际字节并单列，原 v1/BEFORE 不追改。', '',
    '| 最后完整窄检查 | 实际结果 | PID | 单轮时间 | 源漂移 |', '| --- | --- | --- | --- | --- |',
    *[f"| {record['label']} | {'73/73；0 failed/0 skipped' if record['mode']=='unit' else 'exit 0；0 warnings' if record['mode']=='lint' else 'exit 0'} | {record['pid']} | {record['elapsedMs']} ms | 0 |" for record in latest], '',
    '最终一轮 5 文件、73 例 = v1 保留 50 + v2 新增 23，非跨轮累加。Node 24 固定路径、NODE_OPTIONS=--no-experimental-webstorage；最新各轮 uncaughtExceptionRecords=0。完整 argv、环境、PID、exit/ms、sourceBefore/After、日志 SHA、首败归因与原输入快照、隔离 TEMP 保留见 RESULT-v2.json 和各 command.json。', '',
    'R04：点击时捕获来源/模型、正文代次、加载身份；await flush 后任一变化取消并给出说明，不自动采用新选择或旧正文。原操作在 HTTP 前同时保存完整 FrozenSubmission 与首次 source signature/epoch；unknown 深等原包重放保留原 source/edit/load。来源或模型 A→B→A 也失效；reload 旧候选保守 stale，可查看/拒绝；教师显式新点击才创建新输入。旧 job/proposal GET 不能贴到新 generation。恢复包的同 operation ID、不同首次 metadata 会暂停，原两份缓存字节不覆盖。', '',
    'R05：固定报告按真实上限 200 行逐页读取至 total；total 是班级×知识点行数，读完后去重 class IDs。每页保留请求 epoch；非法 total/offset、total 改变、越界、缺失空页或读取失败可见，未采用不完整来源。已覆盖目标班级只在第 201 行，前 200 行为同班重复 KP 行，以及后页失败/空页/非法 total/变化 total。要求输入旁显示个人信息提示并有 aria-describedby。', '',
    'R03 私有补充：同一文档历史→当前 copy 快照在真实 initial props 去掉 revisionId 后保留；另开文档、另一 history、本地会清 intent。leave 取消时不安装 intent；A 的迟到确认不能覆盖已由 props 选择的 B。root page key 由 CTRL 修改，不属于本实现写入。', '',
    '首失败全部保留：unit-r1 68/71 为三项测试漏设 spy；lint-r1 为测试 Context Ref 别名；unit-r3 71/72 为真实 Gateway 迟到离开跨文档问题；unit-r5 72/73 为首次恢复 metadata 只比 ID 的实现问题。后两项先添加真实反例保全失败，再改产品。修后新 label，不删除用例、不弱化断言、不延长预算；所有执行输入快照 SHA 已验证。', '',
    '未执行及原因：独立 V00、真实 API/RAG/model/job 和浏览器链、全量 check/build/API/e2e/chat、真实 Next/native Back、各尺寸视觉及 Word/WPS 人工版式均由 CTRL/独立验收负责；本卡仅有限私有验证。未读写正式 .env/数据/凭证/真实草稿，没有起停服务、打开浏览器或执行 Git。', '',
    '所有检查子进程与日志已关闭，全部隔离 TEMP 保留。产品写权限已释放；等待 CTRL 稳定候选和独立 V00，不把替身/单测通过当真实闭环验收。', '',
    '## 本批可写产品变更', '', *[f'- `{name}`' for name in manifest['changedProductFiles']], '',
]
with (OUT / 'RESULT-v2.md').open('x', encoding='utf-8') as stream:
    stream.write('\n'.join(lines))
print(json.dumps({'status': result['status'], 'changedProductFiles': len(result['scope']), 'rootOwnedChanges': result['rootOwnedReadOnlyChanges'], 'historicalEvidenceFilesVerified': 834, 'contractDrift': [], 'manifestSha256': result['manifestSha256'], 'resultSha256': sha(OUT / 'RESULT-v2.json'), 'productWritesStoppedAtUtc': stopped}, ensure_ascii=False))
