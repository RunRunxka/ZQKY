B4-R14-V00-METADATA v1.2 作者窄修正完成；未运行浏览器或服务，不是恢复业务通过。

传播结论来自源码语义与精确唯一差异，未执行附件拒绝故障注入或浏览器场景。

只在finally的info.attach外包try/catch，将附件拒绝describeError追加既有cleanupFailures。有主体primaryFailure时原catch已经重抛，finally不再以附件异常替换首败；无主体失败时原cleanupFailures.toEqual([])继续明确失败。没有新增重试、吞主体异常、改UI操作/oracle/matcher/标题/超时/deadline/helper/config/product。

r19 before SHA256 6ca6f9281f1e1e13861db15c85c860a126c5d7ca1e23557b5b92e9b4287777a8，新源 SHA256 b91844519626705be87c6ac6dcf9c6deae91d40bb144589799f2346faeadfc79。反向去除此唯一wrapper后逐字节完全复原r19原件；两原标题与61条含expect源码行全同，所有matcher原文全同。完整准确diff：

```diff
--- r19.before
+++ r14-recovery.v12
@@ -261,10 +261,14 @@
     if (clickProbeInstalled) {
       try { clickProbe = await removeClickProbe(page); } catch (error) { cleanupFailures.push(describeError(error)); }
     }
-    await info.attach('r14-independent-facts', {
-      contentType: 'application/json',
-      body: Buffer.from(JSON.stringify({ scenario, startedAtMs, deadline, target, expectedNote, expectedClicks, before, result, after, finalLocks, independentClickProbe: clickProbe, helperCleanup: cleanup, primaryFailure, cleanupFailures }, null, 2)),
-    });
+    try {
+      await info.attach('r14-independent-facts', {
+        contentType: 'application/json',
+        body: Buffer.from(JSON.stringify({ scenario, startedAtMs, deadline, target, expectedNote, expectedClicks, before, result, after, finalLocks, independentClickProbe: clickProbe, helperCleanup: cleanup, primaryFailure, cleanupFailures }, null, 2)),
+      });
+    } catch (error) {
+      cleanupFailures.push(describeError(error));
+    }
     if (!primaryFailure) {
       expect(cleanupFailures).toEqual([]);
       expect(cleanup?.resourcesReleased).toBe(true);
```

原完整六TS types限定单轮actual exit0 / 785.902ms / PID22136；stdout/stderr 0/0B，真实全部内容明确存R14-QA-METADATA-v12-types-command.json，空字符串不省略。自然退出、两pipe关闭、六输入posthash零漂移，新OS根C:\Users\96022\AppData\Local\Temp\zqky-b4-r14-p-meta-v12-types-dymawtvs保留。收据SHA256 1e1d19357259590892bad76d314a3d00f123b429686c7c075aaba1b637ec6b97。

原完整六TS lint限定单轮actual exit0 / 1246.303ms / PID6936；stdout/stderr 0/0B，真实全部内容明确存R14-QA-METADATA-v12-lint-command.json，空字符串不省略。自然退出、两pipe关闭、六输入posthash零漂移，新OS根C:\Users\96022\AppData\Local\Temp\zqky-b4-r14-p-meta-v12-lint-poai7h30保留。收据SHA256 33113abeec981455bdc936fa04754621bff127f86162afad6f32ab0badb3b87f。

旧r19/first/v11全部证据保留，v11三件SHA重新只读登记于新JSON，不修改旧结果。不调用Git、main、浏览器/监听/服务或构建。新源已停写，等待CTRL工具前缀适配后冻结r20，不能称新source与r19冻结同源。
