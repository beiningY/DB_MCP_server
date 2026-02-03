"""
DB Analysis MCP Server
支持通过 Streamable HTTP 进行远程连接的 MCP 服务器
支持动态数据库连接 + 客户端 URL 参数配置

该模块实现了一个基于 MCP (Model Context Protocol) 的数据分析服务器。
客户端可以通过 URL 参数传递数据库凭证，服务器提供 data_agent 工具进行数据查询和分析。

主要功能：
- MCP 协议支持（SSE 和 HTTP 传输）
- 动态数据库连接配置（通过 URL 参数）
- 预定义数据库配置支持（通过环境变量）
- 健康检查端点

使用方式：
    # 方式1：直接启动
    python main.py

    # 方式2：使用 uvicorn
    uvicorn db_mcp.server:app --host 0.0.0.0 --port 8000

客户端连接示例：
    # URL 参数方式
    http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb

    # 预定义配置方式
    http://localhost:8000/sse?session=prod
"""

import os
import json
from contextlib import asynccontextmanager
from typing import Dict, Any
from urllib.parse import parse_qs

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# ============================================================================
# 全局变量
# ============================================================================

# 加载环境变量
load_dotenv()

# 从环境变量读取预定��的数据库配置（可选）
# 格式：JSON 对象，key 为 session 名称，value 为数据库配置
# 示例：{"prod": {"host": "localhost", "port": 3306, ...}}
_predefined_db_configs: Dict[str, Dict[str, Any]] = {}

# 当前请求的数据库配置（从 URL 参数中提取）
# 注意：这是请求级别的全局变量，每个请求会更新
_current_db_config: Dict[str, Any] = {}

# 当前请求的 session_id
_current_session_id = "default"


# ============================================================================
# 预定义配置管理
# ============================================================================

def load_predefined_configs() -> Dict[str, Dict[str, Any]]:
    """
    从环境变量加载预定义的数据库配置

    环境变量 DB_MCP_CONFIGS 应为 JSON 格式：
    {"session_name": {"host": "...", "port": 3306, ...}}

    Returns:
        预定义配置字典
    """
    global _predefined_db_configs
    config_str = os.getenv("DB_MCP_CONFIGS", "{}")
    try:
        _predefined_db_configs = json.loads(config_str)
    except json.JSONDecodeError:
        _predefined_db_configs = {}
    return _predefined_db_configs


def get_predefined_config(session_id: str) -> Dict[str, Any]:
    """
    获取指定 session 的预定义配置

    Args:
        session_id: session 名称

    Returns:
        数据库配置字典，如果不存在则返回空字典
    """
    if not _predefined_db_configs:
        load_predefined_configs()
    return _predefined_db_configs.get(session_id, {})


# ============================================================================
# 当前请求配置管理
# ============================================================================

def get_current_db_config() -> Dict[str, Any]:
    """
    获取当前请求的数据库配置

    Returns:
        当前数据库配置字典
    """
    return _current_db_config


def set_current_db_config(config: Dict[str, Any]):
    """
    设置当前请求的数据库配置

    Args:
        config: 数据库配置字典
    """
    global _current_db_config
    _current_db_config = config


def get_current_session_id() -> str:
    """
    获取当前请求的 session_id

    Returns:
        session_id 字符串
    """
    return _current_session_id


def set_current_session_id(session_id: str):
    """
    设置当前请求的 session_id

    Args:
        session_id: session 标识符
    """
    global _current_session_id
    _current_session_id = session_id


# ============================================================================
# MCP 服务器实例
# ============================================================================

# 创建 MCP 服务器实例
mcp = FastMCP(
    name="DB Analysis MCP Server",
    instructions="数据分析智能体服务器，提供连接数据库后的数据查询和分析能力",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,   # 关闭 DNS rebinding 限制
        allowed_hosts=["*"],                     # 允许所有 host 访问
        allowed_origins=["*"]                    # 允许所有跨域请求
    )
)


# 注册工具
from .tool import register_tools
register_tools(mcp)


# ============================================================================
# HTTP 端点
# ============================================================================

async def health_check(request):
    """
    健康检查端点

    Returns:
        JSONResponse: 服务状态信息
    """
    return JSONResponse({
        "status": "healthy",
        "service": "DB Analysis MCP Server",
        "version": "2.1.0",
        "features": [
            "dynamic_database_connection",
            "real_time_schema_query",
            "sql_execution",
            "knowledge_graph_search"
        ]
    })


