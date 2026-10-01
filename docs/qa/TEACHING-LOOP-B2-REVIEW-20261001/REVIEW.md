# B2 代码审查与 B3 前置修复建议

日期：2026-10-01。审查对象：`main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906` 上的 B2 未提交工作区，B2 r2 冻结清单 **84/84 一致，0 差异**。

## 结论

新增 **11 项可复现缺陷：3 项 P1、8 项 P2**。建议 B3 先执行修复与独立复验，再启动成绩业务。当前真实原卷、名单、施测和题库提供了有效基础；新发现说明部分失败、配置变更和竞态路径尚未被原验收覆盖。

本次没有修改产品代码、已登记迁移、B2 冻结记录或权威进度文档。新增内容仅为本审查目录和 B3 提示词。以下 `B2-RVxx` 是本次审查编号，执行方应在开工时登记进现行任务卡；本文件不是第二套进度入口。

现有 B2 定向后端测试 **126 项通过、退出码 0**，与新增探针复现缺陷并不矛盾。未重跑全量 check、全量 API、E2E；本次未做真实模型、Word/WPS、Qdrant或人工视觉验收。原交付报告中的全量结果仅作为历史记录引用。

## 新发现

### B2-RV01 · P1 · 公共重试没有调度执行器

位置：[workflow_jobs.py:82](H:/备份xuexi/智启课源/apps/api/app/api/v1/workflow_jobs.py:82)。

`POST /workflow-jobs/{id}/retry` 只执行 `store.retry()`，把任务置为 `queued`。既没有按 `domain/kind` 调度执行器，也没有后台队列消费者；知识点和题库页面调用后只轮询。

真实装配探针：失败的 `question:generate` 经重试返回 `200 queued`，连续 20 轮查询仍为 `queued`，`attempt=1`，provider 调用数 `1→1`。用户点击重试无法再次执行。

修复：统一注册已实现的域/类型执行器，公共重试原子入队后由唯一调度路径执行；保留冻结输入，防重复执行，处理入队后调度异常及进程重启。真实后端测试覆盖失败→重试→新 attempt→终态，不能只 mock 出 succeeded。

### B2-RV02 · P1 · 任意处置 JSON 和空题面可以通过原卷确认

位置：[service.py:1308](H:/备份xuexi/智启课源/apps/api/app/services/papers/service.py:1308)。

问题处置只要求 `resolution` truthy，不校验补录类型、有效内容或资产引用。探针导入“依赖右图求阴影面积”的题目，未知图形产生 blocking `UNSUPPORTED_OBJECT`；提交 `resolved + {"anything":1}`，没有补录图形，题目内容前后完全相同，仍可确认。另一探针把计分题 `content` 改为 `{}`，保留块归属和知识点后，也确认成功，reader 返回空题面。

修复：建立结构化问题处置契约，补录必须关联实际有效内容/受管资产；排除须有明确理由且符合内容损失规则。确认时验证计分题拥有有效题面及必要共同材料。不能要求答案、解析或评分点才能确认，也不能把“字段非空”当成等价内容已补齐。

### B2-RV03 · P1 · 未归属原文块接口丢失正文

位置：[papers.py:171](H:/备份xuexi/智启课源/apps/api/app/contracts/papers.py:171)、[service.py:1070](H:/备份xuexi/智启课源/apps/api/app/services/papers/service.py:1070)。

`PaperSourceBlockView` 只有 ID、类型、定位和归属，没有持久化的 `block_json`。没有识别出题号的 DOCX 返回 `items=[]`，所有原文块响应均无正文；数据库确有文本。F20 无法通过现有内容 API 显示未归属段落、表格、图片，并让教师手动建题。

修复：双侧契约返回完整可渲染块，补齐受管资产的受控访问；验证无题号文档、孤立未归属块、公式、合并表格和共同材料。不能为了前端展示重新复制一套解析业务或开放任意文件路径读取。

