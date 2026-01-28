from langchain.agents import create_agent
from tools import execute_sql_query, search_knowledge_graph, get_table_schema
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
load_dotenv()
from langchain.agents import create_agent

# ============= 配置 =============
SYSTEM_PROMPT = """你是一个专业的数据分析智能体。

## 可用工具
1. **get_table_schema** - 获取数据库表结构信息
2. **search_knowledge_graph** - 搜索知识图谱，查找历史 SQL 和业务逻辑
3. **execute_sql_query** - 执行 SQL 查询（仅支持 SELECT）

## 工作流程
1. 理解用户问题
2. 如有需要，先用 get_table_schema 了解表结构
3. 用 search_knowledge_graph 查找相关历史查询和业务逻辑
4. 生成并执行 SQL 查询
5. 整理结果回答用户

请用清晰、专业的方式回答用户的数据分析问题。
"""


# ============= 模型和 Agent =============
_agent = None

def get_agent():
    """延迟初始化 Agent"""
    global _agent
    if _agent is None:
        model = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
        )
        tools = [execute_sql_query, search_knowledge_graph]
        _agent = create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)
    return _agent

if __name__ == "__main__":
    agent = get_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "请问还款率是如何计算的"}]}
    )
    print(result)