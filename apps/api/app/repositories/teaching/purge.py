"""教学库「施测链」级联清除（R10-BE，2026-10-13 用户裁定）。

**成绩链保护策略（本模块的裁定与实现）**：施测是成绩链的**所有者**——
``assessment_participants``（参测人次，成绩/报告的证据锚点）→ ``score_imports``
（导入批次）→ ``score_revisions``（成绩修订）→ ``student_item_scores``（小题分）→
``analysis_runs``（学情报告）→ ``practice_sets``（派生练习）。因此：

- **删除施测 = 删除这条链**（唯一的显式销毁入口；不再有"只能归档"的挡路词）；
- 其它实体（班级/学生/试卷/报告/练习）的删除**永不静默销毁学生成绩**：
  能拆的引用置空、能级联的自身产物随行，剩下的按 409 逐项列出（见各服务）。

本模块只做 SQL，守卫（教案冻结血缘 → 409）由调用方先行判定；调用方保证在
``catalog.write_transaction()`` 的同一写事务内执行（``PRAGMA defer_foreign_keys=ON``
让复合外键在提交时统一校验，行序不再敏感；触发器由 ``suspend_triggers`` 统一摘除）。
"""

from __future__ import annotations

import sqlite3

from app.repositories.teaching.analysis import AnalysisRepository
from app.repositories.teaching.practices import PracticeRepository
from app.repositories.teaching.triggers import (
    CASCADE_DELETE_TRIGGERS,
    suspend_triggers,
)

#: 教案冻结血缘引用键（删施测链会破坏已应用 AI 教案血缘 → 调用方 409 逐项列出）。
FROZEN_LESSON_KEYS = ("lessonGenerationInputs", "lessonProposals")


def frozen_lesson_counts_in(
    conn: sqlite3.Connection, assessment_id: str
) -> dict[str, int]:
    """该施测链上的教案冻结血缘计数（报告 → 生成输入/候选）。

    两处 ``analysis_run_id`` 都是 **NOT NULL** 且行受 ``lesson_*_immutable_*``
    触发器保护：删除报告/施测会让已应用 AI 教案的来源变成悬挂引用，因此非零即
    拒绝（由调用方按 ``ASSESSMENT_IN_USE`` / ``ANALYSIS_RUN_IN_USE`` 逐项列出）。
    """
    row = conn.execute(
        "SELECT "
        " (SELECT COUNT(*) FROM lesson_generation_inputs WHERE analysis_run_id IN "
        "  (SELECT id FROM analysis_runs WHERE assessment_id = ?)) AS lessonGenerationInputs, "
        " (SELECT COUNT(*) FROM lesson_ai_proposals WHERE analysis_run_id IN "
        "  (SELECT id FROM analysis_runs WHERE assessment_id = ?)) AS lessonProposals",
        (assessment_id, assessment_id),
    ).fetchone()
    return {key: int(row[key]) for key in FROZEN_LESSON_KEYS}


