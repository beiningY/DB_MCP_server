"""
DB MCP Server 模块

使用方式：
    from db_mcp import start_server, app

    start_server()                  # 直接启动
    uvicorn db_mcp.server:app ...   # 或 uvicorn 启动
"""

from .server import mcp, start_server, app, get_current_db_config, get_current_db_key

from .connection_pool import (
    get_engine,
    get_pool,
    get_session,
    execute_query,
    execute_query_many,
    close_pool,
    close_all_pools,
    get_pool_stats,
    get_pool_stats_async,
    get_pool_info,
    test_connection,
    AsyncDBConnection,
    AsyncDBSession,
)

__all__ = [
    "mcp", "start_server", "app",
    "get_current_db_config", "get_current_db_key",
    "get_engine", "get_pool", "get_session",
    "execute_query", "execute_query_many",
    "close_pool", "close_all_pools",
    "get_pool_stats", "get_pool_stats_async", "get_pool_info",
    "test_connection", "AsyncDBConnection", "AsyncDBSession",
]

__version__ = "2.3.0"
