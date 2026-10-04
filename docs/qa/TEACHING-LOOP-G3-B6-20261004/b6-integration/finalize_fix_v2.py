"""Append the stopped B6-R01 v2 author receipt without modifying v1."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base = json.loads((HERE.parent / 'CANDIDATE-B6-base-v1.json').read_bytes())
product = 'apps/web/src/features/lesson-plan/components/SourcePanel.tsx'
test = 'apps/web/src/features/lesson-plan/b6-source-loading.test.tsx'
labels = ['fix-v2-opening-pending-r1', 'fix-v2-author-unit-r1', 'fix-v2-author-types-r1', 'fix-v2-author-lint-r1']
commands = {n: json.loads((HERE / n / 'COMMAND.json').read_bytes()) for n in labels}
checks = labels[1:]
for n in checks:
    assert commands[n]['exitCode'] == 0 and not commands[n]['sourceDrift'] and not commands[n]['qaDrift']
    assert commands[n]['sourceAfter'][product] == sha(ROOT / product)
    assert commands[n]['sourceAfter'][test] == sha(ROOT / test)
assert '142 passed (142)' in (HERE / checks[0] / 'output.log').read_text(encoding='utf-8')
result = dict(
    task='B6-R01-AUTHOR-v2', status='AUTHOR_READY_PRODUCT_STOP_INDEPENDENT_PENDING',
    at=datetime.now(timezone.utc).isoformat(), changedProducts={product: sha(ROOT / product)},
    newTests={test: sha(ROOT / test)}, productStopped=True, authorTestStopped=True,
    otherG3Products={n: sha(ROOT / n) for n in [
        'apps/web/src/features/lesson-plan/model/useServerPersistence.ts',
        'apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx']},
    baseCandidateSHA=sha(HERE.parent / 'CANDIDATE-B6-base-v1.json'),
    sourceDeltaFromBase=[n for n, h in base['sourceFiles'].items() if sha(ROOT / n) != h],
    sourceLF=dict(crlf=(ROOT / product).read_bytes().count(b'\r\n'), lf=(ROOT / product).read_bytes().count(b'\n')),
    preservedV1=dict(jsonSHA=sha(HERE / 'B6-R01-AUTHOR-RESULT-v1.json'), mdSHA=sha(HERE / 'B6-R01-AUTHOR-RESULT-v1.md'),
        originalProductSHA=sha(HERE / 'B6-R01-v2-opening/SourcePanel.tsx'),
        originalTestSHA=sha(HERE / 'B6-R01-v2-opening/b6-source-loading.test.tsx')),
    firstRequired=dict(label=labels[0], passed=0, failed=1, filteredSkipped=4,
        reason='Existing A, explicit B pending, then metadata refresh calls old A getRun twice and cancels B.',
        expectation='Old A getRun stays exactly once; B eventually becomes the complete selected source.'),
    implementation=[
        'Track the currently owned report intent by a private Symbol.',
        'Automatic metadata report selection requires no pending intent both at metadata start and adoption, plus unchanged selection epoch.',
        'Success/failure/clear release only their own report Symbol in finally; an old completion cannot release a newer intent.',
        'Unmount and successful discard invalidate report ownership while existing metadata/source mode/document/store/session guards remain.'],
    finalChecks={n: {k: commands[n].get(k) for k in ['command', 'pid', 'exitCode', 'durationMs', 'sourceDrift', 'qaDrift', 'nextEnvSHA']} for n in checks},
    finalUnit=dict(files=7, passed=142, failed=0, skipped=0, newMeaningfulBehavior=5, affectedPrior=137),
    nextEnvBeforeSHA=base['nextEnvSHA'], nextEnvAfterSHA=sha(ROOT / 'apps/web/next-env.d.ts'),
    nextEnvChangedByAuthor=False, nextEnvWrittenByAuthor=False, typegenCommandsRun=False, buildCommandsRun=False,
    baseBuildFilesCompared=len(base['buildFiles']),
    baseBuildDeltaAtProductStop=[n for n, h in base['buildFiles'].items() if not (ROOT / n).exists() or sha(ROOT / n) != h],
    buildCacheAttribution='Direct tsc may update its incremental cache; no author typegen/build or next-env write. ROOT owns all build work.',
    authorChildrenClosed=all(commands[n].get('childClosed', False) for n in labels), servicesStarted=False, gitWrites=False,
    notRun=['ROOT independent complete eight on v2', 'ROOT full check and new production build',
        'fresh built actual delayed-metadata browser five-field chain', 'paid model / teacher rubric review'],
    evidence={n: dict(receiptSHA=sha(HERE / n / 'COMMAND.json'), logSHA=sha(HERE / n / 'output.log')) for n in labels})
path = HERE / 'B6-R01-AUTHOR-RESULT-v2.json'
summary = HERE / 'B6-R01-AUTHOR-RESULT-v2.md'
assert not path.exists() and not summary.exists()
path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
summary.write_text('''# B6-R01 作者结果 v2

产品与作者测试已 STOP，待独立复验。只修改 SourcePanel.tsx，并在同一个新作者测试文件追加第五个真实 Workspace 行为；v1 报告、源码及所有首败均保留。

修前第五个反例实跑 1 failed、4 filtered skipped：已有固定报告 A，教师读取 B 在途，刷新元数据先完成，实际自动重读 A（getRun A 从预期 1 次变成 2 次），撤销 B。修前精确源码、断言和首败保留在 fix-v2-opening-pending-r1。

最小修复增加报告请求 Symbol owner。元数据自动复选同时要求开始与采用时没有报告意图，并维持原选择 epoch 校验。成功、失败或清关联只在 finally 释放本人 Symbol，旧请求不能释放新意图；成功 discard 和卸载同步失效报告 owner。原 mode/document/store/live-session 与元数据刷新 ownership 守卫保留。

最终同一候选 7 文件 142/142 通过（5 新行为、137 受影响旧回归），direct tsc 通过，定向 lint 零警告。命令、PID、duration、源码/QA SHA 在 JSON 和每轮 COMMAND.json 中，最后三项 before/after 漂移全部为 0。next-env 仍为原 SHA 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc；无 typegen/build、next-env 写入、服务或 Git 操作。

独立完整八例、ROOT 完整 check/新构建、真实延迟元数据的完整 UI 五字段链均未执行本候选；教学质量仍 teacher_review_pending。现有无 TCP 后台整链证据保持原样，不因本轮前端 SourcePanel 修复冒称后台重跑。
''', encoding='utf-8')
print(json.dumps({k: result[k] for k in ['changedProducts', 'newTests', 'sourceDeltaFromBase', 'sourceLF', 'baseBuildDeltaAtProductStop', 'nextEnvAfterSHA']}, ensure_ascii=False))
