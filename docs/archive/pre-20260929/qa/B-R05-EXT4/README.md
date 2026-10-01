# B-R05-EXTEND v4 证据（2026-09-19）

任务卡：[TASK-CARD.md](TASK-CARD.md)（含 §8 队长裁定）。起点 SHA `b0b24fa`，实现候选 `d54bd93`（分支 `codex/replica-review-20260908`）。
范围：R-05 视觉规范推广第四批——`/settings`（设置）与 `/lesson-plans`（教案）。**这是全站最后两个既有模块页**；本批后 R-05 仅剩「阅读工作区三栏 + `/space` 其余子页」。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `TASK-CARD.md` | 任务卡：§2 两条硬边界（模型区 contract-v1 禁区 / 教案导出与草稿链路禁区）、§3 共享层定稿、§4 独占文件表与禁区文件、§6 验收条件、**§8 队长裁定**（§8.1 做 10 项 / §8.2 不做 11 类 / §8.3 实施约束 7 条） |
| `E4-GAP-LIST.md` | E4 只读取证：两页差距 34 条（设置 21 / 教案 13，**教案已声明无 DeepTutor 参考对照**，对照对象为 /chat 基准与教案自身）；**风险清单 1（模型区可视改动风险 R1-R10）**、**风险清单 2（教案禁区 D1-D10）**；窄视口风险 N1-N5、附录 A 样式归属（含 `.settings-form` 等同名类双定义与 import 顺序事实）、附录 B 五个 spec 断言行号清单 |
| `before/` `after/` | 两页 × 三视口（1440×900 / 1920×1080 / 390×844）×（全页 + Tab 焦点图），另含 `/settings#models` 系列，各 18 张 |
| `A1-REPORT.md` | 独立验收报告（结论 **pass：33 pass / 0 fail / 4 not_run**；含 mock 前提声明、备查观察、not_run 边界） |
| `A1-shots/` | A1 自测证据 26 个文件（含导出的 `a1-export-sample.docx`，通过 `verifyDocx` 全项） |
| `shoot.mjs` | 队长前后对照截图脚本（含 390 溢出量测输出） |

种子数据（隔离上下文）：教案用 `tests/fixtures/lesson-plan.json` 注入 `zhiqikeyuan:lesson-plan:v1`（与 `lesson-plan.spec.ts:5-12` 同源）；设置页不注入数据（无后端时模型区显示错误态为预期）。

## 实施内容（I1 设置 / I2 教案）

- **共享层边界**：`globals.css`/`space.css`/`motion.css` 只读；`settings.css` 与 `lesson-plan.css` **既有规则零修改**，全部增量进新建 `settings-extend.css`（`.settings-*`）与 `lesson-visual.css`（`.lesson-*`），只消费既有变量、零 `!important`、注释无提前闭合序列。
- **设置页**：索引导航图标 + hover/current 双态 + 焦点环（保留 `aria-current="location"` 与既有 160ms 参数）、搜索框 focus 态 + 清除按钮（新名称「清除搜索」，全仓唯一）+ 无结果空态、ExtensionManager 卡片与开关视觉、外观/关于分区排版与 Toggle 轨道。
- **教案页**：表单分区/type-chip/模板缩略卡视觉、预览工具栏 hover/disabled、toast 与 storage-alert 视觉（文案与 role 未动）、导航分段微调、导出菜单进场 `lesson-menu-in 180ms`（对齐 /chat `chat-home-popup` 基准）。
- **顺带修复**：390 视口设置页起点既有的 2 处页面级 `<a>` 溢出（索引条带内预期横向滚动）实测归零。

## 双禁区守护（本批最高风险）

