"""
埋点数据模型
用于记录和分析 MCP 服务的使用情况
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base

# 复用已有的 Base
from .models import Base


class AgentExecutionLog(Base):
    """
    Agent 执行日志表

    记录每次 Agent 调用的详细信息，用于分析使用情况和性能
    """
    __tablename__ = "agent_execution_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 请求信息
    session_id = Column(String(64), comment="会话ID（用于关联同一用户的多次请求）")
    request_id = Column(String(64), unique=True, comment="请求唯一标识")
    db_key = Column(String(128), comment="数据库标识符")

    # 查询内容
    user_query = Column(Text, comment="用户原始查询")
    query_length = Column(Integer, comment="查询长度")
    query_type = Column(String(32), comment="查询类型：data_exploration/analysis/knowledge/etc")

    # Agent 信息
    agent_type = Column(String(32), comment="Agent类型：simple/plan")
    agent_version = Column(String(16), comment="Agent版本")

    # 执行过程
    plan_steps = Column(Integer, comment="规划的步骤数")
    executed_steps = Column(Integer, comment="实际执行的步骤数")
    iterations = Column(Integer, comment="迭代次数")

    # 工具调用
    tools_called = Column(Text, comment="调用的工具列表（JSON）")
    tool_call_count = Column(Integer, comment="工具调用总次数")
    sql_executed = Column(Integer, comment="执行的SQL次数")
    knowledge_searched = Column(Integer, comment="知识图谱搜索次数")

    # 性能指标
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration_ms = Column(Float, comment="执行时长（毫秒）")
    llm_tokens_used = Column(Integer, comment="LLM token使用量")

    # 结果
    status = Column(String(16), comment="执行状态：success/error/timeout")
    error_code = Column(String(32), comment="错误码")
    error_message = Column(Text, comment="错误信息")

    # 响应信息
    response_length = Column(Integer, comment="响应长度")
    has_data = Column(Boolean, comment="是否返回数据")

    # 元数据
    client_ip = Column(String(64), comment="客户端IP")
    user_agent = Column(String(256), comment="客户端User-Agent")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_db_key', 'db_key'),
        Index('idx_start_time', 'start_time'),
        Index('idx_status', 'status'),
        Index('idx_agent_type', 'agent_type'),
    )


class ToolCallLog(Base):
    """
    工具调用日志表

    记录每个工具的详细调用信息
    """
    __tablename__ = "tool_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联信息
    request_id = Column(String(64), comment="关联的请求ID")
    agent_execution_id = Column(Integer, comment="关联的Agent执行日志ID")

    # 工具信息
    tool_name = Column(String(64), comment="工具名称")
    tool_type = Column(String(32), comment="工具类型：sql/knowledge/schema")

    # 调用参数
    parameters = Column(Text, comment="调用参数（脱敏后，JSON）")

    # 执行信息
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration_ms = Column(Float, comment="执行时长（毫秒）")

    # 结果
    status = Column(String(16), comment="执行状态：success/error")
    error_message = Column(Text, comment="错误信息")
    result_row_count = Column(Integer, comment="返回数据行数")
    result_size_bytes = Column(Integer, comment="返回数据大小（字节）")

    # 工具输出摘要（记录工具返回的关键结果，截断保留）
    result_summary = Column(Text, comment="工具输出摘要（截断后，前1000字符）")

    # SQL 特定字段
    sql_executed = Column(Text, comment="执行的SQL语句")
    sql_execution_time_ms = Column(Float, comment="SQL执行时间（毫秒）")
    database_name = Column(String(128), comment="数据库名称")

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_request_id', 'request_id'),
        Index('idx_tool_name', 'tool_name'),
        Index('idx_start_time', 'start_time'),
        Index('idx_status', 'status'),
    )


class SQLQueryLog(Base):
    """
    SQL 查询日志表

    专门记录 SQL 查询的详细信息，用于查询分析和优化
    """
    __tablename__ = "sql_query_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联信息
    request_id = Column(String(64), comment="关联的请求ID")
    tool_call_id = Column(Integer, comment="关联的工具调用日志ID")

    # SQL 信息
    sql_hash = Column(String(64), comment="SQL语句hash（用于去重分析）")
    sql_template = Column(Text, comment="SQL模板（参数化后）")
    sql_executed = Column(Text, comment="实际执行的SQL")

    # 查询类型
    query_type = Column(String(32), comment="查询类型：simple/join/aggregation/subquery/etc")
    tables_accessed = Column(Text, comment="访问的表列表（JSON）")
    columns_accessed = Column(Text, comment="访问的列列表（JSON）")

    # 性能
    execution_time_ms = Column(Float, comment="执行时间（毫秒）")
    rows_returned = Column(Integer, comment="返回行数")
    rows_scanned = Column(Integer, comment="扫描行数（如果可获取）")

    # 结果
    status = Column(String(16), comment="执行状态：success/error")
    error_message = Column(Text, comment="错误信息")

    # 数据库信息
    db_key = Column(String(128), comment="数据库标识符")
    database_name = Column(String(128), comment="数据库名称")

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_sql_hash', 'sql_hash'),
        Index('idx_request_id', 'request_id'),
        Index('idx_db_key', 'db_key'),
        Index('idx_created_at', 'created_at'),
        Index('idx_query_type', 'query_type'),
    )


class UserSessionLog(Base):
    """
    用户会话日志表

    记录用户会话信息，用于分析用户行为模式
    """
    __tablename__ = "user_session_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 会话信息
    session_id = Column(String(64), unique=True, comment="会话唯一标识")
    client_ip = Column(String(64), comment="客户端IP")
    user_agent = Column(String(512), comment="客户端User-Agent")

    # 数据库使用
    db_key = Column(String(128), comment="主要使用的数据库标识符")
    db_keys_used = Column(Text, comment="使用过的数据库列表（JSON）")

    # 时间
    start_time = Column(DateTime, comment="会话开始时间")
    end_time = Column(DateTime, comment="会话结束时间")
    last_activity = Column(DateTime, comment="最后活跃时间")

    # 统计
    request_count = Column(Integer, default=0, comment="请求数量")
    success_count = Column(Integer, default=0, comment="成功请求数量")
    error_count = Column(Integer, default=0, comment="错误请求数量")

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_client_ip', 'client_ip'),
        Index('idx_start_time', 'start_time'),
    )


class KnowledgeGraphLog(Base):
    """
    知识图谱查询日志表

    记录知识图谱的使用情况
    """
    __tablename__ = "knowledge_graph_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联信息
    request_id = Column(String(64), comment="关联的请求ID")
    tool_call_id = Column(Integer, comment="关联的工具调用日志ID")

    # 查询信息
    query = Column(Text, comment="查询内容")
    query_type = Column(String(32), comment="查询类型")

    # 执行信息
    search_mode = Column(String(32), comment="搜索模式：naive/local/global/hybrid/mix")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration_ms = Column(Float, comment="执行时长（毫秒）")

    # 结果
    status = Column(String(16), comment="执行状态：success/error")
    result_length = Column(Integer, comment="结果长度")
    has_result = Column(Boolean, comment="是否有结果")

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_request_id', 'request_id'),
        Index('idx_search_mode', 'search_mode'),
        Index('idx_created_at', 'created_at'),
    )


class ErrorLog(Base):
    """
    错误日志表

    记录系统错误信息，用于错误分析和监控
    """
    __tablename__ = "error_log"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联信息
    request_id = Column(String(64), comment="关联的请求ID")
    session_id = Column(String(64), comment="会话ID")

    # 错误信息
    error_code = Column(String(32), comment="错误码")
    error_type = Column(String(64), comment="错误类型")
    error_message = Column(Text, comment="错误消息")
    traceback = Column(Text, comment="错误堆栈")

    # 上下文
    component = Column(String(64), comment="出错组件：agent/tool/db/llm/etc")
    function_name = Column(String(128), comment="出错函数名")

    # 元数据
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 索引
    __table_args__ = (
        Index('idx_error_code', 'error_code'),
        Index('idx_component', 'component'),
        Index('idx_created_at', 'created_at'),
    )
