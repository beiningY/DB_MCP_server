# DB MCP Server

基于 MCP (Model Context Protocol) 协议的数据工具服务器，支持云端部署，提供 SQL 执行、表结构查询、知识图谱搜索等功能。

## 核心特性

- **MCP 协议支持**：兼容 Cursor、Claude Desktop 等 AI 客户端
- **SSE 远程连接**：支持云端部署，客户端通过 HTTP 连接
- **数据工具集成**：SQL 执行、表结构查询、知识图谱搜索
- **元数据资源**：在线字典、BI 元数据、历史查询

## 服务依赖

### 必需服务

| 服务 | 说明 | 配置项 |
|------|------|--------|
| **MySQL** | 数据库（用于 SQL 查询） | `DB_URL` |

### 可选服务

| 服务 | 说明 | 配置项 | 启动方式 |
|------|------|--------|----------|
| **LightRAG** | 知识图谱搜索 | `LIGHTRAG_API_URL` | 独立部署 |
| **Neo4j** | 图数据库（LightRAG 依赖） | `NEO4J_URI` | `docker-compose up neo4j` |
| **Qdrant** | 向量数据库（LightRAG 依赖） | `QDRANT_URL` | `docker-compose up qdrant` |

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp env.example .env

# 编辑配置文件
nano .env
```

**最小配置**（仅需 MySQL）：
```bash
# 数据库连接（必需）
DB_URL=mysql+pymysql://用户名:密码@主机:3306/数据库名?charset=utf8mb4
```

**完整配置**：
```bash
# 数据库连接（必需）
DB_URL=mysql+pymysql://用户名:密码@主机:3306/数据库名?charset=utf8mb4

# LightRAG 知识图谱（可选，用于 search_knowledge 工具）
LIGHTRAG_API_URL=http://localhost:9621

# 服务器配置（可选）
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=info
```

### 3. 启动可选服务（如需要）

如果使用知识图谱功能，需要先启动 Neo4j 和 Qdrant：

```bash
# 启动 Neo4j + Qdrant
docker-compose up -d

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

### 4. 启动 MCP Server

```bash
# 使用 uv 运行（推荐）
uv run python server.py

# 或直接运行
python server.py

# 自定义端口（通过环境变量）
MCP_PORT=8000 python server.py

# 自定义主机
MCP_HOST=0.0.0.0 MCP_PORT=8080 python server.py
```

### 5. 验证启动

```bash
# 健康检查
curl http://localhost:8080/health
```

预期返回：
```json
{
  "status": "ok",
  "server": "db-analysis-server",
  "version": "1.0.0",
  "tools": ["ask_data_agent"],
  "resources": ["db://singa_bi/overview", "db://singa_bi/tables"]
}
```

## 工具说明

| 工具名 | 功能 | 依赖服务 |
|--------|------|----------|
| `ask_data_agent` | 数据分析智能体（自然语言交互） | MySQL + LLM |
| `execute_sql` | 执行 SQL 查询（仅 SELECT） | MySQL |
| `get_table_schema` | 获取表结构信息 | 元数据文件 |
| `search_knowledge` | 搜索知识图谱 | LightRAG（可选） |

### ask_data_agent 工具

智能数据分析 Agent，支持自然语言交互：

```python
# 示例调用
await session.call_tool("ask_data_agent", {"query": "查询最近7天的订单数量"})
await session.call_tool("ask_data_agent", {"query": "还款率是如何计算的"})
```

Agent 会自动：
1. 理解用户问题
2. 查询表结构获取相关表信息
3. 搜索知识图谱查找历史 SQL
4. 生成并执行 SQL 查询
5. 整理结果返回

## 资源说明

资源信息**实时从数据库获取**，而非本地文件。

| URI | 说明 | 数据来源 |
|-----|------|----------|
| `db://{database}/overview` | 数据库概览（表列表） | 实时查询 `information_schema` |
| `db://{database}/tables` | 所有表完整 Schema | 实时查询数据库 |
| `db://{database}/table/{name}` | 单表详细结构 | 实时查询（含索引、外键） |

**注意**: `{database}` 会自动替换为 `DB_URL` 中配置的数据库名。

