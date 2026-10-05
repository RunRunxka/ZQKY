# B4-P-OWNER-QA-ADAPT v1 · ready

仅按CTRL明确任务卡改`probe_support.Scene.question`唯一表达式：`insert_question_in(...owner_id="local",...)`→`owner_id=self.app.state.question_bank_service.owner_id`。这个Scene只由标准main构造，因此自有新候选题应使用实际题库服务owner；不把其他库local或foreign负例统一改掉。

修前完整原字节保留于`OWNER-QA-BEFORE/probe_support.py.before.txt`，SHA `5f3107ec5582fcb0c30adc98e12f21a767cf176222498dfd04760761fd7f9448`。修后逆替该唯一表达式与修前逐字节完全相同；原helper23条assert AST完全一致。两份原测试及runner与before副本逐字节一致，原135条test assert、23声明函数/原参数展开64例保持，所有教学local、foreign/wrong-owner、作者手工域local/default reader及R09/R10原6例断言保持。

新`QA-SOURCE-MANIFEST-v1.3.json`包含正确的新helper及原两测试/runner全部SHA；v1.2和所有首败收据不覆盖。`OWNER-QA-ADAPT-v1.json`保存精确一行diff与静态核验。不导入app、不运行pytest/种子/服务，只做静态AST与字节核查；执行源已停写，等待CTRL完整候选冻结后原完整64一次复验。
