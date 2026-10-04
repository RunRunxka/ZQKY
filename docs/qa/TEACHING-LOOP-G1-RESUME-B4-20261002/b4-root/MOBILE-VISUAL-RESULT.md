# R12 真实手机可读性与补屏

两个单轮分别保存，未改测量脚本或4.5硬门槛。修前r11/旧r5构建 mobile-visual-first exit1/3265.256ms：灰字与蓝底对比1.013659399，元信息宽67.046875px/高90px，被挤在条目右侧。修后r13/新build ST2AWsfwxRYxFKZb_qsip mobile-visual-fixed-first exit0/2085.439ms：白字与同蓝底对比5.168555560，元信息整行310px/高18px，准备状态显示正确。

CTRL实际查看两轮各八张390×844原截图，以及第五 returned-report 的1440/1920/390三张原图。手机三种下载按钮、导出固定身份、报告事实、计分叶、原始来源与回流映射可读，无页面横向溢出；修后长身份辅助信息排列在标题下方。三视口公式、表格、图片及来源原文正常。补屏实际滚动内部主区域，补齐原fullPage截图未覆盖导出和映射的盲区，不把原盲图当全部布局证明。

两次均新隔离Edge context，只放行GET；禁止写请求0，没有提交/修改这两份本批合成数据。context/browser实际关闭，ZIP逐条CRC和内容SHA核验并关闭；每张PNG和两个完整trace原件SHA记录MOBILE-VISUAL-RESULT.json。修前失败完整保留。R11另由独立原2组件场景及第五完整118matcher真实browser验证，本手机GET补屏不单独证明queued→terminal转换。

两次runner PID3264/27260均实际exit，完整合并stdout/stderr及新OS外层根分别保留。API由CTRL持有第五11984，frontend由用户持有3820；本脚本不管服务生命周期。Word/WPS人工排版未执行，此处仅网页真实画面验收。
