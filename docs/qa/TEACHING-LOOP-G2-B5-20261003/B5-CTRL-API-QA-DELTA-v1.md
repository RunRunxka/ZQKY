# B5 完整后端首轮归因与现行测试适配

2026-10-03 18:16，CTRL唯一写入者；原完整单轮 `b5-api-full-backend-v1` 为1912通过/5失败/1既有规模skip，exit1/371244.395ms/PID22280，410绑定文件0漂移。完整log/XML/source/sample保留，不把该轮当通过。

三备份CLI失败均来自父解释器启动时仍GBK模式，而runner在进程内设置PYTHONUTF8使子CLI输出UTF-8，`subprocess.run(text=True)`父reader按GBK解码抛UnicodeDecodeError，stderr为None。保留原断言与备份test所有字节；后轮在启动Python解释器之前由PowerShell明确设置PYTHONUTF8=1/PYTHONIOENCODING=utf-8，再运行同一guarded runner。未删除CLI检查、降低中文断言或改生产备份代码。

另两失败为原测试仍要求`lesson_plan_ai_fill`为planned、GET lesson-plans为501。正常main已装真实服务与执行器，本批明确授权实现该能力，故CTRL保存两test修前原字节后更新现行预期：正常能力ready；缺真实service时unavailable且GET503；lesson列表移到真实200/完整空owned Page检查，剩余规划端点继续原501/错误信封检查。旧lesson参数case由新真实路由case完整承接，不仅删除失败项；补依赖缺失反例1例，完整预期数量增加1。

修改仅apps/api/tests/test_capabilities.py与test_not_implemented.py；原0001～0009声明、冻结33件、业务源和备份test不改。两份修前bin在ctrl，后轮重新建立SOURCE/candidate并窄复验，再补完整工程API。仍待独立业务/新build/browser/153/14，B5未关闭。

随后UTF8父解释器新窄轮`b5-api-qa-adaptation-v2`30通过/1失败、exit1/28012.788ms/PID28352、410源0漂移，parentUtf8Mode=1/preferredEncoding=utf-8；原三CLI失败均已正常完整执行，无reader解码异常。唯一新失败是CTRL新增成功Page case沿用了错误响应专属x-request-id假设，实际成功契约未要求该header。保全新增case修前字节后，仅改这个新case为成功JSON content-type与完整四字段Page检查；剩余规划501/错误requestId检查全部原样保留。不改生产middleware/断言预算，另新label复验。

18:32补记：同3文件新单轮v3 31/31、exit0/27908.894ms、PID14120已退、410 source0；父UTF8=1/preferredEncoding=utf-8，原AnyIO warning1。新完整轮b5-api-full-prebuild-v1在稳定候选上运行中，不能以窄轮替代。
