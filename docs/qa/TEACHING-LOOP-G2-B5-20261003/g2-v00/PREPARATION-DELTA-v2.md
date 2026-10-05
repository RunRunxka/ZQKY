# G2-V00准备源码 delta v2

2026-10-03，北京时间。准备manifest v1保持。编写后静读发现零参数vi.fn回调会将mock.calls类型推导为空tuple，不适合后续读取原HTTP参数；两处独立unit源码改为显式参数类型并消费参数，测试行为及全部断言不变。各自修改前原字节在 `.prepared-v1.before.txt` 保存。

状态仍为 **PREPARED_NOT_RUN**，没有运行任何产品或工程检查。manifest v2将登记实际准备源；旧v1仅保留准备当时SHA，不套当前源。CTRL冻结候选之后才实跑，首败照常保留。

CTRL指出原browser链只测从别处Back返回练习，不能当dirty练习原生Back离开。因此在源里追加真实Next返回练习Link建立历史条目，再由dirty页调用原生history.back：取消保原URL/输入，分别明确保留或成功保存才重放原遍历。另外追加两个不同目的地的真实mouse点击，modal只能有一份，最终只执行第一个原目的地，返回仍为原练习。browser准备声明现在是8例（含Back的两份参数实例），未运行或实际计数不变。

browser修改前源码也保留为 `.prepared-v1.before.txt`。准备读取另曾误猜独立NavButton文件，已改读实际公共壳来源；没有产品执行失败。

CTRL公共窄审发现的两边界追加独立准备：同operationId/submissionId/body但替换首次contextKey/editGeneration/loadGeneration的recovery分别应false，并在后续submit中保持完整原对象；guard A等待期间新注册dirty B，原导航结果应false且action零次，新发导航再由B明确拒绝。unit源现为4文件，全部仍not_run。
