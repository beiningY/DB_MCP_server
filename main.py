#!/usr/bin/env python3
"""
DB Analysis MCP Server 启动入口

启动方式:
    python main.py
    
或使用 uvicorn (端口通过环境变量 MCP_PORT 配置，默认 8080):
    uvicorn db_mcp.server:app --host 0.0.0.0 --port ${MCP_PORT:-8080}
"""

from db_mcp import start_server

if __name__ == "__main__":
    start_server()
