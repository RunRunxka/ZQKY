# B4 独立反例台账

独立执行期间实现源码停写，旧首轮和失败样本保留。已复现不等于已修复；修复后另冻候选，原正确行为断言重新执行。

| ID | 事实与影响 | 状态/证据 |
| --- | --- | --- |
| B4-R01 | 审核练习与转换卷保存完整题号16(2)，实际T30→T60→T70返回Evidence.itemPath为16/16(2)。T60沿用文件卷父号拼接，使练习完整题号重复套前缀，违反v1.3来源一致口径。 | 已修复独立关闭，r2原64和最新r10原64正确行为通过；首轮11pass/1fail/50未执行、14172ms原件保留。 |
| B4-R02 | 审核practice父analysisRun/subject能真实COMMIT重归属；初始english practice可引用math ready报告。owner/id则原FK于COMMIT拒绝，不归为原产品反例。 | 提交级诊断3失败保留；v1.4修复，r2及最新r10独立完整64通过，已关闭。 |
| B4-R03 | conversion错practice来源或错owner可真实COMMIT，完整FK检查仍0。 | 提交级诊断2失败保留；v1.4修复，独立真实COMMIT边界已正确拒绝，r2/最新r10通过，已关闭。 |
| B4-R04 | 同一practice/paper合法源叶A可真实COMMIT映射到卷叶B，原复合FK无法识别同卷错叶。 | 提交级诊断1失败保留；v1.4修复，独立同卷错叶COMMIT拒绝，最新P64及第五实际映射通过，已关闭。 |

commit-diagnostic：单轮57通过/7失败、exit1、62386ms，完整64项实际执行。4个明确夹具与提前终判已修正另冻，整ZIP相同SHA alias、实际名单模板、归档后成功原包及恢复后真实HTTP现在通过；原11失败诊断日志保持。R01同轮再次失败，v1.4已按固定来源分支修复，所有4组仍须独立新候选通过才关闭。

r2 fixed-first独立64/64通过、68555ms，R01～R04修复正确行为均已通过，原失败不覆盖。另有B4-R05由最终check发现：内部ReviewSession漏接returnPracticeSetId，typecheck退出2；root已补prop并新增2实际确认导航验证，待新候选check及实际浏览器补题返回链验收，不因前端专属18通过而忽略该集成缺陷。

R05现已关闭：r5与最终r13完整typecheck/check通过，第五真实补题→人工编辑/审核/确认→实际返回同练习链通过。R06是原名单转班组件断言早于ready effect通知的QA等待问题，原11 matcher不改仅等待正向notice；最终完整unit1105通过。R07是种子缺paper_source_blocks图片授权上下文，补27完整来源块/真实GET200不放宽产品；R08只增精确导航await，原同步match/115 matcher保留。第二轮首败后的单次导入GET500保留观察，原样克隆标准mainGET200、后续第三/第四/第五两次实际导入GET均200，根因未定，不宣称恒无间歇。

QA准备问题另记根首败：A first对404可选details过严；仅改共同信封必填，不改独立literal与业务字段定位。P后续CollectAll只用于同源完整诊断，不算修复验收或隐藏首败。

R09 已独立修复：标准 main 题库 owner=local-user，练习教学 owner=local；旧练习固定题筛选误用教学 owner，真实人工确认题不进入建议/保存。独立真实上传→校对→审核→确认首轮4例中1通过/3失败，90 HTTP；修复仅注入实际题库 owner 并保持固定 reader 严格归属，原四例再跑4通过/4320ms、91 HTTP。旧题 owner、教学 owner 与历史快照不改。

R10 已独立修复：外归属正式题 get/patch/delete 原先可200/200/204，实际 revision/content/status 被改变，独立原两例均失败。三个公开服务入口补严格 owner 检查后，原两例2通过/2989ms、46 HTTP，foreign404且数据库原样。固定 reader 没有放宽。作者新增三条真实 HTTP 边界回归；r9全量 API1698通过/1规模门控skip，exit0。

