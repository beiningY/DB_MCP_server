"""
数据库连接池管理
实现连接复用，提高性能

该模块提供数据库连接池的统一管理，避免每次查询都创建新的连接。
相同数据库配置的请求会自动复用连接池。

主要功能：
- 连接池自动创建和复用
- 线程安全的连接池管理
- 连接统计和监控接口
- 连接测试功能
- 应用关闭时自动清理

使用示例：
    from db_mcp.connection_pool import get_engine, close_all_pools

    # 获取引擎（自动创建或复用连接池）
    engine = get_engine("localhost", 3306, "root", "password", "mydb")

    # 使用完后关闭所有连接池
    close_all_pools()
"""

from typing import Dict, Optional, Any
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
import threading
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# 全局变量
# ============================================================================

# 全局连接池存储
# key: "host:port@username@database"
# value: SQLAlchemy Engine 实例
_pools: Dict[str, Engine] = {}
_pools_lock = threading.Lock()

# ============================================================================
# 默认配置
# ============================================================================

DEFAULT_POOL_SIZE = 5          # 连接池大小
DEFAULT_MAX_OVERFLOW = 10      # 最大溢出连接数
DEFAULT_POOL_TIMEOUT = 30      # 获取连接超时时间（秒）
DEFAULT_POOL_RECYCLE = 3600    # 连接回收时间（秒）


# ============================================================================
# 公共函数
# ============================================================================

def _make_pool_key(host: str, port: int, username: str, database: str) -> str:
    """
    生成连接池的唯一 key

    注意：不包含 password 以避免在日志中暴露

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        database: 数据库名

    Returns:
        连接池唯一标识字符串
    """
    return f"{host}:{port}@{username}@{database}"


def _build_db_url(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str
) -> str:
    """
    构建数据库连接 URL

    自动转义密码中的特殊字符。

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        password: 数据库密码
        database: 数据库名

    Returns:
        SQLAlchemy 连接 URL
    """
    from urllib.parse import quote_plus
    safe_password = quote_plus(password)

    return f"mysql+pymysql://{username}:{safe_password}@{host}:{int(port)}/{database}?charset=utf8mb4"


def get_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
    pool_timeout: int = DEFAULT_POOL_TIMEOUT,
    pool_recycle: int = DEFAULT_POOL_RECYCLE,
    pool_pre_ping: bool = True,
    echo: bool = False,
) -> Engine:
    """
    获取数据库引擎（带连接池）

    相同配置的请求会复用同一个连接池。

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        password: 数据库密码
        database: 数据库名
        pool_size: 连接池大小（默认 5）
        max_overflow: 最大溢出连接数（默认 10）
        pool_timeout: 获取连接超时时间（秒，默认 30）
        pool_recycle: 连接回收时间（秒，默认 3600）
        pool_pre_ping: 连接前检查有效性（默认 True）
        echo: 是否打印 SQL 语句（默认 False）

    Returns:
        SQLAlchemy Engine 实例

    Examples:
        >>> engine = get_engine("localhost", 3306, "root", "pass", "mydb")
        >>> # 相同配置会复用连接池
        >>> engine2 = get_engine("localhost", 3306, "root", "pass", "mydb")
        >>> assert engine is engine2
    """
    pool_key = _make_pool_key(host, port, username, database)

    # 双重检查锁定
    if pool_key not in _pools:
        with _pools_lock:
            if pool_key not in _pools:
                db_url = _build_db_url(host, port, username, password, database)

                logger.debug(f"创建新的连接池: {pool_key}")

                engine = create_engine(
                    db_url,
                    poolclass=QueuePool,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    pool_timeout=pool_timeout,
                    pool_recycle=pool_recycle,
                    pool_pre_ping=pool_pre_ping,
                    echo=echo,
                )

                _pools[pool_key] = engine
            else:
                logger.debug(f"复用现有连接池: {pool_key}")
    else:
        logger.debug(f"复用现有连接池: {pool_key}")

    return _pools[pool_key]


def get_or_create_engine(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str,
    **kwargs
) -> Engine:
    """
    获取或创建数据库引擎（便捷函数）

    与 get_engine 相同，但提供更简洁的调用方式。

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        password: 数据库密码
        database: 数据库名
        **kwargs: 额外的连接池配置参数

    Returns:
        SQLAlchemy Engine 实例
    """
    return get_engine(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        **kwargs
    )


