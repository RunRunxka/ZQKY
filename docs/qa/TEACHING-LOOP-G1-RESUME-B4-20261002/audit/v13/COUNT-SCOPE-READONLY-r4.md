# G1R-AUDIT v1.4 · r4 计数归属只读定位 / 可执行源停写

2026-10-02。r4 冻结核对 exit0/740ms：826源、24可执行QA、815旧证据、1979构建文件全部零漂移；next-env原字节、main/HEAD、BUILD_ID和8001代理一致。manifest SHA `50ab522a939516d333abb97330c7a71ff9ab052a19842c28a6bf057179fa5c7e`。

受影响业务 oracle 在 r4 第一次执行 exit1/314ms，错误 `35 !== 36`。这仍是本审计者的 QA 计数边界错误，原 stdout/command/当前冻结源保留，不能写作此 oracle 已通过或产品失败。r3 首次 `87 !== 51` 的日志/命令和原源 .txt 同样保留。

仅读现行与第一源文件、AST 父链，得到准确静态归属：

| 位置 | AST直接 expect 调用数 | 归属 |
| --- | --- | --- |
| 第一 test callback | 51 | 第一用例 |
| R08 test callback | 35 | R08回调本身 |
| 模块级 screenshotLayout helper | 1 | R08相关 helper；不在任何 test callback 内 |
| 整模块 | 87 | 51+35+1；R08相关静态断言合计36 |

`screenshotLayout` 定义位于 [real-browser.spec.ts:187](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/real-browser.spec.ts:187)，唯一 helper expect 位于 [第199行](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/real-browser.spec.ts:199)：`expect(layout.scrollWidth - layout.width, JSON.stringify(layout)).toBeLessThanOrEqual(1)`。唯一调用点位于 R08 回调 [第316行](H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser/real-browser.spec.ts:316)，在三视口循环中调用。旧 first-source.txt 的定义/断言/调用点同位置、同文本；静态源调用数不等于循环中的动态执行次数。

两个失败轮次都在失败前已通过：仅相邻三步的字节重建、原/现整模块 expect 调用原文数组相同、两 test 名称相同；r4 还通过分例 old/new 计数相同及第一 callback=51。配置核对位于失败之后，因此不能声称这两失败命令完成了它的后续配置检查；配置保留由原 r1 独立核对和 r4 全配置文件SHA验证另行支持。

最小后续计数方案为第一callback51、R08callback35、模块helper1、总87分别断言；可另报告R08相关36=35+1。只能在 CTRL 明确登记下一版、当前153项 E2E结束、重新冻结后修正/复跑此受影响oracle。此报告不使用未冻结inline替代失败oracle，也不修改任何可执行源。

之前 r3 的 ZIP oracle exit0/372ms，88源项→46输出项/42重复跳过，每项名称/长度/CRC/解压SHA与原合并规则一致；r4仅计数oracle改变，无新的ZIP/运行时输入，不重复未受影响的ZIP探针或check/API。r2漏掉的两个新审计源在r3已纳入，共同826+22项manifest SHA完全相同，见 `r2-r3-coverage-audit.json`；不能将旧r2写成覆盖全部24项。

当前153 E2E由CTRL执行，结果尚未正式结束，此报告不写它已通过，也不关闭G1或开始B4。待CTRL登记r5计数修正；全部可执行源保持绝对停写。
