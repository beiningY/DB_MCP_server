"""
数据分析师 Agent
基于 Plan-Execute-Replan 模式，集成知识模块和 SQL 执行器

改进点：
- step_index 防止重复执行同一步骤
- MAX_ITERATIONS 唯一限制，超限自动生成兜底回答（用 len(past_steps) 计数）
- 每个节点 try-except 错误处理
- threading.Lock 线程安全延迟初始化
- should_end 增加计划完成自动终止逻辑
- 支持从上下文获取数据库配置，避免配置通过 LLM 传递导致丢失
"""

import os
import operator
import threading
import contextvars
import logging
from typing import Annotated, List, Tuple, Union, Dict, Any
from typing_extensions import TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.errors import GraphRecursionError
from langchain.agents import create_agent

# 获取日志器
logger = logging.getLogger("mcp.agent")


load_dotenv()

# 导入工具
from tools import (
    execute_sql_query,
    search_knowledge_graph,
    get_table_schema,
    set_tool_db_key
)


# ============================================================================
# 数据库标识符上下文（只存储 db_key，完整配置延迟加载）
# ============================================================================

# 当前请求的数据库标识符
_agent_db_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "agent_db_key", default=""
)


def set_agent_db_key(db_key: str) -> None:
    """设置 agent 执行时的数据库标识符"""
    _agent_db_key.set(db_key)
    # 同时设置到工具层
    set_tool_db_key(db_key)


def get_agent_db_key() -> str:
    """获取 agent 执行时的数据库标识符"""
    return _agent_db_key.get()


# ============= 常量 =============
# 唯一需要调整的限制：agent 最多执行多少轮（execute_step 调用次数）
# LangGraph 的 recursion_limit 会根据此值自动推导，无需单独设置
MAX_ITERATIONS = 15


# ============= 状态定义 =============
class PlanExecute(TypedDict):
    """Agent 状态"""
    input: str                                            # 用户输入
    plan: List[str]                                       # 当前计划步骤列表
    step_index: int                                       # 当前执行到第几步（从 0 开始）
    past_steps: Annotated[List[Tuple], operator.add]      # 已完成步骤（累加），len() 即迭代次数
    response: str                                         # 最终响应
    error_log: Annotated[List[str], operator.add]         # 错误日志（累加）


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
    """获取 LLM 实例（每次调用创建新实例，本身是线程安全的）"""
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4"),
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
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
2. 对于复杂业务逻辑，可以使用 search_knowledge_graph 参考历史查询作为参考
3. 复杂查询应该分步骤验证
4. 每个步骤应该清晰、具体、可执行

## 示例步骤
- "使用 get_table_schema 获取所有表列表，找到与放款相关的表"
- "使用 get_table_schema('orders') 查看 orders 表的字段结构"
- "使用 search_knowledge_graph 搜索'如何计算放款金额'的历史查询"
- "执行 SQL: SELECT COUNT(*) FROM orders WHERE date = '2024-01-01'"

## 重要：输出格式
**只输出 JSON 对象，不要有任何其他文字！**
直接输出：{{"steps": ["步骤1", "步骤2", ...]}}
"""),
    ("placeholder", "{messages}"),
])


# ============= Replanner =============
# 更新 prompt：增加进度信息和错误日志，引导 replanner 在步骤完成后返回 Response
replanner_prompt = ChatPromptTemplate.from_template(
    """你是一个数据分析任务重规划师。
根据已完成的步骤和当前状态，决定接下来的行动。

原始目标: {input}
原始计划: {plan}
执行进度: 已执行 {step_index}/{total_steps} 步
已完成步骤及结果: {past_steps}
错误记录: {error_log}

## 决策原则
- 如果已经获得足够信息可以回答用户问题，返回 Response
- **如果所有计划步骤已执行完毕，必须根据执行结果返回 Response 进行总结回答**
- 如果任务未完成或需要修正，返回更新后的 Plan（只包含尚未完成的步骤）
- 如果 SQL 执行失败，分析错误原因并修正计划
- 如果出现多次错误，可以考虑换一种方式实现

