# G2-V00-QA v7 · 原生 Back 真实 SPA 历史前置绑定

2026-10-03，北京时间。CTRL新卡仅授权准备；v7 PREPARED_NOT_RUN。v6已冻结原件/manifest/delta保持原样，v6 browser精确17920B（SHA b2f43b82197b23dc6c1224b53651dd260d2bb867e8f0b5cd879d305d19c8e9c6）保留 browser/correct-behavior.spec.ts.qa-v6.before.txt。现 spec SHA 962608a25866e11c9c6c5a5d553a3ee34801e5f5e20224bbdadeb64e5a694077；没有执行测试/产品/工程检查，也没有起停服务、写产品/权威文档或操作Git。

仅在原keep/save两个native Back case插入前置身份绑定：goto真实question-bank source后，在原expect10s内只读poll history.state，要求 __NA===true、__zqkyNavigationPosition 为有限number，再保存source stamp。仍点击原真实Next Link；练习输入可见且可编辑后，只读取target stamp，要求有限number且不同source。没有写history，没有test-only pushState/replaceState，未替换Link或Back。

静态bytes/text/hash比对仅有插入，移除新增区块后严格字节等于v6。所有原native取消/keep/save/URL/编辑字段/回流/截图及其他case原行保留，v6两条第二ACK成功终态等待保留。共8case、retries0、test45000ms/expect10000ms/unit23/API11预算不变，其余8执行QA字节不变。静态结果嵌入新manifest，不执行TS模块或浏览器。

静态文档helper的两次启动错误完整记入manifest：第一次stdin line12 TypeError: sequence item 0: expected a bytes-like object, list found（嵌套byte slices的join缺少展平）；第二次stdin line16 AssertionError（赋值子串检测误匹配严格等号===）。两次均发生在新delta/manifest创建前，只修helper本身，未执行或改变QA源码/产品来修错，未隐去工具报错；不将它们计作业务门禁。

v1/v2首败RESULT、原源码、HTTP logs/XML、新TEMP和44四库证据保持原样。此处是执行前历史身份前置准备，不构成产品修复或通过证据。QA再次停写，等待CTRL G2-r3稳定候选SHA与正式新卡；browser执行仍须单独runtime/seed身份放行。
