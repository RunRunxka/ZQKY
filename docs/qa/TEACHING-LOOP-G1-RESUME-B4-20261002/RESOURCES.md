# 本次资源状态

用户手动5174：PID6836，完整start命令及127.0.0.1归属记录于root/frontend-listener.json。沿用BUILD_ID gIyYdxBPz-86QUIMw_JX2和8001构建代理，1979构建文件未改。CTRL从未重试被拒启动、换端口或停止用户进程；完整E2E结束时仍是同PID监听。

独立浏览器API：CTRL自己的PID19736、uvicorn teaching_loop_backend:app，完整命令/数据/监听见root/browser-api-resource.json。新系统temp `zqky-g1-resume-browser-b6354636fb974675bd048a956fb9929e`，credentials_file=None、ENV=test、教材空目录、Qdrant16333，不读取正式数据。第二轮正式结束后按PID+命令+127.0.0.1:8001重新核归属，用Windows Stop-Process结束这个准确进程；不把它记作应用优雅shutdown。外层exec session34794结束exit1是主动终止结果，API日志Tee文件保留，后续4库integrity ok/foreign_key_check0。停止前后见root/browser-api-stop-before/after.json，独立8001释放后才启动全量E2E。

完整E2E新样本：assessments由自身PID5240管理，根 `C:/Users/96022/AppData/Local/Temp/zqky-f20i-2EJViG`；question-bank-real由自身PID17440管理，根 `C:/Users/96022/AppData/Local/Temp/zqky-f10-real-xsUvsr`。两spec串行占8001，都按KEEP1在childClosed/logClosed后保留根和api.log，物理日志大小/SHA及8库只读完整性检查见root/full-e2e-retained-resources.json，实际命令另存。全量结束只有用户5174仍监听，8001无监听。

Playwright两独立轮的worker和临时Edge profile已释放；first两残缺trace及33文件保持原SHA，second两完整trace242/95条由作者与CTRL标准库再验CRC/内容SHA。全量原配置retain-on-failure保持，153全通过的本轮不额外产生失败trace。没有结束用户浏览器会话或读取真实草稿。

trace诊断只持有新OS临时样本与短时Node进程，没有业务端口。所有根按逐轮receipt保留，final resource JSON证无probe进程。既有Node24只作为runner选择，未改PATH/全局运行时/锁文件/用户Node26服务。诊断原源ZIP、Node26 partial与Node24完整ZIP均保留；原merge只移除自己新建.work.zip，原源副本保留。资源harness默认cleanup只删除四场景中属于自身、经过路径校验且已关闭的两个新测试根，不触碰其它目录。

旧六policy拒删目录未重试删除或用作本批样本。原G1/B3/审查815证据逐字节保护；本次没有Git写入、推送、分支切换或部署。B4资源在阶段开始时另登记，当前尚未开始。
