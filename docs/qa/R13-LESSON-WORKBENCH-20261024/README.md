# R13 五项真机修复 + 预览复刻 DOCX（2026-10-24）

> 范围：① `/chat` 输入区模型图标/发送键；② 教案预览「三、教学目标」空白；③ 本地教案
> `NOT_FOUND` 与导出失败；④ 导出与预览两套视觉；⑤ 逻辑库删除入口。
> 本目录为**文字记录**；截图在系统临时目录 `%TEMP%\zqky-r13-shots`，未入库。

## 门禁（2026-10-24 实测）

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 后端 | `cd apps/api && uv run python -m pytest --disable-warnings` | **1953 passed / 0 failed**（430.72s；R12 基线 1946，+7） |
| 前端 | `NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit` | **88 文件 786 例**全绿（R12 基线 87/771；默认并发下 `ScoreImportPanel` 已知负载 flake，单跑 5/5，`--maxWorkers=2` 全量 786 绿） |
| 类型 / Lint | `npm.cmd run typecheck` / `npm.cmd run lint` | 0 / 0 警告 |
| 构建 | `npm.cmd run build` | 成功（15 条静态 + 2 条动态路由） |
| e2e | `npm.cmd run test:e2e` | **20 passed**（msedge；新增长模型名省略/图标对齐/发送键向上 + 预览折叠布局 + 页首表格线） |

## 修复点

1. **对话输入区**：`ModelSelector` 自带 `styles/model-selector.css`，/chat 不再缺
   `display:inline-flex; align-items:center`；长模型名 `nowrap + ellipsis`，品牌图标/文字/
   chevron 单行对齐；发送键 `ArrowDown → ArrowUp`；≤480px grid 的思考档位归位。
2. **教学目标空白**：`pagination.ts` 的 `measureCells()` 原先对目标第 2/3 行从第 1 列起算宽度，
   忽略上一行 `rowspan=3` 占列，导致 438px 正文按 113px 估算、高度放大约 4 倍；新增
   `columnOffset=1` 修正。三行可跨页拆分，续页保留空白合并标签（与 Word vMerge 一致）；
   `MIN_SPLIT_LINES=2` 让内容行像 Word 一样在页底拆 2 行。
3. **本地教案 404**：班级列表与本地记忆对账，失效 classId 清空重选；后端班级缺失改
   `CLASS_NOT_FOUND`；stale planId 导出 404 时清记忆并按当前归属新建重试一次。
4. **预览=DOCX 模板视觉**：默认排版改为模板口径（正文/标签 18.67px=14pt、band 20px=15pt、
   行距 1.714≈24pt exact、页边距 72px、段距 0、模块间距 8px、0.5pt 边框、`#8eaadb` 蓝 band、
   单元格上下 0/左右 7.2px）；页脚绝对定位、标题 22.67/40/8；旧草稿 48/16/6 一次性迁移。
   导出侧修复 `_fill_cell` 空段、`教学难点` 正则、行距 exact、`pageMargin/moduleGap` 写入、
   评价/反思空值空段、模板首行缩进；正文按 `modules` 顺序/显隐/custom 位置重建，目录同源。
5. **逻辑库删除**：DELETE 改物理删除（库行 + `library_documents` 关联；书册/原文保留），
   列表卡片与详情页补「删除逻辑库」二次确认（409 刷新提示、404 按已删处理）。

## 隔离真机视觉

- 环境：`ZQKY_DATA_DIR=%TEMP%\zqky-r13-data` 后端 8010、前端 5175（`ZQKY_ALLOWED_ORIGINS`
  含 5175）；未读写用户真实 `.local-data`。
- 数据：临时班级 + 「荷塘月色」教案（3 类目标各 10 行、教学分析长文、过程 4 阶段）。
- 预览：正文 **8 页**（第 3–10 页），页脚正文页码 1–8。
- 导出：docx **10 页**（封面 1 + 目录 1 + 正文 8），LibreOffice 转 PDF、pypdfium2 渲染逐页 PNG。
- 逐页对比第 3–10 页：断页位置、行折行、目标 vMerge 跨页、重点/难点、评价四项/反思三项、
  阶段行居中、首行缩进均一致；目标值格无空段、难点有值。
- 另用 API 导出「过程置顶 + 隐藏教学分析 + custom 插入中间」：正文 band 序列与目录均为
  `一、教学过程 / 二、基本信息 / 课前测试安排 / 三、教学目标 / 四、教学策略 / 五、评价反馈 / 六、教学反思`，
  无「教学分析」，custom 表在中间。
- `/chat` 三档（1440/900/390）：trigger `display=inline-flex`、`align-items=center`、
  高度 32/32/44px、子元素垂直中心差 0、长名单行 ellipsis、发送键含 `.lucide-arrow-up`；
  390 无横向溢出（e2e routes 覆盖）。
