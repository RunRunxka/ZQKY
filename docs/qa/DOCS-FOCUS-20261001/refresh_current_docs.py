"""One-time documentation refresh; original bytes live in the archive manifest."""
from __future__ import annotations
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SNAP = ROOT / "docs/archive/snapshots/20261001-docs-focus"
MP = ROOT / "docs/archive/pre-20260929/MANIFEST.json"
manifest = json.loads(MP.read_text(encoding="utf-8-sig"))


def preserve(name):
    if any(e["source"] == name and e["operation"].startswith("snapshot") for e in manifest["files"]):
        return
    source, target = ROOT / name, SNAP / name
    assert source.resolve().is_relative_to(ROOT) and target.resolve().is_relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest["files"].append({"source": name, "destination": target.relative_to(ROOT).as_posix(),
        "operation": "snapshot_before_current_document_update", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "bytes": source.stat().st_size})


def write(name, text):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


write("docs/CURRENT_STATUS.md", r'''
# 当前状态与实施主线

更新：2026-10-01。当前建设主线以 **2026-09-29（含）之后**的教材 RAG 与教学闭环任务为准。本文件是唯一进度、问题台账和下一动作入口；稳定规则见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，阅读顺序见 [文档索引](README.md)。旧正文已逐字节保存为 [整理前状态快照](archive/snapshots/20261001-docs-focus/docs/CURRENT_STATUS.md)。

<a id="current-task"></a>
## 1. 当前任务与下一动作

**B0–B3 已交付；B3 独立代码审查发现 2 项 P1、8 项 P2，修复尚未执行。** 本次用户授权的是文档归档与过期说明修正，不包括产品修复、B4 实施或 Git 提交/推送。

- 现场代码提交：`main@d70f812777539374743e2ac0becad828fa167552`，用户已提交 B2/B3 实现。旧报告中的 `0f4b8cb` 是交付当时起点，不是今天的 HEAD。本次对照 B3 冻结清单，产品文件（不含 AGENTS 文档）无散列变化，不能把提交动作视为审查问题已修复。
- 当前优先项：按下表处理 B3-R01–R10，形成新修复候选并独立复验。任务来源是 [B3 代码审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md)。
- 后续依赖：B4 的学情事实与报告（T70/T80 等）以可靠的固定原卷、参测快照、成绩修订为前提。B4 尚未启动，范围按用户后续请求确定；原计划中的 B0 默认启动和旧 H1–H6 路线不再作为下一动作。

## 2. B3 审查待修台账

以下各项均有隔离复现，状态统一为 **待修复、未复验**；详细定位、输入和验收条件见审查报告，不用既有测试通过替代反例复验。

| 编号 | 优先级 | 已确认问题 |
| --- | --- | --- |
| B3-R01 | P1 | 新建补题 queued@0→attempt 1 被前端误判接管，停止观察，候选入口不出现 |
| B3-R02 | P1 | 文件缺考标记加剩余空白被前端算成伪 missing，合法成绩无法确认 |
| B3-R03 | P2 | C/c 绕过物理列唯一校验，正式成绩可被封存为错误分数 |
| B3-R04 | P2 | 同表修正 headerRow 不重建行集合，真实表头仍被当成学生行 |
| B3-R05 | P2 | 身份表头未识别但计分列可识别时上传 500，无法进入人工映射 |
| B3-R06 | P2 | GB18030 成绩 CSV 使用替换解码，中文身份与状态证据乱码 |
| B3-R07 | P2 | recorded 修正携带空白/缺考/免考文本时返回纯文本 500 |
| B3-R08 | P2 | 旧施测创建响应在面板卸载后仍更新父级选择，覆盖新上下文 |
| B3-R09 | P2 | 失权整理轮的失败 checkpoint 写入无原租约 CAS，可覆盖新轮进度 |
| B3-R10 | P2 | 模型名额等待时取消，取得名额后仍发起模型调用 |

这 10 项是当前实现偏差，不改写 B3 原验收报告的历史结论。当前产品状态应同时读取交付证据与后续审查；“冻结清单自洽”不表示上述行为已正确。

## 3. 当前能力与建设边界

| 模块 | 已有实现 | 当前边界 |
| --- | --- | --- |
| 学习问答与模型管理 | 真实三协议 SSE、模型连接/目录/发现、凭证后端管理 | 真实供应商证据按具体模型与场景判断，不能以注册数量当通过数量 |
| 教材资料库与 RAG | 真实上传/解析/目录/修订/索引；混合检索、证据验证、可恢复轮次；生产走 RagV2Service | 相关性拒答闸门仍待完善；人工教学质量未验；历史本地登记只读 |
| 独立知识点库 | 身份/不可变修订/父树/别名/教材依据、表格导入和候选确认、真实页面 | AI 候选不自动发布，教材依据不可用不能当作没有依据 |
| 题库 | 独立库、导入与校对、知识点关联、AI 整理/补题候选、六态任务 | B3-R01/R03/R09/R10 等待修；真实 AI 教学质量未验 |
| 名单、原卷、施测 | 班级/学生/归属历史；DOCX 富解析/人工确认；固定原卷与参测快照 | 不自动评分、不识别评分点；修改已确认卷建立新修订 |
| 成绩工作区 | XLSX/CSV 小题得分导入、校对/承认/确认、修正新版本、历史矩阵分页 | B3-R02–R08 相关偏差待修；无独立出勤校正端点 |
| 教案工作台 | 本地规则填充、编辑/草稿恢复、Word 与打印/PDF 导出 | 已有实现须保留；学情驱动 AI 教案调整尚未实现 |
| 学情报告与练习回流 | 有设计和后续任务规格 | T70/T80、练习批次及转换外键尚未实现；不得标成可用 |
| 书籍、课程 | 保留本地内容/进度和课程会话联动 | 书籍生成仍是显式本地模拟，不作为本轮实施核心 |
| 写作、阅读、学习空间、智能组卷、模板中心 | 规划根页 | 旧已移除子路由不恢复；规划页不返回假成功 |

## 4. 9 月 29 日起的批次索引

| 批次 | 交付与后续状态 | 证据入口 |
| --- | --- | --- |
| RAG-QUALITY v1.1，09-29 | 图片文本投影、首答预算、证据窗口、模型选择、可验证备份恢复；独立复验附条件通过 | [批次报告](qa/RAG-QUALITY-v1/README.md)、[原批规格](archive/snapshots/20261001-docs-focus/docs/PLAN.md) |
| B0，09-30 | 四库、迁移、受管资产、任务协议、提交幂等与公共客户端 | [B0](qa/TEACHING-LOOP-B0/README.md) |
| B1，09-30 | 富内容、知识点后端、名单后端 | [B1](qa/TEACHING-LOOP-B1/README.md) |
| B2，10-01 | 原卷、题库增量、施测、知识点前端；原审查 RV01–RV11 由 B3 G0 修复 | [B2](qa/TEACHING-LOOP-B2/README.md)、[B2 审查](qa/TEACHING-LOOP-B2-REVIEW-20261001/REVIEW.md) |
| B3，10-01 | G0、成绩后端、五步工作区、题库前端；后续审查 10 项未修 | [原交付](qa/TEACHING-LOOP-B3/REPORT.md)、[后续审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md) |
| 文档整理，10-01 | 旧文档归档、现行说明修正，未改产品 | [本次记录](qa/DOCS-FOCUS-20261001/README.md) |

## 5. 验证记录与如实边界

- B3 原交付：后端 1405 例收集，一轮全绿，其余遇 R-19；check 97 文件/927 单测及 build 通过；全量 E2E 149 过/1 败为 R-14，隔离 3/3。以上是原交付的历史运行，不是本次文档整理重跑。
- 后续只读审查：既有窄回归 89 passed、1 skipped；独立成绩/任务反例和实际组件诊断复现 10 项问题。诊断测试通过表示复现成功，不是产品修复通过。
- 成绩确认和修正的真实浏览器故障注入、真实模型/Word/WPS/Qdrant、人为教学质量未完成；F10-QB 原交付测试主要用替身，后续审查补了真实任务协议响应验证并发现 R01。
- 正式数据根的迁移/业务状态不从旧报告推断。本次没有启动正式应用、检查或迁移正式库；需要时按当前授权和隔离要求核对。
- 本次文档整理仅验证文件保全、当前引用和说明一致性，不重跑业务全量检查。冻结件保持历史原文；现行文档的后续变更单独登记，不重算旧候选清单来隐藏差异。

## 6. 仍需保留的跨批问题

| 编号 | 状态 | 边界与依据 |
| --- | --- | --- |
| RAG-REL | 未关闭 | 09-29 质量集的 10 个边界问题仍返回 ok，缺相关性拒答闸门；[RAG 质量报告](qa/RAG-QUALITY-v1/README.md) |
| R-13 | 未关闭 | 特定真实模型推理预算样本出现零正文或 length 截断，不擅自关推理或无界加预算；完整旧台账在状态快照 |
| R-14 | 未关闭、跨批间歇 | 书籍双标签集合写锁竞争可进入明确 interrupted，测试期待与既有恢复行为需稳定化；[旧证据](archive/pre-20260929/qa/UX-PERF-CLOSEOUT-20260923/r14/REPRO-EVIDENCE.md) |
| R-15 | 09-29 已关闭 | 旧 settings selector 按 contract-v1 修正，test:chat 14/14；不能继续沿用旧表中的未关闭状态 |
| R-18 | 未关闭、跨批间歇 | EmbeddingPanel 单测对并行加载时序敏感，不能靠重试或放宽断言宣布修复 |
| R-19 | 未关闭、跨批间歇 | jieba 冷启动约 350ms 超过测试 TTL 50ms；基线同样存在，留测试稳定化任务 |

旧缺陷、已移除模块和历史首败的完整原文见 [归档索引](archive/README.md)，不在此继续铺开旧 H1–H6 路线。
''')

