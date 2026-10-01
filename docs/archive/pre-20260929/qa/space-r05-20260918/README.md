# B-R05-SPACE-VISUAL v1 证据（2026-09-18）

任务卡：docs/STATUS.md §5（B-R05-SPACE-VISUAL v1）。起点 SHA `dae550a`，阅读批检查点 `a9ebcaa`，视觉批与最终状态见 STATUS 批次表。

## 内容

- `before-space-*.png`：改动前（HEAD dae550a 构建）`/space` 首页 1440×900 / 1920×1080 / 390×844 全页截图与 Tab 焦点图。种子数据：1 会话（IndexedDB zhiqikeyuan-chat）、2 题库、1 笔记本、3 角色（localStorage），隔离上下文，端口 5174。
- `after/space-*.png`：改动后同视口同种子截图。
- `read-first-failure-excerpt.txt`：READ-RETRY/READ-END 首败摘要（5 用例败：重试点击后 run 仍 1 次；重复/迟到 end 落库 2 份）。
- `read-after-fix-excerpt.txt`：阅读修复后 5/5 通过摘要。
- `e2e-after-excerpt.txt`：最终全量 e2e 154 passed 摘要。
- `shoot.mjs`：截图脚本（复用 tests/e2e/space-pages.spec.ts 的种子方式；reducedMotion=reduce 模拟系统减少动画）。

## 前后差异要点

- 标题/分组标签：YaHei 无衬线 → Chat Lora（var(--font-display)，与 /chat 标题同源）。
- 磁贴：右上角孤立数字 → 40px 蓝底图标块 + 大数字计数 + 单位 + ArrowUpRight（对照参考 DashboardCard）。
- 仪表盘自身不再显示"返回学习空间"（对照参考 SpaceMain isDashboard 分支；子页保留）。
- 计数失败时显示脉冲骨架（对照参考 animate-pulse）而非"…"。
- 全部磁贴跳转、演示标识（CLI 应用"（演示）"）、真实计数逻辑保留。

## 检查记录

| 检查 | 结果 |
| --- | --- |
| typecheck / lint | pass（0 警告） |
| unit（Node26 + --no-experimental-webstorage） | 43 文件 297/297（基线 292 + 新增阅读 5） |
| build | pass |
| e2e（隔离 5174 自动拉起） | 154/154 |
| api | 未重跑（本批零后端改动；基线 181 于同日现场复跑通过） |
| 键盘焦点 | Tab 焦点环截图 after/space-1440x900-focus.png |
| 减少动画 | 截图脚本以 reducedMotion='reduce' 拍摄，无动画异常 |
| 三视口 | 1440/1920/390 前后各 3 张 + 焦点图 |

## 边界与未验

- R-05 仅关闭 `/space` 首页与公共变量层切片，不关闭全站视觉统一。
- 动画逐项来源核对：磁贴 hover 上浮/阴影（参考 DashboardCard transition-all + hover:-translate-y-0.5）、计数脉冲（参考 animate-pulse）；未新增参考没有的动画。
- 触摸设备真机、1920 以外视口、真实供应商均不在本批范围。
