# Agent 工具模块

这个模块包含数据分析师 Agent 使用的核心工具，用于数据库查询、知识图谱搜索和表结构获取。

## 工具列表

### 1. execute_sql_query - SQL 执行工具

直接连接 MySQL 数据库执行 SQL 查询。

**功能特性：**
- ✅ 支持 SELECT 查询
- ✅ 自动添加 LIMIT 保护（默认 100 行）
- ✅ 安全检查：禁止 INSERT/UPDATE/DELETE 等修改操作
- ✅ 超时保护：30 秒超时
- ✅ 自动处理特殊类型（Decimal、datetime）

**参数：**
- `sql` (str, 必需): SQL 查询语句
- `database` (str, 可选): 数据库名称，默认 "singa_bi"
- `limit` (int, 可选): 最大返回行数，默认 100

**返回格式：**
```json
{
    "success": true,
    "data": [{"col1": "value1", "col2": 123}, ...],
    "columns": ["col1", "col2"],
    "row_count": 10,
    "execution_time": 45.67,
    "message": "查询成功，返回 10 行数据"
}
```

**使用示例：**
```python
from tools import execute_sql_query

# 基本查询
result = execute_sql_query.invoke({"sql": "SELECT * FROM users WHERE id = 1"})

# 指定返回行数
result = execute_sql_query.invoke({"sql": "SELECT COUNT(*) as cnt FROM orders", "limit": 1})

# 查询特定数据库
result = execute_sql_query.invoke({"sql": "SELECT * FROM products", "database": "shop_db"})
```

**注意：** 工具使用 LangChain 的 `@tool` 装饰器，需要通过 `.invoke()` 方法调用，传入参数字典。

**环境变量：**
```bash
DB_URL=mysql+pymysql://username:password@localhost:3306/singa_bi?charset=utf8mb4
```

---

### 2. search_knowledge_graph - 知识图谱搜索工具

通过 LightRAG 搜索历史 SQL 查询、表字段说明和业务逻辑。

**功能特性：**
- ✅ 自然语言查询
- ✅ 多种搜索模式（naive/local/global/hybrid）
- ✅ 可配置返回结果数量
- ✅ 支持业务逻辑查询

**参数：**
- `query` (str, 必需): 搜索查询（自然语言）
- `mode` (str, 可选): 搜索模式，可选值：
  - `"naive"`: 简单向量相似度搜索，不使用知识图谱
  - `"local"`: 关注特定实体及其直接关系
  - `"global"`: 分析知识图谱中更广泛的模式和关系
  - `"hybrid"`: 结合 local 和 global 方法
  - `"mix"`: 集成知识图谱检索和向量搜索（**推荐**，默认）
  - `"bypass"`: 直接 LLM 查询，不使用知识检索
- `top_k` (int, 可选): 返回结果数量，默认 5

**返回格式：**
```json
{
    "success": true,
    "results": "相关的历史查询和业务知识...",
    "mode": "hybrid",
    "top_k": 5,
    "message": "搜索成功"
}
```

**使用示例：**
```python
from tools import search_knowledge_graph

# 搜索业务逻辑
result = search_knowledge_graph.invoke({"query": "如何计算 NPL 率"})

# 搜索表的用途
result = search_knowledge_graph.invoke({"query": "temp_rc_model_daily 表的用途", "mode": "local"})

# 搜索历史 SQL
result = search_knowledge_graph.invoke({"query": "查询昨天新增用户的 SQL", "top_k": 3})

# 搜索字段含义
result = search_knowledge_graph.invoke({"query": "machine_status 字段的含义"})
```

**注意：** 工具使用 LangChain 的 `@tool` 装饰器，需要通过 `.invoke()` 方法调用，传入参数字典。

**环境变量：**
```bash
LIGHTRAG_API_URL=http://localhost:9621
LIGHTRAG_API_KEY=your_api_key  # 可选
```

**LightRAG API 说明：**

LightRAG 使用 POST `/query` 端点进行查询，支持以下模式：

