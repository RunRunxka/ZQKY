# H1-BOOKS-PIPELINE v2 批次证据（书籍生成流水线与增量阅读闭环）

- 起点候选：`bf460ab5ee53810679752c5104f7e2a777221d08`（分支 `codex/replica-review-20260908`）。
- 本批提交：见 `docs/STATUS.md` §4 批次表（提交后回填 SHA）；提交前候选差异标识见 [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)。
- 范围与冻结契约：[TASK-CARD.md](TASK-CARD.md)；固定参考逐字规格：[REFERENCE-SPEC.md](REFERENCE-SPEC.md)。
- 首败与修复台账（含总控裁定 A1–A7 与本轮新发现的 N1–N8）：[DEFECT-LEDGER.md](DEFECT-LEDGER.md)。
- 独立验收：`A1-REPORT.md`（只读独立验收者产出，逐项 pass/fail/not_run）。

## 1. 本批做了什么（一句话）

把书籍生成从“确认大纲即同步 ready”改成**显式模拟流水线**：七态状态机 + 页面/块状态 + 可替换的本地模拟执行器（增量事件、租约单执行者、检查点续跑、一次性失败注入），
界面承载活动条/展开详情/暂停横幅/继续生成/重试与整页重生成/导出未完成标注，并把 UI 上的每个注入开关都做成**真的会命中**（不再是静默无操作）。

**真实服务边界：全部为本地模拟执行器与本地显式注入，不接真实 LLM/解析；本批任何一条通过都不代表真实供应商能力通过。**

