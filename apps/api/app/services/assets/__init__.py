"""受管资产服务：内容寻址的文件本体（``<assets_root>/blobs/<sha256>``）。

B0 只冻结本体存储与校验（``AssetStore``）：内容寻址命名、同内容幂等、``os.replace``
原子落盘、读取/校验时重算 sha256。数据库登记（``file_assets``）在
``app.repositories.assets.file_assets``；``media_type`` / ``original_name`` 只用于
登记，不参与路径拼接。
"""

from app.services.assets.store import AREA_BLOBS, AssetStore, StoredAsset

__all__ = ["AREA_BLOBS", "AssetStore", "StoredAsset"]
