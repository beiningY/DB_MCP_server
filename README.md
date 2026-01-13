# DB MCP Server

一个支持远程连接的 MCP (Model Context Protocol) 服务器框架，基于 Python 实现。

## 特性

- 🌐 **远程连接支持**: 通过 SSE (Server-Sent Events) 协议支持远程客户端连接
- 🔧 **可扩展工具系统**: 基于类的工具定义，易于扩展
- 📦 **资源管理**: 支持自定义资源的注册和访问
- 📝 **提示模板**: 支持预定义的提示模板
- 🔒 **CORS 支持**: 内置跨域资源共享支持
- 📊 **健康检查**: 提供服务健康状态端点

## 项目结构

```
DB_MCP_server/
├── server.py           # 核心服务器模块
├── main.py            # 入口文件
├── pyproject.toml     # 项目配置
├── tools/             # 工具模块
│   ├── __init__.py
│   ├── base.py        # 工具基类
│   └── db_tools.py    # 数据库工具示例
├── resources/         # 资源模块
│   ├── __init__.py
│   ├── base.py        # 资源基类
│   └── db_resources.py # 数据库资源示例
└── README.md
```

## 快速开始

### 安装依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 启动服务器

```bash
# 基本启动
python main.py

# 指定端口和地址
python main.py --host 0.0.0.0 --port 8000

# 开发模式 (热重载)
python main.py --reload

# 查看帮助
python main.py --help
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | 0.0.0.0 | 监听地址 |
| `--port` | 8000 | 监听端口 |
| `--reload` | false | 开启热重载 (开发模式) |
| `--log-level` | info | 日志级别 (debug/info/warning/error) |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务器信息 |
| `/health` | GET | 健康检查 |
| `/sse` | GET | SSE 连接端点 |
| `/messages/` | POST | MCP 消息处理 |

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

## 内置工具

| 工具名 | 描述 |
|--------|------|
| `ping` | 测试服务器连接 |
| `echo` | 回显输入消息 |
| `calculate` | 数学表达式计算 |

## 内置资源

| URI | 描述 |
|-----|------|
| `info://server/status` | 服务器运行状态 |
| `info://server/version` | 版本信息 |

## 技术栈

- **MCP SDK**: `mcp[cli]>=1.25.0`
- **Web 框架**: Starlette
- **ASGI 服务器**: Uvicorn
- **SSE 支持**: sse-starlette

## 开发

```bash
# 安装开发依赖
uv sync

# 运行测试
pytest

# 代码格式化
ruff format .

# 代码检查
ruff check .
```

## 数据库知识图谱

本项目集成了基于 LightRAG 的数据库表关系知识图谱功能，支持：

- 从 MySQL 数据库自动提取元数据
- 构建表关系知识图谱
- 使用自然语言查询数据库结构
- 可视化展示表关系

### 快速开始

#### 1. 配置环境

```bash
# 复制配置文件
cp env.example .env

# 编辑 .env 配置 MySQL、LLM 和 Neo4j 连接信息
```

#### 2. 导出数据库元数据

**方式一：使用 pymysql 直接连接数据库**

```bash
# 需要先安装依赖
pip install pymysql python-dotenv

# 导出元数据
python main_kg.py export --database singa_bi
```

**方式二：手动准备元数据 JSON 文件**

创建 `metadata/{database}_metadata.json` 文件，格式如下：

```json
{
  "database": "singa_bi",
  "owner": "数据部",
  "submitted_by": "张三",
  "submitted_at": "2026-01-07",
  "tables": [
    {
      "table_name": "users",
      "table_comment": "用户表",
      "business_domain": "user",
      "granularity": "per_user",
      "columns": [
        {
          "column_name": "id",
          "data_type": "bigint",
          "comment": "用户ID",
          "is_primary_key": true
        }
      ]
    }
  ]
}
```

#### 3. 构建知识图谱

```bash
# 安装 LightRAG 依赖
pip install lightrag-hku

# 构建知识图谱
python main_kg.py build metadata/singa_bi_metadata.json
```

#### 4. 查询知识图谱

```bash
# 交互式查询
python main_kg.py query --interactive

# 直接查询
python main_kg.py query -q "users 表有哪些字段？"
```

### 元数据格式说明

| 字段 | 说明 |
|------|------|
| `table_name` | 表名 |
| `table_comment` | 表注释 |
| `business_domain` | 业务域（如 user, order, collection） |
| `granularity` | 数据粒度（per_user, per_order, per_day 等） |
| `columns` | 字段列表 |
| `columns[].related_table` | 外键关联表 |
| `columns[].related_column` | 外键关联字段 |
| `columns[].is_pii` | 是否为 PII 敏感数据 |

### 支持的查询示例

- "users 表有哪些字段？"
- "哪些表与 sgo_orders 表有关联？"
- "催收业务域有哪些表？"
- "查找所有包含 user_id 的表"
- "请列出所有 PII 敏感字段"

### 项目结构

```
DB_MCP_server/
├── db_lightrag/              # 知识图谱模块
│   ├── config.py             # 配置管理
│   ├── metadata_exporter.py  # 元数据导出器
│   ├── kg_builder.py         # 知识图谱构建器
│   └── queries.py            # 智能查询接口
├── metadata/                 # 元数据文件目录
│   └── singa_bi_metadata.json
├── main_kg.py               # 知识图谱主入口
└── env.example              # 配置示例
```

## License

MIT License