## 客户端配置

### Cursor 配置

编辑 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "db-analysis": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Claude Desktop 配置

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "db-analysis": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Python 客户端

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://localhost:8080/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print("可用工具:", [t.name for t in tools.tools])
            
            # 列出资源
            resources = await session.list_resources()
            print("可用资源:", [r.uri for r in resources.resources])
            
            # 调用 Agent 工具
            result = await session.call_tool(
                "ask_data_agent", 
                {"query": "有哪些用户相关的表？"}
            )
            print(result.content[0].text)
            
            # 读取资源
            overview = await session.read_resource("db://singa_bi/overview")
            print(overview.contents[0].text)

asyncio.run(main())
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/sse` | GET | SSE 连接端点（MCP 客户端使用） |
| `/messages/` | POST | MCP 消息处理 |

## 项目结构

```
DB_MCP_server/
├── server.py              # MCP 服务器（工具、资源、SSE 端点）
├── logger_config.py       # 日志配置
├── pyproject.toml         # 项目依赖
├── docker-compose.yml     # Neo4j + Qdrant 服务
│
├── agent/                 # AI Agent
│   ├── data_simple_agent.py       # 数据分析 Agent（ReAct 模式）
│   ├── data_analyst_agent.py      # 高级分析 Agent
│   └── prompts.py                 # Agent 提示词
│
├── tools/                 # 数据工具（Agent 内部使用）
│   ├── execute_sql_tool.py        # SQL 执行
│   ├── get_table_schema_tool.py   # 表结构查询
│   └── search_knowledge_tool.py   # 知识图谱搜索
│
├── metadata/              # 元数据文件
│   ├── online_dictionary.json     # 在线数据字典
│   ├── singa_bi_metadata.json     # BI 表元数据
│   └── redash_queries.json        # Redash 历史查询
│
├── data_pipeline/         # 数据管道工具
└── webapp/                # Web 应用界面
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | sse | 服务器模式：sse（云端）或 stdio（本地） |
| `--host` | 0.0.0.0 | 监听地址 |
| `--port` | 8000 | 监听端口 |
| `--reload` | false | 开发模式（热重载） |
| `--log-level` | info | 日志级别 |

## 云端部署

### Docker 部署

```bash
# 构建镜像
docker build -t db-mcp-server .

# 运行容器
docker run -d \
  --name db-mcp-server \
  -p 8000:8000 \
  -e DB_URL="mysql+pymysql://user:pass@host:3306/db" \
  -v $(pwd)/metadata:/app/metadata \
  db-mcp-server
```

### 客户端连接云端服务器

```json
{
  "mcpServers": {
    "db-server": {
      "url": "http://服务器公网IP:8000/sse"
    }
  }
}
```

## 启动检查清单

启动前确认：

- [ ] Python >= 3.11
- [ ] 依赖已安装（`uv sync` 或 `pip install -e .`）
- [ ] `.env` 文件已配置
- [ ] `DB_URL` 已正确设置（如需 SQL 功能）
- [ ] `metadata/` 目录存在元数据文件（如需表结构功能）
- [ ] LightRAG 服务已启动（如需知识图谱功能）

## 常见问题

### Q: 必须配置所有服务吗？

不需要。最小配置只需要 MySQL。其他服务根据需要的功能选择性启动：
- 只用 `execute_sql`：只需 MySQL
- 只用 `get_table_schema`：只需元数据文件
- 使用 `search_knowledge`：需要 LightRAG + Neo4j + Qdrant

### Q: 如何添加自定义工具？

1. 在 `tools/` 目录创建工具文件
2. 在 `server.py` 的 `list_tools()` 添加工具定义
3. 在 `call_tool()` 添加执行逻辑

### Q: 工具执行失败怎么办？

1. 检查 `.env` 配置是否正确
2. 查看日志：`tail -f logs/db_mcp_server.server.log`
3. 确认依赖服务是否启动

## 技术栈

- **MCP SDK**: mcp[cli] >= 1.25.0
- **Web 框架**: Starlette + Uvicorn
- **数据库**: SQLAlchemy + PyMySQL
- **SSE**: sse-starlette

## License

MIT License
