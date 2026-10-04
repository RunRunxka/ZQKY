# G2-ROOT-REVIEW v1 · CTRL 公共件只读审查

2026-10-03，北京时间。负责人 G2-BE。依赖 G2 契约 v1；原 BE 实现和证据继续停写。本卡仅写此报告，没有运行测试/服务、修改被审源码/旧证据/权威文档或执行 Git 写操作。

结论：正常原包提交、迟到收据和旧调用路径静态一致；发现 **2 处公共 API 边界的源码推导问题，待 CTRL 修复或用独立反例复核**。本报告未执行探针，不声称真实浏览器已复现，也不把它们直接等同于正常练习界面已发生的数据丢失。G2 仍待独立验收。

## ROOT-R01 · 恢复同一操作时可以替换首次编辑元数据

位置：[hooks.ts:332](../../../../apps/web/src/features/assessments/hooks.ts:332)，尤其341行。`recoverFrozen` 在已有 `previous` 时只比较 submissionId 与 payloadKey；没有比较 previous.metadata。传入对象通过各字段类型校验后，342行重新冻结传入对象，覆盖原操作。

源码可推导的调用序列：已有 unknown 操作 s1/body2，metadata 为 context p1、editGeneration2、load m1；随后恢复对象保持同 operationId/submissionId/payloadKey/body，却将 metadata 改成 p1、editGeneration3、load m2。当前判断返回 true，并把首次代次换成新代次。接下来正常未知重试沿用的已经是被改写的 metadata，调用者的 ACK 比较可能误确认新编辑。这违背 G2“首次操作身份、载荷、编辑和加载代次共同冻结”的公共契约。

建议：已有同操作时要求 operationId、contextKey、originalEditGeneration、loadGeneration 也完全一致；合法重复恢复继续使用原 `previous`，异 metadata 明确拒绝，保留现有 unknown 包。新增独立断言覆盖 unknown 之后恢复同 ID/body 但改变三个 metadata 字段，期望 false/原对象不变；完全相同包的 StrictMode 重复恢复继续 true。

当前 [公共 hook 测试](../../../../apps/web/src/features/assessments/hooks.frozen-operation.test.tsx) 已写首次深复制、unknown原代次、跨 context 发送拒绝、pending重复点击、release迟到收据、重复恢复及 payloadKey 损坏；未找到已有 previous + 异 metadata 恢复的断言。模块恢复缓存另有严格校验，本报告没有证明正常界面会制造这种恢复输入。

## ROOT-R02 · 异步离开决策期间新增会话可以漏审

位置：[navigation-guard.tsx:35](../../../../apps/web/src/services/navigation-guard.tsx:35)、[48行](../../../../apps/web/src/services/navigation-guard.tsx:48)。`requestNavigation` 只遍历开始时的 `[...guards.current]`，每个 await 后只核原 key 的 entry 仍相同。`register` 不改变 epoch，最后执行 action 前也不核整个注册集仍相同。

源码可推导的序列：开始时注册 A；A 的 guard 返回未完成 Promise；等待期间新增不同 key 的 B（B 返回 false）；A 后来返回 true。A 的 entry 没变、mounted/epoch也没变，当前逻辑会执行 action，完全不调用此时已注册的 B。公共契约“先审全部已注册会话”因此存在遗漏边界。

建议：使用注册集 revision，或保留整个 Map 身份快照并在每次 await 后/执行 action 前检查一致性；新增/替换会话应使此次决策失效，不自动延伸教师对原对象的同意。添加等待期间新增 B 拒绝/新增同意/注销重注册的行为断言；保持旧注销不能删除新同 key 注册的既有保证。

当前 [导航测试](../../../../apps/web/src/services/navigation-guard.test.tsx) 已写取消/guard错误、单个pending导航、同key旧注销保护、卸载时不导航与历史私有字段；其中“替换为另一个 document”是先注销旧 A，已有检查可以拒绝，未覆盖保留 A 同时新增 B。当前练习工作区注册一个固定 workspace key，本报告未执行界面反例来证明常规路径会新增 B。

## 其余静态核查

- `immutableSubmission` structuredClone 后递归冻结 payload 和 metadata；send 在首次操作建立时冻结 originalEditGeneration/loadGeneration，unknown 无论传入最新 payload 或代次都复用旧对象。
- send 用同步 busyRef 拒绝重复点击；success 返回包含原 operation 的 receipt；mounted/epoch失效时仅返回 current=false，不写新状态。旧 submit 仅返回 current 有效的 result，保留旧明确失败后同包复用 ID 的行为。StrictMode effect setup 恢复 mounted，cleanup 递增 epoch；recover 不自动发请求。
- WorkspaceShell 的品牌、桌面与手机菜单统一进入 requestNavigation，再调用原 beforeNavigate；其错误仍由原 onNavigationError 处理。layout 将唯一 Provider 放在公共壳外。无 Provider 的 GuardedLink 保留普通 Link，不强制 router hook，旧独立组件 host 兼容。
- 历史守卫保留 Next state 的 __NA 与私有 tree，捕获 popstate 后先还原原历史项再打开异步决定；正常接受后重走原 traversal，取消则留原项。仅恢复自己仍持有的方法包装，减少覆盖其他持有者的风险。
- 对照本地 [Next Link 文档](../../../../node_modules/next/dist/docs/01-app/03-api-reference/02-components/link.md) 的 onNavigate：修改键新标签、外部 URL 与 download 不触发此入口。此类操作不应误报为已由 SPA 导航守卫覆盖；刷新/关闭保护依赖模块 beforeunload/pagehide 和已声明缓存。

## 历史 Back 与 StrictMode 的待实际验证边界

本卡未执行任何历史遍历。必须由稳定构建浏览器实际核对：取消/保存失败/unknown 下 Back 留原编辑；允许后仅预期 traversal进入 Next handler；连续 Back/Forward 与导航按钮交叠时不会放行非预期事件；Next 与 Provider 的包装安装/StrictMode清理顺序不破坏 state；旧未标号或 primitive foreign history 使用恢复缓存时不静默丢稿。当前 `replaying` 分支按 phase 放行下一个 popstate，没有逐次匹配预期 target，快速遍历建议列独立边界观察，本报告不把它判作已复现产品缺陷。

## 审查来源 SHA256

| 文件 | 本次实际读取来源 |
| --- | --- |
| hooks.ts | 7fc5e62cb4243105e312227e78eb1470934ef2e380321014871963af01bae88f |
| navigation-guard.tsx | fad48ef4de297905af84d45994b9c6f0fb193e964f3e69a4fa9eff44e1191f70 |
| WorkspaceShell.tsx | 3303aa8c3c3ad1af8cf59c89aeeedde98fc13f5e1e930b2c26f2fb8c4e9be0d8 |
| layout.tsx | 8cce704306ca1d0ce752e258780b9cc5cb8f234ca89804f12ffecfb5b78d9d18 |
| hooks.frozen-operation.test.tsx | af6f09b231af7058cf388bffb08d1dfa71475eb65e1b80b6c13c26a9c3fa8403 |
| navigation-guard.test.tsx | 9caa2f0cfd54d62e35eeb8a5416c3acfac353ed4fe4788a057e0e4d7aa1ea868 |

后续 CTRL 修复属于新来源，不将此报告当成新源码的 PASS。未执行：公共/模块单测、类型/lint/build、API、浏览器/像素、真实模型与正式数据操作；原因是此卡明确仅只读静态审查。
