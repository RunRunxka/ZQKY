# F20 首次失败记录摘录

来源：本实现者当时 functions.exec 工具返回；首轮未重定向到日志。本文件保留摘要，不能冒称完整原始 stdout。

2026-10-02 12:42:21（Asia/Shanghai）：

命令：`NODE_OPTIONS=--no-experimental-webstorage npm.cmd run test:unit -- apps/web/src/features/assessments/AssessmentsPanel.test.tsx apps/web/src/features/assessments/ScoreImportReview.test.tsx apps/web/src/features/assessments/labels.test.ts`

- exit 1；18 passed / 5 failed，失败均为 ScoreImportReview.test.tsx beforeEach：`showModal does not exist`。
- 首败由 jsdom 缺少 HTMLDialogElement.showModal/close 引起；补限定于测试文件的原型 fixture，afterEach 清除。
- 随后 narrow-02：38 passed，exit 0；没有修改确认闸门或放宽业务断言。

其他实际首败保留原始 stdout：

- f20-narrow-04.txt：49 passed / 1 failed；刷新后原表行资源正在读取，测试直接 getByLabelText 查询过早。改为 findByLabelText 等待原表行返回，仍要求校对值为 1、映射总分列为 Z，narrow-05 exit 0。
- f20-eslint-01.txt：1 error / 7 warnings；清理旧推导未使用导入、声明、捕获 effect 内同一 operation 对象，并将 fixture 声明改 const。eslint-02 exit 0。
- f20-paper-01.txt：7 passed / 1 failed；夹具只有 th，测试误 getAllByRole(cell)，缺项诊断触发 jsdom getComputedStyle 异常。改查真实存在的 columnheader；公式、table、rich payload 保全仍逐项断言。paper-02 exit 0。
