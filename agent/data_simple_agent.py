from langchain.agents import create_agent
from tools import execute_sql_query, search_knowledge_graph, get_table_schema
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
load_dotenv()
from langchain.agents import create_agent
model = ChatOpenAI(
    model=os.getenv("LLM_MODEL"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)
system_prompt = """
你是一个数据分析智能体，请你调用工具回答用户的问题
"""
user_question = "请问还款率是如何计算的"
tools = [execute_sql_query, search_knowledge_graph, get_table_schema]
agent = create_agent(model=model, tools=tools, system_prompt=system_prompt)
result = agent.invoke(
    {"messages": [{"role": "user", "content": user_question}]}
)
print(result)