"""名单业务域（TEACHING-LOOP B1 / T30-a）。

对外只暴露 ``RosterService`` 与装配工厂 ``build_roster_service``；路由从
``app.state.roster_service`` 取服务，未装配时返回 503（不返回空列表）。
"""

from app.services.roster.service import RosterService, build_roster_service

__all__ = ["RosterService", "build_roster_service"]
