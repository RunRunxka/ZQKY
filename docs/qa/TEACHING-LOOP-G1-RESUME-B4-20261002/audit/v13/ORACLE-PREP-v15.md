# G1R-AUDIT-ORACLE-PREP v1.5 · ready / 停写待r5冻结

2026-10-02。CTRL在r4全量153项E2E正式结束后授权本次唯一计数修正；产品、浏览器spec/config、安装库/runtime、三步字节重建、原/现expect原文数组、名称和配置比较及其它断言未改变。

首先按原字节保存r4失败源为 `verify_business.r4-source.txt`，SHA `4332c11429f9ec49389ba727359a5c947528443665646fd7d13173af7338fdf0`。原r4 `35 !== 36` 首败log/command保留；r3 `87 !== 51` 首败及 `verify_business.first-source.txt` 也保留。

计数仅修正为第一callback51、R08callback35、模块级screenshotLayout helper1、模块total87分别断言；old/new helper计数相等，报告另记R08相关36=35+helper1。辅助函数名通过AST父链识别，业务expect原文比较没有替换或删除。

准备后新 `verify_business.mjs` SHA `3b9bdb6be44cf2478723b9f47da06b63a4360c2387e3ac8bcf6119445f7d26cf`。**此准备阶段没有执行修正脚本**；所有可执行源现停写，等待CTRL r5正式冻结后只重跑受影响oracle和冻结核查。此前真实第二浏览器与全量E2E自己的结果不因无关QA计数修正重复执行；最终引用时须绑定共同826业务、测试源、配置、代理及runtime身份，不能将准备或计数oracle当业务执行。
