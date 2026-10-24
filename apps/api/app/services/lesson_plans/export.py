"""教案 docx 导出组装（R7-BE 核心新能力）：以空白模板为底，组装封面/目录/正文。

模板（仓库内，只读）：``app/resources/lesson_templates/lesson-plan-blank.docx``

**两节结构（保留不动）**：

- 第 1 节：封面 + 目录，无页脚（不显示页码）；
- 第 2 节：正文（第 3 页起），footer 引用 PAGE 域 + ``pgNumType start=1``
  ——正文从 1 重新计数。组装只在两节**内部**改写段落/表格，不增删节、
  不移动分节符/分页符。

**组装口径**：

1. 封面（第 1 页）：标题「（课题名称）」→ ``data.title``；封面表 4 行
   （课程名称/授课教师/授课对象/授课学时）从 ``data.basic`` 取值；
2. 目录（第 2 页）：按 ``modules`` 重写条目行（样式沿用模板：
   仿宋 sz30、行距 exact 680、右对齐点线制表位）；**页码优先取请求里的
   ``sectionPages``**（前端预览分页的「模块 → 正文页码」，正文 1 起），缺省才回退
   行数估算；目录与预览同源；
3. 第 3 页起正文：页眉标题「（课程名称）　教学设计」→「{courseName}　教学设计」；
   各内置模块按模板四表口径填充：
   - 一、基本信息（4 列表：课程名称/授课对象/授课时间/授课地点/教学章节）；
   - 二、教学分析（2 列：学情/教材/内容/思政）；
   - 三、教学目标（3 列 vMerge：教学目标跨 3 行 + 知识/能力/思政；重点/难点两行）；
   - 四、教学策略（在目标表尾部 3 行：设计思路/教学流程/教学手段——模板里
     策略与目标同表）；
   - 五、教学过程（4 列：环节/教师活动/学生活动/设计意图，阶段跨列行；
     超出模板 5 阶段/6 内容行时按行克隆，不丢环节）；
   - 六、评价反馈（跨列表：模板四项小标题常驻——（一）课后测试、（二）课后作业、
     （三）课后调查反馈、（四）督导专家反馈；（二）承接 homework，空则 exercises）；
   - 七、教学反思（跨列表：模板三项小标题常驻——目标达成度/教学特色/教学后记，
     带标题的文本按标题拆分）；
   - **自定义模块**：克隆模板表样式新增「标题跨列 + 正文」表，按 ``modules``
     顺序插入到正文表序列末尾；
4. 字体与字号：``w:eastAsia``/``w:ascii`` 按 ``style.fontId`` 写入中文俗名；
   板块标题用 ``headingSize``、标签格用 ``labelSize``、正文用 ``baseSize``，
   行高与段距写入段落间距（预览滑杆在 docx 里同样生效）。

**重开校验**（``verify_document``）：导出后用 python-docx 重新打开断言
节数=2、第 2 节 footer 引用 PAGE、表数=四表+自定义数、关键文本入位、
产物字节 >0 且 ``PK`` 魔数。

产物落盘：``file_assets``（kind='export'，内容寻址 blob）——与 R6 学情报告
产物同一受管资产形态（``export_artifacts`` 表被 practice_exports 表级外键
锁死，不可伪造练习占位行，见 ``services/export_artifacts`` 的分派语义）；
重复导出生成新产物（同内容 blob 幂等、资产登记新行、artifactId 新）。
"""

from __future__ import annotations

import copy
import hashlib
import io
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt

#: 模板位置（仓库内只读资源；样板 ``lesson-plan-filled-sample.docx`` 供人工比对）。
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "resources" / "lesson_templates"
BLANK_TEMPLATE = TEMPLATE_DIR / "lesson-plan-blank.docx"

#: 导出 docx 的 media type（与学情报告产物一致）。
LESSON_EXPORT_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

#: 内置模块默认顺序与中文标签（与前端 BUILTIN_MODULES 一致）。
BUILTIN_ORDER: tuple[str, ...] = ("basic", "analysis", "objectives", "strategy", "process", "evaluation", "reflection")
BUILTIN_LABEL: dict[str, str] = {
    "basic": "基本信息", "analysis": "教学分析", "objectives": "教学目标", "strategy": "教学策略",
    "process": "教学过程", "evaluation": "评价反馈", "reflection": "教学反思",
}

#: 预览 tableId 分组（与 pagination.ts / PaperPreview.TableSegment 同口径）：
#: 目标+策略共用一张表；过程单独一张；评价+反思共用一张表；custom 各自成表。
MODULE_TABLE_ID: dict[str, str] = {
    "basic": "basic",
    "analysis": "analysis",
    "objectives": "objectives",
    "strategy": "objectives",
    "process": "process",
    "evaluation": "evaluation",
    "reflection": "evaluation",
}

CHINESE_NUMBERS: tuple[str, ...] = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")
#: A4 宽度（twips）；页边距由 style.pageMargin（px）换算。
PAGE_WIDTH_TWIPS = 11906

#: fontId → docx eastAsia 字体名（前端字体族的首选中文名；未装字体由 Word 回退）。
FONT_EAST_ASIA: dict[str, str] = {
    "puhuiti": "阿里巴巴普惠体",
    "misans": "MiSans",
    "noto-sans-sc": "思源黑体",
    "source-han-serif": "思源宋体",
}

#: 目录行样式参数（沿用模板：仿宋 sz30 半点单位、行距 exact 680 twips、点线制表位）。
#: 模板右制表位 9298tw / 内容宽 9752tw；页边距变化时按比例调整。
TOC_TAB_RATIO = 9298 / 9752
TOC_LINE_EXACT = 680
TOC_FONT_SIZE_HALF_PT = 30

#: 页码估算口径：模板正文每页约容纳的表格内容行（A4，行距 exact 480 twips 的表格行）。
_ESTIMATED_ROWS_PER_PAGE = 12


class ExportAssemblyError(Exception):
    """导出组装失败（模板缺失/重开校验不通过）；调用方转 500 AppError。"""


@dataclass
class ExportPayload:
    """一次导出装配请求（前端 ``LessonExportRequest`` 的服务端形状）。"""

    data: dict
    style: dict = field(default_factory=dict)
    modules: list[dict] = field(default_factory=list)
    section_pages: dict[str, int] = field(default_factory=dict)

    @classmethod
    def parse(cls, body: Any) -> "ExportPayload":
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise ExportAssemblyError("导出请求缺少教案正文 data。")
        data = body["data"]
        if not any(key in data for key in _LESSON_DATA_KEYS):
            raise ExportAssemblyError("教案文档结构无法识别：正文 data 缺少教案字段。")
        style = body.get("style") if isinstance(body.get("style"), dict) else {}
        raw_modules = body.get("modules") if isinstance(body.get("modules"), list) else []
        modules = [m for m in raw_modules if isinstance(m, dict)]
        if not modules:
            # 缺省：全部内置模块按默认顺序可见（与前端默认布局一致）。
            modules = [{"id": key, "kind": "builtin", "builtinId": key, "label": BUILTIN_LABEL[key]} for key in BUILTIN_ORDER]
        raw_pages = body.get("sectionPages")
        section_pages: dict[str, int] = {}
        if isinstance(raw_pages, dict):
            for key, page in raw_pages.items():
                if isinstance(key, str) and isinstance(page, int) and page >= 1:
                    section_pages[key] = page
        return cls(data=body["data"], style=style, modules=modules, section_pages=section_pages)


