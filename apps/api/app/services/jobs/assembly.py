"""业务域任务引擎装配支持（R 系列多域回归共用，由总控维护）。

背景：``JobEngine`` 构造时**拷贝** stores 映射，不能靠引用追加；业务域又在不同批次
落地。约定：

- 每个域装配模块（``app.services.<domain>.assembly``）在 ``assemble(app, settings)``
  末尾调用 ``register_job_store(app, domain, store)``；
- 本函数把该域的 ``JobStore`` 登记进 ``app.state.job_stores``，并以**当前全集**重建
  ``app.state.job_engine``——只在装配期调用，服务期不再重建，无并发歧义；
- 域装配模块之间互不依赖文件，只有本模块是共享写入点。

``/workflow-jobs`` 的 retry 调度依赖 ``app.state.job_executors``（``JobExecutorRegistry``，
各域装配期注册自己的执行器工厂，参见 ``app.services.jobs.registry`` 的说明）。
"""

from __future__ import annotations

from typing import Any

from app.services.jobs.engine import JobEngine


def register_job_store(app: Any, domain: str, store: Any) -> JobEngine:
    """登记一个域的 JobStore 并重建 JobEngine（返回新引擎，同时挂 app.state）。"""
    stores = dict(getattr(app.state, "job_stores", None) or {})
    stores[domain] = store
    app.state.job_stores = stores
    engine = JobEngine(stores)
    app.state.job_engine = engine
    return engine


__all__ = ["register_job_store"]
