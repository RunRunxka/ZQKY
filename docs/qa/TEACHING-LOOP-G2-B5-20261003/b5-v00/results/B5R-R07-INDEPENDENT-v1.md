# B5R-R07 独立归因 v1

**确认产品P2回归：正常本地稿立即导航被新LeaveProtection人工弹窗拦住。** 原153完整151pass/2fail，PID14660 exit1/391550.724ms，原2spec/body/assert/10s预算不改，不拼绿。

两fill后的导航click均真实结束无错误。等待10s后URL仍/lesson-plans，末error-context与原trace show已保存到本机同时离开当前教案dialog仍开；两末JPEG已实际view。不是按钮未点击或Next单纯未commit。

LeaveProtection.ask把localPending直接纳入手动询问并创建未决promise；LessonWorkspace有公共provider时beforeNavigate为空，正常本地旧flush路径不再走。600ms writer自行保存后不触发finish(true)，所以已经保存仍等待二次人工选择。DocumentGateway加载不是此两根因；shared导航注册/epoch检查应保留。

用户原要求52/184及冻结契约80要求保留本地600ms串行写和快速导航完整回归；原lesson-plan:33与navigation:54要求立即保存后跳页、返回恢复。正确修复需要本地正常flush成功后继续原导航，失败保持内容，后台dirty/unknown策略不弱化。

localStorage最后实际字节在原trace没有显式post-edit读取：保存状态是真观察，writer/repository写路径属于源码推断，不能冒称全11 cache深等已执行。无新HTTP/browser/service/agent/Git、无产品/QA改动；原JSON/XML/log/2trace保持，原201及candidate938/2419/33/build2004独立hash0。新correct-behavior QA待ROOT窄卡授权，stream14由ROOT暂停。STOP。
