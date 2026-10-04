B4-R14-V00-QA-TYPE v1.1 作者静态自检完成；未执行浏览器/服务，不是独立真实分支验收。

原r18 QA strict首轮在199/243行TS7006，exit2，2214.16ms/PID12208，原before及first命令/日志保留。唯一修改为readBookFacts的pages增加Array<{id:string;status:string}>显式类型；反向去除此一类型标注后逐字节完全等于r18原件，所有runtime操作、oracle、expect、场景/标题、两180000ms/120000ms/deadline、helper、配置、产品均未改。

before SHA256 d8bdb7a529ef5bcefaa219159bf2389308fba1397e3b858751869df5a0ba0e41；after SHA256 6ca6f9281f1e1e13861db15c85c860a126c5d7ca1e23557b5b92e9b4287777a8。六TS使用原完整strict/noEmit/incremental false命令单轮，actual exit0 / 696.532ms / PID22020，stdout与stderr各0/0B（完整内容明确存JSON，空字符串也记录），子进程自然退出、两pipe关闭、六源post hash零漂移。新OS temp C:\Users\96022\AppData\Local\Temp\zqky-b4-r14-p-type-v11-uj84wpjo保留；main未导入、无浏览器/监听/服务/构建/Git命令。原r18仅作为原件来源，当前一处授权类型差异不伪称r18全零。

```diff
--- r18.before
+++ r14-recovery.v11
@@ -51,7 +51,7 @@
       if (notes.length !== 1 || typeof notes[0].content !== 'string') {
         throw new Error(`Independent oracle: note on ${pid} missing/malformed`);
       }
-      const pages = book.pages.map((item: { id?: unknown; status?: unknown }) => {
+      const pages: Array<{ id: string; status: string }> = book.pages.map((item: { id?: unknown; status?: unknown }) => {
         if (typeof item.id !== 'string' || typeof item.status !== 'string') {
           throw new Error(`Independent oracle: page identity/status malformed in ${id}`);
         }
```

完整argv/env/start/finish/exit/PID/ms/stdout/stderr及SHA见R14-QA-TYPE-v11-command.json。准备已停exe写，等待CTRL合并guard工具修复与新r19冻结后正式单轮放行。
