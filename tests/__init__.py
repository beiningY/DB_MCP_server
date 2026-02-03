"""
DB MCP Server 测试模块

测试组织结构：
- test_sql_validator.py: SQL 验证器测试
- test_connection_pool.py: 连接池测试
- test_errors.py: 错误处理测试
- test_logger.py: 日志测试
- test_tools_integration.py: 工具集成测试
- test_tools.py: 基础工具测试（旧版）
- test_mcp_client.py: MCP 客户端测试（需要服务器运行）

使用方式：
    # 运行所有测试
    pytest

    # 运行特定测试文件
    pytest tests/test_sql_validator.py

    # 运行特定测试类
    pytest tests/test_sql_validator.py::TestSQLValidator

    # 运行特定测试函数
    pytest tests/test_sql_validator.py::TestSQLValidator::test_valid_select_queries

    # 显示覆盖率
    pytest --cov=db_mcp --cov=tools --cov-report=html

    # 详细输出
    pytest -v

    # 只运行单元测试
    pytest -m unit

    # 跳过需要数据库的测试
    pytest -m "not requires_db"
"""

import pytest


def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers", "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试"
    )
    config.addinivalue_line(
        "markers", "requires_db: 需要数据库的测试"
    )
    config.addinivalue_line(
        "markers", "requires_llm: 需要 LLM 的测试"
    )


# 简单的烟雾测试，验证基本功能正常
@pytest.mark.smoke
@pytest.mark.unit
def test_imports():
    """测试所有模块可以正常导入"""
    # 核心模块
    from db_mcp import server, tool
    from db_mcp.sql_validator import validate_sql
    from db_mcp.connection_pool import get_engine
    from db_mcp.errors import format_error_response
    from db_mcp.logger import get_logger

    # 工具模块
    from tools import execute_sql_query, get_table_schema, search_knowledge_graph

    # Agent 模块
    from agent.data_simple_agent import get_agent

    assert True


@pytest.mark.smoke
@pytest.mark.unit
def test_sql_validator_basic():
    """测试 SQL 验证器基本功能"""
    from db_mcp.sql_validator import validate_sql

    # 有效查询
    is_valid, _ = validate_sql("SELECT * FROM users")
    assert is_valid is True

    # 无效查询
    is_valid, _ = validate_sql("DROP TABLE users")
    assert is_valid is False


@pytest.mark.smoke
@pytest.mark.unit
def test_error_handling_basic():
    """测试错误处理基本功能"""
    from db_mcp.errors import format_error_response, ErrorCode

    result = format_error_response("测试错误", ErrorCode.INVALID_PARAMS)
    import json
    data = json.loads(result)

    assert data["success"] is False
    assert data["error"]["code"] == 1001
