# V00-Q v1 独立预期（运行前手写）

2026-10-05，g4_s；只读质量工具，唯一写本目录。未运行未 STOP 的 G4-Q 工具。本文件与独立脚本先冻结，再由 ROOT 提供三个工具 STOP SHA；不存在从实际结果反推预期集合的步骤。

冻结预期 manifest：原 `b6-quality/case-specs.json` SHA `353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55`。预期完整集合逐项为 C01、C02、C03、C04、C05、C06、C07、C08、C09、C10、C11、C12、C13、C14、C15；显式子集为 C01～C14，C15 必须单列 unrun。原候选 SHA `f79ac91201f3d5ecedab2cf01ea92a2ebc0b6d794e7fa18ebf9e3796e0e54db9` 用于固定每个原件，而非使用 SUMMARY 的 caseCount 作为 oracle。

预期正常汇总：完整 15/15 与明确 14/14 均完成实际逐例技术结构及 DOCX 结构核验；对应 checked/technical/docx 三个计数分别等于 15 或 14。教师分数保持 null/pending、live未运行。frozen-source-binding 只可将完整冻结 canonical/source identity 绑定标 PASS；旧 TEMP 当前 SQLite 已缺失，物理四库和 Blob 必须 not_run，不得伪称新核实际数据库通过。readonly-catalogs 对同一缺库明确非零，不迁移或重建旧库。

预期硬失败：未授权全集漏 C15（原反例：caseCount15/results14）；计数改14也仍失败；重复ID、额外/未知ID、缺DOCX记录或文件、缺CASE结果、SHA不符、错误 source/source row canonical/固定身份均退出非零并且无通过计数。坏 ZIP 的深入反例将新复制件 DOCX、manifest 与 export binding 的新 hash 一致绑定，以确保不是只在外部 SHA 步骤失败；预期最终 BAD_ZIP，旧文件保持。

范围预检的七种原非法输入，以及空白/非字符串模型、caseIds 非数组/空/未知/重复/非字符串、sampleCount 的 bool/0/负数/浮点/不等长、maxAttempts 的 bool/0/负数/浮点、无预算或 null/bool/非正/NaN/Infinity预算、非JSON/重复键/数组根/凭证或未知字段，全部非零并给字段定位。正确全集、明确 C10～C13、单例子集只通过范围形状预检，不能宣称模型已验或产生授权；maxAttempts纳入canonical scope hash，增加次数仅显示需要额外授权，不构成执行。

每条子命令在独立网络／应用导入／正式env读取阻断器下执行；记录实际调用尝试数、PID、UTC/北京时间、退出码、源SHA before/after与新输出原件。每项新目录不可覆盖；首败保留。没有模型请求、服务、浏览器、Git或用户缓存操作。
