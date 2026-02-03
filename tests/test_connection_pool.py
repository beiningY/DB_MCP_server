"""
连接池管理单元测试
测试数据库连接池的创建、复用和清理
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from db_mcp.connection_pool import (
    get_engine,
    close_pool,
    close_all_pools,
    get_pool_stats,
    get_pool_info,
    test_connection as test_connection_func,  # 重命名避免冲突
    _make_pool_key,
    DBConnection,
    _pools,  # 导入全局变量以便清理
)
from sqlalchemy import Engine


@pytest.fixture(autouse=True)
def reset_pools_before_each_test():
    """每个测试前清理连接池"""
    close_all_pools()
    yield


class TestPoolKeyGeneration:
    """连接池 Key 生成测试"""

    def test_make_pool_key(self):
        """测试连接池 key 生成"""
        key = _make_pool_key("localhost", 3306, "root", "mydb")
        assert key == "localhost:3306@root@mydb"

        # 不同配置应该生成不同 key
        key2 = _make_pool_key("localhost", 3306, "admin", "mydb")
        assert key != key2

        # 相同配置应该生成相同 key
        key3 = _make_pool_key("localhost", 3306, "root", "mydb")
        assert key == key3

    def test_make_pool_key_excludes_password(self):
        """测试 key 不包含密码"""
        key1 = _make_pool_key("localhost", 3306, "root", "mydb")

        # 确认 key 不包含密码字段
        assert "password" not in key1
        assert "pass" not in key1.lower()


class TestEngineCreation:
    """引擎创建测试"""

    @patch('db_mcp.connection_pool.create_engine')
    def test_get_engine_creates_new_engine(self, mock_create_engine):
        """测试 get_engine 创建新引擎"""
        mock_engine = Mock(spec=Engine)
        mock_engine.pool = Mock()
        mock_engine.pool.size = Mock(return_value=5)
        mock_engine.pool.checkedin = Mock(return_value=5)
        mock_create_engine.return_value = mock_engine

        engine = get_engine("localhost", 3306, "root", "password", "mydb")

        # 应该调用 create_engine
        mock_create_engine.assert_called_once()
        assert engine is not None

    @patch('db_mcp.connection_pool.create_engine')
    def test_get_engine_reuses_existing_engine(self, mock_create_engine):
        """测试相同配置复用引擎"""
        mock_engine = Mock(spec=Engine)
        mock_engine.pool = Mock()
        mock_create_engine.return_value = mock_engine

        # 第一次调用
        engine1 = get_engine("localhost", 3306, "root", "pass1", "mydb")

        # 第二次调用（相同配置）
        engine2 = get_engine("localhost", 3306, "root", "pass2", "mydb")

        # 由于 key 不包含密码，应该复用同一个引擎
        assert engine1 is engine2

        # create_engine 只应该被调用一次
        assert mock_create_engine.call_count == 1

    @patch('db_mcp.connection_pool.create_engine')
    def test_get_engine_different_config_creates_new_pool(self, mock_create_engine):
        """测试不同配置创建新连接池"""
        mock_engine = Mock(spec=Engine)
        mock_engine.pool = Mock()
        mock_create_engine.return_value = mock_engine

        engine1 = get_engine("localhost", 3306, "root", "pass", "db1")
        engine2 = get_engine("localhost", 3306, "root", "pass", "db2")

        # 不同数据库应该创建不同的连接池
        assert mock_create_engine.call_count == 2


class TestPoolManagement:
    """连接池管理测试"""

    @patch('db_mcp.connection_pool.create_engine')
    def test_close_pool(self, mock_create_engine):
        """测试关闭单个连接池"""
        mock_engine = Mock(spec=Engine)
        mock_engine.pool = Mock()
        mock_create_engine.return_value = mock_engine

        # 创建一个连接池
        get_engine("localhost", 3306, "root", "pass", "mydb")

        # 关闭连接池
        close_pool("localhost", 3306, "root", "mydb")

        # 验证 engine.dispose() 被调用
        mock_engine.dispose.assert_called_once()

    def test_close_nonexistent_pool(self):
        """测试关闭不存在的连接池"""
        # 关闭不存在的连接池不应该抛出异常
        close_pool("nonexistent", 3306, "root", "mydb")

    @patch('db_mcp.connection_pool.create_engine')
    def test_close_all_pools(self, mock_create_engine):
        """测试关闭所有连接池"""
        mock_engine = Mock(spec=Engine)
        mock_engine.pool = Mock()
        mock_create_engine.return_value = mock_engine

        # 创建多个连接池
        get_engine("localhost", 3306, "root", "pass", "db1")
        get_engine("localhost", 3306, "root", "pass", "db2")

        # 关闭所有连接池
        close_all_pools()

        # 验证 dispose 被调用
        assert mock_engine.dispose.call_count == 2


class TestPoolStats:
    """连接池统计测试"""

    @patch('db_mcp.connection_pool.create_engine')
    def test_get_pool_stats(self, mock_create_engine):
        """测试获取连接池统计"""
        mock_pool = Mock()
        mock_pool.size = Mock(return_value=5)
        mock_pool.checkedin = Mock(return_value=3)
        mock_pool.checkedout = Mock(return_value=2)
        mock_pool.overflow = Mock(return_value=0)
        mock_pool._max_overflow = 10

        mock_engine = Mock(spec=Engine)
        mock_engine.pool = mock_pool
        mock_create_engine.return_value = mock_engine

        # 创建连接池
        get_engine("localhost", 3306, "root", "pass", "mydb")

        # 获取统计信息
        stats = get_pool_stats()

        assert len(stats) == 1
        assert "localhost:3306@root@mydb" in stats
        assert stats["localhost:3306@root@mydb"]["pool_size"] == 5

    def test_get_pool_info_empty(self):
        """测试空连接池信息"""
        info = get_pool_info()

        assert info["total_pools"] == 0
        assert info["pool_keys"] == []
        assert info["stats"] == {}


class TestDBConnection:
    """DBConnection 上下文管理器测试"""

    @patch('db_mcp.connection_pool.get_engine')
    def test_db_connection_context_manager(self, mock_get_engine):
        """测试 DBConnection 上下文管理器"""
        mock_engine = Mock(spec=Engine)
        mock_connection = Mock()
        mock_engine.connect.return_value = mock_connection
        mock_get_engine.return_value = mock_engine

        # 使用上下文管理器
        with DBConnection("localhost", 3306, "root", "pass", "mydb") as conn:
            # 验证连接被创建
            mock_engine.connect.assert_called_once()
            assert conn == mock_connection

        # 验证连接被关闭但引擎没有被销毁
        mock_connection.close.assert_called_once()
        mock_engine.dispose.assert_not_called()


class TestConnectionTest:
    """连接测试功能测试"""

    @patch('db_mcp.connection_pool.get_engine')
    def test_test_connection_success(self, mock_get_engine):
        """测试连接成功"""
        # Mock 连接和结果
        mock_result = Mock()
        mock_result.fetchone.return_value = (1,)

        mock_connection = Mock()
        mock_connection.execute.return_value = mock_result
        mock_connection.__enter__ = Mock(return_value=mock_connection)
        mock_connection.__exit__ = Mock(return_value=False)

        mock_engine = Mock(spec=Engine)
        mock_engine.connect.return_value = mock_connection
        mock_get_engine.return_value = mock_engine

        # 测试连接
        success, message = test_connection_func("localhost", 3306, "root", "pass", "mydb")

        assert success is True
        assert "成功" in message

    @patch('db_mcp.connection_pool.get_engine')
    def test_test_connection_failure(self, mock_get_engine):
        """测试连接失败"""
        from sqlalchemy.exc import SQLAlchemyError

        mock_engine = Mock(spec=Engine)
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")
        mock_get_engine.return_value = mock_engine

        # 测试连接
        success, message = test_connection_func("localhost", 3306, "root", "pass", "mydb")

        assert success is False
        assert "连接失败" in message or "异常" in message
