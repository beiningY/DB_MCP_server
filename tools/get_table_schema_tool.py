"""
数据库表结构查询工具
从 MySQL information_schema 实时获取表的字段、类型、注释等元数据信息
集成异步连接池和统一错误处理
"""

from typing import Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.tools import tool

# 导入异步连接池和错误处理模块
from db_mcp.connection_pool import get_engine
from db_mcp.errors import (
    format_error_response,
    ErrorCode,
)
from db_mcp.logger import get_logger

# 获取日志器
logger = get_logger("mcp.tool.get_table_schema")


def format_table_info(
    table_name: str,
    table_comment: str,
    columns: list,
    indexes: list = None
) -> str:
    """
    将表结构信息格式化为文本

    Args:
        table_name: 表名
        table_comment: 表注释
        columns: 字段信息列表
        indexes: 索引信息列表（可选）

    Returns:
        格式化的文本字符串
    """
    lines = [
        f"【表名】{table_name}",
        f"【表注释】{table_comment}" if table_comment else "",
        "",
        "【字段列表】"
    ]

    # 收集主键信息
    primary_keys = set()
    if indexes:
        for idx in indexes:
            if idx.get("index_type") == "PRIMARY":
                primary_keys.add(idx.get("column_name"))

    # 处理字段信息
    for col in columns:
        col_name = col.get("column_name", "")
        column_type = col.get("column_type", "")
        is_nullable = col.get("is_nullable", "YES") == "YES"
        column_comment = col.get("column_comment", "")
        extra = col.get("extra", "")

        # 构建字段描述
        col_desc = f"  - {col_name} ({column_type})"

        # 添加标记
        marks = []
        if col_name in primary_keys:
            marks.append("主键")
        if not is_nullable:
            marks.append("非空")
        if extra:
            marks.append(extra)

        if marks:
            col_desc += f" [{', '.join(marks)}]"

        # 添加注释
        if column_comment:
            col_desc += f": {column_comment}"

        lines.append(col_desc)

    # 过滤空行并拼接
    return "\n".join(line for line in lines if line is not None and line != "")


@tool
async def get_table_schema(
    table_name: Optional[str] = None,
    host: str = "localhost",
    port: int = 3306,
    username: str = "root",
    password: str = "",
    database: str = "information_schema"
) -> str:
    """
    获取数据库表的结构信息（字段、类型、注释等），返回易读的文本格式
    实时从 MySQL information_schema 查询，支持动态数据库连接

    功能特性：
    - 支持模糊匹配表名
    - 显示字段详细信息（类型、主键、非空、注释）
    - 支持查询所有表摘要
    - 使用异步连接池提高性能
    - 完整的错误处理和日志记录

    Args:
        table_name: 表名。
            - 如果为 None：返回所有表的摘要列表
            - 如果指定表名：返回该表的详细结构（包含所有字段信息）
        host: 数据库主机地址，默认 "localhost"
        port: 数据库端口，默认 3306
        username: 数据库用户名，默认 "root"
        password: 数据库密码，默认 ""
        database: 目标数据库名称，默认 "information_schema"

    Returns:
        文本格式的表结构信息：
        - 表名、表注释
        - 字段名、类型、注释
        - 主键、非空等标记

    Examples:
        >>> await get_table_schema.invoke({"host": "localhost", "database": "mydb"})  # 获取所有表
        >>> await get_table_schema.invoke({"table_name": "users", "host": "localhost", "database": "mydb"})  # 获取指定表
    """
    # ========== 1. 基本参数验证 ==========
    if not host:
        logger.warning("获取表结构时缺少主机地址")
        return format_error_response(
            "数据库主机地址 (host) 不能为空",
            ErrorCode.MISSING_REQUIRED_PARAM
        )

    # 记录查询请求
    logger.info(
        f"获取表结构请求",
        extra={
            "host": host,
            "database": database,
            "table_name": table_name if table_name else "（所有表）"
        }
    )

    # ========== 2. 获取数据库连接（使用异步连接池） ==========
    try:
        # 连接到 information_schema 查询元数据
        engine = await get_engine(
            host=host,
            port=port,
            username=username,
            password=password,
            database="information_schema"
        )

        async with engine.connect() as conn:
            # ========== 3. 如果未指定表名，返回所有表的摘要 ==========
            if not table_name:
                return await _get_all_tables_summary(conn, database)

            # ========== 4. 查询指定表的详细结构 ==========
            return await _get_table_detail(conn, table_name, database)

    except SQLAlchemyError as e:
        error_msg = str(e)
        logger.error(
            f"数据库查询错误: {error_msg}",
            extra={
                "host": host,
                "database": database,
                "table_name": table_name,
                "exception_type": type(e).__name__
            },
            exc_info=True
        )

        # 判断错误类型
        error_msg_lower = error_msg.lower()
        if "connection" in error_msg_lower:
            return format_error_response(
                f"数据库连接错误: {error_msg}",
                ErrorCode.DB_CONNECTION_ERROR
            )
        else:
            return format_error_response(
                f"数据库查询错误: {error_msg}",
                ErrorCode.DB_QUERY_ERROR
            )

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"未知错误: {error_msg}",
            extra={
                "host": host,
                "database": database,
                "table_name": table_name,
                "exception_type": type(e).__name__
            },
            exc_info=True
        )

        return format_error_response(
            f"未知错误: {error_msg}",
            ErrorCode.UNKNOWN_ERROR
        )


