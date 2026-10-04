# B5-V00-QA v9 窄调度卡

- ID/version：B5-V00-QA-v9；负责人V00；ROOT授权时点：2026-10-03T12:30:30.842600+00:00
- 前提：r4 second原完整7pass/1fail、全部原附件与非exec独立报告先封存；ROOT API24384已专属stop退出，样本保留。
- 原因：ROOT/V00/独立R06只读trace确认 current列表button已请求真实200/currentA，但helper同步hrefBefore在Next URL commit之前；JSON下载时本已currentURL/full11，不是下载改变URL或产品失配。
- 可写：仅本批b5-v00/v9/三个新browser副本及新私有非exec manifest/readiness/static/collect receipts；原v1–v8、产品源/契约/构建/权威文档不改。同文件唯一写入者V00。
- 改动：v9 config只testDir；independent.spec.ts与v8原始字节一致；history-copy只在history→current及local→current两个列表按钮前注册真实current GET等待，点击后核GET200/完整latestA并等精确current URL（没有revisionId）、enabled当前课题内容，然后调用原fullCurrentData helper。不动helper、href/cache/full11、6 JSON、意向隔离/取消/放弃/历史/本地/固定读原断言，不force、不加预算、不减少用例。
- 验收：原完整8同名/原45s expect10s retry0 worker1；静态诊断0、收集8实际browser0；938源/33冻结/2004构建/v8manifest177旧原件rawSHA0；全部写入者STOP后ROOT另新r5冻结、新隔离API完整8单轮。不拼旧7绿，不把新等待当产品修复。
- 结果：新QA manifest SHA、精确增量（raw与归一化文本分列）、静态/收集cmd PID exit计数ms、前后source/QA/hash、TEMP保留、READY STOP与未执行runtime。
