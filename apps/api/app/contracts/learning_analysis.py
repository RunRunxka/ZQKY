"""学情分析 R6 冻结端点契约（knowledge-stats / student-knowledge / distribution / report）。

与前端 ``apps/web/src/contracts/learning-analysis.ts`` 的对应类型**逐字段镜像**（R6-FE
已按此实现并冻结）；既有分析契约（``AnalysisRunView`` / ``ItemStatView`` / ``NoteView``
等）仍在 ``app.contracts.b4`` / ``app.contracts.scores``，本模块只承载本卡冻结的
**新增端点**形状，不重复声明既有类型。

数字落空口径（红线）：无有效依据时 ``scoreRate`` 返回 ``null``（不补 0）、空集合返回
空列表（不伪造数据）——与前端「显式兜底、不猜造数据」一致。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


# --------------------------------------------------------------------------- 知识点得分率

class KnowledgeStatItem(_Frozen):
    """一个知识点的全班得分率（按小题得分率聚合；``scoreRate`` 降序出现在响应里）。

    - ``name``：报告冻结的知识点名称快照；
    - ``path``：知识点目录路径（``code`` 逐级「 / 」拼接；知识点库未装配或节点缺失时
      为 ``null``——不伪造路径）；
    - ``scoreRate``：0–1；primary 链接小题的满分加权得分率；
    - ``questionCount``：参与聚合的 primary 链接小题数。
    """

    knowledge_point_id: str = Field(alias="knowledgePointId")
    name: str
    path: str | None = None
    score_rate: float = Field(alias="scoreRate")
    question_count: int = Field(alias="questionCount", ge=1)


class KnowledgeStatsResponse(_Frozen):
    items: list[KnowledgeStatItem]


# --------------------------------------------------------------------------- 学生 × 知识点矩阵

class StudentKnowledgeCell(_Frozen):
    """矩阵单元：该生（脱敏代称行）在该知识点上的得分率。

    ``scoreRate`` 为 null = 该生在该知识点的 primary 小题上没有任何 recorded 依据
    （全 missing/absent/exempt）；不补 0。
    """

    knowledge_point_id: str = Field(alias="knowledgePointId")
    score_rate: float | None = Field(default=None, alias="scoreRate")
    question_count: int = Field(alias="questionCount", ge=0)


class StudentKnowledgeRow(_Frozen):
    """矩阵一行：``label`` 由后端给出（参与者脱敏代称/座号，**不是**学生姓名）。"""

    label: str
    cells: list[StudentKnowledgeCell]


class StudentKnowledgeResponse(_Frozen):
    knowledge_points: list["KnowledgePointRef"] = Field(alias="knowledgePoints")
    students: list[StudentKnowledgeRow]


class KnowledgePointRef(_Frozen):
    """矩阵列头的最小知识点引用（与前端 ``{knowledgePointId, name}`` 逐字段一致）。"""

    knowledge_point_id: str = Field(alias="knowledgePointId")
    name: str


# --------------------------------------------------------------------------- 分数段分布

class DistributionBucket(_Frozen):
    """学生级得分率分档计数（低 <60% / 中 60–85% / 高 ≥85%）。"""

    label: str
    count: int = Field(ge=0)


class DistributionResponse(_Frozen):
    buckets: list[DistributionBucket]


# --------------------------------------------------------------------------- 报告导出产物

class ExportArtifactRef(_Frozen):
    """``POST /analysis-runs/{run_id}/report`` → 201 的 ``artifact`` 标识。

    只承载前端需要的最小集合；完整产物视图（含 downloadUrl）走既有
    ``GET /export-artifacts/{artifactId}``。
    """

    artifact_id: str = Field(alias="artifactId")
    file_name: str = Field(alias="fileName")
    byte_size: int = Field(alias="byteSize", ge=1)


class AnalysisReportReceipt(_Frozen):
    artifact: ExportArtifactRef


StudentKnowledgeResponse.model_rebuild()

__all__ = [
    "AnalysisReportReceipt",
    "DistributionBucket",
    "DistributionResponse",
    "ExportArtifactRef",
    "KnowledgePointRef",
    "KnowledgeStatItem",
    "KnowledgeStatsResponse",
    "StudentKnowledgeCell",
    "StudentKnowledgeResponse",
    "StudentKnowledgeRow",
]
