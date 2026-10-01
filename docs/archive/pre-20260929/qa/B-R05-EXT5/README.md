# B-R05-EXTEND v5 证据（2026-09-19）｜R-05 收尾批

任务卡：[TASK-CARD.md](TASK-CARD.md)（含 §8 队长裁定）。起点 SHA `7b2ba5e`，实现候选 `a9c28ea`（分支 `codex/replica-review-20260908`）。
范围：R-05 视觉规范推广**收尾批**——组 A 阅读工作区（`/reading/[workspaceId]` 含 sessions 子页）；组 B `/space` 四子页（chat-history / questions / personas / cli-apps）。**本批后 R-05 已关闭**（依据见 STATUS §5.3）。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `TASK-CARD.md` | 任务卡：§2.1 阅读工作区铁律（交互保护区）、§2.2 /space 子页铁律、§3 共享层定稿（含 `reading.css` 三方共用约束）、§4 独占文件表（**I1/I3 同文件串行**）、**§8 队长裁定**（§8.1 做 9 项 / §8.2 不做 11 类 / §8.3 约束 6 条 / §8.4 I3 裁定前置） |
| `E5-GAP-LIST.md` | E5 只读取证：44 条差距；**清单 1 阅读工作区交互保护区（19 条机制 + 锚点三档分级）**；**清单 2 `reading.css` 多方共用影响面（14 类，其中 4 类被 Whisper/Writing 隐式共用）**；窄视口 N1-N8、e2e 冲突汇总 9 行、附录 A/B |
| `before/` `after/` | 两组页面 × 三视口（1440×900 / 1920×1080 / 390×844）全页 + Tab 焦点图，各 30 张 |
| `A1-REPORT.md` | 独立验收报告（结论 **pass 0 fail**；含逐项表、BUILD_ID 核对、未执行项、与实现者差异） |
| `A1-shots/` | A1 自测证据 25 张（截图 + 量测数据） |
| `shoot.mjs` | 队长前后对照截图脚本（含 390 溢出量测输出） |

## 交付内容

### 组 A 阅读工作区（`reading-ws.css` + `ReadingWorkspace.tsx` className）
- 按钮反馈过渡（150ms + `active scale(0.97)`，对照参考 `ReadingCompanion.tsx:331,351,370,383`）
- 材料 tab 长标题截断（修 E5 标为最高风险的 N1）+ 解析中 tab 旋转指示
- 错误横幅可关闭（`关闭伴生错误提示`/`关闭会话错误提示`）：**只隐藏视觉、不改 error 数据、重试仍可用**，新错误自动重显（字符串匹配式 dismissed 状态）
- 伴生栏与阅读头部形态 chip 化（会话计数 chip 由 `sessions.length` 只读派生）
- **交互保护区 19 条机制零语义改动**（diff 逐 hunk 核对；`reading.css` 与 `reading-store` 零改动）

### 组 B `/space` 四子页（`space-sections.css`）
- 卡片/列表/工具条视觉统一、会话与题库计数 chip + 刷新 spinner 态
- 题库 refreshing 变暗（对照参考 `transition-opacity + opacity-60`）
- CLI 启停状态徽标、行头窄视口 wrap
- 真实计数/筛选/搜索/批量/演示载入/来源回链（R-10）保留；`space.css` 只读

## R-09 flaky 受控诊断与修复（I3，本批最重要产出）

### 双层机制（均有直接证据）

**机制 C（CDP 读值抢跑，测试层）**：`page.mouse.wheel` 的 CDP 派发需经 compositor→命中测试→主线程，而 `Runtime.evaluate` 可后发先至。24 次决定性实验（dev 12 + prod 12）全部判定 `CDP_RACE`；wheel 到达延迟实测 **20-30ms**；失败时读到的 **179** 恰为流式早期容器贴底位置。

**机制 M（产品真实缺陷）**：流式增量拉底与用户上滚同帧竞争时，**拉回产生的 scroll 事件因 `dist<90` 把 `followBottom` 重置回 true**，用户上滚被永久吞掉。
现场探针（注入 spec 环境复刻原用例）抓到的完整序列：
```
wheel=810ms 命中容器 → scroll[810, top=0, dist=179]（上滚成功）
→ 5ms 后 scroll[815, top=179, dist=42]（流式 effect 拉回）
→ scroll[937, top=263] → scroll[998, top=212]（最终贴底 = 断言失败值）
「回到最新」可见性 [812,true] → [816,false] 证明 followBottom 被拉回的 scroll 重置
```
深层原因：`setFollowBottom(false)` 从 onScroll 到 React 提交存在延迟窗口，期间流式 effect（依赖 `turn?.text`）读到旧 state `followBottom=true` 执行拉底。

