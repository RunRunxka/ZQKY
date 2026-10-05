# B5-DOC-AUDIT v2 小范围复核

2026-10-03，北京时间；CTRL授权 `/root/g1_doc_audit` 只读复核。此卡新增非可执行文档与JSON，不执行b5_candidate.py、app.main、测试、Git或服务，不写权威说明、产品、冻结可执行QA或旧审计结果。任务不构成B5整体关闭审核或最终精确文档字节核准。

结论：**前四项文案已修正；原件保全已独立核实零漂移；初查证据工具的一项范围/计数不符已报CTRL并修复，当前工具静态确认仅放行两项。新候选与工程绑定另验。**

## 四项文字与稳定规则

| 项目 | 当前字节复读 | 结论 |
| --- | --- | --- |
| R01 根概述/目标 | 根AGENTS第1节明确后台教案与固定学情建议已有候选源码，AI只形成待教师选择建议，CURRENT决定验收。PROJECT_GUIDE:13改为同工作台增量接入，并分开源码存在和独立验收 | 已修，符合实际BE/AI/runtime候选存在且不宣称完成 |
| R02 信封时间 | API:87改为带时区ISO8601字符串，新本地稿通常UTC，显式导入保留合法原时区/字符串拼写 | 已修，符合DraftEnvelope validator返回原字符串、完整旧稿包保留 |
| R03 B5接口时态 | API:150/359改指文末B5后台教案候选契约，独立验收/门禁只看CURRENT；旧独立`/lesson-plans/fill`规划口未混为proposals | 已修，无新增实现/验收夸称 |
| R04 准备期历史时态 | CURRENT_STATUS:22明确“B5准备期当时的实际结果（历史，随后冻结及当前进度见下文）”，尾句改“当时独立审查…” | 已修，当时未冻结事实和原首败/计数仍保留，不覆盖现行冻结进展 |

ROOT更新的lesson-plan/AGENTS和PROJECT_GUIDE§15、API B5段相互一致：默认本地规则、旧v1正文/ProcessItem/旧键保持，后台外层2与按document缓存；600ms串行、首次包/来源/编辑/加载身份冻结、unknown原包重放与409保稿；固定ready单班/KP、生产RagV2段落及confirmed/reviewed固定修订；五整字段、教师六字段保留、partial终结、历史复制/undo新保存；已知身份/最终三协议wire核验不宣称普遍匿名化；原Word/100ms打印冻结与非标准A4分页边界；0010同四库/版本感知gate。权限仍由装配owner和真实归属检查保护，没有宣称新增账号鉴权。Word/WPS人工排版、真实模型教学质量/正式迁移/Qdrant与RAG-REL保留未验边界。

这些是文案对稳定约束的核对，不等于R03～R05所有实际反例已通过。CTRL新消息确认静态v3另发现R04旧候选在新模型生成明确失败后复活，尚需新独立反例与窄修/新候选/重建。原prebuild-v1上的check实际完成由CTRL记录；完整API/业务/浏览器和最终B5门禁不能据本报告关闭。

## B5-DOC-R05：原工具归类587+4，当前已收窄589+2

[证据路径修正卡](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/B5-CTRL-EVIDENCE-PATH-DELTA-v1.md)最初声明仅两份live REPORT/README以核准G2快照保护，其他589件不可改原件实时核hash。但初查时b5_candidate.py将整个authorityDocumentsAtStart与g2Evidence交集当live例外，Windows Path.as_posix后实际有4件：REPORT、README、G2-CLOSE-MATRIX、TASK-CARDS。该原工具已保存在[b5-candidate-before-live-two-v4.bin](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-candidate-before-live-two-v4.bin)，SHA64e09190efc49978f51729d9117971b34d6497520f1c910df9636019763fccae，与本轮SHA-BEFORE捕捉工具相同。

因此原[CANDIDATE-B5-prebuild-v1.json](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-B5-prebuild-v1.json)实际记录immutableG2Count=587、authorityPreservation=4，和卡写的589+2不符。归档原字节仍保护全部四件，但工具没有对G2-CLOSE-MATRIX/TASK-CARDS两件继续施加实时原hash限制；当前这两件实际仍为原hash。本项是工具例外范围与文案不一致，未发现既有原件被破坏。

建议ROOT将live例外显式限定为本批REPORT/README两条规范路径，并断言集合恰2，其余589件继续逐项实时原hash。同时保留本次工具原字节、首败、旧candidate/原manifest，不改baseline；后续新候选及核准文件应明确记录589+2。CTRL已采纳并完成窄修：复读当前[b5_candidate.py](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5_candidate.py:60)，authorized_live只从README.md/REPORT.md构成；authority再据此过滤，authority及g2_live均断言等于该集合，其余589直接进入原hash实时核验。18:37 DELTA补记如实记录首次587+4及新工具修复，没有把原prebuild-v1追改成589+2。

本轮只静态核现行代码，并以独立只读hash核两archive及589/4136，不执行新helper。ROOT明确新helper改动在旧check/独立15与42运行结束后进行；旧check仅绑定旧QA，不能宣称工程回归已执行本轮新helper。原候选仍为587+4且原hash不变，之后必须另版记录新绑定。审计未修改工具、产品或可执行QA。

## 原件链独立核对

按baseline原hash独立读取589件应为不可改的G2文件：**589/589匹配，零缺失/漂移**。读取4136历史QA：**4136/4136匹配，零缺失/漂移**。只读核验没有访问正式业务目录或凭证。

两份live文档原字节已核：

| 文档 | baseline原hash = authority声明 = 已批准v2 after快照hash |
| --- | --- |
| REPORT | `522f24b833204b810db385ebe94c3add10491c6aaf6f30e90f24ea082ecbcf8c` |
| README | `3b9a37b43253932b8d6861c3aee92e62520eacc3f8ac62d78ab138216cf7e680` |

快照位置为 `ctrl/G2-DOC-CLOSE-CANDIDATE-v2/after/docs/qa/TEACHING-LOOP-G2-B5-20261003/{REPORT,README}.md`。实时文档哈希不同，是ROOT持续记录B5授权进度；不能据此改写或放宽589历史件。G2-CLOSE-MATRIX/TASK-CARDS的current、archive和baseline目前也全等。

原B5-BASELINE-v1 SHA `a6f8a79a4c080270f20e5890a03e606b2b9c4a7449cab3c780064fd1b430a67a`仍等冻结33的登记值；旧CANDIDATE-prebuild-v1的baselineSHA也相等。G2关闭receipt SHA `a0be17fadcae62193aaed25443e59272ea03d43f9e3df847714e673f7dc7baa3`与baseline一致；它所批准的原G2-CLOSURE-MANIFEST-r4-v2 SHA `658bbd77a91cd9a772dc1f3d30487f6a2947989254fd49612965338d7f909c9c`及独立CLOSURE-r4-v1 SHA `f1b062b92e7d6719114d7fc2d1d82bff69e3176f78ffa1422d2a081d2f4edeb4`实际匹配。baseline/原关闭件未被修改。

对应15件复读文件与保护分组的前后hash另存DOC-RECHECK-v2-SHA-BEFORE/AFTER.json；机器结论另存DOC-RECHECK-v2.json。任何获授权ROOT实时文档或工具后续修改均记录为并发变化，不能把它们当成审计写入或假报全文零漂移。本文完成后停写；整体B5关闭与最终精确文档字节另卡审核。
