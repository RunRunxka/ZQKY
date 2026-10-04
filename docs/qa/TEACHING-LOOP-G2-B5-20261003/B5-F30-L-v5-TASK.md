# B5-F30-L-v5 / R07 旧本地快速导航回归窄修

ID/version B5-F30-L-v5；负责人g2_fe；ROOT授权时点 2026-10-03T12:51:48.988171+00:00

R5全8已独立接受，但原完整153 first为151pass/2产品fail（391550.724ms/PID14660）。两原trace与两独立验收确认LeaveProtection.ask把正常localPending当dirty后台稿直接挂人工promise；600ms自行成功保存后仍不resolve，原立即flush→导航行为丢失。不能适配/删除原lesson-plan与navigation测试。

唯一可写产品文件：apps/web/src/features/lesson-plan/components/LeaveProtection.tsx、apps/web/src/features/lesson-plan/lesson-workspace.test.tsx；仅作者b5-fe新v5私有QA/结果/输入源快照。其他产品/契约/公共导航服务/后端/原tests/e2e/v1-v4原件/权威文档不改。若确需别的文件先报ROOT具体理由。

验收：正常local mode无unknown/import/create在途时先flush原writer，成功直接允许导航，不要求二次点击；慢save等待成功不先离开，失败/坏稿仍保护并可明确retry/keep/discard，原body保留，不冒称失败已保存。flush后如期间本地新编辑或操作身份变化须依原串行writer/latest guard正确处理；存储block、操作busy/unknown、server dirty/conflict/unknown、printSnapshot与历史保护不得弱化。内外公共导航/同模块打开后台均沿同ask能力。

先保存两源修前原字节与private新同一组meaningful author测试，修前至少正确行为失败完整记录；修后原106+新增本地flush相关的完整新单轮，QA字节不放宽。类型/零警告lint；不用build/TCP/浏览器/付费模型/Git。独立V00另有handwritten QA不采用生产merge/or作者oracle。

ROOT frontend21928/23196已专属stop退出/session5223 exit0，API27068 closed；原153已结束，没有运行source-binding检查。ROOT独占新check/build、next-env恢复与候选冻结、全部153/14。作者全部停写后再独立unit+完整check/build+完整8+原153/14。不拼原151或8旧绿。

结果卡：ID/version/完成待验/两可写diff及SHA/每条cmd PID exit单轮数ms source与QA前后0/TEMP&日志保留/旧前序证据&33冻结0/首失败原件/STOP时点。无Git写入或新agent。