### B2-RV04 · P2 · 执行模型漂移，来源仍记录冻结旧指纹

位置：[proposals.py:430](H:/备份xuexi/智启课源/apps/api/app/services/papers/proposals.py:430)、[generation.py:614](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/generation.py:614)、[service.py:879](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:879)。

原卷建议、题库生成和整理恢复按 profile ID 重新解析当前配置，但不比对已冻结 fingerprint。原卷及补题探针均确认：任务创建后同 profile 改模型，实际调用新模型，任务仍成功且记录旧指纹。补题探针在模型名额排队期间将 `model-A→model-B`，来源指纹仍为 A。

修复：调用前核对真正用于本次调用的非敏感配置指纹，漂移则明确失败，要求新任务；或者真正解析冻结配置。执行和来源记录必须一致，不携带凭证快照、不默默回退。公共实现同时覆盖其他已实现模型任务。

### B2-RV05 · P2 · 整理器中间批提交不校验租约

位置：[catalog.py:1531](H:/备份xuexi/智启课源/apps/api/app/repositories/question_bank/catalog.py:1531)、[service.py:973](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:973)。

`record_organize_batch()` 不接收 token/attempt，不要求任务 running，只检查取消标志。探针中旧 attempt=1 租约过期、新 claim=2 后，旧批次仍能写入建议并推进新 attempt 的 checkpoint；任务收敛为 interrupted 后，迟到批次也能写入。

修复：中间批建议与 checkpoint 提交也要在同一事务验证当前有效 lease、attempt、状态及取消标志；旧 attempt、失权及终态零写入。终态 `store.complete()` 的 CAS 不能保护此前已提交的批次。

### B2-RV06 · P2 · 原卷和题库确认不复核已归档知识点

位置：[papers/service.py:655](H:/备份xuexi/智启课源/apps/api/app/services/papers/service.py:655)、[question_bank/service.py:1315](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:1315)。

草稿绑定时核验 active，但确认时没有进入统一发布协调器重新核验。两个域均复现“草稿绑定活跃知识点→归档→确认仍成功”，发布了新的已确认关联。这与保留已发布历史关联不同。

修复：确认及适用关联发布在同一个 `PublicationCoordinator` 内读取知识点状态、修订和学科，然后执行域内短事务。不要释放协调锁后才写新引用。保留已确认的历史引用，不自动替换历史修订。

### B2-RV07 · P2 · 改题学科时继承旧关联产生跨学科题

位置：[service.py:1397](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:1397)、[catalog.py:1031](H:/备份xuexi/智启课源/apps/api/app/repositories/question_bank/catalog.py:1031)；草稿同类入口：[service.py:545](H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:545)。

仅显式提供 `knowledgeLinks` 时核验新学科；省略时无条件复制旧关联。正常 HTTP 探针把有数学知识点的正式题改为 `subjectId=chinese`，省略关联字段，返回 200，新修订继续带数学关联。

修复：学科改变时核验有效的完整关联集合；冲突须要求显式替换/清空或拒绝变更。正常同学科改内容仍保留关联，旧修订不变。

### B2-RV08 · P2 · 施测改日期绕过班级归属确认

位置：[service.py:438](H:/备份xuexi/智启课源/apps/api/app/services/assessments/service.py:438)。

`update_assessment()` 校验日期格式后直接写入，没有重核既有参测归属。真实链创建 `joinedOn=2026-09-20`、施测 `heldOn=09-30` 后，PATCH 日期到 `09-01` 返回 200，学生仍 `classConfirmed=false`。

修复：日期变化须对现有参测人次重新核验；需要显式确认的不能通过普通 PATCH 放行。采用定位拒绝或明确重确认流程，保留归属历史和姓名/学号快照。“今日导入名单，分析过去考试”仍应由教师显式确认流程支持。

### B2-RV09 · P2 · StrictMode 中任务 hook 永久忽略更新

