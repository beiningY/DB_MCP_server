# DB MCP Server

> 基于 MCP (Model Context Protocol) 协议的数据分析服务器
> 通过自然语言查询和分析数据库，集成 SQL 安全验证、连接池和统一错误处理

[![MCP](https://img.shields.io/badge/MCP-v1.25.0-blue)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.10+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 核心特性

- **MCP 协议支持**：兼容 Cursor、Claude Desktop 等 AI 客户端
- **自然语言交互**：只需一个 `data_agent` 工具，通过对话完成所有操作
- **URL 参数配置**：客户端直接在 URL 中传入数据库配置
- **SQL 安全验证**：严格检测 SQL 注入和危险语句
- **连接池管理**：自动复用数据库连接，提高性能
- **实时表结构查询**：从 `information_schema` 实时获取表结构
- **知识图谱集成**：支持搜索历史 SQL 和业务逻辑（可选）

---

## 快速开始

### 1. 安装依赖

```bash
cd DB_MCP_server

# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# ========== LLM 配置（必需） ==========
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1

# ========== 服务器配置（可选） ==========
MCP_PORT=8000
MCP_HOST=0.0.0.0

# ========== 日志配置（可选） ==========
LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_JSON=false        # 生产环境设为 true

# ========== 连接池配置（可选） ==========
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# ========== LightRAG 知识图谱（可选） ==========
LIGHTRAG_API_URL=http://localhost:9621
```

### 3. 启动服务器

```bash
# 方式1：直接运行
python main.py

# 方式2：使用 uv
uv run python main.py

# 方式3：指定端口
MCP_PORT=8080 python main.py
```

启动成功后会显示：

```
==================================================
DB Analysis MCP Server (v2.1)
==================================================
🌐 地址: http://0.0.0.0:8000
📡 SSE 端点: http://0.0.0.0:8000/sse
📡 HTTP 端点: http://0.0.0.0:8000/mcp
❤️  健康检查: http://0.0.0.0:8000/health
🔧 支持动态数据库连接
==================================================
```

### 4. 验证服务

```bash
curl http://localhost:8000/health
```

预期返回：

```json
{
  "status": "healthy",
  "service": "DB Analysis MCP Server",
  "version": "2.1.0",
  "features": ["dynamic_database_connection", "real_time_schema_query", "sql_execution", "knowledge_graph_search"]
}
```

---

## 客户端配置

### Cursor 配置

编辑 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "my_database": {
      "url": "http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb"
    },
    "prod_db": {
      "url": "http://localhost:8000/sse?host=192.168.1.100&port=3306&username=admin&password=pass123&database=production"
    }
  }
}
```

### Claude Desktop 配置

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "我的数据库": {
      "url": "http://localhost:8000/sse?host=localhost&port=3306&username=root&password=&database=mydb"
    }
  }
}
```

### URL 参数说明

| 参数 | 说明 | 默认值 | 必需 |
|------|------|--------|------|
| `host` | 数据库主机地址 | 无 | 是 |
| `port` | 数据库端口 | 3306 | 否 |
| `username` | 用户名 | root | 否 |
| `password` | 密码 | 空 | 否 |
| `database` | 数据库名 | information_schema | 否 |
| `session` | 预定义配置名 | 无 | 否 |

### 使用预定义配置

在 `.env` 中配置：

```bash
DB_MCP_CONFIGS={"prod":{"host":"192.168.1.100","port":3306,"username":"admin","password":"pass123","database":"production"}}
```

客户端配置：

```json
{
  "mcpServers": {
    "prod_db": {
      "url": "http://localhost:8000/sse?session=prod"
    }
  }
}
```

---

## 使用方式

配置完成后，在 Claude/Cursor 中直接通过自然语言提问：

```
查询 users 表有多少条记录
显示 orders 表的结构
最近7天的订单数量趋势
还款率是怎么计算的
有哪些用户相关的表
```

