"""Source-only B6-R01 author result; no business imports or extra checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
base = json.loads((HERE.parent/'CANDIDATE-B6-base-v1.json').read_bytes())
product = 'apps/web/src/features/lesson-plan/components/SourcePanel.tsx'
test = 'apps/web/src/features/lesson-plan/b6-source-loading.test.tsx'
labels = ['fix-opening-required-r1','fix-author-unit-r1','fix-author-unit-r2','fix-author-unit-r3',
    'fix-author-types-r1','fix-author-types-r2','fix-author-types-r3','fix-author-lint-r1','fix-author-lint-r2','fix-author-lint-r3']
commands = {n:json.loads((HERE/n/'COMMAND.json').read_bytes()) for n in labels}
build_delta = [n for n,h in base['buildFiles'].items() if not (ROOT/n).exists() or sha(ROOT/n)!=h]
result = dict(task='B6-R01-AUTHOR-v1',status='AUTHOR_READY_PRODUCT_STOP_INDEPENDENT_PENDING',
    at=datetime.now(timezone.utc).isoformat(),changedProducts={product:sha(ROOT/product)},newTests={test:sha(ROOT/test)},
    otherG3Products={n:sha(ROOT/n) for n in ['apps/web/src/features/lesson-plan/model/useServerPersistence.ts',
        'apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx']},
    baseCandidateSHA=sha(HERE.parent/'CANDIDATE-B6-base-v1.json'),
    sourceDeltaFromBase=[n for n,h in base['sourceFiles'].items() if sha(ROOT/n)!=h],
    sourceLF=dict(crlf=(ROOT/product).read_bytes().count(b'\r\n'),lf=(ROOT/product).read_bytes().count(b'\n')),
    nextEnvBeforeSHA=base['nextEnvSHA'],nextEnvAfterSHA=sha(ROOT/'apps/web/next-env.d.ts'),
    nextEnvChangedByAuthor=False,typegenCommandsRun=False,buildCommandsRun=False,nextEnvWrittenByAuthor=False,
    baseBuildFilesCompared=len(base['buildFiles']),baseBuildDeltaAtProductStop=build_delta,
    buildCacheAttribution='No author build/typegen; direct tsc incremental cache is not business source. Root owns rebuild.',
    firstRequired=dict(label='fix-opening-required-r1',result='1 failed + 3 filtered skipped',
        reason='real SourcePanel explicit ready report completed while metadata deferred; late profiles/taxonomy absent'),
    authorFailures=[dict(label='fix-author-unit-r1',result='140 pass +1 fail',
        reason='new QA expected persistence key for unchanged trusted context; null key is correct; no product change for this'),
        dict(label='fix-author-lint-r2',result='zero-warning gate failed for one dead QA constant',
            reason='unused new test constant removed; product unchanged')],
    finalChecks={n:{k:commands[n].get(k) for k in ['command','pid','exitCode','durationMs','sourceDrift','qaDrift','nextEnvSHA']} 
        for n in ['fix-author-unit-r3','fix-author-types-r3','fix-author-lint-r3']},
    finalUnit=dict(files=7,passed=141,failed=0,skipped=0,newMeaningfulBehavior=4),
    implementation=['separate metadata ownership from report/evidence selection epoch',
        'metadata still binds mount/mode/document/store/live server session and successful discard invalidation',
        'only latest refresh accepts lists or releases its loading indicator',
        'late metadata cannot automatically restore a teacher-replaced source selection'],
    notRun=['root full check/build','independent component acceptance','new built UI full five-field chain',
        'paid model / teacher rubric review'],servicesStarted=False,gitWrites=False,
    productStopped=True,authorChildrenClosed=all(commands[n].get('childClosed',False) for n in labels),
    evidence={n:dict(receiptSHA=sha(HERE/n/'COMMAND.json'),logSHA=sha(HERE/n/'output.log')) for n in labels})
path=HERE/'B6-R01-AUTHOR-RESULT-v1.json'
assert not path.exists()
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=HERE/'B6-R01-AUTHOR-RESULT-v1.md'
assert not summary.exists()
summary.write_text('''# B6-R01 作者结果 v1

产品已 STOP，待独立复验。唯一修改产品为 SourcePanel.tsx；新增 b6-source-loading.test.tsx 四个真实组件行为。

修前正确行为 1 failed、3 filtered skipped：打开来源总列表时模型读取暂缓，显式 ready 报告读取成功后，迟到元数据仍应显示模型/年级/版本并释放加载提示；实际未显示。原源码、QA 和首败已保留。

修复将元数据读取 owner 与报告/证据选择 epoch 分开，保留 mount/mode/document/store/live-session/discard 全部身份核验。元数据只允许最新刷新采用；自动复选旧报告还须教师选择代次未变。成功 discard 使旧元数据失权。初始可信正文和同一 context 读取不会无条件新建恢复键。

最后同一候选实际 7 文件 141 单测通过（4 新行为 + 137 受影响回归），direct tsc 通过，定向 lint 零警告。全部命令 PID、duration、源码/QA before/after SHA 在 JSON 与每次 COMMAND 中，最后漂移均为 0。修后第一轮新 QA 对 null recovery key 的预期错误和零警告门槛发现的死常量首败均原样保留；两项只修改新测试，没有让产品重建恢复键。

没有运行 typegen/build，没有写 next-env，没有服务/Git 操作。next-env 原 SHA 保持 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc。ROOT 独占完整 check、生产构建与资源控制；独立组件和真实 UI 五字段链尚未执行，教学质量仍 teacher_review_pending。
''',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['changedProducts','newTests','sourceDeltaFromBase','sourceLF','baseBuildDeltaAtProductStop','nextEnvAfterSHA']},ensure_ascii=False))
