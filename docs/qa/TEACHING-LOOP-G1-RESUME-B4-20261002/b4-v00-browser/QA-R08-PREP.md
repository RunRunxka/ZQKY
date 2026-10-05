# B4-F-QA-R08 v1 — 精确导航wait准备

唯一新增原spec第168行之前一行 `await expect(page).toHaveURL(...)`，等待固定127.0.0.1:5174的 `/question-bank/imports/<nonempty id>?returnPracticeSetId=本次practiceSetId` 精确路径与上下文，末尾锚定。仍随后执行原 `page.url().match(...)` 与 `not.toBeNull`。完整新SHA **`66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156`**，全部可执行源停写，新spec/seed/browser均未执行。

原r6-byte文件 `real-browser.spec.r6-before.txt` SHA `cb425d1ca424f4e59a10f9362eaa590b8d64172a7f52cf574a434fb2ff461dae` 原样保留。移除单一新增行后源码全文与原件完全一致（包括LF），原115matcher全文均保留；新116只是追加导航同步，不删/放宽业务路径、接口、PII、数字或timeout。877产品/其它35QA/5契约静态0差异。纯静态parse/精确URL字面求值exit0，旧生成页、缺return、错return、额外query或fragment均不能通过新wait；记录见 [QA-R08-static.json](QA-R08-static.json)。

全spec唯一同步 `page.url()` 读取就是该处，已先等待真实目的路由；其它现有URL检查已await toHaveURL，题干fill自带实际DOM可见/可编辑等待，因此没有无根据新增等待。证据为r6原trace的真实异步RSC导航200与原即时null断言，**后续真实GET500仍独列待CTRL诊断，未用等待掩去**。待CTRL/A审查重冻后新样本单轮执行。