guide_source = (SNAP / "docs/PROJECT_GUIDE.md").read_text(encoding="utf-8-sig")
rag_stable = guide_source.split("### 9.1 存储与唯一权威", 1)[1].split("### 9.5 独立题库", 1)[0]
recent_stable = "## 10. " + guide_source.split("## 10. ", 1)[1]
recent_stable = recent_stable.replace(
    "实施 B0；\n业务模块（知识点、名单、原卷、成绩、学情、练习、教案）属 B1—B7，**尚未实现**。",
    "形成公共基础契约。这里保存稳定约束；各业务模块实施状态以 CURRENT_STATUS 为准，不将 B0 时点的未实现状态沿用到今天。")
recent_stable = recent_stable.replace(
    "**B0 的启动收敛范围只含知识点库与教学库**（`app/main.py` 的 `RECONCILE_DOMAINS`）：题库组织任务仍是\n  既有五态与旧界面视图，提前写入 `interrupted` 会让旧界面出现未知状态；题库任务在 B2 迁移到统一任务协议时一并纳入。",
    "**当前启动收敛覆盖 knowledge、teaching、question 三域**；题库在 B2 已接入六态共享协议，不再使用旧五态范围作为当前限制。")
recent_stable = recent_stable.replace(
    "**分期 DDL（B2 不得越界）**：`paper_revisions.source_practice_revision_id` 与\n  `assessments.active_score_revision_id` 本批**只允许为空**（无外键、CHECK 拒绝非空），\n  由 B3/练习批次通过新迁移补齐外键与写入能力；",
    "**当前分期 DDL**：`paper_revisions.source_practice_revision_id` 仍只能为空，练习批次另补外键；\n  `assessments.active_score_revision_id` 已由 B3 0007 恢复同施测复合外键，允许引用已确认成绩修订。")
