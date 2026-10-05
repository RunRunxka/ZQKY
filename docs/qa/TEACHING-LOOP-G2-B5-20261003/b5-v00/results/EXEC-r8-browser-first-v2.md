# B5-V00 EXEC r8 browser first v2

独立接收本轮原完整 **8/8**；B5 阶段仍 OPEN，由 CTRL 汇总。只用 r8 单轮，不拼前轮结果。产品、可执行 QA、HTTP 均 STOP。

- Candidate `c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007`，938 source / 3061 QA / 33 frozen / 2004 build，build `FVU-OXmtBh9WBSHehixfE`。
- 固定 Node24，`v9/browser/external.config.ts`，label `r8-browser-first`，全8各1次 attempt / retry0 / workers1 / 45s / expect10s。PID18596，exit0，43533.495ms；Playwright stats42771.955ms，8expected / 0skip / 0unexpected / 0flaky，首败无。
- JSON/XML、完整log、50附件、8trace、样本全部保留。938/3061/33/2004/1702 prior / 原v11 221件 SHA drift0，runner源QA前后0、child/log closed。
- 22 PNG 已逐张实际 view，四视口390×844、1024×768、1440×900、1920×1080；未见阻断遮挡。图只说明视觉后态，交互由原 trace 和完整断言证明。
- 原 trace 离线11 HTML全含新build ID，53 static响应 / 12 unique资源与冻结构建 SHA exact。没有新发身份HTTP请求；r2额外身份政策拒绝保持 not_run。
- 188附件/全字段检查完整重新计算PASS；另8最终指针检查PASS。20 immutable正文/context/import envelope/selectedFields/process metadata/hash直接SQL相等；四库mode=ro、integrity ok / FK0 / bytes0、连接关闭。9documents / 28revisions / 28reviews / 4generation inputs / 4proposals / 4terminal decisions。
- 每主链导入v1→manual v2→所选 keyPoints/exercises v3→undo另存v4；手写11fields、teacher6、未选3字段、历史不可变、partial terminal accepted指针均核。历史复制全11、dirty/undo/redo/新save、A/B/history/local intent隔离、unknown真正manual PATCH200丢回执/continuedB/原包重放/nativeBack、双标签CAS409→显式基线→200及Tab/Escape均有本轮实际证据。
- 四 Word下载保存文件 CRC / ZIPXML / 原正文与六教师字段 / 冻结v3来源SHA核完。网络读取的是静态模板，生成Word为blob下载；不把两者SHA混同。四 actual print各0→1，间隔≥100ms，title均冻结v3 UUID；不宣称已保存原生PDF。
- 六公开JSON备份 schemaVersion1 / 手写全部11字段相等。四 finalwire / 三真实provider serializer协议全部匿名，actual participant/name/no/ID及固定run/class/score ID均无泄漏；只有隔离HTTP transport fixture。
- 原四固定业务GET全部200、与seed.originalFixed深等、响应关闭：PID20880 / 84.6759ms；HTTP STOP。ROOT API29412已正常关闭，server/watcher/transport/log全部closed/restored、sample retained、sourceDrift[]；V00没有起停服务。
- 前述审计v1六谓词错误及served MIME严格比较错误原件保留，v2只纠正非exec表达，v3从同原件完整fresh188复核。没有修QA/产品、业务复跑或拼绿。

同938产品的原v11全27单轮pass已独立封存；后端410文件与既有完整API1918+1及独立42 exact绑定，**不是修后新API重跑**。原full153由其他独立reviewer审本轮153/153；原chat14本轮14/14的离线图/资源审计随后单列，尚不以其命令绿替代视觉结论。

明确 not_run：Word/WPS人工打开、保存原生PDF、付费真实provider、正式Qdrant、额外身份HTTP（政策拒绝未重试）、新独立runtime四库恢复。已有恢复的作者真实执行与V00 readonly读取另表归因。

全部本轮 SQLite / 文件 handles 已关闭；TEMP、下载和附件保全。细项与SHA见 `EXEC-r8-browser-first-v2.json`、`R8-FULL-FIELD-ARTIFACT-AUDIT-v3.json`、`R8-FINAL-POINTERS-v1.json`。
