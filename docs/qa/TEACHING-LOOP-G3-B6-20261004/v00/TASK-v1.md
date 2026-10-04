# G3-V00-v1 — 独立正确行为与真实浏览器

日期：2026-10-04。负责人：`/root/g3_v00`；总控：ROOT。起点：`main@6cb6a40db890390f0261d547213e319040f64785`。本卡执行用户本批 G3 授权，不提前开展 B6。

独占可写范围：本 `v00/` 新目录；产品源码、公共契约、旧 QA、权威进度与 Git 只读。实现停止写入且 ROOT 冻结新候选后才执行行为验收。ROOT 持有 5174/8001 服务，V00 不起停服务。

## 验收内容与当前状态

| 检查 | 准备情况 | 行为运行状态 |
| --- | --- | --- |
| R01：旧树多周期、keep/flush/pagehide、立即卸载、新 B、删除失败、pending/unknown/exclusive/auxiliary、本地稿 | `unit/discard.test.tsx`，9 例 | 未执行，待稳定候选 |
| R02：长正文与 process 编辑、恢复包/intent、正常复制/Undo、双击、失败重试、真实 CAS、切文档迟到 | `unit/history-copy.test.tsx`，6 例 | 未执行，待稳定候选 |
| R01：实际公共导航到真实 Next `/chat` 响应延迟、旧树保留超过三个600ms周期、真实FastAPI版本/完整历史不变 | `browser/g3.spec.ts`，四尺寸各一例 | 未执行，待新build及5174 |
| R02：实际业务 GET 延迟、课题/长正文/process/恢复包/intent保持，重新确认/Undo/Redo/另存固定版本 | 同上，四尺寸各一例 | 未执行，待新build及5174 |
| 浏览器：双键盘点击、真正并发CAS、成功GET后transport丢失/重试、A迟到返回与B隔离 | 同上，4 例 | 未执行，待新build及5174 |
| 390×844、1024×768、1440×900、1920×1080，焦点与reduced-motion | 随核心八场景记录截图/实际焦点/媒介状态 | 未执行 |

合计准备：15 独立组件用例、12 真实浏览器用例。原两个 required-behavior 首败由 ROOT 在本批新目录保存，旧原件保持；本表的用例数不是已通过数。

## 隔离样本与首败

标准 FastAPI 由 ROOT 在任何 `app.main` 导入前配置新 TEMP 数据根、`ZQKY_ENV=test`、`PYTHONUTF8=1`，`Settings.credentials_file=None`。`seed-v1.json` 只包含匿名隔离班级和来源绑定，不含正式学生或凭证。

首次 seed 工具 POST 班级实际 201 成功，QA 错将 ClassView 的 `id` 预期为 `classId` 导致工具退出1，保留 `seed-class.first-source.txt` 与 `seed-first-failure.json`。随后只 GET 同一已创建班级回读，未重复POST或清理数据。`recover-seed.mjs` 已 Dispose request context；独立班 id 为 `dd6d3c80ee60458ab3ccee1552d638c5`。开工 seed 的 buildId 是旧构建 `FVU-OXmtBh9WBSHehixfE`，新构建必须另存来源绑定后再浏览器验收，不能冒称旧 seed 已绑定新候选。

TypeScript parser/transpile 6文件0诊断见 `preparation-syntax-v1.json`，仅语法准备检查，不是类型检查或产品行为通过。新增第四个浏览器边界后再保存独立语法检查版本。

## 实际执行要求

每轮必须使用新的 run 标签/结果目录，`NODE_OPTIONS=--no-experimental-webstorage`，Playwright `webServer: undefined`、单 worker、0 retry、全trace。受控网络仅延迟或丢弃真实业务/Next响应，不伪造产品成功。所有后台正文与修订使用完整JSON深等；旧fixed对象与当前新修订分列。

每例独立报告 pass/fail/not_run，并保存命令、PID、时长、原日志/JSON/截图。首败不覆盖；仅 QA 夹具修正明确归因，产品后改由ROOT重冻候选。旧政策拒绝的额外HTTP身份动作不重试；浏览器合法业务trace和离线build绑定单列。

不执行真实付费Provider、教师人工质量评分、Word/WPS/PDF保存、正式6333、正式迁移、额外规模压力。它们不是本 G3 浏览器准备的通过项。ROOT适用check/API/原153E2E/14聊天另有总控收据，不拿本卡窄验代替。
