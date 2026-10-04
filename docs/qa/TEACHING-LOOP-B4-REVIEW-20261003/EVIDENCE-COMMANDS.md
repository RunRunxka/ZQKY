# 本轮验证入口

仓库根目录，2026-10-03，北京时间。只读产品源码；新证据仅本目录。所有旧B4对象不写入。

## 团队实际探针和窄回归

- [analysis/RESULT](analysis/RESULT.md)：隔离pytest新增4探针/20既有回归均exit0，首日志与XML见该目录。
- [frontend/RESULT](frontend/RESULT.md)：`NODE_OPTIONS=--no-experimental-webstorage`，独立Vitest配置3个正确行为断言失败exit1，既有4文件27回归exit0；原选择器首败保留并说明。
- [practices/RESULT](practices/RESULT.md)：真实FastAPI四库草稿改分后的原包恢复1failed/exit1，18既有回归exit0；另一个模板理想行为诊断仅作观察，首败全保留。

上述是本轮实际运行，不将B4原153/14/2或check1110/API1698计为本轮重跑。没有本轮build/服务/浏览器/真实模型/Qdrant/正式迁移。

## CTRL保全与文档检查

实际工作区为 `H:\备份xuexi\智启课源`。审计脚本只用stdlib/git只读命令，不导入app.main。

```powershell
$env:PYTHONUTF8='1'
uv run --directory apps/api python ../../docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/audit_review.py baseline
uv run --directory apps/api python ../../docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/audit_review.py final
uv run --directory apps/api python ../../docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/verify_docs.py
git diff --check -- docs/CURRENT_STATUS.md docs/NEXT_SESSION_START.md docs/README.md docs/PLAN.md docs/qa/README.md docs/design/teaching-loop-v1/README.md
```

`baseline`拒绝覆盖已有BASELINE。开工/收尾均exit0：r21五分组879/53/5/2007/191全部0漂移，两旧B4目录2916文件没有变更或新增，HEAD/分支/清单/next-env保持；完整结果见[BASELINE](BASELINE.json)、[FINAL](FINAL-VERIFICATION.json)。文档链接结果见[DOCUMENT-CHECK](DOCUMENT-CHECK.json)。链接首轮exit1仅因被文档引用的自身输出JSON当时尚未生成，原结果保留于[DOCUMENT-CHECK-first](DOCUMENT-CHECK-first.json)；输出落盘后复查，不涉及产品错误。`git diff --check` exit0，只有现有CRLF转换提示，无空白错误。

权威文档后续说明修改仅为本轮审查入口/三项待修与提示词索引，未重新冻结r21或修改其历史记录。下一批提示词另经未参与编写的Agent只读复核，补充了外部预检前receipt优先和旧ACK不倒退基线两项；这是规格修正，不是产品修复。
