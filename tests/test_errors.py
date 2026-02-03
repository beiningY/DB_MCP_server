"""
错误处理单元测试
测试统一错误处理和错误码
"""

import pytest
import json

from db_mcp.errors import (
    # 错误码
    ErrorCode,
    # 异常类
    MCPError,
    DBConfigError,
    SQLSecurityError,
    SQLValidationError,
    DBQueryError,
    DBConnectionError,
    AgentError,
    # 响应格式化
    format_error_response,
    format_success_response,
    format_sql_result,
    # 工具函数
    wrap_exception,
)


class TestErrorCode:
    """错误码测试"""

    def test_error_code_values(self):
        """测试错误码值"""
        assert ErrorCode.UNKNOWN_ERROR == 1000
        assert ErrorCode.INVALID_PARAMS == 1001
        assert ErrorCode.UNAUTHORIZED == 2000
        assert ErrorCode.DB_CONNECTION_ERROR == 3000
        assert ErrorCode.SQL_INJECTION_DETECTED == 4000
        assert ErrorCode.MISSING_DB_CONFIG == 5000
        assert ErrorCode.AGENT_ERROR == 6000

    def test_error_code_name(self):
        """测试错误码名称"""
        assert ErrorCode.UNKNOWN_ERROR.name == "UNKNOWN_ERROR"
        assert ErrorCode.SQL_INJECTION_DETECTED.name == "SQL_INJECTION_DETECTED"


class TestMCPError:
    """MCPError 基础异常测试"""

    def test_mcp_error_creation(self):
        """测试 MCPError 创建"""
        error = MCPError("测试错误", ErrorCode.INVALID_PARAMS)
        assert error.message == "测试错误"
        assert error.code == ErrorCode.INVALID_PARAMS
        assert error.details == {}

    def test_mcp_error_with_details(self):
        """测试带详情的 MCPError"""
        details = {"field": "username", "value": "test"}
        error = MCPError("验证失败", ErrorCode.INVALID_PARAMS, details)
        assert error.details == details

    def test_mcp_error_to_dict(self):
        """测试 MCPError 转字典"""
        error = MCPError("测试错误", ErrorCode.DB_QUERY_ERROR, {"table": "users"})

        result = error.to_dict()
        assert result["success"] is False
        assert result["error"]["code"] == 3001
        assert result["error"]["code_name"] == "DB_QUERY_ERROR"
        assert result["error"]["message"] == "测试错误"
        assert result["error"]["details"]["table"] == "users"

    def test_mcp_error_to_json(self):
        """测试 MCPError 转 JSON"""
        error = MCPError("测试错误", ErrorCode.UNKNOWN_ERROR)
        json_str = error.to_json()
        data = json.loads(json_str)

        assert data["success"] is False
        assert data["error"]["message"] == "测试错误"


class TestSpecificErrors:
    """特定错误类测试"""

    def test_db_config_error(self):
        """测试数据库配置错误"""
        error = DBConfigError("缺少数据库配置")
        assert error.code == ErrorCode.MISSING_DB_CONFIG
        assert error.message == "缺少数据库配置"

    def test_sql_security_error(self):
        """测试 SQL 安全错误"""
        error = SQLSecurityError("检测到 SQL 注入")
        assert error.code == ErrorCode.SQL_INJECTION_DETECTED
        assert error.message == "检测到 SQL 注入"

    def test_sql_validation_error(self):
        """测试 SQL 验证错误"""
        error = SQLValidationError("SQL 格式错误")
        assert error.code == ErrorCode.SQL_VALIDATION_ERROR

    def test_db_query_error(self):
        """测试数据库查询错误"""
        error = DBQueryError("查询超时")
        assert error.code == ErrorCode.DB_QUERY_ERROR

    def test_db_connection_error(self):
        """测试数据库连接错误"""
        error = DBConnectionError("无法连接到数据库")
        assert error.code == ErrorCode.DB_CONNECTION_ERROR

    def test_agent_error(self):
        """测试 Agent 错误"""
        error = AgentError("Agent 执行失败")
        assert error.code == ErrorCode.AGENT_ERROR


