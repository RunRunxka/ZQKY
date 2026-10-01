# A1 独立验收报告 —— H1-BOOKS-PIPELINE v2（书籍生成流水线与增量阅读闭环）

- 验收者：独立验收者 A1（只读；未修改任何产品文件）
- 验收时间：2026-09-20 18:20–19:40（本地）
- 环境：Windows 10.0.26200 x64 / Git Bash / Node 26 / Playwright 1.58.2（chromium，channel=msedge）
- 结论先行：**通过（pass）。逐项 32 项全部 pass，0 fail，未执行项如实列出。**

---

## 1. 候选指纹校验

| 项目 | 结果 |
| --- | --- |
| HEAD | `git rev-parse HEAD` → `bf460ab5ee53810679752c5104f7e2a777221d08`（与 FROZEN-CANDIDATE.parentCommit 一致） |
| 分支 | `git branch --show-current` → `codex/replica-review-20260908`（一致） |
| 工作树 | `git status --short` → 21 项（与任务卡 §0 声明的接手前改动 + 本批文件一致，候选未提交，符合契约） |
| BUILD_ID | `apps/web/.next/BUILD_ID` → `hrsgX9VjAM3HhtDYpjgPj`（与 FROZEN-CANDIDATE.buildId 一致；**注意：验收委托书正文写成 `hrsgX9VjAM3HHTDYpjgPj`（大写 HT），与冻结 JSON 不符，以冻结 JSON 与实际文件为准**） |
| 15 文件 SHA256 | 逐文件 `sha256sum` 与 `FROZEN-CANDIDATE.json.fileSha256` **全部一致**（前后各校验一次；末次明细存 `_work/h1-books/a1/final-sha256.txt`） |

校验命令（首次与末次相同，两次结果一致）：

```bash
git rev-parse HEAD; git branch --show-current; git status --short
cat apps/web/.next/BUILD_ID
for f in <15 个相对路径>; do sha256sum "$p"; done   # 与 FROZEN-CANDIDATE.json 逐项比对
```

