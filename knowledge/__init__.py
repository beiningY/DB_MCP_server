"""
知识模块包
提供数据字典、元数据、历史查询等知识查询能力
"""

from .base import KnowledgeModule
from .online_dictionary import OnlineDictionaryModule
from .metadata import SingaBIMetadataModule
from .lightrag_client import LightRAGClient

__all__ = [
    'KnowledgeModule',
    'OnlineDictionaryModule',
    'SingaBIMetadataModule',
    'LightRAGClient',
]
