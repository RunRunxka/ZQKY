# R-14 复现证据摘录（UX-PERF-CLOSEOUT v1，2026-09-23）

候选：`.next` BUILD_ID `ZkSw3NYEUtNUBATU0sde5`（本批修复后的构建）。
命令：`npx playwright test tests/e2e/books-commit-safety.spec.ts --repeat-each=2`
结果：第 1 轮第 3 例失败（2.2m，`expect(strip(page)).toHaveCount(0, { timeout: 120_000 })` 超时），
      第 2 轮同一用例通过（20.6s）；隔离运行 `-g "双标签页并发写不同书" --repeat-each=3` 3/3 通过。
失败页快照（Playwright error-context 中与状态判定相关的行，逐字保留）：

```
- button "重建书籍" [ref=e83] [cursor=pointer]:
```
```
- text: 重建书籍
```
```
- paragraph [ref=e88]: 阅读进度 25% · 已读 2/8 页
```
```
- generic [ref=e93]: 生成已中断（无执行器在跑）
```
```
- button "继续生成" [ref=e97] [cursor=pointer]:
```
```
- text: 继续生成
```
```
- strong [ref=e220]: 我的笔记（本地保存）
```
```
- textbox "我的笔记内容" [ref=e221]:
```
```
- text: 书A的笔记：只在书A里。
```

判定：与 STATUS §3 登记的 R-14 一致——并发写竞争下生成进入既有的**如实中断**状态
（「生成已中断（无执行器在跑）」+「继续生成」），测试假设「两本书都会自动生成完成」与该既定行为不符，
故 120s 等待「生成活动条消失」超时；**笔记与阅读进度均在，无数据丢失**。本批不修改该用例、不加等待。
