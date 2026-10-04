# B4-V00-F — ui-fixed-first

按 CTRL 授权，仅在冻结 r12-ui-fixed 候选上执行原独立 FE 组件场景一次：实际 1 文件、18/18 passed、0 failed/skip/todo；child PID17320、exit0、2143ms，外层实际 exit0。本轮未改 QA、断言或产品。

候选 `CANDIDATE-b4-r12-ui-fixed.json` SHA256 `07a8900807a6cd58c4a5231c2f9dc0bfabd034bd7ea4366644617de4a28cfc54`。执行前/后均完整核查 878 产品、43 可执行 QA、5 共享契约，全部零漂移；next-env 原字节一致。前审实际197ms、CLI 282.358ms/PID2628/exit0；后审实际195ms、CLI 278.556ms/PID19236/exit0。审计不计作业务用例。

原独立 FE 文件 SHA256 `283928976d1f3dbcfeb4e17d19dfdbed5a6f7f3b00cdec1694d0e29c5e607b44`，原配置 SHA256 `a2ba3fbb94d690fd6663abccece4067b1f611401765cec35050f9b1730ef7a80` 均未变。实际场景涵盖晚响应、409/422、dirty refresh、过期建议、unmount、未知原包重放、明确施测选择及导出固定身份；组件替身不作为真实四库或浏览器证据。

完整命令、隔离环境、PID、原始输出与18个实际用例结果分别保存在 `fe-ui-fixed-first-command.json`、`fe-ui-fixed-first-stdout.log`（4371字节）、`fe-ui-fixed-first-stderr.log`（实际0字节）、`fe-ui-fixed-first.log`、`fe-ui-fixed-first-results.json`。前后审 JSON/原始流/命令收据均保留。本轮无首败，所有旧首败和旧成功证据保持原样，不合并各轮计数。

资源：子进程自然退出；没有自有监听或浏览器上下文。本次新目录 `C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-e85_79ll` 保留，未删除；用户前端与 CTRL 后端生命周期均未操作。没有执行 seed、浏览器、服务、构建或 Git。新 UI 修复仍须绑定新构建的实际浏览器验收，不能以旧构建或本轮18组件场景关闭整个 R11/R12 门禁。

收口后仅 MD/JSON 写入，所有可执行源保持停写。CTRL 随后发现独立于本轮 FE 的 canonical check lint warning；第五 seed 尚未开始，等待新的稳定候选。
