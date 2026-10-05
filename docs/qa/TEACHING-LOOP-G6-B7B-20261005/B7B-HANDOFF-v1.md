# B7-B 后续交接 v1

本批G6已独立有限关闭，B7-B离线技术已由预算64/结果76两个独立新完整轮签收，ROOT限定技术收据见CLOSE-v1.json；文档后验、资源、完整性和封印另存本批证据，本批STOP后只等用户新指示。当前进度只看[CURRENT_STATUS](../../CURRENT_STATUS.md)，本文件只记录后续需要的输入与能力边界，不授权新批次或真实调用。

## 已有入口和证据身份

执行入口为[controlled_trial.py](../../../scripts/teaching-quality/controlled_trial.py)，能力和用法见[执行器说明](../../../scripts/teaching-quality/README-controlled-trial-v1.md)。只新增试评CLI与JSON审计账本，复用现有FastAPI生产prepare/build_request/execute、JobEngine和三协议Provider，不增加业务API/表、迁移或依赖。

`--mode dry-run`使用新TEMP、匿名固定事实和显式HTTP MockTransport。scope选择必须精确；固定原15规格的相同字节和每case事实在发送前复核。新结果绑定scope、实际wire、raw、usage、attempt、job、指纹、候选及QA所选字段应用。原15规格/273包/四旧导出不重制。

结果入口为[trial_result_check.py](../../../scripts/teaching-quality/trial_result_check.py)，规则见[结果说明](../../../scripts/teaching-quality/README-trial-result-v1.md)。结构验收使用生产规范化与校验，允许合法的不同四阶段分钟分配；固定事实、完整教师字段和未选字段仍须保持。教师返回和native返回使用独立接口，旧prepare空表校验器不用于填写后的返回。

SHA使用实际文件字节。账费证明内部canonical wire散列和wire.json文件散列分开；不能改一个引用的SHA后忽略其scope/ticket/job关联。源码、执行QA、构建、材料和最后文档delta分别绑定。查看[本批报告](REPORT-v1.md)及相应独立收据，首败和实际候选身份保留，不据文件数称用例数。

## 真实调用前仍需的技术能力

当前CLI live是显式拒绝入口，注册表为空：没有可信真人授权接入/真实host和凭证绑定，没有具体真实模型完整账费及usage语义证明。成本模式也没有冻结价格、币种和汇率依据。当前不能提供一份scope后直接调用任意模型；所有真实调用为0。

未来批次须在该批明确授权内补齐可信宿主：使用已有后端配置与凭证机制解析真实profile/model，不将Key放入scope/材料/日志；将真实授权来源绑定稳定authorizationId和immutable scope；证明最终协议wire的输入、输出、reasoning和其他收费项上界及usage语义，或完整可执行成本上界；注入原三协议Provider与明确无重试transport并完成独立反证。UnsupportedLiveProof/fixture上界不是真实模型证明，不猜字符token或默认费率。

同一授权控制状态由固定namespace及authorizationId决定，与run/output label无关。未来迁移批次namespace必须承接原授权账本；不能以另一个scopeHash、空ledger或输出目录重置次数/额度。reserved/dispatched/responded未结算、未知usage、超时/取消/响应落盘失败与超上界均保留预留并停止，重启不自动发送。已成功原receipt重放增量0；明确失败也只能在原attempt和剩余预算允许时显式重试。控制目录和本地代码由可信宿主管理，不宣称防操作系统所有者篡改。

## 用户应明确提供的真实范围

以文字或新scope明确给出以下值，且明确授权按此范围调用真实模型。不要提供密钥。

| 字段 | 必须明确的内容 |
| --- | --- |
| modelProfileId | 已有后端配置ID，不能用fixture profile |
| modelId | 实际模型ID，与所选profile一致 |
| caseIds | 精确案例ID列表，不能默认全15 |
| sampleCount | 与上述列表精确长度一致 |
| maxAttempts | 每例最多尝试，失败和可能送达上游的发送均计入 |
| maxTotalTokens或maxCostCny | 在具体模型证明和执行能力支持的模式下，可执行的总上限；本修订成本模式未支持 |

教师和native安排另以文字或交接文件记录，不塞进strict live_scope未知字段；可独立pending，不代替模型授权。部分案例只按实际覆盖验收，未选及STOP后未运行的案例分别列出，不关闭未覆盖的原计划要求。

## 真人和原生返回

教师需实际评审新输出，返回绑定case/输出/candidate/DOCX的真实SHA、评审者/时间、八维评分、硬失败、原文位置、支持和不支持理由、修改建议及真人结论。自动化只核完整性与身份一致，保持真人原结论；合成完整接口样例不计真人返回，顶层teacher仍pending。

新真实候选有审查或导出需要时，才生成其固定修订工作副本。未应用/未导出证据分别not_run，缺DOCX不能冒称已核其排版。Word/WPS需记录应用与版本、实际页数/页码、secondary/中文符号/合并/跨页/裁剪、逐页证据和理由；逐页覆盖及真实hash须一致。合成ZIP/1像素图仅接口反证；原13历史PDF页不能代替Word/WPS原生查看。本批原生控制不可用，真实native仍pending/not_run，不安装工具或操作未知会话。

RAG-REL需独立实际检索相关性试验；固定手写教材事实不能代签。原B6/B7整体、旧物理SQLite/Blob缺源恢复、R14跨批间歇/CV01～03/OBS-LP-MODE-LABEL和环境观察保持原台账边界。本批不自动实施这些后续内容，不提交、推送、切分支或部署。
