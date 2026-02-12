"""
统一日志配置
提供结构化的日志输出，避免重复记录
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import os
import json
from logging.handlers import RotatingFileHandler


# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# 从环境变量读取日志级别
DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# 是否使用 JSON 格式输��
DEFAULT_JSON_OUTPUT = os.getenv("LOG_JSON", "false").lower() == "true"
# 日志文件目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# 全局标志：是否已配置根日志器（防止重复配置）
_root_configured = False


def _ensure_unique_handlers(logger: logging.Logger) -> None:
    """
    确保日志器没有重复的 handler

    检查并移除重复类型的 handler，防止日志重复输出
    """
    if not logger.handlers:
        return

    # 按类型分组
    handler_types = {}
    for h in logger.handlers[:]:
        h_type = type(h).__name__
        if h_type in handler_types:
            logger.removeHandler(h)
        else:
            handler_types[h_type] = h


class JSONFormatter(logging.Formatter):
    """
    JSON 格式日志格式化器
    适合生产环境，便于日志收集和分析
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "path": record.pathname,
        }

        # 添加进程和线程信息
        log_data["process_id"] = record.process
        log_data["thread_id"] = record.thread

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }

        # 添加额外字段
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data, ensure_ascii=False)


class ColorFormatter(logging.Formatter):
    """
    带颜色的控制台日志格式化器
    适合开发环境，便于阅读
    """

    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # 获取颜色
        color = self.COLORS.get(record.levelname, '')

        # 格式化消息
        level_name = f"{color}{record.levelname}{self.RESET}"
        timestamp = self.formatTime(record, '%Y-%m-%d %H:%M:%S')

        # 构建日志消息
        message = f"{timestamp} [{level_name:8s}] {record.name}: {record.getMessage()}"

        # 添加异常信息
        if record.exc_info:
            message += '\n' + self.formatException(record.exc_info)

        return message


class ContextLogger:
    """
    带上下文的日志器
    支持添加额外的上下文信息
    """

    def __init__(self, name: str, logger: logging.Logger):
        self._name = name
        self._logger = logger
        self._context: Dict[str, Any] = {}

    def with_context(self, **kwargs) -> 'ContextLogger':
        """添加上下文信息，返回新的日志器实例"""
        new_logger = ContextLogger(self._name, self._logger)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(self, level: int, msg: str, *args, **kwargs):
        """内部日志方法"""
        if self._logger.isEnabledFor(level):
            # 合并上下文和额外参数
            extra = kwargs.pop('extra', {})
            extra = {**self._context, **extra}

            # 创建带有额外信息的 LogRecord
            if extra:
                # 使用 adapter 添加上下文
                adapter = logging.LoggerAdapter(self._logger, extra)
                adapter.log(level, msg, *args, **kwargs)
            else:
                self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        """DEBUG 级别日志"""
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """INFO 级别日志"""
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """WARNING 级别日志"""
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """ERROR 级别日志"""
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """CRITICAL 级别日志"""
        self._log(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """记录异常（自动包含堆栈跟踪）"""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, msg, *args, **kwargs)


# 全局日志器缓存
_loggers: Dict[str, logging.Logger] = {}


