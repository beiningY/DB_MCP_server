"""
统一日志配置模块
提供规范的日志配置，支持控制台输出、文件输出、日志轮转
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


# 日志级别映射
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


class LoggerConfig:
    """日志配置管理类"""
    
    # 默认日志格式
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(thread)d] - [%(filename)s:%(lineno)d] - %(message)s'
    
    # 日期格式
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_level: str = 'info',
        console_output: bool = True,
        file_output: bool = True,
        rotation_mode: str = 'size',  # 'size' 或 'time'
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        log_format: str = DEFAULT_FORMAT
    ):
        """
        初始化日志配置
        
        Args:
            log_dir: 日志文件目录，默认为项目根目录下的 logs/
            log_level: 日志级别（debug/info/warning/error/critical）
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            rotation_mode: 日志轮转模式（size: 按大小轮转, time: 按时间轮转）
            max_bytes: 单个日志文件最大字节数（仅 size 模式）
            backup_count: 保留的备份文件数量
            log_format: 日志格式
        """
        self.log_dir = log_dir or os.path.join(Path(__file__).parent, 'logs')
        self.log_level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
        self.console_output = console_output
        self.file_output = file_output
        self.rotation_mode = rotation_mode
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.log_format = log_format
        
        # 创建日志目录
        if self.file_output:
            os.makedirs(self.log_dir, exist_ok=True)
    
    def get_logger(self, name: str = 'db_mcp_server') -> logging.Logger:
        """
        获取配置好的 logger
        
        Args:
            name: logger 名称
            
        Returns:
            配置好的 Logger 实例
        """
        logger = logging.getLogger(name)
        
        # 避免重复添加 handler
        if logger.handlers:
            return logger
        
        logger.setLevel(self.log_level)
        formatter = logging.Formatter(self.log_format, datefmt=self.DATE_FORMAT)
        
        # 控制台输出
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # 文件输出
        if self.file_output:
            # 主日志文件
            log_file = os.path.join(self.log_dir, f'{name}.log')
            
            if self.rotation_mode == 'size':
                # 按大小轮转
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
            else:
                # 按时间轮转（每天）
                file_handler = TimedRotatingFileHandler(
                    log_file,
                    when='midnight',
                    interval=1,
                    backupCount=self.backup_count,
                    encoding='utf-8'
                )
            
            file_handler.setLevel(self.log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 错误日志单独记录
            error_log_file = os.path.join(self.log_dir, f'{name}_error.log')
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            logger.addHandler(error_handler)
        
        return logger


# 全局日志配置实例
_global_config: Optional[LoggerConfig] = None


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    console_output: bool = True,
    file_output: bool = True,
    rotation_mode: str = 'size',
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    log_format: str = LoggerConfig.DEFAULT_FORMAT
) -> LoggerConfig:
    """
    配置全局日志
    
    Args:
        log_dir: 日志文件目录
        log_level: 日志级别，从环境变量 LOG_LEVEL 读取，默认 info
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        rotation_mode: 日志轮转模式
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的备份文件数量
        log_format: 日志格式
        
    Returns:
        LoggerConfig 实例
    """
    global _global_config
    
    # 从环境变量读取日志级别
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'info')
    
    _global_config = LoggerConfig(
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output,
        file_output=file_output,
        rotation_mode=rotation_mode,
        max_bytes=max_bytes,
        backup_count=backup_count,
        log_format=log_format
    )
    
    return _global_config


def get_logger(name: str = 'db_mcp_server') -> logging.Logger:
    """
    获取 logger 实例（便捷函数）
    
    Args:
        name: logger 名称
        
    Returns:
        Logger 实例
    """
    global _global_config
    
    # 如果没有配置过，使用默认配置
    if _global_config is None:
        setup_logging()
    
    return _global_config.get_logger(name)


# 为不同模块提供专用的 logger 获取函数
def get_agent_logger() -> logging.Logger:
    """获取 Agent 模块的 logger"""
    return get_logger('db_mcp_server.agent')


def get_executor_logger() -> logging.Logger:
    """获取 Executor 模块的 logger"""
    return get_logger('db_mcp_server.executor')


def get_knowledge_logger() -> logging.Logger:
    """获取 Knowledge 模块的 logger"""
    return get_logger('db_mcp_server.knowledge')


def get_server_logger() -> logging.Logger:
    """获取 Server 模块的 logger"""
    return get_logger('db_mcp_server.server')


def get_tools_logger() -> logging.Logger:
    """获取 Tools 模块的 logger"""
    return get_logger('db_mcp_server.tools')


# 日志装饰器：用于记录函数执行
def log_execution(logger: Optional[logging.Logger] = None):
    """
    日志装饰器：记录函数执行
    
    Args:
        logger: Logger 实例，如果为 None 则使用默认 logger
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger()
            
            func_name = func.__name__
            logger.debug(f"开始执行: {func_name}")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                logger.debug(f"执行完成: {func_name} (耗时: {elapsed_time:.3f}s)")
                return result
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"执行失败: {func_name} (耗时: {elapsed_time:.3f}s) - {str(e)}")
                raise
        
        return wrapper
    return decorator


def log_async_execution(logger: Optional[logging.Logger] = None):
    """
    异步函数日志装饰器：记录异步函数执行
    
    Args:
        logger: Logger 实例，如果为 None 则使用默认 logger
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger()
            
            func_name = func.__name__
            logger.debug(f"开始执行: {func_name}")
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                elapsed_time = time.time() - start_time
                logger.debug(f"执行完成: {func_name} (耗时: {elapsed_time:.3f}s)")
                return result
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"执行失败: {func_name} (耗时: {elapsed_time:.3f}s) - {str(e)}")
                raise
        
        return wrapper
    return decorator
