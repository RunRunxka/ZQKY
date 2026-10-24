"""R13 导出组装：模板视觉 + 正文跟随预览的模块布局 + 段落/行距/难点修复。

结构断言覆盖：两节/footer PAGE、按 modules 顺序/显隐/custom 位置重建正文、
目录与正文同一套动态编号、模板空段复用、教学重点/难点分格、模板字号/行距/页边距。
"""
import io
import re

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.services.lesson_plans.export import (
    BUILTIN_ORDER,
    ExportAssemblyError,
    ExportPayload,
    artifact_filename,
    build_document,
    verify_document,
)

_BAND_RE = re.compile(r"^[一二三四五六七八九十]+、")


def full_data() -> dict:
    return {
        "title": "高频谐振功率放大器", "totalLessons": "2", "currentLessonNo": "1", "lessonTypes": ["new"],
        "otherTypeText": "", "coreCompetencies": "知识：了解功放原理\n能力：能分析电路\n思政：培养工程伦理",
        "keyPoints": "教学重点：谐振功放结构\n教学难点：负载特性", "teachingDesign": "板书设计",
        "process": [], "exercises": "课本 P12 1-3", "reflection": "反思正文",
        "basic": {"courseName": "通信电子线路", "teacher": "王老师", "audience": "本科二年级",
                  "hours": "2", "teachingTime": "周一", "location": "教室301", "chapter": "第四章 功放"},
        "analysis": {"learning": "学情", "textbook": "教材", "content": "内容", "ideological": "思政"},
        "strategy": {"designThinking": "设计思路", "teachingFlow": "教学流程", "methods": "教学手段"},
        "evaluation": {"afterClassTest": "课后测试", "homework": "作业"},
        "processV2": [
            {"id": "p1", "phase": "warmup", "phaseLabel": "课前热身", "title": "观察",
             "teacherActivity": "教师演示", "studentActivity": "学生观察", "intent": "引入"},
            {"id": "p2", "phase": "introduction", "phaseLabel": "第一阶段　课程引入", "title": "提问",
             "teacherActivity": "教师提问", "studentActivity": "学生回答", "intent": "激趣"},
        ],
    }


#: 与前端 DEFAULT_LESSON_STYLE 一致的模板口径（14pt / 15pt / 24pt exact / 72px / 8px / 0）。
STYLE = {
    "fontId": "puhuiti",
    "baseSize": 18.67,
    "headingSize": 20,
    "labelSize": 18.67,
    "lineHeight": 1.714,
    "pageMargin": 72,
    "moduleGap": 8,
    "paragraphGap": 0,
}


def builtin_modules() -> list[dict]:
    return [
        {"id": key, "kind": "builtin", "builtinId": key, "label": label}
        for key, label in (
            ("basic", "基本信息"),
            ("analysis", "教学分析"),
            ("objectives", "教学目标"),
            ("strategy", "教学策略"),
            ("process", "教学过程"),
            ("evaluation", "评价反馈"),
            ("reflection", "教学反思"),
        )
    ]


def custom_module(module_id: str = "custom-1", label: str = "安全须知", body: str = "实验安全第一") -> dict:
    return {"id": module_id, "kind": "custom", "label": label, "body": body}


def _payload(data=None, modules=None, style=None, section_pages=None) -> ExportPayload:
    if modules is None:
        modules = [*builtin_modules(), custom_module()]
    body = {
        "data": full_data() if data is None else data,
        "style": STYLE if style is None else style,
        "modules": modules,
    }
    if section_pages is not None:
        body["sectionPages"] = section_pages
    return ExportPayload.parse(body)


def _row_with(table, needle: str):
    for row in table.rows:
        if needle in row.cells[0].text:
            return row
    raise AssertionError(f"找不到包含「{needle}」的行")


def _row_after(table, needle: str):
    for index, row in enumerate(table.rows):
        if needle in row.cells[0].text:
            return table.rows[index + 1]
    raise AssertionError(f"找不到「{needle}」之后的行")


