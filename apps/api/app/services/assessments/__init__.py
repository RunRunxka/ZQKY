"""施测服务包（TEACHING-LOOP B2 / T30-b）。

对外入口只有两处：

- ``build_assessment_service(...)``（CTRL 装配到 ``app.state.assessment_service``，
  reader 来自 T40 的 ``app.state.confirmed_paper_reader``）；
- ``AssessmentService`` 的公开方法（HTTP 路由 ``app/api/v1/assessments.py`` 调用）。

SQL 在 ``app/repositories/teaching/assessments.py``；本包只做闸门与事务编排。
"""

from app.services.assessments.service import (
    AssessmentService,
    build_assessment_service,
)

__all__ = ["AssessmentService", "build_assessment_service"]
