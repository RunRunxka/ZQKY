# main 审查证据（2026-09-22）

审查候选：`main@7a394ef`，开工工作区干净。仅审查用户指定的 main，不将默认集成分支 `feat/glass-theme` 的主题与实现计入。与上轮 `596414e` 相比，产品差异只有公共导航字体改用 `--font-ui`；书籍流水线与后端代码未变。本批没有修改产品代码。

## 方法与实际检查

- 阅读实际源码、STATUS、PROJECT_GUIDE、三矩阵、宿主与 RAG 的 AGENTS；核对本地 Git 分支与差异，未 fetch、切分支、合并或推送。
- `npm run typecheck`：通过。
- `npm run lint`：通过，0 warning。
- `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit`：46 文件，353/353。
- `npm run test:api`：181/181；Starlette/AnyIO 1 条第三方弃用警告。
- `npm run template:verify`：`original=true`、`source=true`，原件与模板源校验通过。
- 新增隔离故障探针：3/3 成功复现缺陷。**探针断言的是缺陷存在，不能作为修复验收通过数。** 所有记录均为 jsdom 临时存储，使用假时钟，无真实浏览器数据、网络或密钥。
- 本轮 build、浏览器 E2E、人工视觉/动画、真实供应商调用、RAG 模型调用与质量评测未运行；历史 build/e2e 168 通过不能标成当前重新验收。

复现命令（项目根）：

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npx.cmd vitest run --config docs/qa/main-review-20260922/book-probe.config.ts
```

## 发现及证据层级

| ID | 优先级 | 发现 | 证据与修复出口 |
| --- | --- | --- | --- |
| M22-01 | P1 | 执行器提前退出不释放资源 | `book-generation.ts:733–754` 将读取异常转换成空书；`drive:701–709` 直接 return，无 finally。删除也是同一路径。探针前两例复现：书已删除或存储暂拒后仍 `running`，心跳持续续租，恢复读取也不继续生成。统一收尾，区分删除/读取失败，保证定时器、监听、注册表与自有租约释放；删除入口停止对应任务。 |
| M22-02 | P1 | 页/块修复没有冻结任务归属，也不返回异步结果 | `book-generation.ts:988–1043` fire-and-forget；等待后重新取当前 runId，没有比较启动时身份。探针第三例换入 `replacement-run` 后，旧任务仍将第一块写为 ready；返回值确为 undefined。须 Promise/错误反馈、启动时冻结 runId 和修复操作版本、每次写入前核对、重复修复互斥及取消。仅返回 Promise 不足以解决迟到写入。 |
| M22-03 | P1（并发风险） | localStorage 租约检查与获取不是原子操作 | `book-generation.ts:630–677` 两标签可同时检查通过；后续心跳盲写，无所有权丢失停止。源码确认，**本轮未做真实双标签同时竞争复现**。使用真正互斥/带代次的所有权校验；已有单标签注册表和顺序接管测试不足。还要检查多书共享集合的读改写是否覆盖其他书的更新。 |
| M22-04 | P2 | 首次读取书籍失败被加载分支掩盖 | `BooksRoute.tsx:469–475,549–557` 只设 error、不设 books，先返回加载 UI；成功刷新也未清旧 error。源码确认，浏览器故障注入待修复批。须可见错误、重试入口与数据保护。 |
| M22-05 | P2 | 最终完成写入失败被吞掉 | `book-generation.ts:769–778` 在 finishBookRun 异常后仍设 finished 并移除句柄。持久层仍可能 compiling；同挂载自动接管又受 autoRunRef 限制。源码确认，需专门注入最后一次写失败，验证不能假报完成且有恢复入口。 |
| M22-06 | P2 | 编辑器方向键触发全局翻页 | `PageReader.tsx:153–164` 未排除输入框、contenteditable、组合输入和修饰键。源码确认，需真实笔记编辑与普通阅读两组键盘回归。 |

前述六项合并了上一轮七条观察中的“删除不停止”和“读取失败幽灵任务”，并将 M22-02 的旧任务写入新轮次升级为合成复现。不是六项都已做浏览器首败。

## RAG 勘察边界

用户提供路径 `F:\ZQKY\_RAG` 不存在；发现并核对 `F:\ZQKY_RAG`，其 AGENTS 和集成说明明确指向本宿主。RAG HEAD 为 `3b132df45cf50917a76cade711e15b3f1fce43b5`，P5–P7 大量改动和 `src/service.py` 等文件仍在未提交工作树；不能将该 HEAD 单独当作可移交实现。

已读其 STATUS、SCHEMA 对应契约、`src/service.py`、`src/contracts.py`、P6/P7 审查与旧合并方案。RAG STATUS 记载 P8A 十项问题尚未修复、段级/讲解人工质量 not_run；这些是外部项目记录，**本轮未重跑其探针或评测**。本地检索历史 Hit@5 75.8% 是节级指标，不是讲解正确率；本地 rerank 未达门槛，默认 off。旧方案“只补三处通道”及云端模型目录不适用于当前本地优先约束。

RAG 当前有同步函数 `locate_and_explain(..., deps=ServiceDeps(...))`，无独立 HTTP 服务，适合作为宿主内部适配目标；服务合同有 `ok/partial/uncertain/model_unavailable/invalid_citation`，保留 EvidenceSpan/Citation、坐标与来源散列。实际接入与性能、取消、恢复仍需专门验收。

## 进度口径

main 的原复刻目标完成度仍估计约 **48/100（约 45–51）**，为工程判断，非自动验收指标；依据功能闭环 40%、视觉 15%、真实服务 20%、动画 10%、工程质量 15%，分别暂估 43/55/27/43/84。仅用于排期，不由页面数量、测试数或 Git 提交数推导。新增 RAG 目标另列阶段，不将其独立项目的历史成果计入宿主完成量。当前状态与下一动作只见 STATUS；长期架构见 PROJECT_GUIDE。
