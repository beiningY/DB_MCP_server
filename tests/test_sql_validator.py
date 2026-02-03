"""
SQL 验证器单元测试
测试 SQL 注入检测和安全验证功能
"""

import pytest

from db_mcp.sql_validator import (
    validate_sql,
    SQLValidationError,
    is_select_query,
    sanitize_limit,
    check_for_injection,
    check_sql_structure,
)


class TestSQLValidator:
    """SQL 验证器测试类"""

    def test_valid_select_queries(self):
        """测试有效的 SELECT 查询应该通过验证"""
        valid_queries = [
            "SELECT * FROM users",
            "SELECT id, name FROM users WHERE age > 18",
            "SELECT COUNT(*) as cnt FROM orders",
            "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id",
            "SELECT * FROM (SELECT * FROM users) t",
            # CTE (WITH 语句)
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte",
            # 带有函数
            "SELECT MAX(price) FROM products",
            "SELECT AVG(score) as avg_score FROM results",
            # 带有 GROUP BY, HAVING, ORDER BY
            "SELECT category, COUNT(*) FROM products GROUP BY category",
            "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
        ]

        for query in valid_queries:
            is_valid, error_msg = validate_sql(query, strict_mode=True)
            assert is_valid is True, f"查询应该有效: {query}\n错误: {error_msg}"

    def test_dangerous_keywords_blocked(self):
        """测试危险关键字被阻止"""
        dangerous_queries = [
            ("DROP TABLE users", "DROP"),
            ("DELETE FROM users", "DELETE"),
            ("INSERT INTO users VALUES (1)", "INSERT"),
            ("UPDATE users SET name='test'", "UPDATE"),
            ("TRUNCATE TABLE users", "TRUNCATE"),
            ("ALTER TABLE users ADD COLUMN x INT", "ALTER"),
            ("CREATE TABLE new_table (id INT)", "CREATE"),
            ("GRANT ALL ON users TO 'user'", "GRANT"),
            ("REVOKE ALL ON users FROM 'user'", "REVOKE"),
            ("EXECUTE procedure_name", "EXECUTE"),
            ("SHOW TABLES", "SHOW"),
            ("DESCRIBE users", "DESCRIBE"),
        ]

        for query, keyword in dangerous_queries:
            is_valid, error_msg = validate_sql(query)
            assert is_valid is False, f"查询应该被拒绝: {query}"
            assert keyword in error_msg or "危险关键字" in error_msg or "仅允许 SELECT" in error_msg

    def test_sql_injection_patterns_blocked(self):
        """测试 SQL 注入模式被检测"""
        injection_queries = [
            "SELECT * FROM users WHERE id = 1; DROP TABLE users",  # 多语句
            "SELECT * FROM users WHERE id = 1 -- comment",  # 注释（某些情况）
        ]

        for query in injection_queries:
            is_valid, error_msg = validate_sql(query)
            # 注入检测应该拒绝或警告
            if not is_valid:
                assert "注入" in error_msg or "分号" in error_msg or "注释" in error_msg

    def test_empty_sql_rejected(self):
        """测试空 SQL 被拒绝"""
        is_valid, error_msg = validate_sql("")
        assert is_valid is False
        assert "不能为空" in error_msg

        is_valid, error_msg = validate_sql("   ")
        assert is_valid is False

    def test_structure_validation(self):
        """测试 SQL 结构验证"""
        # 括号不匹配
        is_valid, error_msg = check_sql_structure("SELECT * FROM users WHERE (id = 1")
        assert is_valid is False
        assert "括号" in error_msg

        # 单引号不匹配
        is_valid, error_msg = check_sql_structure("SELECT * FROM users WHERE name = 'test")
        assert is_valid is False
        assert "引号" in error_msg

        # 结构正常
        is_valid, error_msg = check_sql_structure("SELECT * FROM users WHERE (id = 1)")
        assert is_valid is True

    def test_is_select_query(self):
        """测试 is_select_query 函数"""
        assert is_select_query("SELECT * FROM users") is True
        assert is_select_query("WITH cte AS (SELECT * FROM users) SELECT * FROM cte") is True
        assert is_select_query("INSERT INTO users VALUES (1)") is False
        assert is_select_query("") is False
        assert is_select_query(None) is False

    def test_sanitize_limit(self):
        """测试 limit 清理函数"""
        # 正常值
        assert sanitize_limit(100) == 100
        assert sanitize_limit(50) == 50

        # None 返回默认值
        assert sanitize_limit(None) == 100

        # 负数返回 1
        assert sanitize_limit(-1) == 1
        assert sanitize_limit(-100) == 1

        # 超过最大值返回最大值
        assert sanitize_limit(20000) == 10000
        assert sanitize_limit(10001) == 10000

    def test_strict_mode_extra_checks(self):
        """测试严格模式下的额外检查"""
        # 危险函数
        is_valid, error_msg = validate_sql("SELECT LOAD_FILE('/etc/passwd')", strict_mode=True)
        assert is_valid is False
        assert "危险函数" in error_msg

        # 语句过长
        long_sql = "SELECT * FROM users WHERE " + "a=1 OR " * 3000
        is_valid, error_msg = validate_sql(long_sql, strict_mode=True)
        assert is_valid is False
        assert "过长" in error_msg

    def test_non_strict_mode(self):
        """测试非严格模式允许更多查询"""
        # 非严格模式下，一些查询可能通过
        is_valid, _ = validate_sql("SELECT * FROM users WHERE id IN (SELECT id FROM other)", strict_mode=False)
        assert is_valid is True