## 2. 实际运行的命令清单

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | 通过（next typegen + tsc --noEmit，无错误） |
| `npm run lint`（`--max-warnings=0`） | 0 | 通过，0 警告 |
| `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | **46 文件 / 352 例全部通过**（18.06s） |
| `npx playwright test tests/e2e/books-pipeline.spec.ts tests/e2e/books-courses.spec.ts` | 0 | **19 例通过**（books-courses 6 + books-pipeline 13；2.7m） |
| `npx playwright test`（全量复跑） | 0 | **167 例通过 / 0 失败**（4.9m） |
| `npx playwright test tests/e2e/course-resource-faults.spec.ts` | 0 | 9 例通过（R-11 课程资源三态佐证） |
| A1 自有取证 4 批（`_work/h1-books/a1/`，5176 服务，msedge） | 0 | 25 条记录（见 §3），中途 5 次失败均为 A1 脚本自身选择器/路径错误，修正脚本后复跑通过，非产品缺陷 |
| `node scripts/run-web.mjs start 5176` | — | 验收专用端口（未触碰 5173/5174/8000） |

A1 脚本中途失败说明（如实记录）：`.book-reader-page-failure`（实际为复数 `book-reader-page-failures`）、`.book-pipeline-banner`（实际为 `space-banner error`）、导出按钮定位（按钮在书籍详情阅读器内而非列表卡）、演示书首页无 user_note 块（该块只生成在"第2页"结构）——这些是 A1 取证脚本写错，**不是候选缺陷**；每次失败的首败现场均保留在 `_work/h1-books/a1/.test-results/`，且失败现场快照本身提供了额外佐证（如 A1-02b 失败现场快照中已可见"生成已中断（无执行器在跑）"）。

## 3. 逐项验收表

| 编号 | 范围 | 结论 | 命令/手段 | 观察到的证据 |
| --- | --- | --- | --- | --- |
| A1-01a | 正常链路·活动条 | pass | 5176 浏览器 | 活动条 boundingBox 高度 = 46px（容差 2） |
| A1-01b | 正常链路·活动条语义 | pass | 同上 | `role="status"`、`aria-live="polite"`（BookGenerationStrip.tsx:99） |
| A1-01c | 正常链路·阶段/章数/计时 | pass | 同上 | 文案「正在逐章编译（本地模拟，不调用模型）…」、`1/4 章`格式、计时文本 `^\d{2}:\d{2}$` 且 `aria-label="已运行 mm:ss"`（T1 口径） |
| A1-01d | 正常链路·展开浮层 | pass | 同上 | 浮层 `role="dialog"` + `aria-label="已生成内容"`；截图 a1-01-detail-open.png |
| A1-01e | 正常链路·收尾 | pass | 同上 | 完成后活动条消失（count=0）；刷新后无"本章尚未生成"占位；生成中页与已完成块同页可见 |
| A1-02a1~4 | (a) 块失败 | pass | 5176 浏览器 | 失败卡="小节 块生成失败 / 内容生成失败（本地模拟）/ 模拟块生成失败（本地注入：首次失败，重试即成功；非模型产出）。/ 重试"；重试后失败卡消失、无活动条出现（未重建整本）、页码"第 1/8 页"结构保留 |
| A1-02b1~3 | (b) 整页失败→已中断 | pass | 5176 浏览器 | "页面生成失败"面板含「重新生成本页」；活动条含"生成已中断（无执行器在跑）"+「继续生成」（书籍保持 compiling 不假 ready）；点击后完成（一次性注入不再失败） |
| A1-02c1~3 | (c) 整轮失败（storage） | pass | 5176 浏览器 | error 横幅="生成失败（本地模拟）：本地保存失败（写入本地数据（zhiqikeyuan:books）失败（存储可能已满）；本次修改已回滚，原数据保留。）已停止生成，原数据保留。"+「重试生成」；重试后续跑完成 |
| A1-02d1 | (d) 不谎报已保存 | pass | 同上 | 注入后 localStorage 键 `zhiqikeyuan:books` 仍可读（长度 10113），原数据保留；BooksRoute error 横幅为唯一长文案来源（N8 修复确认） |
| A1-03a1~4 | 用户暂停/恢复/刷新 | pass | 5176 浏览器 | 横幅标题「生成已暂停」+ user 说明 + `Paused by user.` 代码块 +「恢复生成」；**刷新后 3s 观察：仍 paused、未自动续跑**；刷新后点「恢复生成」→ 回到"正在逐章编译"→ 完成（N3 链路成立） |
| A1-03b1~3 | 模拟供应商暂停 | pass | 5176 浏览器 | 横幅="本地模拟的供应商连续失败，生成已暂停：……这是显式模拟的暂停场景，**不代表真实上游服务故障**。" + reason="模拟供应商连续失败（本地注入场景，非真实上游故障）。"；无"额度/密钥"归因；恢复后不再在同一触发点失败（阈值 2：连续 2 页失败后暂停，e2e 与单测同证） |
| A1-03c1~2 | 刷新中断自动续跑 | pass | 5176 浏览器 | 生成中刷新 → 活动条重现（自动续跑）→ 完成后刷新无未生成占位（已完成内容保留） |
| A1-04a~c | 并发双标签 | pass | 5176 浏览器（同 context 两 page） | 标签 B 无「暂停生成」按钮（count=0），显示"本书正在另一个标签页生成"；A 完成后 B 刷新数据完整（4 页骨架无重复） |
| A1-06a~c | 导出·未完成书 | pass | 5176 浏览器 | `a1-export-probe.md` 文首="> 注意：本书尚有 1 个章节页未生成完成（本地模拟编译，导出时如实标注，不代表完整成书）。"；未完成页逐页标注"本章尚未生成完成（状态：…）" |
| A1-07a | 演示数据幂等 | pass | 5176 浏览器 | 清库后载入演示数据 3 次 → 书数=2（幂等） |
| A1-07b | 旧四态可读不写回 | pass | 5176 浏览器 + 源码 | 种入无 `run` 的旧四态 `ready` 书，列表可读；读取后存储记录无新增字段（`status:ready` 且无 `run` 键——读取期派生不写回，books-store.ts:896 `page.status ?? 'ready'` 同口径） |
| A1-08a~d | 挑刺①演示书强制重生成 | pass | 5176 浏览器 | 无 run 记录的演示就绪书「强制重新生成」→ 块占位出现（真的重生成，非静默无操作）→ 完成后笔记"A1验收笔记-必须保留"仍在、活动条未出现（书籍仍 ready 不整本重建）、块数=13 与页码结构不变 |
| A1-09a~b | 挑刺②页内笔记写失败 | pass | 5176 浏览器（注入 QuotaExceededError） | 页内提示="写入失败，内容未保存。本页笔记未写入本地存储，请重试或另行保存。"（role=alert）；存储 JSON 中无该笔记文本（未谎报已保存） |
| A1-10 | 三视口横向溢出 | pass | 5176 浏览器（1440×900/1920×1080/390×844） | `scrollWidth - innerWidth` = 0（三档均 ≤1） |
| A1-11a~b | reduce 动画压制 | pass | 5176 浏览器（emulateMedia reduce） | 呼吸动画 computedStyle `animation-name: none`、浮层进场同（全局层压制生效，本批未新增 reduce 规则） |
| A1-12a~b | 快速暂停/恢复不丢内容 | pass | 5176 浏览器 | 暂停落库 status=paused 且 ready 块数>0；恢复后 status=ready 且 ready 块数 ≥ 暂停时值 |
| A1-13a~d | partial 持久态呈现 | pass | 5176 浏览器（种子 partial 书） | ready 书含 partial 页时卡片仍显示「可阅读」；页内失败卡"文本 块生成失败"与已完成块同页可用；书籍顶部仅"阅读进度 50% · 已读 1/2 页"，无"全部成功/全部完成" |
| A1-13e | 导出·partial 页 | pass | 5176 浏览器 | `a1-partial-export.md` 含"> 本章部分内容生成失败（状态：部分块生成失败）……"与"> [块生成失败（content·本地模拟）] text" |
| A1-14 | 键盘焦点可见 | pass | 5176 浏览器 | 「恢复生成」focus 后 outline=`2px solid rgb(37, 99, 235)` |
| E2E-P | books-pipeline.spec.ts 13 例 | pass | `npx playwright test …` 退出码 0 | 正常生成/暂停恢复/供应商暂停/刷新中断/双标签/块失败/整页重生成保笔记/整页失败→继续生成/storage→重试/笔记书签不覆盖/删除不复活/导出标注/窄视口 390 全过 |
| E2E-C | books-courses.spec.ts 6 例 | pass | 同上 | 书籍状态机异步断言（更强）、续读定位/书签/翻页/练习、课程演示/资源附加/归档、新建导航全过 |
| E2E-F | 全量 167 例 | pass | `npx playwright test` 退出码 0 | 既有 154 + 新增 13 全部通过 |
| R-11 | course-resource-faults 9 例 | pass | 同上 | 资源三态不回退（故障→重试→修复恢复可用，不清数据） |
| UNIT | 单测 46 文件/352 例 | pass | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` 退出码 0 | 含 A1/A2/A4/N1 修复的专项断言（'*first' 展开、一次性注入、无 run 补检查点、供应商开关单独开启生效、storage 真实抛错） |
| TC/LINT | typecheck / lint | pass | 退出码均 0 | lint 0 警告 |

