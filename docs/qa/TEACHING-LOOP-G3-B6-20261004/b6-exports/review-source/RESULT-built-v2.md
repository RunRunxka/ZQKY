# B6-R01 新构建来源独立签核 v2

更新时间：2026-10-04T14:55:37.315628+08:00。责任人 g3_v00。**稳定新build的来源八例及受影响组件门禁签收；实际UI与完整浏览器门禁待完成，本卡STOP。** 新叶补充v1，不覆盖其修前首败和旧候选结果。

构建 `LkFgY8qsEnCOUbC11Dm1T`，候选 SHA `530005e154a3620f4d0fc6a0a3ade36c35bbd2f8316a91b71e65b1e007a8deb0`。本人逐文件重算当前完整942源、33共享契约、3136冻结可执行QA、2161构建文件，全部与候选清单相同；SourcePanel `bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8`、原next-env `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。源八例 ca149188…自QA3以来字节保持，最终built原断言完整单轮再次通过。

| ROOT完整执行 | PID | 持续ms | 实际单轮 |
| --- | --- | --- | --- |
| source独立八例 | 23012 | 2078.647 | 8/8 pass |
| 原G3 V00十五例 | 3652 | 5098.214 | 15/15 pass |
| G3 boundary八例 | 23936 | 3162.138 | 8/8 pass |
| 完整check（新QA等待同步后） | 16920 | 105612.417 | 1286单测/type/lint0/build pass |

各原command/log SHA已核，三个built单轮942源before/after同时精确等于新候选，源/QA本轮零漂移、next-env原字节相同。本人只读核验，不重复执行。check绑定生成前qa3候选，build产物后另冻结built候选，身份分开记录。

既有lesson-workspace四分支用例仅增加真实可访问dialog等待，并等待原关闭断言；原点击、正文/cache/保存次数/重放body/导航等15项expect保持，未改变skip/retry/全局超时或产品。原完整check首败与诊断保持，完整成功只取新一轮。ROOT另报首次猜不存在built文件在封冻前FileNotFound、0case/无执行收据，TEMP drd_woy9保留；本人未找到对应原receipt，将其作为ROOT所报准备失败列明且不计通过。

八项来源正确行为与修前S03、事件fixture两次delta见 [v1](RESULT-v1.md)。pending报告意图、metadata独立epoch和会话/discard守卫的源码结论保持。实际新build UI五字段链仍browser-r7进行中；新build G3四视口14与原完整153尚未在本叶签收。真人/live模型、WPS排版、RAG-REL边界保持。原四公开导出和质量15技术包保留q84e实际来源，不称本轮重跑。

逐组原命令、PID/时间、SHA与完整清单复核见 [RESULT-built-v2.json](RESULT-built-v2.json)。
