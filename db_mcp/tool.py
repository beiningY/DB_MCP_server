"""
MCP Tools - 数据分析工具定义
只暴露 data_agent 工具，其他工具由 Agent 内部调用

该模块负责注册 MCP 工具到服务器。对外只暴露一个 data_agent 工具，
该工具内部会调用 LangChain Agent，Agent 会根据需要调用三个内部工具：
- execute_sql_query: 执行 SQL 查询
- get_table_schema: 获取表结构
- search_knowledge_graph: 搜索知识图谱

使用方式：
    # 该模块会被 server.py 自动导入和调用
    from .tool import register_tools
    register_tools(mcp)
"""

import os
import json
from typing import Optional, Dict, Any


# ============================================================================
# 数据库配置获取函数
# ============================================================================

def get_current_db_config_from_server() -> Dict[str, Any]:
    """
    从 server 模块获取当前请求的数据库配置

    Returns:
        当前数据库配置字典，包含 host, port, username, password, database
    """
    try:
        from .server import get_current_db_config
        return get_current_db_config()
    except ImportError:
        return {}


def get_current_session_id_from_server() -> str:
    """
    从 server 模块获取当前请求的 session_id

    Returns:
        session_id 字符串
    """
    try:
        from .server import get_current_session_id
        return get_current_session_id()
    except ImportError:
        return "default"


def get_default_db_config(session_id: str = None) -> Dict[str, Any]:
    """
    获取当前数据库配置（从 URL 参数）

    Args:
        session_id: session 标识符（可选）

    Returns:
        数据库配置字典
    """
    url_config = get_current_db_config_from_server()
    if url_config:
        return url_config
    return {}


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
        - data_agent: 数据分析智能体（自然语言查询接口）
    """

    @mcp.tool()
    async def data_agent(
        query: str
    ) -> str:
        """
        数据分析智能体 - 通过自然语言查询和分析数据库

        这是 MCP 服务器对外暴露的主要工具。用户可以用自然语言描述数据需求，
        Agent 会自动调用合适的工具完成任务。

        功能：
        - 理解自然语言的数据分析需求
        - 自动查询数据库表结构（实时从 information_schema）
        - 搜索知识图谱（业务逻辑、历史 SQL、BI库里的表和字段命名规则）
        - 生成并执行 SQL 查询
        - 整理分析结果

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

        Examples:
            >>> data_agent("查询 users 表有多少条记录")
            >>> data_agent("显示 orders 表的结构")
            >>> data_agent("最近7天的订单数量趋势")
            >>> data_agent("还款率是怎么计算的")

        注意：
            使用前需要在 URL 中配置数据库连接参数，例如：
            http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb
        """
        if not query:
            return "错误：查询内容不能为空"

        # 检查数据库配置
        config = get_default_db_config()
        if not config.get("host"):
            return """错误：未配置数据库连接

请在客户端配置文件的 URL 中添加数据库参数：
?host=数据库地址&port=端口&username=用户名&password=密码&database=数据库名

示例：
"url": "http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb"

或者使用预定义配置：
"url": "http://localhost:8000/sse?session=prod"
"""

        # 调用 Agent
        try:
            from agent.data_simple_agent import get_agent

            agent = get_agent()
            result = agent.invoke({
                "messages": [
                    {
                        "role": "system",
                        "content": f"""你是一个数据分析智能体。当前数据库配置：
- 主机: {config['host']}
- 端口: {config['port']}
- 用户: {config['username']}
- 数据库: {config['database']}

可用工具：
1. execute_sql_query - 执行 SQL 查询（需要传入数据库连接参数）
2. get_table_schema - 获取表结构（需要传入数据库连接参数）
3. search_knowledge_graph - 搜索知识图谱（业务逻辑、历史 SQL）

重要：调用 execute_sql_query 和 get_table_schema 时，必须传入以下参数：
- host: {config['host']}
- port: {config['port']}
- username: {config['username']}
- password: {config['password']}
- database: {config['database']}
"""
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ]
            })

            # 提取最终回复
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                for msg in reversed(messages):
                    if hasattr(msg, "content") and msg.content:
                        return msg.content
                    elif isinstance(msg, dict) and msg.get("content"):
                        return msg["content"]

            return str(result)

        except Exception as e:
            return f"Agent 调用失败: {str(e)}"
