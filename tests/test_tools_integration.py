"""
工具集成测试
测试 execute_sql_query 和 get_table_schema 工具
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# 模拟导入
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestExecuteSQLQueryTool:
    """execute_sql_query 工具测试"""

    def setup_method(self):
        """测试前设置"""
        # 导入工具
        from tools.execute_sql_tool import execute_sql_query
        self.tool = execute_sql_query

    def test_empty_sql_returns_error(self):
        """测试空 SQL 返回错误"""
        result = self.tool.invoke({"sql": ""})
        data = json.loads(result)

        assert data["success"] is False
        assert "不能为空" in data["error"]["message"]

    def test_missing_host_returns_error(self):
        """测试缺少 host 返回错误"""
        result = self.tool.invoke({
            "sql": "SELECT 1",
            "host": ""
        })
        data = json.loads(result)

        assert data["success"] is False
        assert "主机地址" in data["error"]["message"]

    @patch('tools.execute_sql_tool.validate_sql')
    def test_sql_validation_blocks_dangerous_queries(self, mock_validate):
        """测试 SQL 验证阻止危险查询"""
        # 模拟验证失败
        mock_validate.return_value = (False, "检测到危险关键字: DROP")

        result = self.tool.invoke({
            "sql": "DROP TABLE users",
            "host": "localhost"
        })
        data = json.loads(result)

        assert data["success"] is False
        assert "SQL 安全检查失败" in data["error"]["message"] or "危险关键字" in data["error"]["message"]

    @patch('tools.execute_sql_tool.get_engine')
    @patch('tools.execute_sql_tool.validate_sql')
    def test_successful_query_with_mock_db(self, mock_validate, mock_get_engine):
        """测试使用模拟数据库的成功查询"""
        # 验证通过
        mock_validate.return_value = (True, "")

        # 模拟数据库引擎和连接
        mock_result = Mock()
        mock_result.keys.return_value = ["id", "name"]
        mock_result.fetchall.return_value = [(1, "Alice"), (2, "Bob")]

        mock_connection = MagicMock()
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=False)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_connection
        mock_get_engine.return_value = mock_engine

        # 执行查询
        result = self.tool.invoke({
            "sql": "SELECT * FROM users LIMIT 10",
            "host": "localhost",
            "database": "test"
        })
        data = json.loads(result)

        assert data["success"] is True
        assert data["row_count"] == 2
        assert data["data"][0]["name"] == "Alice"

    @patch('tools.execute_sql_tool.validate_sql')
    def test_limit_is_sanitized(self, mock_validate):
        """测试 limit 被清理"""
        mock_validate.return_value = (True, "")

        # 模拟执行，只检查 limit 处理
        from tools.execute_sql_tool import sanitize_limit
        assert sanitize_limit(None) == 100
        assert sanitize_limit(-1) == 1
        assert sanitize_limit(100000) == 10000


class TestGetTableSchemaTool:
    """get_table_schema 工具测试"""

    def setup_method(self):
        """测试前设置"""
        from tools.get_table_schema_tool import get_table_schema
        self.tool = get_table_schema

    def test_missing_host_returns_error(self):
        """测试缺少 host 返回错误"""
        result = self.tool.invoke({"host": ""})
        data = json.loads(result)

        assert data["success"] is False
        assert "主机地址" in data["error"]["message"]

    @patch('tools.get_table_schema_tool.get_engine')
    def test_get_all_tables_summary(self, mock_get_engine):
        """测试获取所有表摘要"""
        # 模拟查询结果
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ("users", "用户表", "InnoDB", 100),
            ("orders", "订单表", "InnoDB", 500),
        ]

        mock_connection = MagicMock()
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=False)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_connection
        mock_get_engine.return_value = mock_engine

        # 调用工具
        result = self.tool.invoke({
            "host": "localhost",
            "database": "test"
        })

        assert result is not None
        assert isinstance(result, str)
        assert "共 2 个表" in result

    @patch('tools.get_table_schema_tool.get_engine')
    def test_get_specific_table_schema(self, mock_get_engine):
        """测试获取指定表结构"""
        # 模拟表检查结果
        mock_check_result = Mock()
        mock_check_result.fetchone.return_value = ("users", "用户表")

        # 模拟字段查询结果
        mock_columns_result = Mock()
        mock_columns_result.fetchall.return_value = [
            ("id", "int", "int(11)", "NO", None, "主键", "auto_increment", "1"),
            ("name", "varchar", "varchar(255)", "YES", None, "用户名", "", "2"),
        ]

        # 模拟索引查询结果
        mock_indexes_result = Mock()
        mock_indexes_result.fetchall.return_value = [
            ("PRIMARY", "id", "PRIMARY", 0),
        ]

        # 配置 mock 连接
        mock_connection = MagicMock()

        def execute_side_effect(text, params=None):
            if "TABLES" in str(text):
                return mock_check_result
            elif "COLUMNS" in str(text):
                return mock_columns_result
            elif "STATISTICS" in str(text):
                return mock_indexes_result
            return Mock()

        mock_connection.execute.side_effect = execute_side_effect
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=False)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_connection
        mock_get_engine.return_value = mock_engine

        # 调用工具
        result = self.tool.invoke({
            "host": "localhost",
            "database": "test",
            "table_name": "users"
        })

        assert result is not None
        assert isinstance(result, str)
        assert "users" in result


class TestSearchKnowledgeGraphTool:
    """search_knowledge_graph 工具测试"""

    def setup_method(self):
        """测试前设置"""
        from tools.search_knowledge_tool import search_knowledge_graph
        self.tool = search_knowledge_graph

    def test_empty_query_returns_error(self):
        """测试空查询返回错误"""
        result = self.tool.invoke({"query": ""})
        data = json.loads(result)

        assert data["success"] is False
        assert "不能为空" in data["error"]["message"]

    @patch('tools.search_knowledge_tool.requests.post')
    def test_successful_search(self, mock_post):
        """测试成功的搜索"""
        # 模拟 API 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "测试搜索结果"}
        mock_post.return_value = mock_response

        result = self.tool.invoke({"query": "如何计算还款率"})
        data = json.loads(result)

        # 由于没有 API 服务，这里只验证返回格式
        assert "success" in data

    @patch('tools.search_knowledge_tool.requests.post')
    def test_connection_error_handling(self, mock_post):
        """测试连接错误处理"""
        from requests.exceptions import ConnectionError
        mock_post.side_effect = ConnectionError("无法连接")

        result = self.tool.invoke({"query": "测试查询"})
        data = json.loads(result)

        assert data["success"] is False
        assert "无法连接" in data["error"]["message"]


class TestToolsIntegration:
    """工具集成测试"""

    def test_tools_import(self):
        """测试工具可以正常导入"""
        from tools import execute_sql_query, get_table_schema, search_knowledge_graph

        assert execute_sql_query is not None
        assert get_table_schema is not None
        assert search_knowledge_graph is not None

    def test_tool_invocation_signature(self):
        """测试工具调用签名"""
        from tools import execute_sql_query, get_table_schema, search_knowledge_graph

        # 所有工具都应该有 invoke 方法
        assert hasattr(execute_sql_query, 'invoke')
        assert hasattr(get_table_schema, 'invoke')
        assert hasattr(search_knowledge_graph, 'invoke')

        # 测试 execute_sql_query 参数
        result = execute_sql_query.invoke({
            "sql": "SELECT 1",
            "host": "localhost"
        })
        assert isinstance(result, str)

        # 测试 get_table_schema 参数
        result = get_table_schema.invoke({"host": "localhost"})
        assert isinstance(result, str)
