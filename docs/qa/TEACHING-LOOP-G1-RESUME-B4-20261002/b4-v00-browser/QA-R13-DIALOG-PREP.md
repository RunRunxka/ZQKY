# R13 independent dialog environment preparation

Status: prepared; all executable QA stopped; no test, seed, service or browser execution.

The r16 green-first real run was one passed test and one QA environment error: the now-open actual generation modal called jsdom's missing `HTMLDialogElement.showModal`. The original complete log, command receipt, candidate and retained temporary root are unchanged. This error is not counted as product pass or failure.

Only this independent QA file changed. Before bytes are preserved in `r13-navigation.r16-green-first-before.txt` (SHA256 183e71e0a1a8f361630825b2fc654c0102076ee4255a7f1503215b7c2d584315). Prepared source SHA256 6b524213274fd197ddc55ee6b8191ef912f114bc40dc89740afd2aacbbd95dc3; config stays 73cd980526f787f4c213d2fec3a93499eb0f4c654b9e12c701c1607bc687cf21.

The shim records each original property descriptor before defining `showModal` and `close`, sets only the native `open` attribute via its property, and restores the exact original descriptor after cleanup. An originally absent method is deleted after each case. No spy on an absent method is used.

Actual static TypeScript parser check: two test definitions and the entire describe remain byte-for-byte equal; all 21 expect expression texts remain equal; zero parse diagnostics. This is source preservation evidence, not a behavior test.

Exact diff:

```diff
--- r16-green-first-original
+++ prepared-dialog-environment
@@ -57,6 +57,8 @@
 const libraryTab = () => screen.getByRole('tab', { name: '已入库题目' });
 const importsTab = () => screen.getByRole('tab', { name: '导入批次' });
 const practice = 'practice /+?';
+let originalShowModal: PropertyDescriptor | undefined;
+let originalClose: PropertyDescriptor | undefined;
 
 function assertPushedIntent(tab: 'imports' | 'library') {
   const href = navigation.push.mock.calls.at(-1)?.[0];
@@ -68,6 +70,18 @@
 }
 
 beforeEach(() => {
+  originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'showModal');
+  originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, 'close');
+  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
+    configurable: true,
+    writable: true,
+    value: function showModal(this: HTMLDialogElement) { this.open = true; },
+  });
+  Object.defineProperty(HTMLDialogElement.prototype, 'close', {
+    configurable: true,
+    writable: true,
+    value: function close(this: HTMLDialogElement) { this.open = false; },
+  });
   navigation.push.mockReset();
   navigation.query = new URLSearchParams();
   window.history.replaceState(null, '', '/question-bank');
@@ -75,6 +89,10 @@
 afterEach(() => {
   cleanup();
   vi.restoreAllMocks();
+  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, 'showModal', originalShowModal);
+  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
+  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, 'close', originalClose);
+  else Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
   window.history.replaceState(null, '', '/question-bank');
 });
 
```

Awaiting root's new candidate freeze and single-run authorization.
