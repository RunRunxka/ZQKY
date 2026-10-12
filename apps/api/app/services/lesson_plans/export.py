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
2. 目录（第 2 页）：按 ``modules``（可见模块）重写条目行（样式沿用模板：
   仿宋 sz30、行距 exact 680、右对齐点线制表位）；**页码列为估算值**
   （正文按内容行数近似估算，docx 分页由 Word 排版引擎决定，python-docx
   无法精确分页；样张比对显示估算与实际可偏差 ±1 页，见交付说明）；
3. 第 3 页起正文：页眉标题「（课程名称）　教学设计」→「{courseName}　教学设计」；
   各内置模块按模板四表口径填充：
   - 一、基本信息（4 列表：课程名称/授课对象/授课时间/授课地点/教学章节）；
   - 二、教学分析（2 列：学情/教材/内容/思政）；
   - 三、教学目标（3 列 vMerge：教学目标跨 3 行 + 知识/能力/思政；重点/难点）；
   - 四、教学策略（在目标表尾部 3 行：设计思路/教学流程/教学手段——模板里
     策略与目标同表）；
   - 五、教学过程（4 列：环节/教师活动/学生活动/设计意图，阶段跨列行）；
   - 六、评价反馈（跨列表：课后测试/作业）；
   - 七、教学反思（跨列表：目标达成/特色/改进）；
   - **自定义模块**：克隆模板表样式新增「标题跨列 + 正文」表，按 ``modules``
     顺序插入到正文表序列末尾；
4. 字体：正文/标题 run 的 ``w:eastAsia``/``w:ascii`` 按 ``style.fontFamily``
   的首个字体族写入（未装字体由 Word 回退，可接受；见交付说明）。
   模板默认「黑体标题/宋体正文」；``fontId`` 映射到中文俗名字体名。

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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

#: 模板位置（仓库内只读资源；样板 ``lesson-plan-filled-sample.docx`` 供人工比对）。
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "resources" / "lesson_templates"
BLANK_TEMPLATE = TEMPLATE_DIR / "lesson-plan-blank.docx"

#: 导出 docx 的 media type（与学情报告产物一致）。
LESSON_EXPORT_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

#: 内置模块键 → 模板表序号（正文表 1..4 承载七个内置模块；策略与目标同表）。
#: table 0 是封面表；正文表：1=基本信息 2=教学分析 3=目标+策略 4=过程+评价+反思。
BUILTIN_TABLE_OF: dict[str, int] = {
    "basic": 1,
    "analysis": 2,
    "objectives": 3,
    "strategy": 3,
    "process": 4,
    "evaluation": 4,
    "reflection": 4,
}

#: 内置模块默认顺序与中文序号（与前端 BUILTIN_MODULES 一致）。
BUILTIN_ORDER: tuple[str, ...] = ("basic", "analysis", "objectives", "strategy", "process", "evaluation", "reflection")
BUILTIN_NO: dict[str, str] = {
    "basic": "一", "analysis": "二", "objectives": "三", "strategy": "四",
    "process": "五", "evaluation": "六", "reflection": "七",
}
BUILTIN_LABEL: dict[str, str] = {
    "basic": "基本信息", "analysis": "教学分析", "objectives": "教学目标", "strategy": "教学策略",
    "process": "教学过程", "evaluation": "评价反馈", "reflection": "教学反思",
}

#: fontId → docx eastAsia 字体名（前端字体族的首选中文名；未装字体由 Word 回退）。
FONT_EAST_ASIA: dict[str, str] = {
    "puhuiti": "阿里巴巴普惠体",
    "misans": "MiSans",
    "noto-sans-sc": "思源黑体",
    "source-han-serif": "思源宋体",
}

#: 目录行样式参数（沿用模板：仿宋 sz30 半点单位、行距 exact 680 twips、点线制表位）。
TOC_TAB_POS = 9298
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
        return cls(data=body["data"], style=style, modules=modules)


#: 教案正文可识别的键（至少命中一个才算教案文档；与前端 isLessonDataShaped 同口径）。
_LESSON_DATA_KEYS = ("title", "basic", "analysis", "strategy", "evaluation", "processV2",
                     "coreCompetencies", "keyPoints", "teachingDesign", "reflection")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


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


