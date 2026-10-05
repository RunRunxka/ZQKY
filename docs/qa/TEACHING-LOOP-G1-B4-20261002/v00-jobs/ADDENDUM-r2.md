# G1-V00-JOBS r2 覆盖审计补充

仅追加审计，原 RESULT.md、52 个行为探针及原首跑证据保持原样。结论 **pass**。

- r1 原 825 项与 r2 共同 825 项逐项 SHA 完全相同，0 改变、0 删除；r1 清单本体 SHA `1c6ba3c16f5db6e0e008ed1c24e9629e521ce9f852dd4b8077e392ed278ed305`。
- r2 完整 826 项与实际工作区逐项 SHA 完全相同，0 漂移；r2 清单本体 SHA `9471f43eb5ba9cde9d79ab65b84f5cf1fcd607729b1ad2388d2bfde5c78a072b`。
- 旧 629 份证据全部逐字节 SHA 相同，0 漂移。
- 唯一新增覆盖项为 `apps/api/.env.example`。它已被 Git 跟踪，工作区与暂存区均无 Git diff；当前文件按 Git 换行规范归一化后与 HEAD blob 完全相同。这是覆盖过滤器补漏，没有新增产品行为或配置修改。没有读取正式 `.env`。
- 分支仍为 `main`，HEAD 仍为 `6aeb57280f6a7e0d7391cad4d150745479ea58ec`；产品、原 RESULT 与原行为证据零写入。

行为候选未变，**未重复执行 52 个探针**。原首跑 `52 passed / exit 0` 继续适用于共同 825 项；本补充实际新行为运行次数为 0，不能把这次 SHA 审计计作再次运行 52 例。

实际命令（PowerShell 根目录，exit 0）：

```powershell
& apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-jobs/audit_r2_addendum.py
```

完整 826 项实际 SHA、629 项证据 SHA、r1/r2 对比和新增项 Git 校验收据见 r2-coverage-audit.json。脚本仅使用标准库与只读 Git 命令，未导入 app 模块、未创建业务数据、未监听端口、未构建。只写本目录此补充与独立脚本，完成后再次停写。