**同书翻页不重启执行器**：由模块级注册表（book-generation.ts:110 `registry`，不随 React 卸载取消）与 BooksRoute.tsx:522 注释（组件卸载不清除执行器、翻页靠 key 稳定性）保障；e2e「正常生成」「刷新中断」用例均在翻页后由同一 run 跑完（若重启会导致 seq/租约冲突，未出现），A1-01e 生成中翻到列表再进入，活动条仍显示同一运行计时，未见重启。

**页面/块状态生产者与转移**：源码核对与 TASK-CARD §4.1 表一致（`applyEventToBook` 各 case、`pauseBookRun` 复位 pending、`finishBookRun` 有未完成页保持 compiling、`resumeBookRun` paused/error→compiling、`runWritable` 放行 compiling/paused/error/ready）。

**模拟边界（§3.8）**：全部 30 处"模拟"标注保留于 books-store.ts / BooksRoute.tsx / PageReader.tsx（grep 计数：store 20+、Route 30、Reader 7）；全项目 grep 无"额度不足/密钥被拒/凭据被拒"等真实上游归因；`provider` 一词仅用于 `RunPauseKind` 类型与供应商暂停开关，其呈现文案固定为"本地模拟的供应商连续失败/非真实上游故障"。

## 4. 汇总

- **pass：32**（逐项含子断言 45 条记录）
- **fail：0**
- **not_run：0**（本表范围内无；未执行项见 §5，均超出本批验收范围或环境不可行）

## 5. 未执行项与原因

| 项目 | 原因 |
| --- | --- |
| 真实供应商/真实 LLM/真实解析链路 | 本批未接入（任务卡非目标）；**无凭证的供应商调用一律 not_run，本报告不出现"真实供应商/真实服务通过"表述** |
| `apps/api` 后端测试 | 本批 `apps/api` 零改动，队长与任务卡裁定不重跑（如实记录，非"应当通过"） |
| 硬件触摸/真实移动设备 | 仅 390×844 视口模拟，无触控硬件 |
| 逐帧动画曲线采样 | 属 H6 总验收范围；本批以 computedStyle（0.18s / cubic-bezier(0.16,1,.3,1) / 1.8s / reduce none）与视觉证据覆盖 |
| 8000 端口后端联调 | 本批无后端改动，未启动 |
| `npm run build` | 委托书明确禁止（构建由队长完成）；BUILD_ID 以既有产物核对 |

