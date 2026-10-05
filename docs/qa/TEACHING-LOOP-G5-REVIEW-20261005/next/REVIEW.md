# B7-B 接续依赖审查（只读，2026-10-05）

本审查只核当前代码和交接条件，不执行下一批，不宣称实现执行器、模型质量或原生排版通过。阅读了根/API AGENTS、CURRENT_STATUS 最新 G5 块、G5 REPORT/B7B-HANDOFF/G5 提示词、原 v2 验收与 B7 条款、既有三个离线工具、生产教案/模型/任务代码和原 15 例质量材料。没有导入 `app.main`，没有读取 `.env`/凭证、打开数据库、网络、模型调用或服务启动；只新增本文件。没有跑测试，因此本文件无新的测试通过计数。

## 接续结论

G5 的限定两项技术关闭与下一阶段边界自洽。本分项审查只负责试评接续依赖；并行恢复审查另已确证新 P2 `R-G5-CACHE-01`：正常 ACK 删除另一标签页合法原操作恢复包。下一批先按 [恢复审查](../recovery/REVIEW.md) 最小修复并独立关闭 G6，再进入实际试评；本报告不否定该新证据或以 G5 原关闭覆盖它。

试评接续不需要重新建立教案业务模块或重新制作原 15 例准备包。需要补的是**实际模型试评的一次性受控执行与证据**，再分别取得真人教师判断、Word/WPS 原生页核；它们不是 `scope_preflight` 或工程全绿能够代替的结论。该开头于提示词后验时按新恢复报告补充，先前分项只读规划不是“无 G6 问题”的全域审查结论。

没有明确 live scope 时，可以在用户下发下一批技术任务后完成执行器的离线实现、受控 Provider 反证、总预算/尝试/恢复停止的独立技术门禁；目前用户报告 G5 结束本身不授权这项实施，也不授权收费调用。不要因真人材料未返回重复制作离线包或新建教师评分系统。

## 现有可复用入口

| 入口 | 代码位置与现有事实 | 下一批用途 |
| --- | --- | --- |
| 教案生成 API | `apps/api/app/api/v1/lesson_plans.py:88`，`POST /api/v1/lesson-plans/{lesson_id}/proposals` | 继续使用现有业务协议，不新增“质量生成”业务 API |
| 幂等创建与调度 | `apps/api/app/services/lesson_plans/service.py:206`，`generate_proposal`；同文件 `:55` 注册教案执行器 | 原包 receipt 优先；仅新接受请求 schedule；同 submission 重放不重复调用 |
| 固定来源准备 | `apps/api/app/services/lesson_generation/service.py:48` → `preparation.py:82` `prepare`；后者 `:179` 白名单核验、`:181` 冻结 profile/fingerprint | 使用 ready 固定报告、单班/所选知识点、确认题、审核练习与已核教材；不能把旧 fixture 的 profile 换个名字当 live |
| 生产请求 | `apps/api/app/services/lesson_generation/service.py:51` `build_request`，`:57` 输出 cap，`:70` 最终协议输出预算检查 | 复用 SYSTEM_PROMPT、匿名 modelPayload、既有协议体与隐私核验；执行器不得另写更容易通过的提示词 |
| 实际模型调用 | 同文件 `:99` `execute`，`:122` `provider.complete` | 在这一真实 Provider 调用边界前后登记预算/尝试与原始文本证据，不旁路生产候选验证 |
| Resolver | `apps/api/app/services/model_runtime.py:178` `resolve_chat_model`；`:134` `resolve_frozen_model`；`:124` `fingerprint_of_handle` | 生产连接/模型与冻结指纹核对。当前指纹不是完整请求参数指纹，见下文 |
| Provider | `apps/api/app/providers/llm/base.py:323` `LLMProvider.complete`；`:261` `post_json` | 既有 complete → _complete → HTTP，不新增模型访问库；现 post_json 没有代码级自动重试循环 |
| 用量 | `apps/api/app/providers/llm/base.py:76` `LLMUsage`；`:95` `LLMResponse.usage`；三协议适配器均可返回 input/output tokens | 用量可能为 None，且现 lesson execute 未保存 response.usage；当前 proposal API 没有实际费用/用量字段 |
| 任务 | `apps/api/app/services/jobs/engine.py:146` `run_job`、`:189` `schedule`、`:228` `shutdown`；`apps/api/app/api/v1/workflow_jobs.py:79` retry | 沿用租约、取消、同事务发布及显式 retry。JobEngine model_limit=1 控制并发，不是总费用/次数控制 |
| 来源验证 | `apps/api/app/services/rag_v2/service.py:253` `verify_selected_evidence`；`apps/api/app/services/analysis/service.py:258` `read_ready_report` | 是固定来源的生产入口。选证据验证不等于真实检索相关性/拒答实验，RAG-REL 仍单独 OPEN |
| 输出验证 | `apps/api/app/services/lesson_generation/validation.py:97` `normalize_model_output`、`:120` `validate_for_apply` | 严格 JSON、五整字段、固定 alias、四阶段与总分钟、教师字段保护；不因真实模型输出不合格而修饰 raw/放宽规则 |

