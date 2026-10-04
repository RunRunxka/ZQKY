# 总控首败与修正记录

首次失败证据保留，不以末轮绿覆盖。工程环境与集成失败在此登记，原始日志见本目录 logs、browser-first 与各实现者结果卡。

- `npm.cmd run typecheck` 首轮：exit 2，`.next/dev/types/routes.d.ts:57` 生成文件出现尾部残片 `ort type ParamsOf`；确认5173无监听后，只从本轮有效`.next/types`复制routes/root-params生成文件到忽略的dev缓存。未改产品源码；用户原有next-env内容将在全部构建后逐字节恢复。
- 再跑类型：exit 2，`RosterImportPanel.tsx:298` result nullable；实现者按明确result空值收敛修正。随后exit 2仅名单新增测试的`getByRole`选项`exact`非法，改为字符串name的默认精确匹配，没有放宽断言。
- 在`apps/web`执行`npx vitest run src/features/question-bank/QuestionPreview.rich.test.tsx`：exit 1，根vitest配置include为`apps/web/src/**`而此filter无匹配。回根目录正确路径重跑2/2通过，见root-rich-question-r1.txt；不算产品缺陷。
- 新增原始OMML视觉渲染首轮typecheck：exit 2，React类型无`JSX.IntrinsicElements.math`；使用`createElement('math',...)`保留原MathML输出，未回退为纯文本。root-typecheck-r2/r3保留失败与修正结果。
- rich renderer首轮jsdom没有object URL API（6过1败），以明确create/revoke替身核真实资源释放行为，后续7/7通过，见root-shared-first/r1；OMML渲染新增边界回归4/4通过。
- 出勤首轮fixture第二场景复用学生号0001触发真实唯一约束；改fixture第二学生0002，不改业务闸门。迁移故障回归首轮复用既有pt2、二轮registry列名错，分别改fixture为pt3和id；全部五阶段回滚/重跑通过。首败和修正日志原样保留。
- 首轮真实浏览器6例：1过、3败、2因serial组首败未运行，exit 1（root-browser-chain-first.txt，完整原始test-results复制到browser-first）。成绩“工作表名”等查询与新增名单字段发生子串重名，改准确标签；补题下拉框label包裹所有option，exact label查询不匹配，改面板内准确combobox名称。Provider调用数为0，未发生模型业务失败。诊断期间zip尚在写入不能被zipfile打开，最终以真实首败结果保全，不把当时不完整trace误判为产品错误。
- 整合check第二轮：107文件通过、1文件失败；1061例通过、1例失败（jobs.test首次interrupted终态）。回调已同步执行，Harness外部控制器要等React提交后的useEffect，原测试仅等待callback立即读取view发生时序竞争。改为同一waitFor等待callback恰好一次及完整终态字段，所有断言保留，未改产品。独立前端验收者源码核对同意原因；25/25窄复验通过，重新冻结r2并全量重跑。日志root-check-final.txt/root-jobs-render-sync.txt。
- 浏览器r2：3过2败1因serial未运行（root-browser-chain-r2.txt及完整browser-r2）。新真实名单链误把既有名单dataNo当表格物理行；T30-a既有dataNo不含表头，修fixture选择1–4，成绩物理坐标2–5仍原断言。生成已成功、Provider1，review题干label含textarea文本造成exact查询失败，改准确textbox题干角色；实际公共retry已通过，Provider明确失败/重试共2次，attempt1→queued1→success2。
- V00发现并保全：极端Decimal四例HTTP500/错误舍入；成绩PATCH过期及预计算后漂移2例；重复物理行静默丢弃1例；F20三确认unknown后偷换包3例；题库unknown同ID换草稿修订及假称零入库2例；正式题关联发布锁空隙1例；过期心跳复活1例；知识点首次queued0观察误判1例。独立首次日志/HTTP JSON在各V00目录，修复后须最新冻结复验，源码已修改不算验收。
- root-review-boundaries-r3首轮74例中最后排队心跳失败：既有测试一次假时钟跳91s超过3s lease后仍期望heartbeat复活，与独立过期零写规则冲突。改为10次×2秒各自在到期前真实等心跳，保留20>3、JOB_BUSY、并发1、任务成功、active0全部原断言；另增已过期心跳不修改/旧批零写。独立G0验收者核对调整合理。最终边界窄测74例全过。
- root-question-freeze-r3：新增unknown回读测试修订r5有3处展示，改限定确认region；既有ignore409 switch间歇丢失新草稿编辑，DraftEditor改同步dirty/touched ref保护延后effect，独立前端额外复核。首轮56过2败日志原样保留，最终窄复验另记。
- r3完整后端1523场景：1517过6败、5warnings、exit1、208.09秒，root-api-final-r3.txt及root-api-final.xml保留。3个备份CLI失败为PYTHONIOENCODING=utf8但Windows父进程text默认GBK解码，导致reader UnicodeDecodeError/stderr None；增加PYTHONUTF8=1后完整备份23例实跑通过，业务拒绝/零写全部原断言。另有旧成绩测试仍使用PATCH隐式刷新、本轮双任务假时钟只等一方心跳造成另一方失效、已知R19 jieba冷加载317ms消耗50ms TTL。针对性r3复验24过1败（R19，冷启动明确证据）；没有修改产品来绕过失败。
- r4三个Python测试调整由独立G0/SCORE验收者只读审口径：成绩旧confirm/validPATCH必须409零修改→三版本POSTrefresh→原人次人工消歧→新人missing3/原200,300,500；两任务每轮同时running/attempt1/expiry严格前进并>任务钟再推进2s，仍20秒等待/不可接管/并发1/收尾；R19仅替换service模块time绑定为独立monotonic钟，50ms TTL不增，真实检索/asyncio继续，显式推进70ms后保留容量/过期/retired/重启断言。候选r4无产品改动，首败不覆盖。

- r4浏览器3过2败1未跑：原卷磁盘File在测试postDataBuffer快照里丢字节，真实服务正确拒绝空文件；题库测试把改内容与reviewed同包提交，被既有正确needs_review守卫回退。原样browser-r4；独立前端源码复核catalog与现存正确行为测试。修spec先保存再审核，并在8001真实Next代理上传完整字节。首败trace两处封尾不完整，不冒称trace可读。
- r5启动轮代理旧构建仍固定8000（ECONNREFUSED），总控停止运行，首败browser-r5-startup与logs保全；没有成功读取正式后端。Next rewrite在build阶段固化，设8001重新build并核routes-manifest后重跑。r5隔离轮4过1败1未跑：真实确认响应丢失原包重放已成功，测试却要求fresh文案“已确认入库”；改为严格验证“已确认（重放）/本次未重复写入”，原deepEqual包/ID/revision仍保留。
- r6完整业务链与成绩修正、v1旧JSON/矩阵不变已通过，390外层宽度失败；首败browser-r6。独立诊断单跑1440/1920无溢出、390 scrollWidth413，截图后仍超宽；browser-layout-first实际图片定位修正人次native select含长classId撑开field/form。矩阵内部表715px正确被容器裁剪，非根因。root仅模块field/select约束min/max-width，无页面overflow隐藏。r7全check1069及真实浏览器6项全过，三视口root宽度1440/1920/390精确相等；初败测量、图片与正确回归都保留。
