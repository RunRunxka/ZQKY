# B4-R07-REVIEW v1 · 停写后独立静态补审

结论：**PASS（仅静态补审）**。实际R07仅补合法原卷来源块/逐题关联与真实资产GET的字节/hash/MIME预检，未放宽资产授权、产品或原浏览器断言。未执行seed/browser/app.main/服务，不能将计划中的HTTP200记为已发生。

已收到CTRL明确停写与SHA放行后核查，快照 2026-10-02T13:31:55.215665+00:00。r6候选SHA fd24f5d7e7cf6088459f1a3143a38bd947bc8e93d58e63f348212b463ed6ec9e，seed SHA 4f50256da7bc41bd7c09b6be3364969eae8f7a66999fd811b19ee4509970d044，原before SHA c29c9fc2a40903a8fa43ef19dc5984263224c5363d8c83e3c98b49852ea03e29。

## 冻结身份与原断言

r5→r6 产品877零改、共享契约5零改；QA总数36，只有seed.py 1项变化，其余35项零改，无增/删。对r6的877+36+5=918条当前文件逐项SHA核查，0漂移。原before与r5登记seed逐字节同身份。real-browser.spec.ts与r5-before完全一致，SHA cb425d1ca424f4e59a10f9362eaa590b8d64172a7f52cf574a434fb2ff461dae / 29536字节。

AST多重集合核对：原115 calls全部保留；原2 assert全部保留；新137 calls/6 assert。源码diff仅新增行，没有删除原行。原emptyB4Counts五表0断言、真实T30固定三叶200/300/500（totalScoreUnits1000＝10分）、T60名单/明确补考/五人次与固定成绩预期、题库富原题均保留；浏览器未知原包、模板和全固定oracle字节不变。原首敗与模板断言未改或覆盖。

## 合法来源与资产读取规则

PaperService.get_revision_asset_content（service.py:648–682）先核原卷/修订复合归属、受管blobs键，再从本修订kind=image的paper_source_blocks取引用，未引用则404。仅item.content中的assets声明不会授权；AssetStore.read(:137–144)核真实字节SHA，HTTP papers.py:146–159返回实际bytes和魔数MIME。确认闸门service.py:2071–2143同样要求材料块id、资产id能落在本修订来源中。

新seed在confirm前，将每题固定stem/source（若存在）/共同材料/全部选项/答案/解析逐块deepcopy；block_id包含revision/item/originalBlockId，ordinal连续，kind不变，disposition=item并指向该次真实item。PaperRepository.insert_blocks_in参数/现有复合关联一致。每题source_locator记录同实际source_file的file.asset_id、stored.sha256和全部插入block ID；每块额外记录完整questionNo/section/blockIndex。来源文件仍是原真实renderer DOCX受管文件，图片仍是原真实PNG，不加入任意路径、他卷或未引用资产。

按静态rich结构预计3×9＝27块，**尚未执行，不冒称实际落库计数**。全部新增源行在原创建事务内，且在confirm封存前完成；不是去改确认后的产品或删授权检查。

## 新HTTP预检与边界

新增client.get走真实标准create_app TestClient及原papers资产端口，编码实际aid；四断言要求HTTP200、response.content等于原png()、实际内容SHA等于image.sha256、实际content-type为image/png。没有mock、route.fulfill、预造response或改HTTP200返回。新增initialAssetHTTP元数据取实际响应状态/头/字节/SHA和真实固定paper/revision，不能在运行前当作成功收据。

只写本MD/JSON。没有导入app.main、执行seed、运行测试/收集、启动/停止服务、查询端口或读写临时/正式data；产品、QA执行源、历史与旧失败原件均未改。静态补审通过后由CTRL执行新冻候选seed并保留实际首轮结果，随后独立真实browser门禁；本报告不替代这些业务验收。
