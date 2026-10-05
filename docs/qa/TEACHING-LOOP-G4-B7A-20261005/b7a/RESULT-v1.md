# B7A-Q v1 离线入口作者结果：STOP，待独立验收

2026-10-05。实施前ROOT已交[需求矩阵](../B7A-REQUIREMENTS-MATRIX-v1.md)，SHA d6f533aad487ea2c3010564f4560f384b440dcd499d28e305d8dd0be24125d10，并关闭限定G4（收据SHA327f877…）。本卡仅新增prepare_review.py、专属test_prepare_review.py、专属README及本目录；旧G4三工具与52测试、原expected/15输出/旧QA、前后端产品、契约、锁与ROOT权威文档未写。

用户明确仅离线。本卡没有模型执行器、预算执行器、模型resolver调用、app导入、.env读取、网络、服务、浏览器、原生排版或Git操作。没有生成教师评分、模型存在声明或调用授权；原B6/B7整体和RAG-REL不关闭。

## 当前完整作者轮

[prepare-author-r3](prepare-author-r3-command.json)：PID2292，3762.170ms，exit0，**21/21**新工具窄测试完整通过。每个CLI在socket/app/.env拒绝guard内运行，22个CLI原件均networkAttempts/appImportAttempts/formalEnvReadAttempts=0；工具/QA/README前后SHA零漂移，原冻结1056份材料逐字节零漂移。

完整15、明确14 subset（C15 unrun）通过；缺C15、未知案例/错误集合、缺artifact、错误SHA、已填伪人审列、代表四导出少一例、实际PDF/PNG缺失、坏DOCX ZIP、错来源根、schemaVersion true/1.0、secret/unknown/重复键/非JSON/NaN、矩阵SHA错误与重复输出label全部拒绝。重复label第一份MATERIALS SHA保持。没有用作者通过数量代替独立验收。

首轮[prepare-author-r1](prepare-author-r1.log)完整21为15pass/6fail，PID22104/3666.700ms/exit1，输入与日志保留；同一新工具误把代表manifest.context的选择描述当完整contextSnapshot。新prepare修正为analysisRunId/KP身份关联，并全等核saved/before/after完整固定修订、11字段/context及前后全历史JSON、固定source标签。r2新完整21/21通过；随后专属README补充这两种结构关系，r3再核最终公开入口/说明的同源完整21，不拼不同轮片段，也没有改原业务断言或旧材料。

## 可交付正常材料包

[prepared-full-v1 使用说明](prepared-full-v1/README.md)、[材料SHA与状态索引](prepared-full-v1/MATERIALS.json)、[四文件原生逐页空表](prepared-full-v1/native-pages-feedback.csv)、[历史PDF13页参考索引](prepared-full-v1/pdf-reference-pages.csv)。该正常label仅生产一次；[实际命令](prepared-full-v1-command.json)PID12556/389.703ms/exit0，显式绑定[plan-full-v1](plan-full-v1.json) SHA9659953d9e6a8b03dd309f7f943c946879ae0d14d7fa8ae9a92ec0cb3ca7507f，guard三项0，新工具域及旧1056材料0漂移。

MATERIALS SHA46eaa6ce99c9fea2f617504262b75a2d1498f51de65afcc00767fd082c802b6f；原生空表SHA85bf5656126ad5e97a490adafffa274442aa6f7f0923442ef1bc42884085657b。显式scope在[scope-full-v1](scope-full-v1.json)逐一列C01～C15，expected集合由手写manifest和scope产生，不从results反填。

入口调用G4新failclosed aggregate，核旧15案例完整包及15实际DOCX；代表四DOCX、四旧实际PDF和13个原PNG/逐页proof精确SHA、rubric、15行原空feedback引用分别索引。旧fixture输出、旧PDF证据、本轮材料核查、真人教学判断、native与物理旧源各自分栏。既有15案例/DOCX/PDF没有重新生成或复制成新产物；只为反证构造少量明确标记的破损测试输入副本，原件只读且所有测试副本保留。

native表只有short/long/multi/symbols四个起始行；实际原生页号、页数、应用/版本、真人姓名时间、证据理由和结论全部空。教师须按实际Word/WPS每页追加行，不把PDF的1/8/2/2当原生页数。原八维feedback不改；需要真人填写时复制到新的教师评审label，再填原文位置、支持/不支持理由及修改建议。技术结构及合法引用不是教学质量。

## 冻结与未执行边界

新入口SHA50ce80157540b471e6e545882c28dbce90f2a434b328de700096f053ee1c34c5；新测试SHA3b3e03f0cd606c403d57b3f5e1b0d0d68cf8d0928e2afb2129ae792ad5ec600f；专属README SHA80d8fcfe6206e90330e9a3326ee5350e1105703dcc11790b1e01a5d2c31a5f4f。完整文件与命令清单见[RESULT-v1.json](RESULT-v1.json)。没有更改已验common/aggregate/scope_preflight及旧52测试。

physicalSourceCheck=not_run_source_temp_unavailable：旧四库/Blob只引用冻结来源绑定和旧物理证据，不能称本轮新物理复核；readonly-catalogs缺文件仍非0。liveRun=not_run_user_offline_scope，teacher_review_pending，Word/WPS待真人手动打开，RAG-REL OPEN，原B6/B7整体未关闭。未重跑无变更的check/174E2E/API/恢复/聊天或重新导出，G4门禁由ROOT精确来源域引用。

所有本卡CLI子进程、日志和文件句柄关闭，未启动监听服务；guard及全部TEMP/首败保留。工具、专属QA、计划/正常材料包与作者证据已STOP，等待ROOT新冻结及独立反证，未自签独立通过。
