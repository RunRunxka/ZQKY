# G3-FINAL-V00 / v1 独立结论

2026-10-04。V00对冻结候选的R01/R02正确行为、真实浏览器14项和完整原153第二轮门禁给出 **独立签收通过**。该结论使用完整新单轮结果，不把首轮152通过与诊断1通过拼接。CTRL须结合其他适用工程/API/聊天及资源证据作G3关闭决定；本报告不实施B6。

## 身份及保全

`../CANDIDATE-G3-r2-qa5.json` SHA256 `1ef1756283abc1fda103c2263c3a49034c5d3ffec4f06669c0735488134efcbb`，main@`6cb6a40db890390f0261d547213e319040f64785`，构建 `q84e_pxQoZ2_nwnws9QiI`。最终只读逐文件复核941源码、3136执行QA、33共享契约和2161生产构建SHA全部一致，next-env原字节保持。原153来自24个原spec，全部当前SHA等于冻结候选，原E2E不在相对开工的改动清单。没有改原测试、产品、依赖、网络参数或timeout。

全部精确哈希、24原spec哈希、153逐例结果、完整命令及原首败trace归因保存于 [G3-FINAL-V00-v1.json](G3-FINAL-V00-v1.json)。V00仅写本目录新非执行报告，没有权威文档/Git/服务动作，也未重跑或发HTTP请求。

## 完整原153实际结果

| 运行原件 | 实际结果 | PID / elapsed |
| --- | --- | --- |
| `../ctrl/g3-e2e-full-r2-qa5-node24-first-command.json` | 首轮152pass/1fail、0skip/0retry；原首败保留 | 21988 / 388290.997ms |
| `../ctrl/g3-e2e-kp-keyboard-diagnostic-r2-qa5-command.json` | 原同一case诊断1pass；没有合并为全153 | 21752 / 2456.962ms |
| `../ctrl/g3-e2e-full-r2-qa5-node24-second-command.json` | 第二轮原24spec全部153pass、0skip/0retry/0flaky/0error | 26492 / 394353.994ms |

独立读取第二轮 `../e2e-g3-r2-qa5-node24-second/results.json`，SHA `a1e2694512e080f4f75dd3d53d1a866ce2c823f434435063979ae43af53d1304`：153项均只有一条实际结果、status passed、retry0、errors空；顶层errors也空。JSON报告耗时393607.979ms，与执行器总耗时的746.015ms启动/退出差异分开记录。

第二轮实际执行绝对路径Node24 `C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe node_modules/@playwright/test/cli.js test --config docs/qa/TEACHING-LOOP-G3-B6-20261004/ctrl/e2e.external.config.ts`，exit0、child/log closed、source/QA漂移空数组。实际日志SHA `7640be73b228e45bc6fb764504ee3968c47177274d9e757e1cb96c5317a190ce` 与收据一致；首轮/诊断/第二轮/真实14共四份日志SHA均独立核对相符。

首轮唯一失败是 `tests/e2e/knowledge-points.spec.ts:717` 的键盘对话框场景，Enter之后line726找不到dialog。V00独立重新读取首败trace（SHA `abd1afd5892ca959763b679b42c7d499c221f952b5d74c0ce47d48ac076b44aa`），79资源CRC正常，18网络记录中真实 `/_next/static/chunks/0az8vxg2gfuhm.js` status=-1，console明确 `net::ERR_NO_BUFFER_SPACE`，业务API0次。该证据支持必要客户端chunk未加载、页面初始化受阻；没有据此推断具体OS/socket/物理内存根因，也没有证明键盘handler缺陷。保留首轮失败、独立归因和诊断原件，不把第二轮通过写为恒绿或删除历史观察。

## R01/R02与真实14签收保持

此前本候选相关独立组件15/15、原required2/2、原B5组件27/27、第三方实际Workspace/SourcePanel边界8/8的实际核查见 [UNIT-RESULT-r2.md](UNIT-RESULT-r2.md)。两原required断言仍是正确行为，过滤的4个旧错误诊断不作为产品豁免。

本候选QA5真实14单轮全部pass（PID23212、exit0、43797.925ms）；14份trace完整CRC/After Hooks通过、零error，16全文JSON和21PNG均已独立核查，21PNG全部使用view_image实际查看。详细逐例/字段/来源和图片签收见 [BROWSER-RESULT-r2-qa5.md](BROWSER-RESULT-r2-qa5.md) 及 `results/run-g3-r2-qa5-node24/independent-review/`。其文末原153首败状态是当时历史记录，本文件追加第二轮实际新状态，没有修改首败报告。

R01四尺寸390×844/1024×768/1440×900/1920×1080的真实公共导航、焦点/Enter、Next RSC延迟2056～2098ms、多定时器周期旧子树、三次恢复键null、浏览器PATCH0、完整current/history/fixed不变均已核对。

R02真实GET延迟1616～1645ms期间，完整11字段/6720字长正文/过程/恢复包/intent和v2基线保持；再次明确复制、Undo/Redo及两次真PATCH200保存v3历史正文/v4新B成立，原固定版本完整正文不变。物理双击仅1读、真CAS变化、真实成功GET后运输失败retry、不同文档迟到A均通过。来源旧GET延迟1551ms在discard后撤权，BASE正文/固定context/教师model、43分钟、要求和全部控件保持；同一保留子树内新的A/KP操作可真保存v2。四尺寸reduced-motion实际matchMedia=true与焦点键盘断言完成。

## 保留观察及边界

CV01～03、R-14跨批间歇、RAG-REL相关性问题继续保留；本轮原153通过不证明全部触发根因已消除、恒绿或全站视觉PASS。

`OBS-LP-MODE-LABEL`：OutlinePanel.tsx:139硬编码“本地工作模式 / 草稿保存在当前浏览器”，后台固定v4/v2截图仍显示；文件SHA与冻结候选一致且不属本轮改动。保留为既有体验/试用材料观察，没有发现其导致R01/R02撤权/复制/保存技术错误。B6材料应以后台固定身份和保存ACK判断业务保存状态，不以该泛化Outline文案判模式；本轮没有改产品消除文案。

V00未重新执行ROOT所属完整check/API/聊天命令，也未把原153全部截图作全站像素验收；这些需各自适用证据。真实付费Provider、教师教学质量判断、Word/WPS人工排版、V00真实14中的实际PDF保存、正式6333/正式迁移/超范围压力均未执行。原额外HTTP身份复核未重试，本轮用合法业务trace及离线构建身份绑定。未提前进行B6，也未提交/推送/部署。

**STOP：** V00独立技术验收范围已签收，全部执行QA/产品继续停写，交CTRL汇总关闭G3及决定下一任务卡。
