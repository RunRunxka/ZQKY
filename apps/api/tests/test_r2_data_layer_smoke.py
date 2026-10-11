"""R2-BE1 数据层恢复冒烟：textbooks 库迁移 + TextbookCatalog 读操作。

最小自检：tmp_path 建库 → schema.migrate（R0-A 冻结迁移）→ 实例化权威层完成
一次读操作（catalog_state 单行）。不读写正式数据，不访问网络。

注：归档 ``schema.migrate()`` 返回 ``None``（迁移登记结果经
``app.core.migrations.applied_migrations`` 查询），本测试按此契约断言。
"""

from __future__ import annotations

from pathlib import Path

from app.core.migrations import applied_migrations
from app.core.sqlite import connect
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import CatalogState
from app.repositories.textbook_catalog.schema import REQUIRED_TABLES, migrate

BASELINE_ID = "0001_textbooks_baseline"


def test_r2_data_layer_smoke(tmp_path: Path) -> None:
    db_path = tmp_path / "catalog.sqlite3"

    # 1) 直接用 schema.migrate 在裸连接上建库（R0-A 冻结迁移）
    connection = connect(db_path)
    try:
        migrate(connection)  # 返回 None；结果经登记表查询
        registry = applied_migrations(connection)
        assert BASELINE_ID in registry, f"迁移未登记：{registry}"
        # 重复调用幂等：登记不变
        migrate(connection)
        assert applied_migrations(connection) == registry
        # REQUIRED_TABLES 全部存在
        for table in REQUIRED_TABLES:
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            assert row is not None, f"缺表：{table}"
    finally:
        connection.close()

    # 2) 权威层实例化 + 一次读操作（读 catalog_state 单行）
    catalog = TextbookCatalog(db_path)
    try:
        catalog.migrate()  # 实例内已迁移登记后才能读
        state = catalog.catalog_state()
        assert isinstance(state, CatalogState)
        assert state.active_generation_id is None
        assert state.rebuild_job_id is None
        assert state.catalog_version == 0
    finally:
        catalog.close()
