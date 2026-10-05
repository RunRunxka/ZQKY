# D00 准备 STOP v1

已读本批用户授权、root AGENTS、CURRENT_STATUS、PROJECT_GUIDE、任务卡、OPENING 与 ROOT 草稿 REPORT/README。仅本目录新增 PLAN、ORACLE 和标准库只读后验脚本；Python AST/JSON 解析通过，实际 OPENING SHA 与 oracle 的64位值相同。当前未执行正式审计，未签 PASS。

冻结准备 SHA：

- PLAN-v1.md：ab2ffff93cdf735e9f97ccf1590f50ef7118baa498ea88c9bc02bbc327a3f70d
- ORACLE-v1.json：31ce26e2a95154f1922923b3ed1a04f6da395ffeb9395c60388efeab5f0a57a1
- audit_documents_v1.py：de98f77295f686d05a885532b4c8848ea2eb6ebd78b639e69272441f3f416d5b
- OPENING-v1.json：676831c8b441388108c80d1ffaecc15c239c66b0155ed40b021843ac2f3c738f

最终 INPUTS 字段：release=`ROOT_FINAL_DOCUMENTS_REVIEWABLE`；candidate/candidateSHA；documents/evidence 为相对路径→SHA字典；gates 为 check/components/browser/full174/b7b_independent/result_identity（每项 commandRecord/commandSHA/rawEvidence/rawSHA/rawFormat/claims，JSON claim为pointer/expected，文本claim为literal）；branchMatrix 六项各status/reason/evidence；realModelCalls=0；manualAssertions须由D00实际独立逐项观察填写；separatePostCandidateDelta=true；deferredROOTFinalization列ROOT审计后追加边界。所有最终证据必须实际已存在，INPUTS放本目录，脚本不修改输入。

ROOT 可先在 ctrl/ 形成原始确切路径/SHA输入草案，最终释放后D00据冻结原件核行与语义，再写本目录独立索引。ROOT runner统一执行新label，输出 runs/<label>/RESULT-v1.json/md，失败不覆盖。最终资源/INTEGRITY/封印后追加不提前依赖；已有 G6 资源收据可作为当前存在证据。

本准备没有 app 导入、HTTP/身份probe、数据库连接、正式.env/草稿/6333读取、Git命令/写入、服务/用户进程或真实模型操作。本目录执行QA现已停止写入；等ROOT all候选冻结及明确最终文档释放。
