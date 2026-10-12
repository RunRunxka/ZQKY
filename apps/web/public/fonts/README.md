# 教案工作台字体资源（apps/web/public/fonts/）

更新：2026-10-12（R7-FE）。本目录只放**教案工作台**用到的字体文件；界面字体（Chat Geist /
Chat Lora）在 `fonts/chat/`，不在此处。

## 已随仓库提供（必需，自托管）

| 文件 | 字体族 | 字重 | 来源 | 许可 |
| --- | --- | --- | --- | --- |
| `lesson/AlibabaPuHuiTi-3-55-Regular.ttf` | Alibaba PuHuiTi（阿里巴巴普惠体） | 55 Regular | 阿里巴巴普惠体官方免费发布（3.0 版本，官方免费商用发布页下载） | 阿里巴巴普惠体许可：免费商用，不得单独售卖字体文件、不得改名字体后二次发布（随产品嵌入使用允许） |
| `lesson/AlibabaPuHuiTi-3-85-Bold.ttf` | Alibaba PuHuiTi | 85 Bold | 同上 | 同上 |

- 引入方式：`apps/web/src/features/lesson-plan/styles/lesson-fonts.css` 的 `@font-face`，
  `font-display: swap`；工作台默认字体即普惠体。
- 文件在归档提交 `archive-full-v1-20261011` 中已随仓库保存（同 SHA），本卡只做登记与
  `@font-face` 声明，不重打包、不改字形。

## 未随仓库提供（可选族，本机 `local()` 回退）

| 字体族 | 状态 | 许可与来源 | 回退 |
| --- | --- | --- | --- |
| MiSans（小米兰亭 Pro 后继） | 未下载文件（官方发布为整包，单字重 >10MB） | 小米 MiSans 官方发布页；**许可要求保留其许可说明**（允许免费商用，不得单独售卖/改名再发布），若后续入库需按官方文档在 `public/fonts/lesson/` 附 `MiSans-License` 原文 | `local('MiSans')` → PingFang SC → Microsoft YaHei → Noto Sans SC |
| 思源黑体（Noto Sans SC / Source Han Sans SC） | 未下载文件（完整 CJK 字重 >10MB/个） | SIL Open Font License 1.1（Google Noto / Adobe Source Han） | `local('Noto Sans SC')` → PingFang SC → Microsoft YaHei |
| 思源宋体（Source Han Serif SC / Noto Serif SC） | 未下载文件（完整 CJK 字重 >10MB/个） | SIL Open Font License 1.1 | `local('Source Han Serif SC')` → Songti SC → STSong → SimSun |

**降级约定（不允许假字体）**：字体选择器里的四个族都真实对应到上面的字体族或系统回退链；
未安装且未自托管时由 `font-family` 回退链给出系统字体，运行时不伪造字形、不静默换成其它
自托管字体。若后续要求把 MiSans / 思源黑体 / 思源宋体也自托管，按上表来源下载后放入
`lesson/` 目录，并在 `lesson-fonts.css` 增加对应 `@font-face`（`src: url(...)` 优先于 `local()`）。

## 再生成/校验

- 校验文件未被截断：`node -e "const fs=require('fs');for(const f of ['AlibabaPuHuiTi-3-55-Regular.ttf','AlibabaPuHuiTi-3-85-Bold.ttf'])console.log(f,fs.statSync('apps/web/public/fonts/lesson/'+f).size)"`
  （55 Regular ≈ 8.5MB，85 Bold ≈ 8.4MB）。
- 预览里切换字体后可用 `getComputedStyle(paper).fontFamily` 断言实际生效的字体族。
