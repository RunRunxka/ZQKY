# G2-V00-QA v4 · 首轮证据保留后的最小修正

2026-10-03，北京时间。CTRL 已批准此 QA-only 修正；产品、私有实现、旧 QA、权威文档和 Git 均未写。v4 状态 PREPARED_NOT_RERUN，等待 G2-r2 冻结及新执行卡。首轮实际失败事实在不可覆盖的 RESULT-v1.md/json，不追改成绿；browser 始终未运行。

全部 9 份 r1 可执行 QA 原字节在 run-api-first/source-snapshot/*.r1.before.txt，原 v1/v2/v3 manifest 保留。raw API receipt/log/XML、5 份 HTTP journal 与新 TEMP 四库数据全部保留。unit 在启动 Python 前被 Windows 拒绝，1173 条 source 参数路径、2361 个 requested argv 参数完整保留在 run-unit-first/LAUNCH-FAILURE-v1.*；没有重新提交该过长命令。

## 本次改动

唯一修改的可执行 QA 是 api/test_draft_receipts.py（原 SHA d5a1ffdc74644b96ac09da39f8b184c52cc2076c2a74bfffb49a286d05fece02；现 SHA 6086dcf5c2aea0a159fe447719b54a62264015d7df50fa2850bcfb5ccfeca629）。

- 11 个原测试函数采用字面短且唯一标签 g2-v00-api01 至 g2-v00-api11，知识点 code 加原数字后缀最长 13 字符，符合现行 max64 契约。journal 记录 testName/seedTag 对应。测试输入业务分数、CAS、S1/S2 包、并发数量均不变。
- 四库读取用真实公开 app.core.sqlite.open_readonly(catalog.db_path)，连接在 finally 中显式关闭。TextbookCatalog 公开 db_path/open_existing，后者不返回连接；未调用私有 _open 或不存在的方法。仍逐库执行 PRAGMA integrity_check == [('ok',)] 和 foreign_key_check == []，四库名称不变，不把失败当空库。
- 4 条 once-write 断言保留 ==1，查询严格限同 practice.draft:setId operation 与本测原 S1 submissionId；seed 自身的合法 draft 收据不计入 S1 的次数。完整业务及所有收据快照的无写/回滚等式继续保留，不放宽或删除 once-write、冲突、owner、旧收据不回退和 receipt 插入失败全回滚断言。

静态源码比对仅用标准库 ast/text/hash，不 import 或执行 QA 模块及产品。STATIC-REVIEW-v4.json 记录：11 个函数集合/顺序不变，4 条准确 S1 once-write、全部四库 integrity/FK、其他 8 个可执行 QA 文件字节未变。未跑 pytest/Vitest/Playwright/typecheck/check，也未操作服务。原预算保持 unit 23、API 11、browser 8；browser retries 0，超时不增加。

## 下一次启动约定

CTRL run_command 已批准按 --candidate 内部捕获全部 source/QA 的 before/after。unit 命令只给候选路径，严禁再次展开 --source；显式 Node24 路径仍为 C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe。Python 仍为 apps/api/.venv/Scripts/python.exe，runner 使用 ctrl/run_command.py；随后 -- 后跟 Node24、node_modules/vitest/vitest.mjs run --config 本批 unit/vitest.config.ts --reporter=default --reporter=json 和全新 run-unit-<label>/results.json。

API 仍用 ctrl/run_api.py --label <新标签> --candidate <G2-r2 路径> 本批 api/test_draft_receipts.py；G2_V00_OUTPUT 必须指向全新独占 run-api-<label>。两个 runner 各用新 TEMP，原 first 输出不能覆盖。正式 argv/env、PID/ms、source/QA 前后绑定与全部 logs/counts/skip/errors 由新运行记录保留。浏览器仍须 CTRL 单独放行真实 build/8001/5174/seed 身份；本 v4 不启动或停止任何进程。
