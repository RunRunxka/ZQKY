# 今日执行工具独立静态审查 · v1

结论：**3处静态工具缺口已报告CTRL，未执行工具或业务，不作放行。** 原读取文件SHA与精确位置见[JSON](TOOLS-STATIC-v1.json)。本卡保存修正前字节；新实现须另冻另审。

| ID | 实际位置 | 缺口与修正边界 |
| --- | --- | --- |
| 01 | candidate.py:13/51/54/78–93 | audit不核冻结baselineSHA/3043count及expected nextenvSHA；补冻结身份/计数/SHA，并保留原byte equality |
| 02 | run_check.py:28–31/52，三external默认run/输出 | label只防receipt/log覆盖，改label沿用默认run仍可复用结果目录；在Popen前按真实env/default+已知config推导绝对output并拒已有目录，不删旧结果 |
| 03 | run_check.py:52–64 | launcher异常没有收敛自身Popen/pipe；仅处理已知自有句柄并记录真实wait/exit/stdio/log，未核descendants/API不得虚报关闭 |

CTRL拟议方案合理：output guard置launcher，不放config顶层，避免worker再加载误伤；三执行卡必须经launcher。baseline/nextenv核冻结身份；异常只触碰自己的Popen，实际尚未核的后代和端口如实待收口。此仅方案静态意见，未审未落的新代码。

其余本范围静态对应正确：outer隔离在Settings/app前；stream fence实际检查credentialsNone；原fixture runpy与三协议不变，exact nested TemporaryDirectory保留、原server.shutdown/cleanup finally保留，同app/uvicorn参数、fresh owned stopfile与日志范围明确。原fullE2E/chat配置集合和workers1/45000/expect10000/channel表达式继承，外部webServer全undefined；installed Playwright defaults为repeat1/retry0。r14只限定独立新scene/traceon。candidate实际build口径排cache/trace、记录BUILD_ID/8001，3043为读取baseline元数据计数，并非本卡重扫。

r18已有冻结、root静态TS7006首败和拟P窄类型适配按CTRL消息保留；本卡未开始总r18/原AST验算，也不将后续变更冒称原r18同源。没有执行Python/TS/Node、test/collect/service/browser/HTTP或访问真实/未知数据，未修改源/执行QA/权威文档。仅新增本MD/JSON后停写，待CTRL新候选卡。