def _table_with(document, needle: str):
    """在正文表里按单元格文本定位（不依赖固定表序号）。"""
    for table in document.tables[1:]:
        for row in table.rows:
            if any(needle in cell.text for cell in row.cells):
                return table
    raise AssertionError(f"找不到包含「{needle}」的正文表")


def _module_sequence(document) -> list[str]:
    """正文模块顺序：每张表首行（内置 band / 自定义标签）+ 同表内后续 section band。"""
    sequence: list[str] = []
    for table in document.tables[1:]:
        for row_index, row in enumerate(table.rows):
            text = row.cells[0].text.strip()
            if row_index == 0 or _BAND_RE.match(text):
                sequence.append(text)
    return sequence


def _toc_sequence(document) -> list[str]:
    return [p.text.split("\t")[0] for p in document.paragraphs if "\t" in p.text]


def test_export_preserves_two_sections_footer_page_and_tables():
    content = build_document(_payload(modules=[]))
    assert content[:2] == b"PK" and len(content) > 0
    document = Document(io.BytesIO(content))
    assert len(document.sections) == 2
    # 第 1 节无页脚；第 2 节 footer 引用 PAGE 域 + pgNumType start=1
    assert document.sections[0].footer.is_linked_to_previous
    assert "PAGE" in document.sections[1].footer._element.xml
    sect = document.sections[1]._sectPr
    pg_num = sect.find(qn("w:pgNumType"))
    assert pg_num is not None and pg_num.get(qn("w:start")) == "1"
    # 封面表 + 5 张正文表（基本信息/教学分析/目标+策略/教学过程/评价+反思）
    assert len(document.tables) == 6


def test_export_fills_cover_toc_and_body_tables():
    payload = _payload(modules=[])
    content = build_document(payload)
    document = Document(io.BytesIO(content))
    # 封面：标题 + 封面表四行
    assert document.paragraphs[0].text == "高频谐振功率放大器"
    cover = document.tables[0]
    assert cover.rows[0].cells[1].text == "通信电子线路"
    assert cover.rows[1].cells[1].text == "王老师"
    assert cover.rows[2].cells[1].text == "本科二年级"
    assert cover.rows[3].cells[1].text == "2"
    # 目录：七条（含页码列），页码按正文从 1 起
    toc = [p.text for p in document.paragraphs if p.text.startswith(("一、", "七、"))]
    assert len(toc) == 2 and "\t" in toc[0]
    assert toc[0].endswith("\t1")
    # 正文标题（第 3 页起）
    body_titles = [p.text for p in document.paragraphs if "　教学设计" in p.text]
    assert body_titles == ["通信电子线路　教学设计"]
    # 基本信息表
    basic = _table_with(document, "课程名称")
    assert basic.rows[1].cells[1].text == "通信电子线路"
    assert basic.rows[3].cells[1].text == "第四章 功放"
    # 目标三行 vMerge（知识/能力/思政）
    objectives = _table_with(document, "知识目标")
    assert objectives.rows[1].cells[2].text == "了解功放原理"
    assert objectives.rows[2].cells[2].text == "能分析电路"
    assert objectives.rows[3].cells[2].text == "培养工程伦理"
    # 过程：阶段跨列行 + 内容行
    process = _table_with(document, "教学环节")
    assert process.rows[3].cells[0].text == "课前热身"
    assert process.rows[4].cells[1].text == "教师演示"
    # 评价/反思入位（默认相邻，同一张表）
    evaluation_table = _table_with(document, "六、评价反馈")
    evaluation_row = _row_after(evaluation_table, "六、评价反馈")
    reflection_row = _row_after(evaluation_table, "七、教学反思")
    assert "课后测试" in evaluation_row.cells[0].text
    assert "反思正文" in reflection_row.cells[0].text


