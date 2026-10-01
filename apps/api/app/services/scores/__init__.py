"""成绩服务包（TEACHING-LOOP B3 / T60）。

装配契约（B3 任务卡冻结）：``build_score_service(catalog, *, asset_store, file_assets,
assessment_service, paper_reader, publication_coordinator) -> ScoreService``。
CTRL 的 ``app.main`` 负责把该工厂接到 ``app.state.score_service``；路由模块
``app.api.v1.scores`` 只从 ``app.state`` 取服务，不自行装配。

- ``imports``：纯分析层（表头识别、四态解析、行定位、全矩阵预览）；
- ``ScoreImportPatchRequest`` 已并入冻结契约 ``app.contracts.scores``；
- ``matrix``：只读矩阵分页装配；
- ``service``：用例门面（导入/校对/确认/修正/读取）。
"""

from __future__ import annotations

# 先导入无环的子模块，再导入门面，避免包初始化期的解析顺序问题
from app.services.scores import imports as imports  # noqa: F401
from app.services.scores import matrix as matrix  # noqa: F401
from app.services.scores.service import ScoreService, build_score_service

__all__ = ["ScoreService", "build_score_service"]
