"""
DB Analysis MCP Server (SSE)

客户端传入 db 参数，服务器从 db_mapping 表查找连接配置。
    http://localhost:8000/sse?db=singa
"""

import os
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
import uvicorn

from .logger import configure_logging, get_logger

# ---------- 初始化 ----------

load_dotenv()

_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.path.join(_log_dir, "mcp-server.log"),
)
logger = get_logger("mcp.server")

# ---------- 数据库映射（内存缓存） ----------

# {db_name: {host, port, username, password, database}}
_db_mapping: Dict[str, Dict[str, Any]] = {}
_db_mapping_service = None  # 延迟初始化

# 当前请求上下文（每次请求由中间件更新）
_current_db_config: Dict[str, Any] = {}
_current_db_key: str = "default"


def _get_mapping_service():
    """获取 DBMappingService 单例（延迟初始化）"""
    global _db_mapping_service
    if _db_mapping_service is None:
        from db.database import DBMappingService
        _db_mapping_service = DBMappingService()
    return _db_mapping_service


def load_db_mapping() -> Dict[str, Dict[str, Any]]:
    """从 db_mapping 表加载所有活跃映射到缓存"""
    global _db_mapping
    try:
        _db_mapping = _get_mapping_service().load_to_mapping_dict()
        logger.info(f"数据库映射已加载: {len(_db_mapping)} 条")
    except Exception as e:
        logger.error(f"加载映射失败: {e}")
        _db_mapping = {}
    return _db_mapping


def get_db_config(db_key: str) -> Dict[str, Any]:
    """获取数据库配置，缓存未命中时实时查询"""
    if db_key in _db_mapping:
        return _db_mapping[db_key]

    # 实时查询（处理运行期间新增映射）
    try:
        mapping = _get_mapping_service().get_by_db_name(db_key)
        if mapping and mapping.is_active:
            config = {
                "host": mapping.host,
                "port": mapping.port,
                "username": mapping.username,
                "password": mapping.password,
                "database": mapping.database,
            }
            _db_mapping[db_key] = config
            logger.info(f"实时查询到映射: {db_key}")
            return config
    except Exception as e:
        logger.error(f"查询映射失败 ({db_key}): {e}")
    return {}


def refresh_db_mapping() -> Dict[str, Dict[str, Any]]:
    """刷新映射缓存（重新从数据库加载）"""
    global _db_mapping_service
    _db_mapping_service = None
    return load_db_mapping()


# ---------- 当前请求上下文（中间件 / tool 使用） ----------

def get_current_db_config() -> Dict[str, Any]:
    return _current_db_config


def get_current_db_key() -> str:
    return _current_db_key


# ---------- MCP 实例 & 工具注册 ----------

mcp = FastMCP(
    name="DB Analysis MCP Server",
    instructions="数据分析智能体服务器，提供连接数据库后的数据查询和分析能力",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"],
        allowed_origins=["*"],
    ),
)

from .tool import register_tools  # noqa: E402
register_tools(mcp)


# ---------- HTTP 端点 ----------

async def health_check(request):
    """健康检查"""
    return JSONResponse({"status": "healthy", "service": "DB Analysis MCP Server"})


async def root(request):
    """服务信息"""
    db_keys = list(_db_mapping.keys()) if _db_mapping else []
    return JSONResponse({
        "message": "MCP Server running",
        "endpoints": {"/sse": "MCP SSE", "/health": "健康检查", "/refresh": "刷新映射"},
        "available_databases": db_keys,
        "total": len(db_keys),
        "usage": "/sse?db=<database_name>",
    })


async def refresh_mapping(request):
    """刷新数据库映射缓存"""
    mapping = refresh_db_mapping()
    db_keys = list(mapping.keys())
    logger.info(f"手动刷新映射缓存: {len(db_keys)} 条")
    return JSONResponse({"status": "ok", "total": len(db_keys), "available_databases": db_keys})


# ---------- 生命周期 ----------

@asynccontextmanager
async def lifespan(app):
    """启动时加载映射，关闭时清理连接池"""
    logger.info("MCP Server 启动中...")
    mapping = load_db_mapping()
    db_keys = list(mapping.keys())
    if db_keys:
        logger.info(f"可用数据库 ({len(db_keys)}): {', '.join(db_keys)}")

    yield

    try:
        from .connection_pool import close_all_pools
        await close_all_pools()
        logger.info("连接池已清理")
    except ImportError:
        pass
    logger.info("MCP Server 已关闭")


# ---------- 纯 ASGI 中间件：从 URL ?db= 解析数据库配置 ----------

class DatabaseConfigMiddleware:
    """纯 ASGI 中间件，从 query_string 中提取 db 参数并设置当前请求的数据库配置"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        global _current_db_config, _current_db_key

        if scope["type"] in ("http", "websocket"):
            qs = scope.get("query_string", b"").decode()
            if qs:
                params = parse_qs(qs)
                if "db" in params:
                    db_key = params["db"][0]
                    _current_db_key = db_key
                    db_config = get_db_config(db_key)
                    if db_config:
                        _current_db_config = db_config
                        logger.debug(f"数据库映射: {db_key}")
                    else:
                        logger.warning(f"未找到映射: {db_key}")

        await self.app(scope, receive, send)


# ---------- Starlette 应用 ----------

app = Starlette(
    debug=False,
    lifespan=lifespan,
    middleware=[Middleware(DatabaseConfigMiddleware)],
    routes=[
        Route("/", endpoint=root),
        Route("/health", endpoint=health_check),
        Route("/refresh", endpoint=refresh_mapping),
        Mount("/", app=mcp.sse_app()),
    ],
)


# ---------- 启动入口 ----------

def start_server():
    """启动生产级 uvicorn 服务器"""
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    workers = int(os.getenv("MCP_WORKERS", "1"))

    print(f"""
{'=' * 45}
  DB Analysis MCP Server
{'=' * 45}
  SSE:     http://{host}:{port}/sse?db=<name>
  Health:  http://{host}:{port}/health
  Refresh: http://{host}:{port}/refresh
  Workers: {workers}
{'=' * 45}""")

    uvicorn.run(
        "db_mcp.server:app",       # 字符串引用，支持多 worker 进程
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
        timeout_keep_alive=65,     # 保持连接超时（秒），略大于常见反代 60s
        timeout_graceful_shutdown=30,
        limit_concurrency=200,     # 最大并发连接数
        limit_max_requests=10000,  # 单 worker 处理请求上限后自动重启（防内存泄漏）
    )
