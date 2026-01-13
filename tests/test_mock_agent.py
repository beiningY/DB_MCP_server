"""
使用 Mock 执行器测试数据分析师 Agent
不需要真实的数据库和 Redash 连接
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def test_mock_agent_simple():
    """测试基础功能 - 使用 Mock 执行器"""
    print("\n" + "="*60)
    print("测试 1: 简单查询（Mock 模式）")
    print("="*60)
    
    # 动态导入，避免在模块级别就需要数据库连接
    from agent.data_analyst_agent import DataAnalystAgent
    from executors import MockExecutor
    
    # 创建 Mock 执行器
    mock_executor = MockExecutor()
    
    # 创建 Agent（使用 Mock 执行器）
    agent = DataAnalystAgent(
        mysql_config={},  # 不需要真实配置
        redash_config={},
        llm_config={
            'model': os.getenv('LLM_MODEL', 'gpt-4'),
            'api_key': os.getenv('LLM_API_KEY')
        }
    )
    
    # 替换为 Mock 执行器
    agent.mysql_executor = mock_executor
    agent.redash_executor = mock_executor
    
    # 重新初始化工具（使用 Mock 执行器）
    agent._initialize_tools()
    agent._initialize_agent_executor()
    
    question = "查询数据库中有多少个表"
    print(f"\n问题: {question}")
    print("使用执行器: Mock\n")
    
    try:
        result = await agent.analyze(question, max_iterations=5)
        print(f"✓ 回答:\n{result}\n")
        print(f"✓ Mock 执行次数: {mock_executor.execution_count}")
    except Exception as e:
        print(f"❌ 测试失败: {e}\n")


async def test_mock_agent_metadata():
    """测试元数据查询 - 不需要执行器"""
    print("\n" + "="*60)
    print("测试 2: 元数据查询（无需数据库连接）")
    print("="*60)
    
    from agent.data_analyst_agent import DataAnalystAgent
    from executors import MockExecutor
    
    mock_executor = MockExecutor()
    
    agent = DataAnalystAgent(
        mysql_config={},
        redash_config={},
        llm_config={
            'model': os.getenv('LLM_MODEL', 'gpt-4'),
            'api_key': os.getenv('LLM_API_KEY')
        }
    )
    
    agent.mysql_executor = mock_executor
    agent.redash_executor = mock_executor
    agent._initialize_tools()
    agent._initialize_agent_executor()
    
    question = "temp_rc_model_daily 表的 machine_status 字段是什么含义？"
    print(f"\n问题: {question}")
    print("使用执行器: Mock\n")
    
    try:
        result = await agent.analyze(question, max_iterations=5)
        print(f"✓ 回答:\n{result}\n")
    except Exception as e:
        print(f"❌ 测试失败: {e}\n")


async def test_mock_agent_business_query():
    """测试业务查询 - 使用 Mock 数据"""
    print("\n" + "="*60)
    print("测试 3: 业务数据查询（Mock 数据）")
    print("="*60)
    
    from agent.data_analyst_agent import DataAnalystAgent
    from executors import MockExecutor
    
    mock_executor = MockExecutor()
    
    agent = DataAnalystAgent(
        mysql_config={},
        redash_config={},
        llm_config={
            'model': os.getenv('LLM_MODEL', 'gpt-4'),
            'api_key': os.getenv('LLM_API_KEY')
        }
    )
    
    agent.mysql_executor = mock_executor
    agent.redash_executor = mock_executor
    agent._initialize_tools()
    agent._initialize_agent_executor()
    
    question = "查询 cyc_Loan_summary_app 表中最新的放款记录"
    print(f"\n问题: {question}")
    print("使用执行器: Mock（返回模拟放款数据）\n")
    
    try:
        result = await agent.analyze(question, max_iterations=8)
        print(f"✓ 回答:\n{result}\n")
        print(f"✓ Mock 执行次数: {mock_executor.execution_count}")
    except Exception as e:
        print(f"❌ 测试失败: {e}\n")


async def test_mock_executor_directly():
    """直接测试 Mock 执行器"""
    print("\n" + "="*60)
    print("测试 4: Mock 执行器直接测试")
    print("="*60)
    
    from executors import MockExecutor
    
    executor = MockExecutor()
    
    # 测试各种 SQL
    test_sqls = [
        "SELECT COUNT(*) FROM information_schema.tables",
        "SELECT * FROM cyc_Loan_summary_app LIMIT 10",
        "SELECT date, COUNT(*) as user_count FROM users GROUP BY date",
        "SELECT SUM(amount) as total FROM orders"
    ]
    
    for sql in test_sqls:
        print(f"\nSQL: {sql}")
        result = await executor.execute(sql)
        
        if result.success:
            print(f"✓ 成功: {result.row_count} 行, 耗时 {result.execution_time:.2f}秒")
            print(f"  列: {result.columns}")
            print(f"  数据: {result.rows[:2]}")  # 只显示前2行
        else:
            print(f"❌ 失败: {result.error}")
    
    print(f"\n✓ 总执行次数: {executor.execution_count}")


async def test_knowledge_modules():
    """测试知识模块 - 不需要数据库"""
    print("\n" + "="*60)
    print("测试 5: 知识模块（无需数据库连接）")
    print("="*60)
    
    try:
        from knowledge import OnlineDictionaryModule, SingaBIMetadataModule
        
        # 测试在线字典
        print("\n1. 测试在线字典模块:")
        online_dict = OnlineDictionaryModule()
        result = await online_dict.search_table("temp_rc_model_daily", fuzzy=False)
        print(f"✓ 找到表: {result['total']} 个")
        if result['results']:
            print(f"  表注释: {result['results'][0]['table_comment']}")
        
        # 测试元数据模块
        print("\n2. 测试 BI 元数据模块:")
        metadata = SingaBIMetadataModule()
        result = await metadata.search_tables("loan", fuzzy=True)
        print(f"✓ 找到表: {result['total']} 个")
        
        # 测试业务域
        domains = metadata.get_all_domains()
        print(f"✓ 业务域: {domains[:5]}...")  # 只显示前5个
        
    except Exception as e:
        print(f"❌ 知识模块测试失败: {e}")


async def main():
    """运行所有 Mock 测试"""
    print("\n" + "="*70)
    print("🧪 数据分析师 Agent Mock 测试")
    print("📝 不需要真实的数据库和 Redash 连接")
    print("="*70)
    
    # 检查 LLM API KEY
    if not os.getenv('LLM_API_KEY'):
        print("\n⚠️ 警告: 未设置 LLM_API_KEY 环境变量")
        print("某些测试可能会失败，但知识模块和 Mock 执行器测试仍可运行\n")
    
    tests = [
        ("Mock 执行器直接测试", test_mock_executor_directly),
        ("知识模块测试", test_knowledge_modules),
        ("简单查询", test_mock_agent_simple),
        ("元数据查询", test_mock_agent_metadata),
        ("业务数据查询", test_mock_agent_business_query),
    ]
    
    for name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            print(f"\n❌ {name} 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("✓ Mock 测试完成")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
