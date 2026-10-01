"""知识点跨库引用核验（TEACHING-LOOP B3 / G0 · B2-RV06 公共修复）。

原卷与题库在**确认/发布新引用**前必须复核知识点身份、修订归属、学科与归档状态；
草稿期校验过的状态在确认时可能已经变化（例如知识点被归档）。本模块提供唯一的
只读核验实现；调用方必须把它放在 ``PublicationCoordinator.publication(...)`` 内、
**写事务之前**执行，避免"释放协调锁之后才写新引用"。

边界：

- 只做**只读**查询（跨库读，不写知识点库、不共享连接）；
- 只约束**新发布**的引用；历史已确认关联继续按名称快照可读，不回溯重核；
- 不要求引用的是"当前修订"（设计允许同一知识点使用较早内容修订），
  但要求修订真实存在且属于该知识点。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError

KNOWLEDGE_REFERENCE_INVALID = "KNOWLEDGE_REFERENCE_INVALID"
KNOWLEDGE_ARCHIVED = "KNOWLEDGE_ARCHIVED"


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """知识点身份 + 指定修订 + 学科 + 状态（核验结果，可安全冻结进快照）。"""

    knowledge_point_id: str
    knowledge_revision_id: str
    name: str
    subject_id: str
    version: int
    status: str


@dataclass(frozen=True)
class KnowledgeReference:
    """一条待发布的引用：知识点身份 + 内容修订（+ 可选期望学科）。"""

    knowledge_point_id: str
    knowledge_revision_id: str
    role: str = "primary"


def _reference_error(message: str, *, index: int, field: str) -> AppError:
    return AppError(
        message,
        code=KNOWLEDGE_REFERENCE_INVALID,
        status_code=422,
        details=error_details(
            issues=[
                ErrorIssue(
                    field=f"references[{index}].{field}",
                    code=KNOWLEDGE_REFERENCE_INVALID,
                    message=message,
                )
            ]
        ),
    )


def read_knowledge_snapshots(
    knowledge_catalog, references: Iterable[KnowledgeReference]
) -> dict[str, KnowledgeSnapshot]:
    """按引用集合读取知识点快照（跨库只读；缺失/修订不符 → 422 可定位）。"""
    refs = list(references)
    ids = sorted({ref.knowledge_point_id for ref in refs if ref.knowledge_point_id})
    if not ids:
        return {}
    snapshots: dict[str, KnowledgeSnapshot] = {}
    with knowledge_catalog.read_connection() as conn:
        for index, ref in enumerate(refs):
            if not ref.knowledge_point_id:
                raise _reference_error(
                    "引用缺少知识点身份。", index=index, field="knowledgePointId"
                )
            if ref.knowledge_point_id in snapshots:
                continue
            row = conn.execute(
                "SELECT kp.id, kp.subject_id, kp.status, kp.current_revision_id, "
                "kpr.id AS revision_id, kpr.version, kpr.name "
                "FROM knowledge_points kp "
                "LEFT JOIN knowledge_point_revisions kpr ON kpr.knowledge_point_id = kp.id "
                "WHERE kp.id = ?",
                (ref.knowledge_point_id,),
            ).fetchall()
            if not row:
                raise _reference_error(
                    f"知识点不存在：{ref.knowledge_point_id}。",
                    index=index,
                    field="knowledgePointId",
                )
            revisions = {
                r["revision_id"]: r for r in row if r["revision_id"] is not None
            }
            target = revisions.get(ref.knowledge_revision_id)
            if target is None:
                raise _reference_error(
                    f"知识点修订不存在或不属于该知识点：{ref.knowledge_revision_id}。",
                    index=index,
                    field="knowledgeRevisionId",
                )
            base = row[0]
            snapshots[ref.knowledge_point_id] = KnowledgeSnapshot(
                knowledge_point_id=str(base["id"]),
                knowledge_revision_id=str(target["revision_id"]),
                name=str(target["name"]),
                subject_id=str(base["subject_id"]),
                version=int(target["version"]),
                status=str(base["status"]),
            )
    return snapshots


def require_active_knowledge_references(
    knowledge_catalog,
    references: Iterable[KnowledgeReference] | Mapping[str, str],
    *,
    expected_subject_id: str | None = None,
) -> dict[str, KnowledgeSnapshot]:
    """核验引用集合：存在、修订归属、同学科、未归档；失败抛 422/409 且可定位。

    ``references`` 可以是 ``KnowledgeReference`` 列表，或 ``{knowledgePointId: revisionId}``
    映射（role 默认 primary）。返回核验通过的快照（调用方据此刷新名称/学科快照）。
    """
    if isinstance(references, Mapping):
        refs = [
            KnowledgeReference(
                knowledge_point_id=str(point_id), knowledge_revision_id=str(revision_id)
            )
            for point_id, revision_id in references.items()
        ]
    else:
        refs = list(references)

    snapshots = read_knowledge_snapshots(knowledge_catalog, refs)
    for index, ref in enumerate(refs):
        snapshot = snapshots.get(ref.knowledge_point_id)
        if snapshot is None:  # pragma: no cover - read_knowledge_snapshots 已覆盖缺失
            continue
        if snapshot.status != "active":
            raise AppError(
                f"知识点已归档，不能作为新引用：{snapshot.name}。",
                code=KNOWLEDGE_ARCHIVED,
                status_code=409,
                details=error_details(
                    issues=[
                        ErrorIssue(
                            field=f"references[{index}].knowledgePointId",
                            code=KNOWLEDGE_ARCHIVED,
                            message="已归档知识点不能用于新引用；请先恢复或改选。",
                        )
                    ]
                ),
            )
        if expected_subject_id and snapshot.subject_id != expected_subject_id:
            raise _reference_error(
                f"知识点学科与目标学科不一致（{snapshot.subject_id} ≠ {expected_subject_id}）。",
                index=index,
                field="knowledgePointId",
            )
    return snapshots