write("docs/PROJECT_GUIDE.md", r'''
# 项目目标与稳定决定

更新：2026-10-01。当前实施核心从 **2026-09-29（含）起**收敛到教材 RAG 和教师教学闭环。本文保存目标与稳定契约，实施状态及偏差只看 [CURRENT_STATUS](CURRENT_STATUS.md)；原全文保存在 [整理前快照](archive/snapshots/20261001-docs-focus/docs/PROJECT_GUIDE.md)。

## 1. 产品目标与用户已确定的业务规则

智启课源是面向教师的 AI 教学工作台。教学主线为：**独立知识点库 → 原卷题目与知识点确认 → 名单及施测快照 → 教师小题得分 → 本次需巩固知识点 → 教案调整建议 → 针对练习 → 新成绩回流**。教材 RAG 提供可核验的教材依据，题库通过知识点关联提供练习材料。

- 学情证据只来自教师提供的原卷、已确认小题知识点和教师给出的得分；不改卷、不识别评分点、不调用 AI 给学生答案评分。
- 采用 `any_loss_v1`：任一关联小题有效得分低于满分，相关知识点列为本次需巩固。它不是长期掌握概率，不使用知识追踪、加权掌握度或多知识点分值分摊。
- 知识点独立管理、物理独立 SQLite；教材是可选依据，不是题目入库的必经父级。题目与知识点为关联关系。
- `recorded(0)` 是有效得分；missing、absent、exempt 不能当 0。综合小题失分关联多个知识点时展示关联和教师复核提示，不凭分数确定具体错因。
- 教案已有规则填充、编辑、草稿和 Word/PDF 导出；后续是在现有工作台增量加入学情依据与 AI 建议，不重新搭一套教案系统。
- AI 的题目、知识点、教案及练习输出只进候选，经教师审核后发布。学生姓名、学号和人员 ID 不发送给模型。

## 2. 工程与界面约束

正式前端为 `apps/web` 的 Next.js App Router，唯一业务后端为 `apps/api` 的 FastAPI。页面薄、业务厚；跨模块类型进 contracts、API 调用进 services、能力显式注入。不能用 Next Route Handlers 再建一套业务后端。依赖沿用根 npm workspace 与 uv 锁文件，不随文档整理升级框架。

`F:\DeepTutor` 固定 v1.6.5 / `42fab3cf429a1fbf36b257ab8d116a3814964202` 仅作为既有界面/交互的只读历史参考。全页面复刻、旧 H1–H6 阶段及已移除模块不再是当前执行核心；仍保留已经形成的兼容、视觉和数据保护约束。

- `/chat` 是默认主页及既有视觉基准，保留智启课源品牌与蓝色主题。公共侧栏沿用 220/56px、学习记录位于侧栏；手机抽屉保留遮罩、焦点圈定和焦点返回。
- 共用 `globals.css` 的字体/颜色 token：ui、display、ui-serif、document、mono；不要在页面散写字体名或污染共享 space 样式。聊天 912px 宽度不硬套到成绩矩阵或文档编辑器。
- 减少动画设置、参考已有反馈和中断行为保留；不为文档或当前教学模块任意增删旧动画。
- 主聊天仅真实服务；书籍等保留的本地模拟明确标识。真实错误不回退成模拟成功、空数据或假导出。
- 真实流式 SSE 的文本与推理顺序不改；课程上下文/历史/当前问题走唯一预算构建器，当前问题不静默裁剪。活跃推理沿用轻量呈现、前缘立即/尾部合并及 80ms 更新上限，终态再完整渲染；终态/停止/切换前提交缓冲。

## 3. 数据、凭证与运行保护

四库分别为 `textbooks/catalog.sqlite3`、`question-bank/question-bank.sqlite3`、`knowledge/knowledge.sqlite3`、`teaching/teaching.sqlite3`。Qdrant 只负责教材向量；原件走内容寻址受管 assets。数据库连接统一经 `app/core/sqlite.py`，先 busy_timeout、再 WAL、开启外键。已登记迁移只能追加，不能改散列；损坏库不能重建成空库。

跨库发布/归档统一使用 PublicationCoordinator 的进程内锁，锁内仅数据库读取与短事务；不宣称它提供多进程锁或跨库原子事务。模型、解析、网络和资产写入在 SQL 写事务外。教材原文及正式业务修订不可变，变更建立新修订。

Key 只存后端 `apps/api/.env`，不进前端、源码、日志、截图或测试样本。服务仅监听回环，Origin 受控；公网 Base URL 必须 HTTPS、HTTP 仅回环。供应商身份/认证/API 格式/参数分层，不按模型名猜连接；目录注册不代表真实调用验收通过。

原始教案 Word、`F:\DeepTutor` 与 `F:\人教版教材\markdown` 只读。读取失败不冒充空库，写入失败保留编辑，不覆盖正式浏览器草稿或用户未提交修改。

## 4. 执行、验证与 Git

开工读取现场 HEAD/分支/工作区和对应模块 AGENTS；历史基线、旧授权或归档提示词不授权新任务。当前请求范围内持续完成，不把文档中的整条路线自动变成实施范围。同文件同一时段唯一写入者；总控独占公共契约、迁移、权威文档、锁文件与最终 Git。

后端探针在任何 `app.main` 导入前设置临时 ZQKY_DATA_DIR，隔离正式库；浏览器测试用隔离上下文与 5174，测试 API 用 8001，Qdrant 测试实例 16333。不得连正式 6333 跑测试。Node 26 单测需 `NODE_OPTIONS=--no-experimental-webstorage`。

产品变更按根 AGENTS 执行适用 check/test:api；页面/保存/导出改动先 build 再 E2E。未执行写 not_run 和原因；构建成功不等于业务、视觉、真实模型或教学质量通过。纯文档整理验证归档散列、引用与一致性，不冒称重跑业务测试。

不自动切换共享分支、不批量暂存、不清理未知数据、不改全局 Git 身份；提交、推送与部署按本次明确授权。历史用户曾授权某批本地提交不延续为本次自动提交授权。

## 5. 文档权威与历史读取

当前任务读 [CURRENT_STATUS](CURRENT_STATUS.md)，目标/规则读本文件，契约读 [API](API.md)、页面索引读 [ROUTES](ROUTES.md)，详细教学设计读 [设计目录](design/teaching-loop-v1/README.md) 和 [v2.0 实施计划](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)。

9 月 29 日前 QA、旧复刻矩阵、旧原始规划在 [归档索引](archive/README.md)。仍适用的规则按本文件和 AGENTS 保留，不能因日期旧就废除数据保护、许可或现有教案能力。冻结报告保存当时事实和原路径，归档映射见 MANIFEST；不追改旧验收结论，不改旧冻结清单掩盖后续文档差异。

## 6. 教材解析、索引与定位的保留契约

以下延续已有 RAG v2 的解析/索引/定位约束；模型选择、首答预算和备份以之后的 9 月 29 日及 B0 决定覆盖旧策略。具体实现偏差和质量限制在 CURRENT_STATUS 登记。

### 6.1 存储与唯一权威
''' + rag_stable + "\n" + recent_stable)

