# V-G7-B 独立验收任务卡 v1（同源双页真实浏览器链，非作者）

- ID/版本：V-G7-B/v1
- 起点：候选已冻结（build `49nH0q5IXMfFQTcg4mpIR`，proxy 8001，next-env 已恢复 `0f7062…`；产品源码停止写入）。**你只读产品；发现缺陷只报告不修复。**
- 可写范围：只写 `docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/browser/`（自有 QA）。旧 QA/产品源码只读。
- 停止点：完成下面链条、写 `v00/browser/V-G7-B-RESULT-v1.md` + JSON/日志收据、按 PID/出生/argv 精确关闭你启动的前端服务后停止。

## 目标

用一个**全新隔离的 Playwright BrowserContext 内的两个 Page**（真实同源 localStorage 共享；两个独立 Context 不作跨页证据）验证 G7 写入闸门：**先在键者结果未知时，后到者不得覆盖其恢复包、不得发送 HTTP；foreign 显式结束/清理后，后到者才可恢复原包并仅解锁，HTTP 须显式重试。**

## 方法

1. 在 `v00/browser/` 写你自己的 Playwright 外部配置（`G7B_*` 环境变量控 run 名；`webServer: undefined`；`testDir` 指向本目录；`fullyParallel:false, workers:1, retries:0, trace:'on'`；reporter list+json+junit 输出到 `v00/browser/<run>`）。可参考旧 spec 的方式（只读 `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/browser/g6.spec.ts` 与 `external.config.ts` 的**基础设施写法**），但**不得复用旧“两页先后正常写入同键”的前置**。
2. 自己启动冻结构建的前端（不要与 5174 争用）：`node scripts/run-web.mjs start 5175`（记录 PID/命令行/端口/日志；结束时只关你自己启动的这个进程树）。spec 内用 `context.route('**/api/v1/**')` 接管全部接口（GET 文档/分类/画像返回固定 mock；create/import POST 先扣押不响应），不调用真实业务 API/数据库。
3. spec 至少要有的断言链（create 与 import **各一遍**，各覆盖 390 与 1440 两种视口；同一 Context 内 A、B 两 Page）：
   1. 两页都先加载（空操作键）；用真实 localStorage 写读证明同源共享（A 写 B 读）。
   2. B 点击开始（“将当前正文创建为后台教案” / “导入完整旧本地稿到后台”）→ 恰好 1 个 B 的 POST 被扣押；断言存储中的 B 包与 POST 的 `submissionId/operationId/metadata/payload` 逐字段一致（完整恢复包）。
   3. 把 B 的 POST 作为**未知**释放（abort）→ B 出现“重试原创建包/重试原导入包”且可用；记录 B 原字节。
   4. **A 点击同样的开始按钮 → 不得出现第 2 个 POST；A 的操作键必须逐字节等于 B 的原字节；A 出现阻断原因（包含“另一原操作”的可见文本）且开始按钮禁用、缓存重试按钮可用；A 不得解锁、不得导航/创建。**
   5. B 点击重试原包 → 第 2 个 POST 的 body 与第 1 个逐字段相同（同一 `submissionId`/完整 payload/metadata）→ 返回成功 → B 自己的包被清理（键空）。
   6. **A 点击“重试创建/导入操作恢复缓存” → 成功恢复 A 自己的原包（键中 operation 的 payload 与 A 的输入逐字段一致、`submissionId` 即 A 后续显式重发将使用的身份）；此时仍不得有任何 A 的 POST；界面提示“尚未发送HTTP，请显式重试原包”。**
   7. （可选但推荐）A 显式重试原包 → 第 3 个 POST 使用 A 自己的 `submissionId` 与完整载荷，success 后 A 自己的包被清理。
4. 证据：每例的实际截图（至少 A 被阻断时的整页图 + B 未知状态）、trace、Playwright JSON/JUnit、服务日志；失败/超时如实保留（首败另存，不得删改成绩单）。

## 判据

- 4 个（或 6 个）用例在**单轮完整运行**中全部通过、0 retry/skip；A 侧 POST 计数在步骤 4 与 6 必须为 0；B 原字节在步骤 4/6 前后逐字节不变；同源共享有真实读写证据。
- 任一失败：如实记录，不得改为多轮拼凑；不得为了让测试变绿而改产品、旧 QA 或断言。

## 交回格式

`v00/browser/V-G7-B-RESULT-v1.md` + `v00/browser/V-G7-B-RECEIPT-v1.json`（命令/PID/端口/时间/退出/日志与证据 SHA、每个用例 pass/fail、未执行项）。关闭自有前端服务（PID/出生/argv 守卫）并记录关闭收据。