async def _get_all_tables_summary(conn, database: str) -> str:
    """
    获取数据库中所有表的摘要

    Args:
        conn: 数据库连接
        database: 数据库名

    Returns:
        表摘要文本
    """
    tables_sql = text("""
        SELECT
            TABLE_NAME,
            TABLE_COMMENT,
            ENGINE,
            TABLE_ROWS
        FROM TABLES
        WHERE TABLE_SCHEMA = :database
        AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)

    result = await conn.execute(tables_sql, {"database": database})
    tables = result.fetchall()

    logger.info(f"查询到 {len(tables)} 个表", extra={"database": database})

    lines = [
        f"数据库 {database} 表结构摘要",
        f"共 {len(tables)} 个表",
        "=" * 60,
        ""
    ]

    for table in tables:
        t_name = table[0]
        t_comment = table[1] or ""
        engine_type = table[2] or ""
        row_count = table[3] or 0

        lines.append(f"  • {t_name}")
        if t_comment:
            lines.append(f"    注释: {t_comment}")
        if engine_type:
            lines.append(f"    引擎: {engine_type}, 估算行数: {row_count}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("提示: 使用 get_table_schema('表名') 查看具体表的详细结构")

    return "\n".join(lines)


async def _get_table_detail(conn, table_name: str, database: str) -> str:
    """
    获取指定表的详细信息

    Args:
        conn: 数据库连接
        table_name: 表名
        database: 数据库名

    Returns:
        表详细信息文本或错误消息
    """
    table_name_lower = table_name.lower()

    # ========== 1. 检查表是否存在 ==========
    check_sql = text("""
        SELECT TABLE_NAME, TABLE_COMMENT
        FROM TABLES
        WHERE TABLE_SCHEMA = :database
        AND LOWER(TABLE_NAME) = :table_name
    """)

    result = await conn.execute(check_sql, {"database": database, "table_name": table_name_lower})
    table_info = result.fetchone()

    if not table_info:
        # 表不存在，尝试模糊匹配
        logger.warning(
            f"表不存在: {table_name}",
            extra={"database": database, "requested_table": table_name}
        )

        similar_sql = text("""
            SELECT TABLE_NAME
            FROM TABLES
            WHERE TABLE_SCHEMA = :database
            AND LOWER(TABLE_NAME) LIKE :pattern
            ORDER BY TABLE_NAME
            LIMIT 10
        """)
        result = await conn.execute(similar_sql, {"database": database, "pattern": f"%{table_name_lower}%"})
        similar_tables = [row[0] for row in result.fetchall()]

        msg = f"表 '{table_name}' 在数据库 '{database}' 中不存在\n"
        if similar_tables:
            msg += f"\n你可能想查找以下表：\n"
            for t in similar_tables:
                msg += f"  • {t}\n"
        return msg

    actual_table_name = table_info[0]
    table_comment = table_info[1] or ""

    # ========== 2. 查询字段信息 ==========
    columns_sql = text("""
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            COLUMN_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_COMMENT,
            EXTRA,
            ORDINAL_POSITION
        FROM COLUMNS
        WHERE TABLE_SCHEMA = :database
        AND TABLE_NAME = :table_name
        ORDER BY ORDINAL_POSITION
    """)

    result = await conn.execute(columns_sql, {"database": database, "table_name": actual_table_name})
    columns = []
    for row in result.fetchall():
        columns.append({
            "column_name": row[0],
            "data_type": row[1],
            "column_type": row[2],
            "is_nullable": row[3],
            "column_default": row[4],
            "column_comment": row[5] or "",
            "extra": row[6] or ""
        })

    # ========== 3. 查询索引信息（用于识别主键） ==========
    indexes_sql = text("""
        SELECT
            INDEX_NAME,
            COLUMN_NAME,
            INDEX_TYPE,
            NON_UNIQUE
        FROM STATISTICS
        WHERE TABLE_SCHEMA = :database
        AND TABLE_NAME = :table_name
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """)

    result = await conn.execute(indexes_sql, {"database": database, "table_name": actual_table_name})
    indexes = []
    for row in result.fetchall():
        indexes.append({
            "index_name": row[0],
            "column_name": row[1],
            "index_type": row[2],
            "non_unique": row[3]
        })

    logger.info(
        f"查询表结构成功",
        extra={
            "table": actual_table_name,
            "column_count": len(columns),
            "index_count": len(indexes)
        }
    )

    # ========== 4. 格式化输出 ==========
    result_text = format_table_info(actual_table_name, table_comment, columns, indexes)
    result_text += f"\n\n 共 {len(columns)} 个字段"

    return result_text
