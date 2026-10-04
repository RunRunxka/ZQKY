# G1R 独立浏览器结果（第一轮 / 待复验）

**未通过：第一轮退出 1，0 pass / 2 timedOut；整体 G1 浏览器门禁尚未完成。**

候选 g1-resume-r1 完整 826 源 + 10 执行 QA，前/后均 0 漂移；815 旧证据无漂移，main / HEAD `6aeb57280f6a7e0d7391cad4d150745479ea58ec` 未变。详见 hash-before-first.json / hash-after-first.json。使用用户既有 5174 与 CTRL 新 temp 的 8001，未启动/停止监听，未触碰正式数据、凭证、草稿或旧六目录。

原业务用例第一处错误是取消参测后再操作被正常禁用的出勤/人次控件。正式 timeout/error-context/失败 PNG/原完整收据/原脚本和不完整 trace 全保留，见 FIRST-FAILURES.md。已按 CTRL v1.2 授权只修交互次序，原 51 个 expect 全留，当前停写等待重冻；不得将适配后的准备当复验通过。

第二 R08 实际业务体在 2636ms 完成，未出现业务断言错误，真实 DOCX 导入、保存、确认后的固定卷 totalScoreUnits=1000（10 分）、叶 200/300/500，三种分隔符两参数 x/y 的文字/操作符/几何/像素、三视口无文档横溢、Tab/Enter 可见焦点和实际减少动画均走到末尾。然而最终仍因收尾 timeout180000ms 被记 timedOut，两个 trace.zip 均无 EOCD/中央目录，故不记 R08 PASS；资源诊断由 CTRL 另派 Agent。

像素检查已查看 default-pipe-390、explicit-comma-1440、explicit-pipe-1440，x/y 和相应分隔符清晰完整；三张整页及固定确认图待 CTRL 核查。所有图在 `browser-artifacts-first/real-browser-R08-actual-DO-28ae1-board-actual-reduced-motion/`，9 个公式局部图、3 个整页图、键盘焦点图和固定确认图均已保存。

完整单次命令/环境/退出见 browser-first-command.json，stdout 见 browser-first.log，正式计数和错误见 browser-results-first.json；总运行 544.94 秒。首轮资源只读记录见 first-resources.json，runner 已退出；隔离 temp 数据保留，8001/5174 留给 CTRL 后续处理，不宣称正常无超时收尾。
