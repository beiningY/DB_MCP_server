"""
MCP Server 核心模块
支持远程连接 (SSE/HTTP) 的 MCP 服务器框架
"""
import argparse
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# 导入日志配置
from logger_config import setup_logging, get_server_logger

# 在模块级别设置日志（将在 main 函数中初始化）
logger = None


class MCPServerApp:
    """MCP 服务器应用类"""
    
    def __init__(self, name: str = "DB MCP Server"):
        self.name = name
        self.server = Server(name)
        self.sse = SseServerTransport("/messages/")
        
        # 初始化数据分析师 Agent
        self._initialize_data_analyst()
        
        # 注册默认处理器
        self._register_handlers()
    
    def _initialize_data_analyst(self):
        """初始化数据分析师 Agent"""
        try:
            from agent import DataAnalystAgent
            
            self.data_analyst = DataAnalystAgent(
                mysql_config={'db_url': os.getenv("DB_URL")},
                redash_config={
                    'redash_url': os.getenv("REDASH_URL"),
                    'api_key': os.getenv("REDASH_API_KEY")
                },
                llm_config={
                    'model': os.getenv("LLM_MODEL", "gpt-4"),
                    'api_key': os.getenv("LLM_API_KEY"),
                    'base_url': os.getenv("LLM_BASE_URL")
                },
                lightrag_config={
                    'api_url': os.getenv("LIGHTRAG_API_URL")
                }
            )
            if logger:
                logger.info("✓ 数据分析师 Agent 初始化成功")
        except Exception as e:
            if logger:
                logger.warning(f"⚠️ 数据分析师 Agent 初始化失败: {e}")
            self.data_analyst = None
        
    def _register_handlers(self):
        """注册 MCP 协议处理器"""
        
        @self.server.list_tools()
        async def list_tools() -> list[types.Tool]:
            """列出所有可用工具"""
            return self._get_tools()
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
            """调用指定工具"""
            return await self._call_tool(name, arguments)
        
        @self.server.list_resources()
        async def list_resources() -> list[types.Resource]:
            """列出所有可用资源"""
            return self._get_resources()
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """读取指定资源"""
            return await self._read_resource(uri)
        
        @self.server.list_prompts()
        async def list_prompts() -> list[types.Prompt]:
            """列出所有可用提示模板"""
            return self._get_prompts()
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
            """获取指定提示模板"""
            return await self._get_prompt(name, arguments)
    
    def _get_tools(self) -> list[types.Tool]:
        """获取工具列表 - 可扩展"""
        tools = [
            types.Tool(
                name="ping",
                description="测试服务器连接是否正常",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="echo",
                description="回显输入的消息",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "要回显的消息"
                        }
                    },
                    "required": ["message"]
                }
            ),
            types.Tool(
                name="calculate",
                description="执行简单的数学计算",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如 '2 + 3 * 4'"
                        }
                    },
                    "required": ["expression"]
                }
            )
        ]
        
        # 添加数据分析师工具
        if self.data_analyst:
            tools.append(
                types.Tool(
                    name="data_analyst",
                    description="""智能数据分析助手 - 基于 Plan-Execute-Replan 模式的 AI 数据分析师

核心能力：
1. **自然语言转 SQL** - 理解中文/英文问题，自动生成 SQL 查询
2. **元数据搜索** - 搜索表结构、字段含义、业务域信息
3. **历史查询参考** - 通过 LightRAG 搜索相似的历史 SQL 查询
4. **SQL 执行** - 支持 MySQL 直连和 Redash API 两种执行方式
5. **查询优化** - 分析 SQL 性能并提供优化建议
6. **数据分析** - 对查询结果生成统计分析和洞察

适用场景：
- 快速查询业务数据（放款、催收、用户等）
- 生成业务报表和统计分析
- 优化慢查询
- 了解表结构和字段含义

数据库：singa_bi（印尼金融科技业务数据）""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "数据分析问题（支持中文/英文）\n示例：\n- 查询昨天的放款总金额\n- temp_rc_model_daily 表的 machine_status 字段是什么含义？\n- 最近7天每天的新用户注册数量"
                            },
                            "database": {
                                "type": "string",
                                "description": "目标数据库名称（默认: singa_bi）",
                                "default": "singa_bi"
                            },
                            "use_redash": {
                                "type": "boolean",
                                "description": "是否通过 Redash API 执行查询（默认: false，使用 MySQL 直连）",
                                "default": False
                            },
                            "max_iterations": {
                                "type": "integer",
                                "description": "最大迭代次数（默认: 10）",
                                "default": 10
                            }
                        },
                        "required": ["question"]
                    }
                )
            )
        
        return tools
    
    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """工具调用分发器"""
        if logger:
            logger.info(f"调用工具: {name}, 参数: {arguments}")
        
        if name == "ping":
            return [types.TextContent(type="text", text="pong! 服务器连接正常 ✓")]
        
        elif name == "echo":
            message = arguments.get("message", "")
            return [types.TextContent(type="text", text=f"Echo: {message}")]
        
        elif name == "calculate":
            expression = arguments.get("expression", "")
            try:
                # 安全的数学表达式求值
                allowed_chars = set("0123456789+-*/(). ")
                if not all(c in allowed_chars for c in expression):
                    raise ValueError("表达式包含不允许的字符")
                result = eval(expression)
                return [types.TextContent(type="text", text=f"{expression} = {result}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"计算错误: {str(e)}")]
        
        elif name == "data_analyst":
            if not self.data_analyst:
                return [types.TextContent(
                    type="text",
                    text="❌ 数据分析师 Agent 未初始化，请检查配置"
                )]
            
            question = arguments.get("question", "")
            database = arguments.get("database", "singa_bi")
            use_redash = arguments.get("use_redash", False)
            max_iterations = arguments.get("max_iterations", 10)
            
            try:
                if logger:
                    logger.info(f"数据分析师处理问题: {question}")
                result = await self.data_analyst.analyze(
                    question=question,
                    database=database,
                    use_redash=use_redash,
                    max_iterations=max_iterations
                )
                return [types.TextContent(type="text", text=result)]
            except Exception as e:
                if logger:
                    logger.error(f"数据分析失败: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"❌ 分析失败: {str(e)}"
                )]
        
        else:
            raise ValueError(f"未知工具: {name}")
    
    def _get_resources(self) -> list[types.Resource]:
        """获取资源列表 - 可扩展"""
        resources = [
            types.Resource(
                uri="info://server/status",
                name="服务器状态",
                description="获取当前服务器运行状态",
                mimeType="application/json"
            ),
            types.Resource(
                uri="info://server/version",
                name="版本信息",
                description="获取服务器版本信息",
                mimeType="text/plain"
            )
        ]
        
        # 添加元数据资源
        if self.data_analyst:
            resources.extend([
                types.Resource(
                    uri="metadata://online_dictionary",
                    name="在线数据字典",
                    description="表和字段的业务含义、枚举值、注释等信息",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="metadata://singa_bi",
                    name="Singa BI 元数据",
                    description="BI 数据库的完整表结构、业务域、字段类型、关系等信息",
                    mimeType="application/json"
                ),
                types.Resource(
                    uri="metadata://summary",
                    name="元数据摘要",
                    description="数据库元数据的统计摘要信息",
                    mimeType="application/json"
                )
            ])
        
        return resources
    
    async def _read_resource(self, uri: str) -> str:
        """读取资源"""
        if logger:
            logger.info(f"读取资源: {uri}")
        
        if uri == "info://server/status":
            import json
            status = {
                "status": "running",
                "name": self.name,
                "tools_count": len(self._get_tools()),
                "resources_count": len(self._get_resources()),
                "data_analyst_enabled": self.data_analyst is not None
            }
            return json.dumps(status, ensure_ascii=False, indent=2)
        
        elif uri == "info://server/version":
            return "DB MCP Server v0.1.0"
        
        elif uri.startswith("metadata://") and self.data_analyst:
            # 使用元数据资源模块
            from resources.metadata_resources import MetadataResources
            
            for resource in MetadataResources.get_all_resources():
                if resource.uri == uri:
                    return await resource.read()
            
            raise ValueError(f"未找到元数据资源: {uri}")
        
        else:
            raise ValueError(f"未知资源: {uri}")
    
    def _get_prompts(self) -> list[types.Prompt]:
        """获取提示模板列表 - 可扩展"""
        return [
            types.Prompt(
                name="greeting",
                description="生成问候语",
                arguments=[
                    types.PromptArgument(
                        name="name",
                        description="用户名称",
                        required=True
                    )
                ]
            )
        ]
    
    async def _get_prompt(self, name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
        """获取提示模板内容"""
        if name == "greeting":
            user_name = arguments.get("name", "用户") if arguments else "用户"
            return types.GetPromptResult(
                description="个性化问候",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"你好，{user_name}！欢迎使用 DB MCP Server。"
                        )
                    )
                ]
            )
        raise ValueError(f"未知提示模板: {name}")
    
    async def handle_sse(self, request: Request):
        """处理 SSE 连接请求"""
        if logger:
            logger.info(f"新的 SSE 连接: {request.client}")
        async with self.sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await self.server.run(
                streams[0], streams[1], self.server.create_initialization_options()
            )
    
    async def handle_messages(self, request: Request):
        """处理消息请求"""
        await self.sse.handle_post_message(request.scope, request.receive, request._send)
    
    def create_app(self) -> Starlette:
        """创建 Starlette 应用"""
        
        async def health_check(request: Request):
            """健康检查端点"""
            return JSONResponse({
                "status": "healthy",
                "server": self.name,
                "version": "0.1.0"
            })
        
        async def server_info(request: Request):
            """服务器信息端点"""
            return JSONResponse({
                "name": self.name,
                "version": "0.1.0",
                "protocol": "MCP",
                "transport": "SSE",
                "endpoints": {
                    "sse": "/sse",
                    "messages": "/messages/",
                    "health": "/health"
                },
                "tools": [t.name for t in self._get_tools()],
                "resources": [r.uri for r in self._get_resources()]
            })
        
        # 配置 CORS 中间件，允许跨域访问
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
        
        # 定义路由
        routes = [
            Route("/", endpoint=server_info, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/sse", endpoint=self.handle_sse, methods=["GET"]),
            Route("/messages/", endpoint=self.handle_messages, methods=["POST"]),
        ]
        
        return Starlette(
            routes=routes,
            middleware=middleware,
            on_startup=[self._on_startup],
            on_shutdown=[self._on_shutdown]
        )
    
    async def _on_startup(self):
        """服务器启动回调"""
        if logger:
            logger.info(f"🚀 {self.name} 启动成功")
            logger.info("📡 SSE 端点: /sse")
            logger.info("📨 消息端点: /messages/")
    
    async def _on_shutdown(self):
        """服务器关闭回调"""
        if logger:
            logger.info(f"👋 {self.name} 正在关闭...")


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description="DB MCP Server - 支持远程连接的 MCP 服务器")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    parser.add_argument("--reload", action="store_true", help="开启热重载 (开发模式)")
    parser.add_argument("--log-level", type=str, default="info", 
                       choices=["debug", "info", "warning", "error"],
                       help="日志级别 (默认: info)")
    parser.add_argument("--log-dir", type=str, default=None, help="日志文件目录 (默认: ./logs)")
    parser.add_argument("--no-file-log", action="store_true", help="禁用文件日志输出")
    
    args = parser.parse_args()
    
    # 配置日志
    global logger
    setup_logging(
        log_dir=args.log_dir,
        log_level=args.log_level,
        console_output=True,
        file_output=not args.no_file_log,
        rotation_mode='time',  # 按天轮转
        backup_count=30  # 保留30天
    )
    logger = get_server_logger()
    logger.info("日志系统初始化完成")
    
    # 创建应用
    mcp_app = MCPServerApp(name="DB MCP Server")
    app = mcp_app.create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              DB MCP Server - 远程连接模式                      ║
╠══════════════════════════════════════════════════════════════╣
║  🌐 服务地址: http://{args.host}:{args.port}                      
║  📡 SSE 端点: http://{args.host}:{args.port}/sse                  
║  📨 消息端点: http://{args.host}:{args.port}/messages/            
║  ❤️  健康检查: http://{args.host}:{args.port}/health              
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 启动服务器
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload
    )


if __name__ == "__main__":
    main()