def close_pool(host: str, port: int, username: str, database: str):
    """
    关闭指定配置的连接池

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        database: 数据库名

    Examples:
        >>> close_pool("localhost", 3306, "root", "mydb")
    """
    pool_key = _make_pool_key(host, port, username, database)

    with _pools_lock:
        if pool_key in _pools:
            logger.info(f"关闭连接池: {pool_key}")
            _pools[pool_key].dispose()
            del _pools[pool_key]
        else:
            logger.warning(f"尝试关闭不存在的连接池: {pool_key}")


def close_all_pools():
    """
    关闭所有连接池

    通常在应用关闭时调用。
    """
    with _pools_lock:
        pool_count = len(_pools)
        if pool_count > 0:
            logger.info(f"关闭所有连接池（共 {pool_count} 个）")
            for engine in _pools.values():
                engine.dispose()
            _pools.clear()
        else:
            logger.debug("没有需要关闭的连接池")


def get_pool_stats() -> Dict[str, Dict[str, Any]]:
    """
    获取连接池统计信息

    Returns:
        字典，key 为 pool_key，value 为统计信息
        - pool_size: 连接池大小
        - checked_in: 已归还的连接数
        - checked_out: 已借出的连接数
        - overflow: 溢出的连接数
        - max_overflow: 最大溢出数

    Examples:
        >>> stats = get_pool_stats()
        >>> for key, info in stats.items():
        ...     print(f"{key}: {info['checked_out']}/{info['pool_size']} 连接在使用")
    """
    stats = {}

    with _pools_lock:
        for key, engine in _pools.items():
            pool = engine.pool
            stats[key] = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "max_overflow": pool._max_overflow,
            }

    return stats


def get_pool_info() -> Dict[str, Any]:
    """
    获取连接池概览信息

    Returns:
        包含连接池概览的字典
        - total_pools: 总连接池数
        - pool_keys: 连接池 key 列表
        - stats: 详细统计信息

    Examples:
        >>> info = get_pool_info()
        >>> print(f"共有 {info['total_pools']} 个连接池")
    """
    with _pools_lock:
        return {
            "total_pools": len(_pools),
            "pool_keys": list(_pools.keys()),
            "stats": get_pool_stats(),
        }


def test_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database: str
) -> tuple[bool, str]:
    """
    测试数据库连接

    Args:
        host: 数据库主机
        port: 数据库端口
        username: 数据库用户名
        password: 数据库密码
        database: 数据库名

    Returns:
        (success, message) 元组
        - success: 连接是否成功
        - message: 结果消息

    Examples:
        >>> success, msg = test_connection("localhost", 3306, "root", "pass", "mydb")
        >>> if success:
        ...     print("连接成功")
    """
    try:
        from sqlalchemy import text

        engine = get_engine(host, port, username, password, database)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
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

class DBConnection:
    """
    数据库连接上下文管理器

    提供便捷的数据库连接管理，自动处理连接的获取和释放。

    使用方式：
        with DBConnection(host, port, username, password, database) as conn:
            result = conn.execute(text("SELECT * FROM users"))

    注意：由于使用连接池，连接不会真正关闭，而是归还到连接池。
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
        """
        初始化上下文管理器

        Args:
            host: 数据库主机
            port: 数据库端口
            username: 数据库用户名
            password: 数据库密码
            database: 数据库名
            **kwargs: 额外的连接池配置参数
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.kwargs = kwargs
        self.engine = None
        self.connection = None

    def __enter__(self):
        """
        进入上下文，获取数据库连接

        Returns:
            数据库连接对象
        """
        self.engine = get_engine(
            self.host,
            self.port,
            self.username,
            self.password,
            self.database,
            **self.kwargs
        )
        self.connection = self.engine.connect()
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        退出上下文，释放连接

        注意：不关闭 engine，因为它是共享的连接池。
        """
        if self.connection:
            self.connection.close()


# ============================================================================
# 清理函数
# ============================================================================

def cleanup():
    """
    清理所有连接池资源

    通常在应用关闭时调用。与 close_all_pools() 相同。
    """
    close_all_pools()
