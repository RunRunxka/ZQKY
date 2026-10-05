# G1R 独立真实浏览器准备 v1

负责人 `/root/g1_resume_browser`，唯一写入本目录。产品与历史 QA 只读；不启动/停止任何监听。不占用用户浏览器；Playwright 创建独立上下文。

当前：**prepared / not_run**。收集只证明脚本能够编译并识别 2 个用例，不代表浏览器或业务通过。必须等待 CTRL 确认 5174 身份、8001 新隔离样本、适配候选冻结与实现者停写后执行。

## 种子

CTRL 在仓库根目录运行 `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/seed_browser.py`。任何 app 导入前须设置 `ZQKY_ENV=test`、`ZQKY_DATA_DIR` 为 CTRL 本批新建、已登记的系统 temp `zqky-g1-resume-browser-*/data`，以及 UTF-8/临时教材目录/测试 Qdrant 16333/不可达 embedding 9。脚本进一步拒绝非 temp、非前缀或非空旧 data。执行时元数据尚不存在；不会替换原样本或原 seed。

元数据 `browser-seed.json` 保留 `dataDir/paperId/paperRevisionId/title`，另有 `richPaperFile/richPaperSha256/delimiters/credentialsFile/scoreLeaves`。ScoresHarness 配置凭证文件必须为 None。固定正式测试卷仍 Q1=200、Q2=300、Q3=500；真实 DOCX 另存新 temp 根，保留原 3 题、2/3/5 分、原公式、材料、合并表格和图片，并加合法 OMML 默认 `|`、显式 `,` 与显式 `|` 两参数 x/y 样本。

## 浏览器边界与断言

复制旧 v00-fe 原业务链：添加学生、名单导入、转班后保留合法参测/出勤/人次；映射 F 实际 PATCH 200 延迟后编辑 G；未保存校对无确认；保存后重新承认；真实确认已提交后丢响应；冻结包重放；唯一正式成绩修订/历史矩阵。原业务断言全部保留。延迟和丢响应均 `route.fetch()` 真 API 成功后再延迟/abort，未造业务 200。

新增第二用例走真实 DOCX 上传、原卷校对保存和正式确认，使用实际知识点 API。公式校验 x/y 两个文字、每个分隔操作符和顺序、正宽高/可见/真实坐标及局部截图；三视口 1440/1920/390 保存整页截图及文档横溢检查。真实键盘 Tab/Enter 检查 :focus-visible 的 2px 轮廓。减少动画先观察实际名单按钮 hover 的 Web Animations 活跃 transition，再切 reduce 重做实际 hover，检查无运行 transition、背景在相邻帧已稳定改变；媒体查询本身不作为通过依据。

无 `webServer`、无 fallback 启动。所有日志/收据/JSON/截图/trace 输出至本批；trace 设 on。执行失败必须保留完整首败与输出，再修本目录脚本，不能改产品或放宽业务断言。每次执行设唯一 `ZQKY_G1_BROWSER_RUN`（如 first / second）；配置通过 `fileURLToPath(import.meta.url)` 解析本目录的绝对路径，输出顶层独立 `browser-artifacts-<run>` 与 `browser-results-<run>.json`，禁止后一次覆盖前一次失败。

## 已执行

仓库根目录命令：

```powershell
npx.cmd playwright test --config docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/playwright.config.ts --list 2>&1 | Tee-Object -FilePath docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/collection-first.log
```

退出 0，收集 2 个测试 / 1 文件；没有启动浏览器、没有执行用例、没有启动监听。首次未录 stdout 的同一收集输出仍存在原工具结果；此记录为第二次收集，不借此宣称重复通过。随后仅配置增加唯一运行身份，最终收集同一命令改日志名 `collection-final.log`，退出 0、仍 2 测试；准备脚本现已停写，等待 CTRL 冻结与执行许可。

`business-preservation-audit.json` 对原完整业务 test body 做严格归一化对比，仅忽略新增元数据读取和收据输出路径；字节相同，原 51 个 expect 调用完整保留。

CTRL 发现在相对 reporter 路径下，先前 collection JSON 进入本目录内嵌套 docs/qa 路径；原件全部保留未删除。按 CTRL 通知只修配置为本目录绝对路径，再收集的日志为 `collection-absolute-path.log`，退出 0、仍 2 用例；不改业务断言。