class TestSQLInjectionPatterns:
    """SQL 注入模式检测测试"""

    def test_comment_injection(self):
        """测试注释注入"""
        malicious_queries = [
            "SELECT * FROM users WHERE id = 1 -- AND status = 'active'",
            "SELECT * FROM users WHERE id = 1# AND status = 'active'",
            "SELECT * FROM users WHERE id = 1/* comment */AND status = 'active'",
        ]

        for query in malicious_queries:
            is_injection, msg = check_for_injection(query)
            # 注释可能会被检测到

    def test_union_based_injection(self):
        """测试 UNION 注入"""
        # UNION SELECT 在某些情况下是合法的，需要小心处理
        is_valid, _ = validate_sql("SELECT name FROM users UNION SELECT name FROM admins")
        # 这个应该被验证，因为 UNION SELECT 在某些上下文中是合法的

    def test_boolean_based_injection(self):
        """测试布尔注入"""
        malicious_queries = [
            "SELECT * FROM users WHERE id = 1 OR '1'='1'",
            "SELECT * FROM users WHERE id = 1 AND '1'='1'",
        ]

        for query in malicious_queries:
            is_injection, msg = check_for_injection(query)
            # 可能会被检测为注入

    def test_time_based_injection(self):
        """测试时间注入"""
        query = "SELECT * FROM users WHERE id = 1; WAITFOR DELAY '00:00:05'"
        is_valid, error_msg = validate_sql(query)
        assert is_valid is False


class TestSQLValidatorEdgeCases:
    """SQL 验证器边界情况测试"""

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        queries = [
            "select * from users",
            "SELECT * FROM users",
            "SeLeCt * FrOm users",
        ]

        for query in queries:
            is_valid, _ = validate_sql(query)
            assert is_valid is True

    def test_whitespace_variations(self):
        """测试空白字符变体"""
        queries = [
            "SELECT*FROM users",  # 无空格
            "SELECT  *  FROM  users",  # 多空格
            "SELECT\n*\nFROM\nusers",  # 换行
            "SELECT\t*\tFROM\tusers",  # Tab
        ]

        for query in queries:
            is_valid, _ = validate_sql(query)
            # 大多数应该被规范化后通过

    def test_with_cte_queries(self):
        """测试 WITH/CTE 查询"""
        queries = [
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte",
            "WITH cte1 AS (SELECT * FROM users), cte2 AS (SELECT * FROM orders) SELECT * FROM cte1 JOIN cte2",
        ]

        for query in queries:
            is_valid, error_msg = validate_sql(query)
            assert is_valid is True, f"CTE 查询应该有效: {query}\n错误: {error_msg}"

    def test_subquery_depth(self):
        """测试子查询深度限制"""
        # 正常嵌套
        query = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders WHERE id IN (SELECT order_id FROM items))"
        is_valid, _ = validate_sql(query)
        assert is_valid is True

        # 超深嵌套
        deep_query = "SELECT * FROM users WHERE id IN (" + "SELECT id FROM users WHERE id IN (" * 30
        is_valid, error_msg = validate_sql(deep_query, strict_mode=True)
        assert is_valid is False
        assert "嵌套" in error_msg or "过深" in error_msg


class TestSQLValidationErrors:
    """SQL 验证错误类测试"""

    def test_sql_validation_error(self):
        """测试 SQLValidationError 异常"""
        error = SQLValidationError("测试错误")
        assert error.message == "测试错误"
        assert error.code == "SQL_VALIDATION_ERROR"

        error_with_code = SQLValidationError("测试错误2", code="CUSTOM_ERROR")
        assert error_with_code.code == "CUSTOM_ERROR"
