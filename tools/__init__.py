"""
数据分析师 Agent 工具模块
提供数据库查询、知识图谱搜索、表结构获取等工具

支持延迟加载配置：只存储 db_key，完整配置在工具调用时才从数据库查询
"""

import contextvars
from typing import Dict, Any
from .execute_sql_tool import execute_sql_query
from .search_knowledge_tool import search_knowledge_graph
from .get_table_schema_tool import get_table_schema


# ============================================================================
# 数据库标识符上下文（只存储 db_key，不存储完整配置）
# ============================================================================

# 当前请求的数据库标识符
_current_db_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tool_db_key", default=""
)


def set_tool_db_key(db_key: str) -> None:
    """设置当前请求的数据库标识符"""
    _current_db_key.set(db_key)


def get_tool_db_key() -> str:
    """获取当前请求的数据库标识符"""
    return _current_db_key.get()


def get_tool_db_config() -> Dict[str, Any]:
    """
    获取数据库配置（延迟加载）

    根据 db_key 从数据库查询完整配置。
    这确保配置不在 LLM 上下文中传递，而是在工具调用时才获取。
    """
    db_key = get_tool_db_key()
    if not db_key:
        return {}

    try:
        from db.database import DBMappingService
        service = DBMappingService()
        mapping = service.get_by_db_name(db_key)

        if mapping and mapping.is_active:
            return {
                "host": mapping.host,
                "port": mapping.port,
                "username": mapping.username,
                "password": mapping.password,
                "database": mapping.database,
            }
    except Exception:
        pass

    return {}


# ============================================================================
# 导出原始工具
# ============================================================================

__all__ = [
    "execute_sql_query",
    "search_knowledge_graph",
    "get_table_schema",
    "set_tool_db_key",
    "get_tool_db_key",
    "get_tool_db_config",
]
