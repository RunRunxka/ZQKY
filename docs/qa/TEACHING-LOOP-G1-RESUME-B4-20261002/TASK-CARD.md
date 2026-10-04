# G1续验+B4接续任务卡 v1

CTRL `/root`，2026-10-02。起点为新BASELINE.json登记的现场，main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，继承g1-r2完整826项及逐文件SHA。新审查未发现产品修复票，不重复八项独立测试或全量check/API。原G1/B3/新代码复查的全部证据由本批PROTECTED-EVIDENCE.json逐字节保护，next-env现场原字节另存。

授权仅G1+B4；G1全部必要门禁通过前不开始B4契约/迁移/代码。没有用户报告5174已启动时不启动/重试/改端口工具或Agent绕过旧拒绝。8001仅在根核用户就绪及服务/构建身份后用新临时根恢复，127.0.0.1，credentials_file=None，端口归属明确；不读正式.env/.local-data/凭证/草稿或旧六目录，不提交/推送/切分支/部署。最多root+3，同文件/构建/端口同时一个写入者。当前依赖为用户持有的5174就绪状态。

## G1R-E2E-ADAPT v1

负责人新Agent `/root/g1_resume_e2e`。精确可写：tests/e2e/assessments.spec.ts、tests/e2e/question-bank-real.spec.ts，以及本批adapt-e2e/**。其它测试/产品/配置/锁/权威文档/旧QA只读，无共享例外。

增加明确ZQKY_KEEP_TEST_DATA=1 opt-in：afterAll关闭并等待自有后端与日志流后，记录本轮新临时根并保留目录及api.log；默认分支仍按既有行为清理，只处理本轮自己创建且校验过的系统temp路径。不能改变业务用例集合、业务断言或API响应/默认成功口径。验证实际资源分支（保留/默认清理/子进程与日志关闭），使用新隔离样本；禁止启动Next前端或业务8001、删除未知/旧六目录。新候选冻结前自检并提供精确差异/单次命令/结果/首败/资源RESULT，ready后停写。root负责统一全量E2E配置和执行。

## G1R-V00-BROWSER-PREP v1

负责人新独立Agent `/root/g1_resume_browser`。唯一可写本批v00-browser/**，产品/原QA/权威文档只读，无共享例外。参考原v00-fe/real-browser.spec.ts与配置，复制到新路径并适配新种子元数据/收据/JSON/截图/trace/输出，不覆盖旧seed或样本。保留原完整业务链断言，新增R08真实富公式x/y及默认/显式分隔、三视口画面/横溢、键盘焦点及减少动画实际效果断言；不能仅媒体查询或MathML存在。

新seed可仅在本批目录准备（固定三叶业务契约不变，追加真实DOCX OMML审阅样本），不得执行旧seed脚本。当前仅准备/编译/收集；必须等root确认用户5174、独立8001就绪、新适配候选冻结且所有实现者停写后才执行独立浏览器。用无webServer配置，不fallback启动；response延迟/丢失必须源自真实route.fetch。不占未知端口/用户浏览器，测试上下文隔离。报告区分prepared/not_run/pass/fail，保留首败及原全断言。root独占后端/构建资源。

## G1R-AUDIT v1

v1.1负责人复用已完成且未参与本次适配的独立Agent `/root/g1_v00_fe`（新agent创建遇线程数量限制，仅调整负责人；与当前browser独立执行者不同）。唯一可写本批audit/**，其它文件只读。先核开工826原候选/新保护范围及构建8001代理；检查G1实际13产品改动对聊天的依赖影响并给是否需额外stream集成依据，不凭旧全绿。新测试适配完成后等root冻结通知，再核业务集合/断言未变、opt-in资源分支证据及新完整SHA、原件保全。不开业务服务/浏览器、不做Git写入或正式数据读取；不能把准备/收集当浏览器通过。RESULT给独立结论/命令/单次计数/限制，发现问题报root由原写入者修复。此任务不代替剩余实际浏览器/E2E门禁。

## CTRL v1与后续阶段

root独占本批root/**、无webServer全量配置、完整候选/命令/首败/矩阵/资源/报告及权威说明，登记解释器隔离环境/自有后端/端口。测试适配纳入新候选，完整826范围及新增配置/测试适配的逐文件SHA分开登记；产品未变不虚称重跑全部API/check。G1正式关闭后另立B4任务卡/DTO/DDL冻结版本，当前不派发B4实现。用户新附件收紧规则优先，T90/B5不进入。

## G1R-V00-BROWSER-PREP v1.2 / G1R-TRACE-DIAG v1

首轮正式exit1、0 pass、2 timeout保留。第一旧QA先取消参测再操作禁用出勤/人次控件；第二测试及AfterHooks合计2636ms（其中AfterHooks约130ms），最终trace合并收尾超时，两trace ZIP缺中央目录/EOCD，均不计通过。

浏览器原负责人仅可在v00-browser/real-browser.spec.ts将三步调整为先exempt、填3、再uncheck；先另存real-browser.first-source.txt原字节，全部断言及业务包保留。配置和产品源码不得改，准备完停写，等CTRL新冻结再执行。

资源原负责人仅可写adapt-e2e/trace-diag/**，用安装的Playwright同zip writer做新OS临时样本短时探针，保留结果；只读查可用Node与当前选项。不升级或切运行时，不启动业务服务，不改冻结源码/配置/依赖。收尾原因有证据后由CTRL登记最小适配范围，不能直接关闭trace隐藏超时。

## G1R-TEST-RUNTIME v1 / G1R-AUDIT v1.3

诊断有界复现：同安装mergeTraceFiles、同随机payload与两源ZIP，Node26.2.0在20秒watchdog截断ZIP，现有bundledNode24.19.0在190ms完成。小包/直接大readStream写包都正常，结论只覆盖实际大/多流yauzl→yazl合并路径，不推广成全部Node26故障。

CTRL选择本机已有`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`仅执行已安装的Playwright CLI，最终业务源、依赖锁、trace、timeout及断言保持；不下载/升级/修补node_modules，不改变或结束用户Node26前端。资源作者在原diag范围补完整ZIP entry/内容SHA/CRC核验并停写；CTRL纳入全部可执行QA重新冻结后才执行。

独立负责人`/root/g1_v00_fe` v1.3唯一可写audit/v13/**。核same-input/source/runtime身份、完整归档等效、三步次序修正与51旧断言保留、826产品/新QA/815旧证据/1979构建/next-env身份，停写准备阶段之后由CTRL下发冻结版本；不启动浏览器/服务、不改源。浏览器原负责人在新冻结通知后用该精确runtime执行全两例，另存second输出，不覆盖first。

冻结覆盖补录：r2冻结时CTRL未等audit停写确认，漏纳其在停写通知到达前创建、尚未执行的verify_business.mjs/verify_frozen.py。两文件不参与浏览器，r2原件保留；r3只增加这两核验源，共同826产品+22QA逐字不变，完整为826+24QA，SHA `21f2220b1be186e53cef0d7610ff233037e4fb1f9e6e5714916130a1543e0389`。r3前审产品/QA/815旧证据0漂移且next-env原字节匹配。新独立审计按r3执行，second业务执行保留实际起始时点及所见版本，不能称r2全QA零新增；以实际spec/config/runtime/proxy共同散列绑定后续候选。

## G1R-AUDIT-ORACLE-PREP v1.4

第二轮浏览器已正式2pass，full E2E尚未开始。审计者verify_business.mjs首轮自建oracle错误将两例总expect计数87断为51；三步字节重建、原expect数组比较与两例名称此前已正确，首败按QA缺陷保留，不登记产品失败。

唯一允许执行源改动是原负责人audit/v13/verify_business.mjs的计数范围：第一例51、R08 36、合计87分别断言；先将原冻结源以.txt原字节保存，保留原失败命令/日志。其余业务比较/断言/产品/配置禁止改。准备后停写，CTRL另冻r4，再复跑这个受影响独立oracle与稳定清单核验。浏览器业务源不变，共同SHA绑定的second2pass保持原实际执行身份；不将未冻结inline修正算最终门禁。

## G1R-AUDIT-ORACLE-PREP v1.5 / 最终审计候选r5

r4计数复验仍失败，原因是将R08相关36个callsite全部算为callback；准确AST为第一callback51、R08 callback35、模块screenshotLayout helper1=总87。原r3/r4失败和冻结源.txt均保留。完整153项E2E运行期间严格停写，正式exit0后才授权同一个mjs计数归属修正，其它比较原文与断言不变。

准备后停写，CTRL最终r5为826+24QA，manifest SHA `04fd4a41f1f883edc81917aba5ebd8dd9e00da7b0f73428a11b3c81f75e98a9f`。r5只改这个独立审计oracle，共同826产品、两个浏览器用例/config、完整E2E集合/config、runtime/build与实际2pass/153pass所见源完全相同；影响范围为独立计数审计，重冻后复跑它及清单核验。root前审0漂移、815旧证据0、next-env原字节匹配。未受影响业务不重复重跑或冒称其在r5另跑了一轮。
