"""
数据分析师 Agent 集成测试
"""

import asyncio
import os
from dotenv import load_dotenv
from agent import DataAnalystAgent as create_data_analyst_agent

# 加载环境变量
load_dotenv()


async def test_simple_query():
    """测试简单查询"""
    print("\n=== 测试案例 1: 简单查询 ===")
    
    agent = create_data_analyst_agent(
        mysql_url=os.getenv("DB_URL"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4"),
        llm_api_key=os.getenv("LLM_API_KEY")
    )
    
    question = "查询 singa_bi 数据库中有多少个表"
    print(f"问题: {question}\n")
    
    result = await agent.analyze(question, max_iterations=5)
    print(f"回答:\n{result}\n")


async def test_metadata_query():
    """测试元数据查询"""
    print("\n=== 测试案例 2: 元数据查询 ===")
    
    agent = create_data_analyst_agent(
        mysql_url=os.getenv("DB_URL"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4"),
        llm_api_key=os.getenv("LLM_API_KEY")
    )
    
    question = "temp_rc_model_daily 表的 machine_status 字段是什么含义？"
    print(f"问题: {question}\n")
    
    result = await agent.analyze(question, max_iterations=5)
    print(f"回答:\n{result}\n")


async def test_business_query():
    """测试业务查询"""
    print("\n=== 测试案例 3: 业务数据查询 ===")
    
    agent = create_data_analyst_agent(
        mysql_url=os.getenv("DB_URL"),
        redash_url=os.getenv("REDASH_URL"),
        redash_api_key=os.getenv("REDASH_API_KEY"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        lightrag_url=os.getenv("LIGHTRAG_API_URL")
    )
    
    question = "查询 cyc_Loan_summary_app 表中最新的 10 条记录"
    print(f"问题: {question}\n")
    
    result = await agent.analyze(question, max_iterations=8)
    print(f"回答:\n{result}\n")


async def test_historical_query():
    """测试历史查询搜索"""
    print("\n=== 测试案例 4: 历史查询搜索 ===")
    
    agent = create_data_analyst_agent(
        mysql_url=os.getenv("DB_URL"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        lightrag_url=os.getenv("LIGHTRAG_API_URL")
    )
    
    question = "找一个计算放款金额的历史查询作为参考"
    print(f"问题: {question}\n")
    
    result = await agent.analyze(question, max_iterations=5)
    print(f"回答:\n{result}\n")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("数据分析师 Agent 集成测试")
    print("=" * 60)
    
    tests = [
        ("简单查询", test_simple_query),
        ("元数据查询", test_metadata_query),
        ("业务数据查询", test_business_query),
        ("历史查询搜索", test_historical_query)
    ]
    
    for name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            print(f"❌ {name} 测试失败: {e}\n")
    
    print("=" * 60)
    print("所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    # 检查必要的环境变量
    required_vars = ["DB_URL", "LLM_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️ 缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请在 .env 文件中配置这些变量")
        exit(1)
    
    # 运行测试
    asyncio.run(main())
