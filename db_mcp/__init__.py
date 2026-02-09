"""
DB MCP Server 模块
数据分析 Agent 服务的核心组件

该模块提供：
- MCP Server 实例（FastMCP）
- 数据库配置管理（服务端映射）
- 动态数据库连接支持
- 异步连接池管理（SQLAlchemy Async）
- 工具注册接口

使用方式：
    from db_mcp import mcp, start_server, app

    # 方式1：直接启动
    start_server()

    # 方式2：使用 uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from .server import (
    mcp,
    start_server,
    app,
    get_current_db_config,
    set_current_db_config,
    get_current_db_key,
    set_current_db_key,
    load_db_mapping,
    get_db_config,
    get_all_db_keys,
    refresh_db_mapping,
)

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
    # MCP 服务器实例
    "mcp",
    # 服务器启动函数
    "start_server",
    # Starlette 应用实例
    "app",
    # 数据库映射管理（从 db_mapping 表加载）
    "load_db_mapping",
    "get_db_config",
    "get_all_db_keys",
    "refresh_db_mapping",
    # 当前请求配置管理
    "get_current_db_config",
    "set_current_db_config",
    "get_current_db_key",
    "set_current_db_key",
    # 异步连接池 - 引擎
    "get_engine",
    "get_pool",
    "get_session",
    # 异步连接池 - 查询
    "execute_query",
    "execute_query_many",
    # 异步连接池 - 管理
    "close_pool",
    "close_all_pools",
    "get_pool_stats",
    "get_pool_stats_async",
    "get_pool_info",
    "test_connection",
    # 异步连接池 - 上下文管理器
    "AsyncDBConnection",
    "AsyncDBSession",
]

__version__ = "2.3.0"
__author__ = "DB MCP Server Team"
