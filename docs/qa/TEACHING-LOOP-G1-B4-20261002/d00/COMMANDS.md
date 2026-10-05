# G1-D00 v1 实际核对命令

工作目录 `H:\备份xuexi\智启课源`。本任务未导入应用、未连接业务数据库、未启动服务或浏览器；Python 仅用于读取仓库文件并解析 JSON/XML 和计算 SHA。

```powershell
$env:PYTHONIOENCODING='utf-8'
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/d00/audit.py 2>&1 | Tee-Object -FilePath docs/qa/TEACHING-LOOP-G1-B4-20261002/d00/audit-first.log
```

首次脚本 exit 1：检测到说明中的 `root/omml-first.log` 不存在。首跑日志、退出码及当时脚本分别保留在 `audit-first.log`、`audit-first.exit.txt`、`audit-first-source.py`，已通知 CTRL 修正说明，不伪补该原日志。

```powershell
$env:PYTHONIOENCODING='utf-8'
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/d00/audit.py 2>&1 | Tee-Object -FilePath docs/qa/TEACHING-LOOP-G1-B4-20261002/d00/audit-final.log
```

最终脚本将缺失本地首败日志明确记录为 `missingLocalFirstFailureLog`，不将它与候选／旧证据漂移混淆。最终 exit 0；826 候选、629 旧证据均零差异，正确行为最终 XML 单次计数为 52/53/20/1。见 `EVIDENCE-AUDIT.json`、`audit-final.log`、`audit-final.exit.txt`。没有复跑这些业务用例。

只读资源观测使用 `Get-NetTCPConnection -State Listen` 筛选 8001/5174，并用 `Get-CimInstance Win32_Process -Filter 'ProcessId = 4844'` 核对旧 PID；两者结果为空，完整时间和结果在 `RESOURCE-AUDIT.json`。未调用 Stop-Process、Start-Process 或其他资源变更操作。

Git 只执行 `ls-files -z`、`branch --show-current`、`rev-parse HEAD`；`rg --files --hidden` 仅收集授权源目录文件名，哈希之前排除真实 `.env`、数据目录和缓存；安全 `.env.example` 纳入冻结核查。

两次最早的内联只读元数据列举命令发生 QA 命令错误，工具输出保留：PowerShell `foreach` 后直接管道触发 `An empty pipe element is not allowed`；之后 Python 对列表调用 `items` 触发 `AttributeError`。它们没有执行应用或修改产品，未将其计为业务测试失败或通过，也未伪称已生成本地原日志。

首次文档链接审计在生成本身的 `DOCUMENT-AUDIT.json` 之前检查了 RESULT 指向该文件的链接，报告自身尚不存在并exit1；原JSON保留为 `DOCUMENT-AUDIT-first.json`。文件生成后重新核实链接存在，并纳入CTRL随后补充的D00范围说明和FINAL-SUMMARY/AUTHORITY-DOCUMENTS，两者均没有虚报业务或浏览器通过。该问题仅为D00审计输出生成顺序，不涉及任何权威文档或产品修改。
