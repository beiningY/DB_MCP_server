# 日志配置文档

本项目使用统一的日志系统，提供规范的日志记录、轮转和管理功能。

## 功能特性

### 1. 统一日志配置
- 全局统一的日志格式和级别控制
- 支持控制台和文件双输出
- 自动创建日志目录
- 模块化日志管理（Agent、Executor、Knowledge、Server、Tools）

### 2. 日志轮转
支持两种轮转模式：
- **按大小轮转**：单个日志文件达到指定大小时自动切分
- **按时间轮转**：每天自动生成新的日志文件

### 3. 日志级别
- `debug`: 调试信息，包含详细的执行流程
- `info`: 一般信息，记录关键操作和状态
- `warning`: 警告信息，非致命错误
- `error`: 错误信息，包含异常堆栈
- `critical`: 严重错误，系统无法继续运行

### 4. 日志文件结构
\`\`\`
logs/
├── db_mcp_server.server.log        # 服务器主日志
├── db_mcp_server.server_error.log  # 服务器错误日志
├── db_mcp_server.agent.log         # Agent 模块日志
├── db_mcp_server.agent_error.log   # Agent 错误日志
├── db_mcp_server.executor.log      # Executor 模块日志
├── db_mcp_server.executor_error.log # Executor 错误日志
├── db_mcp_server.knowledge.log     # Knowledge 模块日志
└── db_mcp_server.knowledge_error.log # Knowledge 错误日志
\`\`\`

## 使用方法

### 1. 基本使用

在代码中导入并使用日志：

\`\`\`python
from logger_config import get_logger

# 获取默认 logger
logger = get_logger()

# 记录不同级别的日志
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
\`\`\`

### 2. 模块专用 Logger

项目为不同模块提供了专用的 logger：

\`\`\`python
# Agent 模块
from logger_config import get_agent_logger
logger = get_agent_logger()

# Executor 模块
from logger_config import get_executor_logger
logger = get_executor_logger()

# Knowledge 模块
from logger_config import get_knowledge_logger
logger = get_knowledge_logger()

# Server 模块
from logger_config import get_server_logger
logger = get_server_logger()

# Tools 模块
from logger_config import get_tools_logger
logger = get_tools_logger()
\`\`\`

### 3. 装饰器记录函数执行

使用装饰器自动记录函数执行时间和状态：

\`\`\`python
from logger_config import log_execution, log_async_execution

# 同步函数
@log_execution()
def my_function():
    # 函数逻辑
    pass

# 异步函数
@log_async_execution()
async def my_async_function():
    # 异步逻辑
    pass

# 指定 logger
@log_execution(logger=get_agent_logger())
def my_agent_function():
    pass
\`\`\`

## 配置方式

### 1. 环境变量配置

在 \`.env\` 文件中设置：

\`\`\`bash
# 日志级别（debug/info/warning/error/critical）
LOG_LEVEL=info
\`\`\`

### 2. 命令行参数配置

启动服务器时通过命令行参数配置：

\`\`\`bash
# 设置日志级别
python server.py --log-level debug

# 指定日志目录
python server.py --log-dir /path/to/logs

# 禁用文件日志（仅输出到控制台）
python server.py --no-file-log
\`\`\`

## 最佳实践

1. **合理选择日志级别**：开发环境使用 debug，生产环境使用 info
2. **包含上下文信息**：记录用户ID、查询参数等关键信息
3. **避免敏感信息**：不要记录密码、API密钥等
4. **异常日志使用 exc_info=True**：记录完整的异常堆栈

## 查看日志

\`\`\`bash
# 实时查看所有日志
tail -f logs/db_mcp_server.*.log

# 只看错误
tail -f logs/*_error.log

# 搜索关键词
grep "查询失败" logs/db_mcp_server.*.log
\`\`\`

完整文档请参考项目的 docs/LOGGING.md
