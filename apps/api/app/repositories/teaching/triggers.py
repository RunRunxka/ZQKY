"""同事务「临时摘除 / 逐字恢复」触发器的公共设施（R10-BE 删除级联）。

迁移登记里的**不可变兜底触发器**（已确认成绩修订、已封存报告、已审核练习修订、
已确认原卷…）把"修订一经确认即不可改写"落到了数据库层。删除级联要在受控路径上
越过这些兜底：先例是 ``scores.delete_revision_in`` / ``analysis.delete_run_in``
（同事务 DROP → 删除 → 按登记原文恢复；DDL 可事务化，任一步失败整体回滚，触发器
随事务恢复；``BEGIN IMMEDIATE`` 下无并发写者可见窗口）。

本模块把那套做法抽成两件东西，供 R10-BE 的多处级联复用：

- :func:`suspend_triggers`：按名从 ``sqlite_master`` **读取原文**后摘除——不在代码里
  复制第二份 DDL，避免与迁移声明漂移；恢复用的就是库里的真实文本。
- :data:`CASCADE_DELETE_TRIGGERS`：删除级联需要摘除的触发器并集（不存在的名称被
  静默跳过，因此对老库/部分升级库同样安全）。

嵌套安全：已经被外层摘除的名称在内层查不到（``sqlite_master`` 反映本连接未提交的
DDL），内层恢复集合为空、不做任何事；最终由最外层统一恢复。调用方必须在同一个
写事务里使用，且让 ``finally`` 走到（``with`` 语义已保证）。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

#: 成绩链确认扫描册：确认后的修订/矩阵行平时不可增删改。
SCORE_CHAIN_TRIGGERS: tuple[str, ...] = (
    "immutable_score_revisions_delete",
    "immutable_score_revisions_update",
    "immutable_item_scores_delete",
)

#: 学情报告的冻结子表与身份行（封存后不可删除）。
ANALYSIS_FROZEN_TRIGGERS: tuple[str, ...] = (
    "analysis_no_delete",
    "freeze_analysis_participants_delete",
    "freeze_analysis_item_snapshots_delete",
    "freeze_analysis_student_results_delete",
    "freeze_analysis_class_results_delete",
    "freeze_analysis_evidence_delete",
    "immutable_analysis_teacher_notes_delete",
)

#: 练习连带历史彻底删除（含把转换生成的原卷修订的来源指针置空）。
#: 顺序 = 历史登记顺序（``paper_source_fixed`` 殿后）：同表多个 BEFORE 触发器
#: 以创建顺序触发，恢复后与摘除前逐字一致——``R10-FE`` 之前的行为因此不变。
PRACTICE_HISTORY_TRIGGERS: tuple[str, ...] = (
    "practice_revision_delete",
    "freeze_practice_selections_delete",
    "freeze_practice_items_delete",
    "freeze_practice_item_knowledge_delete",
    "immutable_practice_exports_delete",
    "immutable_export_artifacts_delete",
    "immutable_practice_conversions_delete",
    "immutable_practice_paper_item_mappings_delete",
    "immutable_paper_revisions_update",
    "paper_source_fixed",
)

#: 原卷修订链（已确认修订及其原文块/小题/知识点/处置问题）。
PAPER_REVISION_TRIGGERS: tuple[str, ...] = (
    "immutable_paper_revisions_delete",
    "immutable_paper_revisions_update",
    "freeze_paper_items_delete",
    "freeze_paper_item_knowledge_delete",
    "freeze_paper_source_blocks_delete",
    "freeze_paper_issues_delete",
)

#: 教案修订（把 ``analysis_run_id`` 来源指针置空时必须能写一次）。
LESSON_REVISION_TRIGGERS: tuple[str, ...] = ("lesson_plan_revisions_immutable_update",)

#: 删除级联的触发器并集：调用方一次摘除、末尾一次恢复（嵌套调用自动退化为空操作）。
CASCADE_DELETE_TRIGGERS: tuple[str, ...] = tuple(
    dict.fromkeys(
        SCORE_CHAIN_TRIGGERS
        + ANALYSIS_FROZEN_TRIGGERS
        + PRACTICE_HISTORY_TRIGGERS
        + PAPER_REVISION_TRIGGERS
        + LESSON_REVISION_TRIGGERS
    )
)


@contextmanager
def suspend_triggers(
    conn: sqlite3.Connection, names: Sequence[str]
) -> Iterator[tuple[tuple[str, str], ...]]:
    """在写事务内按名摘除触发器，退出时按原文逆序恢复。

    :param conn: 已 ``BEGIN IMMEDIATE`` 且已 ``PRAGMA defer_foreign_keys = ON`` 的连接。
    :param names: 触发器名（不存在/已被外层摘除的名称跳过）。
    :returns: 本次**实际**摘除的 ``(名称, sqlite_master 原文)`` 元组；调用方一般忽略。
    """
    saved: list[tuple[str, str]] = []
    for name in names:
        row = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (name,),
        ).fetchone()
        if row is None or not row["sql"]:
            continue
        conn.execute(f'DROP TRIGGER "{row["name"]}"')
        saved.append((row["name"], row["sql"]))
    try:
        yield tuple(saved)
    finally:
        # 按传入顺序恢复：多个 BEFORE 触发器同表触发时以创建顺序为准，
        # 各组常量因此按"历史登记顺序"排列，恢复后行为与摘除前逐字一致。
        for _name, statement in saved:
            conn.execute(statement)


__all__ = [
    "ANALYSIS_FROZEN_TRIGGERS",
    "CASCADE_DELETE_TRIGGERS",
    "LESSON_REVISION_TRIGGERS",
    "PAPER_REVISION_TRIGGERS",
    "PRACTICE_HISTORY_TRIGGERS",
    "SCORE_CHAIN_TRIGGERS",
    "suspend_triggers",
]