## 6. 疑点与风险（未构成 fail，交总控裁定是否记入台账）

1. **`contentVersion` 生产代码从不写入（A1 挑刺发现）**：`books-store.ts:65` 定义、`quizAttemptMatches`（:274-282）与 PageReader 作答链路消费，但生产路径无任何写入——`book-generation.ts` 的 `plannedToBlockPayload`（:535-545）与 `block-ready` 事件载荷均不含 `contentVersion`，`grep contentVersion:` 全 src 仅命中测试种子。效果：每次作答的 `blockVersion` 为 undefined，按"缺版本视为匹配"规则（:280）旧作答**总是**被视为新题答案。版本关系机制本身正确（单测 :215-219、PageReader.test :502-546 用种子数据验证），但整页重生成后"旧作答不算新题答案"在真实运行中不会触发。**影响**：重生成后恢复的作答展示为旧题答案且提示语不出现；**建议**：总控决定是补生产者（block-ready 时写入内容哈希/版本）还是接受当前"模拟执行器内容不变"口径并记录。
2. **验收委托书 BUILD_ID 笔误**：正文写 `hrsgX9VjAM3HHTDYpjgPj`，冻结 JSON 与实际文件为 `hrsgX9VjAM3HhtDYpjgPj`。以冻结 JSON 为准，已如实记录，无产品影响。
3. **暂停按钮忙碌态 600ms 固定时器**（BooksRoute.tsx:603/614/624）：pausing/resuming/retrying 忙态用 `setTimeout(600)` 复位而非跟随真实落库，慢机上可能表现为按钮提前恢复可点；语义无害（幂等点击），记录备查。
4. **`getRun` 500ms 轮询驱动 UI**（BooksRoute.tsx:494）：活动条/横幅由轮询刷新，事件落库与 UI 更新间最大约 0.5s 延迟；实测不可感知，记录备查。
5. **旧四态书兼容依赖"缺 status 即 ready"约定**（books-store.ts:896、执行器 stepOnce :735 同口径）：若未来引入缺 status 但实际未完成的页会被误判 ready；当前契约明确如此，不算缺陷。

## 7. 挑刺项结论（§3.9 要求至少 2 项）

| 挑刺项 | 结论 | 证据 |
| --- | --- | --- |
| 无 run 记录的演示就绪书点「强制重新生成」是否真的重生成（A2 修复是否真成立） | **成立** | A1-08a：占位出现→完成，笔记保留、块身份不变、无整本重建；非静默无操作 |
| 页内笔记写入失败是否谎报已保存（§3.2(d)） | **不谎报** | A1-09a/b：页内 role=alert 提示"写入失败，内容未保存…"；存储中无该文本 |
| `provider` 开关单独开启是否真的暂停（N1） | **成立** | A1-03b1：单独勾选该开关（未开整页失败）后真实跑到暂停横幅，文案正确；单测「只开启…也会真的暂停」同证 |
| interrupted 态是否有恢复入口（N6） | **成立** | A1-02b2：活动条含「继续生成」（RefreshCcw），点击后完成（A1-02b3） |

## 8. 声明

- **本批通过只代表本地模拟执行器与本地注入场景在候选指纹上的行为成立；不代表真实服务/真实 LLM/真实供应商通过，不代表书籍模块或全站全部完成**（BookChatPanel、课程学习会话、真实 HealthBanner、侧栏折叠、R-13、R-06 补测、14 类 block 重做等仍不在范围）。
- 视觉通过为浏览器取证（msedge + Playwright）意义上的布局/溢出/焦点/动画口径，非人工像素级审阅。
- 验收期间 A1 未修改任何产品文件、未运行 git 写操作、未触碰 5173/5174/8000、未放宽或删除任何断言（A1 自有取证脚本修正不涉及产品）。

## 9. 末次指纹复验

