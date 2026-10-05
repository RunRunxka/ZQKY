# B5-REGRESSION-R8-v1 / 原完整 E2E 独立核查

负责人 `/root/b5_r06_review`；STOP UTC 2026-10-03T13:47:53.186096+00:00。只读源码／既有完整 JSON、XML、命令与日志并新增本报告和同名 JSON；未执行测试、浏览器、HTTP、服务、SQL、Git，未修改产品、QA、权威文档或旧证据。

## 独立结论

**CTRL 原完整 24 spec／153 case 新单轮 r8-first：153/153 passed，153 个 attempt，零重试、失败、跳过与 flaky。两个原 R07 用例均完整通过。** 本结论只关闭此次原 E2E 门禁的独立核查，不关闭 B5；适用聊天、视觉与资源收口由 CTRL 负责。

命令 PID13224，exit0，367124.838ms；UTC 13:38:00.277276 开始、13:44:07.684522 结束，childClosed／logsClosed true，样本保留。JSON reporter 时间为 366376.137ms，二者是不同计时范围，未混写。源／QA 命令前后零差异，next-env 前后均为原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。

## 全部用例与原两个反例

逐例读取全部 153 标题、file／line／ID、project、expectedStatus、timeout 与每次 attempt；153 均 expectedStatus=passed、结果 passed、retry=0、无首错。全局及结果 errors 均0。XML 实际153个 testcase，24个 classname、0 failure／error／skipped；XML 与 JSON 全标题多重集合一致。完整逐例审计保存在同名 JSON 的 `all153CaseAudit`，未只查总计或日志末尾。

| 原 R07 用例 | 本轮实际结果 | 原正确行为 |
| --- | --- | --- |
| lesson-plan.spec.ts:33：路由切换立即保存，返回恢复；其他页面不继承教案打印样式 | passed，1 attempt，retry0，628ms／45000ms | 编辑最后一笔→学习问答 URL与内容→print样式隔离→品牌入口→侧栏返回→课题仍为最后一笔 |
| navigation.spec.ts:54：教案编辑后经新规划入口往返不丢草稿 | passed，1 attempt，retry0，453ms／45000ms | 编辑课题→智能组卷规划页 URL与标题→返回教案→原课题仍在 |

两用例的原完整 body／断言及预算均未改。本轮没有提前许可或测试豁免；原 r5 完整单轮151 pass／2 fail保留，不以窄 B5 八例代替，也不拼接多轮为153绿。JSON没有运行 steps，不能编造执行断言次数；上述行为依据原 body完全保持及该完整 case 实际 passed。

## 配置、预算与身份

r5→r8 所有24 spec与唯一 E2E helper `book-interrupted-recovery.ts` raw SHA一致；外部配置同 raw SHA，只继承原配置并把输出隔离到本轮／使用已核前端。153 case 的 ID、标题、文件位置、project、expectedStatus 与预算逐件一致，身份差异0。workers=1，fullyParallel=false，retries=0，repeatEach=1，默认45000ms、expect10000ms；原大场景特殊预算保持。实际 timeout 分布：{180000: 4, 300000: 1, 240000: 1, 600000: 1, 120000: 1, 45000: 143, 150000: 2}。

所有 parallelIndex=0。运行结果中的 workerIndex有0、1；1仅用于末尾 replica-settings.spec.ts，是后续 worker进程编号，不能把编号数量称为并发2，也不能声称全程只有一个固定 worker进程。

唯一 test annotation差异来自原200人次×100叶规模场景的现场计时：首屏549ms相同，翻页539→543ms。原 scale注释代码与业务断言原字节保持；未将运行注释值变化当QA修改，也未从该采样宣称性能长期不变。

## 来源、构建与历史保全

候选 `CANDIDATE-B5-r8.json` SHA `c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007`，build `FVU-OXmtBh9WBSHehixfE`。本审查实际逐件复核938 source／3061 executableQA／33 frozen／2004 build／1702 prior／4136历史 raw SHA全部零差异，当前没有next-env或build派生。G2完成组为589原不可变件＋2经批准的原文archive，共591精确保持；持续更新的 live README／REPORT不混作不可变原件。