Agent 会自动：
1. 理解你的问题
2. 选择合适的工具（查询表结构、执行 SQL、搜索知识图谱）
3. 使用配置的数据库连接
4. 返回整理好的结果

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              客户端 (Cursor / Claude)                        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │ MCP Protocol (SSE/HTTP)
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DB MCP Server                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  DatabaseConfigMiddleware                                           │   │
│  │  - 从 URL 参数提取数据库配置                                         │   │
│  │  - 支持预定义配置                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                       │                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  data_agent (MCP Tool)                                             │   │
│  │  - 自然语言接口                                                     │   │
│  │  - 调用 LangChain Agent                                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                       │                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  LangChain Agent                                                   │   │
│  │  - 理解用户意图                                                     │   │
│  │  - 选择合适的工具                                                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                       │                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  内部工具 (LangChain Tools)                                        │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │   │
│  │  │ execute_sql_    │  │ get_table_       │  │ search_knowledge_  │  │   │
│  │  │ query           │  │ schema           │  │ graph             │  │   │
│  │  │                 │  │                  │  │                    │  │   │
│  │  │ - SQL安全验证   │  │ - 实时查询表结构  │  │ - 搜索历史SQL     │  │   │
│  │  │ - 连接池管理    │  │ - 模糊匹配       │  │ - 业务逻辑问答    │  │   │
│  │  │ - 统一错误处理  │  │ - 索引信息       │  │                    │  │   │
│  │  └─────────────────┘  └──────────────────┘  └────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MySQL 数据库                                      │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │ 用户数据库        │  │ information_     │  │ LightRAG 服务          │  │
│  │                  │  │ schema           │  │ (可选)                 │  │
│  │ - 业务表         │  │                  │  │                        │  │
│  │ - 数据查询       │  │ - 表结构元数据   │  │ - 历史SQL              │  │
│  │                  │  │ - 字段信息       │  │ - 业务逻辑             │  │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 安全特性

| 特性 | 说明 |
|------|------|
| SQL 注入防护 | 检测危险关键字、注入模式、结构验证 |
| 仅允许 SELECT | 拒绝 INSERT/UPDATE/DELETE/DROP 等 |
| 查询限制 | 默认最多 100 行，最多 10000 行 |
| 超时保护 | 查询超时 30 秒 |
| 连接池 | 防止连接泄漏 |

### 错误码体系

| 错误码 | 说明 |
|--------|------|
| 1xxx | 通用错误 |
| 2xxx | 认证错误 |
| 3xxx | 数据库错误 |
| 4xxx | SQL 安全错误 |
| 5xxx | 配置错误 |
| 6xxx | Agent 错误 |

---

## 项目结构

```
DB_MCP_server/
├── main.py                     # 启动入口
├── pyproject.toml              # 项目依赖
├── .env                        # 环境变量
│
├── db_mcp/                     # MCP 服务器核心
│   ├── __init__.py            # 模块导出
│   ├── server.py              # FastMCP 服务器 + 中间件
│   ├── tool.py                # MCP 工具注册
│   ├── sql_validator.py       # SQL 安全验证
│   ├── connection_pool.py     # 连接池管理
│   ├── errors.py              # 统一错误处理
│   └── logger.py              # 日志配置
│
├── agent/                      # AI Agent
│   └── data_simple_agent.py   # 数据分析 Agent
│
├── tools/                      # Agent 内部工具
│   ├── __init__.py
│   ├── execute_sql_tool.py    # SQL 执行工具
│   ├── get_table_schema_tool.py # 表结构查询工具
│   └── search_knowledge_tool.py  # 知识图谱搜索
│
└── webapp/                     # Web 界面（可选）
    └── app.py                 # FastAPI 应用
```

---

## 工具说明

### MCP 工具（客户端可见）

| 工具名 | 功能 |
|--------|------|
| `data_agent` | 通过自然语言查询和分析数据库 |

### Agent 内部工具（Function Call）

| 工具名 | 功能 | 安全特性 |
|--------|------|----------|
| `execute_sql_query` | 执行 SQL 查询 | SQL 验证、连接池、超时保护 |
| `get_table_schema` | 获取表结构 | 连接池、模糊匹配 |
| `search_knowledge_graph` | 搜索知识图谱 | 超时保护 |

---

## 故障排查

### 问题1：连接失败

```bash
# 检查服务器是否启动
curl http://localhost:8000/health

# 检查端口是否被占用
lsof -i :8000
```

### 问题2：数据库连接失败

检查客户端 URL 参数是否正确配置：
```
?host=xxx&port=xxx&username=xxx&password=xxx&database=xxx
```

### 问题3：Agent 无响应

检查 LLM 配置：
```bash
# 确认环境变量已设置
echo $LLM_API_KEY
```

### 问题4：SQL 被拒绝

检查是否：
- SQL 以 SELECT 开头
- 不包含危险关键字（DROP、DELETE 等）
- 不包含注入模式（注释、分号注入等）

---

## 技术栈

| 组件 | 技术 |
|------|------|
| MCP SDK | mcp[cli] >= 1.25.0 |
| Web 框架 | Starlette + Uvicorn |
| 数据库 | SQLAlchemy + PyMySQL |
| LLM | LangChain + OpenAI |
| 知识图谱 | LightRAG (可选) |

---

## License

MIT License

---

## 更新日志

### v2.1.0 (2025-01-XX)

- 新增 SQL 安全验证器
- 新增数据库连接池管理
- 新增统一错误处理和日志
- 新增错误码体系
- 优化架构设计

### v2.0.0

- 初始版本
- 支持 MCP 协议
- 支持 URL 参数配置
- 集成 LangChain Agent
