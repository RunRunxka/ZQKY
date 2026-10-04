# G2 ROOT 两项公共边界修后静态复核

2026-10-03，北京时间。依据 CTRL 新授权只读检查修后源码；原 [ROOT-REVIEW-v1](ROOT-REVIEW-v1.md) 原文及当时 SHA 保持，报告 SHA `63ee343ff69f1d6b85224b9e4f378ed9e12f5c7c72a007a1abbd2d5fde4be449`。原 BE 候选继续停写。

**两个原静态条件均已消除，待实际测试与独立验收。** 本卡没有运行测试、浏览器或服务，没有修改被审源码。

- ROOT-R01：`recoverFrozen` 已比较原 operationId 和 metadata 的 contextKey、originalEditGeneration、loadGeneration。异体在写 frozen 前返回 false；相同包使用 previous 对象，不重新冻结覆盖。新增测试逐项改变三个 metadata 字段并要求 false/原 frozen 身份保持，相同恢复包要求 true/仍同对象。与未知重试复用原操作、StrictMode等价重复恢复的要求一致。
- ROOT-R02：新增 registrations 代次；注册、新同key替换和仍有效的移除均递增，旧已失效 unregister 不递增。requestNavigation 在开始时冻结注册代次，每个 guard await 后和执行 action 前都检查未变化；因此 A 等待期间新增 B 即使保留 A，也会取消原 action。新增测试正是这个原边界，要求不导航。

修后来源 SHA256：

| 文件 | SHA256 |
| --- | --- |
| hooks.ts | 24879cfbd35ba8dcc252b2d18c81d48975f14c5ce618f81c0a46f5a289522127 |
| navigation-guard.tsx | 8ec40ba4e8bcabfb9397251e16f72d3f0bcf5760183dff92419bd2b4c3bc80f3 |
| hooks.frozen-operation.test.tsx | 95b7c889b26f9ffca80ad9add779e1d4e643711c96fa6408ba5446747a12ca53 |
| navigation-guard.test.tsx | 7e7d41fc076bb4c6985fdecc312a34e40eadea7fc8d08af3e73fc680b30e9608 |

未执行：新增测试、原公共/模块回归、type/lint/build/API和浏览器历史链。此处仅说明源码修复与测试设计吻合，不能宣称测试实际通过；历史 Back/Forward、StrictMode与 Next 包装安装顺序的真实浏览器边界仍按原报告等待稳定构建验收。
