# 数据分析师 Agent 使用指南

## 概述

数据分析师 Agent 是一个基于 Plan-Execute-Replan 模式的智能数据分析助手，集成了多个知识模块和 SQL 执行引擎，能够理解自然语言问题并自动生成、执行 SQL 查询。

## 架构

```
DataAnalystAgent (Plan-Execute-Replan)
├── Knowledge Modules (知识模块)
│   ├── OnlineDictionaryModule    - 在线数据字典
│   ├── SingaBIMetadataModule     - BI 元数据
│   └── LightRAGClient            - 历史查询 RAG
├── Execution Tools (执行工具)
│   ├── MySQLExecutor             - MySQL 直连
│   └── RedashExecutor            - Redash API
└── 5 Core Tools (核心工具)
    ├── MetadataSearchTool         - 元数据搜索
    ├── HistoricalQuerySearchTool  - 历史查询搜索
    ├── SQLExecutorTool            - SQL 执行
    ├── QueryOptimizationTool      - 查询优化
    └── DataAnalysisTool           - 数据分析
```

## 核心能力

### 1. 自然语言转 SQL
将中文/英文问题自动转换为 SQL 查询。

**示例**：
- "查询昨天的放款总金额"
- "最近7天每天的新用户注册数量"
- "统计各个业务域的表数量"

### 2. 元数据搜索
搜索表结构、字段含义、业务域信息。

**示例**：
- "temp_rc_model_daily 表的 machine_status 字段是什么含义？"
- "有哪些表包含放款信息？"
- "collection 业务域下有哪些表？"

### 3. 历史查询参考
通过 LightRAG 搜索相似的历史 SQL 查询。

**示例**：
- "找一个计算 NPL 率的 SQL"
- "参考历史上的放款金额统计查询"

### 4. SQL 执行
支持 MySQL 直连和 Redash API 两种执行方式。

### 5. 查询优化
分析 SQL 性能并提供优化建议。

### 6. 数据分析
对查询结果生成统计分析和洞察。

## 配置

### 环境变量（推荐）

在项目根目录创建 `.env` 文件（可参考 `env.example`）:

```bash
# ============ 必需配置 ============
# MySQL 数据库
DB_URL=mysql+pymysql://user:password@host:3306/singa_bi?charset=utf8mb4

# LLM 配置
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-api-key-here
# LLM_BASE_URL=https://api.openai.com/v1  # 可选，用于代理或其他服务

# ============ 可选配置 ============
# Redash API（如需权限管理和审计）
REDASH_URL=https://your-redash.com
REDASH_API_KEY=your_redash_api_key

# LightRAG（如需历史查询参考）
LIGHTRAG_API_URL=http://localhost:9621

# Neo4j（如需知识图谱）
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Qdrant（如需向量检索）
QDRANT_URL=http://localhost:6333
```

详细配置说明请查看 [ENV_CONFIG.md](ENV_CONFIG.md)

### 最小配置

只需 MySQL 和 LLM 即可运行：

```bash
DB_URL=mysql+pymysql://root:123456@localhost:3306/singa_bi?charset=utf8mb4
LLM_MODEL=gpt-4
LLM_API_KEY=sk-xxxxx
```

## 使用方式

### 方式 1: 通过 MCP Server（推荐）

#### 1. 启动 MCP Server

```bash
python main.py --host 0.0.0.0 --port 8000
```

#### 2. 在 Cursor/Claude Desktop 中配置

编辑 MCP 配置文件（`~/.cursor/mcp.json` 或 Claude Desktop 配置）:

```json
{
  "mcpServers": {
    "db-server": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

#### 3. 使用 data_analyst 工具

在 Cursor AI 或 Claude Desktop 中直接提问：

```
使用 data_analyst 工具查询昨天的放款总金额
```

或通过 Python 客户端：

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            await session.initialize()
            
            # 调用 data_analyst 工具
            result = await session.call_tool(
                "data_analyst",
                {
                    "question": "查询昨天的放款总金额",
                    "database": "singa_bi",
                    "use_redash": False,
                    "max_iterations": 10
                }
            )
            
            print(result.content[0].text)

asyncio.run(main())
```

### 方式 2: 直接使用 Agent（Python 脚本）

适用于脚本自动化或深度集成场景：

```python
import asyncio
from agent import create_data_analyst_agent

async def main():
    # 创建 Agent（从环境变量读取配置）
    agent = create_data_analyst_agent()
    
    # 分析问题
    result = await agent.analyze(
        question="查询昨天的放款总金额",
        database="singa_bi",
        use_redash=False,
        max_iterations=10
    )
    
    print(result)

asyncio.run(main())
```

