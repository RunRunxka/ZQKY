# G1-V00-FE v1 独立结果

负责人 `/root/g1_v00_fe`，2026-10-02。候选 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。**独立组件正确行为与真 API 组件业务链通过；真实浏览器待执行，不能据此将 G1 的适用浏览器门禁记为通过。** 本 Agent 未实现或修复产品，只写任务卡登记的 `v00-fe/**`。

## 冻结与范围

开工 `g1-r1` 825 项 SHA 全部一致，见 `hash-before.json`。验后 r1 825 项、r2 826 项、旧证据 629 项均零漂移，见 `hash-after.json`。r2 仅补安全 `.env.example` 的冻结覆盖，没有修改 r1 产品；原清单保留。`next-env.d.ts` 与本批原字节逐字节一致，SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。未切换分支/暂存/提交/推送/部署。

读取根/web/api AGENTS、CURRENT_STATUS、PROJECT_GUIDE、用户完整本轮授权、B3-FIX REPORT、新只读审查 REVIEW 与各范围报告、旧前端三条反例/收据/首败及富 OMML 诊断；相关 Next 仓库文档为 `node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`。检查本次相关组件、共享 hook/服务契约及真实浏览器 fixture，旧诊断不作为修复通过断言。

## 独立正确行为

| 问题 | 实际独立断言 | 状态 |
| --- | --- | --- |
| R01 | 已进入承认后编辑、确认弹窗已打开后编辑，两个确认入口失效且零 POST；保存中锁校对/确认；保存后等待新的服务端 revision/previewVersion 和新 missing 承认；未知响应即使当前映射和预览变化仍深等重放原请求 | pass，4 个组件用例 |
| R02 | F 请求在途后 G：200、409、422、网络失败都保留 G 和 dirty；显式刷新后仍保留；旧对象卸载后的 200/409/422 不覆盖新对象 H 或引入旧错误/回执；全部 StrictMode | pass，7 个组件用例 |
| R03 | 真实 Workspace 保持已挂载施测：名单新增、CSV 导入、转班均更新；合法甲的取消勾选、免考与第 3 人次不丢，转走乙撤销并有明确说明，没有切班/重开页面 | pass，1 个组件用例，另有真 HTTP 全链 |
| R08 | 三个表达式含空中项与分式全部呈现；显式 `\|`、`,`、空分隔符；默认 `\|`、单空表达式；未知元素/表达式/外来命名空间显示不支持且保留全文安全源，不插入 script | pass，8 个组件用例 |

手写断言没有调用生产守卫/解析转换作为期望 oracle。组件 fetch 替身只证明交互、请求和竞态，不冒充实际四库持久化。

额外 `real-api.test.tsx` 把真实组件业务请求逐字节转发 root 持有的 `127.0.0.1:8001`，不制造成功业务响应。jsdom FormData/File 转成实际 multipart；因 jsdom AbortSignal 与 Node Undici 不兼容，传输适配不测试物理网络取消，组件自身操作身份仍生效。隔离根和 `credentials_file=None` 由 root 的既有测试 fixture 在装配前设置。没有导入 app.main、读取正式 `.env` 或正式数据库。

真 HTTP 一次完整链验证：新增丙/CSV 导入丁/转走乙 → 已挂载施测合法草稿保留、真实名单只有甲/丙/丁 → 固定三叶卷建立实际施测 → CSV 成绩真实上传/映射 → 甲 Q1 从 2 编辑为 1，未保存零确认 → 保存且读回新预览 → 实际确认 HTTP200 已提交后故意丢响应 → 相同 submissionId/完整包重放 HTTP200 → 正式修订恰好一份，实际矩阵甲 `[100,200,500]`，合计 `800`。收据 `real-api-receipts.json`：assessment `6b855beb49c54c1daf44564939a9abf3`，import `93bdc0f7f2b544d08ef086d30d426999`，scoreRevision `bbe7c4fadbe74bbc8fce13aa3c3274e9`。

## 实跑命令与首败

各 Node 命令均 `NODE_OPTIONS=--no-experimental-webstorage`，工作目录仓库根。每轮独立保留日志/XML/命令 JSON，重复运行不相加。

```powershell
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/vitest.config.ts
node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/vitest.config.ts real-api.test.tsx --outputFile.junit=docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/real-api-third.xml
node node_modules/@playwright/test/cli.js test --config docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/playwright.config.ts --list
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/verify.py
```

| 单次运行 | 结果 | 证据 |
| --- | --- | --- |
| 组件首次 | 20 failed，exit1，1.30s；QA 在 web tsconfig 外，classic JSX 的 React 未定义，未到产品断言 | component-first.log/xml/command.json |
| 组件第二次 | 14 passed/6 failed，exit1，3.31s；空校正初始输入本来为空导致未产生 change；两个同名刷新按钮、上传按钮名为“上传名单”导致夹具定位失败 | component-second.log/xml/command.json/receipts.json |
| 组件完整最终 | **20 passed，exit0，2.35s**，1 文件 | component-third.log/xml/command.json，component-receipts.json |
| 真 API 组件首次 | 1 failed，exit1，2.46s；初始实际创建 API 成功，jsdom AbortSignal 不能交给 Undici 导致 UI 查询转发失败 | real-api-first.log/xml/command.json/receipts.json |
| 真 API 组件第二次 | 1 failed，exit1，1.99s；同步断言在 React 名单提示 effect 呈现前执行，保存旧失败；改为等待明确提示，不降低撤销/保留断言 | real-api-second.log/xml/command.json/receipts.json |
| 真 API 组件完整最终 | **1 passed，exit0，2.21s**，1 文件 | real-api-third.log/xml/command.json，real-api-receipts.json |
| 浏览器脚本收集 | exit0，1 test/1 file；只是编译/收集，未执行 browser | browser-collection.log/command.json |
| 全指纹验后 | exit0；825/826/629 零差异，next-env 原字节相同 | hash-after.json |

没有产品正确行为断言失败后擅自修产品。上述自建夹具的修正仅在登记 QA 范围，所有首败原件保留。

## 未执行与资源

真实 Playwright 浏览器 **not_run/pending**：root 启动已构建 5174 的命令被自动审批拒绝，正等待用户手动开放该窗口；本 Agent 没有重试该动作或换命令/工具绕过。脚本 `real-browser.spec.ts` 与 `playwright.config.ts` 已准备且收集通过，配置没有 webServer，下一步只使用已开放的 5174/8001。脚本设计真实名单新增/导入/转班、映射迟到真实响应、保存新分数、确认丢响应原包重放、矩阵读回，以及三视口/键盘/reduced-motion；这些均不能在未执行时声称通过。

本任务未执行全量 check/API/E2E（由 CTRL 独占）、人工像素/Word/WPS/真实模型/Qdrant/正式迁移。所有 Agent 网络业务只用 root 自有的新系统 temp 真后端；没有新增监听/启动后台进程、浏览器会话或读取用户草稿。root8001与数据根由 root 收尾；失败轮和最终轮测试数据留在该隔离根，不删除未知数据或旧六目录。

当前结果可供 CTRL 记录本范围组件与真 API 行为已验；G1 总体仍须完成真实浏览器及适用门禁，不能以本结果启动 B4。
