"""
MCP Server - 数据分析 Agent 服务
使用 FastMCP 简化服务器创建，支持远程 SSE 连接
"""

import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from mcp.server.fastmcp import FastMCP
import uvicorn

# 加载环境变量
load_dotenv()

# ============= FastMCP Server 实例 =============
mcp = FastMCP("db-analysis-server")

# ============= 数据库连接 =============
_engine: Optional[Engine] = None


def get_db_engine() -> Optional[Engine]:
    """获取数据库引擎（单例模式）"""
    global _engine
    if _engine is None:
        db_url = os.getenv("DB_URL")
        if not db_url:
            return None
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
    return _engine


def get_database_name() -> str:
    """从 DB_URL 提取数据库名"""
    db_url = os.getenv("DB_URL", "")
    if "/" in db_url:
        db_part = db_url.split("/")[-1]
        if "?" in db_part:
            return db_part.split("?")[0]
        return db_part
    return "unknown"


# ============= 注册工具和资源 =============
from .tool import register_tools
from .resource import register_resources

register_tools(mcp)
# register_resources(mcp, get_database_name, get_db_engine)


# ============= SSE App 缓存 =============
_app = None


def get_app():
    """获取 ASGI app（单例模式，用于 uvicorn 直接启动）"""
    global _app
    if _app is None:
        _app = mcp.sse_app()
    return _app


# ============= 启动服务器 =============
def start_server():
    """启动 MCP 服务器（SSE 模式）"""
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8080"))
    database = get_database_name()
    
    db_status = "已连接" if get_db_engine() else "未配置"
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           DB Analysis MCP Server (FastMCP)               ║
╠══════════════════════════════════════════════════════════╣
║  远程连接地址: http://{host}:{port}/sse
╠══════════════════════════════════════════════════════════╣
║  数据库: {database} ({db_status})
╠══════════════════════════════════════════════════════════╣
║  工具:                                                   ║
║    - ask_data_agent: 数据分析智能体                      ║
║  资源:                                                   ║
║    - db://{database}/overview: 数据库概览                
║    - db://{database}/tables: 所有表结构                  
╚══════════════════════════════════════════════════════════╝
    """)
    
    # 使用缓存的 app 实例
    uvicorn.run(get_app(), host=host, port=port)


# 导出 app 供 uvicorn 直接使用
app = get_app()
