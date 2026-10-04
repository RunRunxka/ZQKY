# B3-FIX r7 前端独立审查

负责人 `/root/b3fix_frontend_review`，2026-10-02。审查对象是 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec` 上未提交的 B3-FIX r7 候选。产品与原 B2/B3/B3-FIX 证据只读；新增配置、探针、缓存和日志均在本目录。**发现 3 项可由正常界面操作触发的 P2 问题。** 不把尚未开始的 B4 能力或主观视觉选择记为缺陷。

## 发现

### F-REVIEW-01 / P2：进入承认后新校对仍可确认旧成绩

- 位置：`apps/web/src/features/assessments/ScoreImportReview.tsx:557–563`，实际提交守卫 `:153–167` 与 `:632`。
- 触发：批次已校对、原格 C2 为 2 → 点击“进入预览承认” → 再在原表行校对中输入 1 → 点击“确认入库”及弹窗确认。
- 实际：单格徽章显示 1，且显示“有未保存的校对”，但两个确认按钮仍启用；发出的 POST 只有旧 `expectedImportRevision=1`、`previewVersion=1` 和承认包，不包含未保存的 1。探针拿到“已确认入库”回执。服务端按持久化旧矩阵确认是正常行为，缺口在前端确认闸门。
- 原因：只在进入承认的按钮检查 `drafts.dirty`；留在 acknowledge 阶段继续编辑不会退出承认/使承认失效，打开确认与 `buildConfirmPayload` 均未重检 dirty。
- 正确行为：存在未保存校对时不能发确认；编辑后重新完成保存、权威预览和承认。覆盖“承认后编辑”及“弹窗打开后产生编辑”的守卫，不能只禁首次进入按钮。
- 证据：`score-edit-boundaries.test.tsx` 的 F-REVIEW-01；`score-edit-probes-3.log` 的 receipt 显示 `visibleCorrection=1`、`persistedSource=2`、实际确认包旧 r1/preview1，期望零确认请求的断言实际为 1。

### F-REVIEW-02 / P2：映射保存成功擦掉请求开始后的新输入

- 位置：`apps/web/src/features/assessments/ScorePanel.tsx:279–281`（总分映射输入 `:545–549`）。
- 触发：映射总分列 E→F → 点击“保存映射并重算” → 请求仍在途时把输入改为 G → 先前 F 请求返回 200。
- 实际：在途时输入仍启用；用户已看到 G，迟到成功却执行 `mappingDirty.current=false` 和 `setMappingDraft(mappingFromView(next))`，输入退回 F，并显示已保存映射。G 从未进入 PATCH，且本地未保存标记被清除。
- 正确行为：在途锁定映射输入，或绑定保存时的编辑代次并仅清除属于该次请求的编辑；较新的输入须保留为 dirty。两种方案均需保持失败时编辑保留。
- 证据：F-REVIEW-02 实际 PATCH `totalColumn=F`，响应后 `actualInput=F`，期望新输入 G 的断言失败。

### F-REVIEW-03 / P2：名单补充后已访问的施测面板继续用旧名单

- 位置：`apps/web/src/features/assessments/AssessmentsPanel.tsx:92–98`；名单变更只刷新局部资源 `RosterPanel.tsx:363–368`。`AssessmentsWorkspace.tsx:129–139` 保持已访问施测面板挂载，而名单步骤未通知全局名单版本。
- 触发：选择班级 → 先进入“施测”（甲的勾选框） → 回“名单”添加乙，POST 成功且名单页出现乙 → 再回“施测”。
- 实际：施测可选名单仍只有甲。学生资源 key 只含 classId，步骤 hidden/unhidden 不重载；名单新增/导入的 onChanged 只刷新 RosterPanel 自己。施测没有单独刷新参测名单的入口。需要切换班级/原卷导致重挂载或重开页面才能纳入乙。
- 正确行为：名单新增/导入/转班通知到工作区，已有施测学生资源按明确名单版本或返回步骤时刷新，同时保留仍有效学生的勾选/出勤/人次草稿。
- 证据：F-REVIEW-03 使用真实 `AssessmentsWorkspace`、`RosterPanel`、`AssessmentsPanel`，只替换 fetch 边界。receipt：`currentRosterNames=[原名单甲,新名单乙]`，成功 POST 带 `classId=probe-class`，名单页先显示乙，回施测的 `assessmentChoices=[参测 原名单甲]`；期望乙勾选框断言为 null。

## 覆盖与实跑

- 读取根/web AGENTS、CURRENT_STATUS、PROJECT_GUIDE、本批 REPORT 和旧 V00-FRONTEND-REPORT；查看所有本批新增/修改的施测、成绩、名单、原卷、出勤、补考、历史组件，公共任务 hook、题库审核/确认/富内容相关实现及服务契约。
- 原 B3-R01：queued 首次 `[N,N+1]`、公共取消/重试及观察代次；相关新 hook、题库 jobs/Generation/ReviewWorkspace 原测试本次通过。
- 原 B3-R02：服务端 requiredAcknowledgements 为有效全矩阵权威；原表缺考加其余空格、0/missing/exempt 区分、旧字段缺失禁确认的原测试本次通过。
- 原 B3-R04：前端发送 headerRow 映射 PATCH，成功后重新读取批次 revision，引发同批次行资源按 revision 重载。映射修正与 CAS/422 原测试本次通过；后端真实提行语义由后端审查负责，本审查没有用 fetch 替身声明实际 XLSX/CSV 解析通过。
- 原 B3-R08：卸载、class/paper 变化、同班同卷改选施测的迟到创建不改父级选择，原测试本次通过。
- 富内容检查：共享 renderer 的受管图片代次/object URL 清理、OMML 白名单/原文 fallback、合并表格、外链图片/HTML 限制、Markdown 显式 null 转换和题库原包重试；相关原测试本次通过。没有新增可确认的富内容或任务观察缺陷。

实际命令均带 `NODE_OPTIONS=--no-experimental-webstorage`：

```powershell
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/frontend/vitest.config.ts --reporter=verbose
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/frontend/vitest-regression.config.ts --reporter=verbose
```

| 执行 | 结果 | 证据 |
| --- | --- | --- |
| 首次新边界 2 项 | 2 failed，exit 1，942ms | `score-edit-probes.log` |
| 补上工作区返回名单场景后的 3 项完整执行 | 3 failed，exit 1，1.26s；全部到达产品正确行为断言，无夹具错误 | `score-edit-probes-3.log` |
| 相关既有测试（15 文件） | 195 passed，exit 0，22.64s | `regression.log` |

新反例与既有通过测试覆盖不同场景；前一轮两项探针与最终三项不相加为执行数。fetch 替身记录是前端交互/请求证据，不是实际业务数据库持久化证据。

## 未执行与边界

未执行 build、typecheck/lint、全量 check/API/e2e、真实服务浏览器、人工三视口/键盘/减少动画、真实模型/Word/WPS/Qdrant/正式迁移。此次只读审查禁止重建和占端口，窄组件探针足以验证上述前端状态/请求问题；布局与真实业务验收没有扩大声明。未读写正式浏览器草稿/凭证、未修改产品/旧证据、未提交/推送/部署、未删除数据。
