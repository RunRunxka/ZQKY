# B3-FIX-F10 v1 结果卡

- 任务：B3-R01 新建补题观察窗口修复。
- 负责人：F10 实现 Agent。
- 起点：总控核定 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。
- 状态：**ready_for_review（实现自检完成，待独立验收）**。
- 写入停止：本结果卡完成后不再写入候选文件，交由总控冻结与独立复验。

## 改动与行为

`useQuestionJob.adopt` 根据创建收据的状态选择观察窗口：`queued@N` 接受 `[N,N+1]`，因此真实创建协议 `queued@0 → running/terminal@1` 能正常观察；已 `running` 收据仍只接受自己的 attempt，终态收据直接收敛。首次窗口仍拒绝 attempt `N+2`，不接受其他执行轮的候选结果。公共工作流客户端、跨模块契约和知识点 hook 均未改动。

新增回归使用真实 hook、实际 `observeJob` 和实际 `GenerationPanel`，仅在 fetch 边界返回受控响应，断言正确业务行为：

- queued@0 经 running@1 到 succeeded@1，候选批次入口出现且刷新回调一次；直接 terminal@1 的 succeeded/failed/cancelled/interrupted 均正常收敛。
- 首次 failed@1 显示可读失败和重试入口；重试 queued@1 接受 running/succeeded@2，只发送工作流重试请求，不再创建任务或发送模型参数。
- queued@0 后 attempt 2 的结果被拒绝，不显示候选；running@1 收据也拒绝 attempt 2。
- 既有重试 `[N,N+1]`、queued 持续等待、N+2 接管、StrictMode 和在途 busy 行为继续通过。
- 取消/重试在 switch/unmount 后的迟到成功和失败均不更新视图、错误或终态回调。

## 精确修改文件

1. `apps/web/src/features/question-bank/jobs.ts`
2. `apps/web/src/features/question-bank/jobs.test.tsx`
3. `apps/web/src/features/question-bank/GenerationPanel.test.tsx`
4. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/F10-RESULT.md`
5. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-first-failure.log`
6. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-regression.log`
7. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-regression-final.log`
8. `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-eslint.log`

## 首败、修复与命令

所有单测命令先设置 `$env:NODE_OPTIONS='--no-experimental-webstorage'`，均在仓库根目录执行，不启动服务端口，不操作正式草稿、凭证或数据根。

| 阶段 | 命令 | 结果 | 证据 |
| --- | --- | --- | --- |
| 修复前正确行为首败 | `npm.cmd run test:unit -- apps/web/src/features/question-bank/jobs.test.tsx apps/web/src/features/question-bank/GenerationPanel.test.tsx` | exit 1；6 failed / 30 passed。queued@0 的 running/terminal@1 被旧实现丢弃，留在 queued@0 + notice；组件成功/失败入口均未出现 | [首败日志](logs/f10-first-failure.log) |
| 局部格式化 | `npx.cmd prettier --write apps/web/src/features/question-bank/jobs.ts apps/web/src/features/question-bank/jobs.test.tsx apps/web/src/features/question-bank/GenerationPanel.test.tsx` | exit 0 | 命令输出未另存日志 |
| 修复后初轮 | 同上述单测命令 | exit 0；36 passed / 2 files | [初轮日志](logs/f10-regression.log) |
| 加入直接首次 succeeded@1 后最终回归 | 同上述单测命令 | exit 0；37 passed / 2 files（hook 25，组件 12） | [最终回归日志](logs/f10-regression-final.log) |
| 局部静态检查 | `npx.cmd eslint apps/web/src/features/question-bank/jobs.ts apps/web/src/features/question-bank/jobs.test.tsx apps/web/src/features/question-bank/GenerationPanel.test.tsx --max-warnings=0` | exit 0；0 警告 | [ESLint 日志](logs/f10-eslint.log) |

## not_run 与总控复验建议

- **未执行**全量 `npm.cmd run check`、全量单测、构建、TypeScript 全量检查和 E2E：按任务卡由总控统一串行执行。
- **未执行**真实 API/浏览器补题→候选校对→确认链：总控负责隔离数据根、端口、Provider 与浏览器上下文；本卡的 fetch 回归不冒称真实 API 通过。
- **未执行**真实模型或教学质量验收、正式数据迁移、Git 命令、提交/推送/部署。
- B3 原审查及 probes 保持原样，不用其“断言旧缺陷存在”的诊断结果作为修复成功证明。

总控的真实链建议保留 POST 的 queued@0 收据和 GET 的 running/terminal@1 响应，核实页面没有接管提示、候选入口出现并能进入校对确认；另以受控失败验证首次失败入口和 queued@1→attempt 2 的重试，并验证 N+2 结果不会进入本轮候选展示。

## F10-BROWSER v1 追加交付

状态：**ready_for_review，停止写入**。总控追加授权后新增以下独占文件，原 F10 产品候选不再修改：

- `tests/fixtures/teaching_loop_backend.py`
- `tests/e2e/question-bank-real.spec.ts`
- `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-browser-eslint.log`
- `docs/qa/TEACHING-LOOP-B3-FIX-20261002/logs/f10-fixture-smoke.log`

fixture 导出 `create_fixture_app(*, enable_question_generation: bool | None = None) -> FastAPI` 和 `app`。导入 `app.main` 前强制核验绝对临时数据根与 `ZQKY_ENV=test`，拒绝正式 `.local-data`、仓库内路径及整个系统临时目录；创建实际应用时使用 `replace(Settings.from_env(), credentials_file=None)` 与显式 `SecretStore()`，不会进入正式 `.env` 的凭证读取分支。默认不启用模型替身，可供成绩 E2E 共用；`ZQKY_TEST_GENERATION=1` 时真实模型配置仓储登记当前可调用的本地 profile、知识点仓储种子数学/有理数，只替换题库模型 Provider/resolver。仍使用真实四库、JobEngine、注册表、租约发布、校对和确认。

新 spec 检测并独占测试端口 8001，数据根为本次 `os.tmpdir()` 下 `zqky-f10-real-*` 目录；逐字节转发浏览器 API 请求与真实响应，不 mock 业务接口。受控 Provider 等待测试释放，先核实 queued@0 收据和 running@1 页面，再继续候选成功、题干人工编辑、标记已校对、确认、知识点筛选，并核实候选阶段正式题数为 0、确认后为 1、实际模型调用数为 1。只清理本测试已记录且经路径核验的临时目录。

| 检查 | 命令/方式 | 结果 |
| --- | --- | --- |
| 规格局部格式化 | `npx.cmd prettier --write tests/e2e/question-bank-real.spec.ts` | exit 0 |
| 规格局部 ESLint | `npx.cmd eslint tests/e2e/question-bank-real.spec.ts --max-warnings=0` | exit 0；[日志](logs/f10-browser-eslint.log) |
| 无端口真实应用 smoke | `uv run python -c <隔离 TestClient smoke>`（apps/api 工作目录；先创建 TemporaryDirectory，设置隔离环境，再导入 fixture） | exit 0；catalog 真 callable、queued@0→succeeded@1、Provider 调用 1，credentials_file=None/load_env_credentials=False；[日志](logs/f10-fixture-smoke.log) |

**未执行**浏览器 E2E、build 或服务器端口启动，均交总控串行运行。运行入口：`npx.cmd playwright test tests/e2e/question-bank-real.spec.ts`（先按仓库要求 build）。spec 产出 `generation-succeeded.png`、`candidate-reviewed.png`、`knowledge-filter.png`，附加真实收据/终态/确认/筛选 JSON 和隔离 API 日志；这些是预期产物，尚未宣称已经生成或视觉验收通过。
