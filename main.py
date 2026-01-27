"""
MCP Server 启动入口
支持通过 HTTP + SSE 方式运行，可以部署在云端

使用方式:
    python main.py                    # 默认配置启动
    python main.py --host 0.0.0.0 --port 8000  # 自定义地址和端口
    python main.py --reload          # 开发模式（热重载）
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入服务器和日志配置
from server import app
from logger_config import setup_logging, get_server_logger

# 配置日志
logger = get_server_logger()


def create_sse_server():
    """
    创建 SSE (Server-Sent Events) 服务器
    
    SSE 是一种服务器推送技术，允许服务器主动向客户端发送数据。
    这是 MCP 协议支持的远程连接方式之一，适合云端部署。
    
    Returns:
        Starlette 应用实例
    """
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import Response, JSONResponse
    from mcp.server.sse import SseServerTransport
    
    # 创建 SSE 传输实例
    # SseServerTransport 需要指定消息接收的端点路径
    # 客户端会通过 /sse 建立 SSE 连接，然后通过 /messages/ 发送消息
    transport = SseServerTransport("/messages/")
    
    # 定义 SSE 连接端点
    async def handle_sse(request):
        """
        SSE 端点处理函数
        
        处理客户端的 SSE 连接请求，建立长连接进行双向通信。
        MCP 客户端通过此端点与服务器建立连接。
        
        工作流程：
        1. 客户端 GET /sse 建立 SSE 连接
        2. 服务器返回 /messages/?session_id=xxx 告诉客户端消息发送地址
        3. 客户端 POST /messages/?session_id=xxx 发送请求
        4. 服务器通过 SSE 返回响应
        """
        client_host = request.client.host if request.client else 'unknown'
        logger.info(f"新的 SSE 连接请求来自: {client_host}")
        
        # 使用 connect_sse 上下文管理器建立连接
        # 这会返回读写流，用于 MCP 协议通信
        async with transport.connect_sse(
            request.scope, 
            request.receive, 
            request._send
        ) as streams:
            # streams[0] 是读取流（接收客户端消息）
            # streams[1] 是写入流（发送服务器响应）
            await app.run(
                streams[0], 
                streams[1], 
                app.create_initialization_options()
            )
        
        # 返回空响应，避免 NoneType 错误
        return Response()
    
    async def health_check(request):
        """
        健康检查端点
        
        用于检查服务器是否正常运行，适合用于负载均衡和监控。
        """
        return JSONResponse({
            "status": "healthy",
            "server": "DB MCP Server",
            "version": "0.1.0",
            "tools": ["execute_sql", "get_table_schema", "search_knowledge"],
            "resources": ["metadata://online_dictionary", "metadata://singa_bi", "metadata://redash_queries", "info://server/status"]
        })
    
    async def root(request):
        """
        根路径端点
        
        返回服务器基本信息和使用说明。
        """
        return JSONResponse({
            "name": "DB MCP Server",
            "version": "0.1.0",
            "description": "数据工具 MCP 服务器 - 提供 SQL 执行、表结构查询、知识图谱搜索等功能",
            "endpoints": {
                "/": "服务器信息（当前页面）",
                "/health": "健康检查",
                "/sse": "SSE 连接端点（MCP 客户端连接此端点）",
                "/messages/": "MCP 消息处理（SSE 传输使用）"
            },
            "tools": {
                "execute_sql": "执行 SQL 查询",
                "get_table_schema": "获取表结构信息",
                "search_knowledge": "搜索知识图谱"
            }
        })
    
    # 创建 Starlette 应用
    # 注意：/messages/ 使用 Mount 挂载 transport.handle_post_message
    # 这是 MCP SSE 传输的标准用法
    starlette_app = Starlette(
        routes=[
            Route("/", root, methods=["GET"]),
            Route("/health", health_check, methods=["GET"]),
            Route("/sse", handle_sse, methods=["GET"]),
            # Mount 用于挂载 ASGI 应用，处理客户端发送的消息
            Mount("/messages", app=transport.handle_post_message),
        ]
    )
    
    return starlette_app


async def run_stdio_server():
    """
    运行标准输入输出（stdio）服务器
    
    这是 MCP 的标准模式，通过标准输入输出进行通信。
    适合本地开发和命令行工具集成。
    """
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def main():
    """
    主函数：解析命令行参数并启动服务器
    """
    parser = argparse.ArgumentParser(
        description="DB MCP Server - 数据工具 MCP 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置启动 HTTP 服务器
  python main.py
  
  # 指定地址和端口
  python main.py --host 0.0.0.0 --port 8000
  
  # 开发模式（热重载）
  python main.py --reload
  
  # 使用 stdio 模式（本地开发）
  python main.py --mode stdio
  
  # 设置日志级别
  python main.py --log-level debug
        """
    )
    
    # 服务器模式
    parser.add_argument(
        "--mode",
        choices=["sse", "stdio"],
        default="sse",
        help="服务器模式：sse (HTTP+SSE，适合云端) 或 stdio (标准输入输出，适合本地)"
    )
    
    # 网络配置
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("SERVER_HOST", "0.0.0.0"),
        help="监听地址（默认: 0.0.0.0，监听所有网络接口）"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SERVER_PORT", "8000")),
        help="监听端口（默认: 8000）"
    )
    
    # 开发选项
    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用热重载（开发模式，自动检测代码变化并重启）"
    )
    
    # 日志配置
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical"],
        default=os.getenv("LOG_LEVEL", "info"),
        help="日志级别（默认: info）"
    )
    
    parser.add_argument(
        "--log-dir",
        type=str,
        default=os.getenv("LOG_DIR", "./logs"),
        help="日志文件目录（默认: ./logs）"
    )
    
    parser.add_argument(
        "--no-file-log",
        action="store_true",
        help="禁用文件日志，仅输出到控制台（适合容器环境）"
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(
        log_level=args.log_level,
        log_dir=args.log_dir,
        file_output=not args.no_file_log
    )
    
    logger.info("=" * 60)
    logger.info("DB MCP Server 启动中...")
    logger.info(f"模式: {args.mode}")
    logger.info(f"日志级别: {args.log_level}")
    logger.info("=" * 60)
    
    # 根据模式启动不同的服务器
    if args.mode == "stdio":
        # stdio 模式：使用标准输入输出
        logger.info("使用 stdio 模式（标准输入输出）")
        logger.info("适合本地开发和命令行工具集成")
        
        try:
            asyncio.run(run_stdio_server())
        except KeyboardInterrupt:
            logger.info("服务器已停止")
    
    else:
        # SSE 模式：使用 HTTP + SSE
        logger.info(f"使用 SSE 模式（HTTP + Server-Sent Events）")
        logger.info(f"监听地址: {args.host}:{args.port}")
        logger.info("适合云端部署和远程客户端连接")
        logger.info("")
        logger.info("可用端点:")
        logger.info(f"  - http://{args.host}:{args.port}/          # 服务器信息")
        logger.info(f"  - http://{args.host}:{args.port}/health     # 健康检查")
        logger.info(f"  - http://{args.host}:{args.port}/sse        # SSE 连接端点")
        logger.info("")
        
        # 创建 SSE 服务器应用
        starlette_app = create_sse_server()
        
        # 导入 uvicorn（ASGI 服务器）
        try:
            import uvicorn
        except ImportError:
            logger.error("未安装 uvicorn，请运行: pip install uvicorn")
            sys.exit(1)
        
        # 启动 uvicorn 服务器
        # uvicorn 是一个高性能的 ASGI 服务器，支持异步和热重载
        uvicorn.run(
            starlette_app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            access_log=True
        )


if __name__ == "__main__":
    main()
