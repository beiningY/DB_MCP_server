"""
埋点配置和管理

提供埋点开关和初始化功能
"""

import os
from typing import Dict, Any, Optional
from .analytics_service import (
    get_analytics_service,
    generate_request_id,
    start_request_timer,
    get_request_duration_ms
)
from .analytics_models import (
    AgentExecutionLog,
    ToolCallLog,
    SQLQueryLog,
    ErrorLog
)


# ============================================================================
# 埋点开关
# ============================================================================

# 从环境变量读取埋点开关
ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "false").lower() in ("true", "1", "on", "yes")


def is_analytics_enabled() -> bool:
    """检查埋点是否启用"""
    return ANALYTICS_ENABLED


def enable_analytics():
    """启用埋点"""
    global ANALYTICS_ENABLED
    ANALYTICS_ENABLED = True
    os.environ["ANALYTICS_ENABLED"] = "true"


def disable_analytics():
    """禁用埋点"""
    global ANALYTICS_ENABLED
    ANALYTICS_ENABLED = False
    os.environ["ANALYTICS_ENABLED"] = "false"


# ============================================================================
# 埋点上下文变量
# ============================================================================

import contextvars

# 当前请求ID
_analytics_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "analytics_request_id", default=""
)

# 当前会话ID
_analytics_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "analytics_session_id", default=""
)

# 请求开始时间
_analytics_start_time: contextvars.ContextVar[float] = contextvars.ContextVar(
    "analytics_start_time", default=0.0
)

# 工具调用计数
_analytics_tool_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "analytics_tool_count", default=0
)

# SQL 执行计数
_analytics_sql_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "analytics_sql_count", default=0
)

# 知识图谱搜索计数
_analytics_kg_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "analytics_kg_count", default=0
)


# ============================================================================
# 埋点上下文辅助函数
# ============================================================================

def get_analytics_request_id() -> str:
    """获取当前请求ID"""
    return _analytics_request_id.get()


def set_analytics_request_id(request_id: str):
    """设置当前请求ID"""
    _analytics_request_id.set(request_id)


def get_analytics_session_id() -> str:
    """获取当前会话ID"""
    return _analytics_session_id.get()


def set_analytics_session_id(session_id: str):
    """设置当前会话ID"""
    _analytics_session_id.set(session_id)


def increment_tool_count() -> int:
    """增加工具调用计数"""
    count = _analytics_tool_count.get(0) + 1
    _analytics_tool_count.set(count)
    return count


def increment_sql_count() -> int:
    """增加SQL执行计数"""
    count = _analytics_sql_count.get(0) + 1
    _analytics_sql_count.set(count)
    return count


def increment_kg_count() -> int:
    """增加知识图谱搜索计数"""
    count = _analytics_kg_count.get(0) + 1
    _analytics_kg_count.set(count)
    return count


def get_tool_count() -> int:
    """获取工具调用计数"""
    return _analytics_tool_count.get(0)


def get_sql_count() -> int:
    """获取SQL执行计数"""
    return _analytics_sql_count.get(0)


def get_kg_count() -> int:
    """获取知识图谱搜索计数"""
    return _analytics_kg_count.get(0)


def reset_request_context():
    """重置单次请求的埋点上下文（保留 session_id，因为 session 跨越整个 SSE 连接）"""
    _analytics_request_id.set("")
    _analytics_start_time.set(0.0)
    _analytics_tool_count.set(0)
    _analytics_sql_count.set(0)
    _analytics_kg_count.set(0)


def reset_analytics_context():
    """完全重置埋点上下文（包括 session_id，仅在 SSE 断开时使用）"""
    _analytics_request_id.set("")
    _analytics_session_id.set("")
    _analytics_start_time.set(0.0)
    _analytics_tool_count.set(0)
    _analytics_sql_count.set(0)
    _analytics_kg_count.set(0)


# ============================================================================
# 埋点记录器（简化版）
# ============================================================================