```text
# _work/h1-books/a1/final-sha256.txt（2026-09-20，验收结束时）
services/books-store.ts                    c25c09efcce5e387641886cfaf4b9708076a695270b4d9a7ae8f924580a37b86
services/book-generation.ts                dcd0df3b962a1232214ecae1677fa9abb800e06d9810cee4a16d9538a7f2ec41
features/books/BooksRoute.tsx              55c9bfc415a77a218302cfc171133f44235f6c3e76c6a131a4d33de2c4b6a46e
features/books/PageReader.tsx              3e4e3f01f0f6c5ea3681eba1dc2b9a0c1c488ef33d4161859ee60a173bf093a4
features/books/BookGenerationStrip.tsx     9f3ab7b7658def87ada0f1b08a473caead35aba968924cc760e7d672b543de73
features/books/BookPausedBanner.tsx        0ee4d76c8ac2567bd91599db15bea2712ad0736d5e6b7a3edcfc26693410d536
features/books/BookBlockFailure.tsx        970b45f08cd26e25d73e6e98484011492e1e09a2c17c10acf587ab122673f152
services/books-store.test.ts               cc778caa00f16224d729d4157f84285be821b6a9b40619a6b5aaedc6573388aa
services/book-generation.test.ts           69c6fc8f24588c5b57d50fea72bb8873258ff461b366419997bfeb54f7ede014
features/books/PageReader.test.tsx         61c001cf2476c4f8aa86719921694a225934f38a460d6647c819d61d96777ced
features/books/BookGenerationStrip.test.tsx 619e04148d4412411e775c61846d0665a514e230873a90aaef7d637712595904
tests/e2e/books-pipeline.spec.ts           adfd00571b9fae96252493a0f247dab48d5fafabbc761a77c55df5082d69473a
tests/e2e/books-courses.spec.ts            c1fc357ec196d6e7ebdd1bdb0a6f30d3d441411e58b5eee3038b760695d8889a
features/books/styles/book-pipeline.css    342fbb817b9eec53aba1f1abfdc16a7b75edbae63174c80b12af8ebada1ec439
features/books/styles/book-reader-states.css b090ce037c0eb0945be522904d02b3063d5c01b3edd1a6f8d9386c235de37d9e
```

与 `FROZEN-CANDIDATE.json` 逐项一致，**验收期间产品代码未被修改**（`git status --short` 前后均为 21 项，HEAD 与分支未变；BUILD_ID 未变）。A1 写入的文件仅：本报告 + `_work/h1-books/a1/`（git 忽略）。

---

# 复验（r2 候选）

- 复验者：独立验收者 A1（只读；本节为对 r2 冻结候选的定向复验，上文 §1–§9 保留为对 r1 的原始结论，不做改写）
- 复验时间：2026-09-20 19:21–20:05（本地）
- 复验起因：r1 报告疑点 #1（`contentVersion` 生产代码从不写入 → 作答版本关系在生产路径上永不触发）被总控采纳修复，冻结 r2 候选后定向复验。

## R-1. r2 指纹校验（前后两次）

- `git rev-parse HEAD` → `bf460ab5ee53810679752c5104f7e2a777221d08`；分支 `codex/replica-review-20260908`——与 r1 相同，仍为工作树候选（未提交）。
- `apps/web/.next/BUILD_ID` → `tqqP-RbOtTrgBVOXkRUET`（与 r2 JSON 一致）。
- 15 文件 SHA256 与 r2 `FROZEN-CANDIDATE.json`（revision=r2）**逐项一致**，复验开始与结束时各校验一次，两次结果相同（明细：`_work/h1-books/a1/r2-sha256-first.txt` / `r2-sha256-final.txt`，`diff` 为空）。
- **相对 r1 的变化面核对**：仅 `services/book-generation.ts`（`dcd0df3b…` → `f0ed5f89…`）与 `services/book-generation.test.ts`（`69c6fc8f…` → `9b5458b9…`）两个哈希变化；**其余 13 个文件哈希与 r1 完全相同**（r1 报告 §9 末次明细逐项比对）。
- `git status --short` 项数：r1 为 21 项，r2 复验首末均为 **24 项**。新增 3 项为 `docs/replica/AI_INTERACTIONS.md`、`docs/replica/MOTION_MATRIX.md`、`docs/replica/PAGE_MATRIX.md`（均为总控权威文档可写范围的文档改动）；**产品代码/测试文件集合与 r1 一致，无计划外文件**。

