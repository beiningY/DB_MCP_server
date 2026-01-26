# DB MCP Server

一个基于 MCP (Model Context Protocol) 协议的智能数据分析服务器，集成了 AI Agent、知识图谱和多数据源支持。

## 核心特性

### 🤖 智能数据分析师 Agent
- **Plan-Execute-Replan 架构**: 智能规划和动态调整分析流程
- **自然语言转 SQL**: 理解中文/英文问题，自动生成并执行 SQL 查询
- **多知识源集成**: 在线字典、BI 元数据、LightRAG 历史查询
- **双执行引擎**: 支持 MySQL 直连（快速）和 Redash API（审计）
- **查询优化建议**: 分析 SQL 性能并提供优化方案
- **数据洞察分析**: 自动生成统计分析和业务洞察

### 🌐 远程连接支持
- **SSE (Server-Sent Events)**: 支持远程客户端连接
- **RESTful API**: 标准的 HTTP/JSON 接口
- **CORS 支持**: 跨域资源共享
- **健康检查**: 完善的服务监控端点

### 🔧 可扩展架构
- **模块化设计**: 知识模块、执行器、工具独立可扩展
- **资源管理**: 统一的资源注册和访问机制
- **工具注册**: 基于类的工具定义系统
- **提示模板**: 预定义的 Prompt 管理

## 项目结构

```
DB_MCP_server/
├── server.py                      # MCP 服务器核心
├── main.py                        # 服务入口
├── logger_config.py               # 统一日志配置
├── pyproject.toml                 # 项目配置和依赖
├── docker-compose.yml             # Neo4j + Qdrant 服务
├── env.example                    # 环境配置示例
│
├── agent/                         # 数据分析师 Agent
│   ├── data_analyst_agent.py      # Plan-Execute-Replan Agent
│   ├── prompts.py                 # Prompt 模板
│   └── plan_execute_replan_agent.py # agent抽象实现逻辑
│
├── knowledge/                     # 知识模块
│   ├── base.py                    # 知识模块基类
│   ├── online_dictionary.py       # 在线数据字典
│   ├── metadata.py                # BI 元数据
│   └── lightrag_client.py         # LightRAG 客户端（支持根据历史query查询表和字段以及业务逻辑）
│
├── executors/                     # SQL 执行器
│   ├── base.py                    # 执行器基类
│   ├── mysql_executor.py          # MySQL 直连
│   ├── redash_executor.py         # Redash API
│   └── mock_executor.py           # Mock 执行器
│
├── tools/                         # MCP 工具
│   ├── base.py                    # 工具基类
│   ├── db_tools.py                # 数据库工具
│   └── analyst_tools.py           # 分析师工具（5种）
│
├── resources/                     # MCP 资源
│   ├── base.py                    # 资源基类
│   ├── db_resources.py            # 数据库资源
│   └── metadata_resources.py      # 元数据资源
│
├── metadata/                      # 元数据文件
│   ├── online_dictionary.json     # 在线字典
│   ├── singa_bi_metadata.json     # BI 元数据
│   └── redash_queries.json        # Redash 查询
│
├── data_pipeline/                 # 数据管道
│   ├── 01_build_metadata.py       # 构建元数据
│   ├── 02_get_online_dic.py       # 获取在线字典
│   ├── 03_get_redash_query.py     # 获取 Redash 查询
│   └── 04_upload_redash_queries.py # 上传到 LightRAG
│
├── tests/                         # 测试
│   ├── test_knowledge_modules.py  # 知识模块测试
│   ├── test_executors.py          # 执行器测试
│   ├── test_data_analyst.py       # Agent 集成测试
│   └── test_basic.py              # 基础功能测试
│
└── docs/                          # 文档
    ├── PROJECT_SUMMARY.md         # 项目总结
    ├── DATA_ANALYST_AGENT.md      # Agent 使用指南
    ├── ENV_CONFIG.md              # 环境配置
    └── LOGGING.md                 # 日志配置说明
```

## 架构说明

本项目包含两个独立的服务器，可根据需求选择使用：

### MCP Server（端口 8000）
- 基于 MCP 协议的智能服务器
- 用于 AI Agent 工具调用（Cursor、Claude Desktop 等）
- 支持 SSE 连接
- 完整的 Agent 推理能力

