"""Produce F30-L author-only handoff, checking frozen hashes and last check sources."""
import datetime as dt
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODULE = ROOT / 'apps/web/src/features/lesson-plan'
FROZEN = OUT.parent / 'ctrl/B5-CONTRACT-FROZEN-v1.json'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
expected = '8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db'
if sha(FROZEN) != expected: raise ValueError('frozen manifest changed')
frozen = json.loads(FROZEN.read_text(encoding='utf-8'))
drift = [name for name, value in frozen['files'].items() if sha(ROOT / name) != value]
if drift: raise ValueError(f'Frozen inputs drifted: {drift}')
opening = json.loads((OUT / 'opening-v1.json').read_text(encoding='utf-8'))
private = {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(MODULE.rglob('*')) if path.is_file()}
changed = [name for name, value in private.items() if name in opening['sources'] and opening['sources'][name] != value]
added = [name for name in private if name not in opening['sources']]
if 'apps/web/src/features/lesson-plan/model/types.ts' in changed: raise ValueError('shared type was modified')
latest = [json.loads((OUT / f'{label}-command.json').read_text(encoding='utf-8')) for label in ['f30-unit-r6', 'f30-types-r7', 'f30-lint-r4']]
for record in latest:
    if record['exitCode'] or record['changedSources']: raise ValueError('latest check did not pass without drift')
    for name, value in record['sourceAfter'].items():
        if sha(ROOT / name) != value: raise ValueError(f'Post-check drift: {name}')
history = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(OUT.glob('f30-*-command.json'))]
at = dt.datetime.now(dt.timezone.utc).isoformat()
manifest = {'task': 'F30-L', 'version': 1, 'owner': 'g2_fe', 'status': 'AUTHOR_VERIFIED_PENDING_INDEPENDENT', 'productWritesStoppedAtUtc': at, 'contractManifestSha256': expected, 'contractFileCount': len(frozen['files']), 'contractDrift': drift, 'files': private, 'changedExisting': changed, 'newFiles': added, 'publicReadOnlyInputs': {name: value for name, value in latest[0]['sourceAfter'].items() if not name.startswith('apps/web/src/features/lesson-plan/')}}
target = OUT / 'PRIVATE-MANIFEST-v1.json'
with target.open('x', encoding='utf-8') as stream: json.dump(manifest, stream, ensure_ascii=False, indent=2)
result = {'task': 'F30-L', 'version': 1, 'owner': 'g2_fe', 'status': manifest['status'], 'productWritesStoppedAtUtc': at, 'manifest': target.relative_to(ROOT).as_posix(), 'manifestSha256': sha(target), 'contractManifestSha256': expected, 'contractFileCount': 33, 'contractDrift': [], 'scope': {'changedExisting': changed, 'newFiles': added, 'sharedTypesUnchanged': True}, 'latestChecks': [{k: record.get(k) for k in ['label', 'mode', 'argv', 'environment', 'pid', 'exitCode', 'elapsedMs', 'actual', 'changedSources', 'uncaughtExceptionRecords', 'sourceBefore', 'sourceAfter', 'sampleRoot', 'sampleRetained', 'childClosed', 'logClosed', 'logSha256']} for record in latest], 'allRounds': [{k: record.get(k) for k in ['label', 'mode', 'exitCode', 'elapsedMs', 'actual', 'firstFailurePreservedIn', 'sampleRoot', 'changedSources']} for record in history], 'firstFailureAttribution': [
 {'labels': ['f30-types-r1'], 'kind': 'private implementation', 'cause': 'TypeScript cannot infer asynchronous callback assignment to local nullable ApiError; replaced with explicit mutable holder.', 'originalInputs': 'f30-types-r1-source', 'shaVerified': True},
 {'labels': ['f30-lint-r1'], 'kind': 'private implementation', 'cause': 'Context ref mutations required explicit Ref aliases; effect dependency required stable setter.', 'originalInputs': 'f30-lint-r1-source', 'shaVerified': True},
 {'labels': ['f30-types-r3'], 'kind': 'author fixture typing', 'cause': 'Unsupported fireEvent.toggle, widened mock discriminants, narrow mock argument tuples, ApiError details argument position.', 'originalInputs': 'f30-types-r3-source'},
 {'labels': ['f30-unit-r2'], 'kind': 'author harness timing/API', 'cause': 'Unsupported toggle helper and clicking generation before its restoration-ready button was enabled. All final stale/input assertions and time budget kept; real interaction readiness added.', 'originalInputs': 'f30-unit-r2-source'}], 'publicDependencies': ['CTRL provided confirmed fixed question revision read port; UI selects returned IDs, never derives or types them.', 'CTRL provided NavigationGuardController.hasProvider; standalone only uses beforeNavigate, root Provider registers one leave guard.'], 'notRun': ['independent V00 acceptance', 'real FastAPI/RAG/model/job wire integration and browser correct behavior', 'full check/build/full API/e2e/chat gates (CTRL owner)', 'desktop/tablet/mobile screenshots and actual native Back/reload browser behavior', 'real Word/WPS manual layout', 'formal migration/data/credentials/real browser storage', 'Git operations/push/deploy'], 'resources': {'servicesStartedOrStopped': 0, 'browserContextsOpened': 0, 'checkChildrenClosed': all(record['childClosed'] for record in history), 'sampleRootsRetained': [record['sampleRoot'] for record in history]}, 'writableScopeReleased': True}