以上位置为本轮只读源码行号。后续实际改动仍需重新核当前位置，不照抄行号作证明。

## 当前确实缺少的技术条件

1. **受控试评执行器**不存在。`scripts/teaching-quality` 现只有 common、scope_preflight、aggregate_review、prepare_review 与测试；`scope_preflight.py:32` 明确输出 executorPresent=false/budgetEnforced=false。这是交付范围边界，不是 G5 回归。
2. **总预算与持久尝试账本**不存在。现单请求输出 cap 不能等于所有案例/重试的总 token 或总费用 cap。现任务 attempt 是任务领取轮数，不应混同为已收费网络发送数。
3. **原始响应/用量/发送身份留证**缺口。Provider 可返回 usage，现教案服务随后只验证并发布候选，没有向 QA 输出 raw text、finishReason、usage 或与 scope 相连的调用记录。不得从已规范化 proposal 反推模型原文。
4. **完成与中断后的计费未知停止**尚无试评级策略。超时、取消、进程中断、账本写失败不能被“当前无成功 candidate”当成未发模型请求而免费重试。
5. **真人反馈接收与原生页核**需要实际材料，不能由自动化代填。现 prepare_review 的 CSV/Markdown 只接受空人审状态，填写后不能再次用该入口签成已人审通过。

最小实现可放在 `scripts/teaching-quality` 的一个受控试评入口与其专属测试；文件名由总控确定。推荐先通过独立依赖注入，在**本批隔离进程**中装饰生产 Resolver 返回的 Provider.complete，以复用 production `LessonGenerationService.execute` 和 JobEngine，并捕获真实 response 及失败。不 monkeypatch 共享 Provider 类、全局 Transport 或常驻用户服务；不另建 prompt/API/表或全站预算功能。若无法在单实例注入边界实现，再提交具体必要性申请，正常不需要改历史迁移、共享 DTO 或锁文件。

## 总预算必须在发送前执行

建议第一轮仅支持用户明确选定且能够证明计量边界的一个模型配置。不是强求一开始兼容所有现有 Provider。

- 原始 scope 沿用 modelProfileId/modelId、caseIds/sampleCount、maxAttempts、maxTotalTokens 或 maxCostCny。保留用户授权原文/来源与 scope 文件 SHA；CLI 的 allow-live 开关、合法 JSON 或用户沉默都不构成授权。
- 实际发送前核实际 handle.model_id/profile_id 与 scope 一致，调用既有冻结 fingerprint 核对。**另冻结与复核非敏感实际请求体 SHA、输出上限、reasoning 参数、有效协议/地址配置身份等**：当前 model_fingerprint 只覆盖 modelId/protocol/host/apiFormat，不足以证明输出上限和完整参数未变。新增试评记录不能冒称旧指纹已覆盖这些因素。
- token 硬上限：每次发送前预留“最终 wire 的可验证输入上界 + Provider 确实执行的输出/推理上界”。输入 UTF-16/256 KiB 上限是工程体积上限，不自动变成 tokenizer 保证；字符数÷若干、预估 token 或上一例 usage 都不能作为硬边界。没有选中模型的可靠上界/计量机制时，真实发送数必须为 0，先报预算执行条件缺失。当前 build_request 中三协议输出参数校验可复用，但还要核所选 Provider 的实际计费 token 语义。
- 金额硬上限：如果用户只给金额，需要明确且可核的所选模型计价上界、币种/汇率适用身份和所有会产生费用的计量维度；用 Decimal 整数最小单位，拒绝 NaN/负数/bool。价格/计量条件不明不能自行填一个单价开跑。若两种 cap 都给，均须满足。未来查实价时在 live 授权范围内查官方来源，本轮未联网。
- 先在独占账本中 durable 写入 reservation 和 attempt，再允许实际 complete。写入失败、冲突或未知状态 => 0 新调用。账本与最终 output 使用新 label，禁止覆盖旧证据；拒绝两个执行器共享账本同时发送。
- 成功且 usage 为精确非负整数、计量维度完整且不超过预留上界，才结算并释放余量。结构无效/finishReason=length 等仍已经花钱，仍计 attempt 与真实用量；不能因为未发布 proposal 将费用清零。
- 返回/失败 usage 缺失、bool/负数/小数、不完整，或 actual 超过预留 => STOP 剩余案例并登记不确定/异常；保留已预留额度，不恢复成 0。超时/取消/中断也不能证明上游未计费。
- maxAttempts 限定每个案例的执行尝试，失败也消耗；精确 providerSendCount 另记。没有用户明确允许第二次时只有一次。技术准备失败且未发送要记调用 0，但不能静默无限重试准备/换模型。