@dataclass
class ModuleEntry:
    """规范化后的模块清单项：顺序/显隐/自定义位置都来自前端 ``modules``。

    与前端 ``normalizeModules`` 同口径：保留请求顺序、去重；缺失的内置模块按默认
    顺序补在尾部。中文序号只给可见内置模块，custom 不占号。
    """

    id: str
    kind: str  # builtin | custom
    builtin: str | None
    label: str
    hidden: bool = False
    body: str = ""
    no: str = ""

    @property
    def title(self) -> str:
        if self.kind == "custom":
            return self.label or "自定义模块"
        return f"{self.no}、{self.label}"

    @property
    def table_id(self) -> str:
        if self.kind == "custom":
            return f"custom:{self.id}"
        return MODULE_TABLE_ID.get(self.builtin or "", "analysis")


def _module_entries(modules: list[dict]) -> list[ModuleEntry]:
    entries: list[ModuleEntry] = []
    seen: set[str] = set()
    for raw in modules:
        if not isinstance(raw, dict):
            continue
        if raw.get("kind") == "custom":
            module_id = _text(raw.get("id")) or f"custom-{len(entries) + 1}"
            if module_id in seen:
                continue
            seen.add(module_id)
            entries.append(
                ModuleEntry(
                    id=module_id,
                    kind="custom",
                    builtin=None,
                    label=_text(raw.get("label")) or "自定义模块",
                    hidden=raw.get("hidden") is True,
                    body=_text(raw.get("body")),
                )
            )
            continue
        builtin = raw.get("builtinId") or raw.get("id")
        if builtin not in BUILTIN_ORDER or builtin in seen:
            continue
        seen.add(builtin)
        entries.append(
            ModuleEntry(
                id=_text(raw.get("id")) or builtin,
                kind="builtin",
                builtin=builtin,
                label=BUILTIN_LABEL[builtin],
                hidden=raw.get("hidden") is True,
            )
        )
    for builtin in BUILTIN_ORDER:
        if builtin not in seen:
            seen.add(builtin)
            entries.append(
                ModuleEntry(id=builtin, kind="builtin", builtin=builtin, label=BUILTIN_LABEL[builtin])
            )
    visible_index = 0
    for entry in entries:
        if entry.kind != "builtin" or entry.hidden:
            continue
        entry.no = (
            CHINESE_NUMBERS[visible_index]
            if visible_index < len(CHINESE_NUMBERS)
            else str(visible_index + 1)
        )
        visible_index += 1
    return entries


