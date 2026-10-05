# 第一轮真实浏览器首败

2026-10-02，候选 g1-resume-r1，manifest SHA256 `af918cc2fe419c4fd449f4bb8fa720e762853b07dfe110192e15dc1d615aa85c`。前/后核对 826 源、10 执行 QA、815 旧证据全部 0 漂移，分支/HEAD 不变。运行结束后退出 1，JSON unexpected=2 / expected=0 / skipped=0，总耗时 544.94 秒；不能宣称 G1 浏览器通过。

第一用例 body 180140ms，spec45 行先 uncheck 参测甲，随后操作已经禁用的出勤 select；Call log 显示 `element is not enabled` 重试 352 次。现行 `AssessmentsPanel.tsx` 出勤和人次控件均 `disabled={!draft.checked || editingLocked}`，页面快照也显示甲两个控件 disabled，因此这属于原浏览器夹具交互次序错误。预期修正仅先设置 exempt/人次3，随后 uncheck，保留所有名单刷新、撤销、保存阻断、矩阵和重放断言。此文件记录时尚未改冻结脚本；须由 CTRL 另行授权修改、重冻后复跑。

第二用例实际 body 2636ms 已完成真实 DOCX 上传/原卷保存/确认、固定卷 `totalScoreUnits=1000`（10 分）与叶 200/300/500、9 公式局部截图、1440/1920/390 画面与无文档横溢、键盘 Tab/Enter 和实际减少动画；最终结果仍为 timedOut，仅错误 `Test timeout of 180000ms exceeded`，没有业务断言错误。不能将业务体完成等同整体测试通过。

实际动画 JSON：普通 hover 有 running 的 150ms transition；reduce 后 `1e-05s`、animations=[]，相邻两帧背景均 rgb(247,247,247)。局部像素已查看默认竖线390、显式逗号1440与显式竖线1440，x/y 两参数与对应分隔符均清晰完整。其余整页像素由 CTRL 继续核查。

两个 trace.zip 保留原始字节，但缺少 ZIP EOCD/中央目录，第二包由 Playwright 自带 yauzl 只读读取报 “End of central directory record signature not found / truncated”。这与业务体完成后收尾超时相符，具体机制尚在只读诊断，**不写 trace 有效、不写第二 PASS**。详见 `first-trace-diagnostic.json`。首次 yauzl 诊断失败未改文件，完整错误仍在工具结果；后续头尾签名诊断不借此重复跑业务。

全部原始 stdout/exit/JSON/PNG/上下文/收据与不完整 trace 均保留本批 first 路径。测试 runner 已退出；未启动或停止任何服务，CTRL 所持 8001 和用户 5174 留给 CTRL 后续处理。

## 经 CTRL 授权的夹具适配 v1.2

首轮正式退出、前后 0 漂移事实已提供后，CTRL 才授权调整起始三步。已先保存首轮完整脚本字节 `real-browser.first-source.txt`（SHA256 `f10eabe75d5cc463fe62d9e7b3d1b2ff6e5977d76568b99e8277b1efb1c9575e`），随后仅改为 exempt → 人次3 → uncheck；见 `order-only-v12.diff`。`git diff --no-index` 退出 1 仅表示存在差异，不是测试失败。

`business-preservation-v12-audit.json` 核完整文件除这三步顺序外字节相同，51 个原业务 expect 完整保留。新脚本 SHA256 `5ebdc2d436f01ff5133f1e5f83bf2a7db75d7d2d4de27b2b27ecaf836e5c1a51`。配置/trace 不改，第二轮未执行，已停写待 CTRL 新候选冻结。trace 资源诊断由 CTRL 另派 Agent 单独执行，本 Agent 不修改其范围。
