"""ROOT closure and additive current status. Run only after independent signoff."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
B = ROOT / 'docs/qa/TEACHING-LOOP-G3-B6-20261004'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
at = datetime.now(timezone(timedelta(hours=8))).isoformat()
assert not (B / 'G3-CLOSE-v1.json').exists()
independent = ['boundary/G3-CLOSE-AUDIT-v1.md', 'boundary/G3-CLOSE-AUDIT-v1.json',
               'v00/G3-FINAL-V00-v1.md', 'v00/G3-FINAL-V00-v1.json']
assert all((B / name).is_file() for name in independent)
receipt = json.loads((B / 'ctrl/g3-e2e-full-r2-qa5-node24-second-command.json').read_bytes())
results = json.loads((B / 'e2e-g3-r2-qa5-node24-second/results.json').read_bytes())
assert receipt['exitCode'] == 0 and not receipt['changedSources'] and not receipt['changedQA']
assert results['stats']['expected'] == 153 and results['stats']['unexpected'] == 0
assert results['stats']['skipped'] == 0 and results['stats']['flaky'] == 0 and not results['errors']
audit = json.loads((B / 'ctrl/G3-PRESERVATION-after-full153-v1.json').read_bytes())
assert all(not x['drift'] for x in audit['groups'].values())
assert not audit['backend410Drift'] and not audit['oldQAUnexpectedDrift']
assert audit['nextEnvOriginalExact']
evidence = {n:sha(B/n) for n in independent + [
    'CANDIDATE-G3-r2-qa5.json','ctrl/g3-e2e-full-r2-qa5-node24-second-command.json',
    'e2e-g3-r2-qa5-node24-second/results.json','ctrl/G3-PRESERVATION-after-full153-v1.json',
    'v00/BROWSER-RESULT-r2-qa5.md','ctrl/G3-API-UNCHANGED-BINDING-v1.json',
    'ctrl/G3-TECH-SOURCE-BINDING-before153-v1.json']}
record = dict(task='G3-CLOSE-v1', at=at, result='G3_CLOSED_TECHNICAL',
    candidate='CANDIDATE-G3-r2-qa5.json', evidence=evidence,
    fixedIssues=['B5F-R01 / G3-R01','B5F-R02 / G3-R02'],
    executed=dict(check='121 files / 1281 unit / type / lint0 / build', originalRequired=2,
                  independentUnit=15, independentBoundary=8, priorRegression=27,
                  realBrowser=14, originalFullE2E=153),
    originalRequiredFilteredNotRun=4, originalFullE2ESingleRun=True,
    originalFullE2EPID=receipt['pid'], originalFullE2EElapsedMs=receipt['elapsedMs'],
    backend='prior same-source 410 exact; 1918 pass + 1 existing heavy skip and 42 independent; not rerun',
    chat14='not_run_this_batch: no shared shell/navigation/chat changes; prior same-source evidence',
    retained=['all first failures','CV01-03','cross-batch R-14','RAG-REL',
              'ERR_NO_BUFFER_SPACE environment observation','OBS-LP-MODE-LABEL'],
    oldRejectedExtraHTTP='not_run_no_retry', B6='authorized limited remainder may start only after this closure',
    quality='live_run awaiting explicit inputs; teacher_review_pending; original B7 not closed',
    gitWrites=False)
(B/'G3-CLOSE-v1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(B/'G3-CLOSE-v1.md').write_text('''# G3 技术关闭 v1

ROOT 在独立签核和完整门禁后关闭 G3-R01/R02（B5F-R01/R02）。不重开原 G2/B5 编号。

| 项目 | 结果与来源 |
| --- | --- |
| 修复 | useServerPersistence、DocumentsPanel、SourcePanel 三个既有产品文件；三个新增行为测试。明确放弃撤销全部旧会话写入口和迟到来源；历史复制冻结本地输入与操作身份，正常复制仍可 Undo/Redo/另存 |
| check | 新单轮121文件1281单测、类型、lint0、生产build通过；构建 q84e_pxQoZ2_nwnws9QiI，实际proxy8001，next-env原字节恢复 |
| 独立正确行为 | 原两失败→2通过（另4条过滤未执行）；独立15、第三人8、既有27分别新单轮通过 |
| 真实浏览器 | 14/14；真实FastAPI、延迟Next路由与历史GET、全部11字段/恢复键/后台固定JSON；14完整trace、16全JSON、21实际PNG及四视口/键盘/reduced-motion已独立核查 |
| 完整适用E2E | 原24spec 153/153，第二轮全新单轮，0skip/retry/flaky；PID26492/394353.994ms。首轮152/1静态块ERR_NO_BUFFER_SPACE与诊断1分别保留，未拼绿；不证明恒绿 |
| 后端 | 410文件逐字节与旧成功运行相同；精确引用原1918pass+1重型skip及独立42；本批未重跑全API，新业务浏览器另计 |
| 聊天14 | 本批未执行；全最终diff没有公共壳/navigation-guard/chat变更，旧同源门禁绑定。原153含基本聊天场景，不冒称替代14专项 |
| 保全 | 941源码/3136执行QA/33契约/2161构建零漂移；旧9196仅当前QA索引已登记追加，其余零漂移；main@6cb6a40与next-env原字节保持 |

[独立边界签核](boundary/G3-CLOSE-AUDIT-v1.md)、[独立V00签核](v00/G3-FINAL-V00-v1.md)、[完整关闭收据及SHA](G3-CLOSE-v1.json)、[原首败](ROOT-FIRST-FAILURES.md)。

CV01～03、书籍跨批R-14、RAG-REL、静态资源环境观察与既有Outline本地模式措辞观察继续保留。旧被拒额外HTTP身份复核未执行且未重试。G3关闭只允许进入用户限定B6剩余集成和质量准备，不代表真实AI/教师教学质量、Word/WPS人工排版、正式Qdrant、迁移或原B7通过。
''',encoding='utf-8')
text = f'''{at}：**G3-R01/R02已修复并独立技术关闭**。新check1281/type/lint0/build、原2/独立15/第三人8/既有27/真实14及原完整153均通过；153为新全轮0skip/retry/flaky，首轮环境失败另存未拼绿。941/3136/33/2161及旧QA/后台同源/next-env/main6cb完成后验。限定B6现在进入“剩余矩阵→三路集成/质量准备/导出材料”；真实模型待明确输入、教师评价待验、原B7未关闭。详见[本批G3关闭](qa/TEACHING-LOOP-G3-B6-20261004/G3-CLOSE-v1.md)。'''
paths = ['docs/CURRENT_STATUS.md','docs/NEXT_SESSION_START.md',
         'docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md']
changes=[]
snap=B/'ctrl/G3-CLOSE-DOC-before-v1'
for name in paths:
    p=ROOT/name; before=p.read_bytes(); stored=snap/name; stored.parent.mkdir(parents=True,exist_ok=True); stored.write_bytes(before)
    localtext=text if 'design/' not in name else text.replace('(qa/', '(../../qa/')
    addition=('\n<!-- G3-CHECKPOINT:20261004-CLOSED -->\n'+localtext+'\n<!-- /G3-CHECKPOINT:20261004-CLOSED -->\n\n').encode()
    pos=before.find(b'\n')+1
    after=before[:pos]+addition+before[pos:]
    assert after[:pos]+after[pos+len(addition):] == before
    if name == 'docs/CURRENT_STATUS.md':
        start = after.index(b'<a id="current-task"></a>') + len(b'<a id="current-task"></a>')
        end = after.index(b'### 1.1', start)
        live = f'''\n\n## 1. 当前任务与下一动作

{at}：G3 已独立技术关闭，详见 [G3 关闭矩阵](qa/TEACHING-LOOP-G3-B6-20261004/G3-CLOSE-v1.md)。新完整 check、原正确行为和独立异步核查、真实14及原完整153通过，全部保全后验完成。首败与环境观察保持，不拼绿或宣称恒绿。

下一动作仅为本次授权 B6：先写需求→现行实现→旧证据→剩余矩阵，再并行完成最小真实教学链、至少12匿名质量案例/手写oracle/评分与反馈、四类当前固定DOCX/打印/PDF和试用材料。真实模型缺明确profile/model/数量/预算，live_run待输入；教师评价teacher_review_pending；原B7未关闭。ROOT继续持有隔离前端21544及后续本批样本资源，main@6cb6a40/共享改动保留，不提交/推送/部署，不重试旧额外HTTP身份拒绝。

'''.encode('utf-8')
        after = after[:start] + live + after[end:]
    p.write_bytes(after)
    changes.append(dict(path=name,beforeSHA=hashlib.sha256(before).hexdigest(),afterSHA=sha(p),
                        insertionOnly=name != 'docs/CURRENT_STATUS.md',
                        currentLiveSectionRefreshed=name == 'docs/CURRENT_STATUS.md',
                        beforeSnapshot=stored.relative_to(ROOT).as_posix()))
(B/'ctrl/G3-CLOSE-DOC-delta-v1.json').write_text(json.dumps(dict(at=at,changes=changes),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(B/'README.md').write_text('''# TEACHING-LOOP G3→限定B6，2026-10-04

G3已独立技术关闭：[关闭矩阵](G3-CLOSE-v1.md)、[关闭收据](G3-CLOSE-v1.json)。限定B6进入剩余矩阵与三路实施，原B7未关闭。唯一进度入口为[CURRENT_STATUS](../../CURRENT_STATUS.md)。

[开工保全](BASELINE-v1.json)、[归因](OPENING-ATTRIBUTION-v1.json)、[任务卡](TASK-CARDS-v1.md)、[首败](ROOT-FIRST-FAILURES.md)。旧r8和历史QA保持；技术/准备/人工待验分列，被拒额外HTTP未重试。
''',encoding='utf-8')
print(json.dumps(dict(at=at,result='G3_CLOSED_TECHNICAL',evidenceCount=len(evidence),documentChanges=changes),ensure_ascii=False))
