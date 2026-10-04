# ROSTER UI v1 实现结果

- 状态：`ready_for_review`，2026-10-02。实现者完成窄测后停止名单与题库产品文件写入；整体验证、真实浏览器链与独立验收由总控接续。
- 负责人：`/root/question_frontend`。
- 范围：名单上传、表头映射、逐行身份消歧、幂等确认、恢复服务端批次、转班及旧 membership 展示，并补齐手建班级/学生的迟到响应保护。

## 精确修改文件

产品与测试：

1. `apps/web/src/features/assessments/RosterImportPanel.tsx`（新增）。
2. `apps/web/src/features/assessments/RosterImportPanel.test.tsx`（新增）。
3. `apps/web/src/features/assessments/RosterPanel.tsx`（修改）。

证据：

1. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/ROSTER-RESULT.md`。
2. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-first-run.log`。
3. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-regression.log`。
4. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-eslint.log`。
5. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-regression-final.log`。
6. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-regression-ready.log`。
7. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/roster-eslint-ready.log`。

共享 `assessments-api` 客户端、contracts、hooks、styles、权威文档与 Git 均由总控持有；本任务未修改这些文件，也未修改 `next-env.d.ts`。题库 F10 与真实题库 fixture/spec 的既有结果见本目录 `F10-RESULT.md`，已停止写入。

## 实现行为与验证边界

- 使用总控提供的真实客户端及 `contracts/roster`，未复制接口契约。CSV/XLSX 文件以 multipart 上传，工作表名及手工映射可选；映射使用客户端真实字段 `mappingJson`。上传失败保留文件与输入，服务端批次列表支持恢复。
- 自动建议仅展示为提示；每一数据行需显式选择 link/create/ignore，link 可查询并关联既有学生。学号作为字符串保留，包括前导零。表头变更需先保存；确认可携带完整行决策。
- 确认使用真实 `useFrozenSubmission`：未知结果冻结原 payload 和 submissionId，重试重放相同请求；409/422 保留编辑与字段错误，显式刷新版本仍保留校对。确认成功副作用仅在有效 submission 结果后执行。
- 切换班级使导入面板重新挂载，旧上传/确认响应及卸载后回调被屏蔽；手建班级/学生与转班也有 generation/mounted/classId 保护。
- 转班传递 expectedStudentRevision、fromClassId、toClassId、movedOn；成功展示旧班结束日期、新班 membership 和返回版本。409 保留表单；未知转班失败提示先刷新历史核对，不自动重放非幂等操作。
- 17 项组件回归通过真实组件与真实客户端，仅替换 fetch 边界：覆盖 CSV 导入消歧/确认、XLSX multipart 字段与恢复批次、409/422 编辑保留和版本刷新、未知确认失败同 submission 重放、迟到上传/确认/手建/转班成功与失败、转班日期版本及历史展示。
- XLSX 单测验证选择文件与 multipart 传输，测试字节不构成真实 XLSX 解析验收。真实 API/browser CSV/XLSX 与转班链仍需总控执行，不能由组件窄测推定通过。

## 首败与修复

首次窄测 `roster-first-run.log`：退出码 1，1 失败 / 11 通过。失败是测试错误地期待 multipart `mapping` 字段；查证现行客户端/后端后改为 `mappingJson`，未为错误测试变更产品接口。修复后 12 项通过，追加迟到响应及转班覆盖后 17 项通过。

总控整合类型检查另反馈两项编译问题：确认结果 nullable 的使用已改为类型明确的 `confirmedResult` 常量并检查有效结果；测试 `getByRole` options 的 `exact` 字段已移除（Testing Library 该 API 无此选项，字符串 name 本身按完整名称匹配）。最终窄测和 ESLint 在修复后重新执行。实现者没有自行运行全量 typecheck，最终整合类型检查由总控负责。

## 命令与退出码

工作目录均为仓库根目录。

| 日志 | 命令 | 退出码 / 结果 |
| --- | --- | --- |
| `roster-first-run.log` | `$env:NODE_OPTIONS='--no-experimental-webstorage'; npm.cmd run test:unit -- apps/web/src/features/assessments/RosterImportPanel.test.tsx` | 1；1 失败 / 11 通过 |
| `roster-regression.log` | 同上 | 0；12 通过 |
| `roster-eslint.log` | `npx.cmd eslint apps/web/src/features/assessments/RosterImportPanel.tsx apps/web/src/features/assessments/RosterImportPanel.test.tsx apps/web/src/features/assessments/RosterPanel.tsx --max-warnings=0` | 0；零警告 |
| `roster-regression-final.log` | 上述单测命令 | 0；17 通过 |
| `roster-regression-ready.log` | 上述单测命令 | 0；17 通过 |
| `roster-eslint-ready.log` | 上述 ESLint 命令 | 0；零警告 |

## 真实浏览器链定位接口

已发送给总控，组件使用现有 `assessment-*` 类，无新增样式需求。

| 控件/结果 | 稳定定位 |
| --- | --- |
| 导入面板 | `data-testid="roster-import-panel"` |
| 文件 | aria `名单文件` |
| 上传 | 按钮 `上传名单` |
| 表头映射 | aria `名单姓名列`、`名单学号列` |
| 上传前可选输入 | aria `上传时姓名表头`、`上传时学号表头`、`名单工作表名` |
| 数据行决策 | aria `第 N 行处理`，value `link` / `create` / `ignore` |
| 关联学生 | aria `第 N 行关联学生` |
| 保存 | 按钮 `保存映射与行决策` |
| 确认 | 按钮 `确认名单` |
| 确认结果 | `data-testid="roster-import-result"`，含 `名单已确认` |
| 批次恢复 | `data-testid="roster-batch-{importId}"` |
| 刷新版本 | 按钮 `刷新版本对照（保留校对）` |
| 转班表单 | aria `转班学生`、`转入班级`、`转班日期`；按钮 `确认转班` |
| 转班结果 | `data-testid="roster-transfer-result"` |

N 是服务端数据行 rowNo（排除表头后从 1 开始），不是工作表物理行号。总控真实链应逐行显式选择 create，再确认 `new0001` 等学号仍为字符串。

## not_run

- 未执行全量 unit、typecheck、lint、`check`、build、Playwright/e2e：总控串行整体验证，避免共享资源冲突。
- 未启动任何端口或服务器；未操作正在运行的浏览器会话。
- 未执行真实 CSV/XLSX 解析、名单真实浏览器链或真实转班 API 验收；由总控补齐证据。
- 未执行 Git 操作、推送、部署或外部消息。

`ready_for_review` 表示实现者自检完成，不代表总控或独立验收已通过。
