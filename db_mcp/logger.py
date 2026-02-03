"""
统一日志配置
提供结构化的日志输出
"""
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import os
import json


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
# 是否使用 JSON 格式输出
DEFAULT_JSON_OUTPUT = os.getenv("LOG_JSON", "false").lower() == "true"


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
    name: str = "mcp_server",
    level: str = DEFAULT_LOG_LEVEL,
    json_output: bool = DEFAULT_JSON_OUTPUT,
    handler: Optional[logging.Handler] = None
) -> logging.Logger:
    """
    设置并获取日志器

    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: 是否使用 JSON 格式
        handler: 自定义 Handler（可选）

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

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 创建或使用自定义 handler
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)

        # 选择格式化器
        if json_output:
            formatter = JSONFormatter()
        else:
            formatter = ColorFormatter()

        handler.setFormatter(formatter)

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
    全局配置日志

    Args:
        level: 日志级别
        json_output: 是否使用 JSON 格式
        log_file: 日志文件路径（可选）
    """
    # 更新默认值
    if level is None:
        level = DEFAULT_LOG_LEVEL
    if json_output is None:
        json_output = DEFAULT_JSON_OUTPUT

    # 清除已存在的日志器
    _loggers.clear()

    # 如果指定了文件，添加文件处理器
    file_handler = None
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        file_handler.setFormatter(JSONFormatter())

    # 重新设置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColorFormatter())
    root_logger.addHandler(console_handler)

    # 添加文件处理器
    if file_handler:
        root_logger.addHandler(file_handler)
