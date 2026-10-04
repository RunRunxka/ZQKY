# B4-R09/R10-FIX-V00 v1 · r9 三轮独立结果

候选 `CANDIDATE-b4-r9-owner-fixed.json` SHA `ba5f0470d7ee7503e384cb68a39a9fdbf47a83745f54e9a9e96aa70feab739ba`，878产品/40执行QA/5契约。三个原 runner 按明确任务卡依次执行，未改源/断言/重试；每轮前后完整 SHA unchanged。第3轮首败后停止。

| 独立单轮 | 实际计数 | exit/毫秒 | PID/输出关闭 |
|---|---|---|---|
| r09-fixed-first，原4例 | 4pass/0fail | 0/4320 | 20560 已退出；stdout1053/stderr0 bytes，流关闭/日志独占读通过 |
| r10-fixed-first，原2例 | 2pass/0fail | 0/2989 | 23620 已退出；stdout906/stderr0 bytes，流关闭/日志独占读通过 |
| owner-fixed-first，原64默认-x | 0pass/1fail，余63未执行 | 1/2820 | 7864 已退出；stdout2532/stderr0 bytes，流关闭/日志独占读通过 |

R09 原正确行为全部通过：实际上传/人工 reviewed/confirm 的 local-user 题进入建议，并可手动固定 rid 保存和真实审核；标准题库 GET 拒绝 foreign 题；FixedQuestionReader 仍严格拒绝 local/foreign 跨 owner。Practice teaching owner仍local，四个新场景实际 question_owner_id=local-user。91实际HTTP/8真实HTTP正式题/16四库 integrity=ok，全部FK零违反。

R10 原正确行为全部通过：实际foreign题在标准服务的PATCH、DELETE均404/QUESTION_NOT_FOUND。请求后的foreign真实GET及只读全部question/revision行完全与之前相同，两题均confirmed/revision1，不新增修订或归档。46实际HTTP/4真实HTTP正式题/8四库integrity=ok。首轮未授权实改/归档的旧样本保持历史原状，不借修复撤销样本。

P首例不是产品owner回归：只读首败新库实际有9题ownerlocal（包含两道hard），一题实际标准seed ownerlocal-user/easy。原`probe_support.Scene.question`仍硬写local，修复后的标准Practice严格读取local-user，hard候选被正确排除，返回selectedCount0。P的标准Scene只由open_api_scene标准main创建，因此仅该造题owner表达式需跟实际QuestionBankService.owner_id。全部业务断言保留；教学SQLlocal、foreign身份负例以及作者独立手工域PracticesScene的local/default reader均不该统一更改。

原23声明test函数（14+9，原参数展开64）完整AST哈希/95+40=135测试assert、helper23assert和四执行源原SHA已保存在`OWNER-QA-ADAPT-PREP.json`；四源完整原字节另存`OWNER-QA-BEFORE/*.before.txt`，与原文件完全一致。根全量API仍运行时本Agent没有写任何执行QA。最小一表达式适配只提出建议，等待CTRL明确放行后再实施、另冻64完整单轮。

三个新OS临时根分别保留：

- `C:\Users\96022\AppData\Local\Temp\zqky-b4-r09-r09-fixed-first-be0ec87e2a3d47fa8428cf8369f8a822`
- `C:\Users\96022\AppData\Local\Temp\zqky-b4-r10-r10-fixed-first-70e7bcad94cf4ea1b49b8064cdf89414`
- `C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-p-owner-fixed-first-1cfa88dbf3d045eda2e636ed62ea0d28`

各完整命令/argv/cwd/env/时间、真实空stderr及资源见各label-receipt.json与日志；用户前端未操作、0监听、正式凭证未读。当前P本轮独立backup/verify/restore场景未执行，因为首例停止；此前r2 64通过/实际恢复HTTP仅作历史结果，不冒充r9本轮通过。B4仍未关闭，FULL-E2E尚未放行。