agents = (SNAP / "AGENTS.md").read_text(encoding="utf-8-sig")
start, rest = agents.split("## 1. 项目概述", 1)
_, tail = rest.split("## 2. 技术栈", 1)
overview = '''## 1. 项目概述

智启课源是面向教师的 AI 教学工作台。**2026-09-29 起的任务核心是教材 RAG 与教学闭环**：独立知识点库、原卷/名单/施测/成绩、知识点题库，后续学情分析、教案调整和练习回流。Next.js 是正式前端，FastAPI 是唯一业务后端。

- **真实业务**：学习问答、模型连接、教材资料库/RAG、知识点、题库、名单、原卷、施测及成绩；已有实现偏差和验收边界只看 CURRENT_STATUS，不能将模块存在等同于全部可用。
- **已有本地能力**：教案规则填充、编辑、草稿恢复和 Word/PDF 导出；书籍生成仍是明确标识的本地模拟。
- **后续设计**：学情报告、学情驱动 AI 教案调整、针对练习与回流闭环；不得提前宣称实现。
- **规划根页**：协同写作、沉浸阅读、学习空间、智能组卷、模板中心。题库不再属于规划页。
- **历史参考**：DeepTutor v1.6.5 固定提交 `42fab3cf…` 只读。保留当前 /chat 视觉基准、品牌和蓝色，不把旧全页面复刻路线或已移除模块当作当前任务。

'''
agents = start + overview + "## 2. 技术栈" + tail
agents = agents.replace("含 rag_engine 固定快照", "含生产 rag_v2 与保留的历史 rag_engine")
agents = agents.replace("chat / lesson-plan / knowledge / books / courses / model-settings / settings", "chat / lesson-plan / textbook / knowledge-points / question-bank / assessments / books / courses / model-settings / settings")
agents = agents.replace("HTTP 路由（chat / rag / model_* / capabilities / health）", "HTTP 路由（chat / rag / textbook_* / knowledge / roster / papers / assessments / scores / question_bank 等）")
agents = agents.replace("页面 / AI 交互 / 动画三矩阵", "历史复刻矩阵与接手兼容入口")
agents = agents.replace("当前分支 `main`（个人分支）；默认集成分支为 `feat/glass-theme`。", "开工读取现场分支/HEAD，不自动切换共享分支；历史 `feat/glass-theme` 不作为当前默认集成目标。")
agents = agents.replace("全部历史归档（只读，非当前指令）", "旧合并历史（只读，非当前指令）；新增归档见 docs/archive/README.md")
agents = agents.replace("| [docs/replica/](docs/replica/) | 页面 / AI 交互 / 动画三矩阵 |", "| [docs/replica/](docs/replica/README.md) | 历史复刻矩阵兼容入口，不维护当前教学闭环进度 |")
agents = agents.replace("## 11. 模块级 AGENTS.md", "| [docs/README.md](docs/README.md) | 当前阅读索引：9 月 29 日起设计、实施、审查与归档 |\n| [docs/design/teaching-loop-v1/](docs/design/teaching-loop-v1/README.md) | 教学闭环设计与 v2.0 详细实施规格 |\n\n## 11. 模块级 AGENTS.md")
write("AGENTS.md", agents)

