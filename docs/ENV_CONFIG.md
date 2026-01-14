# 环境配置说明

## 快速开始

1. **复制环境配置文件**
   ```bash
   cp env.example .env
   ```

2. **编辑 `.env` 文件，填入实际配置值**

## 必需配置项

### 🗄️ MySQL 数据库配置

```bash
# MySQL 连接字符串
DB_URL=mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
```

**示例:**
```bash
DB_URL=mysql+pymysql://root:123456@localhost:3306/singa_bi?charset=utf8mb4
```

### 🤖 LLM 配置

```bash
# 选择模型
LLM_MODEL=gpt-4

# OpenAI API Key
LLM_API_KEY=sk-your-api-key-here

# OpenAI API Base URL (可选，用于代理或私有部署)
LLM_BASE_URL=https://api.openai.com/v1
```

**注意**: 
- 如果使用 OpenAI 官方 API，`LLM_BASE_URL` 可以不配置（默认使用 `https://api.openai.com/v1`）
- 如果使用代理或其他兼容 OpenAI API 的服务（如 DeepSeek、Azure OpenAI 等），需要设置 `LLM_BASE_URL`

## 可选配置项

### 📊 Redash 配置

如果需要通过 Redash API 执行查询：

```bash
REDASH_URL=http://your-redash-server.com
REDASH_API_KEY=your_redash_api_key
```

### 🧠 LightRAG 配置

如果需要使用历史查询搜索功能：

```bash
LIGHTRAG_API_URL=http://localhost:9621
```

### 🗂️ Neo4j 配置

如果需要使用知识图谱功能：

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### 📦 Qdrant 配置

如果需要向量存储：

```bash
QDRANT_URL=http://localhost:6333
```

## 配置说明

### 各组件的作用

| 组件 | 是否必需 | 作用 |
|------|---------|------|
| MySQL | ✅ 必需 | 数据库查询的主要数据源 |
| LLM | ✅ 必需 | AI Agent 的核心推理能力 |
| Redash | ⭕ 可选 | 通过 Redash API 执行查询（带权限审计） |
| LightRAG | ⭕ 可选 | 搜索历史查询，提供参考 SQL |
| Neo4j | ⭕ 可选 | 知识图谱存储（用于 LightRAG） |
| Qdrant | ⭕ 可选 | 向量数据库（用于 LightRAG） |

### 最小配置

只需要配置 MySQL 和 LLM 即可运行基础功能：

```bash
# .env 文件最小配置
DB_URL=mysql+pymysql://root:password@localhost:3306/singa_bi?charset=utf8mb4
LLM_MODEL=gpt-4
LLM_API_KEY=sk-xxxxx
# LLM_BASE_URL=https://api.openai.com/v1  # 可选
```

### 完整配置

如果需要使用所有功能，建议配置所有组件：

1. 启动 Docker 服务（Neo4j + Qdrant）：
   ```bash
   docker-compose up -d
   ```

2. 配置完整的 `.env` 文件（参考 `env.example`）

3. 启动 MCP Server：
   ```bash
   python main.py
   ```

## 获取配置值的方法

### OpenAI API Key
1. 访问 https://platform.openai.com/api-keys
2. 点击 "Create new secret key"
3. 复制生成的 key（格式：`sk-proj-...`）

### Redash API Key
1. 登录 Redash
2. 点击右上角头像 → Settings
3. 在 API Key 部分点击 "Show" 或 "Generate"

### MySQL 连接字符串
- **格式**: `mysql+pymysql://用户名:密码@主机:端口/数据库?charset=utf8mb4`
- **本地**: `mysql+pymysql://root:123456@localhost:3306/mydb?charset=utf8mb4`
- **远程**: `mysql+pymysql://user:pass@192.168.1.100:3306/db?charset=utf8mb4`

## 常见问题

### Q1: 如何测试配置是否正确？

启动服务后访问健康检查端点：
```bash
curl http://localhost:8000/health
```

### Q2: 不配置 Redash 可以使用吗？

可以！默认使用 MySQL 直连方式。Redash 主要用于需要权限管理和审计的场景。

### Q3: LightRAG 是什么？必须配置吗？

LightRAG 用于搜索历史 SQL 查询，提供参考。不是必需的，但配置后可以提升查询质量。

### Q4: Docker 服务启动失败怎么办？

检查端口占用：
```bash
# 检查端口 7474, 7687, 6333, 6334 是否被占用
lsof -i :7474
lsof -i :7687
lsof -i :6333
```

### Q5: 如何使用代理访问 OpenAI？

设置 API Base URL：
```bash
LLM_BASE_URL=https://your-proxy.com/v1
```

### Q6: 如何使用其他 LLM 服务（如 DeepSeek、Azure OpenAI）？

只需配置相应的 Base URL 和 API Key：

**DeepSeek 示例：**
```bash
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/v1
```

**Azure OpenAI 示例：**
```bash
LLM_MODEL=gpt-4
LLM_API_KEY=your-azure-key
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
```

**本地 LLM 示例（如 Ollama、vLLM）：**
```bash
LLM_MODEL=llama3
LLM_API_KEY=dummy  # 某些本地服务不需要 key
LLM_BASE_URL=http://localhost:11434/v1
```

## 安全建议

⚠️ **重要**: 
- ✅ 将 `.env` 加入 `.gitignore`（已默认配置）
- ✅ 不要提交包含真实密钥的配置文件到 Git
- ✅ 定期更换 API Key
- ✅ 生产环境使用受限权限的数据库账号
