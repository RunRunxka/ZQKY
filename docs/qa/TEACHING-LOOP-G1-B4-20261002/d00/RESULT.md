# G1-D00 v1 独立证据核对结果

负责人 `/root/g1_doc_audit`，2026-10-02。结论：**本次事实记录核对通过；G1整体未关闭，真实浏览器/E2E未执行，B4未开工。** 本任务只核既有日志、XML、JSON、收据、源码和最终说明，没有重新执行业务验收，不为 G1 或 B4 添加通过场景。

唯一写入范围为本批 `d00/**`。没有运行应用、连接数据库、启动/停止服务、操作浏览器、访问凭证或正式数据、查看旧六临时目录或执行 Git 写操作。

## 冻结与实际范围

独立读取并逐字节重新计算：候选 g1-r2 **826项零漂移、无未登记新增源文件**，629份旧证据零漂移；next-env 与本次原字节相同。r1共同825项哈希全部不变，r2只新增安全 `.env.example` 的覆盖。分支/HEAD仍为 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。

g1-r2清单本体SHA256为 `9471f43eb5ba9cde9d79ab65b84f5cf1fcd607729b1ad2388d2bfde5c78a072b`。相对开工现场，13个产品文件、4个已修改测试、4个新增测试，共21个，符合 REPORT。覆盖扩展没有行为源码变化；不将它写成重新运行 V00。完整独立文件核对和各 XML 名称见 [EVIDENCE-AUDIT.json](EVIDENCE-AUDIT.json)。

## 八项行为与门禁记录

以下核对均从单次最终日志/XML及独立夹具断言、收据读取；没有将多轮结果相加，也没有以生产身份/守卫函数作为 D00 期望值。

| 范围 | 独立实物结果 | 核对的正确行为 |
| --- | --- | --- |
| R01/R02/R03/R08 | FE最终XML 20通过，0失败/跳过；日志2.35s，命令JSON exit0 | 未保存零确认、保存后新权威预览/承认、未知原包；迟到响应不覆盖较新映射，卸载与Strict；名单变更保留合法选择/出勤/人次及撤销说明；完整delimiter多参数/空项/分式/分隔符及安全全文替代 |
| R04/R07 | SCORE/QB最终XML 53通过，0失败/跳过；日志16.15s，exit文件0 | 33个成绩场景中的完整文本、物理坐标、公式/缓存、四态、拒绝零写与源字节；20个题库场景中的不同共同材料、富题面、真重复/答案冲突、旧指纹、同包及固定原包先重放 |
| R05/R06 | JOBS最终XML 52通过，0失败/跳过；日志6.10s，启动记录exit0 | 真实第二连接BEGIN IMMEDIATE屏障后读钟/到期零写；到期无人接管与失权；16种实际ASGI retry收尾组合，目标轮恰好一次及tracking、取消/错误/重启 |
| 额外真API组件链 | XML另一次1通过，日志2.21s，命令JSON exit0 | 请求转发真实8001；两份完整确认包相同，第一次200提交后故意丢响应，第二次replayed=true且同修订；正式一份修订，甲[100,200,500]/800 |
| CTRL check | 原日志109文件/1088单测通过，81.80s及后续build完成；CTRL记录exit0 | 类型检查、lint及unit/build；D00没有复跑或从旧批结果推断 |
| CTRL全量API | 原日志1599通过/1跳过/1既有warning，232.67s；CTRL记录exit0 | 明确保留跳过；169项专项XML无跳过，包含100叶及200人次规模实际用例，不扩成B4性能通过 |

65项公共专项、119项题库专项、169项成绩专项与上述独立最终 XML 分别核对一致。它们不是新增总计。`real-api-receipts.json` 有65条记录，真API适配仅转发/转换multipart和丢响应，不制造成功业务响应；传输层省略不兼容的 jsdom AbortSignal，不能据此验物理网络取消。

真实链的完整9格矩阵与甲800、丙1000、丁800来自 root只读 SQL对账JSON；四库 integrity_check全部ok、foreign_key_check完整结果为空。D00只核该记录与HTTP/CSV夹具的一致性，没有另行打开任何数据库。

浏览器命令只有 `--list` 收集1例，命令JSON明确无浏览器断言执行；真实API组件链不等于真实浏览器。REPORT、G1-CLOSE-MATRIX、INDEPENDENT-RESULTS、CURRENT_STATUS及QA索引均明确浏览器/E2E `not_run`、整体G1未完成、B4未开工，不能凭当前记录进入 B4。

## 文档、首败与资源

最终API描述与实际源码/收据一致：单元格20,000字符上限在完整转换后核验；超限details包含sheet/物理row/列字母column/address/view/actualLength/maxLength，XLSX view为formula/cached、CSV为csv；csv.Error为TABLE_PARSE_FAILED且只有可靠sheet/row。已注册执行器queued重复retry语义与当前route/registry/engine一致；租约失权零写、旧收尾后目标轮调度和surface指纹说明未超出已核行为。

发现并提交CTRL的一处说明错误已更正：原 `root/omml-first.log` 没有生成，首次stderr只在工具输出中，不能声称有该本地日志。REPORT和ROOT-FIRST-FAILURES现在明确这一缺口，没有伪补原记录。其余已列首败日志/XML/旧夹具实物存在；SCORE/QB四轮、FE组件两轮、真API组件两轮失败计数均与原XML一致，未被最终通过覆盖。D00自身首次脚本因该缺失断言exit1，原脚本/日志/退出码保留；最终脚本把缺失明确记为证据限制，exit0，见 [COMMANDS](COMMANDS.md)。

独立只读系统观测于16:38:41+08:00：8001/5174均无监听、原PID4844不存在，见 [RESOURCE-AUDIT.json](RESOURCE-AUDIT.json)。与root资源记录一致；没有把显式停止进程产生的exec退出1算成产品测试失败或宣称优雅shutdown。新临时样本保留、旧六目录不触及的事实范围来自资源记录，D00未遍历这些目录。

最终权威文本及本次报告哈希、相对文件链接实物核对见 [DOCUMENT-AUDIT.json](DOCUMENT-AUDIT.json)。D00最终发现的问题已修正，无新增阻断本次事实记录的问题；真实浏览器/E2E以及B4所有实现、独立验收、性能、迁移、导出与备份门禁仍未执行。模板verify、Word/WPS、真实模型/Qdrant未执行，边界没有改成通过。
