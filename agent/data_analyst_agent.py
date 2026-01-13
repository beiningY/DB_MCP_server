"""
数据分析师 Agent
基于 Plan-Execute-Replan 模式，集成知识模块和 SQL 执行器
"""

import operator
import os
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent

from pydantic import BaseModel, Field

# 导入提示词
from .prompts import (
    planner_prompt,
    replanner_prompt,
    AGENT_EXECUTOR_SYSTEM_PROMPT
)

# 导入知识模块
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from knowledge import (
    OnlineDictionaryModule,
    SingaBIMetadataModule,
    LightRAGClient
)
from executors import MySQLExecutor, RedashExecutor
from tools.analyst_tools import (
    MetadataSearchTool,
    HistoricalQuerySearchTool,
    SQLExecutorTool,
    QueryOptimizationTool,
    DataAnalysisTool
)


# ============= State 定义 =============
class DataAnalystState(TypedDict):
    """数据分析师 Agent 状态"""
    input: str  # 用户问题
    plan: List[str]  # 执行计划
    past_steps: Annotated[List[Tuple], operator.add]  # 已执行步骤
    response: str  # 最终响应


# ============= Pydantic 模型 =============
class Plan(BaseModel):
    """执行计划"""
    steps: List[str] = Field(
        description="执行步骤列表，按顺序排列"
    )


class Response(BaseModel):
    """最终响应"""
    response: str = Field(
        description="给用户的最终回复"
    )


class Act(BaseModel):
    """行动决策"""
    action: Response | Plan = Field(
        description="下一步行动：Response（结束）或 Plan（继续）"
    )


