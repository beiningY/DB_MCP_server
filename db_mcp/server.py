"""
DB Analysis MCP Server
支持通过 Streamable HTTP 进行远程连接的 MCP 服务器
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import uvicorn

# 加载环境变量
load_dotenv()

# 数据库连接（延迟初始化）
_db_engine = None


def get_db_engine():
    """获取数据库连接引擎（单例模式）"""
    global _db_engine
    if _db_engine is None:
        from sqlalchemy import create_engine
        
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            _db_engine = create_engine(db_url)
    return _db_engine


def get_database_name() -> str:
    """获取当前数据库名称"""
    return os.getenv("DATABASE_NAME", "default_db")


# 创建 MCP 服务器实例
mcp = FastMCP(
    name="DB Analysis MCP Server",
    instructions="数据分析智能体服务器，提供数据查询和分析能力"
)


# 注册工具
from .tool import register_tools
register_tools(mcp)


# 健康检查端点
async def health_check(request):
    """健康检查端点"""
    return JSONResponse({
        "status": "healthy",
        "service": "DB Analysis MCP Server",
        "database": get_database_name()
    })


# 根路径
async def root(request):
    """根路径信息"""
    return JSONResponse({
        "message": "MCP Server running",
        "endpoints": {
            "sse": "/sse - MCP SSE 连接端点",
            "mcp": "/mcp - MCP HTTP 连接端点",
            "health": "/health - 健康检查"
        }
    })


@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # 启动时
    print(f"🚀 MCP Server 启动中...")
    print(f"📊 数据库: {get_database_name()}")
    yield
    # 关闭时
    print("👋 MCP Server 关闭")


# 创建 Starlette 应用，挂载 MCP 路由
app = Starlette(
    debug=True,
    lifespan=lifespan,
    routes=[
        Route("/", endpoint=root),
        Route("/health", endpoint=health_check),
        # 挂载 MCP Streamable HTTP 路由
        Mount("/mcp", app=mcp.streamable_http_app()),
        # 挂载 MCP SSE 路由（兼容旧客户端）
        Mount("/", app=mcp.sse_app()),
    ],
)


def start_server():
    """启动 MCP 服务器"""
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    
    print("=" * 50)
    print("DB Analysis MCP Server")
    print("=" * 50)
    print(f"🌐 地址: http://{host}:{port}")
    print(f"📡 SSE 端点: http://{host}:{port}/sse")
    print(f"📡 HTTP 端点: http://{host}:{port}/mcp")
    print(f"❤️  健康检查: http://{host}:{port}/health")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    start_server()
