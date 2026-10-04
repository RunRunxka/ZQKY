# G3-V00：r2 / QA5 真实浏览器独立签收

2026-10-04，任务卡 `G3-V00-DYNAMIC-r5`。本报告仅签收 ROOT 本次新隔离数据、Node 24、完整14项的一次实际运行；V00没有再次运行测试、访问服务或修改产品/执行QA。G3是否关闭由CTRL汇总全部门禁决定，B6未启动。

## 候选、运行与原件

候选 `../CANDIDATE-G3-r2-qa5.json`，SHA256 `1ef1756283abc1fda103c2263c3a49034c5d3ffec4f06669c0735488134efcbb`，main@`6cb6a40db890390f0261d547213e319040f64785`，构建 `q84e_pxQoZ2_nwnws9QiI`。独立逐文件核941源码、3136执行QA、33共享契约、2161生产构建，均与候选SHA相同；文件数量不作为测试数量。

输入 `../ctrl/g3-browser-r2-qa5-node24-inputs.json`、实际绑定种子 `../ctrl/g3-seeded-r2-qa5-seed-bound.json`（SHA `a390a27f0fce1e48bc6761662691b5b35e76a4cb3d05f6c611a405d498cd5b8b`）一致。种子是 ROOT 管理的新TEMP `zqky-b5-runtime-g3-seeded-r2-qa5-vm0jfh1y/data`，测试环境，真实FastAPI业务；API PID19560、Next PID21544，原始创建/身份以CTRL收据为准。API在运行后由ROOT守卫关闭，TEMP保留。

实际命令：`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe node_modules/@playwright/test/cli.js test --config docs/qa/TEACHING-LOOP-G3-B6-20261004/v00/browser/external.config.ts`。执行器 v24.19.0，`NODE_OPTIONS=--no-experimental-webstorage`，trace on、1 worker、0 retry、无自启服务。

收据 `../ctrl/g3-browser-r2-qa5-node24-command.json`：PID23212、exit0、43797.925ms，child/log均closed、source/QA漂移均空数组、next-env原SHA前后相同。实际日志SHA `d0a218616e58a37025a47f9149e264e8859e45b067fc107039804b8101a8638b` 与收据一致。完整JSON `results/run-g3-r2-qa5-node24/browser-results.json` SHA `2923e847191d94a114c60e9bb05f83c325d304239b679f967c892ed5da5a0ba5`，14 expected、0 unexpected/skip/flaky，全部单次 passed；报告耗时43045.007ms。

## 每例实际判定

| 序号 | 原场景 | 实际 | 行为耗时ms |
| --- | --- | --- | --- |
| 1 | R02 物理键盘双击，仅一个业务读取与完整编辑；Undo恢复 | pass | 2581 |
| 2 | R02 真FastAPI并发v3，拒绝过期历史替换并保输入/intent | pass | 2248 |
| 3 | R02 真GET成功后运输失败，保intent并明确重试 | pass | 690 |
| 4 | R02 公共文档切B，A迟到读取不得覆盖B或其intent | pass | 2556 |
| 5 | R01 390×844 公共导航放弃A，真Next延迟、完整后台不变 | pass | 2747 |
| 6 | R02 390×844 延迟GET中长正文/过程/恢复包/intent，重复制Undo/Redo另存 | pass | 2875 |
| 7 | R01 1024×768 同上 | pass | 2800 |
| 8 | R02 1024×768 同上 | pass | 2915 |
| 9 | R01 1440×900 同上 | pass | 2794 |
| 10 | R02 1440×900 同上 | pass | 2958 |
| 11 | R01 1920×1080 同上 | pass | 2798 |
| 12 | R02 1920×1080 同上 | pass | 2926 |
| 13 | 实际SourcePanel旧报告GET在discard后撤权，不重建缓存或版本 | pass | 4613 |
| 14 | 实际同一保留子树内，新教师报告/KP操作和编辑B可明确保存 | pass | 4903 |

## 完整业务与trace核对

全部14原trace逐个 `ZipFile.testzip()` CRC正常，完整central directory、test.trace/网络/资源均可读取；无test或浏览器trace error，所有After Hooks完成。共16完整JSON附件、21实际PNG从原报告附件提取，保持原bytes/SHA；索引和全部网络正文在 `results/run-g3-r2-qa5-node24/independent-review/artifact-audit.json`。独立深等结果见同目录 `full-json-review.json`，不以截图或标题代替正文判定。

四尺寸R01：真 `/chat` RSC GET200响应保留2056/2093/2068/2098ms；原页面跨900+1050ms仍挂载，三次恢复键读取均null；浏览器PATCH0，完整current/history/fixed在before/during/after逐字段深等，11字段与固定版本不变。实际公共导航点击、明确放弃焦点及Enter均在trace完成。

