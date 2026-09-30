"""受管资产登记仓储（教学库 ``file_assets``）。

文件本体在 ``app.services.assets.store``（``<assets_root>/blobs/<sha256>``）；
本包只负责数据库登记与读取，字段形状来自 ``app.contracts.teaching_loop``。
"""

from app.repositories.assets.file_assets import FileAssetRecord, FileAssetsRepository

__all__ = ["FileAssetRecord", "FileAssetsRepository"]
