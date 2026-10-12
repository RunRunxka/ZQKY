"""只读成绩矩阵分页（TEACHING-LOOP B3 / T60）。

契约形状（``ScoreMatrixPage``）：``items`` 是**不分页**的固定计分叶（矩阵列集合），
``rows`` 按参测人次分页；``totalUnits`` **只在该人次全 recorded 时非空**（有
missing/absent/exempt 一律 null，不用 0 代替）；``missingParticipantIds`` /
``missingCellCount`` / ``absentClassIds`` 与确认预览**同口径**（同一份
``student_item_scores`` 统计），不随后来新增的参测人次变化（修订自己的快照是权威）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.contracts.scores import (
    ScoreCellValue,
    ScoreMatrixPage,
    ScoreMatrixParticipant,
    ScoreMatrixRow,
    ScoreParticipantSnapshot,
    ScoreRevisionView,
)
from app.repositories.teaching.scores import MatrixStats, ScoreRevisionRecord


def build_matrix_page(
    revision: ScoreRevisionRecord,
    *,
    cells: Mapping[tuple[str, str], tuple[str, int | None]],
    stats: MatrixStats,
    offset: int,
    limit: int,
) -> ScoreMatrixPage:
    """把一页矩阵数据装配成契约视图；``cells`` 覆盖本页全部（人次×叶）。"""
    items = list(revision.item_snapshot)
    participants = list(revision.participant_snapshot)
    page = participants[offset : offset + limit]
    item_ids = [item.item_id for item in items]
    total_max_units = sum(item.max_score_units for item in items)

    absent_ids = set(stats.absent_participant_ids)
    class_of = {item.participant_id: item.class_id for item in participants}
    absent_class_ids = sorted(
        {class_of[pid] for pid in absent_ids if pid in class_of}
    )

    rows: list[ScoreMatrixRow] = []
    for participant in page:
        row_cells: list[ScoreCellValue] = []
        all_recorded = True
        total = 0
        for item_id in item_ids:
            status, units = cells.get(
                (participant.participant_id, item_id), ("missing", None)
            )
            row_cells.append(
                ScoreCellValue(itemId=item_id, status=status, scoreUnits=units)
            )
            if status == "recorded":
                total += units or 0
            else:
                all_recorded = False
        rows.append(
            ScoreMatrixRow(
                participant=_participant(participant, all_recorded, total, total_max_units),
                cells=row_cells,
            )
        )
    return ScoreMatrixPage(
        revision=revision.view(),
        items=[item.model_dump(by_alias=True) for item in items],
        rows=rows,
        total=len(participants),
        offset=offset,
        limit=limit,
        missingParticipantIds=list(stats.missing_participant_ids),
        missingCellCount=stats.missing_cell_count,
        absentClassIds=absent_class_ids,
    )


def _participant(
    snapshot: ScoreParticipantSnapshot,
    all_recorded: bool,
    total: int,
    total_max_units: int,
) -> ScoreMatrixParticipant:
    return ScoreMatrixParticipant(
        participantId=snapshot.participant_id,
        studentId=snapshot.student_id,
        studentNo=snapshot.student_no,
        name=snapshot.name,
        classId=snapshot.class_id,
        attemptNo=snapshot.attempt_no,
        attendance=snapshot.attendance,
        totalUnits=total if all_recorded else None,
        totalMaxUnits=total_max_units,
    )


def revision_view(revision: ScoreRevisionRecord) -> ScoreRevisionView:
    return revision.view()


def matrix_cells_for_page(
    revision: ScoreRevisionRecord, *, offset: int, limit: int
) -> tuple[list[ScoreParticipantSnapshot], Sequence[str]]:
    """取一页参测人次与全量叶 id 顺序（供仓储查询拼装）。"""
    participants = list(revision.participant_snapshot)
    return participants[offset : offset + limit], [item.item_id for item in revision.item_snapshot]


__all__ = ["build_matrix_page", "matrix_cells_for_page", "revision_view"]
