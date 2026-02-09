"""
DB Analysis MCP Server
支持通过 SSE 进行远程连接的 MCP 服务器
数据库连接配置从服务端数据库 (db_mapping 表) 中读取

该模块实现了一个基于 MCP (Model Context Protocol) 的数据分析服务器。
客户端只需传入数据库名（db 参数），服务器自动从 db_mapping 表中查找对应的连接配置。

主要功能：
- MCP 协议支持（仅 SSE 传输）
- 从数据库表加载映射配置（启动时缓存 + 请求时实时查询）
- 异步数据库连接池
- 健康检查端点

使用方式：
    # 方式1：直接启动
    python main.py

    # 方式2：使用 uvicorn
    uvicorn db_mcp.server:app --host 0.0.0.0 --port 8000

数据库映射配置：
    映射关系存储在 MCP Server 自身数据库的 db_mapping 表中。
    使用 db/init_db.py 管理映射记录：
        python db/init_db.py init    - 创建表
        python db/init_db.py data    - 插入映射数据
        python db/init_db.py query   - 查询所有映射

客户端连接示例：
    # 客户端只需传入数据库名（db_mapping 表中的 db_name 字段）
    http://localhost:8000/sse?db=singa
    http://localhost:8000/sse?db=sg-pay
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
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .logger import configure_logging, get_logger

# ============================================================================
# 全局变量
# ============================================================================

# 加载环境变量
load_dotenv()

# 配置日志（添加文件输出）
_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.path.join(_log_dir, "mcp-server.log")
)
logger = get_logger("mcp.server")

# 数据库映射配置（内存缓存）
# key: 客户端传入的数据库名（db_mapping 表中的 db_name）
# value: 完整的数据库连接配置 {"host", "port", "username", "password", "database"}
_db_mapping: Dict[str, Dict[str, Any]] = {}

# DBMappingService 单例（延迟初始化）
_db_mapping_service = None

# 当前请求的数据库配置（从 URL 参数中提取）
# 注意：这是请求级别的全局变量，每个请求会更新
_current_db_config: Dict[str, Any] = {}

# 当前请求的数据库标识符
_current_db_key: str = "default"


# ============================================================================
# 数据库映射配置管理（从 db_mapping 表加载）
# ============================================================================

def _get_mapping_service():
    """
    获取 DBMappingService 单例

    延迟初始化，避免启动时未配置数据库导致错误。

    Returns:
        DBMappingService 实例
    """
    global _db_mapping_service
    if _db_mapping_service is None:
        from db.database import DBMappingService
        _db_mapping_service = DBMappingService()
    return _db_mapping_service


def load_db_mapping() -> Dict[str, Dict[str, Any]]:
    """
    从 db_mapping 表加载所有活跃的数据库映射配置到内存缓存

    查询 MCP Server 自身数据库中的 db_mapping 表，
    将所有 is_active=True 的记录加载为映射字典。

    映射格式：
    {
        "singa": {"host": "xxx", "port": 3306, "username": "xxx", "password": "xxx", "database": "singa"},
        "sg-pay": {"host": "xxx", "port": 3306, "username": "xxx", "password": "xxx", "database": "sg-pay"},
    }

    Returns:
        数据库映射字典
    """
    global _db_mapping
    try:
        service = _get_mapping_service()
        _db_mapping = service.load_to_mapping_dict()
        logger.info(f"从数据库加载映射配置成功，共 {len(_db_mapping)} 条记录")
    except Exception as e:
        logger.error(f"从数据库加载映射配置失败: {e}")
        _db_mapping = {}
    return _db_mapping


def get_db_config(db_key: str) -> Dict[str, Any]:
    """
    获取指定数据库的完整连接配置

    优先从内存缓存查找；缓存未命中时，实时查询 db_mapping 表
    （处理运行期间新增映射的情况）。

    Args:
        db_key: 数据库标识符（db_mapping 表中的 db_name 字段）

    Returns:
        数据库配置字典，如果不存在则返回空字典
    """
    global _db_mapping

    # 1. 先从缓存查找
    if db_key in _db_mapping:
        return _db_mapping[db_key]

    # 2. 缓存未命中，实时查询数据库
    try:
        service = _get_mapping_service()
        mapping = service.get_by_db_name(db_key)
        if mapping and mapping.is_active:
            config = {
                "host": mapping.host,
                "port": mapping.port,
                "username": mapping.username,
                "password": mapping.password,
                "database": mapping.database,
            }
            # 写入缓存
            _db_mapping[db_key] = config
            logger.info(f"从数据库实时查询到映射: {db_key}")
            return config
        else:
            logger.warning(f"数据库中未找到活跃的映射: {db_key}")
            return {}
    except Exception as e:
        logger.error(f"查询数据库映射失败 ({db_key}): {e}")
        return {}


def get_all_db_keys() -> list:
    """
    获取所有已配置的数据库标识符

    Returns:
        数据库标识符列表
    """
    global _db_mapping
    if not _db_mapping:
        load_db_mapping()
    return list(_db_mapping.keys())


def refresh_db_mapping() -> Dict[str, Dict[str, Any]]:
    """
    刷新数据库映射缓存

    重新从 db_mapping 表加载所有活跃映射。
    可用于运行时动态刷新配置。

    Returns:
        更新后的数据库映射字典
    """
    global _db_mapping_service
    # 重置 service 以获取最新连接
    _db_mapping_service = None
    return load_db_mapping()


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


def get_current_db_key() -> str:
    """
    获取当前请求的数据库标识符

    Returns:
        数据库标识符字符串
    """
    return _current_db_key


def set_current_db_key(db_key: str):
    """
    设置当前请求的数据库标识符

    Args:
        db_key: 数据库标识符
    """
    global _current_db_key
    _current_db_key = db_key


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
        "version": "2.3.0",
        "features": [
            "db_table_mapping",
            "async_database_pool",
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
    db_keys = get_all_db_keys()
    return JSONResponse({
        "message": "MCP Server running",
        "endpoints": {
            "sse": "/sse - MCP SSE 连接端点",
            "health": "/health - 健康检查",
            "refresh": "/refresh - 刷新数据库映射缓存"
        },
        "available_databases": db_keys,
        "total": len(db_keys),
        "usage": "http://localhost:8000/sse?db=<database_name>",
        "mapping_source": "db_mapping table"
    })


async def refresh_mapping(request):
    """
    刷新数据库映射缓存端点

    重新从 db_mapping 表加载所有活跃映射。

    Returns:
        JSONResponse: 刷新结果
    """
    db_mapping = refresh_db_mapping()
    db_keys = list(db_mapping.keys())
    logger.info(f"手动刷新映射缓存，共 {len(db_keys)} 条记录")
    return JSONResponse({
        "status": "ok",
        "message": f"映射缓存已刷新，共 {len(db_keys)} 条记录",
        "available_databases": db_keys
    })


# ============================================================================
# 应用生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app):
    """
    应用生命周期管理

    启动时从 db_mapping 表加载映射配置，关闭时清理资源。
    """
    # 启动时
    logger.info("MCP Server 启动中...")

    # 从数据库表加载映射配置
    db_mapping = load_db_mapping()
    db_keys = list(db_mapping.keys())
    logger.info(f"从 db_mapping 表加载映射配置: {len(db_keys)} 个数据库")
    if db_keys:
        logger.info(f"可用数据库: {', '.join(db_keys)}")

    yield

    # 关闭时 - 清理连接池
    try:
        from .connection_pool import close_all_pools
        await close_all_pools()
        logger.info("连接池已清理")
    except ImportError:
        pass

    logger.info("MCP Server 关闭")


# ============================================================================
# 中间件：从 URL 参数提取数据库配置（服务端映射）
# ============================================================================

class DatabaseConfigMiddleware(BaseHTTPMiddleware):
    """
    从 URL 查询参数中提取数据库标识符并映射到完整配置

    客户端只需传入 db 参数（db_mapping 表中的 db_name），
    服务器自动从 db_mapping 表查找完整的连接信息。

    示例 URL：
        http://localhost:8000/sse?db=singa
        http://localhost:8000/sse?db=sg-pay
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

            # 方式：使用数据库映射
            if "db" in query_params:
                db_key = query_params.get("db", ["default"])[0]
                set_current_db_key(db_key)

                # 从映射中获取完整配置
                db_config = get_db_config(db_key)
                if db_config:
                    set_current_db_config(db_config)
                    logger.debug(f"使用数据库映射: {db_key}")
                else:
                    logger.warning(f"未找到数据库映射: {db_key}")

        response = await call_next(request)
        return response


