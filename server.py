"""
MCP Server 主文件
提供数据相关的工具和资源，支持云端部署

这个文件实现了 MCP (Model Context Protocol) 服务器，将数据工具包装成 MCP 工具和资源。
支持通过 SSE (Server-Sent Events) 进行远程连接，可以部署在云端。
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Sequence

# MCP 核心库
from mcp.server import Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
)

# 导入现有工具
from tools.execute_sql_tool import execute_sql_query
from tools.get_table_schema_tool import get_table_schema
from tools.search_knowledge_tool import search_knowledge_graph

# 日志配置
from logger_config import get_server_logger

# 初始化日志
logger = get_server_logger()

# 创建 MCP 服务器实例
# Server 是 MCP 协议的核心类，负责处理客户端请求
app = Server("db-mcp-server")


# ============================================================================
# MCP 工具注册
# ============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    列出所有可用的工具
    
    这个函数会在客户端请求工具列表时被调用。
    返回的工具可以被客户端调用执行。
    
    Returns:
        工具列表，每个工具包含名称、描述和参数定义
    """
    logger.info("客户端请求工具列表")
    
    return [
        Tool(
            name="execute_sql",
            description=(
                "执行 SQL 查询并返回结果。"
                "仅支持 SELECT 查询，自动添加 LIMIT 保护。"
                "返回 JSON 格式的查询结果，包含数据、列名、行数和执行时间。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "要执行的 SQL 查询语句（仅支持 SELECT）"
                    },
                    "database": {
                        "type": "string",
                        "description": "目标数据库名称，默认 'singa_bi'",
                        "default": "singa_bi"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大返回行数，默认 100",
                        "default": 100
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="get_table_schema",
            description=(
                "获取数据库表的结构信息（字段、类型、注释等）。"
                "如果不指定表名，返回所有表的摘要列表。"
                "如果指定表名，返回该表的详细结构信息。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "表名。如果为空，返回所有表的摘要列表"
                    },
                    "database": {
                        "type": "string",
                        "description": "数据库名称，默认 'singa_bi'",
                        "default": "singa_bi"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="search_knowledge",
            description=(
                "在知识图谱中搜索相关信息（历史 SQL 查询、表字段说明、业务逻辑）。"
                "支持自然语言查询，可以查找历史查询、表字段含义、业务逻辑等。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，支持自然语言描述。例如：'如何计算放款金额'、'temp_rc_model_daily 表的用途'"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["naive", "local", "global", "hybrid", "mix", "bypass"],
                        "description": "搜索模式，默认 'mix'（推荐）",
                        "default": "mix"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的结果数量，默认 5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """
    执行工具调用
    
    当客户端调用工具时，这个函数会被触发。
    根据工具名称路由到对应的实现函数。
    
    Args:
        name: 工具名称
        arguments: 工具参数（字典格式）
    
    Returns:
        工具执行结果，以 TextContent 或 ImageContent 列表形式返回
    
    Raises:
        ValueError: 如果工具名称不存在
    """
    logger.info(f"调用工具: {name}, 参数: {arguments}")
    
    try:
        # 根据工具名称路由到对应的实现
        if name == "execute_sql":
            # 执行 SQL 查询
            sql = arguments.get("sql", "")
            database = arguments.get("database", "singa_bi")
            limit = arguments.get("limit", 100)
            
            # 调用工具函数（注意：这里需要同步调用，所以使用 asyncio.to_thread）
            result = await asyncio.to_thread(
                execute_sql_query.invoke,
                {"sql": sql, "database": database, "limit": limit}
            )
            
            return [TextContent(type="text", text=result)]
        
        elif name == "get_table_schema":
            # 获取表结构
            table_name = arguments.get("table_name")
            database = arguments.get("database", "singa_bi")
            
            result = await asyncio.to_thread(
                get_table_schema.invoke,
                {"table_name": table_name, "database": database}
            )
            
            return [TextContent(type="text", text=result)]
        
        elif name == "search_knowledge":
            # 搜索知识图谱
            query = arguments.get("query", "")
            mode = arguments.get("mode", "mix")
            top_k = arguments.get("top_k", 5)
            
            result = await asyncio.to_thread(
                search_knowledge_graph.invoke,
                {"query": query, "mode": mode, "top_k": top_k}
            )
            
            return [TextContent(type="text", text=result)]
        
        else:
            # 未知工具
            error_msg = f"未知工具: {name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    except Exception as e:
        # 捕获异常并返回错误信息
        error_msg = f"工具执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "message": error_msg
        }, ensure_ascii=False))]


# ============================================================================
# MCP 资源注册
# ============================================================================

@app.list_resources()
async def list_resources() -> list[Resource]:
    """
    列出所有可用的资源
    
    资源是只读的数据源，客户端可以读取但无法修改。
    这里提供元数据文件作为资源。
    
    Returns:
        资源列表，每个资源包含 URI、名称和描述
    """
    logger.info("客户端请求资源列表")
    
    resources = []
    
    # 元数据文件路径
    metadata_dir = Path("metadata")
    
    # 在线字典资源
    if (metadata_dir / "online_dictionary.json").exists():
        resources.append(
            Resource(
                uri="metadata://online_dictionary",
                name="在线数据字典",
                description="包含表和字段的业务含义、枚举值说明等",
                mimeType="application/json"
            )
        )
    
    # BI 元数据资源
    if (metadata_dir / "singa_bi_metadata.json").exists():
        resources.append(
            Resource(
                uri="metadata://singa_bi",
                name="Singa BI 元数据",
                description="完整的数据库元数据，包含表结构、业务域、字段关系等",
                mimeType="application/json"
            )
        )
    
    # Redash 查询资源
    if (metadata_dir / "redash_queries.json").exists():
        resources.append(
            Resource(
                uri="metadata://redash_queries",
                name="Redash 历史查询",
                description="从 Redash 导出的历史 SQL 查询记录",
                mimeType="application/json"
            )
        )
    
    # 服务器状态资源（动态生成）
    resources.append(
        Resource(
            uri="info://server/status",
            name="服务器状态",
            description="服务器运行状态和配置信息",
            mimeType="application/json"
        )
    )
    
    return resources


@app.read_resource()
async def read_resource(uri) -> str:
    """
    读取资源内容
    
    当客户端请求读取资源时，这个函数会被调用。
    根据 URI 路由到对应的资源文件。
    
    Args:
        uri: 资源 URI（AnyUrl 类型），格式如 "metadata://online_dictionary"
    
    Returns:
        资源内容（字符串格式）
    
    Raises:
        ValueError: 如果资源 URI 不存在或无法读取
    """
    # 将 AnyUrl 转换为字符串进行处理
    uri_str = str(uri)
    logger.info(f"读取资源: {uri_str}")
    
    try:
        # 根据 URI 前缀路由
        if uri_str.startswith("metadata://"):
            # 元数据资源
            metadata_dir = Path("metadata")
            
            if uri_str == "metadata://online_dictionary":
                file_path = metadata_dir / "online_dictionary.json"
            elif uri_str == "metadata://singa_bi":
                file_path = metadata_dir / "singa_bi_metadata.json"
            elif uri_str == "metadata://redash_queries":
                file_path = metadata_dir / "redash_queries.json"
            else:
                raise ValueError(f"未知的元数据资源: {uri_str}")
            
            # 读取文件内容
            if not file_path.exists():
                raise ValueError(f"资源文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
        
        elif uri_str.startswith("info://"):
            # 信息类资源（动态生成）
            if uri_str == "info://server/status":
                # 返回服务器状态
                status = {
                    "status": "running",
                    "server": "DB MCP Server",
                    "version": "0.1.0",
                    "tools_count": 3,
                    "resources_count": 4,
                    "database_configured": bool(os.getenv("DB_URL")),
                    "lightrag_configured": bool(os.getenv("LIGHTRAG_API_URL"))
                }
                return json.dumps(status, ensure_ascii=False, indent=2)
            else:
                raise ValueError(f"未知的信息资源: {uri_str}")
        
        else:
            raise ValueError(f"未知的资源 URI 格式: {uri_str}")
    
    except Exception as e:
        error_msg = f"读取资源失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg)


# ============================================================================
# 服务器启动函数（仅用于 stdio 模式）
# ============================================================================

async def run_stdio_server():
    """
    运行标准输入输出（stdio）模式的服务器
    
    这是 MCP 的标准模式，通过标准输入输出进行通信。
    适合本地开发和命令行工具集成。
    """
    from mcp.server.stdio import stdio_server
    
    logger.info("使用 stdio 模式（标准输入输出）")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    # 直接运行此文件时，使用标准输入输出（stdio）模式
    # 这是 MCP 的标准模式，适合本地开发
    # 对于 SSE 模式，请使用 main.py 启动
    asyncio.run(run_stdio_server())
