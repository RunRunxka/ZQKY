# G5-Q 作者结果 v1

R-B7A-QUALITY-01 已形成稳定修复并完成作者窄自检；此卡只交待独立冻结，不关闭 G5。仅修改 prepare_review.py、专属 test_prepare_review.py 和 README-offline-review-v1.md，证据全部写本批 quality/。

CSV 先核固定20表头、每行恰20键和20字符串值，拒绝 None 额外格（即使为空）及短行，再核固定15例顺序、四项散列和全部15个人审列为空。Markdown按外部冻结 manifest 的 caseId/title 和 case.json SHA 在内存构建现有全文空模板：15块、每块14个 ____ 空槽，共210槽；只有起始UTF-8 BOM及CRLF/CR/LF表示可归一化，未知评语/块/身份/标题/散列及任一填写槽都拒绝。两者核完才允许原空表标识和人审0输出。

首败 original-first 的固定拒绝oracle先于执行写出。两份历史反例原字节只读复制到新label、每份显式重锚新artifact-index SHA和--plan-sha；实际两次exit0/假材料PASS，外层exit1。首败、日志、原判据和新反例均保留。修复后 original-after-fix 原同字节两例都exit2且无MATERIALS发布，不修改历史反例或降低断言。

| 轮次 | 完整结果 | 实际外层执行 |
| --- | --- | --- |
| prepare-author-r2 | 49测试通过；原21方法保留、新28方法；80 CLI，0skip/retry | PID6172，23495.812ms，exit0 |
| legacy-author-r2 | 原aggregate/preflight 52测试通过、53 CLI；旧文件只读 | PID2820，4206.790ms，exit0 |
| original-after-fix | 原CSV额外格/MD填写结论2正确硬拒 | 各CLI退出2，外层退出0 |

80 CLI包括完整15、显式14且C15 unrun（原完整15行/块空表仍核）、CSV额外/短/header/集合/逐人审列/散列、MD14槽/未知正文/重复缺未知块/标题/hash、合法BOM/换行/全引号与空白多行、缺件/路径逃逸/SHA/坏ZIP/来源/覆盖/严格JSON反例。各原文档SHA与每argv/PID/时间/耗时/exit/source before/after见新label -command.json及ROUND.json；所有四类实际guard尝试0。外层加sitecustomize使原52回归的子进程也受网络/app/.env/数据库打开guard覆盖。

r1同样49/52通过，但封印前有一次证据编译首败：我将按PID保存的guard数量推作75 CLI，实际命令记录为80；Windows快速PID复用覆盖了5份外层guard，各80份专属CLI guard仍独立保存且四零。首败发生于任何RESULT发布前，失败编译器/runner/原日志与SEAL-FIRST-FAILURE保留；仅证据runner改为PID+time_ns独占文件名、编译器按实际命令计数，业务源码和原正确行为断言未改。必要的r2两整轮重新执行，最终81/54份外层guard逐命令完整保留，不能把r1/r2拼轮。

各轮源QA零漂移；旧三工具及原test_quality_tools精确SHA保持，旧1056冻结材料及正常包273引用前后全等。全部正例输出只是测试证据，不建立第二套B7交付包、不重做15例/DOCX/PDF/PNG或写人审。原正常prepared-full-v1包继续作为交付入口。

所有自有工具子进程和日志句柄已关闭，全部TEMP/首败保留。未启动服务/浏览器、导入app/main、读.env、调用网络/模型/SQL或Git。当前旧物理源仍未复核；教师、Word/WPS原生、真实模型与原B6/B7整体待验，RAG-REL OPEN。权威根文档由ROOT独占，本Agent未写。

源码/SHA、源QA与材料前后证明、完整执行资源/命令索引见RESULT-v1.json和EVIDENCE-before-result-v1.json。复跑只能新label：python -B docs/qa/TEACHING-LOOP-G5-20261005/quality/run_quality_g5.py --label <新label> --mode prepare；旧工具回归用--mode legacy；原反例复核用--mode reproduce。输出目录存在即拒覆写。

本任务STOP，等待ROOT冻结与独立V00验收；不将作者自检签成独立通过。
