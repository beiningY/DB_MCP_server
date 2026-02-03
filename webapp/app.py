"""
数据分析 Agent 展示页面 - FastAPI 后端
支持动态数据库连接
"""

import os
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# 导入工具
from tools import execute_sql_query, get_table_schema


# ============= 请求/响应模型 =============
class ChatRequest(BaseModel):
    question: str
    # 数据库连接参数
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "information_schema"


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list = []


class SQLRequest(BaseModel):
    sql: str
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "information_schema"
    limit: Optional[int] = 100


class SchemaRequest(BaseModel):
    table_name: Optional[str] = None
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    database: str = "information_schema"


# ============= FastAPI App =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("🚀 数据分析服务启动...")
    print("🔌 支持动态数据库连接")
    yield
    print("👋 服务关闭")


app = FastAPI(
    title="数据分析工具",
    description="支持动态数据库连接的数据分析工具",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= API 路由 =============
@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理对话请求（简化版，直接调用工具）"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        # 简单处理：根据问题类型决定调用哪个工具
        question_lower = request.question.lower()

        if "表" in request.question and ("结构" in request.question or "字段" in request.question):
            # 查询表结构
            # 提取表名（简单处理）
            table_name = None
            for word in request.question.split():
                if word not in ["查询", "表", "结构", "的", "是", "有什么", "有哪些", "字段", "显示"]:
                    table_name = word
                    break

            result = get_table_schema.invoke({
                "table_name": table_name,
                "host": request.host,
                "port": request.port,
                "username": request.username,
                "password": request.password,
                "database": request.database
            })
            answer = result

        elif "select" in question_lower or "sql" in question_lower:
            # 执行 SQL
            sql = request.question
            result = execute_sql_query.invoke({
                "sql": sql,
                "host": request.host,
                "port": request.port,
                "username": request.username,
                "password": request.password,
                "database": request.database,
                "limit": 100
            })
            answer = result

        else:
            # 获取所有表列表
            result = get_table_schema.invoke({
                "table_name": None,
                "host": request.host,
                "port": request.port,
                "username": request.username,
                "password": request.password,
                "database": request.database
            })
            answer = result

        return ChatResponse(answer=answer, tool_calls=[])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/execute-sql")
async def execute_sql(request: SQLRequest):
    """执行 SQL 查询"""
    try:
        result = execute_sql_query.invoke({
            "sql": request.sql,
            "host": request.host,
            "port": request.port,
            "username": request.username,
            "password": request.password,
            "database": request.database,
            "limit": request.limit
        })
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schema")
async def get_schema(
    host: str = "localhost",
    port: int = 3306,
    username: str = "root",
    password: str = "",
    database: str = "information_schema",
    table_name: Optional[str] = None
):
    """获取数据库表结构"""
    try:
        result = get_table_schema.invoke({
            "table_name": table_name,
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "database": database
        })
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "service": "DB Analysis API",
        "version": "2.0.0",
        "features": ["dynamic_database_connection", "real_time_schema_query"]
    }


# ============= 启动入口 =============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
