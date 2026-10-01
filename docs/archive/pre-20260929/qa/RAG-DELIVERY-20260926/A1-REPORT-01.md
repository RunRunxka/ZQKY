# A1-REPORT-01：RAG-DELIVERY-v2 安装候选的独立只读验收

验收者角色：独立验收（只读）。**未修改任何源码、测试或文档**；证据脚本与日志写在
`%TEMP%\zqky-independent\`。验收对象：已安装到 `H:\备份xuexi\智启课源` 的
`RAG-DELIVERY-v2` 候选（起点 `main@31ca45f9c83b93adc550ec7285b5017ece3ae20d`）。

## 结论

**pass（附条件）**：安装一致性与「只发布教材原文摘录」策略成立，六项自动化检查重跑无失败，
真实浏览器脚本独立复跑 34 PASS / 0 FAIL，宿主台账全为本地调用、¥0。
条件与边界见 §4、§5。

## 1. 逐项独立复验

| 项 | 结论 | 独立证据 |
| --- | --- | --- |
| 安装一致性 | 成立 | 按整棵 staging 树比对：76/76 载荷文件宿主与 staging SHA-256 全等（含 `rag_engine/**` 51 个非 pyc 文件）；差异仅 `.venv` 与 `.pyc` 编译产物，非交付内容 |
| 引擎资产 | 成立 | `manifest.json` 9/9 成员哈希匹配；`review_version=delivery-grounding-v7-extractive`；chunks 实测 `4cec9c12…` 与清单一致 |
| 只发布精确正文 | 成立 | 在**已安装**代码上核对：`grounding_review.py:198`（非 body 丢弃）、`:205-207`（唯一精确子串）、`:216-226`（坐标重算 + `validate_evidence` 复验失败即整体 withheld）、`:246-249`（`point` 取章节路径、`explanation` 取已核验原文、无 supplement）；schema 只允许模型返回 `quote_id`，文本由 `selected_review` 回填 |
| `$$…$$` 整块保留 | 成立 | 以宿主 venv 导入已安装模块实测：三行公式块产出单一单位，中间行不可单独选取；未闭合 `$$` 退回句读 |
| 四科范围 | 成立 | 已安装索引 11,608 块全为 `region=body`；四科选择器覆盖 6,745 块（58.1%），26 册非四科册被排除；`runtime.py:135-149` 无 subject 时取并集且不回退全库 |
| 自动化检查 | 成立 | 宿主 `test:api` 233 passed；`typecheck` / `lint` 通过；源项目交付 4 文件 52 passed；源全量 **1109 passed + 1 xpassed**；子集 104 passed |
| 真实浏览器 | 成立 | 独立复跑 `scripts/test-rag-delivery.mjs`：`{'pass':34,'fail':0}`，无「既非 PASS 也非 FAIL」的检查，`externalRequestsBlocked=[]`；台账 42→45（仅 1 组真实新推理，追问与 OOC 为 TTL 内缓存重放）；再次复跑 34/0 且**台账零新增、正文哈希不变**（v7 重放成立） |
| 交付文本可用性 | 成立（附弱相关项） | 数学摘录含列举法定义原文与教材对同一方程的列举示例，实质回答题目；OOC 拒答文本无引用、无快排答案、可补充，属诚实拒答 |
| 无云端调用 | 成立 | 宿主台账 45 行全 `local-ollama`、`sum(est_cost_yuan)=0.0`、0 失败；`execution_policy.py` 仅允许回环端点且不做 DNS |
| 冻结输入 | 成立 | `questions.jsonl` = `24e5c6fd…` 与预登记一致；`splits_v1.json`、`annotation_candidates_v2.jsonl`、`challenge_v1.jsonl` 与文档记录一致；mtime 均 ≤ 2026-09-22 |
| 密钥与忽略规则 | 成立 | 变更文本中无密钥材料（唯一 `ZAI_API_KEY` 命中为环境变量名）；`.local-data/`、`.env*`、`_work/`、`*.log`、`test-results/`、`.next-test/` 均被忽略 |

## 2. 被验收者更正的实现方自述

1. `delivery-state.json` 当时仍写 `prepared_not_installed` / `host_changed=false` /
   `v5_real_model_run=not_run` / `patch_files=75`，与现状矛盾。→ **已更正**：v1 原样存为
   `delivery-state-v1.json`，当前状态另写（`state=installed_and_accepted`，v5 已真实运行，
   载荷 76 文件）。
2. `host-patch.json` 在多次 `prepare` 后退化为**最后一次增量**（1/76），无法据以复验整批。
   → **已补** `host-installed.json`（全量 76 条，宿主 SHA = staging SHA），并在工具中说明该清单
   是差异清单、会被重建覆盖。
3. staging 树曾含 `.venv` 与 548 个 `.pyc`，「staging 即安装内容」在这些路径上不成立。
   → **已清理** `.venv` 之外的字节码缓存；`.venv` 保留（作为按 `uv.lock` 安装就绪的证据），
   `apply_host_delivery.py` 的 roots/白名单显式排除，`host-installed.json` 的 `note` 说明。

## 3. 验收者未能证伪但需记录的风险

- 数学第 3 条引用 `B={0,1}`（224–226 行）与题目无关 → 选择器精度问题，已登记为限制。
- 生成非确定导致跨进程结果漂移（v5 拒答 → v6 摘录）→ 已在批次 README §9 声明。
- `pyc` 头比对显示宿主按本地路径重编译；对功能无影响，但「字节级相同」不能延伸到位码缓存。

## 4. 条件

- 本验收是**工程与协议**验收：`human_quality=not_run` 不变，历史三项质量 FAIL 不变。
- 未在浏览器覆盖「模型不可用」路径（需停 Ollama），仅 API 级覆盖。
- 未执行：真机移动端浏览器、OS 级断网、`test:e2e` / `test:chat` 全量（不在本批范围）。

## 5. 未执行项与原因

| 项 | 原因 |
| --- | --- |
| 人工质量金标/段级评审 | 项目内无金标（`human_quality: not_run`），无对象可评 |
| 重做 v5/v6 模型实验 | 需实现方实验装置与新额度；改为产物内部一致性 + 台账逐行互校 + 模型 digest 比对 + 在已安装 v7 上端到端复跑 |
| 宿主 `build` / `test:unit` / `test:e2e` / `test:chat` | 不在本次授权范围（`build`/`test:unit` 已由实现方在本批运行，见 README §5） |
| `apps/api/.env` 内容 | 按密钥边界故意不读 |
| 源项目工作树全量审计 | 只核冻结输入哈希，未做全仓审计 |