- **local**: 关注特定实体及其直接关系，适合查询具体表或字段的详细信息
- **global**: 分析知识图谱中更广泛的模式和关系，适合理解整体架构
- **hybrid**: 结合 local 和 global 方法，提供全面的结果
- **naive**: 简单向量相似度搜索，不使用知识图谱，速度最快
- **mix**: 集成知识图谱检索和向量搜索，**推荐使用**
- **bypass**: 直接使用 LLM 查询，不进行知识检索

请求格式：
```json
{
    "query": "你的问题",
    "mode": "mix"
}
```

---

### 3. get_table_schema - 表结构查询工具

从元数据文件中获取数据库表的结构信息。

**功能特性：**
- ✅ 获取所有表列表
- ✅ 获取指定表的详细字段信息
- ✅ 支持模糊匹配和相似表推荐
- ✅ 可选包含字段枚举值和示例值

**参数：**
- `table_name` (str, 可选): 表名。如果为 None，返回所有表列表
- `database` (str, 可选): 数据库名称，默认 "singa_bi"
- `include_sample_values` (bool, 可选): 是否包含示例值和枚举值，默认 False

**返回格式（所有表列表）：**
```json
{
    "success": true,
    "data": {
        "tables": [
            {
                "table_name": "orders",
                "comment": "订单表",
                "domain": "交易",
                "column_count": 15
            }
        ],
        "total_count": 120
    },
    "message": "成功获取 120 个表的信息"
}
```

**返回格式（指定表）：**
```json
{
    "success": true,
    "data": {
        "table_name": "orders",
        "comment": "订单表",
        "domain": "交易",
        "columns": [
            {
                "column_name": "id",
                "data_type": "bigint",
                "is_nullable": "NO",
                "column_key": "PRI",
                "comment": "订单ID"
            },
            {
                "column_name": "status",
                "data_type": "int",
                "is_nullable": "NO",
                "column_key": "",
                "comment": "订单状态",
                "enum_values": {"1": "待支付", "2": "已支付"},
                "business_meaning": "订单的当前状态"
            }
        ]
    },
    "message": "成功获取表 'orders' 的结构信息，包含 2 个字段"
}
```

**使用示例：**
```python
from tools import get_table_schema

# 获取所有表列表
result = get_table_schema.invoke({})

# 获取指定表的结构
result = get_table_schema.invoke({"table_name": "temp_rc_model_daily"})

# 包含字段的示例值和枚举值
result = get_table_schema.invoke({"table_name": "users", "include_sample_values": True})
```

**注意：** 工具使用 LangChain 的 `@tool` 装饰器，需要通过 `.invoke()` 方法调用，传入参数字典。

**元数据文件：**
- `metadata/singa_bi_metadata.json`: 表结构元数据
- `metadata/online_dictionary.json`: 字段枚举值和业务含义（可选）

---

## 在 Agent 中使用

这些工具已经集成到数据分析师 Agent 中，Agent 会根据用户问题自动选择合适的工具。

### Agent 工作流程

```
用户问题
    ↓
[Planner] 制定执行计划
    ↓
[Agent Executor] 使用工具执行
    ├─ get_table_schema: 查询表结构
    ├─ search_knowledge_graph: 搜索历史查询
    └─ execute_sql_query: 执行 SQL
    ↓
[Replanner] 判断是否继续或结束
    ↓
返回结果
```

### 典型使用场景

#### 场景 1: 简单查询
```
用户: "查询 users 表有多少条记录"
Agent: 
1. get_table_schema("users") - 确认表存在
2. execute_sql_query("SELECT COUNT(*) FROM users")
3. 返回结果
```

#### 场景 2: 复杂业务查询
```
用户: "查询昨天的放款总金额"
Agent:
1. get_table_schema() - 获取所有表，找到放款相关的表
2. search_knowledge_graph("如何计算放款金额") - 参考历史查询
3. get_table_schema("cyc_Loan_summary_app") - 查看表结构
4. execute_sql_query("SELECT SUM(amount) FROM ...") - 执行查询
5. 返回结果
```

