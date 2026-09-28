"""教材分类字典：学段 / 年级 / 学科 / 版本。

来源：只读原始教材目录 ``F:\\人教版教材\\markdown`` 的组织结构（人教A版、人教B版高中数学
与高中各科电子课本，共 58 册）。字典是后端固定常量：前后端共用同一套 id，
页面显示标签一律取自这里，不在界面层猜造中文名。

本字典只声明"当前有真实材料"的学段与学科；后续扩展由总控在共享契约层决定，
实现者不在此处自行新增未落地的分类。
"""

from __future__ import annotations

from app.schemas.textbook import EditionView, GradeView, StageView, SubjectView, TextbookTaxonomy

STAGE_SENIOR = "senior"

STAGES: tuple[StageView, ...] = (StageView(id=STAGE_SENIOR, label="高中"),)

GRADES: tuple[GradeView, ...] = (
    GradeView(id="senior-1", label="高一", stageId=STAGE_SENIOR),
    GradeView(id="senior-2", label="高二", stageId=STAGE_SENIOR),
    GradeView(id="senior-3", label="高三", stageId=STAGE_SENIOR),
)

SUBJECTS: tuple[SubjectView, ...] = (
    SubjectView(id="chinese", label="语文"),
    SubjectView(id="math", label="数学"),
    SubjectView(id="english", label="英语"),
    SubjectView(id="physics", label="物理"),
    SubjectView(id="chemistry", label="化学"),
    SubjectView(id="biology", label="生物"),
    SubjectView(id="history", label="历史"),
    SubjectView(id="geography", label="地理"),
    SubjectView(id="politics", label="思想政治"),
)

EDITIONS: tuple[EditionView, ...] = (
    EditionView(id="renjiao-a", label="人教A版"),
    EditionView(id="renjiao-b", label="人教B版"),
    EditionView(id="renjiao", label="人教版"),
)

TAXONOMY = TextbookTaxonomy(
    stages=list(STAGES),
    grades=list(GRADES),
    subjects=list(SUBJECTS),
    editions=list(EDITIONS),
)

GRADE_IDS = frozenset(grade.id for grade in GRADES)
SUBJECT_IDS = frozenset(subject.id for subject in SUBJECTS)
EDITION_IDS = frozenset(edition.id for edition in EDITIONS)
STAGE_IDS = frozenset(stage.id for stage in STAGES)
