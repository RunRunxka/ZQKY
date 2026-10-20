"""归一化脚本：把旧库残留的归档数据归一到「删除即删除」新语义（B3，2026-10-20）。

背景（全局移除归档功能）：归档/恢复端点已全部移除，题库 ``DELETE /questions/{id}``
改为物理删除。升级前创建的库可能残留归档行，公开列表不再有 archived 过滤入口，
必须用本脚本一次性归一：

- 知识点库 ``knowledge.sqlite3``：``subjects.status`` / ``knowledge_points.status``
  的 ``archived`` → ``active``；
- 教学库 ``teaching.sqlite3``：``classes.status`` 的 ``archived`` → ``active``；
  ``papers.status`` 的 ``archived`` → ``active``；``assessments.state`` 的
  ``archived`` → ``closed``；``analysis_runs.archived_at`` → ``NULL``；
  ``lesson_plans.archived_at`` → ``NULL``；``practice_sets.status`` 的
  ``archived`` → ``active``；
- 题库 ``question-bank.sqlite3``：``questions.status`` 的 ``archived`` 行走**物理
  删除**（与 ``DELETE /questions/{id}`` 同一删除体：修订、知识点关联（同事务摘除
  不可变触发器并逐字恢复）、来源、内容指纹一并删除；任务历史与导入批次保留）；
- **不恢复** ``students.status='archived'``：这是 R10-BE 以来「有历史成绩已移除」
  的内部状态，名单导入会按既有语义自动恢复，本脚本不碰。

用法（后端环境内）::

    cd apps/api
    uv run python -m scripts.normalize_archives            # dry-run（默认），只打印
    uv run python -m scripts.normalize_archives --apply    # 实际写入

数据根经 ``Settings``（``ZQKY_DATA_DIR`` 等环境变量）解析，不硬编码 live 路径；
可用 ``--data-dir`` 显式覆盖（归一化副本/测试数据用）。脚本可重复执行：无残留时
dry-run 打印零计数、apply 不写任何行。幂等性由「按当前状态归一」的 UPDATE/DELETE
语义保证（重复执行第二次全部计数为 0）。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 脚本以 `python -m scripts.normalize_archives` 从 apps/api 运行：把后端包放进 path
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.core.config import Settings  # noqa: E402
from app.core.sqlite import connect, now_iso  # noqa: E402

TEACHING_DB = "teaching.sqlite3"
KNOWLEDGE_DB = "knowledge.sqlite3"
QUESTION_BANK_DB = "question-bank.sqlite3"


@dataclass
class DbReport:
    """单个库的归一化计数（dry-run 与 apply 共用同一形状）。"""

    name: str
    counts: dict[str, int] = field(default_factory=dict)
    #: archived 题目/班级等实体的标识（ID + 标题，供人工核对）
    samples: dict[str, list[str]] = field(default_factory=dict)


def _sample(rows: list) -> list[str]:
    """行 → 「id｜标题」样本（最多 20 条，避免刷屏）。"""
    return [f"{row[0]}｜{row[1]}" if len(row) > 1 else str(row[0]) for row in rows[:20]]


# --------------------------------------------------------------------- 知识点库


def _knowledge_point_rows(conn) -> list:
    return conn.execute(
        "SELECT p.id, COALESCE(r.name, p.code) FROM knowledge_points p "
        "LEFT JOIN knowledge_point_revisions r ON r.id = p.current_revision_id "
        "WHERE p.status = 'archived' ORDER BY p.id"
    ).fetchall()


def normalize_knowledge(path: Path, *, apply: bool) -> DbReport:
    """知识点库：subjects / knowledge_points 的 archived → active（修订不动）。"""
    report = DbReport(name=str(path))
    if not path.is_file():
        report.counts["skipped"] = 0
        return report
    conn = connect(path)
    try:
        subjects = conn.execute(
            "SELECT id, name FROM subjects WHERE status = 'archived' ORDER BY id"
        ).fetchall()
        points = _knowledge_point_rows(conn)
        report.counts["subjectsArchived"] = len(subjects)
        report.counts["knowledgePointsArchived"] = len(points)
        report.samples["knowledgePoints"] = _sample(points)
        if not apply:
            return report
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE subjects SET status = 'active' WHERE status = 'archived'"
            )
            conn.execute(
                "UPDATE knowledge_points SET status = 'active' WHERE status = 'archived'"
            )
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return report


# --------------------------------------------------------------------- 教学库


def normalize_teaching(path: Path, *, apply: bool) -> DbReport:
    """教学库：班级/原卷 → active，施测 archived → closed，报告/教案归档时间清空。

    ``students.status='archived'``（内部"有历史成绩已移除"）**不**恢复。
    """
    report = DbReport(name=str(path))
    if not path.is_file():
        report.counts["skipped"] = 0
        return report
    conn = connect(path)
    try:
        present = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        def count(sql: str) -> int:
            return int(conn.execute(sql).fetchone()[0])

        if "classes" in present:
            report.counts["classesArchived"] = count(
                "SELECT COUNT(*) FROM classes WHERE status = 'archived'"
            )
            rows = conn.execute(
                "SELECT id, name FROM classes WHERE status = 'archived' ORDER BY id"
            ).fetchall()
            report.samples["classes"] = _sample(rows)
        if "papers" in present:
            report.counts["papersArchived"] = count(
                "SELECT COUNT(*) FROM papers WHERE status = 'archived'"
            )
            rows = conn.execute(
                "SELECT id, title FROM papers WHERE status = 'archived' ORDER BY id"
            ).fetchall()
            report.samples["papers"] = _sample(rows)
        if "assessments" in present:
            report.counts["assessmentsArchived"] = count(
                "SELECT COUNT(*) FROM assessments WHERE state = 'archived'"
            )
            rows = conn.execute(
                "SELECT id, title FROM assessments WHERE state = 'archived' ORDER BY id"
            ).fetchall()
            report.samples["assessments"] = _sample(rows)
        if "analysis_runs" in present:
            report.counts["analysisRunsArchived"] = count(
                "SELECT COUNT(*) FROM analysis_runs WHERE archived_at IS NOT NULL"
            )
        if "lesson_plans" in present:
            report.counts["lessonPlansArchived"] = count(
                "SELECT COUNT(*) FROM lesson_plans WHERE archived_at IS NOT NULL"
            )
            rows = conn.execute(
                "SELECT l.id, COALESCE(json_extract(r.data_json, '$.title'), l.id) "
                "FROM lesson_plans l LEFT JOIN lesson_plan_revisions r "
                "ON r.id = l.current_revision_id "
                "WHERE l.archived_at IS NOT NULL ORDER BY l.id"
            ).fetchall()
            report.samples["lessonPlans"] = _sample(rows)
        if "practice_sets" in present:
            report.counts["practiceSetsArchived"] = count(
                "SELECT COUNT(*) FROM practice_sets WHERE status = 'archived'"
            )
            rows = conn.execute(
                "SELECT id, title FROM practice_sets WHERE status = 'archived' ORDER BY id"
            ).fetchall()
            report.samples["practiceSets"] = _sample(rows)
        if not apply:
            return report
        conn.execute("BEGIN IMMEDIATE")
        try:
            if "classes" in present:
                conn.execute(
                    "UPDATE classes SET status = 'active' WHERE status = 'archived'"
                )
            if "papers" in present:
                conn.execute(
                    "UPDATE papers SET status = 'active' WHERE status = 'archived'"
                )
            if "assessments" in present:
                conn.execute(
                    "UPDATE assessments SET state = 'closed' WHERE state = 'archived'"
                )
            if "analysis_runs" in present:
                conn.execute(
                    "UPDATE analysis_runs SET archived_at = NULL "
                    "WHERE archived_at IS NOT NULL"
                )
            if "lesson_plans" in present:
                conn.execute(
                    "UPDATE lesson_plans SET archived_at = NULL, updated_at = ? "
                    "WHERE archived_at IS NOT NULL",
                    (now_iso(),),
                )
            if "practice_sets" in present:
                conn.execute(
                    "UPDATE practice_sets SET status = 'active' WHERE status = 'archived'"
                )
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return report


# --------------------------------------------------------------------- 题库


def _archived_question_rows(conn) -> list:
    return conn.execute(
        "SELECT q.id, COALESCE(json_extract(r.metadata_json, '$.subjectId'), q.id) "
        "FROM questions q LEFT JOIN question_revisions r ON r.id = q.current_revision_id "
        "WHERE q.status = 'archived' ORDER BY q.id"
    ).fetchall()


def _delete_question_rows(conn, question_id: str) -> dict[str, int]:
    """单题物理删除体（与 ``QuestionBankCatalog.delete_question_in`` 同一 FK 顺序）。

    与线上服务共享同一套顺序与触发器摘除/恢复语义：``question_content_fingerprints``
    → ``question_knowledge_links``（同事务摘除不可变触发器并按原文逐字恢复）→
    ``question_revisions`` → ``question_sources`` → ``questions``；指向本题的草稿
    并入指针置空。任务/批次/草稿历史保留。
    """
    revision_ids = [
        str(row["id"])
        for row in conn.execute(
            "SELECT id FROM question_revisions WHERE question_id = ?", (question_id,)
        ).fetchall()
    ]
    placeholders = ", ".join("?" for _ in revision_ids) or "NULL"
    counts: dict[str, int] = {}
    counts["clearedDraftDuplicates"] = conn.execute(
        "UPDATE question_drafts SET duplicate_of_question_id = NULL "
        "WHERE duplicate_of_question_id = ?",
        (question_id,),
    ).rowcount
    saved: list[tuple[str, str]] = []
    for name in (
        "immutable_question_knowledge_links_delete",
        "immutable_question_knowledge_links_update",
    ):
        trigger = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND name = ?",
            (name,),
        ).fetchone()
        if trigger is not None and trigger["sql"]:
            conn.execute(f'DROP TRIGGER "{trigger["name"]}"')
            saved.append((str(trigger["name"]), str(trigger["sql"])))
    try:
        counts["contentFingerprints"] = conn.execute(
            "DELETE FROM question_content_fingerprints "
            f"WHERE question_revision_id IN ({placeholders})",
            revision_ids,
        ).rowcount
        counts["knowledgeLinks"] = conn.execute(
            "DELETE FROM question_knowledge_links "
            f"WHERE question_revision_id IN ({placeholders})",
            revision_ids,
        ).rowcount
        counts["revisions"] = conn.execute(
            "DELETE FROM question_revisions WHERE question_id = ?", (question_id,)
        ).rowcount
        counts["sources"] = conn.execute(
            "DELETE FROM question_sources WHERE question_id = ?", (question_id,)
        ).rowcount
        counts["questions"] = conn.execute(
            "DELETE FROM questions WHERE id = ?", (question_id,)
        ).rowcount
    finally:
        for _name, statement in saved:
            conn.execute(statement)
    return counts


def normalize_question_bank(path: Path, *, apply: bool) -> DbReport:
    """题库：archived 题目物理删除（修订/关联/来源/指纹一并删；任务历史保留）。"""
    report = DbReport(name=str(path))
    if not path.is_file():
        report.counts["skipped"] = 0
        return report
    conn = connect(path)
    try:
        present = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "questions" not in present:
            report.counts["skipped"] = 0
            return report
        rows = _archived_question_rows(conn)
        report.counts["questionsArchived"] = len(rows)
        report.samples["archivedQuestions"] = _sample(rows)
        if not apply:
            return report
        conn.execute("PRAGMA defer_foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for row in rows:
                counts = _delete_question_rows(conn, str(row[0]))
                for key, value in counts.items():
                    report.counts[key] = report.counts.get(key, 0) + int(value)
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return report


# --------------------------------------------------------------------- 入口


def _print_report(report: DbReport) -> None:
    print(f"== {report.name}")
    if not report.counts:
        print("   （无归档数据，不需要归一化）")
    for key, value in report.counts.items():
        print(f"   {key}: {value}")
    for key, samples in report.samples.items():
        if samples:
            print(f"   [{key}]")
            for sample in samples:
                print(f"     - {sample}")


def normalize_all(settings: Settings, *, apply: bool) -> list[DbReport]:
    """按库执行归一化；dry-run 只统计不写入（题库 archived 计数同口径打印）。"""
    reports = [
        normalize_knowledge(settings.knowledge_root / KNOWLEDGE_DB, apply=apply),
        normalize_teaching(settings.teaching_root / TEACHING_DB, apply=apply),
    ]
    if not apply:
        # dry-run 也要能看到题库 archived 的量：打开只统计，不进删除事务。
        path = settings.question_bank_root / QUESTION_BANK_DB
        report = DbReport(name=str(path))
        if path.is_file():
            conn = connect(path)
            try:
                rows = _archived_question_rows(conn)
            finally:
                conn.close()
            report.counts["questionsArchived"] = len(rows)
            report.samples["archivedQuestions"] = _sample(rows)
        else:
            report.counts["skipped"] = 0
        reports.append(report)
    else:
        reports.append(
            normalize_question_bank(
                settings.question_bank_root / QUESTION_BANK_DB, apply=True
            )
        )
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="归一化旧库残留的归档数据（dry-run 默认；--apply 才写入）。"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行归一化写入；缺省只打印计划（dry-run）。",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="显式数据根（缺省读 ZQKY_DATA_DIR / 项目默认 .local-data）。",
    )
    args = parser.parse_args(argv)

    if args.data_dir:
        settings = Settings(
            host="127.0.0.1",
            port=8000,
            allowed_origins=frozenset(),
            env="development",
            data_dir=Path(args.data_dir),
            credentials_file=None,
        )
    else:
        settings = Settings.from_env()
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"归一化归档数据（{mode}）· 数据根：{settings.data_dir}")
    reports = normalize_all(settings, apply=args.apply)
    for report in reports:
        _print_report(report)
    total = sum(
        value
        for report in reports
        for key, value in report.counts.items()
        if key not in ("skipped",) and not key.startswith("cleared")
    )
    print(f"完成：{mode}；归一化动作合计 {total} 项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