write("README.md", r'''
# 智启课源（ZQKY）

面向教师的 AI 教学工作台，采用 **Next.js + FastAPI**。2026-09-29 起的建设核心是教材 RAG、独立知识点库、原卷与小题得分对齐、题库，以及后续学情分析、教案调整和练习回流。当前任务与实现偏差只看 [CURRENT_STATUS](docs/CURRENT_STATUS.md)，稳定规则见 [PROJECT_GUIDE](docs/PROJECT_GUIDE.md)。

## 功能入口

| 入口 | 能力与边界 |
| --- | --- |
| `/chat` | 真实多模型 SSE 与教材 RAG；默认主页与既有视觉基准 |
| `/knowledge-bases` | 真实教材上传/解析/目录/修订/索引；历史本地登记只读 |
| `/knowledge-points` | 独立知识点管理、别名、教材依据、导入校对和候选确认 |
| `/question-bank` | 独立题库、导入校对、知识点关联与 AI 补题候选；当前审查偏差看状态台账 |
| `/assessments` | 名单→原卷→施测→成绩→历史五步工作区；当前审查偏差看状态台账 |
| `/lesson-plans` | 已有本地规则填充、编辑/草稿恢复、Word 与打印/PDF 导出；学情驱动 AI 调整属后续建设 |
| `/books`、`/courses` | 保留既有内容和课程会话能力；书籍生成仍为显式本地模拟 |
| `/settings` | 模型与连接、Embedding/任教范围、外观及扩展管理 |

学情报告、针对练习与成绩回流闭环尚未实现。写作、阅读、学习空间、智能组卷、模板中心保留规划根页，完整运行时路径见 [ROUTES](docs/ROUTES.md)。

## 本地运行

Node.js 26（当前验证环境）、Python ≥3.12、uv。根 npm workspace 和 `apps/api/uv.lock` 是依赖依据。

```powershell
Set-Location 'H:\备份xuexi\智启课源'
npm.cmd ci
npm.cmd run setup:api
npm.cmd run dev:api     # 127.0.0.1:8000；另一个终端启动前端
npm.cmd run dev         # 127.0.0.1:5173
```

已有依赖时不需要重复安装。聊天和教学业务需要后端；API Key 在设置中配置，仅由后端存于 `apps/api/.env`。浏览器数据按来源/端口隔离，不用开发或测试来源覆盖用户正式草稿。

## 教材 RAG 与存储

生产 `/api/v1/rag/*` 使用 **RagV2Service**，按教师确认的任教范围和教材目录的当前索引代进行检索；不再把旧四科固定快照、6,745 块或旧 `models.yaml` 当作当前运行条件。

先启动本机 Ollama、Qdrant 和 FastAPI，在设置完成 Embedding 配置与任教范围，在教材资料库导入或重建索引，再在学习问答使用 RAG。首答提供紧凑知识点及可核验教材证据；详解冻结并使用当前选择的聊天模型，可为本地或云端。依赖未就绪时如实报错，不降级为云端检索或假成功。

业务采用四个独立 SQLite：教材、题库、知识点、教学业务；Qdrant 仅存教材向量；原件保存在内容寻址的受管 assets。索引代、原文修订与正式成绩版本有各自唯一权威，不混用 ID 和编辑 revision。数据目录不入 Git，备份/恢复与迁移按 [API](docs/API.md)、[稳定决定](docs/PROJECT_GUIDE.md) 和对应脚本执行。

教材 RAG 的可运行性、检索证据和人工教学质量分别验收，不能以构建或自动化通过宣布教学质量已通过。

## 常用检查

```powershell
$env:NODE_OPTIONS='--no-experimental-webstorage'
npm.cmd run check       # typecheck + lint + unit + build
npm.cmd run test:api
npm.cmd run test:e2e    # 先 build；隔离 5174，跑上一次构建
npm.cmd run test:chat
npm.cmd run template:verify
```

自动化使用临时后端数据根、隔离浏览器与测试服务，不读写正式凭证/草稿/6333 向量库。未执行的检查注明原因；文档整理不冒称执行业务回归。

## 文档

- [当前文档索引](docs/README.md)：阅读顺序与 9 月 29 日起主线。
- [当前状态与问题](docs/CURRENT_STATUS.md)：唯一下一动作和台账。
- [教学闭环设计](docs/design/teaching-loop-v1/README.md)、[详细实施计划](docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)：实体/ER/模块/关系表/伪代码与验收规格。
- [当前接手入口](docs/NEXT_SESSION_START.md)、[AGENTS](AGENTS.md)：执行范围、规范与数据保护。
- [API](docs/API.md)、[ROUTES](docs/ROUTES.md)：现行契约和运行时页面索引。
- [历史归档](docs/archive/README.md)：旧任务/复刻矩阵/原始规划/完整状态快照与散列映射。
- [第三方许可](docs/licenses/deeptutor-chat/README.md)：保留并继续适用。

DeepTutor 固定提交仅为历史界面参考，保留智启课源品牌、蓝色主题和已有兼容约束；不再以旧全页面复刻路线组织当前任务。
''')

