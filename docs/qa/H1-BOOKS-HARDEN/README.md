# H1-BOOKS-HARDEN v1 批次证据（main 审查 M22-01～06 修复）

- 起点候选：`40491be`（分支 `main`，开工工作区干净；HEAD 为现场核对结果，不把审查文档提交当作当前 HEAD）。
- 本批提交：（一）`f4c9eaf` 产品与测试；（二）随后的 `docs(harden): 记录 H1-BOOKS-HARDEN v1 结果、独立验收与矩阵更新` 文档提交（含本批所有证据文件）。两次均为**本地小提交，未推送、未部署**；文档提交的自身哈希不写入本文件（写入会因改动文档而失效），用 `git log` 查看。
- 冻结契约与范围：[TASK-CARD.md](TASK-CARD.md)。
- 首败与修复台账：[DEFECT-LEDGER.md](DEFECT-LEDGER.md)。
- 探针断言反转证据：[probe-reversal/](probe-reversal/README.md)（原探针未修改，修复后运行输出）。
- 冻结候选指纹与构建号：[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)。
- 独立验收：`A1-REPORT.md`（只读独立验收者产出：r1 全文 + 总控处置 + r2 定向复验记录，结论 **r2 可交付**；自检不计入）。

## 1. 本批做了什么（一句话）

把书籍生成执行器与页/块修复从"分支里各自 `return`"改成**统一收尾 + 冻结身份 + 明确归属**：
执行器任何非运行出口都释放定时器/监听/注册表/租约并区分"删除/读失败/失权"；修复入口返回真实异步结果、
启动时冻结 runId、每次写入校验归属并具备互斥与取消；租约获取改为写后读回校验并在失权时停止；
首次读取失败不再被加载分支掩盖；最终完成落库失败不再假报完成；编辑器方向键不再触发全局翻页。

**真实服务边界：全部仍为本地模拟执行器与本地显式注入，不接真实 LLM/解析；本批通过不代表真实供应商能力。**

