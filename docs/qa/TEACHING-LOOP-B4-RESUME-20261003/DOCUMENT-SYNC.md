# 每日批次与文档同步约定

适用于2026-10-03用户要求「每日批需要做好文档记录，不要让文档过期」。每个北京时间日期建立独立QA批次；跨日未完成时次日新目录引用前一日实际结果，不能改日期、覆盖旧命令/失败/截图/trace/冻结件冒充新执行。

CTRL在开工、候选变化、真实门禁结束、等待用户、暂停或阶段完成时同步：CURRENT_STATUS唯一进度/问题/下一动作；NEXT_SESSION_START当前接手；docs README/PLAN/qa README当前索引；今日REPORT/CLOSE-MATRIX/EVIDENCE-COMMANDS/ROOT-FIRST-FAILURES/RESOURCES。每条实际结果写候选/构建/单轮计数/exit/ms/完整原件，未执行写原因，共同源绑定不当重跑。

AGENTS/PROJECT_GUIDE/API/ROUTES仅保存规范/稳定决定/现行契约；发现与已实施结构或接口不符时按事实修正，不能把运行进度塞入稳定规则。新文档改变若位于source清单须明示新candidate与业务同源边界，不覆写旧manifest。

收口前核：旧保护逐SHA、来源/构建/next-env/Git身份、当前入口/报告/矩阵互相一致、链接存在、资源实际退出或用户持有边界；另派只读独立文档复核。每日报告不等于自动化/定时任务授权，不创建自动续跑或日程。
