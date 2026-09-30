"""教学闭环请求模型：只放路由入参；响应/视图类型在 ``app/contracts/teaching_loop.py``。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.contracts.teaching_loop import JobDomain


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class JobDomainRequest(_Frozen):
    """公共任务 cancel/retry 的请求体：任务所属业务库。"""

    domain: JobDomain
