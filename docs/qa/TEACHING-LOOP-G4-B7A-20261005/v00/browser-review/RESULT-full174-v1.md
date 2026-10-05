# G4 适用完整174门禁独立数据审查

2026-10-05，g4_v00_product。**本次完整单轮174/174实际通过的资料已独立核查，适用E2E门禁通过。** 新11和旧14仍各自按先前独立卡签收，本卡追加关闭其“174待验”状态，旧卡原件不追改、不合并各轮计数。G4技术总控关闭由ROOT汇总确认；本Agent不代签真人、真实模型、原生Word/WPS或原B6/B7整体。

候选 `CANDIDATE-G4-fix-built-r2.json` SHA `f81a0684abdf734b067a731c089f798a3aabfe66a1f5d336ea1bd1506db34d6e`，构建 `VeOLFBYrp-8v24Yjm-HFi`。命令PID11344、493859.033ms、exit0、child/log均closed。报告stats开始 `2026-10-05T05:25:59.372Z`、duration493133.746ms；命令时长与Playwright测试时长分别保留，不混用。

独立枚举原报告：174个唯一spec ID，29个文件，每case一个expectedStatus=passed测试且唯一结果passed/retry0；skip/flaky/unexpected/global/report errors均0。逐一绑定174个原trace，ZIP CRC全部通过。source956、QA3493、build970 Before/After映射与冻结候选相同、next-env原SHA前后一致。所有29个现行测试原文件SHA同时等于OPENING和候选的sourceFiles，未改测试/断言或重跑。完整case列表、文件计数、trace SHA及实际附件索引见 [full174-inspection.json](full174-inspection.json)。

原UI新增21项完整保留并实际通过：ui-motion3、resource4、textbook4、unification6、workflow4，五文件SHA从OPENING至本次不变。原断言保持DOM/字体/布局对齐、overflow、700px触控高度、GSAP真实活动及reduced-motion/焦点/清理等正确行为；实际layout-measurements四份各17路由和触控/动效原JSON已额外独立核。原文件没有toHaveScreenshot/toMatchSnapshot黄金图片比对，截图是实际采集材料，不虚称像素快照差分通过；截图调用/原PNG SHA保留索引，未逐张重复目检所有同源UI图片。新故障四视口八张焦点恢复图已独立实际查看，真实业务完整正文另见新11材料。

R-14“双标签页并发写不同书”实际passed、唯一attempt、未略过：两本不同bookId的ready结果，各continueAttempts/continueClicks均0；primaryFailure/closeFailure为null，两份cleanup都fulfilled且observer/timer/listeners释放、resourcesReleased=true。原恢复收据逐字节留 [full174-r14-original-recovery.json](full174-r14-original-recovery.json)。本次正常单轮通过不能证明跨批间歇根因或恒绿，R-14原台账保持，不予豁免。

ROOT自有资源与保全后验收据只读核对：`INTEGRITY-G4-gates-v1.json` SHA `31e0f9f6d8e3fa025dfa0112d22c04b3e1e2053e6b25f66486221bc8c08fe358`，source956/QA3493/contracts33/build970/historicalQa19169 changed均空；原五文档剥离新增状态后字节相同、Guide/API/ROUTES/next-env/HEAD不变。首/二API与首/二前端四自有实例closed、Transport恢复、TEMP保留；fullTestDescendants原同实例alive0。`G4-PORTS-CLOSED-v1.json` SHA `1d8b2fb91ca877f4427b1bfc213e60eda9c52fa295d999368d81546aff792fd5` 记录listenerCount0、未知用户进程未触碰、被拒额外HTTP身份probe未重试。取证/关闭服务的所有权属于ROOT，本Agent核收据，没有开停进程或网络探测。

结构化结果见 [RESULT-full174-v1.json](RESULT-full174-v1.json)。完整11/14/174必要浏览器资料和新38组件独立签收均已提供ROOT；live0、teacher_review_pending、Word/WPS not_run、RAG-REL及既有观察保留。STOP，无产品/原QA/原证据/Git修改。