实读 `B5-R08-BUILD-BINDING-v1`：新工程check118文件／1256单测、类型、lint0警告、build全部通过，PID22916／exit0／107857.642ms，收据与绑定SHA相符。410后台文件与本候选精确一致，API1918＋1既有skip及独立42属保留结果的精确源绑定，未宣称本审查员重跑API。实际rewrite指向8001。完整8与原27的关闭依据另由对应独立报告保存，此处不重新作其视觉判断。

| 文件 | SHA-256 |
| --- | --- |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-B5-r8.json | `c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-e2e-r8-first/results.json | `8e8e9a0911ac5bb24b8c2d4b6a63bd935e492dd91585e1eaa4b442f8ce93e0ca` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-e2e-r8-first/results.xml | `68e2c63274cd7524d750fb48ac51b84b7901edb465ab9420ab97eef700a3e962` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-e2e-full-r8-first-command.json | `d07946c22dc533eb577953eaeec277dcabf722cb03d285664980b02557bcce8c` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-e2e-full-r8-first.log | `30f779c20b74caf541583ca148de7cc21bbb4af26f28cacaced3cbefb85ceb62` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-e2e-r5-first/results.json | `04d8ed09a857f6d99fa8e916aaaa8252281a1890ed252fee30b918c37a08d766` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/B5-R08-BUILD-BINDING-v1.json | `e999ba0faa3e594901c035e4a72b27b516bb0c20f13419ef3fca4be8bde9ea94` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-check-prebuild-v6-first-command.json | `b5cc7852b40cee9804d75224e2e221aa208ac2fdfea410dc04bdde31dfd6c14f` |
| playwright.config.ts | `dd32a2826a686f95a13b8b4b12c756af3beca26c0bdfe8673cc740485cfa9df0` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-e2e.external.config.ts | `ea41a2625fd56fe84006a7b7558ac370fe78f5905625945163a6de556349bd46` |
| tests/e2e/lesson-plan.spec.ts | `4cc5547138034d2bf5adf4a4a5d26d3de49427691af54c7d157e4da761fa9699` |
| tests/e2e/navigation.spec.ts | `294e784e7da93e3efbd467d96952688c4c88c74a13e84d64a2a998e76a7562fb` |
| 本次完整逐例审计 JSON | `8d9bcaa1bf5db764ce6ff41e0081b13eff820411e7d4871721197ce88f4edfe3` |

## 本轮全24 spec用例数量

| spec | 完整通过例数 |
| --- | --- |
| assessments.spec.ts | 4 |
| books-commit-safety.spec.ts | 6 |
| books-courses.spec.ts | 7 |
| books-harden.spec.ts | 6 |
| books-pipeline.spec.ts | 14 |
| chat-composer-boundaries.spec.ts | 1 |
| chat-composer.spec.ts | 2 |
| chat-context-budget.spec.ts | 4 |
| chat-deeplink.spec.ts | 7 |
| chat-home.spec.ts | 4 |
| chat.spec.ts | 4 |
| course-resource-faults.spec.ts | 9 |
| course-sessions.spec.ts | 11 |
| knowledge-points.spec.ts | 9 |
| lesson-plan.spec.ts | 9 |
| model-settings-nesting.spec.ts | 4 |
| model-settings.spec.ts | 8 |
| navigation.spec.ts | 7 |
| question-bank-real.spec.ts | 2 |
| replica-settings.spec.ts | 1 |
| settings.spec.ts | 1 |
| shell-home-nav.spec.ts | 24 |
| sidebar-chat-fixes.spec.ts | 5 |
| sidebar-transition.spec.ts | 4 |

单轮全绿不取消既有 R-14 或作者原 v5 计时观察台账。本报告未读取画面、没有视觉PASS宣称，也未接管服务。STOP：独立原153回归核查完成，无新失败；B5仍由CTRL完成其余适用门禁并决定关闭。