## 输出格式
请以 JSON 格式返回，二选一：
- 结束任务：{{"action": {{"response": "最终回答内容"}}}}
- 继续执行：{{"action": {{"steps": ["步骤1", "步骤2", ...]}}}}
"""
)


# ============= 线程安全的延迟初始化 =============
_init_lock = threading.Lock()
_planner = None
_replanner = None
_agent_executor = None


def get_planner():
    """线程安全的延迟获取 Planner（双重检查锁定）"""
    global _planner
    if _planner is None:
        with _init_lock:
            if _planner is None:
                _planner = planner_prompt | get_llm().with_structured_output(
                    Plan,
                    method="json_mode"
                )
    return _planner


def get_replanner():
    """线程安全的延迟获取 Replanner（双重检查锁定）"""
    global _replanner
    if _replanner is None:
        with _init_lock:
            if _replanner is None:
                _replanner = replanner_prompt | get_llm().with_structured_output(
                    Act,
                    method="json_mode"
                )
    return _replanner


# ============= Executor Agent System Prompt =============
EXECUTOR_SYSTEM_PROMPT = """你是一个精确的任务执行器，负责执行数据分析计划中的单个步骤。

## 核心原则
- 你只负责**执行当前分配的任务**，不要自行扩展或规划额外步骤
- 严格使用工具完成任务，不要凭空捏造数据
- 如果工具调用失败，如实报告错误信息，不要自行修正或重试

## 可用工具
1. **get_table_schema** - 获取数据库表结构
   - 不带 table_name 参数：返回数据库所有表列表
   - 指定 table_name：返回该表的详细字段信息（字段名、类型、注释等）

2. **search_knowledge_graph** - 搜索知识图谱
   - 用于查找历史 SQL 查询、业务规则、字段含义等
   - 输入自然语言描述即可

3. **execute_sql_query** - 执行 SQL 查询
   - 仅支持 SELECT 语句
   - 自动添加 LIMIT 保护

## 执行要求
- 调用 execute_sql_query 和 get_table_schema 时，必须使用消息中提供的数据库连接参数
- search_knowledge_graph 不需要数据库连接参数
- 执行完成后，**清晰地汇报结果**，包括关键数据和发现
- 如果任务要求执行 SQL，请在结果中包含实际执行的 SQL 语句
"""


def get_agent_executor():
    """线程安全的延迟获取 Agent Executor（双重检查锁定）"""
    global _agent_executor
    if _agent_executor is None:
        with _init_lock:
            if _agent_executor is None:
                model = ChatOpenAI(
                    model=os.getenv("LLM_MODEL", "gpt-4"),
                    api_key=os.getenv("LLM_API_KEY"),
                    base_url=os.getenv("LLM_BASE_URL"),
                )
                _agent_executor = create_agent(
                    model=model,
                    tools=[execute_sql_query, search_knowledge_graph, get_table_schema],
                    system_prompt=EXECUTOR_SYSTEM_PROMPT
                )
    return _agent_executor


# ============= 辅助函数 =============
def _generate_fallback_response(state: PlanExecute, reason: str = "") -> str:
    """根据已执行步骤生成兜底回答"""
    past_steps = state.get("past_steps", [])
    errors = state.get("error_log", [])

    parts = [f"⚠️ {reason}" if reason else "⚠️ 任务未能正常完成"]

    if past_steps:
        parts.append("\n## 已执行步骤及结果：")
        for i, (step, result) in enumerate(past_steps, 1):
            parts.append(f"\n### 步骤 {i}: {step}")
            parts.append(str(result))

    if errors:
        parts.append("\n## 执行过程中的错误：")
        for err in errors:
            parts.append(f"- {err}")

    return "\n".join(parts)


# ============= Workflow 节点 =============
async def plan_step(state: PlanExecute):
    """规划步骤（带错误处理）"""
    user_input = state["input"]

    # ========== 日志：记录规划开始 ==========
    logger.info(f"[AGENT_PLAN_START] input={user_input[:100]}{'...' if len(user_input) > 100 else ''}")

    try:
        plan = await get_planner().ainvoke(
            {"messages": [("user", user_input)]}
        )

        # ========== 日志：记录规划完成 ==========
        logger.info(f"[AGENT_PLAN_SUCCESS] steps={len(plan.steps)} | plan={plan.steps}")

        return {
            "plan": plan.steps,
            "step_index": 0,
        }
    except Exception as e:
        error_msg = f"[planner] {type(e).__name__}: {str(e)}"

        # ========== 日志：记录规划失败 ==========
        logger.error(f"[AGENT_PLAN_ERROR] error={str(e)}")

        # ========== 埋点：记录错误到 error_log ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code="PLAN_ERROR",
                error_type=type(e).__name__,
                error_message=str(e),
                component="agent_planner",
                function_name="plan_step"
            )
        except ImportError:
            pass

        return {
            "plan": [],
            "step_index": 0,
            "response": f"规划阶段出错，无法生成执行计划: {str(e)}",
            "error_log": [error_msg],
        }


async def execute_step(state: PlanExecute):
    """执行当前步骤（基于 step_index，带错误处理）"""
    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)

    # 安全检查：step_index 越界
    if step_index >= len(plan):
        return {
            "past_steps": [("(无更多步骤)", "所有计划步骤已执行完毕")],
            "step_index": step_index,
        }

    task = plan[step_index]
    plan_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan))

    # ========== 日志：记录步骤开始 ==========
    logger.info(f"[AGENT_STEP_START] step={step_index + 1}/{len(plan)} | task={task[:100]}")

    # 简化的任务描述（不包含配置信息）
    # 配置会通过 contextvar 传递，工具会自动获取
    task_formatted = f"""根据以下计划执行第 {step_index + 1} 步:
{plan_str}

