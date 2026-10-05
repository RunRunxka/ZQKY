# B4-R11-F-QA-PREP v1

READY，全部可执行源码已停写，未执行新种子/浏览器/服务。仅real-browser.spec.ts在初次facts可见和returned facts可见之后各新增一个await expect。固定报告历史区域内selected `button.primary .b4-meta` 必须逐字显示对应runId与“已准备”，不会由另一份已就绪报告代替本报告。

修前原字节保留real-browser.spec.r10-before.txt，SHA256 `66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156`；新spec SHA256 `e8ca4cc6def1d2d320552f949962527dd503d7dcbf6c3933aa476275f5a062ef`。只删除两个新Await和插入换行即可逐byte恢复。静态TypeScript AST解析0错误，移除两个新Await后全AST打印文本完全一致；原116 matcher（115原业务+R08导航等待）均原文保留、新118；两个poll全文/计数2→2原样。原流程/API/PII/时间/字段/期望数字不动，returned既有combined line只为插入新assert拆行，不改原语句顺序。

seed SHA `f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada`、原6个assert完整；runner SHA `f30ef3002b6ec2e974806ff77b713b6b524d630360b602a44d1c9830915fa6d0`保持。新增两matcher准确全文、diff、AST计数、全命令和原输出在QA-R11-PREP.json及QA-R11-AST.json。字节准备exit0/内部4.208ms；AST静态命令exit0/工具0.2770355s，不计业务执行。

第四轮actual1pass/child0/outer0及533项trace/17PNG/三下载/8回流等原件完整保留；那一轮没有这两个新正确断言，不能用于R11新就绪/对比修复闭合。等待CTRL/P红测、产品修复、新freeze/build与用户手动前端条件后，以全新第五样本执行。

