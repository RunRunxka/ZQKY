# G1 前端代码复审

2026-10-02，`/root/g1_frontend_review`。只读审查 G1 的 R01–R03、R08 实现，**本范围没有新增可复现产品缺陷**。没有启动前端、后端或浏览器，没有绕过 5174 的 `blocked by policy`。本结果不能关闭 G1 浏览器门禁。

## 代码核查

| 范围 | 核查结论 |
| --- | --- |
| R01 | `ScoreImportReview.tsx:90–126` 的 dirty/保存中/权威预览守卫与承认失效，`:200–227` 的四入口载荷守卫、未知原包优先，以及 `:598–612`、`:679–683` 的两个提交入口一致。保存后旧预览不会放行；未知结果后即使权威批次已 confirmed，重试仍原样提交冻结请求。 |
| R02 | `ScorePanel.tsx:132–156` 操作代次、`:190–198` dirty/编辑代次与 `:301–314` 保存回执区分请求前后输入。迟到回执不清新编辑；保存后权威 GET 失败仍保留已存映射并阻断旧预览确认。Workspace 以 assessmentId 重挂载 ScorePanel。 |
| R03 | `RosterPanel.tsx:91–95` 共用变更通知、Workspace 独立 rosterRefreshToken 与 `AssessmentsPanel.tsx:104–121` 同 key 刷新保留合法草稿。`:185–187` 及 `:280` 拒绝以读取失败名单发起普通新建；结果未知仍允许原包重放。切班/卷时 Workspace key 使旧面板失效。 |
| R08 | `RichContentRenderer.tsx:55–67` 完整遍历所有 delimiter 表达式并插入显式或默认分隔符，空参数不省略。未知表达式回落到安全原 XML 提示；本文不将 DOM 结构断言当作实际浏览器 MathML 排版验收。 |

读过根/web AGENTS、最新 G1 REPORT/G1-CLOSE-MATRIX、实现者 RESULT、V00-FE RESULT 及其测试，相关 hooks/API 客户端和现行 UI 测试。V00 旧证据只读；未执行带 afterAll 回写旧收据的旧独立脚本。

## 本次新证据

新探针 [authority-boundaries.test.tsx](authority-boundaries.test.tsx) 使用真实产品组件、StrictMode 与受控 fetch 边界，独立手写请求/交互断言，没有制造实际业务持久化结论。

1. 确认已经在服务端提交但响应丢失；后续权威视图为 confirmed 且映射待存，仍原样重放 r1/preview1/assessment1 与同 submissionId。
2. 映射保存成功 r2 后权威 GET 返回 500，保留 F、等待权威预览、普通确认零 POST。
3. 名单读取失败，甲的免考与第三人次、标题保留；按钮及直接表单提交均拒绝普通新建，零 POST。

| 实跑命令（仓库根） | 单次结果 |
| --- | --- |
| `node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/vitest.config.ts --outputFile.junit=docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/probes-final.xml` | **3 passed，exit 0**，1.33s；[日志](probes-final.log)、[XML](probes-final.xml)、[退出码](probes-final.exit.txt)。 |
| `node node_modules/vitest/vitest.mjs run apps/web/src/features/assessments apps/web/src/components/ui/RichContentRenderer.test.tsx --reporter=verbose --reporter=junit --outputFile.junit=docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/regression.xml` | **11 文件 / 111 passed，exit 0**，2.93s；[日志](regression.log)、[XML](regression.xml)、[退出码](regression.exit.txt)。 |

上述两次命令均先设置 `$env:NODE_OPTIONS='--no-experimental-webstorage'`，不加总为同一次运行。首轮探针 **1 failed / 2 passed，exit 1**，原因是 jsdom 缺失 HTMLDialogElement.showModal，尚未执行该例产品请求断言；只补新 QA 中的 dialog 夹具再运行，保留 [首败日志](probes.log)、[XML](probes.xml)、[退出码](probes.exit.txt)，没有改产品或放宽断言。

[本范围 SHA 后验](sha-after.json) 对 G1-r2 清单的 assessments、RichContentRenderer 与 assessments-api 实物逐项比对，零漂移。

## 未执行与边界

浏览器、E2E、三视口像素、键盘与 reduced-motion、完整 check/API、真实模型/Word/WPS/Qdrant、正式迁移均未执行。本次没有监听进程、测试端口或浏览器需要释放；没有读取正式凭证、业务库或真实草稿，也没有删除任何临时目录。产品和旧证据保持原样，新 QA 文件写入仅限本 `frontend/` 目录。

本范围建议下一步继续关闭现有浏览器/E2E 门禁；如果真实浏览器暴露缺陷，应在 G1 原范围修复、重新冻结并重验受影响项，然后才能进入 B4。没有因为组件检查通过而放宽原门槛。
