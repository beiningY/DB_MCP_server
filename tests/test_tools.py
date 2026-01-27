"""
工具基础测试
验证三个工具是否可以正常导入和基本运行
"""

import json
import pytest


class TestExecuteSqlQuery:
    """测试 execute_sql_query 工具"""
    
    def test_empty_sql_error(self):
        """测试空 SQL 返回错误"""
        from tools import execute_sql_query
        
        result = execute_sql_query.invoke({"sql": ""})
        data = json.loads(result)
        
        assert data["success"] is False
        assert "不能为空" in data["message"]
    
    def test_non_select_blocked(self):
        """测试非 SELECT 语句被阻止"""
        from tools import execute_sql_query
        
        # 测试 INSERT
        result = execute_sql_query.invoke({"sql": "INSERT INTO users VALUES (1)"})
        data = json.loads(result)
        assert data["success"] is False
        assert "仅支持 SELECT" in data["message"]
        
        # 测试 DELETE
        result = execute_sql_query.invoke({"sql": "DELETE FROM users"})
        data = json.loads(result)
        assert data["success"] is False
    
    def test_missing_db_url(self, monkeypatch):
        """测试缺少数据库配置"""
        from tools import execute_sql_query
        
        monkeypatch.delenv("DB_URL", raising=False)
        
        result = execute_sql_query.invoke({"sql": "SELECT 1"})
        data = json.loads(result)
        
        assert data["success"] is False
        assert "DB_URL" in data["message"]


class TestGetTableSchema:
    """测试 get_table_schema 工具"""
    
    def test_get_all_tables(self):
        """测试获取所有表列表"""
        from tools import get_table_schema
        
        result = get_table_schema.invoke({})
        
        # 应该返回表摘要或错误信息（取决于元数据文件是否存在）
        assert result is not None
        assert isinstance(result, str)
    
    def test_get_specific_table(self):
        """测试获取指定表"""
        from tools import get_table_schema
        
        result = get_table_schema.invoke({"table_name": "temp_rc_model_daily"})
        
        assert result is not None
        assert isinstance(result, str)
    
    def test_table_not_exist(self):
        """测试表不存在的情况"""
        from tools import get_table_schema
        
        result = get_table_schema.invoke({"table_name": "non_existent_table_xyz"})
        
        # 应该返回错误或找不到的提示
        assert result is not None


class TestSearchKnowledgeGraph:
    """测试 search_knowledge_graph 工具"""
    
    def test_empty_query_error(self):
        """测试空查询返回错误"""
        from tools import search_knowledge_graph
        
        result = search_knowledge_graph.invoke({"query": ""})
        data = json.loads(result)
        
        assert data["success"] is False
        assert "不能为空" in data["message"]
    
    def test_search_returns_json(self):
        """测试搜索返回 JSON 格式"""
        from tools import search_knowledge_graph
        
        result = search_knowledge_graph.invoke({"query": "如何计算放款金额"})
        
        # 验证返回的是有效 JSON
        data = json.loads(result)
        assert "success" in data
        assert "message" in data
    
    def test_different_modes(self):
        """测试不同搜索模式"""
        from tools import search_knowledge_graph
        
        modes = ["naive", "local", "global", "hybrid", "mix"]
        
        for mode in modes:
            result = search_knowledge_graph.invoke({
                "query": "测试查询",
                "mode": mode
            })
            data = json.loads(result)
            # 工具应该能处理所有模式（即使服务未启动也应返回有效 JSON）
            assert "success" in data
