"""
统一错误处理
定义错误码和错误响应格式
"""
from enum import Enum
from typing import Optional, Dict, Any, Union
import json
import traceback


class ErrorCode(int, Enum):
    """错误码定义"""
    # 通用错误 1xxx
    UNKNOWN_ERROR = 1000
    INVALID_PARAMS = 1001
    MISSING_REQUIRED_PARAM = 1002
    TIMEOUT = 1003

    # 认证错误 2xxx
    UNAUTHORIZED = 2000
    INVALID_API_KEY = 2001
    ACCESS_DENIED = 2002

    # 数据库错误 3xxx
    DB_CONNECTION_ERROR = 3000
    DB_QUERY_ERROR = 3001
    DB_TIMEOUT = 3002
    DB_CONFIG_ERROR = 3003
    DB_ENGINE_ERROR = 3004

    # SQL 安全错误 4xxx
    SQL_INJECTION_DETECTED = 4000
    SQL_INVALID_STATEMENT = 4001
    SQL_VALIDATION_ERROR = 4002
    SQL_STRUCTURE_ERROR = 4003

    # 配置错误 5xxx
    MISSING_DB_CONFIG = 5000
    INVALID_DB_CONFIG = 5001

    # Agent 错误 6xxx
    AGENT_ERROR = 6000
    LLM_ERROR = 6001
    TOOL_EXECUTION_ERROR = 6002


class MCPError(Exception):
    """MCP 服务器基础异常"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "code_name": self.code.name,
                "details": self.details
            }
        }

    def to_json(self, ensure_ascii: bool = False) -> str:
        """转换为 JSON 格式"""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii)


class DBConfigError(MCPError):
    """数据库配置错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.MISSING_DB_CONFIG, details)


class SQLSecurityError(MCPError):
    """SQL 安全错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.SQL_INJECTION_DETECTED, details)


class SQLValidationError(MCPError):
    """SQL 验证错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.SQL_VALIDATION_ERROR, details)


class DBQueryError(MCPError):
    """数据库查询错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.DB_QUERY_ERROR, details)


class DBConnectionError(MCPError):
    """数据库连接错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.DB_CONNECTION_ERROR, details)


class AgentError(MCPError):
    """Agent 执行错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCode.AGENT_ERROR, details)


# ============ 响应格式化函数 ============

def format_error_response(
    message: str,
    code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    data: Any = None,
    details: Optional[Dict[str, Any]] = None,
    ensure_ascii: bool = False
) -> str:
    """
    统一格式化错误响应

    Args:
        message: 错误消息
        code: 错误码
        data: 返回的数据（默认为空）
        details: 额外详情
        ensure_ascii: 是否确保 ASCII 编码

    Returns:
        JSON 格式的错误响应
    """
    response = {
        "success": False,
        "error": {
            "code": code.value,
            "code_name": code.name,
            "message": message
        },
        "data": data if data is not None else [],
        "columns": [],
        "row_count": 0
    }

    if details:
        response["error"]["details"] = details

    return json.dumps(response, ensure_ascii=ensure_ascii)


def format_success_response(
    data: Any,
    columns: list = None,
    message: str = "操作成功",
    ensure_ascii: bool = False,
    **extra
) -> str:
    """
    统一格式化成功响应

    Args:
        data: 返回的数据
        columns: 列名列表
        message: 成功消息
        ensure_ascii: 是否确保 ASCII 编码
        **extra: 额外字段

    Returns:
        JSON 格式的成功响应
    """
    if columns is None:
        columns = []

    row_count = 0
    if isinstance(data, list):
        row_count = len(data)

    response = {
        "success": True,
        "data": data,
        "columns": columns,
        "row_count": row_count,
        "message": message,
        **extra
    }

    return json.dumps(response, ensure_ascii=ensure_ascii, default=str)


def format_sql_result(
    data: list,
    columns: list,
    execution_time: float = None,
    message: str = None
) -> str:
    """
    格式化 SQL 查询结果

    Args:
        data: 查询结果数据
        columns: 列名列表
        execution_time: 执行时间（毫秒）
        message: 提示消息

    Returns:
        JSON 格式的响应
    """
    if message is None:
        message = f"查询成功，返回 {len(data)} 行数据"

    extra = {}
    if execution_time is not None:
        extra["execution_time"] = round(execution_time, 2)

    return format_success_response(
        data=data,
        columns=columns,
        message=message,
        **extra
    )


def wrap_exception(
    e: Exception,
    default_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    default_message: str = "发生未知错误"
) -> MCPError:
    """
    将普通异常包装为 MCPError

    Args:
        e: 原始异常
        default_code: 默认错误码
        default_message: 默认错误消息

    Returns:
        MCPError 实例
    """
    # 如果已经是 MCPError，直接返回
    if isinstance(e, MCPError):
        return e

    # 根据异常类型映射错误码
    from sqlalchemy.exc import SQLAlchemyError

    if isinstance(e, SQLAlchemyError):
        return DBQueryError(str(e), {"original_type": type(e).__name__})

    # 其他异常使用默认值
    return MCPError(
        message=str(e) or default_message,
        code=default_code,
        details={"original_type": type(e).__name__, "original_message": str(e)}
    )


# ============ 异常处理装饰器 ============

def handle_errors(
    default_message: str = "操作失败",
    default_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    reraise: bool = False
):
    """
    错误处理装饰器

    Args:
        default_message: 默认错误消息
        default_code: 默认错误码
        reraise: 是否重新抛出异常
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except MCPError:
                if reraise:
                    raise
                return format_error_response(str(func.__Exception__), default_code)
            except Exception as e:
                error = wrap_exception(e, default_code, default_message)
                if reraise:
                    raise error
                return error.to_json()

        return wrapper

    return decorator


def safe_execute(
    func,
    *args,
    error_message: str = "执行失败",
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    **kwargs
) -> str:
    """
    安全执行函数，捕获异常并返回格式化错误

    Args:
        func: 要执行的函数
        *args: 函数参数
        error_message: 错误消息
        error_code: 错误码
        **kwargs: 函数关键字参数

    Returns:
        函数返回值或错误响应 JSON
    """
    try:
        return func(*args, **kwargs)
    except MCPError as e:
        return e.to_json()
    except Exception as e:
        error = wrap_exception(e, error_code, error_message)
        return error.to_json()