def test_export_keeps_template_evaluation_and_reflection_subitems():
    """六、评价反馈保留模板四项；（三）（四）没有数据也保留标题。七、教学反思保留三项。"""
    content = build_document(_payload(modules=[], data={
        **full_data(),
        "reflection": "（一）目标达成度分析\n达成较好\n（二）教学特色与可供借鉴之处\n案例教学\n（三）教学后记\n继续改进",
    }))
    evaluation_table = _table_with(Document(io.BytesIO(content)), "六、评价反馈")
    evaluation = _row_after(evaluation_table, "六、评价反馈").cells[0].text
    for heading in ("（一）学生课后测试情况", "（二）学生课后作业情况", "（三）学生课后调查反馈", "（四）督导专家课后反馈"):
        assert heading in evaluation
    assert "课后测试" in evaluation
    assert "作业" in evaluation
    assert "课本 P12 1-3" in evaluation
    reflection = _row_after(evaluation_table, "七、教学反思").cells[0].text
    for heading in ("（一）目标达成度分析", "（二）教学特色与可供借鉴之处", "（三）教学后记"):
        assert heading in reflection
    assert "达成较好" in reflection
    assert "案例教学" in reflection
    assert "继续改进" in reflection


def test_export_uses_preview_section_pages_for_toc():
    content = build_document(
        _payload(modules=[], section_pages={"basic": 1, "analysis": 2, "objectives": 2, "strategy": 3,
                                            "process": 4, "evaluation": 6, "reflection": 7})
    )
    document = Document(io.BytesIO(content))
    toc = {p.text.split("\t")[0]: p.text.rsplit("\t", 1)[-1] for p in document.paragraphs if "\t" in p.text and p.text.startswith(("一、", "二、", "三、", "四、", "五、", "六、", "七、"))}
    assert toc["一、基本信息"] == "1"
    assert toc["七、教学反思"] == "7"


def test_export_rebuilds_process_rows_beyond_template_capacity():
    """模板只有 5 阶段 / 6 内容行；更多环节按行克隆，不丢行。"""
    rows = []
    for index in range(1, 6):
        rows.append({"id": f"p{index}", "phase": "exploration", "phaseLabel": f"第{index}阶段",
                     "title": f"环节{index}", "teacherActivity": f"教师{index}",
                     "studentActivity": f"学生{index}", "intent": f"意图{index}"})
    content = build_document(_payload(modules=[], data={**full_data(), "processV2": rows}))
    document = Document(io.BytesIO(content))
    process = _table_with(document, "教学环节")
    texts = "\n".join(row.cells[0].text for row in process.rows)
    for index in range(1, 6):
        assert f"第{index}阶段" in texts
        assert f"环节{index}" in texts
    # 评价/反思现在是独立的表（预览 tableId 口径），不在过程表里
    assert _row_with(_table_with(document, "六、评价反馈"), "六、评价反馈") is not None


def test_export_custom_module_appends_table_in_module_order():
    content = build_document(_payload())
    document = Document(io.BytesIO(content))
    # 封面 + 5 张正文表 + 自定义
    assert len(document.tables) == 7
    custom = document.tables[-1]
    assert custom.rows[0].cells[0].text == "安全须知"
    assert custom.rows[1].cells[0].text == "实验安全第一"
    # 目录含自定义条目
    toc_texts = [p.text for p in document.paragraphs if p.text.startswith("安全须知")]
    assert len(toc_texts) == 1


def test_export_reuses_template_paragraphs_and_splits_key_points():
    """多行目标复用模板空段（不留空行）；教学重点/难点分别入格且不重复标签前缀。"""
    data = {
        **full_data(),
        "coreCompetencies": "知识：1. 甲\n2. 乙\n3. 丙\n能力：能分析\n思政：伦理",
        "keyPoints": "教学重点：重点一\n教学难点：难点一\n难点二",
    }
    document = Document(io.BytesIO(build_document(_payload(modules=[], data=data))))
    objectives = _table_with(document, "知识目标")
    knowledge = [p.text for p in objectives.rows[1].cells[2].paragraphs]
    assert knowledge == ["1. 甲", "2. 乙", "3. 丙"]
    assert not any(text == "" for text in knowledge)
    assert objectives.rows[4].cells[1].text == "重点一"
    assert objectives.rows[5].cells[1].text == "难点一\n难点二"


