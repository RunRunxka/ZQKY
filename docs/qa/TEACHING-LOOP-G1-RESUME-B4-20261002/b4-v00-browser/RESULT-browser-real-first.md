# B4-F-BROWSER v1 — r5 real-first 首败

真实浏览器单轮 **1 例失败，exit 1/20454ms，PID 7568 已退出**。首败 `real-browser.spec.ts:124`：已展开 12 条报告证据，图片期望 12、实际 0，15s 超时。没有重试。完整 [命令](browser-real-first-command.json)、[结果](browser-results-real-first.json)、stdout（4099 字节）/stderr（328 字节）、失败 PNG、error-context 与 trace 全保留。

准确分类为 **QA 初种子缺少来源授权上下文**，不是图片断言可以删掉：readonly 旧 teaching DB `paper_source_blocks` 计数 0，三叶 `paper_items` 全含实际受管 image assetId。真实报告 JSON 总计 12、图片块和声明均为 `blobs/868959b7a3619404d2e010a19cf7a723691dd12f1d5b20a46c805ae9b388ce5b`，前端原样送入合法纸卷资产 URL；trace 捕获 12 个 GET 404 `PAPER_ASSET_NOT_FOUND`，每个真实错误是“该资产没有被这个修订的图片块引用，不能读取。” PaperService 只放行本固定修订 `paper_source_blocks.kind=image` 引用；旧 seed 只插入题面而没插入来源块，不能放宽现有产品授权规则。

已执行并通过的前段：history 真实固定成绩链接、同学生两人次显式互斥选择、真实报告生成，4学生/4人次/3叶与 K1 2/3、K2 1/3 的字面事实核对；8 行学生依据、12 条证据展开。实际 keyboard Tab focus-visible/solid2px，正常 hover 150ms running animation、减少动画1e-05s/no running；原始 PNG RGB 变化 normal3371/reduced3367 像素。已查看失败 PNG，图片错误可见，公式/表格/材料/答案解析仍显示；尚未到三视口 layout 截图步骤，不能给整体视觉通过。

其后备注、手动补题/编辑/审阅/确认/查看入库/返回练习、练习晚响应及未知原包、双 DOCX 与名单模板下载/ZIP检查、T30转换、T60新分数确认→T70新报告、逐叶完整mapping、模型PII及旧版本最终核均 **未执行**，不能计通过。整体 B4 未关闭。

冻结身份：r5 SHA `48421bf2255ca4c55940ddb9d7c7c2869598b095c41930c82b78efdd8229ce60`，前审 exit0/185ms、后审 exit0/204ms，877产品/36QA/5契约全零漂移，next-env 一致。构建 `v3NL9Nd4Zve30UcCepg0R` /2007文件，见根 [BUILD-IDENTITY-b4-r5.json](../BUILD-IDENTITY-b4-r5.json)；仅读核磁盘 BUILD_ID 同值，root 核用户 PID24248 启动窗口，真实8001代理。

完整 trace ZIP SHA `9f0fabf05b46e39cd6ff17ee398ab680e83cf6579ca025213b175daa957bf63c`，136 entries全部CRC通过。`test.trace` 的 `Close context` / `pw:api@137` completed/end19194.287/no error，context fixture/AfterHooks和worker browser fixture均完成，证明浏览器上下文正常收尾；root统一服务资源收口，本 Agent未启动/停止服务。首轮 `ssyc3aiq` 全根与旧数据原样保留，无删除、无旧六目录操作。

只读精确 Node24 求值证明原第181行 `/practices\\?practiceSetId` 模板表达式能匹配实际预期 URL，因此没有URL过度转义缺陷，spec逐字未改。首次宽扫静态探针缺少 conversion 上下文而报 ReferenceError，其原命令/输出另存 `r5-regex-wide-read-first-*`，不冒充浏览器失败；随后只读精确行181 probe exit0。

首轮后 CTRL 授权单独 QA-R07 准备，仅seed.py补确认前完整来源块/映射和初始真实HTTP图片bytes/SHA/media预检；原 seed/spec字节before副本保留，新 seed 尚未执行，候选另冻后才可用新样本验收。首轮失败结论和原件不被改写。