write("docs/PLAN.md", '''
# 当前实施计划入口

更新：2026-10-01。当前任务核心为 2026-09-29 起的教材 RAG 和教学闭环。此页提供计划索引，不重复维护进度和缺陷。

1. 实际当前任务与下一动作：[CURRENT_STATUS](CURRENT_STATUS.md)。
2. 教学闭环详细规格、任务依赖、伪代码和验收标准：[多 Agent 实施计划 v2.0](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)。其中能力表是 09-30 原始基线；今天是否实现只看状态与源码。
3. 当前前置问题：[B3 独立代码审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md)，修复未执行。B4 尚未启动。
4. 09-29 已交付 RAG-QUALITY 批次的原整改规格：[原 PLAN 全文快照](archive/snapshots/20261001-docs-focus/docs/PLAN.md)，仅作该批历史规格；原文 needs_revision 不代表重新下发整改。
5. 通用角色与任务卡：[协作模板](MULTI_AGENT_COLLABORATION_PROPOSAL.md)；接手顺序：[NEXT_SESSION_START](NEXT_SESSION_START.md)。

计划内容不自动授权执行。旧 B0 首次启动例、已完成 B1/B2/B3 提示词和 H1–H6 路线不能当当前默认任务；按本次用户请求确定范围，不重复已交付批次。
''')

write("docs/README.md", '''
# 当前文档索引

更新：2026-10-01。当前建设以 **2026-09-29（含）之后**的教材 RAG 与教学闭环为主。日期用于区分任务历史，仍有效的工程约束、许可和既有能力继续保留。

| 阅读顺序 | 文档 | 权威职责 |
| --- | --- | --- |
| 1 | [根 AGENTS](../AGENTS.md) 与模块 AGENTS | 工程规范、数据保护、协作边界 |
| 2 | [CURRENT_STATUS](CURRENT_STATUS.md) | 唯一当前任务、问题和下一动作；B3 审查问题未修 |
| 3 | [PROJECT_GUIDE](PROJECT_GUIDE.md) | 产品目标与稳定契约，不保存执行进度 |
| 4 | [教学闭环设计](design/teaching-loop-v1/README.md) | 架构、实体、约束、模块、ER 与表设计 |
| 5 | [v2.0 详细实施计划](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md) | 分批依赖、文件归属、伪代码和验收标准；原始基线不等于今日状态 |
| 6 | [API](API.md)、[ROUTES](ROUTES.md) | 当前接口与页面索引 |
| 7 | [B3 审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md) | 2 项 P1、8 项 P2 的实证和修复验收条件 |

[PLAN](PLAN.md) 是实施规格索引；[当前接手文本](NEXT_SESSION_START.md) 规定接手步骤；[协作模板](MULTI_AGENT_COLLABORATION_PROPOSAL.md) 可复用，不将旧角色或授权当作当前任命。

近期交付与验收见 [QA 索引](qa/README.md)。9 月 29 日前的 31 个 QA 批次、旧阅读审查和原始规划已进入 [归档](archive/README.md)。旧三矩阵和旧大篇幅状态/目标正文保存完整快照，当前入口不再重复旧 H1–H6 路线。设计 SQL 和 ER 图是建设规格，正式已登记结构以迁移清单和源码为准。

原报告/冻结件不追改；历史链接与文件位置按归档 MANIFEST 的 source→destination 映射解释。现行说明修正会与旧冻结候选的文档散列不同，这是本次明确的后续文档变更，不重新冻结旧候选冒称无差异。
''')

write("docs/NEXT_SESSION_START.md", '''
# 当前接手入口

更新：2026-10-01。按以下顺序接手，不从归档或旧 B0/B1/B2/B3 启动示例推断当前授权。

1. 读取根和拟改模块的 AGENTS，核对实际 HEAD/分支/工作区，保留用户及其他实现者的改动。
2. 读取 CURRENT_STATUS 的“当前任务与下一动作”和全部未关闭问题；再读 PROJECT_GUIDE 的稳定规则。
3. 按本次用户请求确定任务；需要教学实现时读取 v2.0 实施计划、API 和相关源码，并使用具体可写范围的任务卡。
4. 当前 B3-R01–R10 仍未修复；不能以 B0–B3 已交付、已提交或冻结自洽推断问题已关闭。B4 尚未启动。
5. 只在当前请求范围内开展工作。未实现的学情、AI 教案和练习不能提前标可用；已有教案能力不重建。

主要入口：[当前状态](CURRENT_STATUS.md)、[稳定决定](PROJECT_GUIDE.md)、[实施规格](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)、[B3 审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md)、[文档索引](README.md)。

历史提示词只是当时批次的材料，不能重复启动已交付任务；通用提示模板须按本次请求填写实际批次、起点、前置问题和文件边界。
''')