### API Server（端口 8001）⭐ 新增
- 基于 FastAPI 的 HTTP REST API
- 专为前端 Web 应用设计
- 完整的 OpenAPI/Swagger 文档
- SSE 流式响应支持
- 符合标准的 RESTful 接口

**两个服务器可独立运行，也可同时运行。**

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 2. 配置环境

```bash
# 复制配置文件
cp env.example .env

# 编辑 .env，配置以下必需项：
# - DB_URL: MySQL 数据库连接
# - LLM_API_KEY: OpenAI API Key
# - LLM_MODEL: 模型名称（如 gpt-4）
```

**最小配置示例**:
```bash
DB_URL=mysql+pymysql://user:pass@host:3306/singa_bi?charset=utf8mb4
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-api-key
```

详细配置说明请参考 [docs/ENV_CONFIG.md](docs/ENV_CONFIG.md)

### 3. 启动服务（可选：Neo4j + Qdrant）

如需使用知识图谱功能，先启动 Docker 服务：

```bash
docker-compose up -d
```

### 4. 启动服务器

#### 方式 A：启动 MCP Server（用于 AI Agent 集成）

```bash
# 基本启动
python main.py

# 指定地址和端口
python main.py --host 0.0.0.0 --port 8000

# 开发模式（热重载）
python main.py --reload

# 查看所有选项
python main.py --help
```

#### 方式 B：启动 API Server（用于前端 Web 应用）⭐ 推荐

```bash
# 基本启动（默认端口 8001）
python start_api_server.py

# 开发模式（热重载）
python start_api_server.py --reload

# 生产模式（多进程）
python start_api_server.py --workers 4

# 自定义配置
python start_api_server.py --host 0.0.0.0 --port 8080 --log-level debug
```

启动后访问：
- **API 文档**: http://localhost:8001/docs
- **健康检查**: http://localhost:8001/health
- **OpenAPI 规范**: http://localhost:8001/openapi.json

#### 方式 C：同时运行两个服务器

```bash
# 终端1：启动 MCP Server
python main.py --port 8000

# 终端2：启动 API Server
python start_api_server.py --port 8001
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 0.0.0.0 | 监听地址 |
| `--port` | 8000 | 监听端口 |
| `--reload` | false | 开启热重载（开发模式）|
| `--log-level` | info | 日志级别（debug/info/warning/error/critical）|
| `--log-dir` | ./logs | 日志文件目录 |
| `--no-file-log` | false | 禁用文件日志，仅输出到控制台 |

### 日志配置

项目使用统一的日志系统，支持控制台和文件双输出：

```bash
# 设置日志级别为 debug（显示详细调试信息）
python main.py --log-level debug

# 指定自定义日志目录
python main.py --log-dir /var/log/db_mcp_server

# 仅输出到控制台，不写入文件（适合容器环境）
python main.py --no-file-log

# 通过环境变量设置日志级别
export LOG_LEVEL=debug
python main.py
```

**日志文件结构**：
```
logs/
├── db_mcp_server.server.log        # 服务器主日志
├── db_mcp_server.server_error.log  # 服务器错误日志
├── db_mcp_server.agent.log         # Agent 模块日志
├── db_mcp_server.executor.log      # Executor 模块日志
└── db_mcp_server.knowledge.log     # Knowledge 模块日志
```

更多日志配置详情请参考 [docs/LOGGING.md](docs/LOGGING.md)

### 验证安装

访问健康检查端点：
```bash
curl http://localhost:8000/health
```

应返回：
```json
{
  "status": "healthy",
  "server": "DB MCP Server",
  "version": "0.1.0"
}
```

## API 端点

### MCP Server 端点（端口 8000）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务器信息 |
| `/health` | GET | 健康检查 |
| `/sse` | GET | SSE 连接端点 |
| `/messages/` | POST | MCP 消息处理 |

### API Server 端点（端口 8001）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/connection/test` | POST | 测试数据库连接 |
| `/api/connection/save` | POST | 保存连接配置 |
| `/api/query/execute` | POST | 执行 SQL 查询 |
| `/api/metadata/schema` | GET | 获取数据库 Schema |
| `/api/metadata/description/generate` | POST | AI 生成字段描述 |
| `/api/chat/completion` | POST | AI 流式对话（SSE）|

详细 API 文档请参考：
- **在线文档**: http://localhost:8001/docs
- **OpenAPI 规范**: [docs/openapi.yaml](docs/openapi.yaml)
- **详细说明**: [docs/API_SERVER.md](docs/API_SERVER.md)

