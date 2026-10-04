# G3-BOUNDARY r2 独立静态复核

时间：2026-10-04T13:05:21.872785+08:00。状态：STATIC_NO_NEW_CONFIRMED_DEFECT_DYNAMIC_REQUIRED。只读产品复核；没有执行测试、浏览器或服务，没有产品写入。当前产品 SHA 与作者 FINAL STOP / ROOT r2 卡逐项相符；本报告没有用作者自测代替独立复验。

## 来源和判定边界

原 r1 来源 `CANDIDATE-G3-source-r1.json` SHA `4d7b317d093b1a42840eb49a303fc7309b5446b07ded234a45e4ae592e31422b` 已通过 ROOT check，仍被实际 SourcePanel 原反例首跑（PID 19084，exit 1，2020.119ms，1 例 8 个软断言失败）否定完整保存边界。其结果/日志/反例保持原样。r2 在原 DocumentsPanel 不变基础上改 useServerPersistence 和 SourcePanel；受控代码路径已审，原首败是否修复需 ROOT 用原断言不变复跑。

## r2 关键审查

1. `useServerPersistence.ts:161-173` 通过 live ref 捕获 documentId/loadGeneration/writeEpoch；setContext 在任何缓存/正文订阅写入之前校验当前代次与 remove_failed。旧闭包的默认 renderedSession 也必须通过 live 校验，所以 successful discard 后 React 尚未重渲染的空档不能借旧 setter 清 context。新教师操作显式 captureSession 可被接纳，不会永久 paused。
2. `SourcePanel.tsx:27-59` 有独立 discardGeneration 和来源 own epoch。只有成功 discard 递增 display generation，清旧 run/KP 载入态及 evidence/question/practice/classReady；正文新 B 的 writeEpoch 变化不会直接清已选 run。每次业务读取 owner 绑定 mode/document/store 及 live server identity；updateSelection 先确认 owner、再经 guarded setContext，最后同步 doc.selection 与 inputs。
3. `SourcePanel.tsx:61-116` 的分页前后与 Promise.all 返回、固定报告、班级及练习、证据验证均重验 owner。旧 first page 不应继续下一页，迟到结果不能提交旧 UI/error/evidence/classReady；原 6th 和新 7th 精确动态覆盖迟到回调与合法新来源保存。
4. `ServerControls.tsx:14` 的原有实际 effect 将可信 `server.cache.context` 同步到 `doc.selection.context`。此前只看 SourcePanel 自身未调用 doc.setSelection、以自定义 Controls 缺少该 effect 推断工作台 context 失配，判断范围不足，现已纠正。未执行的 UI 假设不登记为产品缺陷。追加第 8 例实际完整工作台，不复制该 effect，检查已加载未保存 A → public nav/discard → BASE 来源/完整正文/无写回 → 新编辑可保存。
5. `DocumentsPanel.tsx:65-99` 保持 r1 版本：pending history 深复制并冻结、原 CAS 与 baseline body、doc/store/load/writeEpoch/edit revision、intent 实体和值均捕获；同步 copyOwner 防双击，await 后重新核所有身份和原 CAS，不接受 fresh refresh 作为原候选自证。未发现 r2 新引入历史复制变化。历史迟到/跨文档/new intent/Undo 仍须 V00 及原 required 复验。
6. r1 删除失败/成功恢复正文守护逻辑保持：discard 先验证匹配 document+CAS+固定 revision/body，再清 timer/代次封存；removeItem 失败保留唯一输入与 raw cache、暂停隐式写；成功恢复 saved body/context 并清 Undo。keep/pagehide/flush/自动保存/业务迟到均须保持空键、保存 0；第 1-5 例审核该闭环，不能凭源码判最终验收。

## 作者证据与独立待办

作者 `impl/RESULT-v2.json` 的 AUTHOR_READY_STOP_PENDING_INDEPENDENT 记录 137/137（6 files；25 新作者例 +112 已有相关例）、direct tsc exit 0、lint exit 0，并报告三个产品 SHA 前后一致。它属于作者自检。ROOT 另消息报告 r2 check exit 0、1281 unit pass /121 files、type/lint 0、build `q84e_pxQoZ2_nwnws9QiI`、105047.583ms、source/QA 零漂移与 next-env 原字节恢复；本报告引用该运行的 ROOT 管理归因，不自行宣称浏览器完成。

待 ROOT 冻结 r2 final、执行 boundary 全 8（原 7 不改）、独立 V00 15、原 required 2、旧 27，以及真实服务与浏览器保存边界，再审日志与来源前后身份。技术 G3 尚待独立门禁；B6 未开始。本静态复核没有确认新的可复现 r2 产品缺陷，也不等同于动态 PASS。

## r2 产品身份

- `apps/web/src/features/lesson-plan/model/useServerPersistence.ts`：`4cb06c213e8a07091a510d5697e3207d373d657704274e81d9d5b943c2d1d961`
- `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`：`1452e19a77d12e843c1064283ec12d72e7ec573996b18f5d0a6a6deb0d0d2e95`
- `apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx`：`d766b73ff2852432cdd3883f236935959fd7ddd3c779b11aee388985d2e99e45`
