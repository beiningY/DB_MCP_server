"""
MCP 资源模块
在此添加自定义资源
"""
from .base import BaseResource, ResourceRegistry
from .db_resources import DatabaseResources
from .metadata_resources import MetadataResources

__all__ = [
    "BaseResource",
    "ResourceRegistry",
    "DatabaseResources",
    "MetadataResources",
]

