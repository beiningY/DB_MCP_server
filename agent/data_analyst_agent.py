"""
数据分析师 Agent
基于 Plan-Execute-Replan 模式，集成知识模块和 SQL 执行器
"""

import os
import operator
from typing import Annotated, List, Tuple, Union
from typing_extensions import TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent


load_dotenv()

# 导入工具
from tools import execute_sql_query, search_knowledge_graph, get_table_schema


# ============= 状态定义 =============
class PlanExecute(TypedDict):
    """Agent 状态"""
    input: str
    plan: List[str]
    past_steps: Annotated[List[Tuple], operator.add]
    response: str


# ============= Schema 定义 =============
class Plan(BaseModel):
    """执行计划"""
    steps: List[str] = Field(
        description="要执行的步骤列表，按顺序排列"
    )


class Response(BaseModel):
    """最终响应"""
    response: str


class Act(BaseModel):
    """行动：继续执行或返回结果"""
    action: Union[Response, Plan] = Field(
        description="下一步行动。如果要响应用户，使用 Response；如果需要继续执行，使用 Plan"
    )


# ============= 初始化 LLM =============
def get_llm():
    """获取 LLM 实例"""
    llm_model = os.getenv("LLM_MODEL", "gpt-4")
    llm_base_url = os.getenv("LLM_BASE_URL")
    llm_api_key = os.getenv("LLM_API_KEY")
    
    
    return ChatOpenAI(
        model=llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key,
    )


# ============= Planner =============
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的数据分析任务规划师，擅长将复杂的数据分析需求拆解为清晰的执行步骤。

## 可用工具
1. **get_table_schema** - 获取数据库表结构
   - 不带参数：获取所有表列表
   - 指定表名：获取该表的详细字段信息
   
2. **search_knowledge_graph** - 搜索知识图谱（历史 SQL、业务逻辑）
   - 查找相似的历史查询
   - 了解表和字段的业务含义
   
3. **execute_sql_query** - 执行 SQL 查询
   - 支持 SELECT 查询
   - 自动添加 LIMIT 保护

## 规划原则
1. 在生成 SQL 前，**务必**先使用 get_table_schema 确认表名和字段
2. 对于复杂业务逻辑，使用 search_knowledge_graph 参考历史查询
3. 复杂查询应该分步骤验证
4. 每个步骤应该清晰、具体、可执行

## 示例步骤
- "使用 get_table_schema 获取所有表列表，找到与放款相关的表"
- "使用 get_table_schema('orders') 查看 orders 表的字段结构"
- "使用 search_knowledge_graph 搜索'如何计算放款金额'的历史查询"
- "执行 SQL: SELECT COUNT(*) FROM orders WHERE date = '2024-01-01'"

## 重要：输出格式
你必须返回一个 JSON 对象，包含 steps 数组，每个元素是一个步骤的文字描述。
注意：steps 是字符串数组，不是工具调用！

正确示例：
{{"steps": ["使用 get_table_schema 获取所有表列表", "根据表名查询相关数据"]}}

错误示例（不要这样）：
{{"tool": "get_table_schema", "args": []}}
"""),
    ("placeholder", "{messages}"),
])

# ============= Replanner =============
replanner_prompt = ChatPromptTemplate.from_template("""你是一个数据分析任务重规划师。
根据已完成的步骤和当前状态，决定接下来的行动。

原始目标: {input}
原始计划: {plan}
已完成步骤: {past_steps}

## 决策原则
- 如果已经获得足够信息可以回答用户问题，返回 Response
- 如果任务未完成或需要修正，返回更新后的 Plan
- 如果 SQL 执行失败，分析错误并修正

## 输出格式
请以 JSON 格式返回，二选一：
- 结束任务：{{"action": {{"response": "最终回答内容"}}}}
- 继续执行：{{"action": {{"steps": ["步骤1", "步骤2", ...]}}}}
""")


# ============= 延迟初始化（避免模块加载时调用 LLM） =============
_planner = None
_replanner = None
_agent_executor = None


def get_planner():
    """延迟获取 Planner"""
    global _planner
    if _planner is None:
        # 使用 json_mode 避免某些模型返回尾部字符的问题
        _planner = planner_prompt | get_llm().with_structured_output(
            Plan, 
            method="json_mode"
        )
    return _planner


def get_replanner():
    """延迟获取 Replanner"""
    global _replanner
    if _replanner is None:
        _replanner = replanner_prompt | get_llm().with_structured_output(
            Act,
            method="json_mode"
        )
    return _replanner


def get_agent_executor():
    """延迟获取 Agent Executor"""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = create_agent(
            model=os.getenv("LLM_MODEL"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            tools=[execute_sql_query, search_knowledge_graph, get_table_schema]
        )
    return _agent_executor


# ============= Workflow 节点 =============
async def plan_step(state: PlanExecute):
    """规划步骤"""
    plan = await get_planner().ainvoke({"messages": [("user", state["input"])]})
    return {"plan": plan.steps}


async def execute_step(state: PlanExecute):
    """执行步骤"""
    plan = state["plan"]
    plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
    task = plan[0]
    
    task_formatted = f"""根据以下计划执行第一步:
{plan_str}

当前任务: {task}

请使用可用工具完成这个任务。"""
    
    agent_response = await get_agent_executor().ainvoke(
        {"messages": [("user", task_formatted)]}
    )
    
    return {
        "past_steps": [(task, agent_response["messages"][-1].content)],
    }


async def replan_step(state: PlanExecute):
    """重新规划"""
    output = await get_replanner().ainvoke(state)
    
    if isinstance(output.action, Response):
        return {"response": output.action.response}
    else:
        return {"plan": output.action.steps}


def should_end(state: PlanExecute):
    """判断是否结束"""
    if "response" in state and state["response"]:
        return END
    else:
        return "agent"


# ============= 构建 Workflow =============
workflow = StateGraph(PlanExecute)

# 添加节点
workflow.add_node("planner", plan_step)
workflow.add_node("agent", execute_step)
workflow.add_node("replan", replan_step)

# 添加边
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "agent")
workflow.add_edge("agent", "replan")
workflow.add_conditional_edges(
    "replan",
    should_end,
    ["agent", END],
)

# 编译
app = workflow.compile()


# ============= 主函数（用于测试） =============
async def main():
    """测试函数"""
    config = {"recursion_limit": 50}
    inputs = {"input": "查询 singa_bi 数据库中有多少个表"}
    
    print("开始执行...")
    async for event in app.astream(inputs, config=config):
        for k, v in event.items():
            if k != "__end__":
                print(f"\n=== {k} ===")
                print(v)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
