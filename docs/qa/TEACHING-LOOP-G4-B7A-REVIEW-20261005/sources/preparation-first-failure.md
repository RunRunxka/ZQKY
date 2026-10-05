2026-10-05。首次运行 run-narrow.ps1 的冻结读取步骤退出 1，Vitest 尚未启动。

原命令：`& ./docs/qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/sources/run-narrow.ps1`

原输出：
```text
Get-FileHash: H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G4-B7A-REVIEW-20261005\sources\run-narrow.ps1:20
Line |
  20 |  … askPath] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $t …
     |                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Could not find file 'H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G4-B7A-20261005\v00\product\helpers.ts'.
```

归因：本审查 runner 将既有 helpers.tsx 误写为 helpers.ts；仅修本目录 runner 路径，原产品和原 QA 均未改。此准备错误不计为产品或测试失败。