def _px_to_twips_line(px: float | int | None, *, base_size_px: float) -> int:
    """前端行高（倍数）× 基础字号 → 行距 twips（exact）。"""
    try:
        multiple = float(px)
    except (TypeError, ValueError):
        multiple = 1.7
    multiple = min(2.0, max(1.0, multiple))
    return max(240, min(2000, int(base_size_px * 0.75 * multiple * 20)))


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


def _fill_cell(cell: Any, text: str, *, east_asia: str, size_half_pt: int, bold: bool = False) -> None:
    """把单元格第一段写为文本（多行按 \\n 拆段）；清掉其余段，保留样式段距。"""
    paragraphs = cell.paragraphs
    lines = [line for line in (text or "").split("\n")] or [""]
    first = paragraphs[0]
    for para in paragraphs[len(lines):]:
        para._p.getparent().remove(para._p)
    for index, line in enumerate(lines):
        para = first if index == 0 else cell.add_paragraph()
        # 继承原段距：清空 runs 后重建
        for run in list(para.runs):
            run._element.getparent().remove(run._element)
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


def _visible_builtin_ids(modules: list[dict]) -> list[str]:
    """按请求顺序取可见内置模块（缺省补齐，保持前端顺序）。"""
    seen: list[str] = []
    for entry in modules:
        if entry.get("kind") != "builtin":
            continue
        key = entry.get("builtinId") or entry.get("id")
        if key in BUILTIN_ORDER and key not in seen and entry.get("hidden") is not True:
            seen.append(key)
    for key in BUILTIN_ORDER:
        if key not in seen:
            seen.append(key)
    return seen


def _visible_custom_modules(modules: list[dict]) -> list[dict]:
    return [entry for entry in modules if entry.get("kind") == "custom" and entry.get("hidden") is not True]


