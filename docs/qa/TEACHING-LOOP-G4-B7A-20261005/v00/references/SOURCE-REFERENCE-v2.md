# G4-REF v2 新候选引用域增量核对（STOP）

2026-10-05，g4_s。只新增本报告和JSON；v1五份原件before/after同SHA，未改或新增可执行QA。内联只读运行PID22220／363.272ms。新候选 `CANDIDATE-G4-fix-built-r2.json` SHA `f81a0684abdf734b067a731c089f798a3aabfe66a1f5d336ea1bd1506db34d6e`，build `VeOLFBYrp-8v24Yjm-HFi`。

新旧956源码映射仅两项变化，以下新SHA均与当前字节一致。旧整956已变化，不转签；本卡未重新核整970构建，ROOT负责新check1354/build及独立门禁。

| 文件 | v1候选SHA | 新候选／当前SHA |
| --- | --- | --- |
| `apps/web/src/features/lesson-plan/g4-recovery.test.tsx` | `b15a48f3cc970c96db961adb451c1931bb1952704727ca99ad78091b2aabbd53` | `4cb6c55ddb29c8cb2c1cd2fa31668da0ca38554e67cbe8853ecc523a23c76e71` |
| `apps/web/src/features/lesson-plan/model/useServerPersistence.ts` | `70db2c7c8ea8e13fa2e76050934c215fa8d14b3e7b4a59e26a3957e53741fcb0` | `32f52f32aa5d213ac9fb9d21541a566e531d580b4640619c357833ef79e36a21` |

| 限定引用域 | 当前字节核对 | 新candidate覆盖 | 本次执行边界 |
| --- | --- | --- | --- |
| backend410 | 410/410原SHA，before/after零漂移 | 410/410 | 原1918通过+1重型skip、独立42通过，只引用，未重跑API或恢复 |
| 最新UI chat关联186 | 186/186原SHA，零漂移 | 186/186 | 最新UI chat14原证据保持，未重跑chat |
| 导出／print／模板核心11 | 11/11原SHA，零漂移 | 10/11，根Word未列新candidate | 原Word由原B6/v1冻结SHA与当前字节绑定；旧整体export/styles43不转签 |
| 旧B6材料1056 | 1056/1056原SHA，零漂移 | 306/1056，750份历史产物未列 | 未列项仍逐SHA绑定原B6/v1；没有新生成15例或4DOCX/4PDF/13PNG |

规范映射SHA、完整v1逐文件清单引用、新candidate未列路径及before/after结果见 [SOURCE-REFERENCE-v2.json](SOURCE-REFERENCE-v2.json)。新candidate未列材料不伪称为其清单成员。

v1的60条reference再次按原身份核对：**59份存在文件原SHA一致，1份原缺证据继续未执行**。旧 `docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-exports/VISUAL-REVIEW-v1.md` 在v1 JSON已是MISSING_NOT_RUN、无SHA且不存在，当前仍缺失；不能将60个引用条目误称60份实在文件全部通过。内联首次校验在全60非空SHA断言处停止，未写文件或改产品；随后保留59+1原预期重新完成全轮核对，未补造缺件。

最新UI472仍有10项教案差异；相对v1只有useServerPersistence当前SHA变化，其他9项不变。作者测试不属于UI472。JSON逐项记录UI冻结SHA、v1当前SHA、新candidate及当前SHA。chat186包含全局styles并保持；旧B6整体43原12漂移限制不变，仅导出核心11可转签，不以旧PDF布局声称新build排版等价。

v1已公布报告SHA锚：

- `SOURCE-REFERENCE-v1.md`：`bd66246806b8b14640d1800e0eeb8d508eb6f5d03768a973dc779e1e1edf861a`
- `SOURCE-REFERENCE-v1.json`：`1e1f9817419476566ede5eb91e5ac15984e6c75c27938cf1f35731af229e4a1a`
- `RECOVERY-TEMP-EXISTENCE-v1.json`：`b08c555d7bad0c91dc6404381dbe2623a97eca9e77d215d0bcfe0b6b63a07536`

v1两份辅助脚本也before/after保持，SHA在JSON。原材料／chat执行身份仍分别是q84e_pxQoZ2_nwnws9QiI和8poFqRffbOe-w2FM8T0jy，与新build分开。

旧quality/export TEMP目录状态与v1相同，各4个SQLite仍缺失；原restore proof、canonical-data/restored-new目录和各4个SQLite仍缺失。本卡只查存在性，未打开或重建SQL／Blob、未新恢复。仅引用原冻结命令/JUnit/复制proof载荷，当前物理来源not_run_source_temp_unavailable；正式Qdrant6333／迁移／额外压力仍not_run。

原15行真人评分／理由为空，teacher_review_pending；live0，Word/WPS原生not_run，旧13PDF页签收只作历史引用，本次未重渲染或看图。RAG-REL保持OPEN，C10～C13不计真实RAG质量；CV01～03、R14、OBS-LP-MODE-LABEL、ERR_NO_BUFFER_SPACE首败／观察保留。

本卡只转签四个引用域，不关闭整G4或原B7。新保存／来源／离开真实浏览器及适用门禁由ROOT另验。应用导入、正式env读取、网络、SQL、服务、Git均0。JSON SHA `1aaad9c71854db9d3786d286a2397ce2a6877fdf613eea2bdf11880db86a289c`。
