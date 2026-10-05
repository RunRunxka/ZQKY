# V00-P 公开保存失败忙碌状态补充 oracle

2026-10-05，g4_v00_product。由 ROOT 的 G4-BROWSER-REVIEW v1 首败授权追加。产品仍只读；本卡和独立 QA 可写。当前未运行新产品轮，等待作者 STOP、ROOT 完整 check/build 和新稳定候选。

原 `public-recovery.test.tsx` SHA `1987ba0aa9c68659f692b506ae929c8eb625ec50c5fc88c7a7b0590b20f66562` 已原字节保存为 `busy-boundary-r1-original.test.tsx.txt`，旧 first/second/third 原件未变。新文件 SHA `ddef5aeb6775bc2c103c19a7cbef36caa7ba6137a404b367bf9f0e13848d7266`。

仅在原公开 pre-send 用例中追加：发送前 save 原包写入失败并显示恢复入口后，在存储故障仍持续时，公开“重试恢复缓存”和“读取后台最新版本”必须可用；“重试原保存包”和正文课题必须保持禁用。全部原断言保留：恢复前零 HTTP、完整被冻结 payload、读回相同缓存、恢复动作本身零 HTTP、原 submissionId 和原保存包显式重放、成功 ACK 清操作。没有新增无意义案例，仍为公共 workspace 14、source 14、operation/first-selection 10，共 38。

这组 jsdom 断言覆盖公开边界，但 act 的微任务合并可能遮盖旧产品在真实浏览器中的渲染时机缺口；没有声称该补充独立重现旧产品。真实浏览器第三轮 pre-send 原 oracle 的 disabled 首败仍是产品缺陷证据；修复后必须按相同公开浏览器 oracle 完整新 11 例整轮通过。旧组件 38/38 只属于旧候选，不能转签新产品。

STOP：QA 断言已完成，尚未执行。请 ROOT 纳入新候选冻结后正式释放新完整 38 轮；禁止使用旧候选运行并归因新产品，禁止拼合轮次。