# ============= 数据分析师 Agent =============
class DataAnalystAgent:
    """
    数据分析师 Agent
    
    架构：Plan-Execute-Replan
    - Planner: 制定执行计划
    - Executor: 使用 ReAct Agent 执行步骤
    - Replanner: 根据结果重新规划或结束
    """
    
    def __init__(
        self,
        mysql_config: Optional[Dict[str, Any]] = None,
        redash_config: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        lightrag_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化数据分析师 Agent
        
        Args:
            mysql_config: MySQL 配置 {'db_url': ...}
            redash_config: Redash 配置 {'redash_url': ..., 'api_key': ...}
            llm_config: LLM 配置 {'model': ..., 'api_key': ..., 'base_url': ...}
            lightrag_config: LightRAG 配置 {'api_url': ..., 'api_key': ...}
        """
        self.mysql_config = mysql_config or {}
        self.redash_config = redash_config or {}
        self.llm_config = llm_config or {}
        self.lightrag_config = lightrag_config or {}
        
        # 初始化组件
        self._initialize_knowledge_modules()
        self._initialize_executors()
        self._initialize_llm()
        self._initialize_tools()
        self._initialize_agent_executor()
        self._initialize_graph()
        
        print("✓ 数据分析师 Agent 初始化完成")
    
    def _initialize_knowledge_modules(self):
        """初始化知识模块"""
        try:
            self.online_dict = OnlineDictionaryModule()
            print("  ✓ 在线字典模块已加载")
        except Exception as e:
            print(f"  ⚠️ 在线字典模块加载失败: {e}")
            self.online_dict = None
        
        try:
            self.metadata = SingaBIMetadataModule()
            print("  ✓ BI 元数据模块已加载")
        except Exception as e:
            print(f"  ⚠️ BI 元数据模块加载失败: {e}")
            self.metadata = None
        
        try:
            self.lightrag = LightRAGClient(
                api_url=self.lightrag_config.get('api_url'),
                api_key=self.lightrag_config.get('api_key')
            )
            print("  ✓ LightRAG 客户端已初始化")
        except Exception as e:
            print(f"  ⚠️ LightRAG 客户端初始化失败: {e}")
            self.lightrag = None
    
    def _initialize_executors(self):
        """初始化 SQL 执行器"""
        try:
            self.mysql_executor = MySQLExecutor(self.mysql_config)
            print("  ✓ MySQL 执行器已初始化")
        except Exception as e:
            print(f"  ⚠️ MySQL 执行器初始化失败: {e}")
            self.mysql_executor = None
        
        try:
            self.redash_executor = RedashExecutor(self.redash_config)
            print("  ✓ Redash 执行器已初始化")
        except Exception as e:
            print(f"  ⚠️ Redash 执行器初始化失败: {e}")
            self.redash_executor = None
    
    def _initialize_llm(self):
        """初始化 LLM"""
        model = self.llm_config.get('model') or os.getenv('LLM_MODEL', 'gpt-4')
        api_key = self.llm_config.get('api_key') or os.getenv('LLM_API_KEY')
        base_url = self.llm_config.get('base_url') or os.getenv('LLM_BASE_URL')
        
        llm_kwargs = {
            'model': model,
            'temperature': 0
        }
        if api_key:
            llm_kwargs['api_key'] = api_key
        if base_url:
            llm_kwargs['base_url'] = base_url
        
        self.llm = ChatOpenAI(**llm_kwargs)
        print(f"  ✓ LLM 已初始化: {model}")
    
    def _initialize_tools(self):
        """初始化工具集"""
        self.tools = []
        
        # 1. 元数据搜索工具
        if self.online_dict and self.metadata:
            self.tools.append(
                MetadataSearchTool(self.online_dict, self.metadata)
            )
        
        # 2. 历史查询搜索工具
        if self.lightrag:
            self.tools.append(
                HistoricalQuerySearchTool(self.lightrag)
            )
        
        # 3. SQL 执行工具
        if self.mysql_executor and self.redash_executor:
            self.tools.append(
                SQLExecutorTool(self.mysql_executor, self.redash_executor)
            )
        
        # 4. 查询优化工具
        self.tools.append(QueryOptimizationTool())
        
        # 5. 数据分析工具
        self.tools.append(DataAnalysisTool())
        
        print(f"  ✓ 工具集已初始化: {len(self.tools)} 个工具")
    
    def _initialize_agent_executor(self):
        """初始化 Agent 执行器（ReAct Agent）"""
        # 将 BaseTool 转换为 LangChain 工具格式
        from langchain_core.tools import tool as langchain_tool
        
        langchain_tools = []
        for t in self.tools:
            # 创建异步函数包装器
            async def tool_wrapper(tool_instance=t, **kwargs):
                result = await tool_instance.execute(kwargs)
                # 提取文本内容
                if result and len(result) > 0:
                    return result[0].text
                return "执行完成，但没有返回结果"
            
            # 使用 tool 装饰器
            lc_tool = langchain_tool(
                name=t.name,
                description=t.description,
                args_schema=None  # 暂时不使用严格的 schema
            )(tool_wrapper)
            
            langchain_tools.append(lc_tool)
        
        # 创建 ReAct Agent
        self.agent_executor = create_react_agent(
            self.llm,
            langchain_tools,
            state_modifier=AGENT_EXECUTOR_SYSTEM_PROMPT
        )
        
        print("  ✓ Agent 执行器已创建")
    
    def _initialize_graph(self):
        """初始化 LangGraph 工作流"""
        workflow = StateGraph(DataAnalystState)
        
        # 添加节点
        workflow.add_node("planner", self.plan_step)
        workflow.add_node("agent", self.execute_step)
        workflow.add_node("replan", self.replan_step)
        
        # 添加边
        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "agent")
        workflow.add_edge("agent", "replan")
        
        # 条件边：决定继续还是结束
        workflow.add_conditional_edges(
            "replan",
            self.should_end,
            {
                "continue": "agent",
                "end": END
            }
        )
        
        # 编译
        self.app = workflow.compile()
        print("  ✓ LangGraph 工作流已编译")
    
    async def plan_step(self, state: DataAnalystState) -> Dict:
        """规划步骤"""
        messages = [HumanMessage(content=state["input"])]
        plan = await (planner_prompt | self.llm.with_structured_output(Plan)).ainvoke(
            {"messages": messages}
        )
        return {"plan": plan.steps}
    
    async def execute_step(self, state: DataAnalystState) -> Dict:
        """执行步骤"""
        plan = state["plan"]
        plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))
        
        # 当前任务
        task = plan[0]
        task_formatted = f"""对于以下计划：
{plan_str}

你当前需要执行步骤 1: {task}

用户原始问题: {state['input']}
"""
        
        # 调用 Agent Executor
        response = await self.agent_executor.ainvoke({
            "messages": [HumanMessage(content=task_formatted)]
        })
        
        # 提取最后的消息
        last_message = response["messages"][-1].content if response.get("messages") else "执行完成"
        
        return {
            "past_steps": [(task, last_message)]
        }
    
    async def replan_step(self, state: DataAnalystState) -> Dict:
        """重新规划步骤"""
        output = await (replanner_prompt | self.llm.with_structured_output(Act)).ainvoke(state)
        
        if isinstance(output.action, Response):
            # 结束，返回响应
            return {"response": output.action.response}
        else:
            # 继续，更新计划
            return {"plan": output.action.steps}
    
    def should_end(self, state: DataAnalystState) -> Literal["continue", "end"]:
        """判断是否应该结束"""
        if "response" in state and state["response"]:
            return "end"
        else:
            return "continue"
    
    async def analyze(
        self,
        question: str,
        database: str = "singa_bi",
        use_redash: bool = False,
        max_iterations: int = 10
    ) -> str:
        """
        分析数据问题
        
        Args:
            question: 用户问题
            database: 数据库名称
            use_redash: 是否使用 Redash 执行
            max_iterations: 最大迭代次数
        
        Returns:
            分析结果
        """
        # 构建输入
        inputs = {
            "input": f"数据库: {database}\n问题: {question}"
        }
        
        # 配置
        config = {
            "recursion_limit": max_iterations
        }
        
        try:
            # 执行工作流
            final_state = await self.app.ainvoke(inputs, config=config)
            
            # 返回最终响应
            return final_state.get("response", "未能生成响应")
        
        except Exception as e:
            return f"执行失败: {str(e)}"
    
    def get_graph_image(self) -> bytes:
        """获取工作流图"""
        try:
            return self.app.get_graph().draw_mermaid_png()
        except Exception:
            return b""


# ============= 便捷函数 =============
def create_data_analyst_agent(
    mysql_url: Optional[str] = None,
    redash_url: Optional[str] = None,
    redash_api_key: Optional[str] = None,
    llm_model: str = "gpt-4",
    llm_api_key: Optional[str] = None,
    lightrag_url: Optional[str] = None
) -> DataAnalystAgent:
    """
    快速创建数据分析师 Agent
    
    Args:
        mysql_url: MySQL 连接字符串
        redash_url: Redash 服务地址
        redash_api_key: Redash API 密钥
        llm_model: LLM 模型名称
        llm_api_key: LLM API 密钥
        lightrag_url: LightRAG 服务地址
    
    Returns:
        DataAnalystAgent 实例
    """
    return DataAnalystAgent(
        mysql_config={'db_url': mysql_url} if mysql_url else {},
        redash_config={
            'redash_url': redash_url,
            'api_key': redash_api_key
        } if redash_url and redash_api_key else {},
        llm_config={
            'model': llm_model,
            'api_key': llm_api_key
        },
        lightrag_config={
            'api_url': lightrag_url
        } if lightrag_url else {}
    )
