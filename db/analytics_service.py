"""
埋点服务
提供记录和分析用户行为的服务功能
"""

import json
import uuid
import time
import contextvars
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy import func, and_, or_, case

from .database import DatabaseManager
from .analytics_models import (
    AgentExecutionLog,
    ToolCallLog,
    SQLQueryLog,
    UserSessionLog,
    KnowledgeGraphLog,
    ErrorLog
)


# ============================================================================
# 上下文变量 - 用于在请求生命周期中传递埋点信息
# ============================================================================

# 当前会话ID
_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "analytics_session_id", default=""
)

# 当前请求ID
_current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "analytics_request_id", default=""
)

# 当前请求开始时间
_current_request_start: contextvars.ContextVar[float] = contextvars.ContextVar(
    "analytics_request_start", default=0.0
)


# ============================================================================
# 埋点服务类
# ============================================================================

class AnalyticsService:
    """
    埋点服务类

    提供记录各种用户行为和系统指标的方法
    """

    def __init__(self, db_manager: DatabaseManager = None):
        """初始化服务

        Args:
            db_manager: 数据库管理器实例，为空则创建默认实例
        """
        if db_manager is None:
            from .database import DatabaseManager
            db_manager = DatabaseManager()
        self.db_manager = db_manager

    # ============= 会话管理 =============

    def create_session(
        self,
        client_ip: str = None,
        user_agent: str = None,
        db_key: str = None
    ) -> str:
        """创建新会话

        Args:
            client_ip: 客户端IP
            user_agent: User-Agent
            db_key: 数据库标识符

        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())

        session = UserSessionLog(
            session_id=session_id,
            client_ip=client_ip,
            user_agent=user_agent,
            db_key=db_key,
            db_keys_used=json.dumps([db_key]) if db_key else None,
            start_time=datetime.now(),
            last_activity=datetime.now()
        )

        db_session = self.db_manager.get_session()
        try:
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)
        finally:
            db_session.close()

        return session_id

    def update_session(
        self,
        session_id: str,
        db_key: str = None,
        request_success: bool = True
    ):
        """更新会话信息

        Args:
            session_id: 会话ID
            db_key: 本次请求使用的数据库
            request_success: 请求是否成功
        """
        db_session = self.db_manager.get_session()
        try:
            session = db_session.query(UserSessionLog).filter(
                UserSessionLog.session_id == session_id
            ).first()

            if session:
                session.last_activity = datetime.now()
                session.request_count += 1

                if request_success:
                    session.success_count += 1
                else:
                    session.error_count += 1

                # 更新使用过的数据库列表
                if db_key:
                    try:
                        db_keys = json.loads(session.db_keys_used or "[]")
                        if db_key not in db_keys:
                            db_keys.append(db_key)
                            session.db_keys_used = json.dumps(db_keys)
                    except json.JSONDecodeError:
                        session.db_keys_used = json.dumps([db_key])

                db_session.commit()
        finally:
            db_session.close()

    def close_session(self, session_id: str):
        """关闭会话

        Args:
            session_id: 会话ID
        """
        db_session = self.db_manager.get_session()
        try:
            session = db_session.query(UserSessionLog).filter(
                UserSessionLog.session_id == session_id
            ).first()

            if session:
                session.end_time = datetime.now()
                db_session.commit()
        finally:
            db_session.close()

    # ============= Agent 执行日志 =============

    def log_agent_execution(
        self,
        request_id: str,
        session_id: str,
        db_key: str,
        user_query: str,
        agent_type: str,
        status: str,
        duration_ms: float,
        plan_steps: int = None,
        executed_steps: int = None,
        iterations: int = None,
        tools_called: List[str] = None,
        tool_call_count: int = 0,
        sql_executed: int = 0,
        knowledge_searched: int = 0,
        error_code: str = None,
        error_message: str = None,
        response_length: int = None,
        has_data: bool = False,
        client_ip: str = None,
        user_agent: str = None
    ) -> int:
        """记录 Agent 执行日志

        Args:
            请求相关：
            request_id: 请求ID
            session_id: 会话ID
            db_key: 数据库标识符
            user_query: 用户查询

            Agent 相关：
            agent_type: Agent 类型
            status: 执行状态
            duration_ms: 执行时长

            执行细节：
            plan_steps: 规划步骤数
            executed_steps: 执行步骤数
            iterations: 迭代次数
            tools_called: 调用的工具列表
            tool_call_count: 工具调用总次数
            sql_executed: SQL执行次数
            knowledge_searched: 知识搜索次数

            结果：
            error_code: 错误码
            error_message: 错误信息
            response_length: 响应长度
            has_data: 是否返回数据

            客户端：
            client_ip: 客户端IP
            user_agent: User-Agent

        Returns:
            日志记录ID
        """
        log = AgentExecutionLog(
            session_id=session_id,
            request_id=request_id,
            db_key=db_key,
            user_query=user_query,
            query_length=len(user_query) if user_query else 0,
            agent_type=agent_type,
            agent_version="2.0",  # Plan agent
            plan_steps=plan_steps,
            executed_steps=executed_steps,
            iterations=iterations,
            tools_called=json.dumps(tools_called or []),
            tool_call_count=tool_call_count,
            sql_executed=sql_executed,
            knowledge_searched=knowledge_searched,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=duration_ms,
            status=status,
            error_code=error_code,
            error_message=error_message,
            response_length=response_length,
            has_data=has_data,
            client_ip=client_ip,
            user_agent=user_agent
        )

        db_session = self.db_manager.get_session()
        try:
            db_session.add(log)
            db_session.commit()
            db_session.refresh(log)
            return log.id
        finally:
            db_session.close()

    # ============= 工具调用日志 =============

    def log_tool_call(
        self,
        request_id: str,
        tool_name: str,
        tool_type: str,
        parameters: Dict[str, Any] = None,
        duration_ms: float = 0,
        status: str = "success",
        error_message: str = None,
        result_row_count: int = 0,
        result_size_bytes: int = 0,
        result_summary: str = None,
        sql_executed: str = None,
        sql_execution_time_ms: float = None,
        database_name: str = None
    ) -> int:
        """记录工具调用日志

        Args:
            request_id: 请求ID
            tool_name: 工具名称（execute_sql_query / get_table_schema / search_knowledge_graph）
            tool_type: 工具类型（sql / schema / knowledge）
            parameters: 调用参数（会脱敏）
            duration_ms: 执行时长
            status: 执行状态
            error_message: 错误信息
            result_row_count: 返回行数
            result_size_bytes: 返回数据大小
            result_summary: 工具输出摘要（截断后）
            sql_executed: 执行的SQL
            sql_execution_time_ms: SQL执行时间
            database_name: 数据库名

        Returns:
            日志记录ID
        """
        # 脱敏处理
        sanitized_params = self._sanitize_parameters(parameters or {})

        log = ToolCallLog(
            request_id=request_id,
            tool_name=tool_name,
            tool_type=tool_type,
            parameters=json.dumps(sanitized_params, ensure_ascii=False),
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            result_row_count=result_row_count,
            result_size_bytes=result_size_bytes,
            result_summary=result_summary[:1000] if result_summary else None,
            sql_executed=sql_executed,
            sql_execution_time_ms=sql_execution_time_ms,
            database_name=database_name
        )

        db_session = self.db_manager.get_session()
        try:
            db_session.add(log)
            db_session.commit()
            db_session.refresh(log)
            return log.id
        finally:
            db_session.close()

    # ============= SQL 查询日志 =============

    def log_sql_query(
        self,
        request_id: str,
        sql_executed: str,
        query_type: str = "simple",
        tables_accessed: List[str] = None,
        columns_accessed: List[str] = None,
        execution_time_ms: float = 0,
        rows_returned: int = 0,
        status: str = "success",
        error_message: str = None,
        db_key: str = None,
        database_name: str = None
    ) -> int:
        """记录 SQL 查询日志

        Args:
            request_id: 请求ID
            sql_executed: 执行的SQL
            query_type: 查询类型
            tables_accessed: 访问的表
            columns_accessed: 访问的列
            execution_time_ms: 执行时间
            rows_returned: 返回行数
            status: 执行状态
            error_message: 错误信息
            db_key: 数据库标识符
            database_name: 数据库名

        Returns:
            日志记录ID
        """
        import hashlib
        sql_hash = hashlib.md5(sql_executed.encode()).hexdigest()

        log = SQLQueryLog(
            request_id=request_id,
            sql_hash=sql_hash,
            sql_executed=sql_executed,
            query_type=query_type,
            tables_accessed=json.dumps(tables_accessed or []),
            columns_accessed=json.dumps(columns_accessed or []),
            execution_time_ms=execution_time_ms,
            rows_returned=rows_returned,
            status=status,
            error_message=error_message,
            db_key=db_key,
            database_name=database_name
        )

        db_session = self.db_manager.get_session()
        try:
            db_session.add(log)
            db_session.commit()
            db_session.refresh(log)
            return log.id
        finally:
            db_session.close()

    # ============= 错误日志 =============

    def log_error(
        self,
        error_code: str,
        error_type: str,
        error_message: str,
        traceback_str: str = None,
        component: str = None,
        function_name: str = None,
        request_id: str = None,
        session_id: str = None
    ) -> int:
        """记录错误日志

        Args:
            error_code: 错误码
            error_type: 错误类型
            error_message: 错误消息
            traceback_str: 堆栈信息
            component: 出错组件
            function_name: 出错函数
            request_id: 请求ID
            session_id: 会话ID

        Returns:
            日志记录ID
        """
        log = ErrorLog(
            request_id=request_id,
            session_id=session_id,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            traceback=traceback_str,
            component=component,
            function_name=function_name
        )

        db_session = self.db_manager.get_session()
        try:
            db_session.add(log)
            db_session.commit()
            db_session.refresh(log)
            return log.id
        finally:
            db_session.close()

    # ============= 辅助方法 =============

    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏处理参数

        Args:
            params: 原始参数

        Returns:
            脱敏后的参数
        """
        sensitive_keys = {'password', 'pwd', 'secret', 'token', 'key'}
        sanitized = {}

        for key, value in params.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_parameters(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    self._sanitize_parameters(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    # ============= 分析查询方法 =============

    def get_usage_stats(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        db_key: str = None
    ) -> Dict[str, Any]:
        """获取使用统计

        Args:
            start_date: 开始日期
            end_date: 结束日期
            db_key: 数据库标识符（可选）

        Returns:
            统计数据
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()

        db_session = self.db_manager.get_session()
        try:
            query = db_session.query(
                func.count(AgentExecutionLog.id).label('total_requests'),
                func.sum(case((AgentExecutionLog.status == 'success', 1), else_=0)).label('success_count'),
                func.sum(case((AgentExecutionLog.status == 'error', 1), else_=0)).label('error_count'),
                func.avg(AgentExecutionLog.duration_ms).label('avg_duration'),
                func.sum(AgentExecutionLog.tool_call_count).label('total_tool_calls')
            ).filter(
                and_(
                    AgentExecutionLog.start_time >= start_date,
                    AgentExecutionLog.start_time <= end_date
                )
            )

            if db_key:
                query = query.filter(AgentExecutionLog.db_key == db_key)

            result = query.first()

            return {
                'total_requests': result.total_requests or 0,
                'success_count': result.success_count or 0,
                'error_count': result.error_count or 0,
                'success_rate': (result.success_count / result.total_requests * 100) if result.total_requests else 0,
                'avg_duration_ms': float(result.avg_duration) if result.avg_duration else 0,
                'total_tool_calls': result.total_tool_calls or 0
            }
        finally:
            db_session.close()

    def get_popular_tables(
        self,
        start_date: datetime = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取热门查询表

        Args:
            start_date: 开始日期
            limit: 返回数量

        Returns:
            热门表列表
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)

        db_session = self.db_manager.get_session()
        try:
            # 从 SQL 查询日志中统计
            results = db_session.query(
                SQLQueryLog.tables_accessed,
                func.count(SQLQueryLog.id).label('count')
            ).filter(
                SQLQueryLog.created_at >= start_date
            ).group_by(
                SQLQueryLog.tables_accessed
            ).order_by(
                func.count(SQLQueryLog.id).desc()
            ).limit(limit).all()

            popular_tables = []
            for tables_json, count in results:
                try:
                    tables = json.loads(tables_json)
                    for table in tables:
                        existing = next((t for t in popular_tables if t['table_name'] == table), None)
                        if existing:
                            existing['count'] += count
                        else:
                            popular_tables.append({'table_name': table, 'count': count})
                except json.JSONDecodeError:
                    pass

            return sorted(popular_tables, key=lambda x: x['count'], reverse=True)[:limit]
        finally:
            db_session.close()


# ============================================================================
# 全局服务实例
# ============================================================================

_analytics_service: AnalyticsService = None


def get_analytics_service() -> AnalyticsService:
    """获取埋点服务单例"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


# ============================================================================
# 上下文辅助函数
# ============================================================================

def get_current_session_id() -> str:
    """获取当前会话ID"""
    return _current_session_id.get()


def get_current_request_id() -> str:
    """获取当前请求ID"""
    return _current_request_id.get()


def set_current_session_id(session_id: str):
    """设置当前会话ID"""
    _current_session_id.set(session_id)


def set_current_request_id(request_id: str):
    """设置当前请求ID"""
    _current_request_id.set(request_id)


def generate_request_id() -> str:
    """生成新的请求ID"""
    return str(uuid.uuid4())


def start_request_timer():
    """开始请求计时"""
    _current_request_start.set(time.time())


def get_request_duration_ms() -> float:
    """获取请求执行时长（毫秒）"""
    start = _current_request_start.get()
    if start:
        return (time.time() - start) * 1000
    return 0
