"""
数据分析 Agent 展示页面 - FastAPI 后端
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

# 导入 Agent
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import execute_sql_query, search_knowledge_graph, get_table_schema


# ============= 配置 =============
SYSTEM_PROMPT = """你是一个专业的数据分析智能体。

## 可用工具
1. **get_table_schema** - 获取数据库表结构信息
2. **search_knowledge_graph** - 搜索知识图谱，查找历史 SQL 和业务逻辑
3. **execute_sql_query** - 执行 SQL 查询（仅支持 SELECT）

## 工作流程
1. 理解用户问题
2. 如有需要，先用 get_table_schema 了解表结构
3. 用 search_knowledge_graph 查找相关历史查询和业务逻辑
4. 生成并执行 SQL 查询
5. 整理结果回答用户

请用清晰、专业的方式回答用户的数据分析问题。
"""


# ============= 模型和 Agent =============
_agent = None

def get_agent():
    """延迟初始化 Agent"""
    global _agent
    if _agent is None:
        model = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
        )
        tools = [execute_sql_query, search_knowledge_graph, get_table_schema]
        _agent = create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)
    return _agent


# ============= FastAPI App =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    print("🚀 数据分析 Agent 服务启动...")
    yield
    print("👋 服务关闭")


app = FastAPI(
    title="数据分析 Agent",
    description="基于 LLM 的智能数据分析助手",
    version="1.0.0",
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


# ============= 请求/响应模型 =============
class ChatRequest(BaseModel):
    question: str
    

class ChatResponse(BaseModel):
    answer: str
    tool_calls: list = []


# ============= API 路由 =============
@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理对话请求"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    try:
        agent = get_agent()
        result = await asyncio.to_thread(
            agent.invoke,
            {"messages": [{"role": "user", "content": request.question}]}
        )
        
        # 提取回答和工具调用
        messages = result.get("messages", [])
        answer = ""
        tool_calls = []
        
        for msg in messages:
            if hasattr(msg, "content") and msg.content:
                # 最后一条有内容的消息作为回答
                if hasattr(msg, "type") and msg.type == "ai":
                    answer = msg.content
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {})
                    })
        
        return ChatResponse(answer=answer, tool_calls=tool_calls)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


# ============= 启动入口 =============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)