#: 教案正文可识别的键（至少命中一个才算教案文档；与前端 isLessonDataShaped 同口径）。
_LESSON_DATA_KEYS = ("title", "basic", "analysis", "strategy", "evaluation", "processV2",
                     "coreCompetencies", "keyPoints", "teachingDesign", "reflection")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _style_number(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    """前端样式值的防御性夹取；异常值退回模板默认，避免生成坏文档。"""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    if not math.isfinite(numeric):
        numeric = fallback
    return max(minimum, min(maximum, numeric))


def _style_sizes(style: dict) -> tuple[float, float, float]:
    """(正文, 板块标题, 标签) 的 px 字号；默认即模板 14pt / 15pt / 14pt。"""
    return (
        _style_number(style.get("baseSize"), 18.67, 8, 40),
        _style_number(style.get("headingSize"), 20, 8, 60),
        _style_number(style.get("labelSize"), 18.67, 8, 40),
    )


def _style_metrics(style: dict) -> dict[str, float]:
    return {
        "line_height": _style_number(style.get("lineHeight"), 1.714, 1.0, 3.0),
        "paragraph_gap": _style_number(style.get("paragraphGap"), 0, 0, 100),
        "module_gap": _style_number(style.get("moduleGap"), 8, 0, 100),
        "page_margin": _style_number(style.get("pageMargin"), 72, 24, 200),
    }


def _content_width_twips(style: dict) -> int:
    margin_twips = round(_style_metrics(style)["page_margin"] * 15)
    return max(1000, PAGE_WIDTH_TWIPS - 2 * margin_twips)


def _font_family(style: dict) -> str:
    font_id = _text(style.get("fontId")) or "puhuiti"
    return FONT_EAST_ASIA.get(font_id, FONT_EAST_ASIA["puhuiti"])


def _px_to_half_pt(px: float | int | None, fallback: float) -> int:
    """前端 px 字号 → docx 半点（1px≈0.75pt；docx sz 单位是半点）。"""
    try:
        px_value = float(px)
    except (TypeError, ValueError):
        px_value = fallback
    half = round(px_value * 0.75 * 2)
    return max(8, min(120, int(half)))


def _set_run_font(run: Any, *, east_asia: str, size_half_pt: int | None = None, bold: bool | None = None) -> None:
    """写 run 字体（含 w:eastAsia）；未装字体由 Word 按族回退（可接受）。"""
    r_pr = run._element.get_or_add_rPr()
    fonts = r_pr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = r_pr.makeelement(qn("w:rFonts"), {})
        r_pr.insert(0, fonts)
    fonts.set(qn("w:ascii"), east_asia)
    fonts.set(qn("w:hAnsi"), east_asia)
    fonts.set(qn("w:eastAsia"), east_asia)
    if size_half_pt is not None:
        sz = r_pr.find(qn("w:sz"))
        if sz is None:
            sz = r_pr.makeelement(qn("w:sz"), {})
            r_pr.append(sz)
        sz.set(qn("w:val"), str(size_half_pt))
    if bold is not None:
        b = r_pr.find(qn("w:b"))
        if b is None:
            b = r_pr.makeelement(qn("w:b"), {})
            r_pr.append(b)
        if bold:
            b.attrib.pop(qn("w:val"), None)
        else:
            b.set(qn("w:val"), "0")


def _clear_paragraph_indent(paragraph: Any) -> None:
    """去掉模板段落的中文首行缩进（w:firstLineChars 优先于 w:firstLine，必须整段移除）。"""
    p_pr = paragraph._p.get_or_add_pPr()
    ind = p_pr.find(qn("w:ind"))
    if ind is not None:
        p_pr.remove(ind)


def _fill_cell(cell: Any, text: str, *, east_asia: str, size_half_pt: int, bold: bool = False) -> None:
    """把单元格写为文本（多行按 \\n 拆段），复用模板已有段落。

    模板的值格预置 2–4 个空段落；旧实现只复用第一段，其余文本用 add_paragraph
    追加到格尾，模板空段就留在文本行之间，导出出现大量空行。这里：
    - 行数少于模板段数：删掉尾部多余段；
    - 行数多于模板段数：在格尾补段；
    - 每个文本行写进对应段落，段间不残留空段。
    """
    paragraphs = list(cell.paragraphs)
    if not paragraphs:
        paragraphs = [cell.add_paragraph()]
    lines = (text or "").split("\n")
    if not lines:
        lines = [""]
    while len(paragraphs) < len(lines):
        paragraphs.append(cell.add_paragraph())
    for para in paragraphs[len(lines):]:
        para._p.getparent().remove(para._p)
    paragraphs = paragraphs[: len(lines)]
    for para, line in zip(paragraphs, lines):
        for run in list(para.runs):
            run._element.getparent().remove(run._element)
        # 模板个别值格带首行缩进；预览不缩进，导出也统一清零。
        fmt = para.paragraph_format
        fmt.left_indent = Pt(0)
        fmt.first_line_indent = Pt(0)
        _clear_paragraph_indent(para)
        run = para.add_run(line)
        _set_run_font(run, east_asia=east_asia, size_half_pt=size_half_pt, bold=bold or None)


def _replace_paragraph_text(paragraph: Any, text: str, *, east_asia: str, size_half_pt: int | None = None) -> None:
    """整段替换文本：保留段落 pPr 与首个 run 的 rPr，仅换内容与字体族。"""
    runs = paragraph.runs
    if runs:
        keep = runs[0]
        keep.text = text
        for run in runs[1:]:
            run._element.getparent().remove(run._element)
        _set_run_font(keep, east_asia=east_asia, size_half_pt=size_half_pt)
    else:
        run = paragraph.add_run(text)
        _set_run_font(run, east_asia=east_asia, size_half_pt=size_half_pt)


def _estimate_page_starts(payload: ExportPayload, visible: list[ModuleEntry]) -> dict[str, int]:
    """目录页码回退估算：按每模块内容行数累加（≈12 行/页）。

    **只有前端没带 ``sectionPages`` 时才用**。页码口径与文档一致：正文从 1 起
    （模板第 2 节 ``pgNumType start=1``），不再是文档页序号 3。实际分页由 Word
    排版引擎决定；预览带页码时以后者为准。
    """
    data = payload.data
    rows_of: dict[str, int] = {}
    basic = data.get("basic") or {}
    analysis = data.get("analysis") or {}
    strategy = data.get("strategy") or {}
    evaluation = data.get("evaluation") or {}
    rows_of["basic"] = 3 + max(1, len(_text(basic.get("chapter")).split("\n")))
    rows_of["analysis"] = 1 + sum(2 for key in ("learning", "textbook", "content", "ideological") if _text(analysis.get(key)))
    rows_of["objectives"] = 5 + len(_text(data.get("coreCompetencies")).split("\n"))
    rows_of["strategy"] = 3 + sum(len(_text(strategy.get(key)).split("\n")) for key in ("designThinking", "teachingFlow", "methods"))
    rows_of["process"] = 2 + len(data.get("processV2") or []) * 2
    rows_of["evaluation"] = 6 + len(_text(evaluation.get("afterClassTest")).split("\n")) + len(
        (_text(evaluation.get("homework")) or _text(data.get("exercises"))).split("\n")
    )
    rows_of["reflection"] = 5 + len(_text(data.get("reflection")).split("\n"))
    starts: dict[str, int] = {}
    page, used = 1, 0  # 正文从第 1 页起（pgNumType start=1）
    for entry in visible:
        starts[entry.id] = page
        if entry.kind == "custom":
            used += 2 + max(1, len(_text(entry.body).split("\n")))
        else:
            used += rows_of.get(entry.builtin or "", 2)
        while used >= _ESTIMATED_ROWS_PER_PAGE:
            page += 1
            used -= _ESTIMATED_ROWS_PER_PAGE
    return starts


def _section_page_starts(payload: ExportPayload, visible: list[ModuleEntry]) -> dict[str, int]:
    """优先用预览分页结果，缺失的模块（如被隐藏）回退到行数估算（口径都是正文 1 起）。"""
    estimated = _estimate_page_starts(payload, visible)
    if payload.section_pages:
        estimated.update(payload.section_pages)
    return estimated


def _rewrite_toc(document: Any, payload: ExportPayload, visible: list[ModuleEntry]) -> None:
    """按可见模块的顺序/动态编号重写目录，页码取预览的 ``sectionPages``。

    模板目录固定七行；可见模块少于七条时删除多余行，多于七条时克隆最后一行。
    目录与正文共用同一套 ``entry.title``，因此重排/隐藏/custom 插中间时两处始终一致。
    """
    east_asia = _font_family(payload.style)
    base_px, _, _ = _style_sizes(payload.style)
    toc_size = max(TOC_FONT_SIZE_HALF_PT, _px_to_half_pt(base_px, 14))
    starts = _section_page_starts(payload, visible)
    titles = [entry.title for entry in visible]
    pages = [starts.get(entry.id, 1) for entry in visible]
    tab_pos = max(1000, round(_content_width_twips(payload.style) * TOC_TAB_RATIO))

    # 定位模板目录行：模板文本仍是「一、基本信息 ~ 七、教学反思」，先按文本收齐七行。
    toc_paras: list[Any] = []
    collecting = False
    for para in document.paragraphs:
        text = para.text.strip()
        if text.startswith("一、基本信息"):
            collecting = True
            toc_paras.append(para)
            continue
        if collecting:
            if re.match(r"^[二三四五六七]、", text):
                toc_paras.append(para)
                continue
            break
    if len(toc_paras) != 7:
        raise ExportAssemblyError(f"模板目录段落异常：{len(toc_paras)} 行（应为 7）。")

    if not titles:
        for para in toc_paras:
            para._p.getparent().remove(para._p)
        return

    template_toc_p = toc_paras[-1]._p
    while len(toc_paras) < len(titles):
        clone = copy.deepcopy(template_toc_p)
        template_toc_p.addnext(clone)
        template_toc_p = clone
        toc_paras.append(_para_of(document, clone))
    if len(toc_paras) > len(titles):
        for para in toc_paras[len(titles):]:
            para._p.getparent().remove(para._p)
        toc_paras = toc_paras[: len(titles)]

    for para, title, page in zip(toc_paras, titles, pages):
        p_pr = para._p.get_or_add_pPr()
        tabs = p_pr.find(qn("w:tabs"))
        if tabs is None:
            tabs = p_pr.makeelement(qn("w:tabs"), {})
            p_pr.insert(0, tabs)
        tab = tabs.find(qn("w:tab"))
        if tab is None:
            tab = tabs.makeelement(qn("w:tab"), {})
            tabs.append(tab)
        tab.set(qn("w:pos"), str(tab_pos))
        tab.set(qn("w:val"), "right")
        tab.set(qn("w:leader"), "dot")
        spacing = p_pr.find(qn("w:spacing"))
        if spacing is None:
            spacing = p_pr.makeelement(qn("w:spacing"), {})
            p_pr.append(spacing)
        spacing.set(qn("w:line"), str(TOC_LINE_EXACT))
        spacing.set(qn("w:lineRule"), "exact")
        runs = para.runs
        if runs:
            keep = runs[0]
            keep.text = title
            for run in runs[1:]:
                run._element.getparent().remove(run._element)
            _set_run_font(keep, east_asia=east_asia, size_half_pt=toc_size)
            tab_run = para.add_run("\t" + str(page))
            _set_run_font(tab_run, east_asia=east_asia, size_half_pt=toc_size)
        else:
            run = para.add_run(title + "\t" + str(page))
            _set_run_font(run, east_asia=east_asia, size_half_pt=toc_size)


def _para_of(document: Any, element: Any) -> Any:
    """把段落 XML 元素包回 python-docx Paragraph 对象。"""
    from docx.text.paragraph import Paragraph

    return Paragraph(element, document)


def _objectives_rows(data: dict) -> tuple[str, str, str]:
    """coreCompetencies 的行编码（与前端 objectives.ts 同一可逆编码）：
    「知识：/能力：/思政：」标签行；无标签文本归入其他 → 追加到思政行尾部不丢字。"""
    rows = {"知识": [], "能力": [], "思政": []}
    other: list[str] = []
    current: str | None = None
    pattern = re.compile(r"^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*(知识|能力|思政)\s*(?:目标|素养)?\s*(?:】|\]|）|\))?\s*(?:[#>*\-–—•·]+\s*)?[：:、.．]?\s*(.*)$")
    keypoints = re.compile(r"^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*教学(?:重点|难点|重、难点|重难点)\s*(?:】|\]|）|\))?")
    for raw_line in _text(data.get("coreCompetencies")).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if keypoints.match(line):
            current = None
            other.append(line)
            continue
        match = pattern.match(line)
        if match:
            current = match.group(1)
            value = (match.group(2) or "").strip()
            if value:
                rows[current].append(value)
            continue
        if current:
            rows[current].append(line)
        else:
            other.append(line)
    join = lambda key: "\n".join(rows[key])
    tail = "\n".join(other)
    ability = join("能力")
    if tail:
        ideological = join("思政")
        ideological = f"{ideological}\n{tail}" if ideological else tail
    else:
        ideological = join("思政")
    # 旧文档完全无标签：整体进知识行（不丢字，形状仍是三行 vMerge）
    if not join("知识") and not ability and not ideological and _text(data.get("coreCompetencies")).strip():
        return _text(data.get("coreCompetencies")).strip(), "", ""
    return join("知识"), ability, ideological


_KEY_LABEL = re.compile(
    r"^\s*(?:[#>*\-–—•·]+\s*)?(?:\d+\s*[.、)）]?\s*)?\s*(?:【|\[|（|\()?\s*"
    r"教学(重点|难点|重、难点|重难点)\s*(?:】|\]|）|\))?\s*[：:、.．]?\s*(.*)$"
)


def _key_points_pair(data: dict) -> tuple[str, str]:
    """keyPoints 字段 → 教学重点/难点两行（与前端 readKeyPoints 同口径）。

    旧实现的正则 ``教学?重、?难点`` 匹配不到「教学难点」，难点行连同内容被并进
    重点格；这里改为与前端一致的 (重点|难点|重、难点|重难点) 捕获，并且只保留
    值（标签列已经写着「教学重点/难点」，值格不再重复前缀）。
    """
    key_points: list[str] = []
    difficulties: list[str] = []
    current: list[str] | None = None
    for raw_line in _text(data.get("keyPoints")).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _KEY_LABEL.match(line)
        if match:
            current = key_points if match.group(1) == "重点" else difficulties
            value = (match.group(2) or "").strip()
            if value:
                current.append(value)
            continue
        if current is not None:
            current.append(line)
        else:
            key_points.append(line)
    return "\n".join(key_points), "\n".join(difficulties)


def _phase_label_of(item: dict) -> str:
    label = _text(item.get("phaseLabel"))
    if label:
        return label
    phases = {
        "warmup": "课前热身", "introduction": "第一阶段　课程引入",
        "exploration": "第二阶段　深入探究", "practice": "第三阶段　练习巩固",
        "conclusion": "第四阶段　总结提升",
    }
    return phases.get(_text(item.get("phase")), "")


def _process_sequence(data: dict) -> list[tuple[str, tuple[str, str, str, str]]]:
    """教学过程行序列：``("stage", (label, "", "", ""))`` 与 ``("content", (title, teacher, student, intent))``。

    阶段行与内容行分开标记，便于按模板行样式克隆/重建（不再受模板 5 阶段 / 6 内容行限制）。
    """
    rows_v2 = data.get("processV2")
    if isinstance(rows_v2, list) and rows_v2:
        items = [item for item in rows_v2 if isinstance(item, dict)]
    else:
        # 旧字段映射（与前端 processToV2 同口径）
        items = [
            {"id": item.get("id") or f"process-{index}", "phase": "exploration", "phaseLabel": "",
             "title": _text(item.get("stage")), "teacherActivity": _text(item.get("design")),
             "studentActivity": "", "intent": _text(item.get("secondary"))}
            for index, item in enumerate(data.get("process") or [])
            if isinstance(item, dict)
        ]
    sequence: list[tuple[str, tuple[str, str, str, str]]] = []
    current_phase: str | None = None
    for item in items:
        label = _phase_label_of(item)
        if label and label != current_phase:
            sequence.append(("stage", (label, "", "", "")))
            current_phase = label
        sequence.append(
            (
                "content",
                (
                    _text(item.get("title")),
                    _text(item.get("teacherActivity")),
                    _text(item.get("studentActivity")),
                    _text(item.get("intent")),
                ),
            )
        )
    return sequence


#: 模板评价反馈的四项小标题（与预览同一口径）。
EVALUATION_HEADINGS = (
    "（一）学生课后测试情况",
    "（二）学生课后作业情况",
    "（三）学生课后调查反馈",
    "（四）督导专家课后反馈",
)

#: 模板教学反思的三项小标题（与预览同一口径）。
REFLECTION_HEADINGS = (
    "（一）目标达成度分析",
    "（二）教学特色与可供借鉴之处",
    "（三）教学后记",
)

_REFLECTION_MARKERS = (
    ("achievement", re.compile(r"^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*目标达成度")),
    ("features", re.compile(r"^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*教学特色")),
    ("postscript", re.compile(r"^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*教学后记")),
)


def _evaluation_text(data: dict) -> str:
    """评价反馈一格：模板四项标题常驻；（二）承接 homework（空则 exercises，都有则合并）。

    值为空时只输出小标题，不输出空段落——与预览的「一格多段」同一口径，避免 docx
    在（三）（四）下面多出没有内容的空行。
    """
    evaluation = data.get("evaluation") or {}
    homework = _text(evaluation.get("homework")).strip()
    exercises = _text(data.get("exercises")).strip()
    if homework and exercises and homework != exercises:
        homework_text = f"{homework}\n{exercises}"
    else:
        homework_text = homework or exercises
    lines: list[str] = []
    for heading, value in (
        (EVALUATION_HEADINGS[0], _text(evaluation.get("afterClassTest")).strip()),
        (EVALUATION_HEADINGS[1], homework_text),
        (EVALUATION_HEADINGS[2], ""),
        (EVALUATION_HEADINGS[3], ""),
    ):
        lines.append(heading)
        if value:
            lines.extend(value.split("\n"))
    return "\n".join(lines)


def _reflection_parts(text: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {"achievement": [], "features": [], "postscript": []}
    current = "achievement"
    for line in (text or "").splitlines():
        hit = next((key for key, pattern in _REFLECTION_MARKERS if pattern.match(line)), None)
        if hit:
            current = hit
            continue
        buckets[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in buckets.items()}


def _reflection_text(data: dict) -> str:
    """教学反思一格：模板三项标题常驻；无标题文本整体进（一）；空值不输出空段。"""
    parts = _reflection_parts(_text(data.get("reflection")))
    lines: list[str] = []
    for heading, value in (
        (REFLECTION_HEADINGS[0], parts["achievement"]),
        (REFLECTION_HEADINGS[1], parts["features"]),
        (REFLECTION_HEADINGS[2], parts["postscript"]),
    ):
        lines.append(heading)
        if value:
            lines.extend(value.split("\n"))
    return "\n".join(lines)


def _row_index_by_text(table: Any, needle: str) -> int | None:
    for index, row in enumerate(table.rows):
        if needle in " ".join(cell.text for cell in row.cells):
            return index
    return None


def _rebuild_process_rows(
    table: Any,
    data: dict,
    *,
    east_asia: str,
    body_half: int,
) -> None:
    """按数据重建「五、教学过程」行区：模板 5 阶段 / 6 内容行的上限不再丢行。

    这里拿到的表已经从模板表 4 中抽取过，只含 band + 两行表头 + 阶段/内容行，
    不再包含「六、评价反馈」；因此直接从第 3 行起重建，用 row 3（阶段）与
    row 4（内容）为样式样板克隆出与数据等长的行序列。
    """
    rows = table.rows
    if len(rows) < 5:
        raise ExportAssemblyError("模板教学过程表结构异常（缺少阶段/内容样板行）。")
    stage_template = copy.deepcopy(rows[3]._tr)
    content_template = copy.deepcopy(rows[4]._tr)
    for row in list(rows)[3:]:
        row._tr.getparent().remove(row._tr)

    sequence = _process_sequence(data)
    if not sequence:
        sequence = [("content", ("", "", "", ""))]
    for kind, _ in sequence:
        clone = copy.deepcopy(stage_template if kind == "stage" else content_template)
        table._tbl.append(clone)

    for offset, (kind, cells_text) in enumerate(sequence):
        row = table.rows[3 + offset]
        if kind == "stage":
            _fill_cell(row.cells[0], cells_text[0], east_asia=east_asia, size_half_pt=body_half)
            continue
        for cell, text in zip(row.cells, cells_text):
            _fill_cell(cell, text, east_asia=east_asia, size_half_pt=body_half)


def _fill_paragraphs_with_bold_headings(cell: Any, text: str, *, east_asia: str, size_half_pt: int) -> None:
    """整格多段写入：以「（一）…」开头的段落加粗（模板评价/反思的小标题）。"""
    lines = text.split("\n")
    paragraphs = cell.paragraphs
    for para in paragraphs[len(lines):]:
        para._p.getparent().remove(para._p)
    for index, line in enumerate(lines):
        para = paragraphs[index] if index < len(paragraphs) else cell.add_paragraph()
        for run in list(para.runs):
            run._element.getparent().remove(run._element)
        # 模板评价/反思格的若干预置段带不同首行缩进；预览统一不缩进，导出也清零。
        fmt = para.paragraph_format
        fmt.left_indent = Pt(0)
        fmt.first_line_indent = Pt(0)
        _clear_paragraph_indent(para)
        run = para.add_run(line)
        heading = bool(re.match(r"^\s*（[一二三四五六七八九十]+）", line))
        _set_run_font(run, east_asia=east_asia, size_half_pt=size_half_pt, bold=heading)


#: 模板里的标签格文本（表头/字段名）；字号用 style.labelSize。
LABEL_TEXTS = frozenset(
    {
        "课程名称", "授课教师", "授课对象", "授课学时",
        "授课时间", "授课地点", "教学章节",
        "学情分析", "教材分析", "教学内容", "思政资源",
        "教学目标", "知识目标", "能力目标", "思政目标", "教学重点", "教学难点",
        "设计思路", "教学流程", "教学手段",
        "教学环节", "教学活动", "教师活动", "学生活动", "设计意图",
    }
)

_SECTION_BAND = re.compile(r"^[一二三四五六七八九十]+、")
_STAGE_LABEL = re.compile(r"^(?:第[一二三四五六七八九十]+阶段|课前热身|课程引入|深入研讨|练习巩固|总结提升)")


def _apply_paragraph_format(
    paragraph: Any,
    *,
    size_px: float,
    line_height: float,
    paragraph_gap_px: float,
    last: bool,
) -> None:
    """行距/段距与预览同口径：exact 行高 = 字号 × 行高；段距只在段与段之间。"""
    fmt = paragraph.paragraph_format
    fmt.line_spacing = Pt(size_px * 0.75 * line_height)
    fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(paragraph_gap_px * 0.75 if not last else 0.0)


def _apply_template_typography(
    document: Any,
    *,
    style: dict,
    roles: dict[Any, str],
    east_asia: str,
    heading_half: int,
    label_half: int,
    body_half: int,
) -> None:
    """正文表格逐格套字号/行距：板块标题 heading、标签格 label、正文 base。

    字号、行高、段距全部来自与预览同一份 style；默认值即模板的 14pt/15pt、
    24pt exact、段距 0，所以默认导出与模板视觉一致，滑杆改动时两端同步。
    """
    base_px, heading_px, label_px = _style_sizes(style)
    metrics = _style_metrics(style)
    line_height = metrics["line_height"]
    paragraph_gap = metrics["paragraph_gap"]
    for table in document.tables:
        role = roles.get(table._tbl)
        for row_index, row in enumerate(table.rows):
            seen: set[Any] = set()
            for cell_index, cell in enumerate(row.cells):
                if cell._tc in seen:
                    continue
                seen.add(cell._tc)
                text = cell.text.strip()
                first_line = text.split("\n", 1)[0].strip()
                if role == "custom" and row_index == 0:
                    size_half, size_px, bold = heading_half, heading_px, True
                elif _SECTION_BAND.match(first_line):
                    size_half, size_px, bold = heading_half, heading_px, True
                elif first_line in LABEL_TEXTS or _STAGE_LABEL.match(first_line):
                    size_half, size_px, bold = label_half, label_px, True
                elif role == "process" and row_index >= 3 and len(row.cells) == 4 and cell_index == 0:
                    # 教学过程内容行的首列（环节名）在模板里是标签格。
                    size_half, size_px, bold = label_half, label_px, True
                else:
                    size_half, size_px, bold = body_half, base_px, None
                paragraphs = cell.paragraphs
                for para_index, para in enumerate(paragraphs):
                    _apply_paragraph_format(
                        para,
                        size_px=size_px,
                        line_height=line_height,
                        paragraph_gap_px=paragraph_gap,
                        last=para_index == len(paragraphs) - 1,
                    )
                    heading_para = bool(re.match(r"^\s*（[一二三四五六七八九十]+）", para.text))
                    for run in para.runs:
                        _set_run_font(
                            run,
                            east_asia=east_asia,
                            size_half_pt=size_half,
                            bold=True if (heading_para and size_half == body_half) else bold,
                        )


def _extract_rows(table: Any, start: int, end: int) -> Any:
    """深拷贝一张模板表并只保留 [start, end) 行（保留 tblPr/tblGrid/边框/底纹）。"""
    clone = copy.deepcopy(table._tbl)
    rows = clone.findall(qn("w:tr"))
    for index, row in enumerate(list(rows)):
        if index < start or index >= end:
            clone.remove(row)
    return clone


def _extract_sources(document: Any) -> dict[str, Any]:
    """从模板四张正文表抽取各模块的行样式样板（在删除旧表之前调用）。"""
    basic = document.tables[1]
    analysis = document.tables[2]
    goals = document.tables[3]
    process = document.tables[4]
    strategy_start = _row_index_by_text(goals, "四、教学策略")
    evaluation_start = _row_index_by_text(process, "六、评价反馈")
    reflection_start = _row_index_by_text(process, "七、教学反思")
    if (
        strategy_start is None
        or evaluation_start is None
        or reflection_start is None
        or reflection_start <= evaluation_start
    ):
        raise ExportAssemblyError("模板正文表结构异常（缺少策略/评价/反思分段）。")
    return {
        "basic": _extract_rows(basic, 0, len(basic.rows)),
        "analysis": _extract_rows(analysis, 0, len(analysis.rows)),
        "objectives": _extract_rows(goals, 0, strategy_start),
        "strategy": _extract_rows(goals, strategy_start, len(goals.rows)),
        "process": _extract_rows(process, 0, evaluation_start),
        "evaluation": _extract_rows(process, evaluation_start, reflection_start),
        "reflection": _extract_rows(process, reflection_start, len(process.rows)),
    }


def _set_band_title(table: Any, title: str, *, east_asia: str, heading_half: int) -> None:
    _fill_cell(
        table.rows[0].cells[0],
        title,
        east_asia=east_asia,
        size_half_pt=heading_half,
        bold=True,
    )


def _make_custom_body_row(element: Any) -> None:
    """自定义模块：band 后只留一行跨 2 列的正文格（删掉模板分析表的其余行/格）。"""
    rows = element.findall(qn("w:tr"))
    if len(rows) < 2:
        raise ExportAssemblyError("模板分析表缺少正文行，无法生成自定义模块。")
    body_row = rows[1]
    cells = body_row.findall(qn("w:tc"))
    if len(cells) >= 2:
        for extra in cells[1:]:
            body_row.remove(extra)
        first = cells[0]
        tc_pr = first.find(qn("w:tcPr"))
        if tc_pr is None:
            tc_pr = OxmlElement("w:tcPr")
            first.insert(0, tc_pr)
        grid_span = tc_pr.find(qn("w:gridSpan"))
        if grid_span is None:
            grid_span = OxmlElement("w:gridSpan")
            tc_pr.insert_element_before(
                grid_span,
                "w:hMerge",
                "w:vMerge",
                "w:tcBorders",
                "w:shd",
                "w:noWrap",
                "w:tcMar",
                "w:textDirection",
                "w:tcFitText",
                "w:vAlign",
                "w:hideMark",
            )
        grid_span.set(qn("w:val"), "2")
        tc_w = tc_pr.find(qn("w:tcW"))
        grid = element.find(qn("w:tblGrid"))
        total = 0
        if grid is not None:
            total = sum(int(column.get(qn("w:w")) or 0) for column in grid.findall(qn("w:gridCol")))
        if tc_w is not None:
            tc_w.set(qn("w:w"), str(total or 9752))
            tc_w.set(qn("w:type"), "dxa")


def _spacer_paragraph(gap_px: float) -> Any:
    """表间空段：exact 行高 = moduleGap px × 15 twips，不留 before/after。"""
    paragraph = OxmlElement("w:p")
    p_pr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:line"), str(max(0, int(round(gap_px * 15)))))
    spacing.set(qn("w:lineRule"), "exact")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    p_pr.append(spacing)
    paragraph.append(p_pr)
    return paragraph


def _build_module_element(
    document: Any,
    entry: ModuleEntry,
    sources: dict[str, Any],
    data: dict,
    *,
    east_asia: str,
    heading_half: int,
    body_half: int,
) -> tuple[Any, str]:
    """按模块类型抽取/填充一张独立表；band 文字使用动态编号/自定义标签。"""
    if entry.kind == "custom":
        element = copy.deepcopy(sources["analysis"])
        rows = element.findall(qn("w:tr"))
        for row in rows[2:]:
            element.remove(row)
        table = _table_from_element(document, element)
        _set_band_title(table, entry.title, east_asia=east_asia, heading_half=heading_half)
        _make_custom_body_row(element)
        _fill_cell(table.rows[1].cells[0], entry.body, east_asia=east_asia, size_half_pt=body_half)
        return element, "custom"

    key = entry.builtin or ""
    element = copy.deepcopy(sources[key])
    table = _table_from_element(document, element)
    _set_band_title(table, entry.title, east_asia=east_asia, heading_half=heading_half)

    if key == "basic":
        basic = data.get("basic") or {}
        _fill_cell(table.rows[1].cells[1], _text(basic.get("courseName")) or _text(data.get("title")), east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[1].cells[3], _text(basic.get("audience")), east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[2].cells[1], _text(basic.get("teachingTime")), east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[2].cells[3], _text(basic.get("location")), east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[3].cells[1], _text(basic.get("chapter")), east_asia=east_asia, size_half_pt=body_half)
    elif key == "analysis":
        analysis = data.get("analysis") or {}
        values = (
            _text(analysis.get("learning")),
            _text(analysis.get("textbook")),
            _text(analysis.get("content")),
            _text(analysis.get("ideological")),
        )
        for row, value in zip(table.rows[1:], values):
            _fill_cell(row.cells[1], value, east_asia=east_asia, size_half_pt=body_half)
    elif key == "objectives":
        knowledge, ability, ideological = _objectives_rows(data)
        _fill_cell(table.rows[1].cells[2], knowledge, east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[2].cells[2], ability, east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[3].cells[2], ideological, east_asia=east_asia, size_half_pt=body_half)
        key_points, difficulties = _key_points_pair(data)
        _fill_cell(table.rows[4].cells[1], key_points, east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(table.rows[5].cells[1], difficulties, east_asia=east_asia, size_half_pt=body_half)
    elif key == "strategy":
        strategy = data.get("strategy") or {}
        values = (
            _text(strategy.get("designThinking")) or _text(data.get("teachingDesign")),
            _text(strategy.get("teachingFlow")),
            _text(strategy.get("methods")),
        )
        for row, value in zip(table.rows[1:], values):
            _fill_cell(row.cells[1], value, east_asia=east_asia, size_half_pt=body_half)
    elif key == "process":
        _rebuild_process_rows(table, data, east_asia=east_asia, body_half=body_half)
    elif key == "evaluation":
        _fill_paragraphs_with_bold_headings(
            table.rows[1].cells[0], _evaluation_text(data), east_asia=east_asia, size_half_pt=body_half
        )
    elif key == "reflection":
        _fill_paragraphs_with_bold_headings(
            table.rows[1].cells[0], _reflection_text(data), east_asia=east_asia, size_half_pt=body_half
        )
    return element, MODULE_TABLE_ID[key]


def _rebuild_body(
    document: Any,
    visible: list[ModuleEntry],
    data: dict,
    sources: dict[str, Any],
    *,
    east_asia: str,
    heading_half: int,
    body_half: int,
    module_gap_px: float,
) -> tuple[list[Any], dict[Any, str]]:
    """删掉模板固定的四张正文表，按预览的模块顺序/分组重建正文。"""
    body = document.element.body
    title = _find_body_title(document)
    sect_pr = body.find(qn("w:sectPr"))
    if sect_pr is None:
        raise ExportAssemblyError("模板正文缺少节属性（sectPr）。")
    node = title._p.getnext()
    while node is not None and node is not sect_pr:
        next_node = node.getnext()
        body.remove(node)
        node = next_node

    segments: list[dict[str, Any]] = []
    for entry in visible:
        element, role = _build_module_element(
            document,
            entry,
            sources,
            data,
            east_asia=east_asia,
            heading_half=heading_half,
            body_half=body_half,
        )
        table_id = entry.table_id
        if entry.kind != "custom" and segments and segments[-1]["table_id"] == table_id:
            target = segments[-1]["element"]
            for row in list(element.findall(qn("w:tr"))):
                target.append(row)
            segments[-1]["entries"].append(entry)
            continue
        segments.append(
            {
                "table_id": table_id,
                "element": element,
                "role": role,
                "entries": [entry],
            }
        )

    anchor = title._p
    for index, segment in enumerate(segments):
        if index > 0:
            spacer = _spacer_paragraph(module_gap_px)
            anchor.addnext(spacer)
            anchor = spacer
        anchor.addnext(segment["element"])
        anchor = segment["element"]

    body_tables: list[Any] = []
    roles: dict[Any, str] = {}
    for segment in segments:
        table = _table_from_element(document, segment["element"])
        body_tables.append(table)
        roles[segment["element"]] = segment["role"]
    return body_tables, roles


def _scale_table_widths(table_xml: Any, content_twips: int) -> None:
    grid = table_xml.find(qn("w:tblGrid"))
    if grid is None:
        return
    columns = grid.findall(qn("w:gridCol"))
    widths = [int(column.get(qn("w:w")) or 0) for column in columns]
    total = sum(widths)
    if total <= 0:
        return
    factor = content_twips / total
    for column, width in zip(columns, widths):
        column.set(qn("w:w"), str(max(1, round(width * factor))))
    for cell in table_xml.iter(qn("w:tc")):
        tc_pr = cell.find(qn("w:tcPr"))
        if tc_pr is None:
            continue
        tc_w = tc_pr.find(qn("w:tcW"))
        if tc_w is None:
            continue
        if tc_w.get(qn("w:type")) not in (None, "dxa"):
            continue
        width = int(tc_w.get(qn("w:w")) or 0)
        if width <= 0:
            continue
        tc_w.set(qn("w:w"), str(max(1, round(width * factor))))
        tc_w.set(qn("w:type"), "dxa")


def _set_table_cell_margins(table_xml: Any, *, top: int, bottom: int, left: int, right: int) -> None:
    tbl_pr = table_xml.find(qn("w:tblPr"))
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        table_xml.insert(0, tbl_pr)
    margins = tbl_pr.find(qn("w:tblCellMar"))
    if margins is None:
        margins = OxmlElement("w:tblCellMar")
        look = tbl_pr.find(qn("w:tblLook"))
        if look is not None:
            look.addprevious(margins)
        else:
            tbl_pr.append(margins)
    for side, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(int(round(value))))
        node.set(qn("w:type"), "dxa")


def _set_cell_margins(cell: Any, *, top: int, bottom: int, left: int, right: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.find(qn("w:tcMar"))
    if margins is None:
        margins = OxmlElement("w:tcMar")
        anchor = None
        for tag in ("w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark"):
            anchor = tc_pr.find(qn(tag))
            if anchor is not None:
                break
        if anchor is not None:
            anchor.addprevious(margins)
        else:
            tc_pr.append(margins)
    for side, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(int(round(value))))
        node.set(qn("w:type"), "dxa")


def _apply_page_geometry(
    document: Any,
    style: dict,
    body_tables: list[Any],
    roles: dict[Any, str],
) -> None:
    """把 pageMargin/moduleGap 写进 docx：节页边距、表宽、单元格边距、表内 band 间距。"""
    metrics = _style_metrics(style)
    margin_px = metrics["page_margin"]
    margin_twips = round(margin_px * 15)
    module_gap_twips = round(metrics["module_gap"] * 15)
    footer_px = min(48.0, max(8.0, margin_px - 16))
    for section in document.sections:
        section.left_margin = Emu(round(margin_px * 9525))
        section.right_margin = Emu(round(margin_px * 9525))
        section.top_margin = Emu(round(margin_px * 9525))
        section.bottom_margin = Emu(round(margin_px * 9525))
        section.header_distance = Emu(round(footer_px * 9525))
        section.footer_distance = Emu(round(footer_px * 9525))
    content_twips = max(1000, PAGE_WIDTH_TWIPS - 2 * margin_twips)
    for table in body_tables:
        _scale_table_widths(table._tbl, content_twips)
        _set_table_cell_margins(table._tbl, top=0, bottom=0, left=108, right=108)
        if roles.get(table._tbl) == "custom":
            continue
        for row_index, row in enumerate(table.rows):
            if row_index == 0:
                continue
            if _SECTION_BAND.match(row.cells[0].text.strip()):
                _set_cell_margins(row.cells[0], top=module_gap_twips, bottom=0, left=108, right=108)


def build_document(payload: ExportPayload) -> bytes:
    """组装导出 docx（bytes）；组装后立即重开校验（verify_document）。

    正文不再固定按模板四张表输出：按前端 modules 的顺序/显隐/自定义位置重建；
    模板只提供每类模块的行样式、表格样式、边框、底纹与列宽。
    """
    if not BLANK_TEMPLATE.is_file():
        raise ExportAssemblyError(f"教案空白模板缺失：{BLANK_TEMPLATE}")
    data = payload.data
    east_asia = _font_family(payload.style)
    base_px, heading_px, label_px = _style_sizes(payload.style)
    metrics = _style_metrics(payload.style)
    body_half = _px_to_half_pt(base_px, 14)
    head_half = _px_to_half_pt(heading_px, 16)
    label_half = _px_to_half_pt(label_px, 12)
    visible = [entry for entry in _module_entries(payload.modules) if not entry.hidden]

    document = Document(str(BLANK_TEMPLATE))

    # ---- 第 1 页封面 ----
    _replace_paragraph_text(document.paragraphs[0], _text(data.get("title")) or "（课题名称）", east_asia=east_asia)
    cover = document.tables[0]
    basic = data.get("basic") or {}
    cover_values = [
        _text(basic.get("courseName")) or _text(data.get("title")),
        _text(basic.get("teacher")),
        _text(basic.get("audience")),
        _text(basic.get("hours")),
    ]
    for row, value in zip(cover.rows, cover_values):
        _fill_cell(row.cells[1], value, east_asia=east_asia, size_half_pt=body_half)

    # ---- 第 2 页目录：可见模块顺序 + 动态编号 + 预览页码 ----
    _rewrite_toc(document, payload, visible)

    # ---- 第 3 页起：正文标题 ----
    page3_title = _text(basic.get("courseName")) or _text(data.get("title")) or "（课程名称）"
    _replace_paragraph_text(_find_body_title(document), f"{page3_title}　教学设计", east_asia=east_asia)

    # ---- 抽取模板行样式，删除固定正文表，按预览布局重建 ----
    sources = _extract_sources(document)
    body_tables, roles = _rebuild_body(
        document,
        visible,
        data,
        sources,
        east_asia=east_asia,
        heading_half=head_half,
        body_half=body_half,
        module_gap_px=metrics["module_gap"],
    )

    # ---- 页面几何 + 字体/行距（预览与导出同一份 style）----
    _apply_page_geometry(document, payload.style, body_tables, roles)
    _apply_template_typography(
        document,
        style=payload.style,
        roles=roles,
        east_asia=east_asia,
        heading_half=head_half,
        label_half=label_half,
        body_half=body_half,
    )
    for para in document.paragraphs:
        if para.text.strip():
            for run in para.runs:
                _set_run_font(run, east_asia=east_asia)

    buffer = io.BytesIO()
    document.save(buffer)
    content = buffer.getvalue()
    verify_document(content, expected_body_tables=len(body_tables))
    return content


def _table_from_element(document: Any, element: Any) -> Any:
    """把表 XML 元素包回 python-docx Table 对象（用于单元格填充）。"""
    from docx.table import Table

    return Table(element, document)


def _find_body_title(document: Any) -> Any:
    """定位第 3 页正文页眉标题段（模板文本「（课程名称）　教学设计」）。"""
    for para in document.paragraphs:
        if "教学设计" in para.text and "教 学 设 计" not in para.text:
            return para
    raise ExportAssemblyError("模板正文标题段缺失。")


def verify_document(content: bytes, *, expected_body_tables: int | None = None) -> None:
    """导出后用 python-docx 重新打开断言结构（试运行校验；失败抛 ExportAssemblyError）。

    断言：字节 >0 且 PK 魔数、节数=2、第 2 节 footer 引用 PAGE 域、
    表数 = 1 张封面 + 动态正文表数、封面标题/目录页码/正文标题/封面表口径。
    正文表顺序由 modules 决定，这里不再假设 tables[1]=基本信息、tables[3]=目标。
    """
    if not content or content[:2] != b"PK":
        raise ExportAssemblyError("导出产物不是合法的 docx（PK 魔数缺失）。")
    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:
        raise ExportAssemblyError(f"导出产物无法重新打开：{exc}") from exc
    if len(document.sections) != 2:
        raise ExportAssemblyError(f"导出产物分节数异常：{len(document.sections)}（应为 2）。")
    footer_xml = document.sections[1].footer._element.xml
    if "PAGE" not in footer_xml:
        raise ExportAssemblyError("第 2 节页脚缺少 PAGE 域引用。")
    if expected_body_tables is not None:
        expected_tables = 1 + expected_body_tables
        if len(document.tables) != expected_tables:
            raise ExportAssemblyError(
                f"导出产物表数异常：{len(document.tables)}（应为 {expected_tables}：封面 + {expected_body_tables} 张正文表）。"
            )
    if not document.tables:
        raise ExportAssemblyError("导出产物缺少封面表。")
    if not document.paragraphs or not document.paragraphs[0].text.strip():
        raise ExportAssemblyError("封面标题为空。")
    toc_hit = any("\t" in para.text for para in document.paragraphs)
    if not toc_hit:
        raise ExportAssemblyError("目录缺少带页码的条目。")
    header_hit = any("教学设计" in para.text for para in document.paragraphs)
    if not header_hit:
        raise ExportAssemblyError("正文页眉标题缺失。")
    if len(document.tables) < 2:
        raise ExportAssemblyError("导出产物缺少正文表。")
    cover = document.tables[0]
    if "课程名称" not in cover.rows[0].cells[0].text:
        raise ExportAssemblyError("封面表口径异常（缺「课程名称」）。")


def artifact_filename(data: dict) -> str:
    """导出文件名：``{课题名}-教学设计.docx``（非法字符替换为 -）。"""
    title = _text(data.get("title")).strip() or "教案"
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "-", title).strip().strip(".")
    return f"{cleaned or '教案'}-教学设计.docx"


def artifact_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "ExportAssemblyError",
    "ExportPayload",
    "LESSON_EXPORT_MEDIA_TYPE",
    "artifact_filename",
    "build_document",
    "verify_document",
]
