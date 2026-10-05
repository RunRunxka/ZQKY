# R14-QA PREP v2 · 忙态判据窄修正

状态：**作者限定静态自检完成，待独立审查/真实UI验收**。全部source/QA已停写；没有执行浏览器、服务或全量测试。

唯一源码改动是helper删除原134–136行busy按钮设置resumed=true三行。原修前完整字节保存为 `R14-QA-v2-helper-r20.before.txt`，没有覆盖旧before/静态收据/首败。新helper SHA：`73a6eb0837350896b40e864743ae5c1baa4f4453825d0eb3a46a1eddc2000087`；原r20 SHA：`cb6407c8045c35dc0ae54915c9854b0ab9275b17f9654ef3aa9dbfedfee0a072`。独立字节比较确认新件精确等于旧件减该唯一三行，前后其余字节一致。

r20首轮normal通过、故障真实trusted Continue后4ms误判的原1pass/1fail结果保留。A独立报告已把pending请求busy与真正working执行分开；未认证恢复完成或锁/租约根因。v2只以原真实准备/编译UI作为恢复执行判据；忙态不启用再次中断。真实ready、一次点击、错误拒绝、重复中断、原绝对deadline和全部清理保持，未将旧interrupted当成功。

原spec仍SHA `b36e6b41fa441a0972d172b632464b085561e0afdb6546d0b88475e8ceae27f9`，与r20逐字节一致。6标题/其它5callbacks/原49expect全文及两个30000 poll、两个120000完成等待和180000总预算均由本轮静态AST重新核对；现52expect是静态表达式数，不是运行断言次数。P独立spec也逐字节同r20，未写入。

本轮限定静态收据各实际执行一次：

| 自检 | PID | exit | elapsed ms | stdout/stderr bytes |
| --- | ---: | ---: | ---: | --- |
| strict TypeScript noEmit + AST + 三行byte oracle | 14916 | 0 | 726.1723 | 2398/0 |
| 原两QA文件ESLint --max-warnings=0 | 3876 | 0 | 1129.2549 | 0/0 |

所有child自然退出、stdin/stdout/stderr和实际日志关闭；JSON保留完整argv/stdin/原流/hash/起止时刻。没有复用v1/v1.1静态结果为v2，没有新运行恢复两例或原153。

交付后停写，等CTRL r21稳定候选与A/P独立验收；所有原首轮失败和聊天14证据保持原样。
