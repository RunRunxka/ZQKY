# G2-V00-QA v3 · 执行前隔离适配

2026-10-03，北京时间。CTRL明确批准本最小差异。状态仍为PREPARED_NOT_RUN；没有执行pytest/Vitest/Playwright或产品/工程检查，也没有启动、装配或停止服务。

只读核CTRL runner发现，run_api.py会把tempfile.tempdir放到新sample/tmp，独立guard旧读法tempfile.gettempdir因而不能表示原操作系统TEMP：它会错误拒绝合法sample/data和sample/pytest。API guard及browser seed现在只从原OS环境TEMP/TMP识别系统根，保留路径/prefix/data存在性及test/UTF8等全部隔离条件。CTRL同时负责在自己的run_api创建sample/data。

没有改变任何业务断言、测试输入、计数、场景或预算。两个修改前原字节在`.qa-v2.before.txt`保留，v1/v2 manifest不改。此处是执行前接口适配，没有业务首败或被隐藏重跑。

unit应由显式Node24运行，argv中的Node固定为`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`，读取文件VersionInfo为24.19.0；不通过node/npm别名推断运行版本。Python入口为仓库`apps/api/.venv/Scripts/python.exe`，runner在app导入前配置全部隔离。执行仍须等待CTRL新候选SHA及放行。