## 客户端连接

### Cursor/Claude Desktop 配置

在 `~/.cursor/mcp.json` 或 Claude Desktop 配置中添加:

```json
{
  "mcpServers": {
    "db-server": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Python 客户端示例

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print("可用工具:", [t.name for t in tools.tools])
            
            # 调用工具
            result = await session.call_tool("ping", {})
            print("Ping 结果:", result.content[0].text)

asyncio.run(main())
```

## 自定义工具

在 `tools/` 目录下创建新的工具:

```python
from tools.base import BaseTool
import mcp.types as types

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "我的自定义工具"
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数1"}
            },
            "required": ["param1"]
        }
    
    async def execute(self, arguments: dict) -> list[types.TextContent]:
        param1 = arguments.get("param1", "")
        return [types.TextContent(type="text", text=f"处理结果: {param1}")]
```

## 自定义资源

在 `resources/` 目录下创建新的资源:

```python
from resources.base import BaseResource

class MyCustomResource(BaseResource):
    @property
    def uri(self) -> str:
        return "custom://my/resource"
    
    @property
    def name(self) -> str:
        return "我的资源"
    
    @property
    def description(self) -> str:
        return "自定义资源描述"
    
    async def read(self) -> str:
        return "资源内容"
```

## 核心工具

### 数据分析师 Agent (`data_analyst`)

智能数据分析助手，支持自然语言查询、元数据搜索、SQL 执行等功能。

**使用示例**:
```python
# 调用 data_analyst 工具
result = await session.call_tool("data_analyst", {
    "question": "查询昨天的放款总金额",
    "database": "singa_bi",
    "use_redash": False,
    "max_iterations": 10
})
```

**支持的查询类型**:
- 元数据查询：`"temp_rc_model_daily 表的 machine_status 字段是什么含义？"`
- 简单查询：`"查询 singa_bi 数据库中有多少个表"`
- 业务查询：`"查询昨天的放款总金额"`
- 统计分析：`"最近7天每天的新用户注册数量"`
- 历史参考：`"找一个计算 NPL 率的历史查询"`

详细使用指南请参考 [docs/DATA_ANALYST_AGENT.md](docs/DATA_ANALYST_AGENT.md)

### 其他内置工具

| 工具名 | 描述 |
|--------|------|
| `ping` | 测试服务器连接 |
| `echo` | 回显输入消息 |
| `calculate` | 数学表达式计算 |

## 内置资源

### 系统资源

| URI | 描述 |
|-----|------|
| `info://server/status` | 服务器运行状态（JSON）|
| `info://server/version` | 版本信息 |

### 元数据资源

| URI | 描述 |
|-----|------|
| `metadata://online_dictionary` | 在线数据字典（表和字段的业务含义）|
| `metadata://singa_bi` | Singa BI 完整元数据（表结构、业务域、关系）|
| `metadata://summary` | 元数据统计摘要 |

**读取资源示例**:
```python
# 读取在线字典
content = await session.read_resource("metadata://online_dictionary")
```

## 技术栈

### 核心框架
- **MCP SDK**: `mcp[cli]>=1.25.0` - Model Context Protocol 协议实现
- **Web 框架**: Starlette - 轻量级 ASGI 框架
- **ASGI 服务器**: Uvicorn - 高性能异步服务器
- **SSE 支持**: sse-starlette - Server-Sent Events 支持

### AI Agent
- **Agent 框架**: LangChain + LangGraph - 智能 Agent 编排
- **LLM**: OpenAI GPT-4（兼容其他 OpenAI API）
- **工作流模式**: Plan-Execute-Replan

### 数据处理
- **数据库**: MySQL + SQLAlchemy - 关系型数据库
- **数据分析**: pandas - 数据处理和分析
- **HTTP 客户端**: httpx, requests - 异步和同步 HTTP 请求

### 知识存储（可选）
- **图数据库**: Neo4j - 知识图谱存储
- **向量数据库**: Qdrant - 向量检索
- **RAG 引擎**: LightRAG - 历史查询检索

## 测试

项目包含完整的测试套件：

```bash
# 测试知识模块
python tests/test_knowledge_modules.py

# 测试 SQL 执行器
python tests/test_executors.py

# 测试数据分析师 Agent
python tests/test_data_analyst.py

# 测试基础功能
python tests/test_basic.py
```

## 开发