位置：[hooks.ts:127](H:/备份xuexi/智启课源/apps/web/src/features/knowledge-points/hooks.ts:127)、[next.config.ts:9](H:/备份xuexi/智启课源/apps/web/next.config.ts:9)。

effect cleanup 设置 `mounted=false`，下一次 setup 不恢复。项目开启 StrictMode，开发模式的 setup→cleanup→setup 后，`apply()` 永久返回。当前 hook 的 React/jsdom 探针：普通模式 adopt(succeeded) 得到 view=succeeded、onTerminal=1；StrictMode 为 view=null、onTerminal=0。

修复：每次 setup 恢复标志，正确清理观察；保留真实 StrictMode 测试。此问题针对开发 StrictMode，不能扩写成所有生产浏览器均失败。

### B2-RV10 · P2 · 迟到的旧重试/取消响应接管新任务

位置：[hooks.ts:199](H:/备份xuexi/智启课源/apps/web/src/features/knowledge-points/hooks.ts:199)，取消同类路径：[hooks.ts:211](H:/备份xuexi/智启课源/apps/web/src/features/knowledge-points/hooks.ts:211)。

操作响应无身份/attempt/观察代次守卫，reset 不使在途请求失效。探针：A failed→延迟 A retry 响应→reset/adopt B→释放 A 响应，视图由 new-B 退回 old-A，新任务观察被旧任务覆盖。UI 允许在旧操作在途时发起新候选。

修复：操作绑定任务身份和观察代次，reset/切换/卸载使旧操作失效，处理 pending 状态；迟到成功和失败均不能污染新任务。

### B2-RV11 · P2 · 新草稿标题改变旧修订的历史展示

位置：[service.py:1037](H:/备份xuexi/智启课源/apps/api/app/services/papers/service.py:1037)、[reader.py:142](H:/备份xuexi/智启课源/apps/api/app/services/papers/reader.py:142)。

固定修订的标题读取可变 `papers.title`。先确认 Original Title，再建立新草稿并改为 NEW DRAFT Title；旧 revisionId 的内容 API 和 reader 标题也随之改变。

修复：增加修订级标题快照，固定修订读取自己的标题；历史回填明确来源与限制，不能声称恢复从未保存的原标题。

## 已披露问题及 B3 准备事项

- 原卷 publish 失败后 running 滞留是 B2 已披露事项，不计入上述 11 项新发现。B3 第 0 阶段应在公共引擎统一处理发布异常：回滚业务写入后按有效租约收敛失败，取消和失权优先，避免只给某个域加特判。
- 现有 `tabular.py` 为知识点/名单返回字符串，使用 data_only、去空行，并限制 64 列；不能直接用它完成成绩输入。B3 应在同一公共模块补充带原始类型、公式/缓存视图和真实行列位置的读取能力；超限明确报错，不静默截断，不改变 B1 已有调用语义。
- `assessments.active_score_revision_id` 目前 CHECK 只能为空。新成绩迁移须恢复复合外键，重建时保留所有参测、范围、索引和触发器。SQLite 的完整表结构变更流程要求事务外设置外键状态，再在事务内创建新表、拷贝、替换和校验；不能把 PRAGMA 塞进现有事务内期待生效，也不能先改名旧表造成子表引用被重写。[SQLite 官方重建流程](https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes)、[foreign_keys 事务限制](https://www.sqlite.org/pragma.html#pragma_foreign_keys)。
- 本机后端运行时 SQLite 版本只读确认：`3.53.1`。新迁移仍应按项目受控流程测试，不能因本机版本较新而取消旧库路径和失败回滚验证。

## 验证与证据

命令、隔离说明和各探针入口见 [EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)。探针写入本审查目录；测试业务数据仅在系统临时目录。所有模型调用均为受控替身，未启动服务或端口。

本审查不追改 V00 r1/r2 的结论；其通过项对应既有验收范围。新增缺陷应产生新的修复候选及复验报告，不通过修改历史报告来关闭。
