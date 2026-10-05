# B7-B 结果检查独立窄审

本次只读检查新结果工具，复用旧独立生产链留下的 C14 chat 与 C01 responses/anthropic 输出作为输入。运行材料复制到本目录的新 label，未再次生成教材、名单或成绩；本轮 fixture 网络发送 0、真实模型调用 0。旧 208 个输入文件逐 SHA 前后相同，产品工具目录逐文件前后相同。

确认 1 项 P2：`R-B7B-NATIVE-01`，原生页证据仅凭文件头被判完整。原 G6 缓存修复不在本卡范围；原 B7-B 独立 76 项通过是历史事实，本卡不追改旧收据。

## Finding

`H:/备份xuexi/智启课源/scripts/teaching-quality/trial_result_check.py:516`–`517` 只核 PNG/JPEG/WebP 魔数，没有验证图片结构或可解码像素。具有正确 SHA 的 8 字节 PNG 签名、3 字节 JPEG 签名、12 字节空 RIFF/WEBP 容器均被接受为 `RESULT_INTEGRITY_PASS`，detail 为 `native_return_integrity_pass`、`actualPagesRecorded=1`。这些文件没有尺寸或像素，无法作为可查看的页证据。

实际正确 oracle 应为拒绝，三例 CLI 退出码却为 0。此问题使上传/复制中被截断且重新登记散列的页面证据进入“返回完整性通过”收据；后续人工无法复核相应页面。顶层 `native_pending` 及 `createsNativeApproval=false` 均保留，本卡不宣称脚本作出了人工排版通过结论。

反例原件：

- [PNG 反例返回](runs/25-native-header-only-png/checked/RESULT.json)、[CLI 收据](runs/25-native-header-only-png/COMMAND.json)、[8 字节文件](runs/25-native-header-only-png/synthetic-page.png)。
- [JPEG 反例返回](runs/26-native-header-only-jpeg/checked/RESULT.json)、[CLI 收据](runs/26-native-header-only-jpeg/COMMAND.json)、[3 字节文件](runs/26-native-header-only-jpeg/synthetic-page.png)。
- [WebP 反例返回](runs/27-native-header-only-webp/checked/RESULT.json)、[CLI 收据](runs/27-native-header-only-webp/COMMAND.json)、[12 字节文件](runs/27-native-header-only-webp/synthetic-page.png)。

最小修复：在确认 SHA、路径与扩展名后，校验实际图像格式、非零且有上限的尺寸，并验证完整容器/像素解码；截断、校验失败、未知格式应拒绝。根据仓库现有能力选择实现，不为此顺手升级运行依赖。PNG/JPEG/WebP 各保留正常图片正向与文件头反例，另补中段截断、无效尺寸或坏校验、格式/扩展名不匹配及过大像素反证。图片完整性通过仍不得代替原生应用打开证明或人类结论。

## 实际执行

入口为 [result_review.py](result_review.py)，汇总为 [SUMMARY.json](SUMMARY.json)，每例包含完整 argv、实际 Popen PID 与 checker 自报 PID、起止、elapsed、exit、四 guard、源码 SHA、结果 SHA 和关闭记录。本轮没有采进程出生时间，该字段明确 `not_collected`，未补造。

```powershell
$env:PYTHONPATH='H:\备份xuexi\智启课源\apps\api\.venv\Lib\site-packages'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
& 'C:\Users\96022\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe' -B docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/results/result_review.py
```

28 个 CLI 完整单轮，25 项匹配预先固定 oracle：6 个正常完整性正向、19 个正确硬拒；3 个图片头反例实际假通过。主入口退出码 1，如实保留首轮全部材料，没有调整正确 oracle 重算全绿。四 guard 在所有 28 个 checker 中均为 0；源码与旧材料零字节变化。

通过的主要判据包括三个真实生产适配协议 fixture 输出、合法可变分钟（C14 新数组 `[4,15,21,5]`）、总分钟不符/缺阶段/知识点及依据越界拒绝、原文与候选不符、raw/normalized usage 不符、累计 attempt 不符、教师字段及未选择字段保护、fixture 改标 live 拒绝、八维 boolean 分数拒绝、硬失败与 usable 冲突拒绝、错输出 SHA 拒绝、逐页漏页/PDF 元数据/错图片 SHA 拒绝、损坏 DOCX 拒绝。

本卡的 DOCX 是明确标识的合成 ZIP，正常页图为合成 1 像素图，只用于返回接口完整性对照。正常 teacher/native 返回均保持 pending，`createsTeacherApproval`/`createsNativeApproval` 为 false，RAG-REL 为 OPEN。

## 可复用与下一步边界

现行结果入口可复用 SHA/scope/累计 ticket/job/raw/wire/usage/candidate 关联、生产规范化与五字段应用保护、八维反馈完整性及逐页记录身份核查。当前 live provenance 显式硬拒属于已披露能力边界，不能靠改 label 或提供任意文件开启真实试评；下一阶段需和真实模型证明、可信宿主、真实授权来源一起明确升级。

教师最小返回：实际输出/候选/固定应用工作副本 SHA、评审者与时间、八维评分及原文位置/理由、硬失败、支持与不支持依据、修改建议、原始结论。原生最小返回：实际打开 Word/WPS 的应用与版本、实际页数、1..N 每页图和 SHA、五项观察及位置/理由、逐页与整体原结论；先修图片完整性 finding，再核真实返回。脚本仍只确认资料完整性，最终认可由人独立确认。

本卡未执行完整 check/API/E2E、新生产 fixture 生成、浏览器、服务、真实模型、教师评审、Word/WPS 打开、正式数据/Qdrant 或 Git 写操作；没有修改旧 QA、原 273 包、权威文档或 v2 计划书。
