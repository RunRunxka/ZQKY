# B4 T70 只读代码复查 · 2026-10-03

本范围**未发现新增可复现缺陷**。这是新的窄范围审查，不将原 B4 独立验收或今日全量 E2E 计为本次重跑。本次未修改产品、旧 QA、冻结件或权威文档，未启动 TCP 服务或浏览器，未读取正式环境、凭证或数据。

审查依据：根与 API `AGENTS.md`、`CURRENT_STATUS.md`、`PROJECT_GUIDE.md`、今日 B4 报告，原 B4 公共契约 v1 与 v1.1～v1.4 errata、A 卡完整独立结果。产品来源散列见 [RESULT.json](RESULT.json)，完整候选保全由 CTRL 汇总核对。

## 代码结论

- [snapshot.py](../../../../apps/api/app/services/analysis/snapshot.py:20) 在教学库单一读快照中读取指定已确认成绩与固定原卷；可选人次、计分叶和矩阵均来自该成绩自身快照。重复人次与同学生多个 attempt 明确拒绝，不自动选最高/最新；校验完整矩阵和满分范围，固定题面、KP 名称/修订、材料/资产/来源与练习映射进入事实包。
- [aggregate.py](../../../../apps/api/app/services/analysis/aggregate.py:7) 对固定整数事实使用 `any_loss_v1`：失分优先，信息完整性独立；0 是有效成绩，missing/absent/exempt 不补零。班级 KP 分母只计至少一格 recorded 的所选唯一学生，零分母返回 null。试卷总分在完整 recorded 时直接按题相加，不按多 KP 重复累计。
- [service.py](../../../../apps/api/app/services/analysis/service.py:51) 排序人次后计算提交身份及完整事实散列；早期重放不重读资产，同事实新提交复用原 run/job。独立并发探针实见两个提交只创建一个 run/job 并调度一次。锁外核资产与计算，发布使用公共 JobOutcome 同库事务。失败、取消、原租约与重试细节另由既有窄回归核验。
- [报告读取和备注](../../../../apps/api/app/services/analysis/service.py:167) 校验 owner 与固定筛选身份；分页结果及 notes 保持归属隔离。备注独立追加、保留原文、提交幂等，错误备注不登记半件；不会改变 ready 事实、输入散列或原矩阵。

## 本次实际检查

| 检查 | 结果 | 范围与原件 |
| --- | --- | --- |
| 新独立探针 | **4 passed / 0 failed / 0 skipped，exit 0，2.657s** | [执行源](test_review_analysis.py)、[首轮日志](probes-first.log)、[XML](probes.xml) |
| 既有相关窄回归 | **20 passed / 0 failed / 0 skipped，exit 0，3.010s** | 五文件：analysis service/http/rules/jobs/lineage；[首轮日志](regression-first.log)、[XML](regression.xml) |

新探针包括：三格 recorded(0/50/100)/missing/absent/exempt 的 **216 个组合**与独立规则断言；同事实并发提交和逆序重放；不同 owner 的读取、报告列表、事实、备注及创建拒绝；真实 `create_app` 的内存 ASGI 路由、固定 participant+KP 分页、空页、错误备注零写入、备注原文/重放/冲突及 ready 事实不变。ASGI 复用真实迁移/SQLite/业务服务/JobEngine，ManualEngine 只拦截自动调度，执行使用真实 `run_job`；没有启动 TCP 8001。

命令在仓库根先设置新的临时 `ZQKY_DATA_DIR`、`ZQKY_ENV=test`、`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`，再运行 `uv run --directory apps/api python -m pytest`。ASGI fixture 的 Settings 显式 `credentials_file=None`，教材源为空临时目录，Qdrant 指向测试端口 16333，embedding 指向 9，均未访问真实外部服务。唯一 warning 为 Starlette 对 AnyIO BlockingPortal 别名的弃用提示，未隐藏或放宽断言。

独立外层根见 [TEMP-ROOT.txt](TEMP-ROOT.txt)，pytest 数据目录亦为新隔离目录，均保留。所有 TestClient 与 DB 连接已按上下文退出；本次没有创建监听端口或管理现有用户进程。

## 适用边界与下一阶段约束

未执行全量 check/API、浏览器/E2E、真实模型/Qdrant、Word/WPS、正式迁移、200×100 再跑或跨进程并发，理由是本次只读源码复查，既有全量结果保留为历史证据。并发探针只证明同进程提交竞争，不能据此宣称所有读写竞态或跨进程锁均已覆盖。

B5 教案调整应通过公开固定报告读取能力获取事实，显式限定固定 run 和目标班级/学生，沿用上述观察状态及证据，不再次计算“掌握率”，也不把空历史班名替换为当前班名。教师备注应与分数事实分开传递，不改旧报告；学情驱动生成质量仍须独立教学评审，T70 技术通过不等于教案内容质量通过。
