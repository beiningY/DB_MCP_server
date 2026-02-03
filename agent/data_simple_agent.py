"""
数据分析师 Agent（支持动态数据库连接）
基于 LangChain Agent 实现

该模块实现了一个数据分析 Agent，能够理解自然语言查询需求，
并调用三个内部工具（execute_sql_query、get_table_schema、search_knowledge_graph）
完成数据查询和分析任务。

Agent 工作流程：
1. 理解用户问题
2. 如有需要，先用 get_table_schema 了解表结构
3. 用 search_knowledge_graph 查找相关业务知识
4. 生成并执行 SQL 查询
5. 整理结果回答用户

使用方式：
    from agent.data_simple_agent import get_agent

    agent = get_agent()
    result = agent.invoke({
        "messages": [
            {
                "role": "system",
                "content": "数据库配置：..."
            },
            {"role": "user", "content": "查询用户表有多少条记录"}
        ]
    })
"""

from langchain.agents import create_agent
from tools import execute_sql_query, search_knowledge_graph, get_table_schema
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()


# ============================================================================
# 配置
# ============================================================================

SYSTEM_PROMPT = """你是一个专业的数据分析智能体。

## ���用工具
1. **execute_sql_query** - 执行 SQL 查询（仅支持 SELECT）
2. **get_table_schema** - 获取数据库表结构
3. **search_knowledge_graph** - 搜索知识图谱（业务逻辑、历史 SQL）

## 工作流程
1. 理解用户问题
2. 如有需要，先用 get_table_schema 了解表结构
3. 用 search_knowledge_graph 查找相关业务知识
4. 生成并执行 SQL 查询
5. 整理结果回答用户

## 重要提示
- 调用 execute_sql_query 和 get_table_schema 时，必须使用 system 消息中提供的数据库连接参数
- search_knowledge_graph 不需要数据库连接
- SQL 查询默认限制 100 行，如需更多数据请添加 LIMIT 子句

请用清晰、专业的方式回答用户的数据分析问题。
"""


# ============================================================================
# Agent 管理
# ============================================================================

# 全局 Agent 实例（延迟初始化）
_agent = None


def get_agent():
    """
    获取或创建 Agent 实例（延迟初始化）

    该函数使用延迟初始化模式，只在首次调用时创建 Agent 实例。
    后续调用会复用已创建的实例。

    环境变量配置：
        LLM_MODEL: 模型名称（默认 "gpt-4"）
        LLM_API_KEY: API 密钥（必需）
        LLM_BASE_URL: API 基础 URL（可选）

    Returns:
        LangChain Agent 实例

    Examples:
        >>> agent = get_agent()
        >>> result = agent.invoke({"messages": [...]})
    """
    global _agent
    if _agent is None:
        # 创建 LLM 实例
        model = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
        )

        # Agent 内部可用的工具
        tools = [
            execute_sql_query,
            search_knowledge_graph,
            get_table_schema
        ]

        # 创建 Agent
        _agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT
        )

    return _agent


# ============================================================================
# 测试入口
# ============================================================================

if __name__ == "__main__":
    """
    测试脚本

    运行该文件可以直接测试 Agent 功能。

    环境变量需要配置：
        - LLM_MODEL
        - LLM_API_KEY
        - LLM_BASE_URL（可选）
    """
    agent = get_agent()
    result = agent.invoke(
        {"messages": [
            {
                "role": "system",
                "content": """数据库配置：
- host: localhost
- port: 3306
- username: root
- password:
- database: test

调用 execute_sql_query 和 get_table_schema 时必须传入这些参数。"""
            },
            {"role": "user", "content": "还款率是如何计算的"}
        ]}
    )
    print(result)
