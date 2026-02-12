"""
DB Analysis MCP Server (SSE)

客户端传入 db 参数，服务器从 db_mapping 表查找连接配置。
    http://localhost:8000/sse?db=singa
"""

import os
import contextvars
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

# 当前请求上下文（使用 contextvars 实现协程级隔离，并发安全）
# 每个 SSE 连接/请求有自己独立的上下文，不会互相覆盖
_current_db_config: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "current_db_config", default={}
)
_current_db_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_db_key", default="default"
)


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
    """获取当前协程绑定的数据库配置（并发安全）"""
    return _current_db_config.get()


def get_current_db_key() -> str:
    """获取当前协程绑定的数据库标识符（并发安全）"""
    return _current_db_key.get()


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
    """
    纯 ASGI 中间件，负责：
    1. 从 query_string 中提取 db 参数并设置当前请求的数据库配置
    2. SSE 连接建立时创建埋点 session，断开时关闭 session

    去重机制（引用计数）：
    - Cursor 等客户端会同时建立多条 SSE 连接（主连接 + 备用连接 + 重连）
    - 同一客户端（ip + db_key）的所有 SSE 连接共享同一个 session
    - 使用引用计数跟踪活跃连接数，最后一条连接断开时才关闭 session

    使用 contextvars 实现协程级隔离：
    - 每个 SSE 连接有独立的上下文，并发请求不会互相覆盖
    - SSE 长连接期间，session_id 在协程 contextvars 中持续存在 
    - 同一 SSE 连接内的所有工具调用共享同一个 session
    """

    # 活跃 session 引用计数：{(client_ip, db_key): (session_id, ref_count)}
    _active_sessions: Dict[tuple, list] = {}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            qs = scope.get("query_string", b"").decode()
            path = scope.get("path", "")
            db_key = None

            # 解析 db 参数
            if qs:
                params = parse_qs(qs)
                if "db" in params:
                    db_key = params["db"][0]
                    _current_db_key.set(db_key)            # 只影响当前协程
                    db_config = get_db_config(db_key)
                    if db_config:
                        _current_db_config.set(db_config)  # 只影响当前协程
                        logger.debug(f"数据库映射: {db_key}")
                    else:
                        logger.warning(f"未找到映射: {db_key}")

            # SSE 连接建立 → 获取或创建埋点 session（引用计数 +1）
            if path == "/sse":
                session_id, cache_key = self._acquire_session(scope, db_key)
                try:
                    await self.app(scope, receive, send)
                finally:
                    # SSE 断开 → 引用计数 -1，归零时关闭 session
                    self._release_session(session_id, cache_key)
                return

        await self.app(scope, receive, send)

    def _acquire_session(self, scope, db_key: str) -> tuple:
        """
        获取或创建埋点会话（引用计数 +1）

        同一客户端的多条 SSE 连接共享同一个 session，
        通过引用计数确保最后一条连接断开时才关闭。

        Returns:
            (session_id, cache_key)
        """
        try:
            from db.analytics_config import is_analytics_enabled, set_analytics_session_id
            if not is_analytics_enabled():
                return "", None

            client = scope.get("client")
            client_ip = client[0] if client else None
            cache_key = (client_ip, db_key)

            # 已有活跃 session → 引用计数 +1，直接复用
            if cache_key in self._active_sessions:
                entry = self._active_sessions[cache_key]
                entry[1] += 1  # ref_count += 1
                set_analytics_session_id(entry[0])
                logger.info(
                    f"埋点会话已复用: session={entry[0]}, db={db_key}, "
                    f"ref_count={entry[1]}"
                )
                return entry[0], cache_key

            # 无活跃 session → 创建新的
            from db.analytics_service import get_analytics_service

            headers = dict(scope.get("headers", []))
            user_agent = headers.get(b"user-agent", b"").decode("utf-8", errors="ignore")

            service = get_analytics_service()
            session_id = service.create_session(
                client_ip=client_ip,
                user_agent=user_agent or None,
                db_key=db_key
            )
            set_analytics_session_id(session_id)

            # 初始引用计数 = 1
            self._active_sessions[cache_key] = [session_id, 1]
            logger.info(f"埋点会话已创建: session={session_id}, db={db_key}, ip={client_ip}")
            return session_id, cache_key

        except Exception as e:
            logger.warning(f"创建埋点会话失败: {e}")
            return "", None

    def _release_session(self, session_id: str, cache_key: tuple):
        """
        释放埋点会话（引用计数 -1）

        引用计数归零时关闭 session 并清理缓存。
        """
        if not session_id or not cache_key:
            return

        try:
            entry = self._active_sessions.get(cache_key)
            if not entry or entry[0] != session_id:
                return

            entry[1] -= 1  # ref_count -= 1
            logger.debug(f"埋点会话释放: session={session_id}, ref_count={entry[1]}")

            if entry[1] <= 0:
                # 最后一条连接断开 → 关闭 session
                del self._active_sessions[cache_key]

                from db.analytics_service import get_analytics_service
                service = get_analytics_service()
                service.close_session(session_id)
                logger.info(f"埋点会话已关闭: session={session_id}")

        except Exception as e:
            logger.warning(f"释放埋点会话失败: {e}")


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

    logger.info(f"""
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
        limit_concurrency=None,    # SSE 长连接场景不限制并发，避免连接耗尽导致 503 死循环
        limit_max_requests=10000,  # 单 worker 处理请求上限后自动重启（防内存泄漏）
    )