async def root(request):
    """
    根路径信息端点

    Returns:
        JSONResponse: 可用端点列表
    """
    return JSONResponse({
        "message": "MCP Server running",
        "endpoints": {
            "sse": "/sse - MCP SSE 连接端点",
            "mcp": "/mcp - MCP HTTP 连接端点",
            "health": "/health - 健康检查"
        }
    })


# ============================================================================
# 应用生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app):
    """
    应用生命周期管理

    启动时打印配置信息，关闭时清理资源。
    """
    # 启动时
    print(f"🚀 MCP Server 启动中...")
    print(f"🔌 支持动态数据库连接")
    print(f"📋 支持 URL 参数配置: ?host=xxx&port=xxx&username=xxx&password=xxx&database=xxx")

    # 显示预定义的数据库配置
    configs = load_predefined_configs()
    if configs:
        print(f"📋 预定义数据库配置: {list(configs.keys())}")

    yield

    # 关闭时
    # 清理连接池
    try:
        from .connection_pool import close_all_pools
        close_all_pools()
        print("🔌 连接池已清理")
    except ImportError:
        pass

    print("👋 MCP Server 关闭")


# ============================================================================
# 中间件：从 URL 参数提取数据库配置
# ============================================================================

class DatabaseConfigMiddleware(BaseHTTPMiddleware):
    """
    从 URL 查询参数中提取数据库配置的中间件

    支持两种方式：
    1. 直接传配置参数：?host=xxx&port=xxx&username=xxx&password=xxx&database=xxx
    2. 使用预配置名：?session=prod（从环境变量 DB_MCP_CONFIGS 读取）

    示例 URL：
        http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb
        http://localhost:8000/sse?session=prod
    """

    async def dispatch(self, request, call_next):
        """
        中间件处理函数

        Args:
            request: Starlette 请求对象
            call_next: 下一个中间件或路由处理器

        Returns:
            响应对象
        """
        # 从 URL 中提取查询参数
        if request.url.query:
            query_params = parse_qs(request.url.query)

            # 方式1：直接传数据库配置参数
            db_config = {}
            if "host" in query_params:
                db_config = {
                    "host": query_params.get("host", ["localhost"])[0],
                    "port": int(query_params.get("port", ["3306"])[0]),
                    "username": query_params.get("username", ["root"])[0],
                    "password": query_params.get("password", [""])[0],
                    "database": query_params.get("database", ["information_schema"])[0],
                }
                set_current_db_config(db_config)
                # 用 host 生成一个 session_id
                set_current_session_id(db_config["host"])

            # 方式2：使用预配置的 session
            elif "session" in query_params:
                session_id = query_params.get("session", ["default"])[0]
                set_current_session_id(session_id)
                # 从预定义配置中读取
                predefined = get_predefined_config(session_id)
                if predefined:
                    set_current_db_config(predefined)

        response = await call_next(request)
        return response


# ============================================================================
# Starlette 应用创建
# ============================================================================

# 创建 Starlette 应用，挂载 MCP 路由
app = Starlette(
    debug=True,
    lifespan=lifespan, # 确保 lifespan 变量已定义
    middleware=[
        # 核心修复：必须是 Middleware(类名) 的格式
        Middleware(DatabaseConfigMiddleware)
    ],
    routes=[
        Route("/", endpoint=root),
        Route("/health", endpoint=health_check),
        # 挂载 MCP 路由
        Mount("/mcp", app=mcp.streamable_http_app()),
        Mount("/", app=mcp.sse_app()),
    ],
)


# ============================================================================
# 服务器启动函数
# ============================================================================

def start_server():
    """
    启动 MCP 服务器

    从环境变量读取配置：
    - MCP_PORT: 端口号（默认 8000）
    - MCP_HOST: 主机地址（默认 0.0.0.0）
    """
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "127.0.0.1")

    print("=" * 50)
    print("DB Analysis MCP Server (v2.1)")
    print("=" * 50)
    print(f"🌐 地址: http://{host}:{port}")
    print(f"📡 SSE 端点: http://{host}:{port}/sse")
    print(f"📡 HTTP 端点: http://{host}:{port}/mcp")
    print(f"❤️  健康检查: http://{host}:{port}/health")
    print(f"🔧 支持动态数据库连接")
    print("=" * 50)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()