或手动指定配置：

```python
agent = create_data_analyst_agent(
    mysql_url="mysql+pymysql://user:pass@host:3306/singa_bi",
    redash_url="https://your-redash.com",
    redash_api_key="your_api_key",
    llm_model="gpt-4",
    llm_api_key="sk-...",
    llm_base_url="https://api.openai.com/v1",  # 可选
    lightrag_url="http://localhost:9621"  # 可选
)
```

## 测试

项目提供了完整的测试套件：

### 1. 运行知识模块测试

```bash
python tests/test_knowledge_modules.py
```

测试内容：
- ✓ 在线字典表搜索
- ✓ 在线字典字段搜索
- ✓ BI 元数据表搜索
- ✓ 业务域查询
- ✓ LightRAG 健康检查和搜索

### 2. 运行执行器测试

```bash
python tests/test_executors.py
```

测试内容：
- ✓ MySQL 连接测试
- ✓ MySQL 查询执行
- ✓ 查询限制 (LIMIT) 功能
- ✓ Redash API 连接测试
- ✓ Redash 查询执行

### 3. 运行 Agent 集成测试

```bash
# 需要先配置 .env 文件中的数据库和 LLM
python tests/test_data_analyst.py
```

测试场景：
1. 简单查询（表数量统计）
2. 元数据查询（字段含义）
3. 业务数据查询（放款记录）
4. 历史查询搜索（相似 SQL 参考）

### 4. 运行基础功能测试

```bash
python tests/test_basic.py
```

### 查看测试报告

所有测试都会输出详细的执行日志和结果，帮助诊断问题。

## 工作流程

1. **Planning（规划）**
   - 用户提出问题
   - Planner 分析问题并制定执行计划
   
2. **Execution（执行）**
   - ReAct Agent 逐步执行计划
   - 使用工具：搜索元数据、查找历史查询、执行 SQL
   
3. **Replanning（重规划）**
   - 根据执行结果判断是否需要继续
   - 如果 SQL 失败，重新规划并修正
   - 如果成功，返回最终结果

## 示例场景

### 场景 1: 简单查询

**问题**: "singa_bi 数据库中有多少个表？"

**流程**:
1. 规划：执行 information_schema 查询
2. 执行：生成并执行 SQL
3. 返回：表数量统计结果

### 场景 2: 元数据查询

**问题**: "temp_rc_model_daily 表的 machine_status 字段是什么含义？"

**流程**:
1. 规划：使用元数据搜索工具
2. 执行：search_metadata("temp_rc_model_daily.machine_status")
3. 返回：字段的业务含义和枚举值

### 场景 3: 复杂分析

**问题**: "对比最近7天和前7天的用户注册转化率"

**流程**:
1. 规划：
   - 步骤1：搜索用户表和字段
   - 步骤2：参考历史转化率查询
   - 步骤3：生成两个时间段的查询
   - 步骤4：执行并计算转化率
2. 执行：使用多个工具完成每个步骤
3. 重规划：如果某步失败，调整计划
4. 返回：对比分析结果

## 最佳实践

### 1. 明确问题描述
- ✅ "查询 cyc_Loan_summary_app 表中昨天的放款记录"
- ❌ "查询昨天的数据"（不明确哪个表）

### 2. 利用元数据搜索
对于不确定的表名或字段名，先搜索元数据：
- "先搜索包含放款信息的表，然后查询昨天的放款金额"

### 3. 参考历史查询
对于复杂的业务指标，参考历史查询：
- "参考历史上的 NPL 率计算方法，然后计算本月的 NPL 率"

### 4. 分步骤验证
对于复杂查询，建议分步骤进行：
- "先查询表结构，确认字段名，然后生成查询语句"

### 5. 指定执行方式
- 快速查询：使用 MySQL 直连（默认）
- 需要审计：使用 Redash API（设置 `use_redash=True`）

## 故障排查

### 问题 1: Agent 初始化失败

**可能原因**:
- 缺少环境变量
- 数据库连接失败
- LLM API 密钥无效

**解决方案**:
1. 检查 `.env` 文件配置
2. 测试数据库连接
3. 验证 LLM API 密钥

### 问题 2: SQL 执行失败

**可能原因**:
- 表名或字段名错误
- 权限不足
- 查询超时

**解决方案**:
1. 使用元数据搜索确认表名和字段名
2. 检查数据库用户权限
3. 优化查询或增加超时时间

### 问题 3: LightRAG 不可用

**表现**: 历史查询搜索功能无法使用