当前任务（第 {step_index + 1}/{len(plan)} 步）: {task}

请使用可用工具完成这个任务。
注意：execute_sql_query 和 get_table_schema 工具会自动使用当前配置的数据库连接。
"""

    try:
        import time
        step_start = time.time()

        # 使用全局 executor（工具会自动从 contextvar 获取配置）
        agent_response = await get_agent_executor().ainvoke(
            {"messages": [("user", task_formatted)]}
        )

        step_duration = (time.time() - step_start) * 1000
        result_content = agent_response["messages"][-1].content

        # ========== 日志：记录步骤完成 ==========
        result_preview = result_content[:200].replace("\n", " ")
        logger.info(f"[AGENT_STEP_SUCCESS] step={step_index + 1} | duration={step_duration:.0f}ms | output_preview={result_preview}")

        return {
            "past_steps": [(task, result_content)],
            "step_index": step_index + 1,
        }
    except Exception as e:
        error_msg = f"[executor] step {step_index} ({task}): {type(e).__name__}: {str(e)}"

        # ========== 日志：记录步骤失败 ==========
        logger.error(f"[AGENT_STEP_ERROR] step={step_index + 1} | error={str(e)}")

        # ========== 埋点：记录步骤失败 ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code="EXEC_ERROR",
                error_type=type(e).__name__,
                error_message=str(e),
                component="agent_executor",
                function_name="execute_step"
            )
        except ImportError:
            pass

        return {
            "past_steps": [(task, f"⚠️ 执行出错: {str(e)}")],
            "step_index": step_index + 1,  # 跳过失败步骤
            "error_log": [error_msg],
        }


async def replan_step(state: PlanExecute):
    """重新规划（带迭代限制和错误处理）"""
    past_steps = state.get("past_steps", [])
    step_index = state.get("step_index", 0)
    plan = state.get("plan", [])

    # ========== 日志：记录重规划开始 ==========
    logger.debug(f"[AGENT_REPLAN_START] step={step_index}/{len(plan)} | past_steps={len(past_steps)}")

    # 用 len(past_steps) 作为迭代计数，超限 → 生成兜底回答
    if len(past_steps) >= MAX_ITERATIONS:
        logger.warning(f"[AGENT_MAX_ITERATIONS] reached {MAX_ITERATIONS}, generating fallback response")
        return {
            "response": _generate_fallback_response(
                state,
                reason=f"已达到最大执行次数({MAX_ITERATIONS})，基于已有信息自动生成回答"
            )
        }

    try:
        replan_input = {
            "input": state.get("input", ""),
            "plan": plan,
            "step_index": step_index,
            "total_steps": len(plan),
            "past_steps": past_steps,
            "error_log": state.get("error_log", []),
        }
        output = await get_replanner().ainvoke(replan_input)

        if isinstance(output.action, Response):
            # ========== 日志：记录任务完成 ==========
            response_preview = output.action.response[:200].replace("\n", " ")
            logger.info(f"[AGENT_COMPLETE] response_preview={response_preview}")
            return {"response": output.action.response}
        else:
            # ========== 日志：记录新计划 ==========
            new_steps = output.action.steps
            logger.info(f"[AGENT_REPLAN] new_steps={len(new_steps)} | plan={new_steps}")
            return {"plan": new_steps, "step_index": 0}

    except Exception as e:
        error_msg = f"[replanner] {type(e).__name__}: {str(e)}"
        logger.error(f"[AGENT_REPLAN_ERROR] error={str(e)}")

        # ========== 埋点：记录错误到 error_log ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code="REPLAN_ERROR",
                error_type=type(e).__name__,
                error_message=str(e),
                component="agent_replanner",
                function_name="replan_step"
            )
        except ImportError:
            pass

        return {
            "response": _generate_fallback_response(
                state,
                reason=f"重规划阶段出错({str(e)})，基于已有信息生成回答"
            ),
            "error_log": [error_msg],
        }


def should_continue_after_plan(state: PlanExecute):
    """Planner 之后的条件判断：失败或空计划则直接结束"""
    # planner 出错时已设置 response → 直接结束
    if state.get("response"):
        return END
    # 计划为空 → 无法执行
    if not state.get("plan"):
        return END
    return "agent"


def should_end(state: PlanExecute):
    """Replan 之后的条件判断"""
    # 1. 已有最终回答 → 结束
    if state.get("response"):
        return END

    # 2. 安全兜底：计划为空或所有步骤已执行完 → 结束
    #    正常情况下 replanner 会生成 Response，这里是防御性检查
    plan = state.get("plan", [])
    step_index = state.get("step_index", 0)
    if not plan or step_index >= len(plan):
        return END

    # 3. 继续执行下一步
    return "agent"


# ============= 构建 Workflow =============
workflow = StateGraph(PlanExecute)

# 添加节点
workflow.add_node("planner", plan_step)
workflow.add_node("agent", execute_step)
workflow.add_node("replan", replan_step)

# 添加边
workflow.add_edge(START, "planner")
# planner → 条件判断：成功则执行，失败则结束
workflow.add_conditional_edges(
    "planner",
    should_continue_after_plan,
    ["agent", END],
)
workflow.add_edge("agent", "replan")
workflow.add_conditional_edges(
    "replan",
    should_end,
    ["agent", END],
)

# 编译
app = workflow.compile()


# ============= 对外接口 =============
async def run_agent(user_input: str, db_key: str = None) -> str:
    """
    运行 Agent 的统一入口。

    限制只有一个：MAX_ITERATIONS（最大执��轮数）。
    LangGraph 的 recursion_limit 由它自动推导，作为框架级安全阀。

    Args:
        user_input: 用户的自然语言输入
        db_config: 可选的数据库配置，如果提供则设置到上下文中

    Returns:
        Agent 的最终回答字符串
    """
    # 设置数据库标识符到上下文（完整配置在工具调用时才查询）
    if db_key:
        set_agent_db_key(db_key)

    # recursion_limit 由 MAX_ITERATIONS 自动推导，无需单独配置
    # 公式：1(planner) + N × 2(agent + replan) + 余量
    config = {"recursion_limit": MAX_ITERATIONS * 2 + 10}
    inputs = {"input": user_input}

    try:
        final_state = await app.ainvoke(inputs, config=config)
        return final_state.get("response", "未能生成回答，请重试。")

    except GraphRecursionError:
        # 框架级安全阀，正常不会触发（MAX_ITERATIONS 会先拦截）
        # ========== 埋点：记录错误到 error_log ==========
        try:
            from db.analytics_config import log_error
            log_error(
                error_code="RECURSION_LIMIT",
                error_type="GraphRecursionError",
                error_message=f"执行超过上限({MAX_ITERATIONS}轮)，已自动终止",
                component="agent",
                function_name="run_agent"
            )
        except ImportError:
            pass
        return f"⚠️ 执行超过上限({MAX_ITERATIONS}轮)，已自动终止。请尝试简化问题后重新提问。"


# ============= 主函数（用于测试） =============
async def main():
    """测试函数"""
    user_input = (
        "请告诉我摄像头的数据信息并介绍分析一下，"
        "数据库的配置是(MYSQL_DATABASE: cognitive,"
        "MYSQL_HOST: rm-0iwx9y9q368yc877wbo.mysql.japan.rds.aliyuncs.com,"
        "MYSQL_PASSWORD: Root155017,MYSQL_PORT: 3306,MYSQL_USER: root)"
    )

    logger.info(f"配置: MAX_ITERATIONS={MAX_ITERATIONS}")
    logger.info("开始执行...")

    result = await run_agent(user_input)
    logger.info(f"最终结果: {result[:200]}...")  # 只记录前200个字符


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
