"""
SQL 执行工具
支持动态连接 MySQL 数据库执行查询
集成 SQL 安全验证、连接池和统一错误处理
"""

import json
import time
import traceback
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.tools import tool

# 导入安全、连接池和错误处理模块
from db_mcp.sql_validator import (
    validate_sql,
    SQLValidationError,
    sanitize_limit
)
from db_mcp.connection_pool import execute_query
from db_mcp.errors import (
    format_error_response,
    format_success_response,
    ErrorCode,
    DBConnectionError,
    DBQueryError,
    SQLSecurityError as SQLSecurityErrorClass
)
from db_mcp.logger import get_logger

# 获取日志器
logger = get_logger("mcp.tool.execute_sql")


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


@tool
async def execute_sql_query(
    sql: str,
    host: str = "",
    port: int = 3306,
    username: str = "root",
    password: str = "",
    database: str = "information_schema",
    limit: Optional[int] = None
) -> str:
    """
    执行 SQL 查询并返回结果（支持动态数据库连接）

    功能特性：
    - 仅允许 SELECT 查询（通过 SQL 解析器严格验证）
    - 自动添加 LIMIT 保护（默认最多 100 行）
    - 使用异步连接池提高性能
    - 完整的错误处理和日志记录
    - 自动转换数据类型（Decimal、datetime 等）
    - 支持从上下文自动获取数据库配置

    Args:
        sql: 要执行的 SQL 查询语句（仅支持 SELECT 查询）
        host: 数据库主机地址（可选，如不提供则从上下文获取）
        port: 数据库端口，默认 3306
        username: 数据库用户名，默认 "root"
        password: 数据库密码，默认 ""
        database: 目标数据库名称，默认 "information_schema"
        limit: 最大返回行数，默认 100。如果 SQL 中已有 LIMIT，则使用 SQL 中的值

    Returns:
        JSON 格式的查询结果，包含：
        - success: 是否成功
        - data: 查询结果（列表形式，每行是一个字典）
        - columns: 列名列表
        - row_count: 返回行数
        - execution_time: 执行时间（毫秒）
        - message: 提示信息或错误信息

    Examples:
        >>> await execute_sql_query("SELECT * FROM users WHERE id = 1", host="localhost", database="mydb")
        >>> await execute_sql_query("SELECT COUNT(*) as cnt FROM orders", host="192.168.1.100", username="admin", password="pass123", database="shop", limit=1)
    """
    # ========== 日志：记录工具调用开始 ==========
    logger.info(f"[TOOL_CALL_START] execute_sql_query | sql={sql[:100]}{'...' if len(sql) > 100 else ''} | database={database}")

    # ========== 0. 从上下文获取数据库配置（如果未提供） ==========
    if not host:
        try:
            from tools import get_tool_db_config
            db_config = get_tool_db_config()
            if db_config.get("host"):
                host = db_config.get("host")
                port = db_config.get("port", port)
                username = db_config.get("username", username)
                password = db_config.get("password", password)
                database = db_config.get("database", database)
        except ImportError:
            pass

    # ========== 1. 基本参数验证 ==========
    sql = sql.strip() if sql else ""
    if not sql:
        logger.warning("收到空的 SQL 查询")
        return format_error_response(
            "SQL 查询不能为空",
            ErrorCode.INVALID_PARAMS
        )

    if not host:
        logger.warning("缺少数据库主机地址")
        return format_error_response(
            "数据库主机地址 (host) 不能为空，且未从上下文获取到配置",
            ErrorCode.MISSING_REQUIRED_PARAM
        )

    # 记录查询请求（不记录敏感信息）
    logger.info(
        f"收到 SQL 查询请求",
        extra={
            "host": host,
            "database": database,
            "sql_preview": sql[:100] if len(sql) > 100 else sql
        }
    )

    # ========== 2. SQL 安全验证 ==========
    try:
        is_valid, error_msg = validate_sql(sql, strict_mode=True)
        if not is_valid:
            logger.warning(
                f"SQL 安全检查失败: {error_msg}",
                extra={
                    "host": host,
                    "database": database,
                    "sql": sql[:200]
                }
            )
            return format_error_response(
                f"SQL 安全检查失败: {error_msg}",
                ErrorCode.SQL_VALIDATION_ERROR
            )
    except SQLValidationError as e:
        logger.warning(f"SQL 验证异常: {e.message}")
        # ========== 埋点：记录错误到 error_log ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code=ErrorCode.SQL_VALIDATION_ERROR,
                error_type="SQLValidationError",
                error_message=e.message,
                component="execute_sql_query",
                function_name="execute_sql_query"
            )
        except ImportError:
            pass
        return format_error_response(
            f"SQL 验证异常: {e.message}",
            ErrorCode.SQL_VALIDATION_ERROR
        )
    except Exception as e:
        logger.error(f"SQL 验证器异常: {e}", exc_info=True)
        # ========== 埋点：记录错误到 error_log ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code=ErrorCode.UNKNOWN_ERROR,
                error_type=type(e).__name__,
                error_message=str(e),
                component="execute_sql_query",
                function_name="execute_sql_query"
            )
        except ImportError:
            pass
        return format_error_response(
            "SQL 验证器异常",
            ErrorCode.UNKNOWN_ERROR
        )

    # ========== 3. 处理 LIMIT ==========
    limit = sanitize_limit(limit)

    # 检查 SQL 中是否已有 LIMIT
    sql_upper = sql.upper()
    if "LIMIT" not in sql_upper:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"

    # ========== 4. 执行查询（使用异步连接池） ==========
    try:
        logger.debug(f"执行异步查询: {host}:{port}/{database}")

        start_time = time.time()

        # 使用异步连接池执行查询
        data, columns = await execute_query(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
            sql=sql
        )

        execution_time = (time.time() - start_time) * 1000  # 转为毫秒

        # 记录成功日志
        logger.info(
            f"查询成功",
            extra={
                "host": host,
                "database": database,
                "row_count": len(data),
                "execution_time_ms": round(execution_time, 2)
            }
        )

        # 构建成功响应
        result_str = format_success_response(
            data=data,
            columns=columns,
            message=f"查询成功，返回 {len(data)} 行数据",
            execution_time=round(execution_time, 2)
        )

        # ========== 埋点：记录工具调用 + SQL 查询 ==========
        try:
            from db.analytics_config import log_tool_call, log_sql_query

            # 简单判断查询类型
            query_type = "simple"
            sql_upper_check = sql.upper()
            if " JOIN " in sql_upper_check:
                query_type = "join"
            elif " GROUP BY " in sql_upper_check:
                query_type = "aggregation"
            elif sql_upper_check.count(" SELECT") > 1:
                query_type = "subquery"

            # 记录到 tool_call_log（工具维度）
            log_tool_call(
                tool_name="execute_sql_query",
                tool_type="sql",
                parameters={"sql": sql[:500], "database": database},
                duration_ms=round(execution_time, 2),
                status="success",
                result_row_count=len(data),
                result_size_bytes=len(result_str.encode("utf-8")),
                result_summary=result_str[:1000],
                sql_executed=sql,
                sql_execution_time_ms=round(execution_time, 2),
                database_name=database
            )

            # 记录到 sql_query_log（SQL 维度）
            log_sql_query(
                sql_executed=sql,
                query_type=query_type,
                execution_time_ms=round(execution_time, 2),
                rows_returned=len(data),
                status="success",
                db_key=None,
                database_name=database
            )
        except ImportError:
            pass

        # ========== 日志：记录工具调用成功 ==========
        # 获取结果预览（前200字符）
        result_preview = result_str[:200].replace("\n", " ")
        logger.info(f"[TOOL_CALL_SUCCESS] execute_sql_query | rows={len(data)} | duration={execution_time:.0f}ms | output_preview={result_preview}")

        return result_str

    except SQLAlchemyError as e:
        # 数据库相关错误
        error_msg = str(e)
        db_error_time = (time.time() - start_time) * 1000
        logger.error(
            f"数据库查询错误: {error_msg}",
            extra={
                "host": host,
                "database": database,
                "exception_type": type(e).__name__
            },
            exc_info=True
        )

        # 判断错误类型
        error_msg_lower = error_msg.lower()
        if "timeout" in error_msg_lower or "time" in error_msg_lower:
            error_result = format_error_response(f"查询超时: {error_msg}", ErrorCode.DB_TIMEOUT)
        elif "connection" in error_msg_lower:
            error_result = format_error_response(f"数据库连接错误: {error_msg}", ErrorCode.DB_CONNECTION_ERROR)
        else:
            error_result = format_error_response(f"SQL 执行错误: {error_msg}", ErrorCode.DB_QUERY_ERROR)

        # ========== 埋点：记录工具调用失败 + SQL 查询失败 ==========
        try:
            from db.analytics_config import log_tool_call, log_sql_query, log_error
            log_tool_call(
                tool_name="execute_sql_query",
                tool_type="sql",
                parameters={"sql": sql[:500], "database": database},
                duration_ms=round(db_error_time, 2),
                status="error",
                error_message=error_msg[:500],
                result_summary=error_result[:1000],
                sql_executed=sql,
                database_name=database
            )
            log_sql_query(
                sql_executed=sql,
                status="error",
                error_message=error_msg[:500],
                db_key=None,
                database_name=database
            )
            # 统一写入 error_log 表
            log_error(
                error_code=ErrorCode.DB_QUERY_ERROR,
                error_type=type(e).__name__,
                error_message=error_msg[:500],
                component="execute_sql_query",
                function_name="execute_sql_query"
            )
        except ImportError:
            pass

        # ========== 日志：记录工具调用失败 ==========
        logger.error(f"[TOOL_CALL_ERROR] execute_sql_query | error={error_msg[:100]}")

        return error_result

    except Exception as e:
        # 其他未知错误
        error_msg = str(e)
        unknown_error_time = (time.time() - start_time) * 1000
        logger.error(
            f"未知错误: {error_msg}",
            extra={
                "host": host,
                "database": database,
                "exception_type": type(e).__name__,
                "traceback": traceback.format_exc()
            },
            exc_info=True
        )

        error_result = format_error_response(
            f"未知错误: {error_msg}",
            ErrorCode.UNKNOWN_ERROR,
            details={"type": type(e).__name__}
        )

        # ========== 埋点：记录工具调用失败 ==========
        try:
            from db.analytics_config import log_tool_call, log_sql_query, log_error
            log_tool_call(
                tool_name="execute_sql_query",
                tool_type="sql",
                parameters={"sql": sql[:500], "database": database},
                duration_ms=round(unknown_error_time, 2),
                status="error",
                error_message=error_msg[:500],
                result_summary=error_result[:1000],
                sql_executed=sql,
                database_name=database
            )
            log_sql_query(
                sql_executed=sql,
                status="error",
                error_message=error_msg[:500],
                db_key=None,
                database_name=database
            )
            # 统一写入 error_log 表
            log_error(
                error_code=ErrorCode.UNKNOWN_ERROR,
                error_type=type(e).__name__,
                error_message=error_msg[:500],
                component="execute_sql_query",
                function_name="execute_sql_query"
            )
        except ImportError:
            pass

        # ========== 日志：记录工具调用失败 ==========
        logger.error(f"[TOOL_CALL_ERROR] execute_sql_query | error={error_msg[:100]}")

        return error_result


# ============ 便捷函数 ============

async def execute_sql_safe(
    sql: str,
    host: str,
    port: int = 3306,
    username: str = "root",
    password: str = "",
    database: str = "information_schema",
    limit: int = 100
) -> Dict[str, Any]:
    """
    安全执行 SQL（返回字典而非 JSON 字符串）

    Args:
        sql: SQL 查询语句
        host: 数据库主机
        port: 数据库端口
        username: 用户名
        password: 密码
        database: 数据库名
        limit: 最大行数

    Returns:
        字典格式的查询结果
    """
    result = await execute_sql_query(
        sql=sql,
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        limit=limit
    )

    return json.loads(result)