## R-2. 复跑命令清单（r2）

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | 通过 |
| `npm run lint`（`--max-warnings=0`） | 0 | 通过，0 警告 |
| `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | **46 文件 / 353 例通过**（预期 353：r1 352 + 新增「块内容版本真实写入」1 例，`book-generation.test.ts:485` 可见且实跑通过） |
| `npx playwright test tests/e2e/books-pipeline.spec.ts tests/e2e/books-courses.spec.ts` | 0 | **19 例通过**（2.7m） |
| `npx playwright test`（全量） | 0 | **167 例通过 / 0 失败**（4.9m） |

## R-3. 定向行为验证（r2 修复的核心，实跑取证）

A1 自有取证脚本 `_work/h1-books/a1/a1-r2.spec.cjs`（5176 独立端口、msedge、真实执行器走完整本书后读 `zhiqikeyuan:books` 与 `zhiqikeyuan:book-quiz-attempts`）：

| 编号 | 验证点 | 结论 | 观察到的证据 |
| --- | --- | --- | --- |
| R2-01a/b | 执行器生成的块**真的带** `contentVersion` | pass | 真实执行器跑完整本书（8 页 68 块全 ready）后逐块读取存储：**68/68** 块带 `contentVersion`，格式均为 `v1-` + 8 位十六进制（样例 `v1-e5b0d941`） |
| R2-01c | 同页不同内容的块版本不同 | pass | 第 1 页 4 个块（section/text/callout/quiz 内容各异）版本互不相同（4/4） |
| R2-01d | 跨页版本分布（复核修正） | pass（修正判定） | A1 初判"全书 68 块无重复版本"**失败**——经 `_work/h1-books/a1/r2-probe.cjs` 取证，重复组全部为跨页**逐字相同**的模板块（callout「学习提示」、figure/interactive/animation 占位、第2页附加的 code/timeline/flash_cards/deep_dive/user_note 等，其 content 不含页标题，跨页逐字相同）。**内容相同 → 版本相同正是修复声明的语义**（同一道题旧作答仍有效），不是缺陷；A1 取证脚本断言写错，非产品问题。真正含页标题的 section/text/quiz 块全书无重复版本 |
| R2-02a | 作答 `blockVersion` **等于**块当前 `contentVersion` | pass | 在练习上作答后读存储：`blockVersion=v1-cee1d8ee` === 该 quiz 块 `contentVersion=v1-cee1d8ee`（**r1 时此处为 undefined**，即疑点 #1 的直接修复证据）；`choice=A correct=true` 历史保留 |
| R2-03a | 重生成（内容相同）→ 版本不变 | pass | 「强制重新生成」整页后块 `contentVersion=v1-499a08c6` 与作答 `blockVersion=v1-499a08c6` 仍相等（同内容同版本，不误判过期） |
| R2-03b | 版本不变时旧作答仍被恢复 | pass | 刷新重新打开页面：`"回答正确。"` 恢复显示、无旧版提示（`.book-reader-quiz-stale` count=0） |
| R2-04a/b/c | 内容变化 → 版本变化 → 旧作答标记为旧版记录 | pass | 构造方式：直接改存储中 quiz 块题干并置 `contentVersion=v1-deadbeef`（模拟"内容真的变了"），刷新后出现提示"该题内容已更新；当前显示的是旧版题目的作答记录（旧作答 A 已保留在历史中）。"，无"回答正确。"（未冒充新题答案），选项可重新作答。说明：模拟模板下执行器自身不产出内容变化（确定性模板），内容变化分支只能以存储注入构造；这与"未来接真实生成时版本随内容变化"的语义等价，版本判定走同一条 `quizAttemptMatches` 路径 |

取证脚本一次时序修正（如实记录）：A1 首版 `newBookCompile` 在点「确认大纲并编译」后直接等活动条消失，350ms 落库定时器未触发时 evaluate 读到旧骨架（R2-01 失败现场保留于 `_work/h1-books/a1/.test-results/`）；改为先等活动条出现再等消失后 4 例全过。**该失败是 A1 脚本竞态，非 r2 产品缺陷。**

## R-4. r1 结论对 r2 的延续性

| 范围 | 结论 |
| --- | --- |
| 与本次两文件直接相关项 | **重验通过**：作答版本关系（R-3 全部 7 条记录）；A1-12 快速暂停恢复（块落库路径唯一变化点 `plannedToBlockPayload` 所在链路，e2e 与单测均覆盖）；A1-08 演示书强制重生成（即时修复路径 `regenerateBlocks` 与 `plannedToBlockPayload` 共用同一版本写入，e2e「整页重生成保留笔记」与 R2-03 实测通过） |
| r1 挑刺 4 项 | `'*first'` 通配命中、页内笔记写失败提示、provider 开关单独开启、interrupted 恢复入口——两文件改动不触及这些链路（对照哈希：BooksRoute/PageReader/BookBlockFailure/BookPausedBanner/BookGenerationStrip 均**未变**），r1 结论延续有效；全量 e2e 167 例与单测 353 例复跑通过为行为层佐证 |
| 其余 r1 项（A1-01～A1-14、导出、三视口、reduce、并发等） | r1 已验；本次通过全量 e2e（167/167）+ 单测（46 文件/353 例）+ typecheck/lint 复跑确认未回归，未逐项重跑浏览器取证（13 个未变文件的 UI 行为不存在变化面） |

## R-5. r2 复验汇总与声明

- **pass：7**（R2-01a~d、R2-02a、R2-03a/b、R2-04a/b/c 按断言计 13 条全过）；**fail：0**；**not_run：0**。
- r1 疑点 #1 **已修复并实测验证**：`contentVersion` 由 `blockContentVersion(planned)`（FNV-1a 内容哈希，`book-generation.ts:543-557`）在 `plannedToBlockPayload`（:559-570）写入，执行器 block-ready 载荷与即时修复路径共用；作答版本关系在生产路径上真实生效（同内容同版本、异版本旧作答如实提示）。
- r1 疑点 #2（BUILD_ID 笔误）不涉及 r2；r1 疑点 #3–#5（600ms 忙态定时器、500ms 轮询、缺 status 兼容约定）在 r2 中未改动，维持 r1 记录。
- **r2 复验通过仍只代表本地模拟执行器与本地注入场景；不代表真实服务/真实 LLM 通过。**
- 末次指纹校验一致、`git status --short` 首末均为 24 项、5176 验收服务已停止；A1 写入文件仅：本报告追加小节 + `_work/h1-books/a1/`（git 忽略）。

---

# 复验（r3 候选）

- 复验者：独立验收者 A1（只读；本节为对 r3 冻结候选的定向复验，上文 r1/r2 结论一字不改）
- 复验时间：2026-09-20 20:03–20:35（本地）
- 复验起因：收口前视觉取证发现台账 N10——活动条「已生成内容」浮层挂在 46px `overflow:hidden` 单行条内部被裁切成细缝（DOM/断言层一直绿、只有量几何才暴露）。r3 按参考结构修复：`.book-pipeline-strip-shell`（relative 锚定）→ 46px 条 → **兄弟**定位层 `.book-pipeline-detail-layer`（absolute; inset-x-0; top:100%; z-40; flex center）→ 浮层本体 `.book-pipeline-detail`（max-width:32rem; max-height:min(60vh,460px); overflow-y:auto；进场动画留在本体）。

## R3-0. r3 指纹校验（前后两次）

- `git rev-parse HEAD` → `bf460ab5ee53810679752c5104f7e2a777221d08`；分支 `codex/replica-review-20260908`；候选仍为工作树未提交。
- `apps/web/.next/BUILD_ID` → `TPMei2ra-L9r31dqKSPpl`（与 r3 JSON 一致，直接从文件读）。
- 15 文件 SHA256 与 r3 `FROZEN-CANDIDATE.json` 逐项一致，复验首末两次结果相同（`_work/h1-books/a1/r3-sha256-first.txt` / `r3-sha256-final.txt`，`diff` 为空）。
- **相对 r2 的变化面核对：恰好 4 个文件哈希变化**——`BookGenerationStrip.tsx`（`9f3ab7b7…`→`3d0267eb…`）、`BookGenerationStrip.test.tsx`（`619e0414…`→`64eec28d…`）、`styles/book-pipeline.css`（`342fbb81…`→`a0976848…`）、`tests/e2e/books-pipeline.spec.ts`（`adfd0057…`→`2dad42df…`）；**其余 11 个与 r2 完全相同**。
- `git status --short`：仍 **24 项**，与 r2 时相同；产品/测试文件集合与 r2 的差异正好是上述 4 个（无计划外文件）。源码核对：`BookGenerationStrip.tsx:101` 外壳 `book-pipeline-strip-shell`、`:162` 定位层 `book-pipeline-detail-layer`、浮层为条的**兄弟节点**；`book-pipeline.css:107-135` 与总控描述的结构一致（relative 外壳 / absolute top:100% z-40 定位层 / 32rem + min(60vh,460px) + 180ms cubic-bezier(0.16,1,0.3,1) 本体）。

## R3-1. 复跑命令清单（r3）

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | 通过 |
| `npm run lint`（`--max-warnings=0`） | 0 | 通过，0 警告 |
| `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | **46 文件 / 353 例通过**（与 r2 相同计数，符合预期） |
| `npx playwright test tests/e2e/books-pipeline.spec.ts` | 0 | **14 例通过**（预期 14：r2 的 13 例 + 新增 390 浮层用例，实测第 14 条「窄视口 390：展开浮层完整可用且不产生页面级溢出」） |
| `npx playwright test`（全量） | 0 | **168 例通过 / 0 失败**（预期 168） |

