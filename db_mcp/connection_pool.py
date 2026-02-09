"""
数据库连接池管理

使用 SQLAlchemy 2.0 Async (AsyncEngine + AsyncSession) + asyncmy 驱动
实现完全异步、生产级别的数据库连接池。

主要特性：
- 使用 SQLAlchemy 2.0 异步 API
- 完全异步的连接获取和释放
- 支持多连接池管理（不同数据库配置）
- LRU 连接池淘汰机制
- 连接健康检查（pool_pre_ping）
- 连接回收（pool_recycle）
- 完整的监控和统计接口

使用示例：
    from db_mcp.connection_pool import get_pool, execute_query

    # 执行查询
    results = await execute_query(
        host="localhost",
        port=3306,
        username="root",
        password="password",
        database="mydb",
        sql="SELECT * FROM users LIMIT 10"
    )
"""

import asyncio
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote_plus
from datetime import datetime
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

from .logger import get_logger

# 加载环境变量
load_dotenv()

logger = get_logger("mcp.async_pool")

# ============================================================================
# 全局变量
# ============================================================================

# 连接池存储
# key: "host:port@username@database"
# value: {"engine": AsyncEngine, "last_used": timestamp, "pool_size": int, "max_overflow": int}
_pools: Dict[str, Dict[str, Any]] = {}
_pools_lock = asyncio.Lock()

# ============================================================================
# 配置（从环境变量读取）
# ============================================================================

def _get_int_env(key: str, default: int) -> int:
    """从环境变量读取整数配置"""
    try:
        value = os.getenv(key, str(default))
        return int(value)
    except (ValueError, TypeError):
        return default

# 连接池配置
DEFAULT_POOL_SIZE = _get_int_env("DB_POOL_SIZE", 5)
DEFAULT_MAX_OVERFLOW = _get_int_env("DB_MAX_OVERFLOW", 10)
DEFAULT_POOL_TIMEOUT = _get_int_env("DB_POOL_TIMEOUT", 30)
DEFAULT_POOL_RECYCLE = _get_int_env("DB_POOL_RECYCLE", 3600)
DB_POOL_MAX_SIZE = _get_int_env("DB_POOL_MAX_SIZE", 50)  # 最大连接池数量限制

# ============================================================================
# 辅助函数
# ============================================================================


def _make_pool_key(host: str, port: int, username: str, database: str) -> str:
    """生成连接池的唯一 key"""
    return f"{host}:{port}@{username}@{database}"


def _build_async_db_url(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    driver: str = "mysql+asyncmy://"
) -> str:
    """
    构建异步数据库连接 URL

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        driver: 驱动前缀，默认使用 asyncmy（性能优于 aiomysql）

    Returns:
        SQLAlchemy 异步连接 URL
    """
    safe_password = quote_plus(password, safe='')
    return f"{driver}{username}:{safe_password}@{host}:{int(port)}/{database}?charset=utf8mb4"


async def _create_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
    pool_timeout: int = DEFAULT_POOL_TIMEOUT,
    pool_recycle: int = DEFAULT_POOL_RECYCLE,
    echo: bool = False,
) -> AsyncEngine:
    """
    创建新的异步引擎

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        pool_size: 核心连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 获取连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        echo: 是否打印 SQL

    Returns:
        AsyncEngine 实例
    """
    db_url = _build_async_db_url(host, port, username, password, database)

    engine = create_async_engine(
        db_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,  # 连接前检查有效性
        echo=echo,
    )

    return engine


async def _evict_old_pools():
    """
    淘汰最久未使用的连接池（LRU）

    当连接池数量超过限制时，清理最久未使用的连接池。
    """
    async with _pools_lock:
        if len(_pools) <= DB_POOL_MAX_SIZE:
            return

        # 按最后使用时间排序
        sorted_pools = sorted(
            _pools.items(),
            key=lambda x: x[1]["last_used"]
        )

        # 关闭最旧的连接池
        to_close = len(_pools) - DB_POOL_MAX_SIZE
        for key, pool_info in sorted_pools[:to_close]:
            try:
                await pool_info["engine"].dispose()
                del _pools[key]
                logger.info(f"关闭空闲连接池: {key}")
            except Exception as e:
                logger.error(f"关闭连接池失败 {key}: {e}")