def _estimate_page_starts(payload: ExportPayload, visible: list[str], custom: list[dict]) -> dict[str, int]:
    """目录页码估算：按每模块内容行数累加（≈12 行/页，向上取整）。

    **近似口径**：docx 实际分页由 Word 排版引擎决定（行距/表格跨页/字体内置
    度量都有影响），python-docx 无法精确计算分页；目录页码以内容行数近似，
    样张量级偏差 ±1 页。交付说明中已注明，如需精确可在 Word 中更新域。
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
    rows_of["evaluation"] = 2 + len(_text(data.get("exercises")).split("\n")) + len(_text(evaluation.get("afterClassTest")).split("\n"))
    rows_of["reflection"] = 2 + len(_text(data.get("reflection")).split("\n"))
    starts: dict[str, int] = {}
    page, used = 3, 0  # 正文从第 3 页起（pgNumType 显示 1，但目录按文档页序号写）
    for key in visible:
        starts[key] = page
        used += rows_of.get(key, 2)
        while used >= _ESTIMATED_ROWS_PER_PAGE:
            page += 1
            used -= _ESTIMATED_ROWS_PER_PAGE
    for entry in custom:
        starts[str(entry.get("id"))] = page
        used += 2 + len(_text(entry.get("body")).split("\n"))
        while used >= _ESTIMATED_ROWS_PER_PAGE:
            page += 1
            used -= _ESTIMATED_ROWS_PER_PAGE
    return starts


def _rewrite_toc(document: Any, payload: ExportPayload, visible: list[str], custom: list[dict]) -> None:
    """按当前模块清单重写目录条目（样式沿用模板：仿宋 sz30、行距 exact、点线制表位）。

    模板目录行固定七条（一、基本信息 ~ 七、教学反思）。组装策略：
    - 内置模块条目**按请求顺序重写进既有七行**（缺省补齐后恰为七条；请求里
      内置模块总是齐全——前端保证，这里再补齐一次）；
    - 自定义模块条目多于七条时，克隆最后一行目录段追加。
    """
    east_asia = _font_family(payload.style)
    base_size = payload.style.get("baseSize") or 14
    toc_size = max(TOC_FONT_SIZE_HALF_PT, _px_to_half_pt(base_size, 14))
    starts = _estimate_page_starts(payload, visible, custom)
    titles: list[str] = [f"{BUILTIN_NO[key]}、{BUILTIN_LABEL[key]}" for key in visible]
    for entry in custom:
        titles.append(_text(entry.get("label")) or "自定义模块")
    pages: list[int] = [starts.get(key, 1) for key in visible] + [
        starts.get(str(entry.get("id")), 1) for entry in custom
    ]
    # 定位模板目录行：从「一、基本信息」开始连续的、以中文序号开头的段落。
    paragraphs = document.paragraphs
    toc_paras: list[Any] = []
    collecting = False
    for para in paragraphs:
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
    # 自定义条目 > 0 时克隆最后一行补足
    template_toc_p = toc_paras[-1]._p
    while len(toc_paras) < len(titles):
        clone = copy.deepcopy(template_toc_p)
        template_toc_p.addnext(clone)
        template_toc_p = clone
        toc_paras.append(_para_of(document, clone))
    if len(toc_paras) > len(titles):
        # 内置最多 7 条，模板行 7 行：不会超；防御性处理——多余行清空文本
        for para in toc_paras[len(titles):]:
            for run in list(para.runs):
                run._element.getparent().remove(run._element)
        toc_paras = toc_paras[: len(titles)]
    for para, title, page in zip(toc_paras, titles, pages):
        p_pr = para._p.get_or_add_pPr()
        tabs = p_pr.find(qn("w:tabs"))
        if tabs is None:
            tabs = p_pr.makeelement(qn("w:tabs"), {})
            p_pr.insert(0, tabs)
        if not tabs.findall(qn("w:tab")):
            tab = tabs.makeelement(qn("w:tab"), {})
            tab.set(qn("w:pos"), str(TOC_TAB_POS))
            tab.set(qn("w:val"), "right")
            tab.set(qn("w:leader"), "dot")
            tabs.append(tab)
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
            # 页码列：制表位（点线）+ 估算页码（近似口径见 _estimate_page_starts）
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


def _key_points_pair(data: dict) -> tuple[str, str]:
    """keyPoints 字段 → 教学重点/难点两行（与前端 readKeyPoints 同口径的宽容切分）。"""
    text = _text(data.get("keyPoints"))
    key_points: list[str] = []
    difficulties: list[str] = []
    current: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*教学?重、?难点", line) or line.startswith("难点"):
            current = difficulties
        elif re.match(r"^\s*(?:[#>*\-–—•·]+\s*)*(?:\d+\s*[.、)）]?\s*)?(?:【|\[|（|\()?\s*教学?重点", line) or line.startswith("重点"):
            current = key_points
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


def _process_rows(data: dict) -> list[tuple[str, str, str, str]]:
    """教学过程行：阶段跨列行（label, "", "", ""）与内容行（title, teacher, student, intent）。"""
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
    result: list[tuple[str, str, str, str]] = []
    current_phase: str | None = None
    for item in items:
        label = _phase_label_of(item)
        if label and label != current_phase:
            result.append((label, "", "", ""))
            current_phase = label
        result.append((_text(item.get("title")), _text(item.get("teacherActivity")),
                       _text(item.get("studentActivity")), _text(item.get("intent"))))
    return result


def _apply_font_to_table(table: Any, *, east_asia: str, size_half_pt: int, skip_cells: set[Any] | None = None) -> None:
    """整表 run 字体统一（标题行黑体语义按模板保留加粗，但族改为所选字体）。"""
    skip_cells = skip_cells or set()
    for row in table.rows:
        seen: set[Any] = set()
        for cell in row.cells:
            if cell._tc in seen or cell._tc in skip_cells:
                continue
            seen.add(cell._tc)
            for para in cell.paragraphs:
                for run in para.runs:
                    _set_run_font(run, east_asia=east_asia, size_half_pt=size_half_pt)


def build_document(payload: ExportPayload) -> bytes:
    """组装导出 docx（bytes）；组装后立即重开校验（verify_document）。"""
    if not BLANK_TEMPLATE.is_file():
        raise ExportAssemblyError(f"教案空白模板缺失：{BLANK_TEMPLATE}")
    data = payload.data
    east_asia = _font_family(payload.style)
    base_size = payload.style.get("baseSize") or 14
    heading_size = payload.style.get("headingSize") or 16
    body_half = _px_to_half_pt(base_size, 14)
    head_half = _px_to_half_pt(heading_size, 16)
    visible = _visible_builtin_ids(payload.modules)
    custom = _visible_custom_modules(payload.modules)

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

    # ---- 第 2 页目录 ----
    _rewrite_toc(document, payload, visible, custom)

    # ---- 第 3 页起：页眉标题 ----
    page3_title = _text(basic.get("courseName")) or _text(data.get("title")) or "（课程名称）"
    _replace_paragraph_text(document.paragraphs[-1] if False else _find_body_title(document), f"{page3_title}　教学设计", east_asia=east_asia)

    # ---- 正文表 ----
    basic_table = document.tables[1]
    analysis_table = document.tables[2]
    objectives_table = document.tables[3]
    process_table = document.tables[4]

    # 一、基本信息（4 列表）
    _fill_cell(basic_table.rows[1].cells[1], _text(basic.get("courseName")) or _text(data.get("title")), east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(basic_table.rows[1].cells[3], _text(basic.get("audience")), east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(basic_table.rows[2].cells[1], _text(basic.get("teachingTime")), east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(basic_table.rows[2].cells[3], _text(basic.get("location")), east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(basic_table.rows[3].cells[1], _text(basic.get("chapter")), east_asia=east_asia, size_half_pt=body_half)

    # 二、教学分析
    analysis = data.get("analysis") or {}
    analysis_values = (
        _text(analysis.get("learning")), _text(analysis.get("textbook")),
        _text(analysis.get("content")), _text(analysis.get("ideological")),
    )
    for row, value in zip(analysis_table.rows[1:], analysis_values):
        _fill_cell(row.cells[1], value, east_asia=east_asia, size_half_pt=body_half)

    # 三、教学目标（vMerge 三行）+ 重点/难点 + 四、教学策略（同表尾部三行）
    knowledge, ability, ideological = _objectives_rows(data)
    _fill_cell(objectives_table.rows[1].cells[2], knowledge, east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(objectives_table.rows[2].cells[2], ability, east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(objectives_table.rows[3].cells[2], ideological, east_asia=east_asia, size_half_pt=body_half)
    key_points, difficulties = _key_points_pair(data)
    _fill_cell(objectives_table.rows[4].cells[1], key_points, east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(objectives_table.rows[5].cells[1], difficulties, east_asia=east_asia, size_half_pt=body_half)
    strategy = data.get("strategy") or {}
    strategy_values = (
        _text(strategy.get("designThinking")) or _text(data.get("teachingDesign")),
        _text(strategy.get("teachingFlow")),
        _text(strategy.get("methods")),
    )
    for row, value in zip(objectives_table.rows[7:], strategy_values):
        _fill_cell(row.cells[1], value, east_asia=east_asia, size_half_pt=body_half)

    # 五、教学过程 + 六、评价反馈 + 七、教学反思（同表）
    process_rows = _process_rows(data)
    # 模板骨架行：4/6/8/10/12 是内容行，3/5/7/9/11 是阶段行；13 是追加内容行。
    # 组装策略：重写 13 行骨架为「阶段行/内容行」序列，不足补行、多余清空。
    template_rows = process_table.rows
    skeleton_content = [4, 6, 8, 10, 12, 13]
    skeleton_stage = [3, 5, 7, 9, 11]
    stage_iter = (row for row in process_rows if not row[1] and not row[2] and not row[3])
    content_iter = (row for row in process_rows if row[1] or row[2] or row[3])
    for index in skeleton_stage:
        if index >= len(template_rows):
            break
        row = template_rows[index]
        try:
            stage = next(stage_iter)
        except StopIteration:
            _fill_cell(row.cells[0], "", east_asia=east_asia, size_half_pt=body_half)
            continue
        _fill_cell(row.cells[0], stage[0], east_asia=east_asia, size_half_pt=body_half)
    for index in skeleton_content:
        if index >= len(template_rows):
            break
        row = template_rows[index]
        try:
            content = next(content_iter)
        except StopIteration:
            for cell in {c._tc: c for c in row.cells}.values():
                _fill_cell(cell, "", east_asia=east_asia, size_half_pt=body_half)
            continue
        _fill_cell(row.cells[0], content[0], east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(row.cells[1], content[1], east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(row.cells[2], content[2], east_asia=east_asia, size_half_pt=body_half)
        _fill_cell(row.cells[3], content[3], east_asia=east_asia, size_half_pt=body_half)
    evaluation = data.get("evaluation") or {}
    evaluation_text = "\n".join(
        part for part in (
            f"（一）学生课后测试情况\n{_text(evaluation.get('afterClassTest'))}" if _text(evaluation.get("afterClassTest")) else "",
            f"（二）学生课后作业情况\n{_text(evaluation.get('homework')) or _text(data.get('exercises'))}" if (_text(evaluation.get("homework")) or _text(data.get("exercises"))) else "",
        ) if part
    )
    _fill_cell(template_rows[15].cells[0], evaluation_text or "（一）学生课后测试情况\n（二）学生课后作业情况", east_asia=east_asia, size_half_pt=body_half)
    _fill_cell(template_rows[17].cells[0], _text(data.get("reflection")), east_asia=east_asia, size_half_pt=body_half)

    # ---- 自定义模块：克隆「标题跨列 + 正文」表（样式沿用模板 TableGrid），插到正文末尾 ----
    for entry in custom:
        label = _text(entry.get("label")) or "自定义模块"
        body_text = _text(entry.get("body"))
        new_tbl = copy.deepcopy(analysis_table._tbl)  # 2 列表：标题行 + 标签行 + 正文
        # 标题行改为跨列标题
        header_tc = new_tbl.findall(qn("w:tr"))[0].findall(qn("w:tc"))[0]
        texts = header_tc.findall(".//" + qn("w:t"))
        if texts:
            texts[0].text = label
            for extra in texts[1:]:
                extra.text = ""
        # 第二行改为「正文」单格（删除第二格、第一格改跨列）
        body_tr = new_tbl.findall(qn("w:tr"))[1]
        tcs = body_tr.findall(qn("w:tc"))
        if len(tcs) >= 2:
            for extra in tcs[1:]:
                body_tr.remove(extra)
            first = tcs[0]
            tc_pr = first.find(qn("w:tcPr"))
            if tc_pr is not None:
                grid_span = tc_pr.find(qn("w:gridSpan"))
                if grid_span is None:
                    grid_span = tc_pr.makeelement(qn("w:gridSpan"), {})
                    tc_pr.append(grid_span)
                grid_span.set(qn("w:val"), "2")
                # 宽度拉满
                tc_w = tc_pr.find(qn("w:tcW"))
                if tc_w is not None:
                    tc_w.set(qn("w:w"), "9751")
        new_table = _table_from_element(document, new_tbl)
        _fill_cell(new_table.rows[1].cells[0], body_text, east_asia=east_asia, size_half_pt=body_half)
        document.element.body.append(new_tbl)

    # ---- 字体统一（封面/正文表；目录已单独设置）----
    for table in document.tables:
        _apply_font_to_table(table, east_asia=east_asia, size_half_pt=body_half)
    for para in document.paragraphs:
        if para.text.strip():
            for run in para.runs:
                _set_run_font(run, east_asia=east_asia)

    buffer = io.BytesIO()
    document.save(buffer)
    content = buffer.getvalue()
    verify_document(content, expected_custom=len(custom))
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


def verify_document(content: bytes, *, expected_custom: int = 0) -> None:
    """导出后用 python-docx 重新打开断言结构（试运行校验；失败抛 ExportAssemblyError）。

    断言：字节 >0 且 PK 魔数、节数=2、第 2 节 footer 引用 PAGE 域、
    表数=模板四表+自定义数、关键文本入位（封面标题/目录首条/基本信息表头）。
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
    expected_tables = 5 + expected_custom  # 封面表 + 正文四表 + 自定义
    if len(document.tables) != expected_tables:
        raise ExportAssemblyError(f"导出产物表数异常：{len(document.tables)}（应为 {expected_tables}）。")
    if not document.paragraphs or not document.paragraphs[0].text.strip():
        raise ExportAssemblyError("封面标题为空。")
    toc_hit = any("一、基本信息" in para.text for para in document.paragraphs)
    if not toc_hit:
        raise ExportAssemblyError("目录缺少「一、基本信息」条目。")
    header_hit = any("教学设计" in para.text for para in document.paragraphs)
    if not header_hit:
        raise ExportAssemblyError("正文页眉标题缺失。")
    if "课程名称" not in document.tables[1].rows[1].cells[0].text:
        raise ExportAssemblyError("基本信息表口径异常（缺「课程名称」）。")


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
