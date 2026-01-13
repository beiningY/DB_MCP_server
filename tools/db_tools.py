"""
数据库相关工具示例
演示如何创建自定义工具
"""
from typing import Any
import mcp.types as types
from .base import BaseTool


class DatabaseTools:
    """数据库工具集合"""
    
    class QueryTool(BaseTool):
        """SQL 查询工具"""
        
        @property
        def name(self) -> str:
            return "db_query"
        
        @property
        def description(self) -> str:
            return "执行 SQL 查询语句"
        
        @property
        def input_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 SQL 查询语句"
                    },
                    "database": {
                        "type": "string",
                        "description": "目标数据库名称",
                        "default": "default"
                    }
                },
                "required": ["sql"]
            }
        
        async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
            sql = arguments.get("sql", "")
            database = arguments.get("database", "default")
            
            # TODO: 实现实际的数据库查询逻辑
            # 这里是示例响应
            return [types.TextContent(
                type="text",
                text=f"[模拟] 在数据库 '{database}' 上执行查询:\n{sql}\n\n结果: 查询成功执行"
            )]
    
    class ListTablesTool(BaseTool):
        """列出数据库表工具"""
        
        @property
        def name(self) -> str:
            return "db_list_tables"
        
        @property
        def description(self) -> str:
            return "列出数据库中的所有表"
        
        @property
        def input_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "目标数据库名称",
                        "default": "default"
                    },
                    "schema": {
                        "type": "string",
                        "description": "数据库 schema (可选)"
                    }
                },
                "required": []
            }
        
        async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
            database = arguments.get("database", "default")
            schema = arguments.get("schema", "public")
            
            # TODO: 实现实际的表列表获取逻辑
            # 这里是示例响应
            mock_tables = ["users", "orders", "products", "categories"]
            return [types.TextContent(
                type="text",
                text=f"数据库 '{database}' (schema: {schema}) 中的表:\n" + 
                     "\n".join(f"  - {table}" for table in mock_tables)
            )]
    
    class DescribeTableTool(BaseTool):
        """描述表结构工具"""
        
        @property
        def name(self) -> str:
            return "db_describe_table"
        
        @property
        def description(self) -> str:
            return "获取指定表的结构信息"
        
        @property
        def input_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名"
                    },
                    "database": {
                        "type": "string",
                        "description": "目标数据库名称",
                        "default": "default"
                    }
                },
                "required": ["table_name"]
            }
        
        async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
            table_name = arguments.get("table_name", "")
            database = arguments.get("database", "default")
            
            # TODO: 实现实际的表结构获取逻辑
            # 这里是示例响应
            mock_columns = [
                {"name": "id", "type": "INTEGER", "nullable": False, "key": "PRIMARY"},
                {"name": "name", "type": "VARCHAR(255)", "nullable": False, "key": ""},
                {"name": "created_at", "type": "TIMESTAMP", "nullable": True, "key": ""},
            ]
            
            result = f"表 '{table_name}' (数据库: {database}) 结构:\n"
            result += "-" * 60 + "\n"
            result += f"{'列名':<15} {'类型':<20} {'可空':<8} {'键':<10}\n"
            result += "-" * 60 + "\n"
            for col in mock_columns:
                result += f"{col['name']:<15} {col['type']:<20} {str(col['nullable']):<8} {col['key']:<10}\n"
            
            return [types.TextContent(type="text", text=result)]
    
    @classmethod
    def get_all_tools(cls) -> list[BaseTool]:
        """获取所有数据库工具实例"""
        return [
            cls.QueryTool(),
            cls.ListTablesTool(),
            cls.DescribeTableTool()
        ]

