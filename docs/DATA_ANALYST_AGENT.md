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

### 环境变量

在 `.env` 文件中配置以下变量：

```bash
# 数据库配置
DB_URL=mysql+pymysql://user:password@host:port/singa_bi

# Redash 配置（可选）
REDASH_URL=https://your-redash.com
REDASH_API_KEY=your_api_key

# LLM 配置
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4

# LightRAG 配置（可选）
LIGHTRAG_API_URL=http://localhost:9621
LIGHTRAG_API_KEY=  # 如果需要认证
```

## 使用方式

### 方式 1: 通过 MCP Server

启动 MCP Server：

```bash
python server.py --host 0.0.0.0 --port 8000
```

调用 `data_analyst` 工具：

```python
import httpx

response = httpx.post(
    "http://localhost:8000/messages/",
    json={
        "method": "tools/call",
        "params": {
            "name": "data_analyst",
            "arguments": {
                "question": "查询昨天的放款总金额",
                "database": "singa_bi",
                "use_redash": False
            }
        }
    }
)

print(response.json())
```

### 方式 2: 直接使用 Agent

```python
import asyncio
from agent import create_data_analyst_agent

async def main():
    # 创建 Agent
    agent = create_data_analyst_agent(
        mysql_url="mysql+pymysql://user:pass@host:port/singa_bi",
        llm_model="gpt-4",
        llm_api_key="sk-..."
    )
    
    # 分析问题
    result = await agent.analyze(
        question="查询昨天的放款总金额",
        database="singa_bi",
        max_iterations=10
    )
    
    print(result)

asyncio.run(main())
```

## 测试

### 运行知识模块测试

```bash
python tests/test_knowledge_modules.py
```

### 运行执行器测试

```bash
python tests/test_executors.py
```

### 运行 Agent 集成测试

```bash
python tests/test_data_analyst.py
```

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

**Q: 支持哪些数据库？**
A: 目前支持 MySQL。可以通过实现新的 Executor 支持其他数据库。

**Q: 可以自定义提示词吗？**
A: 可以。修改 `agent/prompts.py` 文件中的提示词模板。

**Q: 如何提高查询准确性？**
A: 
1. 确保元数据完整准确
2. 提供更多历史查询供 LightRAG 学习
3. 使用更强大的 LLM 模型

**Q: 支持流式输出吗？**
A: 当前版本不支持。计划在未来版本中添加。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
