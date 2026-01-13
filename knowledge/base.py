"""
知识模块基类
所有知识模块的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class KnowledgeModule(ABC):
    """知识模块抽象基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化知识模块
        
        Args:
            config: 配置字典（可选）
        """
        self.config = config or {}
        self._initialize()
    
    @abstractmethod
    def _initialize(self):
        """初始化具体实现（加载数据、建立连接等）"""
        pass
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        搜索知识库
        
        Args:
            query: 查询字符串
            **kwargs: 其他参数
            
        Returns:
            搜索结果字典
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """模块名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """模块描述"""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """获取模块信息"""
        return {
            "name": self.name,
            "description": self.description,
            "config": self.config
        }