def test_export_matches_preview_typography_and_geometry():
    """模板默认值：正文 14pt / 行距 24pt exact / 段距 0 / 页边距 72px / 表宽内容宽。"""
    document = Document(io.BytesIO(build_document(_payload(modules=[]))))
    objectives = _table_with(document, "知识目标")
    paragraph = objectives.rows[1].cells[2].paragraphs[0]
    spacing = paragraph._p.pPr.find(qn("w:spacing"))
    assert spacing.get(qn("w:line")) == "480"
    assert spacing.get(qn("w:lineRule")) == "exact"
    assert spacing.get(qn("w:after")) == "0"

    section = document.sections[1]
    assert int(section.left_margin) // 635 == 1080
    assert int(section.top_margin) // 635 == 1080

    basic = _table_with(document, "课程名称")
    grid = basic._tbl.find(qn("w:tblGrid"))
    total = sum(int(column.get(qn("w:w")) or 0) for column in grid.findall(qn("w:gridCol")))
    assert abs(total - (11906 - 2 * 1080)) <= 2

    # 表间空段按 moduleGap=8px（120tw）输出
    spacers = 0
    for paragraph in document.element.body.findall(qn("w:p")):
        if "".join(paragraph.itertext()).strip():
            continue
        p_pr = paragraph.find(qn("w:pPr"))
        spacing = p_pr.find(qn("w:spacing")) if p_pr is not None else None
        if spacing is not None and spacing.get(qn("w:line")) == "120":
            spacers += 1
    assert spacers == 4

    # 评价反馈空值不再产生空段落
    evaluation = _row_after(_table_with(document, "六、评价反馈"), "六、评价反馈")
    assert not any(paragraph.text == "" for paragraph in evaluation.cells[0].paragraphs)


def test_export_follows_module_order_and_visibility():
    modules = [
        {"id": "process", "kind": "builtin", "builtinId": "process", "label": "教学过程"},
        {"id": "basic", "kind": "builtin", "builtinId": "basic", "label": "基本信息"},
        {"id": "analysis", "kind": "builtin", "builtinId": "analysis", "label": "教学分析", "hidden": True},
        {"id": "objectives", "kind": "builtin", "builtinId": "objectives", "label": "教学目标"},
        {"id": "strategy", "kind": "builtin", "builtinId": "strategy", "label": "教学策略"},
        {"id": "evaluation", "kind": "builtin", "builtinId": "evaluation", "label": "评价反馈"},
        {"id": "reflection", "kind": "builtin", "builtinId": "reflection", "label": "教学反思"},
    ]
    document = Document(io.BytesIO(build_document(_payload(modules=modules))))
    expected = [
        "一、教学过程",
        "二、基本信息",
        "三、教学目标",
        "四、教学策略",
        "五、评价反馈",
        "六、教学反思",
    ]
    assert _module_sequence(document) == expected
    assert _toc_sequence(document) == expected
    assert len(document.tables) == 5  # 封面 + 4 张正文表（过程/基本信息/目标+策略/评价+反思）
    assert not any("教学分析" in cell.text for table in document.tables for row in table.rows for cell in row.cells)


def test_export_custom_module_in_middle_breaks_table_grouping():
    modules = [
        {"id": "basic", "kind": "builtin", "builtinId": "basic", "label": "基本信息"},
        custom_module(),
        {"id": "analysis", "kind": "builtin", "builtinId": "analysis", "label": "教学分析"},
        {"id": "objectives", "kind": "builtin", "builtinId": "objectives", "label": "教学目标"},
        {"id": "strategy", "kind": "builtin", "builtinId": "strategy", "label": "教学策略"},
        {"id": "process", "kind": "builtin", "builtinId": "process", "label": "教学过程"},
        {"id": "evaluation", "kind": "builtin", "builtinId": "evaluation", "label": "评价反馈"},
        {"id": "reflection", "kind": "builtin", "builtinId": "reflection", "label": "教学反思"},
    ]
    document = Document(io.BytesIO(build_document(_payload(modules=modules))))
    expected = [
        "一、基本信息",
        "安全须知",
        "二、教学分析",
        "三、教学目标",
        "四、教学策略",
        "五、教学过程",
        "六、评价反馈",
        "七、教学反思",
    ]
    assert _module_sequence(document) == expected
    assert _toc_sequence(document) == expected
    # 封面 + basic + custom + analysis + 目标/策略 + 过程 + 评价/反思
    assert len(document.tables) == 7
    assert document.tables[2].rows[0].cells[0].text == "安全须知"
    assert document.tables[2].rows[1].cells[0].text == "实验安全第一"