for name, label in [("PAGE_MATRIX", "页面矩阵"), ("AI_INTERACTIONS", "AI 交互矩阵"), ("MOTION_MATRIX", "动画矩阵")]:
    write(f"docs/replica/{name}.md", f'''# 历史{label}入口

更新：2026-10-01。旧复刻{label}已归档，保留原文用于历史验收追溯，不再作为当前教学闭环实施状态或下一任务的依据。

- [原矩阵完整快照](../archive/snapshots/20261001-docs-focus/docs/replica/{name}.md)
- [当前状态与问题](../CURRENT_STATUS.md)
- [教学闭环实施规格](../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)

仍适用的视觉/动画/数据保护规则见 PROJECT_GUIDE 与模块 AGENTS。归档不代表旧未验事项自动通过，也不授权恢复已移除模块。
''')
write("docs/replica/NEXT_SESSION_START.md", '''# 接手入口迁移

现行接手顺序已移至 [docs/NEXT_SESSION_START.md](../NEXT_SESSION_START.md)。
本路径保留兼容入口；[2026-09-26 原文](../archive/snapshots/20261001-docs-focus/docs/replica/NEXT_SESSION_START.md) 仅供历史读取。
''')
write("docs/replica/README.md", '''# 历史复刻材料兼容入口

三矩阵原文已保存至 [整理前快照](../archive/snapshots/20261001-docs-focus/docs/replica/)。本目录保留旧路径入口，不维护当前教学闭环进度。当前读取 [文档索引](../README.md) 和 [接手顺序](../NEXT_SESSION_START.md)。
''')
write("项目规划/README.md", '''# 原始规划已归档

2026-09-04/05 的原始规划正文和相关材料已移至 [历史归档](../docs/archive/pre-20260929/项目规划/)，保持原字节。旧“暂不接数据库”和 TASKS/HANDOFF 等入口不作为现行指令。

当前任务请读 [文档索引](../docs/README.md)、[当前状态](../docs/CURRENT_STATUS.md) 和 [教学闭环设计](../docs/design/teaching-loop-v1/README.md)。
''')
write("docs/qa/RAG-REBUILD-v1/README.md", '''# RAG-REBUILD v1.0 历史兼容入口

本批为 2026-09-28 历史证据，完整原文与附件已移至 [归档目录](../../archive/pre-20260929/qa/RAG-REBUILD-v1/)。

原路径保留 FROZEN-CANDIDATE.json 的逐字节兼容副本，因为 09-29 RAG-QUALITY 清单直接引用其散列；它不是新的冻结或当前候选。原报告中的路径按 [归档映射](../../archive/pre-20260929/MANIFEST.json) 解释。
''')

collab = (SNAP / "docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md").read_text(encoding="utf-8-sig")
collab = collab.replace("更新：2026-09-23。", "更新：2026-10-01。")
collab = collab.replace("当前用户授权由外部队长担任实施总控，负责STATUS当前任务内的代码、必要契约、文档及本地Git；Codex审查，用户单独指定的文档整理除外。旧MODEL-EXEC/P0文本仅归档，不再决定新任务范围。", "总控、实现与独立验收的负责人由本次任务指定；旧外部队长、MODEL-EXEC/P0 和历史本地 Git 授权不构成当前任命或提交授权。当前主线见 CURRENT_STATUS，详细教学任务规格见 design/teaching-loop-v1。")
collab = collab.replace("STATUS、三矩阵和实际源码", "STATUS、教学闭环实施规格和实际源码")
collab = collab.replace("更新 STATUS 和对应矩阵，显式暂存并提交", "更新 STATUS 和该批证据；只有本次明确授权时才执行 Git 提交")
write("docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md", collab)

design = (SNAP / "docs/design/teaching-loop-v1/README.md").read_text(encoding="utf-8-sig")
design = design.replace("新增两个 SQLite 文件是本轮设计对存储边界的扩展。现有 `apps/api/AGENTS.md` 只列教材、题库和 Qdrant，**实施时需要同步后端存储说明和配置**；本次只交付设计，不建立正式数据目录、不改应用启动、不对正式数据库执行 SQL。", "本目录保留 2026-09-30 的设计规格与参考 SQL；B0–B3 已分批落地四库和部分业务结构。当前后端 AGENTS 已登记四库，正式表结构以追加式迁移为准，不能把本设计 SQL 当作重复建库指令。本次文档整理不执行正式数据库 SQL。")
design = design.replace("实施与派发入口（v2.0）：", "当前能力与待修问题先读 [CURRENT_STATUS](../../CURRENT_STATUS.md)；B3 后续审查发现的 10 项问题尚未修复。本文的表/图仍为目标规格，设计中的‘待建设’不自动等于今日状态。\n\n实施与派发入口（v2.0）：")
write("docs/design/teaching-loop-v1/README.md", design)