| 禁区 | 守护措施 | 核查结果 |
| --- | --- | --- |
| 模型区 contract-v1 | E4 风险 R1-R10；§8.3 #1 禁止写会穿透命中模型区内层同名类的 `.settings-workspace` 后代选择器；§8.3 #2 禁止改 `SettingsWorkspace` import 顺序（避免翻转 `model-settings.css` 层叠） | `features/model-settings/**` 与 `features/chat/**` `git diff` **全空**；5 处高危可访问名称锚点原样；A1 用 mock 端点复核成功态全链路通过 |
| 教案导出与草稿 | E4 禁区 D1-D10；§8.3 #5/#6 逐条约束 | `print.css`、`@page lesson-plan`、Word 映射、`DraftRepository`/防抖/flush、`pagination.ts`、`model/*`、`assets/`、`lesson-plan.css` 既有规则 **diff 全空**；14 个布局断言锚点类名保留；未新开 `@media print`；A1 导出产物通过 `verifyDocx` 全项 |

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck | pass |
| lint（`--max-warnings=0`） | pass（0 警告） |
| unit（Node26 + `--no-experimental-webstorage`） | 43 文件 297/297（与基线一致） |
| build | pass（一次通过） |
| e2e（隔离 5174 自动拉起） | **154/154**（首跑 153/154 见下） |
| api | 未重跑（本批零后端改动；基线 181） |
| **独立验收 A1** | **pass：33 pass / 0 fail / 4 not_run**——与 `after/` 六组截图逐像素 0 差异、模型区 mock 成功态全链路、`verifyDocx` 导出全项、损坏草稿不覆盖、草稿恢复与跨页返回、两新 CSS 剥离注释后 `!important` 与 `@media print` 均为 0、390 归零 |

## R-09-FLAKY 处理记录（任务书授权的顺手项）

任务书提示 `tests/e2e/reading.spec.ts` 的「R-09 滚动跟随」用例存在低频 flaky。本批实测与处置：

| 步骤 | 结果 |
| --- | --- |
| 全量 e2e 首跑 | **153/154**——仅 R-09 滚动用例失败，报 `expect(await body.evaluate((el) => el.scrollTop)).toBeLessThan(60)` 超时于 `reading.spec.ts:436` |
| 单独复跑 | 通过（1.1s） |
| 队长试加韧性（把即时断言改为 `expect.poll`，阈值与语义不变） | **无效**：`--repeat-each=6` 复现 **2/6**，失败点正是改动那行（10s 轮询超时） |
| 处置 | **已撤回该测试改动**（`git checkout -- tests/e2e/reading.spec.ts`），不保留无效改动掩盖失败 |
| 撤回后复跑全量 | **154/154 通过** |

**结论**：失败点在「用户上滚」断言，且轮询同样无法使其满足 → 不是单纯读取时序问题，疑为自动跟随回拉或 `mouse.wheel` 未命中容器。**本批对阅读模块零改动**（`reading.css`/`ReadingWorkspace.tsx`/`reading-store` 均无 diff），判为既有时序竞争。已记入 STATUS §3 `R-09-FLAKY`（观察中，未关闭），保持观察、不改断言语义与产品逻辑；如后续要修需单独立卡做受控稳定性诊断。

## 边界与未验

- 本批只关闭 R-05 中这两个页面切片，**不关闭 R-05 全站**（尚余阅读工作区三栏 + `/space` 其余子页）。
- 按 §8.2 保留现状的 11 类项：参考式导航分组折叠、页级草稿工具栏、页级加载/错误横幅、Overview 状态条/就绪面板/语言开关/Tour（含静态占位）、导航失败红点、窄视口分组下拉、模型区任何结构与 CSS 选择器改动、共享 `Modal`/`modal.css` 弹层动效、教案硬编码色替换、教案预览缩放过渡、`M-settings-nav` 参数改动。
- A1 未执行项：**真实供应商模型调用**（无凭证；**mock 通过不等于真实供应商通过**）、真实后端下模型区、打印实际调起（按任务卡）、build/e2e 全量（归队长，已跑）。
- A1 备查观察（非缺陷）：导出菜单不响应 Escape 关闭，属既有行为（`ExportMenu.tsx` 本批零改动），backdrop 关闭正常。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 条目保持「实现待验收」）；触摸真机、真实供应商不在本批范围。