伪代码（为待实现方案，非现有能力）：

```python
async def complete_in_authorized_run(case, frozen_job, config, request):
    assert_run_and_scope_match(case, frozen_job, config, request)
    # 异常/跨进程中断的 reservation 不作为从未发送而消除。
    bound = verified_worst_case_bound(config, final_wire(request))
    slot = ledger.reserve_durable(case, frozen_job.job_id, frozen_job.attempt,
                                  scope_sha, request_sha, bound)
    # 上面检查/落盘失败时 delegate.complete 调用数为 0。
    ledger.mark_dispatch_durable(slot)
    try:
        response = await original_provider.complete(config, request)
    except BaseException as cause:
        ledger.record_unknown_and_stop(slot, sanitized_error(cause))
        raise
    # 保存响应原文、finishReason、原 usage，早于候选 JSON 验证；不保存凭证/头。
    ledger.record_response_durable(slot, safe_raw_text(response), response.usage)
    if not exact_complete_usage(response.usage) or exceeds_reserved(response.usage, slot):
        ledger.stop_remaining(slot, "USAGE_UNCERTAIN_OR_OUT_OF_BOUND")
    else:
        ledger.settle_durable(slot, response.usage)
    return response  # 仍交既有 normalize/publish；不伪造候选或补写合法 raw。
```

若响应证据写失败，即使 Provider 已返回，也保持不确定 STOP；不能忽略异常继续下例。使用成功 response 交生产验证不会替代试评工具自身的非敏感留证约束；已知身份/凭证检测触发时阻止落可外发原文，保留脱敏事实与 hash。

## 重放、重试、重启与预算的交接

- 同 submission 原包重放使用现 generate_proposal 收据，不 reserve 新 attempt，不发新模型请求；记录该操作 network_delta=0。同键异包继续 409。
- 已终结失败显式 retry 经现公共任务端点与唯一注册表；新 attempt 前仍经过同一受控 Provider 与持久预算 gate。不能直接调 provider 绕过任务，也不能认为公共 retry 已自动检查试评 cap。
- 封印中包含 jobId、任务 attempt、case attempt、providerSendCount、scopeSHA、inputHash、modelFingerprint、wireSHA、promptSHA、产品与执行器 SHA 和生成身份。Receipt 的 `[N,N+1]` 观察语义与网络次数分别记，不互相替代。
- 已发请求但没有完整响应或没有 durable settlement 的历史记录，恢复时只读核/保留 reservation、标 uncertain，并 STOP。系统重启仍不自动重叫模型；不能删除 ledger 后用新 label 把同一授权预算当全新。
- 能确认原业务成功但响应丢失时取原收据/任务结果，不重新生成。模型已返回但候选发布失败仍要保留真实调用、raw、用量和 DB 回滚事实。
- scope/产品/Prompt/来源/配置参数变化 => 不沿旧身份继续；保留此前所有费用/失败事实，新范围需新明确授权。不得以“证据 hash 已变”为理由免费重算全部案例。

## Live 正确行为不能绑定手写替身答案

原 `aggregate_review.py:273` 比较每个环节分钟数与 fixture 的 `spec.stageMinutes` 完全相同（C01 为 10/10/10/10）。case.requirements 没有要求这个具体分配，生产 validator `validation.py:47` 起要求的是 4..12 个合法环节、四阶段覆盖、正整数分钟、总时长、知识点/证据来源覆盖等。现 aggregate 还固定旧 applied/DOCX identity，并始终报告 offline 状态。

因此：

1. 保留原 case-specs/expected/旧空反馈及离线工具原字节，手写学情人数、分母、成绩四态与知识点关联 oracle 继续独立比对。
2. Live 新结果按实际生产契约、固定来源和教师保持要求核技术结构；具体语言、教法、环节分钟分配由实际模型给出、教师评价，不能与 handwritten `answer()` 的原文/具体分钟作硬相等。
3. 不以修改旧 stageMinutes/expected 来迎合新答案，不以模型回填 oracle。若某案例另有教师明确特定分钟要求，先冻结该要求与新 oracle，再运行。
4. 如果旧 TEMP 缺失，用原手写 case spec 和自有合成来源在**新 TEMP**通过现有仓储/确认闸门重建所选案例事实；这不是再生成原准备包。新 IDs/新 inputHash 与原 spec SHA/语义事实绑定，不能把新库当旧物理恢复已通过。
5. 旧 seed fixture 的 install/MockTransport/profile/fixture-key/回环9 不进入 live 执行。隔离数据准备能重用已审手写规则与生产确认代码，但 live provider 必须来自真实所选 resolver。实际本机模型允许回环地址；不能简单把所有回环模型都定义成替身。
6. 真实输出仍是待教师审核建议。为了技术保持检查在新 TEMP 按 spec 五字段应用的行为必须标 QA 选择，不能宣称真人已接受。实际教师选择、评分/修改建议和人审结论另留证。

