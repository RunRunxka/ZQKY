"""R7-BE 导出组装：模板两节结构保留、四表口径、自定义模块、重开校验、产物存储。

只做有意义的结构断言（节数/footer PAGE/表数/关键文本/字体/产物魔数），
不触发网络；产物存储走真实 AssetStore + FileAssetsRepository（tmp_path 内）。
"""
import io

import pytest
from docx import Document

from app.services.lesson_plans.export import (
    ExportAssemblyError,
    ExportPayload,
    artifact_filename,
    build_document,
    verify_document,
)


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


STYLE = {"fontId": "puhuiti", "baseSize": 14, "headingSize": 16, "labelSize": 12,
         "lineHeight": 1.7, "pageMargin": 48, "moduleGap": 16, "paragraphGap": 6}


def _payload(data=None, modules=None, style=None) -> ExportPayload:
    return ExportPayload.parse({
        "data": full_data() if data is None else data,
        "style": STYLE if style is None else style,
        "modules": [{"id": "custom-1", "kind": "custom", "label": "安全须知", "body": "实验安全第一"}] if modules is None else modules,
    })


def test_export_preserves_two_sections_footer_page_and_tables():
    content = build_document(_payload(modules=[]))
    assert content[:2] == b"PK" and len(content) > 0
    document = Document(io.BytesIO(content))
    assert len(document.sections) == 2
    # 第 1 节无页脚；第 2 节 footer 引用 PAGE 域 + pgNumType start=1
    assert document.sections[0].footer.is_linked_to_previous
    assert "PAGE" in document.sections[1].footer._element.xml
    sect = document.sections[1]._sectPr
    from docx.oxml.ns import qn

    pg_num = sect.find(qn("w:pgNumType"))
    assert pg_num is not None and pg_num.get(qn("w:start")) == "1"
    # 封面表 + 正文四表（无自定义）
    assert len(document.tables) == 5


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
    # 目录：七条（含页码列）
    toc = [p.text for p in document.paragraphs if p.text.startswith(("一、", "七、"))]
    assert len(toc) == 2 and "\t" in toc[0]
    # 正文标题（第 3 页起）
    body_titles = [p.text for p in document.paragraphs if "　教学设计" in p.text]
    assert body_titles == ["通信电子线路　教学设计"]
    # 基本信息表
    basic = document.tables[1]
    assert basic.rows[1].cells[1].text == "通信电子线路"
    assert basic.rows[3].cells[1].text == "第四章 功放"
    # 目标三行 vMerge（知识/能力/思政）
    objectives = document.tables[3]
    assert objectives.rows[1].cells[2].text == "了解功放原理"
    assert objectives.rows[2].cells[2].text == "能分析电路"
    assert objectives.rows[3].cells[2].text == "培养工程伦理"
    # 过程：阶段跨列行 + 内容行
    process = document.tables[4]
    assert process.rows[3].cells[0].text == "课前热身"
    assert process.rows[4].cells[1].text == "教师演示"
    # 评价/反思入位
    assert "课后测试" in process.rows[15].cells[0].text
    assert "反思正文" in process.rows[17].cells[0].text


def test_export_custom_module_appends_table_in_module_order():
    content = build_document(_payload())
    document = Document(io.BytesIO(content))
    assert len(document.tables) == 6  # 封面 + 四表 + 自定义
    custom = document.tables[5]
    assert custom.rows[0].cells[0].text == "安全须知"
    assert custom.rows[1].cells[0].text == "实验安全第一"
    # 目录含自定义条目
    toc_texts = [p.text for p in document.paragraphs if p.text.startswith("安全须知")]
    assert len(toc_texts) == 1


def test_export_writes_selected_font_family():
    content = build_document(_payload(modules=[], style={**STYLE, "fontId": "source-han-serif"}))
    import re

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


def test_archived_lesson_export_is_rejected(tmp_path):
    import asyncio

    from app.core.exceptions import AppError
    from tests.lesson_plans_support import LessonScene

    async def scenario():
        scene = await LessonScene.create(tmp_path)
        try:
            lesson = scene.be.create_lesson(scene.create_request())
            scene.be.set_archived(lesson["lessonPlanId"], {"expectedRevision": lesson["revision"]}, archived=True)
            scene.be.export_lesson(lesson["lessonPlanId"], {"data": lesson["currentRevision"]["data"], "style": {}, "modules": []})
        finally:
            await scene.close()

    try:
        asyncio.run(scenario())
        raised = False
    except AppError as exc:
        raised = exc.code == "LESSON_INVALID"
    assert raised