## 2. 验证结果（本批实跑）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck` | 通过（`next typegen && tsc --noEmit`，无错误） |
| 静态检查 | `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| 单元测试 | `$env:NODE_OPTIONS=--no-experimental-webstorage; npm run test:unit` | **46 文件 / 353 通过**（基线 47 文件/344 中删去零断言探针 `zz-debug.test.ts`，新增 10 条） |
| 构建 | `npm run build`（总控自跑） | 通过，`BUILD_ID = TPMei2ra-L9r31dqKSPpl`（2026-09-20；迭代：r1 `hrsgX9VjAM3HhtDYpjgPj` → r2 加 `contentVersion` 生产写入 → r3 修活动条展开浮层被 46px 条裁切，见 §3 与台账 N9/N10） |
| 浏览器回归 | `npm run test:e2e` | **168 通过 / 0 失败**（既有 154 + 新增 `books-pipeline.spec.ts` 14 例；e2e 独占 5174，构建产物来自本批源码） |
| 视觉与动画 | 真实浏览器（msedge）三视口 + 焦点 + 减少动画 + 中断/快速开关 | 见 §4 与 [visual/evidence.json](visual/evidence.json) |
| 后端 | 未运行 | 本批 `apps/api` 零改动，API 测试未重跑（如实记录） |

单测基线变化说明：上一任交接记录为「47 文件 / 344 通过」，其中 1 个文件是零断言探针 `apps/web/src/services/zz-debug.test.ts`（总控裁定 A7 删除）。删除后为 46 文件 / 343 条，加上本批新增的 10 条 = **46 文件 / 353 条**。

## 3. 冻结候选

`FROZEN-CANDIDATE.json` 记录候选的 15 个产品/测试文件的 SHA256 与 BUILD_ID，`revision` 字段说明版本：

- **r1**：首个冻结候选；独立验收 A1 首轮在其上执行 → **pass 32 / fail 0 / not_run 0**。
- **r2**：采纳 A1 挑刺（`contentVersion` 生产路径从不写入）后的修订候选（仅 `services/book-generation.ts` 与其单测变动）；A1 定向复验 → **pass（7 项 / 13 条断言）**，并在真实存储上取到「作答 `blockVersion` == 块 `contentVersion`」的直接证据。
- **r3**：总控视觉取证发现活动条展开浮层被 46px 单行条裁切（台账 N10）后修复的修订候选（`BookGenerationStrip.tsx` + `book-pipeline.css` + 两处断言变动）；A1 对 r3 的定向复验记录追加在其报告末尾。

**每次冻结都以当次 A1 复验为界；验收后未再改动产品代码**；若后续需要改动，必须重新冻结并复验。

## 4. 视觉与动画证据（`visual/`）

- 三视口 1440×900 / 1920×1080 / 390×844：`v1-chat-baseline-*`（`/chat` 基准）、`v2-library-compiling-*`、`v3-reader-generating-*`、`v4-strip-detail-open-*`、`v5-strip-detail-quick-toggle-closed-*`、`v6-paused-banner-*`。
- 失败链与只读态（1440）：`v7-block-failure-partial`（块失败卡 + 页失败面板）、`v8-page-failure-interrupted`（已中断 + 「继续生成」）、`v9-run-failure-error-retry`（整轮失败原因 + 「重试生成」）、`v10-archived-readonly`（归档只读说明 + 入口禁用）。
- 交互：`v11-keyboard-focus`（Tab 链）、`v12-reduced-motion`、`v13-focus-strip-control`（活动条按钮焦点环）、`v6b-interrupt-dialog-then-paused`（浮层展开中暂停）。
- 量化证据（`evidence.json`）：
  - 浮层进场 `book-pipeline-detail-in` **0.18s** `cubic-bezier(0.16, 1, 0.3, 1)`（对照参考 180ms 与同曲线）；
  - 呼吸文字 `book-pipeline-breathing` **1.8s**（对照参考 `dt-breathing`）；
  - 减少动画（`prefers-reduced-motion: reduce`）：上述两项 `animation-name: none`、时长 `1e-05s`（全局层压制，本批未新增 reduce 规则）；
  - 快速开关：浮层 0→1→0（连点 4 次仍为 0，无重复浮层，`aria-expanded=false`）；
  - 中断：浮层展开中暂停 → 横幅出现、活动条仅剩「恢复生成 / 已生成内容」、浮层仍可收起（关闭后计数 0）；
  - 恢复：横幅「恢复生成」→ 回到“正在逐章编译”→ 完成（该路径正是修复 N3 的链路）；
  - 键盘焦点：活动条「暂停生成」得到 2px solid `rgb(37, 99, 235)` 焦点环；
  - 展开浮层几何（r3 修复后实测，三视口）：浮层高度 183px（远大于 46px 单行条）、右/下边界不越出视口、`elementFromPoint(中心)` 命中浮层自身（证明画在正文之上且未被裁切）、背景不透明；e2e 与单测各加了对应断言（含「浮层不得是 `role=status` 子节点」的结构断言）。
  - 页面级横向溢出：390×844 实测 0（e2e 窄视口用例断言 `scrollWidth - innerWidth ≤ 1`）。

## 5. 浏览器回归覆盖（`tests/e2e/books-pipeline.spec.ts`，13 例）

正常生成（活动条/计时/展开详情必须真的展开且不越出视口/生成中可读）｜用户暂停与恢复（paused 不自动续跑、刷新后恢复可用）｜模拟供应商连续失败暂停（文案写明本地模拟）｜刷新中断自动续跑｜双标签页单执行者｜块失败与重试（不重建整本）｜整页重生成保留笔记与块身份（演示就绪书本无 run 记录也真的重生成）｜整页失败→已中断→继续生成｜本地存储写入失败→error→重试生成→完成｜生成期间笔记书签不被覆盖｜生成中删除不复活｜未完成书导出如实标注｜窄视口 390（活动条与暂停、展开浮层完整可用且无页面级溢出）。

配套改造：`tests/e2e/books-courses.spec.ts` 两处“确认大纲即同步 ready”的旧断言改为异步流水线断言（更强），其余用例零改动。

## 6. 未执行 / 边界（如实记录）

- 未执行：`apps/api` 测试（本批零后端改动）、真实供应商链路（本批未接真实 LLM/解析）、移动端硬件触摸、逐帧曲线采样（动画精度属 H6 总验收范围）。
- 归档只读（A3）在浏览器侧只能通过存储种子构造：本批 `BooksRoute` 没有归档入口 UI（既有语义不变），归档书的入口禁用由组件测试 + 种子数据浏览器截图覆盖。
- 参考侧 `lazy_compile` 在目标侧无对应物（目标始终整本编译），按任务卡裁定记录为“不适用”；参考 6 阶段准备链不伪造。
- 不包含（不因本批通过而关闭）：BookChatPanel、课程学习会话、真实 LLM/解析、真实 HealthBanner 数据、侧栏折叠、多用户权限、R-13、R-06 补测、14 类 block 全面重做、导航字体收口。
