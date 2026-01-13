"""
基础测试 - 不需要任何外部依赖
测试各个模块的基本功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio


def test_imports():
    """测试模块导入"""
    print("\n=== 测试 1: 模块导入 ===")
    
    try:
        from knowledge import OnlineDictionaryModule, SingaBIMetadataModule, LightRAGClient
        print("✓ 知识模块导入成功")
    except Exception as e:
        print(f"❌ 知识模块导入失败: {e}")
        return False
    
    try:
        from executors import MySQLExecutor, RedashExecutor, MockExecutor
        print("✓ 执行器模块导入成功")
    except Exception as e:
        print(f"❌ 执行器模块导入失败: {e}")
        return False
    
    try:
        from tools.analyst_tools import (
            MetadataSearchTool,
            HistoricalQuerySearchTool,
            SQLExecutorTool,
            QueryOptimizationTool,
            DataAnalysisTool
        )
        print("✓ 工具模块导入成功")
    except Exception as e:
        print(f"❌ 工具模块导入失败: {e}")
        return False
    
    try:
        from agent import DataAnalystAgent
        print("✓ Agent 模块导入成功")
    except Exception as e:
        print(f"❌ Agent 模块导入失败: {e}")
        return False
    
    return True


async def test_online_dictionary():
    """测试在线字典模块"""
    print("\n=== 测试 2: 在线字典模块 ===")
    
    try:
        from knowledge import OnlineDictionaryModule
        
        module = OnlineDictionaryModule()
        print(f"✓ 模块初始化成功")
        print(f"  总表数: {len(module.dictionary)}")
        
        # 测试搜索表
        result = await module.search_table("temp_rc_model_daily")
        print(f"✓ 搜索表 'temp_rc_model_daily': {result['total']} 个结果")
        
        # 测试搜索字段
        result = await module.search_column("status")
        print(f"✓ 搜索字段 'status': {result['total']} 个结果")
        
        return True
    except Exception as e:
        print(f"❌ 在线字典测试失败: {e}")
        return False


async def test_metadata_module():
    """测试元数据模块"""
    print("\n=== 测试 3: BI 元数据模块 ===")
    
    try:
        from knowledge import SingaBIMetadataModule
        
        module = SingaBIMetadataModule()
        print(f"✓ 模块初始化成功")
        
        tables = module.metadata.get('tables', [])
        print(f"  总表数: {len(tables)}")
        
        # 测试搜索表
        result = await module.search_tables("loan")
        print(f"✓ 搜索表 'loan': {result['total']} 个结果")
        
        # 测试业务域
        domains = module.get_all_domains()
        print(f"✓ 业务域数量: {len(domains)}")
        print(f"  业务域: {domains[:3]}...")
        
        return True
    except Exception as e:
        print(f"❌ 元数据模块测试失败: {e}")
        return False


async def test_mock_executor():
    """测试 Mock 执行器"""
    print("\n=== 测试 4: Mock 执行器 ===")
    
    try:
        from executors import MockExecutor
        
        executor = MockExecutor()
        print("✓ Mock 执行器初始化成功")
        
        # 测试连接
        is_connected = await executor.test_connection()
        print(f"✓ 连接测试: {'成功' if is_connected else '失败'}")
        
        # 测试查询
        sql = "SELECT COUNT(*) FROM information_schema.tables"
        result = await executor.execute(sql)
        
        if result.success:
            print(f"✓ SQL 执行成功")
            print(f"  返回行数: {result.row_count}")
            print(f"  执行时间: {result.execution_time:.3f}秒")
            print(f"  结果: {result.rows}")
        else:
            print(f"❌ SQL 执行失败: {result.error}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Mock 执行器测试失败: {e}")
        return False


async def test_tools():
    """测试工具"""
    print("\n=== 测试 5: 工具模块 ===")
    
    try:
        from knowledge import OnlineDictionaryModule, SingaBIMetadataModule
        from executors import MockExecutor
        from tools.analyst_tools import MetadataSearchTool, SQLExecutorTool
        
        # 测试元数据搜索工具
        online_dict = OnlineDictionaryModule()
        metadata = SingaBIMetadataModule()
        tool = MetadataSearchTool(online_dict, metadata)
        
        print(f"✓ 元数据搜索工具创建成功")
        print(f"  工具名称: {tool.name}")
        
        # 测试 SQL 执行工具
        mock_executor = MockExecutor()
        sql_tool = SQLExecutorTool(mock_executor, mock_executor)
        
        print(f"✓ SQL 执行工具创建成功")
        print(f"  工具名称: {sql_tool.name}")
        
        return True
    except Exception as e:
        print(f"❌ 工具测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有基础测试"""
    print("="*60)
    print("🧪 基础功能测试")
    print("📝 测试各模块的基本功能（无需外部连接）")
    print("="*60)
    
    results = []
    
    # 同步测试
    results.append(("模块导入", test_imports()))
    
    # 异步测试
    async def run_async_tests():
        test_results = []
        test_results.append(("在线字典", await test_online_dictionary()))
        test_results.append(("元数据模块", await test_metadata_module()))
        test_results.append(("Mock执行器", await test_mock_executor()))
        test_results.append(("工具模块", await test_tools()))
        return test_results
    
    async_results = asyncio.run(run_async_tests())
    results.extend(async_results)
    
    # 输出总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有基础测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
    
    print("="*60)


if __name__ == "__main__":
    main()