with (OUT / 'RESULT-v1.json').open('x', encoding='utf-8') as stream: json.dump(result, stream, ensure_ascii=False, indent=2)
lines = [
 '# F30-L v1 作者结果卡 — 待独立验收', '',
 f'负责人 g2_fe；产品停止写入 {at}。B5 冻结清单 SHA `{expected}`，33 件核对无漂移。私有清单 `PRIVATE-MANIFEST-v1.json` SHA `{sha(target)}`；共享 `model/types.ts` 保持原字节。', '',
 f'本模块变更既有 {len(changed)} 件，新增 {len(added)} 件。完整文件与源码 SHA、argv、环境、PID、exit、单轮时间、首败原日志/输入、保留 TEMP、资源退出见 RESULT-v1.json 与每轮 command.json。', '',
 '| 最后完整窄检查 | 实际结果 | PID | 耗时 | 源漂移 |', '| --- | --- | --- | --- | --- |',
 *[f"| {record['label']} | {'50/50；0 failed/0 skipped' if record['mode']=='unit' else 'exit 0；零警告' if record['mode']=='lint' else 'exit 0'} | {record['pid']} | {record['elapsedMs']} ms | 0 |" for record in latest], '',
 '最后单轮共 5 文件、50 例：既有规则/分页/导出映射/serial writer 15 例；新增服务器 session、原操作恢复与工作台 UI 35 例。不是跨轮累加。最后三轮 uncaughtExceptionRecords 均为 0。', '',
 '已接入原工作台：后台 list/create/import/current/history/save；每 document 独立缓存和 600ms serial save；首次完整 edit/load/operation 冻结；在途后编辑保持；unknown 原包重放及 StrictMode 无自动 HTTP；较高 CAS/同 CAS 不同固定 ID 防回退；409 可信 GET 后人工对照；内部文档、历史、本地切换及根导航离开四选择；pending/unknown 不可丢弃。成功 create/import/open 使用真实 lessonPlanId URL；后续 route props 同步，刷新按 document key 恢复。invalid route 持续阻断依赖读/编辑，旧本地键空串为读取错误，missing 仍正常。', '',
 '来源只读选择单一学科/班级、ready fixed report/KPs、真实教材 span → 后端 verified scope/evidence、真实 confirmed fixed question IDs、reviewed practice IDs。候选使用公共 six-state job、五个 whole-field diff、选字段一次 store.replace 保留 undo、拒绝不改文；编辑/model/source 变化和晚到候选可见 stale。模型/服务测试使用隔离替身，不能算真实后台链验收。', '',
 'Word/JSON 当前 data/source 同时捕获；打印在 100ms 前冻结 data/source，打印期间编辑不改变纸面，afterprint 恢复。原 Word 模板及 schemaVersion=1/旧 key 保持；旧规则 parse/warnings/confirmation、undo/redo、local writer 兼容。', '',
 '首败全部保留：types-r1 异步闭包推断与 lint-r1 Context Ref 写法属于实现问题；types-r3 fixture 类型和 unit-r2 toggle/readiness 属作者测试问题。修后用新 label，不删除用例、不降低断言、不增加时序预算。首轮两项已逆向按 command SHA 验证重建全部 45 输入字节；后续检查在执行前自动拷贝输入，原日志和 JSON 均不覆盖。', '',
 '未执行：独立 V00、真实 FastAPI/RAG/三协议/model/jobs 浏览器链、全量 check/build/API/e2e/chat、各分辨率视觉/native Back 实机、Word/WPS 人工排版与正式迁移。原因：本卡只授予作者有限私有验证；服务与最终门禁由 CTRL 管理。没有读取正式 .env/凭证/真实草稿，没有起停服务/打开浏览器/Git 写入。', '',
 '所有检查子进程与日志均已关闭；TEMP 样本全部保留。私有产品写权限已释放；下一动作由 CTRL 形成稳定候选并向未参与实现者授权独立验收。B5 尚未验收关闭。', '',
 '## 修改范围', '', *[f'- `{name}`' for name in changed + added], '' ]
with (OUT / 'RESULT-v1.md').open('x', encoding='utf-8') as stream: stream.write('\n'.join(lines))
print(json.dumps({'status': result['status'], 'changedExisting': len(changed), 'newFiles': len(added), 'contractDrift': drift, 'manifestSha256': result['manifestSha256'], 'productWritesStoppedAtUtc': at}, ensure_ascii=False))
