"""教学业务域装配包（R 系列逐批回归）。

本包不放业务实现：班级/名单在 ``app.services.roster``、原卷在 ``app.services.papers``、
施测在 ``app.services.assessments``；这里只提供逐批装配模块（``assemble(app, settings)``），
由 ``app.main`` 的 ``_DOMAIN_ASSEMBLIES`` 逐批调用。
"""

from app.services.teaching.assembly_roster_papers import assemble as assemble_roster_papers

__all__ = ["assemble_roster_papers"]
