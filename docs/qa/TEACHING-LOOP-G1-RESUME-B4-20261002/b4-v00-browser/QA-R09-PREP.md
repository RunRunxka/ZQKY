# B4-R09-F-QA-PREP v1

READY，全部可执行 QA 源已停写，等待 CTRL 稳定候选。未执行新种子或浏览器。

仅 seed.py 第125行正式题 fixture 的 owner 参数，从硬写 `"local"` 改为 `application.state.question_bank_service.owner_id`。读取标准主装配的实际题库身份，不改 QuestionBankService 的身份，不放宽固定题归属校验，也不修改产品、旧种子或旧数据。

原字节保留为 `seed.r09-before.txt`，SHA256：`4f50256da7bc41bd7c09b6be3364969eae8f7a66999fd811b19ee4509970d044`。新 seed.py SHA256：`f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada`。逆向替换这一个表达式即逐字节恢复原件。全部13个可执行 QA 源 SHA 见同名 JSON；只有 seed.py 改变，其他12件不变。

R07 全部真实来源块、初种子 HTTP 图片状态/完整字节/SHA/MIME 校验原样保留；6个原 seed assert 全文一致。R08 导航等待及浏览器原断言均不变，real-browser.spec.ts SHA256：`66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156`。静态 AST 解析无错误；准备命令 exit0，内部计时32.812ms，工具 wall time 0.2102052s。完整命令及原始输出在 QA-R09-PREP.json，本轮仅静态准备，不计为种子或业务通过。

原 real-second 的导入 GET500/21字节非JSON响应与各轮日志/trace保留，未将其归因停服务或由本准备宣称解决。没有启动/停止服务、删除目录、修改旧样本或执行新 HTTP 请求。