# ============================================================================
# Starlette 应用创建
# ============================================================================

# 创建 Starlette 应用，挂载 MCP 路由
app = Starlette(
    debug=True,
    lifespan=lifespan,
    middleware=[
        Middleware(DatabaseConfigMiddleware)
    ],
    routes=[
        Route("/", endpoint=root),
        Route("/health", endpoint=health_check),
        Route("/refresh", endpoint=refresh_mapping),
        # 挂载 MCP SSE 路由
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
    - MCP_WORKERS: 工作进程数（默认 1，单进程模式）
    - MCP_LOOP: 事件循环类型：auto、uvloop、asyncio（默认 auto）

    数据库映射配置从 db_mapping 表加载（而非环境变量）。

    多进程配置建议：
    - CPU 密集型：workers = CPU 核心数
    - I/O 密集型（数据库查询）：workers = CPU 核心数 * 2
    - 单机部署建议：2-4 个 workers
    """
    port = int(os.getenv("MCP_PORT", "8000"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    workers = int(os.getenv("MCP_WORKERS", "1"))
    loop = os.getenv("MCP_LOOP", "auto")

    # 连接池配置（从环境变量读取）
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    max_concurrent = pool_size + max_overflow

    # 从 db_mapping 表加载映射
    db_mapping = load_db_mapping()
    db_keys = list(db_mapping.keys())

    # 构建数据库列表（隐藏密码）
    db_list_str = chr(10).join(
        f'  - {k}: {v["host"]}:{v["port"]}/{v["database"]}'
        for k, v in db_mapping.items()
    ) if db_mapping else "  （无映射记录，请检查 db_mapping 表）"

    # 同时输出到控制台和日志文件
    startup_msg = f"""
{'=' * 50}
DB Analysis MCP Server (v2.3)
{'=' * 50}
地址: http://{host}:{port}
SSE 端点: http://{host}:{port}/sse
健康检查: http://{host}:{port}/health
刷新映射: http://{host}:{port}/refresh

进程配置:
  - Workers: {workers}
  - Loop: {loop}

连接池配置:
  - Pool Size: {pool_size}
  - Max Overflow: {max_overflow}
  - 最大并发/进程: {max_concurrent}
  - 总最大并发: {max_concurrent * workers}

数据库映射 (来源: db_mapping 表, 共 {len(db_keys)} 个):
{db_list_str}

客户端使用:
  http://{host}:{port}/sse?db=<database_name>
{'=' * 50}"""
    print(startup_msg)
    logger.info(f"服务器启动 - 地址: http://{host}:{port}, workers={workers}")

    # 配置 uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        workers=workers,
        loop=loop,
        log_level="info",
    )

    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    start_server()