def setup_logger(
    name: str = "mcp",
    level: str = DEFAULT_LOG_LEVEL,
    json_output: bool = DEFAULT_JSON_OUTPUT,
    handler: Optional[logging.Handler] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    设置并获取日志器（防止重复添加 handler）

    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: 是否使用 JSON 格式
        handler: 自定义 Handler（可选）
        log_file: 日志文件路径（可选）

    Returns:
        logging.Logger 实例
    """
    # 如果已存在，直接返回
    if name in _loggers:
        return _loggers[name]

    # 获取日志级别
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # 创建日志器
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False  # 不传播到根日志器，避免重复

    # 确保没有重复的 handler
    _ensure_unique_handlers(logger)

    # 避免重复添加 handler
    if logger.handlers:
        return _loggers[name]  # 已有 handler，直接返回

    # 创建或使用自定义 handler
    if handler is None:
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # 选择格式化器
        if json_output:
            console_formatter = JSONFormatter()
        else:
            console_formatter = ColorFormatter()

        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # 文件 handler（如果指定了日志文件）
        if log_file:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            # 文件始终使用 JSON 格式，便于解析
            file_formatter = JSONFormatter()
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
    else:
        handler.setLevel(log_level)
        if json_output:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(ColorFormatter())
        logger.addHandler(handler)

    # 缓存日志器
    _loggers[name] = logger

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称，默认为 "mcp_server"

    Returns:
        logging.Logger 实例
    """
    if name is None:
        name = "mcp_server"

    if name not in _loggers:
        return setup_logger(name)

    return _loggers[name]


def get_context_logger(name: str = None) -> ContextLogger:
    """
    获取带上下文的日志器

    Args:
        name: 日志器名称

    Returns:
        ContextLogger 实例
    """
    logger = get_logger(name)
    return ContextLogger(name or "mcp_server", logger)


# 默认日志器实例
logger = get_logger("mcp_server")

# 常用的快捷日志器
mcp_logger = get_logger("mcp.server")
db_logger = get_logger("mcp.db")
agent_logger = get_logger("mcp.agent")
tool_logger = get_logger("mcp.tool")


# 装饰器：记录函数调用
def log_execution(logger: logging.Logger = None, level: int = logging.INFO):
    """
    记录函数执行的装饰器

    Args:
        logger: 使用的日志器
        level: 日志级别
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            log = logger or get_logger()
            func_name = f"{func.__module__}.{func.__name__}"

            log.log(level, f"调用函数: {func_name}")

            try:
                result = func(*args, **kwargs)
                log.log(level, f"函数执行成功: {func_name}")
                return result
            except Exception as e:
                log.error(f"函数执行失败: {func_name}, 错误: {str(e)}", exc_info=True)
                raise

        return wrapper

    return decorator


# 装饰器：记录异常
def log_errors(logger: logging.Logger = None):
    """
    记录函数异常的装饰器

    Args:
        logger: 使用的日志器
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logger or get_logger()
                log.error(f"函数 {func.__name__} 抛出异常: {str(e)}", exc_info=True)
                raise

        return wrapper

    return decorator


def configure_logging(
    level: str = None,
    json_output: bool = None,
    log_file: str = None
):
    """
    全局配置日志（防止重复配置）

    Args:
        level: 日志级别
        json_output: 是否使用 JSON 格式
        log_file: 日志文件路径（可选）
    """
    global _root_configured

    # 防止重复配置
    if _root_configured:
        return

    # 更新默认值
    if level is None:
        level = DEFAULT_LOG_LEVEL
    if json_output is None:
        json_output = DEFAULT_JSON_OUTPUT

    # 获取日志级别
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # 设置根日志器（只处理未被捕获的日志）
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 只在没有 handler 时添加
    if not root_logger.handlers:
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        if json_output:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(ColorFormatter())
        root_logger.addHandler(console_handler)

        # 文件处理器
        if log_file:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(file_handler)

    _root_configured = True


# ============================================================================
# 请求和工具调用日志辅助函数
# ============================================================================

def log_request_start(logger: logging.Logger, query: str, db_key: str = "", request_id: str = ""):
    """
    记录请求开始

    Args:
        logger: 日志器
        query: 用户查询
        db_key: 数据库标识符
        request_id: 请求ID
    """
    logger.info(
        f"请求开始 | query={query[:100]}{'...' if len(query) > 100 else ''} | "
        f"db={db_key} | request_id={request_id}"
    )


def log_request_end(
    logger: logging.Logger,
    request_id: str,
    status: str,
    duration_ms: float,
    response_length: int = 0
):
    """
    记录请求结束

    Args:
        logger: 日志器
        request_id: 请求ID
        status: 状态
        duration_ms: 耗时（毫秒）
        response_length: 响应长度
    """
    logger.info(
        f"请求结束 | request_id={request_id} | status={status} | "
        f"duration={duration_ms:.0f}ms | response_len={response_length}"
    )


def log_tool_call(
    logger: logging.Logger,
    tool_name: str,
    tool_input: Dict[str, Any] = None,
    status: str = "start",
    duration_ms: float = 0,
    error: str = None,
    output_preview: str = None
):
    """
    记录工具调用（详细输入输出）

    Args:
        logger: 日志器
        tool_name: 工具名称
        tool_input: 工具输入参数
        status: 状态 (start/success/error)
        duration_ms: 执行耗时
        error: 错误信息
        output_preview: 输出预览
    """
    if status == "start":
        # 脱敏处理
        input_str = str(tool_input) if tool_input else "{}"
        input_str = input_str[:500]  # 限制长度

        logger.info(f"工具调用开始 | tool={tool_name} | input={input_str}")
    elif status == "success":
        output_str = output_preview[:200] if output_preview else ""
        logger.info(
            f"工具调用成功 | tool={tool_name} | "
            f"duration={duration_ms:.0f}ms | output_preview={output_str}"
        )
    elif status == "error":
        logger.error(
            f"工具调用失败 | tool={tool_name} | "
            f"duration={duration_ms:.0f}ms | error={error}"
        )


def log_sql_execution(
    logger: logging.Logger,
    sql: str,
    database: str,
    row_count: int = 0,
    duration_ms: float = 0,
    status: str = "success",
    error: str = None
):
    """
    记录 SQL 执行

    Args:
        logger: 日志器
        sql: SQL 语句
        database: 数据库名
        row_count: 返回行数
        duration_ms: 执行耗时
        status: 状态
        error: 错误信息
    """
    sql_preview = sql[:200].replace("\n", " ")  # 压缩单行
    if status == "success":
        logger.info(
            f"SQL执行成功 | db={database} | rows={row_count} | "
            f"duration={duration_ms:.0f}ms | sql={sql_preview}"
        )
    else:
        logger.error(
            f"SQL执行失败 | db={database} | error={error} | sql={sql_preview}"
        )


def log_agent_step(
    logger: logging.Logger,
    step_index: int,
    step_name: str,
    status: str = "start",
    duration_ms: float = 0
):
    """
    记录 Agent 执行步骤

    Args:
        logger: 日志器
        step_index: 步骤索引
        step_name: 步骤名称
        status: 状态
        duration_ms: 耗时
    """
    if status == "start":
        logger.debug(f"Agent步骤开始 | step={step_index} | name={step_name}")
    elif status == "success":
        logger.debug(f"Agent步骤完成 | step={step_index} | duration={duration_ms:.0f}ms")
    else:
        logger.warning(f"Agent步骤失败 | step={step_index} | error={step_name}")