四尺寸R02：实际后台GET200被保留1616/1640/1645/1637ms，原响应全文等于真实v2；新稿11字段和6720字长正文、process design/secondary完整保留，恢复包正文=新稿、context=null、serverRevision2及固定revisionId均保持。随后明确重复制、Undo/Redo完成，真实浏览器PATCH恰2次且均200：v3完整历史正文，v4完整Undo新稿。原v1/v2固定正文在trace所有7次相关GET均深等不变。8001夹具准备PATCH另计，未伪算浏览器写入。

双击实际读取1次、延迟1555ms、后台完整before=after；真实并发CAS返回v3完整JSON，迟到读取未把v2基线当已确认；运输失败保存intent后实际retry成功；跨文档延迟1726ms，A/B各完整current/history/fixed均保持。

两SourcePanel场景：真实BASE与A ready报告、固定成绩全文前后深等。旧A实际GET200保留1551ms，真实Next目标保留3623/3932ms；discard后可信11字段备份=BASE正文、固定上下文=BASE、显示报告=BASE，恢复键三次null。全部11项来源控件labels/value/checked/disabled在成功discard后捕捉，旧读返回后完整比较通过；教师模型、43分钟和要求与原输入一致，已加载临时生成资格按设计撤销。stale控制PATCH0；新操作控制从同一保留子树重新选A/KP和改题，完整新缓存正文/context准确，浏览器明确PATCH1次200，真v2全文与A固定上下文正确，原固定v1不变。最后真实导航成功提交；没有把该控制宣称为最终导航失败/取消测试。

## 实际逐图检查及边界

V00使用 `view_image` 实际查看全部21PNG，不以路径存在代替看图：四尺寸每组dialog/多周期旧页面/新稿与恢复intent/Undo后v4四张，共16张；另CAS冲突、跨文档B两张与SourcePanel迟到/新操作三张。390×844对话框四个操作均可见、文字和按钮无水平截断，移动编辑流程保持；1024×768保留编辑及预览双区，1440×900和1920×1080三栏状态清楚。长正文及过程B可见，冲突提示/禁止覆盖、后台保存v4与来源新操作v2身份和预览正文对应。Toast及滚动是截图当时真实状态，不把未进入可见区的控件算像素审查通过。

四尺寸R01/R02各有一个成功 `toBeFocused`、实际Enter和 `matchMedia('(prefers-reduced-motion: reduce)').matches=true` 的返回/断言，源场景也有焦点/Enter完成。这里只确认这些操作的键盘与媒体行为；不扩展为全部tab顺序、全站焦点样式/对比度或动效验收。

既有局部文案观察：`apps/web/src/features/lesson-plan/components/OutlinePanel.tsx:139` 硬编码“本地工作模式 / 草稿保存在当前浏览器”，在后台固定v4/v2状态图仍显示。只读核SHA `048c8b8972442f9f76e82739a241549195361ec65b9c4e90bfe6d3c0a1bad868` 与冻结候选一致，该文件不在相对开工的改动清单，未改产品。这是既有泛化模式文案，与实际后台固定身份、保存ACK和完整业务JSON应分开判断；未见由其触发R01/R02保存/撤权错误，作为B6材料/体验观察记录，不据此撤销本轮技术判定。试用材料应以后台固定身份和保存ACK为模式/持久化依据。既有聊天CV01～03、R-14/RAG-REL观察保留，本报告不写全站视觉PASS。

## 首败保留与未执行

原 `run-g3-r2-qa4` 完整14项均unexpected timedOut，原首败不覆写、不转计pass。前13完成业务与附件后统一trace归档45s超时；Node26/24离线同输入SHA诊断分别7008ms挂起/18ms完成，对应原Playwright mergeTraceFiles流式归档。第14另在备份下载后的 `clock.pauseAt` 超时，后续新来源保存原轮not_run。仅该夹具时钟顺序按ROOT卡前移、原bytes/SHA与精确diff分别保留于 `clock-first-source-r4/`、`BROWSER-CLOCK-QA-DELTA-r5.json`。当前完整新14是新TEMP/种子、全部原业务断言、trace on、Node24的单轮结果，没有关闭trace、增加retry、删除场景或拼旧绿色。

本V00未重新执行完整153全站E2E。ROOT原153本次新单轮 `g3-e2e-full-r2-qa5-node24-first` 已实际152pass/1fail、0skip/0retry：PID21988、exit1、388290.997ms，source/QA零漂移。V00独立读该收据和首败日志，唯一 `tests/e2e/knowledge-points.spec.ts:717` 在Enter后 `dialog` 不存在、line726失败，原首败保留并由ROOT/边界另做实际归因；本14项不得替代或拼接该门禁，G3仍不能关闭。完整check/API/聊天各自以ROOT实际结果汇总，本V00没有重新执行。真实付费模型、教师教学质量判断、Word/WPS人工排版、实际PDF保存、正式6333、正式迁移和超范围压力均not_run；属于后续授权/验收边界。本批旧额外HTTP身份复核未重试；本次仅使用合法业务请求trace及ROOT离线build绑定。没有Git提交/推送/部署，没有提前实施B6。
