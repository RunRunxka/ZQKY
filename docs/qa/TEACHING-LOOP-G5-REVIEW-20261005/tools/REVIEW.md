# G5 空反馈校验与离线工具复核

2026-10-05，本轮只读审查 `prepare_review.py` 及固定交付材料，独立输入与日志只写本目录。结论：**R-B7A-QUALITY-01 两条旧反例均已失败闭合，未发现新的已确认问题。** 原交付包仍合格；这不是教师评价、真实模型质量或 Word/WPS 原生页核通过。

CSV 在[第85行](../../../../scripts/teaching-quality/prepare_review.py:85)先禁止多余键、[第86行](../../../../scripts/teaching-quality/prepare_review.py:86)拒缺列产生的非字符串单元格，再核完整 case 顺序、冻结散列与全部人审列空白。原额外格漏洞不能越过形状检查，合法引号内空白换行保持 CSV 语义。Markdown 在[第105行](../../../../scripts/teaching-quality/prepare_review.py:105)以固定 manifest 的 case/title 和 artifact case hash 构造全模板，[第122行](../../../../scripts/teaching-quality/prepare_review.py:122)全等检查；只归一化起始 BOM 与换行表示。`originalEmptyFeedback` 及 `humanFieldsFilled=0` 在这两种检查之后才发布。

独立新完整轮 **18 次 CLI，4 次正常、14 次预期硬拒，全部符合事先写出的[判据](ORACLE-second.json)**。这是18次工具调用，不是18个教师评分，也不是作者102项的重跑。见[逐调用记录](RESULT-second.json)、[探针](probe_quality.py)、[四类 guard](guard_cli.py)。

| 输入与预期 | 本次实际证据 |
| --- | --- |
| 两份旧反例原字节复制，新索引/计划明确重锚 SHA；均应拒绝 | [CSV旧额外格](runs-second/old-extra-cell/COMMAND.json)、[Markdown旧已填结论](runs-second/old-filled-md/COMMAND.json)：分别 exit2、`INVALID_FEEDBACK_SHAPE` / `INVALID_FEEDBACK_TEMPLATE`，均未发布 MATERIALS |
| 额外空格、末行缺格、C15结论、重复表头/案例应拒绝 | 对应 `runs-second/csv-*`，全部 exit2 |
| Markdown C15结论、附加正文、改标题/hash、缺末块应拒绝 | 对应 `runs-second/md-*`，全部 exit2 |
| 错误新散列、冻结MD索引缺件应拒绝 | [错误SHA](runs-second/csv-wrong-new-sha/COMMAND.json)、[缺件](runs-second/missing-frozen-md-entry/COMMAND.json)，均 exit2 |
| 原全集、合法 CSV 全引号及人审空白多行、MD BOM/CRLF、MD纯CR应保留 | 4正常各 exit0；humanFieldsFilled=0，executorPresent=false、budgetEnforced=false、createsHumanAuthorization=false，仍声明 live/真人/原生未验 |

所有子 CLI 日志/进程已结束，每项有实际 argv/PID/起点/耗时/退出及关闭记录。18份子 guard、[外层guard](outer-guard-second.json)及[材料独立核验guard](current-package-guard.json)均为网络/app import/.env读取/数据库打开尝试0。外层和日志使用本轮 tool 调用的实际 exit；每项 `COMMAND.json` 才是子 CLI 的执行记录。没有访问正式数据或凭证，也没有启服务、浏览器、模型或原生渲染。

另用[独立检查程序](check_current_package.py)直接读取已交付的 `prepared-full-v1`，未借生产空表函数下结论。[结果](CURRENT-PACKAGE.json)确认：273引用唯一且全部实际SHA相符，RESULT/MATERIALS/plan及三新准备文件相符；原CSV严格20列×15行且15个人审列空；MD15案例的标题/hash与CSV/manifest关联、210空槽完整；4行原生起始表所有人审身份/版本/页数/结论留空；历史PDF参考按1/8/2/2严格13行且原生状态not_run。未创建第二份交付包，正常CLI仅在新review标签生成探针证据。

本轮首个诊断 harness 在正常原包调用后误把 `realModelCalls` 从 RESULT 读取，该字段实际在 MATERIALS，导致外层 KeyError。产品正常调用已 exit0，这是审查入口错误，不是产品缺陷。保留[原脚本](probe_quality-first-failed.py)、`runs-first`、[首败说明](FIRST-FAILURE.json)、原oracle和guard；只修此字段读取，完整18例在新 `runs-second` 重跑，没有拼轮或改正确行为预期。

[新完整轮baseline](BASELINE-second.json)与 RESULT-second 的 toolDrift、originalReferenceDrift 均为空：脚本/测试/README、原273引用材料前后字节保持。额外复制输入只在本review目录重锚新SHA，没有修改原反馈/QA/权威文档或Git状态。

本次未重跑完整check、API、E2E或作者整套52/49/102，未新增应用/数据库故障实验或真实模型、教师、Word/WPS证据。固定来源canonical核查不等于旧物理SQLite/Blob恢复源重新可用；原B6/B7、RAG-REL及跨批观察状态由根报告保持。下一步可承接实际试评的授权/执行器与人工页核条件，无需重复制作离线材料包。