## 无 scope 时的最小独立技术门禁

实施仅在用户下发技术执行器范围后开始。此技术候选可以离线验以下正确行为，不等待真人、凭证或网络：

- scope/hash、案例集合/count/profile/model 不匹配、未授权、缺可执行预算、超预算、缺/漂移 cap、journal 不可写、并发所有权争抢 => 真实 Provider 委托调用 0。
- 各唯一案例成功、协议 429/超时/断连、finish length、坏 JSON/非法字段、发布回滚、取消、旧 lease 失权；调用和收费记录不因结果失败而消失。
- 未知/非法/部分 usage => 停止下一例；usage 已知正常 => 按冻结 cap 结算；actual 超 reservation => 报异常并 STOP，不宣称硬预算已通过。
- 两次重放相同 submission 调用增量 0；一次明确受许可 retry 恰一新调用；同键不同 input 拒绝；maxAttempts 和总 budget 穿过 retry 一致。
- 崩溃于 reserve/dispatch/response/settle 的每个窗口，恢复不会重复发送或释放未知消费；独立测试两个 controller 共用 ledger。
- 匿名最终 body/no identity/固定来源/生产 Prompt SHA，原 wire 不含 key 或认证头；实际数据/Provider 替身 guard 与 calls 分列。
- 新 live 检查器能接受一份合法且环节分钟不同于手写 fixture 的候选，又拒绝总分钟/来源/教师字段等真实错误；不运行旧 aggregate 给它假 live PASS。
- 阶段证据明确 executor 技术通过、live=not_run_missing_explicit_scope、teacher_pending/native_not_run。独立验收不过不能开始真实模型。源码仅工具变化时先相关 pytest/CLI 与模型集成反证；不为工具凑数启动全站服务。若确实改业务调用/保存/导出则运行相应 API/check/build/E2E。

## 必须由用户/真人提供的内容及分期停止

真实调用最小输入是：`modelProfileId/modelId + 精确 caseIds/sampleCount + maxAttempts + 可执行 token/金额 cap`，以及对匿名自有样本外发/选定模型调用的明确范围。API Key 不进入 scope 或对话材料，凭证依现 backend SecretStore 安全解析。教师、Word/WPS 的约定可以并行等待，不应因为教师尚未到场阻止一个已明确授权且预算合格的 live 技术运行，也不应因为 live 未授权阻止教师对已有 fixture 流程/原 DOCX 的人工试用；结论分别标识。

建议接续分为一个 B7-B 下的两个技术节点与两条人工证据线：

| 节点 | 条件 | 可关闭的结论 |
| --- | --- | --- |
| 技术执行器 | 用户明确下发离线实施；独立 guard/ledger/provider tests 通过 | 真实执行准备的技术条件，模型 0 |
| 有限 live | 前节点通过 + 人类明确范围/预算 + 实际连接/计量条件齐备 | 实際输出结构/固定来源/调用与成本事实，仍不自动给教学质量 PASS |
| 教师反馈 | 新评审 label、实际教师、明确正在评价 live/fixture 的哪个候选 SHA | 具体材料的教学判断、硬失败/八维评分/证据理由；空槽未返回仍 pending |
| 原生页核 | Word 或 WPS 实际打开被 SHA 固定的工作副本 | 该 DOCX/应用版本/实际原生页数与逐页问题，不能泛化到所有导出 |

真人评价沿用已交付 rubric、复制原空表至新 label 后填写，保存评审者/日期/原文位置/理由/修改建议。只做内容完整性/绑定核对与原样汇总，不建新业务人审 API，不由模型代评分或补人审缺槽。原 CSV/Markdown 仍保持。

原生页核沿用既有四代表 DOCX，在工作副本记录应用版本、实际页码/总页数、每页文本/secondary/中文公式符号/表格跨页/裁切重叠与原图。历史 PDF 的 1/8/2/2 与 13 张 PNG 仅作参考，不预填原生页数。只核旧材料就只关闭这些固定材料的原生核查；若要验现构建新导出，须明确范围并按同一固定 revision 生成新 label，不覆盖原件。

缺一条人类范围或原生证据时，只列具体缺件并停止依赖分支，不默认失败、不自动追人、不重复离线包、不宣布原 B6/B7 整体完成。RAG-REL、正式迁移/Qdrant/额外压力、旧 policy 拒绝 probe 与缺物理恢复源仍按原独立台账，不拿 B7-B 新样本替代旧证据。
