# B4-R05/NAV 与名单测试同步 · 独立只读补审

**静态补审通过。** ReviewSession 的返回上下文接收/转发修复完整；NAV 更新保留精确断言与单一运行时登记；名单 test 的新增等待保留全部原业务断言。本轮未执行组件、单测或浏览器场景，不将静态补审等同 R05 最终关闭或稳定总候选验收。CTRL 正执行 r5 check-third，真实补题返回链仍需按已冻结浏览器安排完成。

仅写本任务新 MD/JSON。未改产品、测试或可执行 QA，未启动服务、执行 Git 或删除数据。前端约定已读 `apps/web/AGENTS.md`，相关 QuestionBank/Practice route、page-parameters、ConfirmPanel、WorkspaceShell 与 AssessmentsPanel 只读。

## 原字节等价与完整差异

CTRL 提供三份名字明确为 `r2-reconstructed.txt` 的旧源，它们不是事先保存的历史副本。本审使用独立 hashlib 验证，字节 SHA 均准确等于 `CANDIDATE-b4-r2.json` 对应路径：

| 路径 | r2 旧源 SHA256 | 当前 SHA256 |
| --- | --- | --- |
| `question-bank/ReviewWorkspace.tsx` | `042db7f4012e4b8f3c904abeabb3bf770dd70df6300c9d0b8eec59d50426935d` | `57577b9d6a8dd242750c1e0033085f925b0e5ce857649494f2dc8202c011b830` |
| `question-bank/ReviewWorkspace.test.tsx` | `bf397d68269e10c79b890bd5adbde54a88260365da8316c8c5d384c0fbcd7650` | `7d2d4d16419505827ba6cc90079646e4f955a81ebcb41c920d9f607279139d35` |
| `services/navigation.test.ts` | `168dadcdb167f2fb0564a5f377495c96428e3cb243398811a0abd028b2e65f00` | `39c3e3872651446775ee07c1eb0a01353939b2dccbef0f6ed4d16d2dc377bc4a` |

`FRONT-INTEGRATION-REVIEW.json` 保存逐文件完整 unified diff、旧源身份、AST结果与两次只读命令的完整 runtime/argv/cwd/env/stdout/stderr/elapsed/exit0/子进程和流关闭记录。产品差异当时只有上述三文件，后端与 API tests 均与已独立验收的 r2 同源；随后获授权的名单 test 变化另存补充 JSON，不覆盖首份证据。

## R05 正常/编码确认返回路径

ReviewWorkspace 产品差异只有两行：向 `<ReviewSession>` 传入 returnPracticeSetId，内部函数参数及可选类型接收同字段。原 public prop、确认后 onOpenLibrary 路径、确认包冻结、未知回执/409/失败保留等流程均原字节不变；修复使既有 callback 使用正确作用域中的 ID。

只读追溯的完整链为：PracticeEditor 手动补题入口 → QuestionBankPage 的 pageParameters → QuestionBankWorkspace 的编码 returnQuery → import review route → ReviewWorkspace → ReviewSession → ConfirmPanel 的成功按钮 → `/question-bank?returnPracticeSetId=…#library` → 现有「返回练习并重新选正式题」链接 → `/practices?practiceSetId=…`。pageParameters 拒绝重复数组、空/首尾空白或超过 200 字符；有效值传递不二次手工解码，每次固定 query 拼接使用 encodeURIComponent。

静态路径表达式核对（不是 rendered component/browser 的执行计数）：

| 输入 ID | 确认成功返回题库 | 题库返回指定练习 |
| --- | --- | --- |
| 未提供 | `/question-bank#library` | 不展示练习返回链接 |
| `practice-17` | `/question-bank?returnPracticeSetId=practice-17#library` | `/practices?practiceSetId=practice-17` |
| `practice /+?` | `/question-bank?returnPracticeSetId=practice%20%2F%2B%3F#library` | `/practices?practiceSetId=practice%20%2F%2B%3F` |

两个有值 query 的标准 URL 解码结果都与输入完全相同。新增 `it.each` 的两个组件场景分别覆盖无上下文和特殊字符：真正点击确认、等待成功按钮、点击「查看已入库题目」、核 router.push 的完整路径；使用现有 API mock，未执行于本补审。

TypeScript 5.7.3 静态 AST/token 核验：ReviewWorkspace.test 原 30 个测试定义完整 token 原样保留；157 个原 matcher 调用全部保留，新增 1 个参数化定义（实际两场景）及 1 个 matcher，合计 31 定义/158 matcher。无既有断言弱化或业务覆盖删除。产品与测试 parse diagnostics 均 0。

## NAV 单一登记与断言

运行时 `navigation.ts` 与 r2 字节相同，SHA `45ec14463af4b99e73327be105d015952bacafb9eb76c09c624c7e2033ceb43a`。静态提取登记表 16 项，id/path 均唯一；learning-analysis `/learning-analysis`、practices `/practices` 各仅一项、status=ready、main/教学工作台。WorkspaceShell 从同一 registry 与 resolveCurrentNavigationId 读取桌面和手机 current 标记，没有新增第二份运行时导航表。

navigation.test 保留 13 个测试定义与 51 matcher。唯一改变的完整 matcher 仍为 `expect(implemented.map(...)).toEqual([...])`：仅增加 learning-analysis/practices，原九项的次序和名称完全保留；未改 arrayContaining 或减少严格度。implemented.slice(2) 的逐项 ready 守卫、唯一 id/path、唯一 home、隐藏父导航与环检查均保留。既有 desktopCases 只增加两个 B4 路径→自身 id，原场景及统一解析断言不变。旧/新导航 AST parse diagnostics 均 0。

## r5 名单同步测试补审

收到 CTRL 的补充授权后，只读核 `AssessmentsWorkspace.test.r4-before.txt`，SHA 准确为 `976c6f8948d3add85ee6f5e51efbaea89541baeb6aa15c356c21c640d67276ed`。当前 test SHA `1b9e93cdaad104de92a4e8fb7e9e1906e788baae9675c6ddb2d1654f8625b72a`。反删唯一新增的 `await screen.findByTestId('assessments-roster-notice');` 后，当前字节与原件完全一致；AST 11 个原 matcher 的文本/token 全保留，旧/新 parse diagnostics 均 0。

该新增等待位于 transfer 分支，在已经等待「参测 甲」消失后、原通知完整文字断言之前。AssessmentsPanel 的学生列表读回会先反映名单，随后 useEffect 检测 removed、清理草稿并 setRosterNotice；通知因此属于后续 state render。等待实际通知出现能对应被测行为的完成信号。完整通知文字、参测/出勤/人次草稿保留、转班 request revision、写请求数量等 11 断言均继续执行；没有 sleep、放宽业务断言或改产品。

`FRONT-INTEGRATION-REVIEW-r5.json` 保留完整一行 diff、byte-exact 证据、11 matcher AST、独立两次命令完整收据。其冻结 r5 文件 SHA 为 `48421bf2255ca4c55940ddb9d7c7c2869598b095c41930c82b78efdd8229ce60`，范围 877 产品/36 执行 QA/5 契约；本审四个前端范围文件均与 r5 对应 SHA 相同，最初三文件在审查期间未变，后端/API tests 仍与 r2 同源。这里只核补审范围及后端沿用身份，不宣称根 check/build 期间的全候选终局身份。

本轮额外窄测试未执行，也未新增可执行文件。现有新增组件场景和已冻结真实 browser 规范分别覆盖特殊 ID 与实际普通 UUID 的补题确认返回。最终 check、该真实链与新构建/浏览器身份验收仍由 CTRL 组织；本静态报告完成后停止写入。
