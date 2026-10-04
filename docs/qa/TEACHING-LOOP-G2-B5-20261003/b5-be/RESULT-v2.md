# T90-BE v2 窄修结果：45 例作者自检通过，待独立验收

2026-10-03；负责人 `/root/g2_be`；CTRL 正式授权 T90-BE v2。共享冻结 manifest SHA 仍为 `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db`。v1 的 RESULT/MANIFEST/44 例原轮与全部首败原件均保持。

实际仅修改两文件：`services/lesson_plans/service.py::_current` 的内部归档新操作拒写由 `LESSON_INVALID/409` 改为冻结 `LESSON_INVALID/422`；`tests/test_lesson_plans_api.py` 新增实际 HTTP 边界用例。该例先保存成功再归档：新 submission 正确 422 且 immutable revision/review/receipt 无新增；原 submission 仍先返回 200 与完整原成功 receipt（replayed=True），不重写后续 head。

修前全部 11 个私有源与 v1 manifest 精确匹配，原字节保存 [BEFORE-v2/](BEFORE-v2/)，其 MANIFEST SHA `901212a250f1b3fba1a66545ea5f4fb9f57ea392bb146cc7a892a81abe7c6c85`。没有修改公共/冻结文件或旧 QA。

新单轮 `b5-be-v2-r1-archive`：**45 passed / 0 failed / 0 errors / 0 skipped**，PID **24264**，exit **0**，整命令 **20983.928 ms**，pytest **19.776 s**，sourceDrift=[]。原 44 例与新增例完整复验，没有只跑新增例来代替原行为复验，没有弱化原断言。保留一条原 Starlette/anyio deprecation 警告。

实际命令为仓库根：`powershell -NoProfile -File docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-be/run-self-tests.ps1 -Label b5-be-v2-r1-archive`；固定 Python 3.12 venv 经 CTRL run_b5_api 运行四私有测试文件。完整 argv/env/PID/exit/ms/源前后 SHA 在 [command receipt](../ctrl/b5-be-v2-r1-archive-command.json)，全 [stdout](../ctrl/b5-be-v2-r1-archive.log)、[XML](../ctrl/b5-be-v2-r1-archive.xml) 保留。v2 执行前完整字节快照 `b5-be-v2-r1-archive-source-snapshot/` 与执行 sourceBefore 逐项匹配，零漂移。

main/pytest 导入前新 OS TEMP/test/UTF8，Settings.credentials_file=None、空教材、Qdrant 16333、embedding 9、KEEP_TEST_DATA=1、显式新 --basetemp。样本根 `C:/Users/96022/AppData/Local/Temp/zqky-b5-ctrl-b5-be-v2-r1-archive-kc7x7dwr` 保留，公共 conftest 生命周期保持，由 runner 仅对当轮经过绝对 containment 核实的样本保全清理。fixture finally 关闭 JobEngine/Rag，catalog contexts 关闭连接；TestClient app lifespan 与日志均已关闭。没有起停 TCP/前端/build，没有读取正式数据/凭证/草稿，没有 Git 或远程操作。

v2 来源与停写记录见 [MANIFEST-v2.json](MANIFEST-v2.json)，SHA `f2f0ac97255be0fb947f81af7dc5136d69e66798770182d957f039166c7f9c6d`。service SHA `597aff473e3a6c549055dba8f03980262839ab3ebdc9c83f5b724f098b1988e6`；API 测试 SHA `653ae6748cb4cfeab946a1af8ee8202fc055f86fd3b0c211fbd256d69eedf930`。其他 9 私有源保持 v1 SHA。

产品与测试再次停写，原静态差异已修。仍只标作者自检通过/待独立验收；完整 API/check/e2e/chat、独立 V00/浏览器/备份恢复/正式迁移/真实供应商质量/Word-WPS 人工验收在本卡未执行，原因与边界继承 [RESULT-v1.md](RESULT-v1.md)，由 CTRL 适用卡后续完成。