```bash
# 安装开发依赖
uv sync

# 代码格式化（如果安装了 ruff）
ruff format .

# 代码检查
ruff check .

# 运行开发服务器（热重载）
python main.py --reload --log-level debug
```

## 数据管道

项目包含完整的数据管道工具，用于准备和维护元数据：

### 1. 构建元数据
```bash
# 从 Google Sheets 导出数据库元数据
python data_pipeline/01_build_metadata.py
```

### 2. 获取在线字典
```bash
# 从 Google Sheets 导出在线数据字典
python data_pipeline/02_get_online_dic.py
```

### 3. 获取 Redash 查询
```bash
# 从 Redash API 导出历史查询
python data_pipeline/03_get_redash_query.py
```

### 4. 上传到 LightRAG
```bash
# 将 Redash 查询上传到 LightRAG 用于 RAG 检索
python data_pipeline/04_upload_redash_queries.py
```

## 架构设计

### 数据分析师 Agent 工作流

```
用户问题
    ↓
┌─────────────┐
│  Planner    │ ← 分析问题，制定执行计划
└─────────────┘
    ↓
┌─────────────┐
│  Executor   │ ← ReAct Agent 执行步骤
│  (Tools)    │   - 搜索元数据
│             │   - 查找历史查询
│             │   - 执行 SQL
│             │   - 分析数据
└─────────────┘
    ↓
┌─────────────┐
│  Replanner  │ ← 判断是否继续或结束
└─────────────┘
    ↓
  最终答案
```

### 知识模块架构

```
┌─────────────────────────────────┐
│  OnlineDictionaryModule         │
│  - 表/字段业务含义              │
│  - 枚举值说明                   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  SingaBIMetadataModule          │
│  - 完整表结构                   │
│  - 业务域分类                   │
│  - 字段类型和关系               │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  LightRAGClient                 │
│  - 历史查询检索                 │
│  - 相似 SQL 推荐                │
└─────────────────────────────────┘
```

### SQL 执行引擎

```
┌─────────────────────────────────┐
│  MySQLExecutor                  │
│  - 直连 MySQL 数据库            │
│  - 快速查询                     │
│  - 连接池管理                   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  RedashExecutor                 │
│  - 通过 Redash API 执行         │
│  - 权限管理                     │
│  - 查询审计                     │
└─────────────────────────────────┘
```

## 文档

- [项目总结](docs/PROJECT_SUMMARY.md) - 项目架构和技术栈详解
- [API Server 文档](docs/API_SERVER.md) - FastAPI 服务器完整文档 ⭐ 新增
- [OpenAPI 规范](docs/openapi.yaml) - 接口文档定义
- [Agent 使用指南](docs/DATA_ANALYST_AGENT.md) - 数据分析师 Agent 完整文档
- [环境配置](docs/ENV_CONFIG.md) - 详细的环境配置说明
- [日志配置](docs/LOGGING.md) - 日志系统配置和使用指南

## 常见问题

### Q: 必须配置所有组件吗？
A: 不需要。最小配置只需要 MySQL 和 LLM API。其他组件（Redash、LightRAG、Neo4j）都是可选的。

### Q: 支持哪些 LLM？
A: 支持所有兼容 OpenAI API 的服务，包括：
- OpenAI GPT-4/GPT-3.5
- DeepSeek
- Azure OpenAI
- 本地部署的 Ollama/vLLM

### Q: 如何添加自定义工具？
A: 继承 `BaseTool` 类并实现必要方法，然后在 `server.py` 中注册。详见 [开发文档](docs/DATA_ANALYST_AGENT.md#扩展开发)。

### Q: Agent 执行失败怎么办？
A: 检查以下项：
1. 数据库连接是否正常
2. LLM API Key 是否有效
3. 元数据文件是否存在
4. 查看日志中的详细错误信息

### Q: 支持哪些数据库？
A: 目前支持 MySQL。可以通过实现新的 Executor 扩展支持其他数据库。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

感谢以下开源项目：
- [LangChain](https://github.com/langchain-ai/langchain) & [LangGraph](https://github.com/langchain-ai/langgraph) - AI Agent 框架
- [MCP Protocol](https://github.com/modelcontextprotocol) - Model Context Protocol
- [LightRAG](https://github.com/HKUDS/LightRAG) - RAG 检索引擎
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL 工具包
- [Pandas](https://pandas.pydata.org/) - 数据分析库

## License

MIT License