# ============================================================================
# 公共 API
# ============================================================================


async def get_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
    pool_timeout: int = DEFAULT_POOL_TIMEOUT,
    pool_recycle: int = DEFAULT_POOL_RECYCLE,
    echo: bool = False,
) -> AsyncEngine:
    """
    获取或创建异步引擎

    相同配置的请求会复用同一个连接池。

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        pool_size: 核心连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 获取连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        echo: 是否打印 SQL

    Returns:
        AsyncEngine 实例
    """
    pool_key = _make_pool_key(host, port, username, database)

    async with _pools_lock:
        # 检查是否已存在
        if pool_key in _pools:
            _pools[pool_key]["last_used"] = time.time()
            return _pools[pool_key]["engine"]

        # 检查连接池数量限制
        if len(_pools) >= DB_POOL_MAX_SIZE:
            logger.warning(
                f"连接池数量达到上限 ({DB_POOL_MAX_SIZE})，触发 LRU 淘汰"
            )
        else:
            # 创建新引擎
            logger.debug(f"创建新的异步引擎: {pool_key}")
            engine = await _create_engine(
                host, port, username, password, database,
                pool_size, max_overflow, pool_timeout, pool_recycle, echo
            )
            _pools[pool_key] = {
                "engine": engine,
                "last_used": time.time(),
                "pool_size": pool_size,
                "max_overflow": max_overflow,
            }
            return engine

    # 在锁外执行淘汰（避免死锁）
    await _evict_old_pools()

    # 再次尝试获取或创建
    async with _pools_lock:
        if pool_key not in _pools:
            engine = await _create_engine(
                host, port, username, password, database,
                pool_size, max_overflow, pool_timeout, pool_recycle, echo
            )
            _pools[pool_key] = {
                "engine": engine,
                "last_used": time.time(),
                "pool_size": pool_size,
                "max_overflow": max_overflow,
            }
        _pools[pool_key]["last_used"] = time.time()
        return _pools[pool_key]["engine"]


def get_pool(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
    pool_timeout: int = DEFAULT_POOL_TIMEOUT,
    pool_recycle: int = DEFAULT_POOL_RECYCLE,
    echo: bool = False,
) -> AsyncEngine:
    """
    获取或创建异步引擎（同步包装函数，提供兼容性）

    注意：这个函数实际上是异步的，应该用 await get_engine()。
    保留此函数是为了向后兼容。

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        pool_size: 核心连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 获取连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        echo: 是否打印 SQL

    Returns:
        AsyncEngine 实例（协程）
    """
    return get_engine(
        host, port, username, password, database,
        pool_size, max_overflow, pool_timeout, pool_recycle, echo
    )


async def get_session(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
) -> AsyncSession:
    """
    获取异步会话

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        pool_size: 核心连接池大小
        max_overflow: 最大溢出连接数

    Returns:
        AsyncSession 实例
    """
    engine = await get_engine(
        host, port, username, password, database,
        pool_size, max_overflow
    )

    # 创建或获取 session factory
    async with _pools_lock:
        pool_key = _make_pool_key(host, port, username, database)
        if "session_factory" not in _pools[pool_key]:
            _pools[pool_key]["session_factory"] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

    return _pools[pool_key]["session_factory"]()


