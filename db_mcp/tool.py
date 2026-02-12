"""
MCP Tools - 数据分析工具定义
只暴露 data_agent 工具，其他工具由 Agent 内部调用

该模块负责注册 MCP 工具到服务器。对外只暴露一个 data_agent 工具，
该工具内部会调用 LangChain Agent（Plan-Execute-Replan 架构），
Agent 会根据需要调用三个内部工具：
- execute_sql_query: 执行 SQL 查询
- get_table_schema: 获取表结构
- search_knowledge_graph: 搜索知识图谱

使用方式：
    # 该模块会被 server.py 自动导入和调用
    from .tool import register_tools
    register_tools(mcp)
"""

import os
import contextvars
import time
from typing import Optional, Dict, Any

from .logger import get_logger, log_request_start, log_request_end

# 获取日志器
logger = get_logger("mcp.tool")


# ============================================================================
# 数据库标识符 ContextVar（只存储 db_key，不存储完整配置）
# ============================================================================

# 当前请求的数据库标识符（如 "prod", "test" 等）
# 完整配置在工具调用时才从数据库查询
_current_db_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_db_key", default=""
)


def set_current_db_key(db_key: str) -> None:
    """设置当前请求的数据库标识符"""
    _current_db_key.set(db_key)


def get_current_db_key() -> str:
    """获取当前请求的数据库标识符"""
    return _current_db_key.get()


# ============================================================================
# 数据库配置获取（延迟加载：只在需要时查询）
# ============================================================================

def get_db_config_by_key(db_key: str) -> Dict[str, Any]:
    """
    根据 db_key 从数据库获取配置（延迟加载）

    这是核心改进：配置不在 server 收到请求时获取，
    而是在工具调用时才查询 db_mapping 表。

    Args:
        db_key: 数据库标识符

    Returns:
        数据库配置字典
    """
    if not db_key:
        return {}

    try:
        from db.database import DBMappingService
        service = DBMappingService()
        mapping = service.get_by_db_name(db_key)

        if mapping and mapping.is_active:
            return {
                "host": mapping.host,
                "port": mapping.port,
                "username": mapping.username,
                "password": mapping.password,
                "database": mapping.database,
            }
    except Exception as e:
        # 查询失败时返回空配置
        pass

    return {}


def get_current_db_config() -> Dict[str, Any]:
    """
    获取当前请求的数据库配置（延迟加载）

    根据当前 db_key 从数据库查询完整配置
    """
    db_key = get_current_db_key()
    return get_db_config_by_key(db_key)


# ============================================================================
# 工具注册
# ============================================================================