def report_ids_in(conn: sqlite3.Connection, assessment_id: str) -> list[str]:
    """该施测派生的学情报告 id（按创建顺序）。"""
    rows = conn.execute(
        "SELECT id FROM analysis_runs WHERE assessment_id = ? ORDER BY created_at, id",
        (assessment_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def purge_assessment_chain_in(
    conn: sqlite3.Connection, *, catalog: object, assessment_id: str, owner_id: str
) -> dict[str, int]:
    """级联清除施测及其自有成绩链（前置：调用方已判定教案冻结血缘为空）。

    步骤（同一写事务，触发器统一摘除、末尾恢复）：

    1. **报告链**：逐份报告先连带历史删除其派生练习（``PracticeRepository``）、
       置空教案修订来源指针，再删报告自身六张冻结子表（``AnalysisRepository``）；
    2. **成绩链**：清 ``active_score_revision_id`` 指针 → 小题分 → 修正审计 →
       导入行 → 导入批次 → 成绩修订（先把 ``source_import_id``/``base_revision_id``
       置 NULL，打断两表之间的互指外键）；
    3. **练习回流**：映射 → 成绩模板导出工件 → 导出 → 转换；
    4. **范围与人次**：参测人次 → 参测范围 → 施测行。

    **保留不动**：``file_assets``（受管资产 blob 不物理删除）、``workflow_jobs``
    （任务历史）、原卷与修订（上游文档由原卷自己的删除入口负责）、班级/学生/教案。

    返回级联计数（回执用）：``analysisRuns``/``practiceSets``/``scoreRevisions``/
    ``scoreImports``/``itemScores``/``participants``/``practiceConversions``/``exports``。
    """
    analyses = AnalysisRepository()
    practices = PracticeRepository(catalog)
    report_ids = report_ids_in(conn, assessment_id)

    with suspend_triggers(conn, CASCADE_DELETE_TRIGGERS):
        practice_sets = 0
        unlinked_lessons = 0
        for run_id in report_ids:
            practice_ids = analyses.practice_set_ids_in(conn, run_id)
            for set_id in practice_ids:
                practices.delete_set_with_history_in(conn, set_id)
            practice_sets += len(practice_ids)
            unlinked_lessons += int(analyses.unlink_lesson_revisions_in(conn, run_id))
            analyses.delete_run_in(conn, run_id, owner_id)

        conn.execute(
            "UPDATE assessments SET active_score_revision_id = NULL WHERE id = ?",
            (assessment_id,),
        )
        item_scores = conn.execute(
            "DELETE FROM student_item_scores WHERE assessment_id = ?", (assessment_id,)
        ).rowcount
        conn.execute(
            "DELETE FROM score_revision_corrections WHERE revision_id IN "
            "(SELECT id FROM score_revisions WHERE assessment_id = ?)",
            (assessment_id,),
        )
        conn.execute(
            "UPDATE score_imports SET base_score_revision_id = NULL WHERE assessment_id = ?",
            (assessment_id,),
        )
        conn.execute(
            "UPDATE score_revisions SET source_import_id = NULL, base_revision_id = NULL "
            "WHERE assessment_id = ?",
            (assessment_id,),
        )
        conn.execute(
            "DELETE FROM score_import_rows WHERE import_id IN "
            "(SELECT id FROM score_imports WHERE assessment_id = ?)",
            (assessment_id,),
        )
        score_imports = conn.execute(
            "DELETE FROM score_imports WHERE assessment_id = ?", (assessment_id,)
        ).rowcount
        score_revisions = conn.execute(
            "DELETE FROM score_revisions WHERE assessment_id = ?", (assessment_id,)
        ).rowcount

        conn.execute(
            "DELETE FROM practice_paper_item_mappings WHERE conversion_id IN "
            "(SELECT id FROM practice_conversions WHERE assessment_id = ?)",
            (assessment_id,),
        )
        exports = conn.execute(
            "DELETE FROM export_artifacts WHERE export_id IN "
            "(SELECT id FROM practice_exports WHERE assessment_id = ?)",
            (assessment_id,),
        ).rowcount
        conn.execute(
            "DELETE FROM practice_exports WHERE assessment_id = ?", (assessment_id,)
        )
        conversions = conn.execute(
            "DELETE FROM practice_conversions WHERE assessment_id = ?", (assessment_id,)
        ).rowcount

        participants = conn.execute(
            "DELETE FROM assessment_participants WHERE assessment_id = ?",
            (assessment_id,),
        ).rowcount
        conn.execute(
            "DELETE FROM assessment_classes WHERE assessment_id = ?", (assessment_id,)
        )
        conn.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))

    return {
        "analysisRuns": len(report_ids),
        "practiceSets": practice_sets,
        "unlinkedLessonRevisions": unlinked_lessons,
        "scoreRevisions": int(score_revisions),
        "scoreImports": int(score_imports),
        "itemScores": int(item_scores),
        "participants": int(participants),
        "practiceConversions": int(conversions),
        "exports": int(exports),
    }


__all__ = [
    "FROZEN_LESSON_KEYS",
    "frozen_lesson_counts_in",
    "purge_assessment_chain_in",
    "report_ids_in",
]