原 P64 在 owner 装配修复后首轮0通过/1失败/63未执行：唯一通用 Scene.question 仍插 local，正式 main 只读 local-user，属于夹具归属错误。只改该表达式取真实服务 owner，原135测试断言/23 helper断言/23测试定义均保留，r10完整64通过/81904ms；新16表/7资产四库备份恢复及恢复后真实HTTP通过。不能把首败删去或拼成另一单轮计数。

R11 独立修前两例均失败：新 queued 报告任务成功并已呈现事实，历史仍“尚未准备”；切源/切 run 后旧事件已正确 Abort/过滤，手动刷新新报告事实后历史仍旧。真实 hooks +受控服务组件 QA，不冒充实际 API/browser。首轮2失败/0通过、Node exit1/3629.593ms，日志/JSON及诊断候选原字节保留。CTRL 已修复 terminal/manual刷新同时更新当前历史；修后独立新轮与构建后真实完整browser待验。

R12 真实手机补屏反例：选中辅助字灰110与蓝37,99,235对比度1.013659399，辅助信息只67.046875px宽挤右栏。mobile-visual-first单轮 exit1、8截图、零业务写请求、无横向溢出，截图均实际查看。CTRL 已作用域修复整行列表按钮及继承选中字色；修后真实颜色与三视口人工画面待验，不能沿用旧截图关闭。

R11/R12现已独立关闭：r13原2场景/21 expect新单轮2通过/1653.261ms，pre/post878/43/5零漂移；第五真实browser完整1通过/24647ms、原118 matcher未改，两处实际历史已准备均通过。CTRL手机同测量脚本新轮exit0/2085.439ms、8补屏、白字蓝底contrast5.168555560、整行310px/18px，逐张原图人工可读确认，原67px窄栏反例未覆盖。新build2007文件和完整check1105已验；r12 lint1warning首败保留，r13仅显式解构stable reload去警告。

B4-R13（区别跨批真实模型预算R-13）：原全量24spec/153case单轮152通过/1失败，第117例人工修改、校对与确认HTTP200后返回题库，library aria-selected=false；trace最终actual location.href `/question-bank#library#library`。原E2E不改，首败105 ZIP条目CRC/SHA与截图/API日志保留。产品只有挂载时严格hash匹配，缺显式query意图及已挂载库generation同步；新受限query方案先独立两例红测，修复与新构建全门禁未完成前保持待修复。三spec新API根/进程/日志已真实关闭，用户5174保留。

R13组件正确行为已复验：r17 original2单轮2pass/1382.246ms（2定义/21expect不改），pre/post878/45/5无漂移。新查询优先、legacy精确#library/#generation兼容、同实例实际补题与编码返回/手动tabs通过；作者相关74pass。第六新构建真实browser随后完整通过，最新原E2E题库两例全部通过；原153整体因独立书籍R-14失败，不能把导航修复等同B4门禁全过。

## 2026-10-03 暂停时收口

B4-R13导航缺陷已按r17原独立两例、第六实际完整链、最新原E2E题库两例关闭。最新原24spec/153case整体仍为152通过/1失败/0skip/0flaky/0retry、exit1/497986.093ms，不能与旧152/1拼一次全绿。

剩余失败属于跨批R-14书籍第二标签场景：原267行strip等待120000ms仍1，B最终DOM真实显示「生成已中断（无执行器在跑）」与「继续生成」。书A完成及完成前两笔记保存通过；具体触发/lease/write-lock因果未证实，实际恢复及原后续最终笔记/双ID/无锁断言均未执行。六关键book源和原spec r1→r17逐字同，但源码未改不能替代实际正确行为验证。[独立只读调查](b4-v00-browser/R14-STATIC-FIRST-FAILURE.md)的受控显式继续方案仅待评估，未实施，不豁免、不关闭R-14。

用户明确要求现在暂停；原14聊天未执行，临时stream已优雅关闭。暂停后只整理证据/资源/文档，无测试、产品或可执行QA修改。恢复后先另声明R-14范围与独立验证，再完成必要门禁；当前B4未关闭。