### 修复（选项 1：诊断确证 + 最小修复）
- 产品侧（`ReadingWorkspace.tsx`，仅 follow-bottom 相关）：
  - `userScrolledAwayRef`：onScroll **同步**写入用户意图，effect 拉底前检查 → 关闭 setState 提交延迟窗口
  - `programmaticScrollRef`：记录程序化拉底到达的 scrollTop，onScroll 在该窗口内仅跳过「已到达目标」的副作用滚动（用户继续上滚仍正常处理）
  - `activeId` 切换与「回到最新」显式清 ref（保持既有语义）
- spec 侧（`tests/e2e/reading.spec.ts`，仅 +4/-1）：一处 `expect` → `expect.poll`，**阈值 `<60` 与断言语义完全不变**，作用仅是吸收 20-30ms 的 CDP 派发窗口。

**为什么 v4 批"仅加 poll"失败**：poll 只吸收机制 C，会让机制 M 的真实失败（贴底 212 + 超时）暴露出来——I3 的中间版本实测「仅 poll」为 2-3/20 失败，正是该形态。两层必须一起修。

### 验证
| 检查 | 结果 |
| --- | --- |
| R-09 五例 | 5/5（I3 与 A1 各自独立复现） |
| **`--repeat-each=10`「R-09 滚动跟随」** | **10/10**（队长独立复测）与 **10/10**（A1 独立复测）；修复前同环境 **3/10 失败** |
| 加压 | I3 另跑 prod `--repeat-each=20` 两轮 20/20+20/20、dev 10/10（修复前 dev 6/10 失败） |
| 阅读 spec 全量 | 17/17 |
| 全量 e2e | 154/154 |

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck / lint（0 警告） | pass |
| unit（`--no-experimental-webstorage`） | 43 文件 297/297（与基线一致） |
| build | **队长在候选上重建**：BUILD_ID `eYs-YyFDf0XQJugH8zZcO`，mtime 2026-09-19 22:20（A1 核对一致） |
| e2e | 154/154 |
| **A1 独立验收** | **pass 0 fail**：R-09 五例 5/5、压测 10/10、阅读 17/17、space-pages 8/8、chat-source-links 21/21、chat-message-locate 12/12、**独立浏览器脚本 55/55**（滚动保持/回到最新只滚伴生容器/会话历史与草稿/错误横幅关闭后新错误重显/tab ellipsis/焦点环/reduce 压制 1e-05s/390 双抽屉/space 四子页全交互/R-10 href 形态） |
| api | 未重跑（本批零后端改动；基线 181） |

## 过程教训

**禁止在共享工作区用 `git stash` 做基线对比**：I2 为量测改动前 390 基线做了 6 秒的 `stash push`+`pop`，队长巡检恰好落在该窗口，看到「space 改动全部消失」并启动了一次误报排查（幸好 `stash list` 与 `_work/` 备份迅速澄清）。正确做法是用 `_work/` 备份副本在独立服务上对比，或直接依赖任务书给的 before 截图。已向实现者明确禁止。

## 边界与未验

- 按 §8.2 保留现状 11 类：参考伴生栏的完整聊天复用（等价于接入真实聊天服务）、滚动语义对齐 80px、会话 URL 历史降级（当前超出参考且已验收）、角色卡 hover 显隐、CLI 搜索/详情/分页、persona `read_only`、选区浮条改底部条、`dt-reader-flash` 跳转脉冲、`space.css` 断点调整、`reading.css` 4 个共用类的既有规则改动。
- A1 未执行项：turn error 横幅的浏览器实测 not_run（本地模拟无法在 UI 稳定构造失败轮次；源码审查确认与 sessionError 横幅同一 dismiss 模式）；无凭证供应商真实调用 not_run（纯前端批）。
- 动画未逐帧采样曲线/中断（MOTION_MATRIX 条目保持「实现待验收」）；触摸真机不在本批范围。
- **R-05 关闭的边界**：`待实现` 模块（partners/agents/mastery/memory/账户等）不属 R-05 范围；「部分验收」页面的功能级全状态验收仍属各自模块后续批；动画精度由 H6 总验收补齐。详见 STATUS §5.3。
