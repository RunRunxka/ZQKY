# G1R-AUDIT-ORACLE-PREP v1.4 · ready / 停写待冻结

2026-10-02。仅按 CTRL 新任务修改 `audit/v13/verify_business.mjs` 的计数范围；没有修改产品、浏览器 spec/config、三步字节重建、业务 expect 原文比较、用例名称比较、配置 SHA 或任何其他断言。

首轮 r3 审计中的 freeze 与 ZIP oracle exit0。业务 oracle exit1 的原因是 QA 将整个两例的 expect 总数硬断为51，实际总数87；它在失败前已通过三步精确重建、原/现 expect 数组逐字相同与名称比较。首败完整保留：`business-frozen-r3.log`、`business-command-frozen-r3.json`、本次另存的 `verify_business.first-source.txt`；原 mjs 和 .txt 字节 SHA 均 `ca3e8d79feeefbcfb8e447f24dd8353dc0dbbefe912a554266f7b150f15a1c52`。不能把该 QA 错误解释为产品/浏览器失败或把首轮改写为成功。

此次唯一计数修正：分别从两个 test 回调递归统计 expect 调用，第一例断言51、R08断言36、两例总数断言87，并核 old/new 分例计数相同。报告的总数及方法说明随该计数范围更新。其他比较与断言保持原样。

修正 mjs SHA256：`4332c11429f9ec49389ba727359a5c947528443665646fd7d13173af7338fdf0`。此时只是 prepared，**没有执行修正脚本**；所有可执行 QA 源停止写入，等待 CTRL r4 冻结后执行受影响独立审计。原第二轮浏览器结果保持其自身共同业务候选身份；此计数 oracle 改变不影响浏览器测试执行源或端口/代理/用户前端。