plan_name = "docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md"
preserve(plan_name)
plan = (ROOT / plan_name).read_text(encoding="utf-8-sig")
plan = plan.replace("代码基线核查日期：2026-09-30。本文为实施设计，业务尚未实现；文中的状态描述对应核查基线，最新状态应以权威进度文档及实际代码为准。", "代码基线核查日期：2026-09-30；文档定位修正：2026-10-01。本文记录原核查基线及实施设计。能力表中的‘当前’和‘尚未实现’均指该基线，不代表今日状态；B0–B3 的交付及审查待修以 CURRENT_STATUS 和实际代码为准。")
plan = plan.replace("本文的默认 B0 指下一轮的启动建议，本轮仅整理文档，不启动 B0，也不修改 `CURRENT_STATUS.md`。", "实际执行批次和前置修复由 CURRENT_STATUS 与用户本次请求确定，不重复启动已交付批次。")
plan = plan.replace("本期默认启动 B0，后续按用户已经给定的范围推进。", "不设当前默认批次，按用户本次已给定的范围推进。")
plan = plan.replace("#### 1. 当前能力及实施方式", "#### 1. 2026-09-30 基线能力及实施方式")
plan = plan.replace("| 模块 | 当前实际情况 | 本次实施方式 |", "| 模块 | 原核查基线实际情况 | 设计实施方式 |")
plan = plan.replace("本轮默认只实施 **B0**", "首次建设示例只实施 **B0**（历史定位，非当前默认）")
write(plan_name, plan)

prompt_name = "docs/design/teaching-loop-v1/多Agent启动提示词_v2.0.md"
preserve(prompt_name)
prompt = (ROOT / prompt_name).read_text(encoding="utf-8-sig")
prompt = prompt.replace("## 使用方式", "**2026-10-01 定位修正：** 下方 B0 是 09-30 首次启动的历史示例，不应直接当作当前任务下发。新任务先读 CURRENT_STATUS 与最近审查，填写实际授权范围、起点、前置问题和文件归属；不重复 B0–B3，不自动启动 B4。\n\n## 使用方式", 1)
prompt = prompt.replace("1. 第一次启动，将“总控 Agent 启动提示词”完整发给总控 Agent。默认只实施 B0，完成后返回可验收结果。", "1. 首次建设的 B0 示例保留作历史参考；当前接手使用继续提示词并填写实际任务范围，完成后返回可验收结果。")
prompt = prompt.replace("## 总控 Agent 启动提示词：可直接复制", "## 历史首次 B0 总控启动示例：当前不可原样下发", 1)
write(prompt_name, prompt)
for batch in ("B1", "B2", "B3"):
    name = f"docs/design/teaching-loop-v1/{batch}_总控启动提示词.md"
    preserve(name)
    original = (ROOT / name).read_text(encoding="utf-8-sig")
    write(name, f"> 2026-10-01 归档定位：本文件保留 {batch} 当时的执行提示词，属于已交付批次的历史材料，不是当前启动授权。当前任务与 B3 审查前置修复见 [CURRENT_STATUS](../../CURRENT_STATUS.md)，不要原样下发以重复旧批次。\n\n" + original)

knowledge_name = "apps/web/src/features/knowledge/AGENTS.md"
preserve(knowledge_name)
knowledge = (ROOT / knowledge_name).read_text(encoding="utf-8-sig")
knowledge = knowledge.replace("# knowledge 模块约定（教材资料库）", "# knowledge 模块约定（历史本地登记）")
knowledge = knowledge.replace("先读根 `AGENTS.md`。入口 `/knowledge-bases`（详情 `/knowledge-bases/[kbName]`）。\n**登记 → 解析 → 索引为显式模拟**（界面标注【模拟】）：真实文件解析与向量检索未接入。", "先读根 `AGENTS.md`。本指南仅约束历史本地登记组件及 `/knowledge-bases/[kbName]` 的只读兼容详情。当前 `/knowledge-bases` 由 `features/textbook/TextbookWorkspace` 承担真实教材管理，解析、目录、索引与 RAG 走 FastAPI；不要将下方历史模拟规则扩大到真实教材模块。")
knowledge = knowledge.replace("**显式模拟**：全程标注，不读真实文件内容，不宣称真实解析/索引成功；保留进度/取消/重试/恢复完整状态。", "**历史模拟边界**：遗留登记不宣称真实解析/索引成功，不把模拟登记接入教材检索；生产历史详情只读。保留数据兼容，真实功能走 textbook 模块。")
knowledge = knowledge.replace("**单一仓储**：目录读写只经", "**历史登记仓储**：本地登记目录只经")
write(knowledge_name, knowledge)

chat_name = "apps/web/src/features/chat/AGENTS.md"
preserve(chat_name)
chat = (ROOT / chat_name).read_text(encoding="utf-8-sig")
chat = chat.replace("独立于普通聊天，无需配置云模型。", "首答独立于普通聊天使用本地检索；详解冻结并使用当前选择的聊天模型，可为本地或云端。")
write(chat_name, chat)

MP.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"originalFilesPreserved": len(manifest["files"]), "productCodeChanged": False}, ensure_ascii=False))
