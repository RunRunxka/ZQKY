# B4-V00-A v1 · 独立 T70 验收准备

负责人：g1_resume_browser。此前为 B4 前端作者，本轮仅验 T70 后端，未参与 T70 实现。
准备读取的产品候选为 CANDIDATE-b4-r1.json，SHA256 e42edc7f0d74fa29380fb9603d055063302a383480c6a21f7a55f4016310c9e8。CTRL 已告知旧 B0 作者测试 fixture 将在下个候选适配，本执行器接受 CTRL 明确指定的新候选路径。

本目录只有独立验收源和证据可写。产品、产品测试、契约、历史 QA 全部只读；未启动或停止监听服务、未改前端或 Git。准备阶段只允许解析语法和计算文件哈希，**独立测试未执行，业务／性能未验收**。

## 独立预期与范围

- `literal_oracle.py` 不导入应用或生产聚合。手写四人总分整数单位 900/null/null/800（9/null/null/8 分）、八条学生知识点观察、K1 2/3 和 K2 1/3、全十二条人次×叶证据。核固定人次、题号、满分、知识点版本、题面／公式／图像声明／表格／答案／共同材料／全 sourceBlocks，班名为 null 并保留说明。
- 仅复用 `tests.analysis_support.AnalysisScene` 的真实迁移、固定数据和手动调度捕获功能，执行仍为真实 JobEngine／AnalysisService／发布租约同事务。该 fixture 不提供独立期望。
- 正确返回包的深拷贝产生十四个错误变体；全部须被 literal oracle 拒绝。包括零分和缺失混淆、仅失分证据、多知识点重复证据、分母错误、总分重复累加、错误观察字面值、历史班名、信息不全和富材料／资产丢失。禁止改冻结产品进行变异。
- 自建额外确认成绩修订覆盖失分同时 missing、全 missing、全 exempt；补考双人次报字段错误，仅显式二次人次出三证据／1000 单位；选择快照须完整。
- 两个真实固定班级核四班级知识点行、筛选一致性；旧报告在学生名／学号、班名、成员转班、知识点当前修订／归档、原卷当前标题、active 成绩修订变更后保持完全相同。
- 真实 create_app 路由 + TestClient HTTP 核 202 只接受、非 ready 返回非空错误、所有报告分页／筛选、同提交同包重放／异包冲突／固定输入复用、原始空格换行备注和备注重放、错误信封、服务缺失。
- 自有临时数据库缺格、自己的单个图像 blob 损坏／移走，须真实失败而无 job/run/submission 半件。原 blob 移到同一明确拥有目录保存原字节。
- 运行时故障仅包装本验收实例的 `repo.create_in`／`repo.publish_in` 原实现；分别在分析行插入后／全报告 ready 后抛错，核创建或所有五个发布子表回滚；恢复实例方法后走真实公共重试路由。没有修改生产文件、聚合函数或 oracle。
- 所有五个 ready 子表逐一 INSERT／UPDATE／DELETE，pending 输入／删除、非法 ready、封存撤回、备注 UPDATE／DELETE，核明确 IMMUTABLE_REVISION（或完整性闸门），旧报告不变。
- 真实 running cancel 抑制已计算的晚结果，重试同 job 到 attempt 2；90 秒租约用独立假时钟失效，过期 lease／原 attempt 拒绝完成，当前 attempt 自行重新执行并发布完整报告。
- 200 人×100 叶全矩阵：20,000 条 DB 证据、100 页每页 200 条 HTTP 证据、完整唯一键集合和每条固定分值／富题面来源；1,000 学生知识点行的全部五页、五班级知识点行，以及知识点／人次／班筛选。输入规律期望独立写定（100/90/80 单位、10000/9000/8000 总分、67 满分与133失分），不调用生产聚合获取期望。

## 执行隔离与计时

CTRL 冻结上述可执行 QA 并发出执行卡后，从仓库根调用：

```powershell
& 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-analysis/run-probe.ps1' -Candidate '<CTRL 指定的完整冻结候选路径>' -Run 'first'
```

每轮从 `$env:TEMP` 新建 `zqky-b4-v00-a-<UUID>`，在任何 app.main／fixture 导入前外层注入 test、UTF8、全新 DATA_DIR、空教材源、Qdrant 16333、embedding 9、PYTHONDONTWRITEBYTECODE；Settings.credentials_file 明确核为 None，fixture HTTP 用内存 SecretStore。Python 用现有 `apps/api/.venv/Scripts/python.exe`。不启动监听服务；TestClient 的 8001 仅 base_url。

`benchmark_compute.py` 在独立新 Python 进程上对完全相同的冻结 20k 输入进行首次冷调用及第二次热调用，丢弃生产返回值，只记录耗时，**该路径不是 oracle**。另外记录数据准备、固定读取、HTTP 接受、实际 executor 验签／取消／计算、租约事务内发布、job 总耗时、全部 100 页 HTTP 加完整 JSON 留存及独立预期核对。三秒纯计算指标分别判断，不把 100 页 HTTP 或数据准备算作纯计算。

保留完整 stdout、stderr、退出收据、CPU／OS／内存、pre/post 候选逐文件指纹、所有请求／响应、全分页、所有错误变体拒绝原因、首败堆栈及临时根。首败停止后续独立验证，不现场改冻源；由 CTRL 决定修复／重冻／受影响复验。

## 未执行与边界

本准备不运行独立探针，不以语法通过冒充业务通过。T80 实践／导出／备份与前端浏览器另有独立验收卡；不声明真实 Qdrant、真模型质量、Word/WPS 排版或正式用户迁移已验。

停写后只接受 CTRL 冻结／执行通知。执行期间可新建结果 MD/JSON/log，不改可执行 QA。