def test_export_hidden_custom_module_is_omitted():
    modules = [*builtin_modules(), {**custom_module(), "hidden": True}]
    document = Document(io.BytesIO(build_document(_payload(modules=modules))))
    assert not any("安全须知" in cell.text for table in document.tables for row in table.rows for cell in row.cells)
    assert not any("安全须知" in paragraph.text for paragraph in document.paragraphs)


def test_export_writes_selected_font_family():
    content = build_document(_payload(modules=[], style={**STYLE, "fontId": "source-han-serif"}))
    fonts = set(re.findall(r'w:eastAsia="([^"]+)"', Document(io.BytesIO(content)).element.body.xml))
    assert "思源宋体" in fonts


def test_export_rejects_broken_payload_and_keeps_no_half_artifact():
    with pytest.raises(ExportAssemblyError):
        ExportPayload.parse({"data": None})
    with pytest.raises(ExportAssemblyError):
        ExportPayload.parse({"data": {"no": "data"}})


def test_verify_document_rejects_truncated_bytes():
    content = build_document(_payload(modules=[]))
    with pytest.raises(ExportAssemblyError):
        verify_document(content[:100])
    with pytest.raises(ExportAssemblyError):
        verify_document(b"not-a-docx")


def test_repeated_export_produces_new_artifact_rows(tmp_path):
    """重复导出生成新产物（同内容 blob 幂等、资产登记新行、artifactId 新）。"""
    import asyncio

    from tests.lesson_plans_support import LessonScene

    async def scenario():
        scene = await LessonScene.create(tmp_path)
        try:
            lesson = scene.be.create_lesson(scene.create_request())
            body = {"data": lesson["currentRevision"]["data"], "style": STYLE, "modules": []}
            first = scene.be.export_lesson(lesson["lessonPlanId"], body)
            second = scene.be.export_lesson(lesson["lessonPlanId"], body)
            assert first["artifact"]["artifactId"] != second["artifact"]["artifactId"]
            assert first["artifact"]["byteSize"] == second["artifact"]["byteSize"]
            return scene, first, second
        except BaseException:
            await scene.close()
            raise

    scene, first, second = asyncio.run(scenario())
    try:
        # R6 产物服务按资产 id 下载（分析报告/教案产物同一分派分支）
        from app.services.export_artifacts import ExportArtifactsService

        service = ExportArtifactsService(scene.catalog, assets=scene.be.assets, file_assets=scene.be.file_assets)
        view, data = service.download(first["artifact"]["artifactId"])
        assert data[:2] == b"PK" and len(data) == first["artifact"]["byteSize"]
        assert view.filename == artifact_filename(full_data()) or view.filename.endswith("教学设计.docx")
    finally:
        asyncio.run(scene.close())


def test_stale_archived_lesson_export_is_rejected(tmp_path):
    """B3 归档移除：残留 archived_at 行（模拟旧库）导出被只读兜底拒绝。"""
    import asyncio

    from app.core.exceptions import AppError
    from tests.lesson_plans_support import LessonScene

    async def scenario():
        scene = await LessonScene.create(tmp_path)
        try:
            lesson = scene.be.create_lesson(scene.create_request())
            with scene.catalog.write_transaction() as conn:
                conn.execute(
                    "UPDATE lesson_plans SET archived_at='2026-10-03T09:00:00Z' WHERE id=?",
                    (lesson["lessonPlanId"],),
                )
            scene.be.export_lesson(lesson["lessonPlanId"], {"data": lesson["currentRevision"]["data"], "style": {}, "modules": []})
        finally:
            await scene.close()

    try:
        asyncio.run(scenario())
        raised = False
    except AppError as exc:
        raised = exc.code == "LESSON_INVALID"
    assert raised


def test_builtin_order_constant_matches_frontend():
    assert BUILTIN_ORDER == ("basic", "analysis", "objectives", "strategy", "process", "evaluation", "reflection")