async def execute_query(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    异步执行 SQL 查询

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        sql: SQL 查询语句
        params: 查询参数（字典形式，支持命名参数）

    Returns:
        (结果列表, 列名列表) 元组
    """
    engine = await get_engine(host, port, username, password, database)

    async with engine.begin() as conn:
        result = await conn.execute(text(sql), params or {})
        rows = result.fetchall()

        # 获取列名
        columns = list(result.keys()) if rows else []

        # 转换为字典列表
        data = []
        for row in rows:
            row_dict = {}
            for key, value in zip(columns, row):
                row_dict[key] = _convert_value(value)
            data.append(row_dict)

        return data, columns


def _convert_value(value: Any) -> Any:
    """
    转换数据库值为 JSON 可序列化类型

    Args:
        value: 数据库返回的值

    Returns:
        转换后的值
    """
    if value is None:
        return None

    # 转换 Decimal 为 float
    if hasattr(value, '__class__') and 'Decimal' in str(value.__class__):
        return float(value)

    # 转换日期时间为字符串
    if hasattr(value, 'isoformat'):
        return value.isoformat()

    # 转换 bytes 为字符串
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.hex()

    return value


async def execute_query_many(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    sql: str,
    params_list: List[Dict[str, Any]],
) -> int:
    """
    异步执行多个 SQL 查询（批量操作）

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        sql: SQL 查询语句
        params_list: 参数字典列表

    Returns:
        影响的总行数
    """
    engine = await get_engine(host, port, username, password, database)

    async with engine.begin() as conn:
        total_rowcount = 0
        for params in params_list:
            result = await conn.execute(text(sql), params)
            total_rowcount += result.rowcount
        return total_rowcount


async def close_pool(
    host: str,
    port: int,
    username: str,
    database: str,
):
    """
    关闭指定配置的连接池

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        database: 数据库名
    """
    pool_key = _make_pool_key(host, port, username, database)

    async with _pools_lock:
        if pool_key in _pools:
            engine = _pools[pool_key]["engine"]
            await engine.dispose()
            del _pools[pool_key]
            logger.info(f"关闭连接池: {pool_key}")


async def close_all_pools():
    """关闭所有连接池"""
    async with _pools_lock:
        pool_count = len(_pools)
        if pool_count > 0:
            logger.info(f"关闭所有连接池（共 {pool_count} 个）")
            for pool_info in _pools.values():
                await pool_info["engine"].dispose()
            _pools.clear()
        else:
            logger.debug("没有需要关闭的连接池")


def get_pool_stats() -> Dict[str, Dict[str, Any]]:
    """
    获取连接池统计信息（同步函数）

    Returns:
        连接池统计信息字典
    """
    stats = {}
    for key, pool_info in _pools.items():
        engine = pool_info["engine"]
        pool = engine.pool
        stats[key] = {
            "pool_size": pool_info["pool_size"],
            "max_overflow": pool_info["max_overflow"],
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "last_used": datetime.fromtimestamp(pool_info["last_used"]).isoformat(),
        }
    return stats


async def get_pool_stats_async() -> Dict[str, Dict[str, Any]]:
    """
    获取连接池统计信息（异步函数）

    相比同步版本，这个函数会在锁保护下读取，确保线程安全。

    Returns:
        连接池统计信息字典
    """
    async with _pools_lock:
        return get_pool_stats()


def get_pool_info() -> Dict[str, Any]:
    """
    获取连接池概览信息

    Returns:
        包含连接池概览的字典
    """
    return {
        "total_pools": len(_pools),
        "max_pools": DB_POOL_MAX_SIZE,
        "pool_keys": list(_pools.keys()),
        "stats": get_pool_stats(),
    }


async def test_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str
) -> Tuple[bool, str]:
    """
    测试数据库连接

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名

    Returns:
        (是否成功, 消息) 元组
    """
    try:
        engine = await get_engine(host, port, username, password, database)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            if row and row[0] == 1:
                return True, "连接成功"
        return True, "连接成功"
    except SQLAlchemyError as e:
        return False, f"数据库连接失败: {str(e)}"
    except Exception as e:
        return False, f"连接测试异常: {str(e)}"


# ============================================================================
# 上下文管理器
# ============================================================================

class AsyncDBConnection:
    """
    异步数据库连接上下文管理器

    使用方式：
        async with AsyncDBConnection(host, port, username, password, database) as conn:
            result = await conn.execute(text("SELECT * FROM users"))
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.kwargs = kwargs
        self.engine = None
        self.connection = None

    async def __aenter__(self):
        self.engine = await get_engine(
            self.host, self.port, self.username,
            self.password, self.database, **self.kwargs
        )
        self.connection = await self.engine.connect()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            await self.connection.close()


class AsyncDBSession:
    """
    异步数据库会话上下文管理器

    使用方式：
        async with AsyncDBSession(host, port, username, password, database) as session:
            result = await session.execute(text("SELECT * FROM users"))
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.kwargs = kwargs
        self.session = None

    async def __aenter__(self):
        self.session = await get_session(
            self.host, self.port, self.username,
            self.password, self.database, **self.kwargs
        )
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