## 2. 验证结果（本批实跑）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck` | 通过（`next typegen && tsc --noEmit`，无错误） |
| 静态检查 | `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| 单元测试 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **48 文件 / 381 例通过**（基线 46 / 353） |
| 构建 | `npm run build`（总控自跑） | 通过，`BUILD_ID = cTTq7b-No7rnD-HNmoyQc` |
| 浏览器回归（本批新增） | `npx playwright test tests/e2e/books-harden.spec.ts` | **6 例通过**（逐条先行验证） |
| 浏览器回归（全量） | `npx playwright test` | **174 例通过 / 0 失败**（既有 168 + 新增 6，5.5 分钟） |
| 审查探针（反转证据） | `npx vitest run --config docs/qa/main-review-20260922/book-probe.config.ts` | 3/3 **按预期失败**（断言缺陷存在，修复后不再复现），输出见 [probe-reversal](probe-reversal/probe-run-after-fix.txt) |
| 后端 | 未运行 | 本批 `apps/api` 零改动，API 测试未重跑（如实记录，沿用本轮 API 基线 181） |

## 3. 修复内容（对照 M22-01～06）

1. **M22-01 统一收尾**：新增 `readBookForRun`（`ok/missing/denied`）与唯一收尾 `teardownRun`（释放合并写盘定时器、心跳、`pagehide`、注册表条目、自有租约、取消在途修复）；删除入口先 `stopRun` 再删记录；`getRunExit` 记录收尾原因，界面如实提示读失败/失权。
2. **M22-02 修复的真实异步结果与操作身份**：`retryBlock`/`regeneratePage` 返回 `Promise<RepairResult>`；启动时**冻结 runId**并每次写入核对归属（旧任务不得借用新 runId）；同页互斥（目标被覆盖则复用同一 Promise，否则取代），`cancelRepairs` 支持取消。
3. **M22-03 租约与共享集合**：租约带 `nonce`、获取为写后读回校验、每步/心跳校验归属、失权即停、只清自有租约；共享集合写入加写标记冲突检测 + 写前重放 + 写后读回校验（有界重试），所有写入路径统一走该路径。
4. **M22-04 首次读取失败可见**：错误面板 + 「重试读取」（复用既有 `space-banner error` + `space-banner-row` 形态），读取成功清除旧错误，加载态只在既无数据也无错误时出现。
5. **M22-05 最终完成写入失败不假报成功**：`finishBookRun` 抛错 → 落 `kind storage` 失败并给出「重试生成」入口（不设 finished、不只清句柄）；新增一次性模拟注入 `storageFailureOnFinish` 与对应 UI 开关。
6. **M22-06 方向键排除输入**：`shouldIgnorePageKey` 排除输入框/文本域/下拉/contenteditable/组合输入/修饰键/已消费事件，普通阅读的 ←/→ 仍有效。

## 4. 测试与基线变化（实跑数字）

单测：基线 `46 文件 / 353 例` → 本批 **48 文件 / 381 例**（净增 2 文件 / 28 例；其中 2 例为采纳独立验收 A1 挑刺后补的写后读回校验回归）。

- 新建：`apps/web/src/services/books-store.harden.test.ts`（5 例：共享集合并发写入不互相覆盖、笔记写入落地校验）、`apps/web/src/features/books/BooksRoute.test.tsx`（2 例：首次读取失败与重试、无效 id 不落加载态）。
- 扩展：`apps/web/src/services/book-generation.test.ts`（原租约用例拆为"运行/他标签页占用/失权"3 条 + 新增 `H1-BOOKS-HARDEN v1 缺陷回归` 11 条：删除收尾、读失败收尾并可恢复、旧任务不得借用新 runId、同目标复用与覆盖、取代、取消、修复写失败、修复期间归档不报 completed、最终写失败不假完成、stopRun 取消在途修复）；`apps/web/src/features/books/PageReader.test.tsx`（新增"全局翻页键的输入排除"2 条与"修复入口的真实异步结果"6 条，共 8 条）。
- 未改动：`apps/web/src/services/books-store.test.ts`（18 例）与 `BookGenerationStrip.test.tsx` 保持原样（指纹与前批一致）。

E2E：既有 168 例 + 新增 `tests/e2e/books-harden.spec.ts` 6 例 = **174 例通过 / 0 失败**（构建产物来自本批源码，`BUILD_ID = cTTq7b-No7rnD-HNmoyQc`）。新增 6 例覆盖：读取失败面板与重试（含 390 视口横向滚动差 ≤1px）、双标签页失权停止与释放后恢复、生成中删除无租约残留、笔记/contenteditable/普通阅读三组键盘、最终完成写失败不假完成并可恢复、同一 tick 连点互斥。

## 5. 视觉与设计（本批新增界面）

- 新增界面共三处（读取失败面板、「重新生成未完成」提示、模拟设置里的「模拟最终完成写入失败」复选项），全部复用既有控件与变量（`space-banner`/`space-banner-row`/`space-button`/`space-toggle`/`book-reader-storage-error`），未新增第二套样式定义、未改主题、未新增参考外动画；对照 `/chat` 基准保持蓝色主题与既有圆角/间距变量。
- 新增的读取失败面板与 R-11 资源目录失败横幅同形态（`space-banner error` + 行内重试按钮）；390×844 实测页面级横向滚动差 ≤1px（e2e 断言 `scrollWidth - innerWidth <= 1`）。
- 设计检查：按 `web-design-guidelines` 清单自查了本批新增/改动 UI（错误异步更新用 `role="alert"`；错误文案给出下一步；按钮有可见文本；无 `transition: all`、无新增动画、无布局读取、无 `outline:none`），未发现需要修改的项；**未**按该清单做全站改造（不属本批范围）。技能清单为外部公开规范，非本批验收标准。

## 6. 边界与未执行项（如实记录）

- 未运行：`apps/api` 测试（零后端改动）、真实供应商/真实 LLM 调用、移动端硬件触摸、逐帧动画曲线（属 H6）。
- 未接入：RAG（PROJECT_GUIDE §4.1 / STATUS §6.1 的阶段性设计；`F:\ZQKY_RAG` 保持只读，仍需先完成 P8A 与可恢复版本交付）。
- 不包含：课程学习会话、BookChatPanel、真实解析、主题重做、`feat/glass-theme` 合并、推送/部署。
- 双标签页竞争：本批用"真实第二标签页接管租约 → 第一标签页失权停止"作为**确定性**证据；两个标签页在同一毫秒写入共享键的极端窗口无法用测试确定性构造，属 `localStorage` 无 CAS 的固有边界（实现为写后读回 + 有界重放）。
- 组合输入（IME `isComposing`）与修饰键在真实浏览器无法稳定构造，测试在组件层完成；真实浏览器覆盖了输入框与 contenteditable 两组键盘。


## 7. 提交与暂存范围（本地）

| 提交 | 内容 | 说明 |
| --- | --- | --- |
| `f4c9eaf` | 产品与测试：`book-generation.ts`、`books-store.ts`、`BooksRoute.tsx`、`PageReader.tsx`、4 个单测（含 2 个新建）、`tests/e2e/books-harden.spec.ts`（新建） | 提交前逐项检查暂存范围：无 `apps/api`、无 `教案模板部分`、无 `assets/`、无 `*.css`/主题、无 `.env*`/`.local-data`、无构建产物或密钥；`apps/web/next-env.d.ts`（构建生成文件）已还原为仓库版本、不随批提交 |
| docs(harden) 提交 | 文档：`docs/STATUS.md`、三矩阵、`docs/qa/H1-BOOKS-HARDEN/**` | 文档提交不触及产品文件，冻结指纹（12 文件 sha256 + BUILD_ID `cTTq7b-No7rnD-HNmoyQc`）在两次提交后保持不变 |

未执行（用户未授权）：推送远程、部署、切换或合并 `feat/glass-theme`、改动全局 Git 身份。