**解决方案**:
1. 检查 LightRAG 服务是否启动
2. 验证 LIGHTRAG_API_URL 配置
3. 测试健康检查端点

## 性能优化

### 1. 元数据缓存
元数据在启动时加载到内存，查询速度快。

### 2. SQL 限制
- 默认限制返回 10000 行
- 可以通过 `limit` 参数调整
- 查询超时默认 30 秒

### 3. 并发执行
Agent 支持异步执行，可以同时处理多个请求。

## 扩展开发

### 添加新的知识模块

```python
from knowledge.base import KnowledgeModule

class MyKnowledgeModule(KnowledgeModule):
    @property
    def name(self) -> str:
        return "my_module"
    
    @property
    def description(self) -> str:
        return "我的知识模块"
    
    def _initialize(self):
        # 初始化逻辑
        pass
    
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        # 搜索逻辑
        return {"results": []}
```

### 添加新的工具

```python
from tools.base import BaseTool

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "我的工具"
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            }
        }
    
    async def execute(self, arguments: dict) -> list:
        # 执行逻辑
        return [types.TextContent(type="text", text="结果")]
```

## 常见问题

### 基础配置

**Q: 支持哪些数据库？**

A: 目前支持 MySQL。可以通过实现新的 `SQLExecutor` 扩展支持其他数据库（如 PostgreSQL、ClickHouse 等）。

**Q: 支持哪些 LLM？**

A: 支持所有兼容 OpenAI API 的服务：
- OpenAI GPT-4, GPT-3.5, GPT-4-turbo
- DeepSeek
- Azure OpenAI
- 本地部署的 Ollama、vLLM 等

配置方法：设置 `LLM_BASE_URL` 指向对应的 API 端点。

**Q: 可以自定义提示词吗？**

A: 可以。修改 `agent/prompts.py` 文件中的以下提示词模板：
- `PLANNER_SYSTEM_PROMPT` - 规划器提示词
- `REPLANNER_SYSTEM_PROMPT` - 重规划器提示词
- `AGENT_EXECUTOR_SYSTEM_PROMPT` - 执行器系统提示词

### 功能使用

**Q: 不配置 Redash 可以使用吗？**

A: 可以！默认使用 MySQL 直连方式。Redash 主要用于需要权限管理和查询审计的场景。

**Q: LightRAG 是什么？必须配置吗？**

A: LightRAG 用于搜索历史 SQL 查询，提供相似查询参考。不是必需的，但配置后可以显著提升复杂查询的准确性。

**Q: 如何提高查询准确性？**

A: 
1. 确保元数据（表结构、字段注释）完整准确
2. 提供更多历史查询供 LightRAG 学习
3. 使用更强大的 LLM 模型（如 GPT-4）
4. 针对业务场景优化提示词

**Q: 支持流式输出吗？**

A: 当前版本不支持流式输出。计划在未来版本中添加此功能。

### 故障排查

**Q: Agent 初始化失败怎么办？**

A: 检查以下项：
1. `.env` 文件配置是否正确
2. 数据库连接字符串格式是否正确
3. LLM API Key 是否有效
4. 元数据文件是否存在于 `metadata/` 目录

**Q: SQL 执行失败怎么办？**

A: 常见原因和解决方案：
- **表名或字段名错误**: 使用元数据搜索确认正确的名称
- **权限不足**: 检查数据库用户权限
- **查询超时**: 优化查询或增加超时时间（修改 `timeout` 参数）
- **语法错误**: Agent 会自动修正，如果持续失败，检查元数据是否准确

**Q: LightRAG 连接失败怎么办？**

A: 
1. 检查 LightRAG 服务是否启动
2. 验证 `LIGHTRAG_API_URL` 配置是否正确
3. 测试健康检查：`curl http://localhost:9621/health`
4. 即使 LightRAG 不可用，Agent 仍可正常工作，只是无法使用历史查询参考功能

**Q: Docker 服务启动失败怎么办？**

A: 检查端口占用情况：
```bash
# 检查端口 7474, 7687, 6333, 6334 是否被占用
lsof -i :7474
lsof -i :7687
lsof -i :6333
```

如果端口被占用，可以修改 `docker-compose.yml` 中的端口映射。

## 贡献

欢迎提交 Issue 和 Pull Request！

### 开发指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 添加适当的注释和文档字符串
- 为新功能编写测试用例

## 相关文档

- [项目总结](PROJECT_SUMMARY.md) - 完整的项目架构和技术栈
- [环境配置](ENV_CONFIG.md) - 详细的配置说明
- [README](../README.md) - 项目概览和快速开始

## 许可证

MIT License
