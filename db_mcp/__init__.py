"""
DB MCP Server 模块
数据分析 Agent 服务的核心组件

该模块提供：
- MCP Server 实例（FastMCP）
- 数据库配置管理（从 URL 参数提取）
- 动态数据库连接支持
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
    get_current_session_id,
    set_current_session_id,
    load_predefined_configs,
    get_predefined_config,
)

__all__ = [
    # MCP 服务器实例
    "mcp",
    # 服务器启动函数
    "start_server",
    # Starlette 应用实例
    "app",
    # 数据库配置管理
    "get_current_db_config",
    "set_current_db_config",
    # Session 管理
    "get_current_session_id",
    "set_current_session_id",
    # 预定义配置管理
    "load_predefined_configs",
    "get_predefined_config",
]

__version__ = "2.1.0"
__author__ = "DB MCP Server Team"
