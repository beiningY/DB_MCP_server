"""
日志配置单元测试
"""
import pytest
import logging
import json
import os
from io import StringIO

from db_mcp.logger import (
    setup_logger,
    get_logger,
    get_context_logger,
    configure_logging,
    JSONFormatter,
    ColorFormatter,
    ContextLogger,
    LOG_LEVELS,
)


class TestLogLevelMapping:
    """日志级别映射测试"""

    def test_log_levels_dict(self):
        """测试日志级别字典"""
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL


class TestJSONFormatter:
    """JSON 格式化器测试"""

    def test_json_formatter_basic(self):
        """测试基本 JSON 格式化"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["line"] == 42
        assert "timestamp" in data

    def test_json_formatter_with_exception(self):
        """测试带异常的 JSON 格式化"""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = True

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=(ValueError, ValueError("Test exception"), None),
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"


class TestColorFormatter:
    """颜色格式化器测试"""

    def test_color_formatter_basic(self):
        """测试基本颜色格式化"""
        formatter = ColorFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "INFO" in result
        assert "Test message" in result
        assert "test.logger" in result


class TestSetupLogger:
    """日志器设置测试"""

    def test_setup_logger_creates_logger(self):
        """测试创建日志器"""
        logger = setup_logger("test_logger", level="INFO")

        assert logger.name == "test_logger"
        assert logger.level == logging.INFO

    def test_setup_logger_returns_cached_logger(self):
        """测试返回缓存的日志器"""
        logger1 = setup_logger("cached_logger")
        logger2 = setup_logger("cached_logger")

        assert logger1 is logger2

    def test_setup_logger_with_json_output(self):
        """测试 JSON 输出模式"""
        logger = setup_logger("json_logger", json_output=True)

        # 检查 handler 的格式化器
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logger_with_text_output(self):
        """测试文本输出模式"""
        logger = setup_logger("text_logger", json_output=False)

        # 检查 handler 的格式化器
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, ColorFormatter)


class TestGetLogger:
    """获取日志器测试"""

    def test_get_logger_default_name(self):
        """测试获取默认名称的日志器"""
        logger = get_logger()
        assert logger.name == "mcp_server"

    def test_get_logger_custom_name(self):
        """测试获取自定义名称的日志器"""
        logger = get_logger("custom.logger")
        assert logger.name == "custom.logger"


class TestContextLogger:
    """上下文日志器测试"""

    def test_context_logger_creation(self):
        """测试上下文日志器创建"""
        logger = logging.getLogger("test")
        ctx_logger = ContextLogger("test", logger)

        assert ctx_logger._name == "test"
        assert ctx_logger._logger is logger

    def test_context_logger_with_context(self):
        """测试添加上下文"""
        logger = logging.getLogger("test")
        ctx_logger = ContextLogger("test", logger)

        # 添加上下文
        new_logger = ctx_logger.with_context(user_id="123", request_id="abc")

        assert new_logger._context["user_id"] == "123"
        assert new_logger._context["request_id"] == "abc"


class TestLoggingOutput:
    """日志输出测试"""

    def test_logger_outputs_to_stdout(self, caplog):
        """测试日志输出到标准输出"""
        logger = get_logger("test_output")

        with caplog.at_level(logging.INFO):
            logger.info("Test info message")
            logger.warning("Test warning message")

        assert "Test info message" in caplog.text
        assert "Test warning message" in caplog.text

    def test_logger_levels(self, caplog):
        """测试不同日志级别"""
        logger = setup_logger("level_test", level="WARNING")

        with caplog.at_level(logging.WARNING):
            logger.debug("Debug message")  # 不应该被记录
            logger.info("Info message")    # 不应该被记录
            logger.warning("Warning message")  # 应该被记录
            logger.error("Error message")  # 应该被记录

        assert "Debug message" not in caplog.text
        assert "Warning message" in caplog.text
        assert "Error message" in caplog.text
