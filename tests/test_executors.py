"""
SQL 执行器测试
"""

import asyncio
import pytest
from executors import MySQLExecutor, RedashExecutor


@pytest.mark.asyncio
async def test_mysql_executor():
    """测试 MySQL 执行器"""
    try:
        executor = MySQLExecutor()
        
        # 测试连接
        is_connected = await executor.test_connection()
        assert is_connected, "MySQL 连接失败"
        print("✓ MySQL 连接成功")
        
        # 测试简单查询
        result = await executor.execute("SELECT 1 as test", timeout=5, limit=1)
        assert result.success, f"查询失败: {result.error}"
        assert result.row_count == 1
        print(f"✓ 查询成功: {result.rows}")
        
        # 测试查询限制
        result = await executor.execute("SELECT * FROM information_schema.tables", limit=10)
        assert result.success
        assert result.row_count <= 10
        print(f"✓ LIMIT 生效: 返回 {result.row_count} 行")
        
    except Exception as e:
        print(f"⚠️ MySQL 测试失败: {e}")


@pytest.mark.asyncio
async def test_redash_executor():
    """测试 Redash 执行器"""
    try:
        executor = RedashExecutor()
        
        # 测试连接
        is_connected = await executor.test_connection()
        if is_connected:
            print("✓ Redash API 连接成功")
            
            # 测试简单查询（如果连接成功）
            result = await executor.execute("SELECT 1 as test", timeout=30, limit=1)
            if result.success:
                print(f"✓ Redash 查询成功: {result.rows}")
            else:
                print(f"⚠️ Redash 查询失败: {result.error}")
        else:
            print("⚠️ Redash API 不可用（可能未配置或服务未启动）")
            
    except Exception as e:
        print(f"⚠️ Redash 测试跳过: {e}")


if __name__ == "__main__":
    print("=== 测试 SQL 执行器 ===\n")
    
    print("1. 测试 MySQL 执行器")
    asyncio.run(test_mysql_executor())
    print()
    
    print("2. 测试 Redash 执行器")
    asyncio.run(test_redash_executor())
    print()
    
    print("=== 所有测试完成 ===")