- 教材资料库：真实建库 → 列表卡片「删除逻辑库」→ 确认 → 提示「已彻底删除…」→ 卡片消失
  （浏览器实测；详情页分支由单测覆盖）。

## 预览折叠布局（2026-10-24 追加）

- 根因：`gridTracks` 在预览折叠时仍以固定 `left% + 8px + mid% + 0px` 结尾，剩余宽度没有轨道
  → 右侧空白；`splitter-mid` 仍可见却落在 0px 轨道；编辑栏折叠时 `splitter-left` 无对应轨道，
  预览可能进隐式行。
- 修复：轨道按可见栏生成（相邻可见栏 8px，最后一个可见栏 `minmax(0,1fr)`，单栏占满，全隐 `0px`）；
  `.preview-collapsed` 隐藏 `splitter-mid`，`.editor-collapsed.preview-collapsed` 隐藏
  `splitter-left`；预览折叠时最右侧可见栏让出 58px，避免悬浮 dock 遮住表单/滑杆数值。
- 视觉实测（1440/1280，msedge）：
  - 1440（容器 1220）：默认 `244 + 8 + 390 + 8 + 570`；隐预览 `244 + 8 + 968`；只留布局 `1220`；
    隐布局 `390 + 8 + 822`；恢复原样。四态轨道和均 = 1220。
  - 1280（容器 1060）：默认 `212 + 8 + 339 + 8 + 493`；隐预览 `212 + 8 + 840`；只留布局 `1060`；
    隐布局 `339 + 8 + 713`；恢复原样。四态轨道和均 = 1060。
  - 截图在 `%TEMP%\zqky-r13-collapse-shots`（default / hide-preview / layout-only / hide-layout /
    restored），核对无右侧空白、无隐式换行、分隔条不悬空、dock 不遮数值。
- e2e 新增「教案工作台：折叠预览/编辑后剩余栏占满，无右侧空洞与隐式换行」；
  单测新增六态 `gridTemplateColumns` 断言。

## 页首表格线（2026-10-24 追加）

- 根因：评价/反思的子项行基础样式 `.lw-sheet-subrow td.subcell { border-top: 0 }` 把**所有**
  子项行的上边框都去掉；当页首是子项续行（或 `no-top` 子项）时，表格第一行没有上边框。
- 修复：子项行默认保留上边框，只有 `.no-top` 去掉内部横线；新增
  `.lw-sheet-table.continued > tbody > tr:first-child > td { border-top: .5pt solid #000 }`，
  跨页续表页首无论首行是普通行、拆分续行还是 `no-top` 子项都补回上边框。
- 视觉实测（本地草稿，长评价/反思；1440）：
  - 预览 8 页；第 5–10 页均以续表子项开头（普通续行/`no-top`/拆分续行三种都有），
    首行 computed `border-top-width` = 1px（0.5pt），内部 `no-top` 子项仍为 0px；
    页 5/6 截图可见页顶横线，内部（三）（四）之间无横线。
  - 同一数据导出 docx → PDF 10 页（封面/目录 + 8 页正文）；PDF 第 5–8 页（正文 3–6）
    页顶均有表格上边框，docx 侧无需改动。
  - 截图与 PDF 在 `%TEMP%\zqky-r13-border-shots`（border-page-*.png / border-docx-page-*.png）。
- e2e 新增「教案预览：跨页续表页首有上边框，内部子项不重复横线」。

## 未执行 / 说明

- **视觉验收 agent 不可用**：`pdf:visual-judge` 返回账号连接不可用
  （`account-connection-unavailable`）；按备用路径由总控逐页人工核图，结论见上。
- **打印对话框未真机截图**：打印 CSS 同步了绝对页脚/页边距，仅做构建与静态规则检查。
- **深色主题未重跑**：纸面恒白、蓝 band 按纸面白底渲染；工作台其余控件沿用 R12 深色走查。
- **Word 与 LibreOffice**：视觉核对基于 LibreOffice 渲染的 PDF；Word 的实际折行可能仍有
  极少量差异，`sectionPages` 仍以预览为唯一来源。
- 临时数据目录与 5175/8010 进程在验收后清理；用户真实数据未触碰。

## 复跑

```powershell
cd apps/api; uv run python -m pytest --disable-warnings
cd ../..; $env:NODE_OPTIONS='--no-experimental-webstorage'; npm.cmd run test:unit
npm.cmd run typecheck; npm.cmd run lint; npm.cmd run build; npm.cmd run test:e2e
```

隔离真机：设 `ZQKY_DATA_DIR` 到临时目录起后端 8010，前端 `ZQKY_API_ORIGIN=http://127.0.0.1:8010`
起 5175；用 `POST /classes` + `POST /lesson-plans` 造数后走查，结束后删临时目录。