def log_agent_start(
    db_key: str,
    user_query: str,
    agent_type: str = "plan",
    client_ip: str = None,
    user_agent: str = None
) -> str:
    """
    记录 Agent 请求开始（每次工具调用时调用）

    Session 已在 SSE 连接建立时由中间件创建，这里只做请求级别初始化：
    - 生成 request_id
    - 启动计时器
    - 重置工具调用计数器

    Args:
        db_key: 数据库标识符
        user_query: 用户查询
        agent_type: Agent 类型
        client_ip: 客户端IP（未使用，session 中已记录）
        user_agent: User-Agent（未使用，session 中已记录）

    Returns:
        请求ID
    """
    if not is_analytics_enabled():
        return ""

    try:
        import time

        # 重置单次请求上下文（保留 session_id）
        reset_request_context()

        # 生成本次请求 ID
        request_id = generate_request_id()
        set_analytics_request_id(request_id)

        # 启动计时
        _analytics_start_time.set(time.time())

        return request_id

    except Exception:
        # 埋点失败不影响主业务
        return ""


def log_agent_end(
    status: str,
    agent_type: str = "plan",
    user_query: str = "",
    response_length: int = None,
    has_data: bool = False,
    plan_steps: int = None,
    executed_steps: int = None,
    iterations: int = None,
    error_code: str = None,
    error_message: str = None,
    db_key: str = None,
    request_id: str = None,
):
    """
    记录 Agent 请求结束

    Args:
        status: 执行状态
        agent_type: Agent 类型
        user_query: 用户查询
        response_length: 响应长度
        has_data: 是否返回数据
        plan_steps: 规划步骤数
        executed_steps: 执行步骤数
        iterations: 迭代次数
        error_code: 错误码
        error_message: 错误信息
        db_key: 数据库标识符（显式传入，避免依赖 contextvars）
        request_id: 请求ID（显式传入，避免 LangGraph 子任务导致 contextvar 丢失）
    """
    if not is_analytics_enabled():
        return

    # 使用统一的 MCP logger（而非默认 root logger，确保日志可见）
    import logging
    _logger = logging.getLogger("mcp.analytics")

    try:
        import time

        # 优先使用显式传入的值，回退到 contextvar
        _request_id = request_id or get_analytics_request_id()
        session_id = get_analytics_session_id()

        # 获取 db_key：优先显式传入 → contextvar → server 模块
        _db_key = db_key or ""
        if not _db_key:
            try:
                from db_mcp.server import get_current_db_key
                _db_key = get_current_db_key()
            except Exception:
                _db_key = ""

        if not _request_id:
            _logger.warning("log_agent_end: request_id 为空，跳过记录")
            return

        # 计算执行时长
        start_time = _analytics_start_time.get(0.0)
        duration_ms = 0
        if start_time:
            duration_ms = (time.time() - start_time) * 1000

        # 从 tool_call_log 表统计实际的工具调用次数（避免 contextvars 在 LangGraph 子任务中丢失）
        tool_count = 0
        sql_count = 0
        kg_count = 0
        tools_called_list = []
        try:
            service = get_analytics_service()
            db_session = service.db_manager.get_session()
            try:
                from .analytics_models import ToolCallLog
                from sqlalchemy import func
                # 按 tool_name 分组统计
                stats = db_session.query(
                    ToolCallLog.tool_name,
                    func.count(ToolCallLog.id)
                ).filter(
                    ToolCallLog.request_id == _request_id
                ).group_by(ToolCallLog.tool_name).all()

                for tool_name, count in stats:
                    tool_count += count
                    tools_called_list.append(tool_name)
                    if tool_name == "execute_sql_query":
                        sql_count += count
                    elif tool_name == "search_knowledge_graph":
                        kg_count += count
            finally:
                db_session.close()
        except Exception as e:
            _logger.warning(f"统计工具调用次数失败: {e}")
            # 回退到 contextvar 计数
            tool_count = get_tool_count()
            sql_count = get_sql_count()
            kg_count = get_kg_count()

        service = get_analytics_service()
        service.log_agent_execution(
            request_id=_request_id,
            session_id=session_id,
            db_key=_db_key,
            user_query=user_query[:500] if user_query else "",
            agent_type=agent_type,
            status=status,
            duration_ms=duration_ms,
            plan_steps=plan_steps,
            executed_steps=executed_steps,
            iterations=iterations,
            tools_called=tools_called_list or None,
            tool_call_count=tool_count,
            sql_executed=sql_count,
            knowledge_searched=kg_count,
            error_code=error_code,
            error_message=error_message,
            response_length=response_length,
            has_data=has_data
        )

        _logger.info(
            f"agent_execution_log 已记录: request_id={_request_id}, "
            f"status={status}, duration={duration_ms:.0f}ms, tools={tool_count}"
        )

        # 更新会话统计（请求计数、成功/失败计数）
        if session_id:
            service.update_session(
                session_id=session_id,
                db_key=_db_key,
                request_success=(status == "success")
            )

        # 重置请求上下文（保留 session_id，因为同一 SSE 连接还会有后续请求）
        reset_request_context()

    except Exception as e:
        # 埋点失败不影响主业务，但记录到 MCP logger 确保可见
        _logger.error(f"log_agent_end 失败: {type(e).__name__}: {e}", exc_info=True)
        reset_request_context()