def register_tools(mcp):
    """
    注册 MCP 工具到服务器

    该函数向 MCP 服务器注册 data_agent 工具。

    Args:
        mcp: FastMCP 实例

    注册的工具：
        - data_agent: 数据分析智能体（自然语言查询接口，使用 Plan 架构）
    """

    @mcp.tool()
    async def data_agent(
        query: str
    ) -> str:
        """
        数据分析智能体 - 通过自然语言查询和分析数据库（Plan-Execute-Replan 架构）

        这是 MCP 服务器对外暴露的主要工具。用户可以用自然语言描述数据需求，
        Agent 会自动规划执行步骤并调用合适的工具完成任务。

        功能：
        - 理解自然语言的数据分析需求
        - 自动规划执行步骤（Plan-Execute-Replan 模式）
        - 自动查询数据库表结构（实时从 information_schema）
        - 搜索知识图谱（业务逻辑、历史 SQL、BI库里的表和字段命名规则）
        - 生成并执行 SQL 查询
        - 整理分析结果

        架构特点：
        - 使用 Plan-Execute-Replan 模式，适合复杂的多步骤分析任务
        - 自动将复杂任务拆解为可执行的步骤
        - 支持动态调整计划，应对执行中的错误

        Agent 内部会自动调用以下工具：
        - execute_sql_query: 执行 SQL 查询
        - get_table_schema: 获取表结构
        - search_knowledge_graph: 搜索知识图谱进行问答（业务逻辑、历史 SQL、BI库里的表和字段命名规则）

        Args:
            query: 用户的数据分析问题或查询需求

        适用场景：
        - 数据查询："查询最近7天的订单数量"
        - 指标分析："计算用户留存率"
        - 业务问题："还款率是如何计算的"
        - 数据探索："有哪些用户相关的表"
        - 表结构："显示 users 表的结构"
        - 复杂分析："分析最近一个月的销售趋势，找出增长最快的产品类别"

        Examples:
            >>> data_agent("查询 users 表有多少条记录")
            >>> data_agent("显示 orders 表的结构")
            >>> data_agent("最近7天的订单数量趋势")
            >>> data_agent("还款率是怎么计算的")

        注意：
            使用前需要在 URL 中指定数据库标识符，例如：
            http://localhost:8000/sse?db=prod
        """
        if not query:
            logger.warning("[REQUEST_EMPTY] 收到空查询请求")
            return "错误：查询内容不能为空"

        # 从 server 获取当前请求的 db_key（已由 Middleware 解析并设置）
        try:
            from .server import _current_db_key as server_db_key
            db_key = server_db_key.get()
        except (ImportError, AttributeError):
            # 备选方案
            from .server import get_current_db_key
            db_key = get_current_db_key()

        if not db_key or db_key == "default":
            return f"""错误：未配置数据库连接

请在 URL 中指定数据库标识符：
?db=<database_name>

可用的数据库标识符请联系服务器管理员获取。

当前数据库标识符: {db_key}
"""

        # 设置到工具层上下文（只设置 db_key，完整配置在工具调用时获取）
        set_current_db_key(db_key)

        # ========== 日志：记录请求开始 ==========
        _request_id = ""
        start_time = time.time()

        try:
            from db.analytics_config import log_agent_start
            _request_id = log_agent_start(
                db_key=db_key,
                user_query=query,
                agent_type="plan",
                client_ip=None,
                user_agent=None
            )
        except ImportError:
            pass  # 埋点模块不可用则跳过

        # 使用新的日志辅助函数
        log_request_start(logger, query, db_key, _request_id)

        try:
            # 使用 Plan 架构的 agent
            from agent.data_analyst_agent import run_agent

            # 调用 agent，传入 db_key（完整配置在工具调用时获取）
            result = await run_agent(query, db_key=db_key)

            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000

            # ========== 日志：记录请求成功 ==========
            log_request_end(logger, _request_id, "success", duration_ms, len(result) if result else 0)

            # ========== 埋点：记录请求成功 ==========
            # 显式传入 request_id 和 db_key，避免 LangGraph 子任务导致 contextvar 丢失
            try:
                from db.analytics_config import log_agent_end
                log_agent_end(
                    status="success",
                    agent_type="plan",
                    user_query=query,
                    response_length=len(result) if result else 0,
                    has_data=bool(result and result.strip()),
                    db_key=db_key,
                    request_id=_request_id,
                )
            except ImportError:
                pass

            return result

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            duration_ms = (time.time() - start_time) * 1000

            # ========== 日志：记录请求失败 ==========
            logger.error(f"请求失败 | request_id={_request_id} | error={type(e).__name__}: {str(e)}")
            log_request_end(logger, _request_id, "error", duration_ms, 0)

            # ========== 埋点：记录请求失败 ==========
            try:
                from db.analytics_config import log_agent_end, log_error
                log_agent_end(
                    status="error",
                    agent_type="plan",
                    user_query=query,
                    error_code=str(type(e).__name__),
                    error_message=str(e),
                    db_key=db_key,
                    request_id=_request_id,
                )
                log_error(
                    error_code=str(type(e).__name__),
                    error_type=type(e).__name__,
                    error_message=str(e),
                    component="data_agent",
                    function_name="data_agent"
                )
            except ImportError:
                pass

            return f"Agent 调用失败: {str(e)}\n\n详细错误:\n{error_detail}"
