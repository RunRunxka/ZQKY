# 新会话接手（最小骨架版）

1. 读 [AGENTS.md](../AGENTS.md)（结构/命令/红线/环境坑，特别是 uv `python -m` 入口坑）。
2. 读 [CURRENT_STATUS.md](CURRENT_STATUS.md)：当前形态为「对话 + Agent + 模型配置」骨架；
   台账列出 Qdrant 集合待清、e2e 对齐、模块级 AGENTS 更新、业务重建四项待办。
3. 需要历史实现参考时，一律经归档 tag 读取：
   `git show archive-full-v1-20261011:<path>`（不要直接捞回工作区）。
4. 开工检查：`git status` / `git log -1`；验证命令 `npm.cmd run check` +
   `cd apps/api && uv run python -m pytest`。