## R3-2. 定向几何取证（本轮重点；A1 自有脚本 `_work/h1-books/a1/a1-r3.spec.cjs`，5176 独立端口，msedge，种子 paused 书进入阅读器展开浮层，等 320ms 进场动画结束后测量）

| 编号 | 断言 | 1440×900 | 1920×1080 | 390×844 |
| --- | --- | --- | --- | --- |
| a | 浮层 `getBoundingClientRect` 高 > 46px（不被裁切） | **pass**：高 118px / 宽 448px | **pass**：高 118px / 宽 448px | **pass**：高 118px / 宽 322px |
| b | 右/下边界相对视口溢出 ≤ 1 | pass：右 −386.0 / 下 −419.5 | pass：右 −626.0 / 下 −599.5 | pass：右 −34.0 / 下 −217.4 |
| c | `scrollWidth − innerWidth` ≤ 1 | pass：0 | pass：0 | pass：0 |
| d | `elementFromPoint(浮层中心)` 命中浮层自身或子节点 | pass：命中 `book-pipeline-detail-chapter-title`（在浮层内） | 同左 | 同左 |
| e | 背景不透明 | pass：`rgb(255, 255, 255)` | 同左 | 同左 |
| f | 进场动画 = `book-pipeline-detail-in` / `0.18s` | pass | pass | pass |
| g | 浮层**不是** `role=status` 子节点（`closest('[role=status]')` 为空）且不在 `.book-pipeline-strip` 内 | pass（两者均 false；父节点=`book-pipeline-detail-layer`） | 同左 | 同左 |
| R3-02 | 390 下浮层宽 ≤ 390 且能读到章标题 | — | — | **pass**：宽 322px，"01 · 第一章 几何 / 已完成 4/4 块"、"02 · 第二章 浮层 / 排队" 可读 |