#### 场景 3: 表字段含义查询
```
用户: "machine_status 字段是什么含义？"
Agent:
1. search_knowledge_graph("machine_status 字段") - 搜索业务含义
2. get_table_schema("temp_rc_model_daily", include_sample_values=True) - 查看枚举值
3. 返回说明
```

---

## 配置要求

### 最小配置
```bash
# .env 文件
DB_URL=mysql+pymysql://user:pass@host:3306/singa_bi?charset=utf8mb4
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-api-key
```

### 完整配置
```bash
# 数据库
DB_URL=mysql+pymysql://user:pass@host:3306/singa_bi?charset=utf8mb4

# LLM
LLM_MODEL=gpt-4
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1

# LightRAG（可选）
LIGHTRAG_API_URL=http://localhost:9621
LIGHTRAG_API_KEY=your_lightrag_api_key
```

### 元数据文件
确保以下文件存在：
- `metadata/singa_bi_metadata.json` - 必需
- `metadata/online_dictionary.json` - 可选（用于字段枚举值）

---

## 开发和测试

### 单独测试工具
```python
# 测试 SQL 执行
from tools import execute_sql_query
result = execute_sql_query.invoke({"sql": "SELECT 1 as test"})
print(result)

# 测试知识图谱搜索
from tools import search_knowledge_graph
result = search_knowledge_graph.invoke({"query": "放款金额"})
print(result)

# 测试表结构查询
from tools import get_table_schema
result = get_table_schema.invoke({})
print(result)
```

**重要提示：** 所有工具都使用 LangChain 的 `@tool` 装饰器，必须通过 `.invoke(参数字典)` 方法调用，不能直接调用。

### 测试 Agent
```bash
cd /Users/sarah/工作/DB_MCP_server
python agent/data_analyst_agent.py
```

---

## 错误处理

所有工具都返回 JSON 格式，包含 `success` 字段：
- `success: true` - 执行成功
- `success: false` - 执行失败，查看 `message` 字段了解错误原因

### 常见错误

#### 1. 数据库连接失败
```json
{
    "success": false,
    "message": "数据库连接未配置，请设置 DB_URL 环境变量"
}
```
**解决方法：** 检查 `.env` 文件中的 `DB_URL` 配置

#### 2. LightRAG 服务不可用
```json
{
    "success": false,
    "message": "无法连接到 LightRAG 服务，请确认服务是否启动"
}
```
**解决方法：** 启动 LightRAG 服务或跳过知识图谱搜索

#### 3. 表不存在
```json
{
    "success": false,
    "message": "表 'xxx' 不存在。你可能想查找：table1, table2",
    "similar_tables": ["table1", "table2"]
}
```
**解决方法：** 使用推荐的相似表名

---

## 扩展开发

### 添加新工具

1. 创建新的工具文件：`tools/my_new_tool.py`
2. 使用 `@tool` 装饰器：
```python
from langchain_core.tools import tool

@tool
def my_new_tool(param: str) -> str:
    """工具描述
    
    Args:
        param: 参数说明
    
    Returns:
        返回值说明
    """
    # 实现逻辑
    return "结果"
```

3. 在 `tools/__init__.py` 中导出
4. 在 `agent/data_analyst_agent.py` 中添加到工具列表

### 修改工具行为

编辑对应的工具文件，修改实现逻辑即可。Agent 会自动使用更新后的工具。

---

## 最佳实践

1. **先查表结构** - 在执行 SQL 前，先用 `get_table_schema` 确认表和字段
2. **参考历史** - 使用 `search_knowledge_graph` 学习业务逻辑和 SQL 写法
3. **限制返回行数** - 使用 `limit` 参数避免返回过多数据
4. **错误重试** - 如果 SQL 执行失败，分析错误信息并重新查询表结构

---

## 相关文档

- [Agent 使用指南](../docs/DATA_ANALYST_AGENT.md)
- [环境配置](../docs/ENV_CONFIG.md)
- [API 文档](../docs/openapi.yaml)
