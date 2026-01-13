"""
数据库相关资源示例
演示如何创建自定义资源
"""
import json
from typing import Any
from .base import BaseResource


class DatabaseResources:
    """数据库资源集合"""
    
    class ConnectionInfoResource(BaseResource):
        """数据库连接信息资源"""
        
        def __init__(self, db_config: dict[str, Any] | None = None):
            self._db_config = db_config or {
                "host": "localhost",
                "port": 5432,
                "database": "default",
                "user": "admin"
            }
        
        @property
        def uri(self) -> str:
            return "db://connection/info"
        
        @property
        def name(self) -> str:
            return "数据库连接信息"
        
        @property
        def description(self) -> str:
            return "当前数据库连接配置信息"
        
        @property
        def mime_type(self) -> str:
            return "application/json"
        
        async def read(self) -> str:
            # 返回连接信息（隐藏敏感信息）
            safe_config = {**self._db_config}
            if "password" in safe_config:
                safe_config["password"] = "***"
            return json.dumps(safe_config, ensure_ascii=False, indent=2)
    
    class SchemaResource(BaseResource):
        """数据库 Schema 资源"""
        
        def __init__(self, database: str = "default"):
            self._database = database
        
        @property
        def uri(self) -> str:
            return f"db://schema/{self._database}"
        
        @property
        def name(self) -> str:
            return f"数据库 Schema ({self._database})"
        
        @property
        def description(self) -> str:
            return f"数据库 {self._database} 的完整 schema 信息"
        
        @property
        def mime_type(self) -> str:
            return "application/json"
        
        async def read(self) -> str:
            # TODO: 实现实际的 schema 获取逻辑
            # 这里是模拟数据
            mock_schema = {
                "database": self._database,
                "tables": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "type": "INTEGER"},
                            {"name": "username", "type": "VARCHAR(50)"},
                            {"name": "email", "type": "VARCHAR(100)"}
                        ]
                    },
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "INTEGER"},
                            {"name": "user_id", "type": "INTEGER"},
                            {"name": "total", "type": "DECIMAL(10,2)"}
                        ]
                    }
                ]
            }
            return json.dumps(mock_schema, ensure_ascii=False, indent=2)
    
    class StatisticsResource(BaseResource):
        """数据库统计信息资源"""
        
        @property
        def uri(self) -> str:
            return "db://statistics"
        
        @property
        def name(self) -> str:
            return "数据库统计信息"
        
        @property
        def description(self) -> str:
            return "数据库的统计和性能指标"
        
        @property
        def mime_type(self) -> str:
            return "application/json"
        
        async def read(self) -> str:
            # TODO: 实现实际的统计信息获取逻辑
            # 这里是模拟数据
            mock_stats = {
                "connections": {
                    "active": 5,
                    "idle": 10,
                    "max": 100
                },
                "queries": {
                    "total": 15420,
                    "per_second": 45.2
                },
                "storage": {
                    "used_mb": 1024,
                    "total_mb": 10240
                }
            }
            return json.dumps(mock_stats, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_all_resources(cls) -> list[BaseResource]:
        """获取所有数据库资源实例"""
        return [
            cls.ConnectionInfoResource(),
            cls.SchemaResource("default"),
            cls.StatisticsResource()
        ]