截图（`_work/h1-books/a1/shots/`）：`r3-detail-1440x900.png`、`r3-detail-1920x1080.png`、`r3-detail-390x844.png`——三视口浮层均完整展开于活动条正下方、覆盖在正文之上（A1 已逐张目检，1440 图中可见浮层盖在"学习提示"卡片之上、390 图中浮层完整两章行可读）。**N10 裁切缺陷在 r3 中已修复且经几何量证。**

A1 取证脚本自身两次修正（如实记录，均非产品缺陷）：书 id 含中文被 URL 编码导致 bookId 不匹配（改 ASCII id）；`openDetailAndMeasure` 首版在视口切换后未重新等活动条可见（种子改为与调试探针一致的顺序后 22 条断言全过）。首败现场保留于 `_work/h1-books/a1/.test-results/`。

## R3-3. r1/r2 结论对 r3 的延续性

| 范围 | 结论 |
| --- | --- |
| 与本次 4 文件直接相关项 | **重验通过**：活动条 46px 单行（几何取证中实测条仍在、`role=status aria-live=polite` 未变，只是浮层移出条内）、A1-01d 浮层 role/label（本轮 g 项重证 `role=dialog aria-label=已生成内容` 且已脱离 status）、r1 §4 视觉基准三视口溢出（本轮 c 项三视口重测均 0）、reduce 动画（CSS 动画仍在本体，`book-pipeline.css:133` 的 180ms 曲线逐字对照参考；r1 A1-11 的全局层压制结论不受结构移动影响）、快速开关/中断期间浮层可用（全量 e2e 168 例含原 13 条浮层断言与新 390 用例全过） |
| r1 挑刺 4 项 + r2 作答版本关系 | 4 个变化文件不触及这些链路（books-store.ts / book-generation.ts / PageReader.tsx / BooksRoute.tsx 哈希均未变），r1/r2 结论延续有效 |
| 其余 r1/r2 项 | 前轮已验、本轮未重跑浏览器取证；由全量 e2e 168/168 + 单测 353 + typecheck/lint 复跑确认无回归 |

## R3-4. r3 复验汇总与声明

- **pass：22**（三视口 a–g 21 条 + R3-02 1 条）；**fail：0**；**not_run：0**。
- N10（浮层被 46px 条裁切）修复确认成立：浮层已是条的兄弟定位层、三视口几何全部达标、`elementFromPoint` 中心命中浮层自身、背景不透明、进场动画参数逐字保持 `180ms cubic-bezier(0.16,1,0.3,1)`。
- 总控所述"非缺陷误判"（1920 首张截图半透明透出 = 进场动画中间帧截屏）与 A1 的实测一致：等 320ms 后背景为不透明白，本节 e 项即证据。
- **r3 复验通过仍只代表本地模拟执行器与本地注入场景；不代表真实服务/真实 LLM 通过。**
- 末次指纹校验一致（首末 `diff` 为空）、`git status --short` 首末均为 24 项、5176 验收服务已停止；A1 写入文件仅：本报告追加小节 + `_work/h1-books/a1/`（git 忽略）。三轮复验至此收口：**r1 pass 32/fail 0 → r2 pass（定向 13 断言）/fail 0 → r3 pass 22/fail 0，无未决缺陷由 A1 遗留。**