def log_tool_call(
    tool_name: str,
    tool_type: str,
    parameters: Dict[str, Any] = None,
    status: str = "success",
    error_message: str = None,
    result_row_count: int = 0,
    result_size_bytes: int = 0,
    result_summary: str = None,
    duration_ms: float = 0,
    sql_executed: str = None,
    sql_execution_time_ms: float = None,
    database_name: str = None
):
    """
    记录工具调用（三个工具共用入口）

    Args:
        tool_name: 工具名称（execute_sql_query / get_table_schema / search_knowledge_graph）
        tool_type: 工具类型（sql / schema / knowledge）
        parameters: 调用参数（会自动脱敏）
        status: 执行状态（success / error）
        error_message: 错误信息
        result_row_count: 返回行数（SQL 工具专用）
        result_size_bytes: 返回数据大小（字节）
        result_summary: 工具输出摘要（截断后的结果，便于回溯分析）
        duration_ms: 执行时长（毫秒）
        sql_executed: 执行的 SQL 语句（SQL 工具专用）
        sql_execution_time_ms: SQL 执行时间（SQL 工具专用）
        database_name: 数据库名称
    """
    if not is_analytics_enabled():
        return

    try:
        request_id = get_analytics_request_id()
        if not request_id:
            return

        increment_tool_count()

        # 根据工具类型增加对应计数
        if tool_type == "sql":
            increment_sql_count()
        elif tool_type == "knowledge":
            increment_kg_count()

        service = get_analytics_service()
        service.log_tool_call(
            request_id=request_id,
            tool_name=tool_name,
            tool_type=tool_type,
            parameters=parameters,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            result_row_count=result_row_count,
            result_size_bytes=result_size_bytes,
            result_summary=result_summary,
            sql_executed=sql_executed,
            sql_execution_time_ms=sql_execution_time_ms,
            database_name=database_name
        )

    except Exception as e:
        # 埋点失败不影响主业务，但记录日志方便排查
        import logging
        logging.getLogger("mcp.analytics").warning(f"log_tool_call 失败: {e}")


def log_sql_query(
    sql_executed: str,
    query_type: str = "simple",
    tables_accessed: list = None,
    execution_time_ms: float = 0,
    rows_returned: int = 0,
    status: str = "success",
    error_message: str = None,
    db_key: str = None,
    database_name: str = None
):
    """
    记录 SQL 查询

    Args:
        sql_executed: 执行的SQL
        query_type: 查询类型
        tables_accessed: 访问的表
        execution_time_ms: 执行时间
        rows_returned: 返回行数
        status: 执行状态
        error_message: 错误信息
        db_key: 数据库标识符
        database_name: 数据库名
    """
    if not is_analytics_enabled():
        return

    try:
        request_id = get_analytics_request_id()
        if not request_id:
            return

        increment_sql_count()

        service = get_analytics_service()
        service.log_sql_query(
            request_id=request_id,
            sql_executed=sql_executed,
            query_type=query_type,
            tables_accessed=tables_accessed,
            execution_time_ms=execution_time_ms,
            rows_returned=rows_returned,
            status=status,
            error_message=error_message,
            db_key=db_key,
            database_name=database_name
        )

    except Exception:
        pass  # 埋点失败不影响主业务


def log_error(
    error_code: str,
    error_type: str,
    error_message: str,
    component: str = None,
    function_name: str = None
):
    """
    记录错误

    Args:
        error_code: 错误码
        error_type: 错误类型
        error_message: 错误消息
        component: 出错组件
        function_name: 出错函数
    """
    if not is_analytics_enabled():
        return

    try:
        request_id = get_analytics_request_id()
        session_id = get_analytics_session_id()

        service = get_analytics_service()
        service.log_error(
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            component=component,
            function_name=function_name,
            request_id=request_id,
            session_id=session_id
        )

    except Exception:
        pass  # 埋点失败不影响主业务
