# G2-V00-QA v6 · unknown 重试第二 ACK 的真实终态等待

2026-10-03，北京时间。CTRL 新卡只授权此 QA 补强，v6 PREPARED_NOT_RUN。产品源码没有写入，未执行 unit/API/browser/check 或服务/Git 操作。

v5 browser 精确 17617 bytes（SHA b67e0a2e47c846c1c672a8df7f04a2ce0a3e0772f71b8471b90b3cc75b772292）保留为 browser/correct-behavior.spec.ts.qa-v5.before.txt。现 spec SHA b2f43b82197b23dc6c1224b53651dd260d2bb867e8f0b5cd879d305d19c8e9c6。唯一差异是插入两条真实 UI 文案等待；移除这两条新增行后，剩余字节与 v5 原件严格相等。全部原请求包深等、新输入值、后端真实结果/旧回执深等、一次备注断言及所有其他场景原字节保留。

- 草稿：原 retry requests[1]==requests[0] 深等及原包 shape 后，等待「发送的草稿已保存；之后的编辑仍保留，尚未保存，请再次保存后审核。」可见，然后才 assertRecovery 新输入3。PracticeEditor 成功 submitWithReceipt、核 operation/current/context 并接受 baseline 后才设置此终态，不以已发第二包替代 ACK 已处理。
- 备注：原 sent[1]==sent[0] 深等后，等待「原备注已追加；发送后的新备注仍保留，尚未追加。」可见，然后断言输入 B。TeacherNotes 实际定义在 LearningAnalysisWorkspace.tsx 成功 receipt/current/context/runId 检查后设置此文案，首次丢响应不会形成该终态。不使用按钮 disappearance；in-flight 标签变化不能证明 ACK。

静态复核只读 bytes/text/hash，结果写入新 manifest。未运行 TypeScript 或 QA 模块。8 browser case、retries0、原测试45000ms/expect10000ms超时、unit23/API11原预算和全部已有断言不变。v5其余8份可执行 QA 字节不变；API并发原双200/一false一true/oncewrite正确行为保留。

v1/v2所有首败、RESULT原件、logs/XML/长argv、新隔离TEMP、原source snapshots和完整四库证据保持原样。此补强是更严格的独立验收准备，不构成业务修复或已通过结论。QA 再次停写，等待 BE-v2/public 候选 G2-r3 SHA 与 CTRL 正式新执行卡。浏览器实际执行仍需单独运行身份/seed授权。