class TestErrorResponseFormatting:
    """错误响应格式化测试"""

    def test_format_error_response_basic(self):
        """测试基本错误响应格式化"""
        response = format_error_response("操作失败")
        data = json.loads(response)

        assert data["success"] is False
        assert data["error"]["message"] == "操作失败"
        assert data["error"]["code"] == 1000
        assert data["data"] == []

    def test_format_error_response_with_code(self):
        """测试带错误码的响应格式化"""
        response = format_error_response("参数错误", ErrorCode.INVALID_PARAMS)
        data = json.loads(response)

        assert data["error"]["code"] == 1001
        assert data["error"]["code_name"] == "INVALID_PARAMS"

    def test_format_error_response_with_details(self):
        """测试带详情的响应格式化"""
        response = format_error_response(
            "验证失败",
            ErrorCode.INVALID_PARAMS,
            details={"field": "email", "reason": "格式错误"}
        )
        data = json.loads(response)

        assert data["error"]["details"]["field"] == "email"
        assert data["error"]["details"]["reason"] == "格式错误"

    def test_format_error_response_with_data(self):
        """测试带数据的响应格式化"""
        response = format_error_response(
            "查询失败",
            data=[{"error": "表不存在"}]
        )
        data = json.loads(response)

        assert len(data["data"]) == 1
        assert data["data"][0]["error"] == "表不存在"


class TestSuccessResponseFormatting:
    """成功响应格式化测试"""

    def test_format_success_response_basic(self):
        """测试基本成功响应格式化"""
        response = format_success_response(
            data=[{"id": 1, "name": "Alice"}],
            columns=["id", "name"]
        )
        data = json.loads(response)

        assert data["success"] is True
        assert data["row_count"] == 1
        assert len(data["data"]) == 1
        assert data["columns"] == ["id", "name"]

    def test_format_success_response_with_extra(self):
        """测试带额外字段的响应格式化"""
        response = format_success_response(
            data=[{"id": 1}],
            columns=["id"],
            execution_time=123.45
        )
        data = json.loads(response)

        assert data["execution_time"] == 123.45

    def test_format_sql_result(self):
        """测试 SQL 结果格式化"""
        response = format_sql_result(
            data=[{"id": 1, "name": "Alice"}],
            columns=["id", "name"],
            execution_time=50.5
        )
        data = json.loads(response)

        assert data["success"] is True
        assert data["execution_time"] == 50.5
        assert "查询成功" in data["message"]


class TestWrapException:
    """异常包装测试"""

    def test_wrap_mcp_error(self):
        """测试包装 MCPError"""
        error = MCPError("原始错误", ErrorCode.DB_QUERY_ERROR)
        wrapped = wrap_exception(error)

        assert wrapped is error  # 应该返回同一个对象

    def test_wrap_sqlalchemy_error(self):
        """测试包装 SQLAlchemy 错误"""
        from sqlalchemy.exc import SQLAlchemyError

        original_error = SQLAlchemyError("查询失败")
        wrapped = wrap_exception(original_error)

        assert isinstance(wrapped, DBQueryError)
        assert "查询失败" in wrapped.message

    def test_wrap_generic_exception(self):
        """测试包装普通异常"""
        original_error = ValueError("未知错误")
        wrapped = wrap_exception(
            original_error,
            default_code=ErrorCode.UNKNOWN_ERROR,
            default_message="默认消息"
        )

        assert isinstance(wrapped, MCPError)
        assert wrapped.code == ErrorCode.UNKNOWN_ERROR
        assert wrapped.details["original_type"] == "ValueError"


class TestErrorHandlingIntegration:
    """错误处理集成测试"""

    def test_error_response_format_consistency(self):
        """测试错误响应格式一致性"""
        responses = [
            format_error_response("错误1", ErrorCode.UNKNOWN_ERROR),
            format_error_response("错误2", ErrorCode.DB_CONNECTION_ERROR),
            format_error_response("错误3", ErrorCode.SQL_INJECTION_DETECTED),
        ]

        for response in responses:
            data = json.loads(response)
            # 所有错误响应应该有相同的结构
            assert "success" in data
            assert "error" in data
            assert "data" in data
            assert "row_count" in data
            assert data["success"] is False
            assert "code" in data["error"]
            assert "code_name" in data["error"]
            assert "message" in data["error"]

    def test_success_response_format_consistency(self):
        """测试成功响应格式一致性"""
        responses = [
            format_success_response([], []),
            format_success_response([{"a": 1}], ["a"]),
            format_success_response([{"a": 1}, {"a": 2}], ["a"]),
        ]

        for response in responses:
            data = json.loads(response)
            # 所有成功响应应该有相同的结构
            assert "success" in data
            assert "data" in data
            assert "columns" in data
            assert "row_count" in data
            assert "message" in data
            assert data["success"] is True
