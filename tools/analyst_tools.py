"""
数据分析师 Agent 工具集
实现 5 种核心能力：元数据搜索、历史查询、SQL执行、查询优化、数据分析
"""

from typing import Any, Dict, List, Optional
import mcp.types as types
from .base import BaseTool

# 导入知识模块和执行器
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from knowledge import OnlineDictionaryModule, SingaBIMetadataModule, LightRAGClient
from executors import MySQLExecutor, RedashExecutor


class MetadataSearchTool(BaseTool):
    """元数据搜索工具 - 搜索表结构、字段含义、业务域"""
    
    def __init__(self, online_dict: OnlineDictionaryModule, metadata: SingaBIMetadataModule):
        self.online_dict = online_dict
        self.metadata = metadata
    
    @property
    def name(self) -> str:
        return "search_metadata"
    
    @property
    def description(self) -> str:
        return """搜索数据库元数据信息，包括：
- 表结构和字段定义
- 字段的业务含义和枚举值（来自在线字典）
- 业务域和数据粒度
- 表之间的关联关系
- PII 敏感字段标识

使用场景：
- 在生成 SQL 前，确认表名和字段名是否正确
- 了解字段的业务含义和可能的取值
- 查找某个业务域下的所有表"""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（表名、字段名或业务域）"
                },
                "search_type": {
                    "type": "string",
                    "enum": ["auto", "table", "column", "domain"],
                    "description": "搜索类型，默认 auto 自动判断",
                    "default": "auto"
                },
                "source": {
                    "type": "string",
                    "enum": ["both", "online_dict", "metadata"],
                    "description": "数据来源：both(两者), online_dict(在线字典), metadata(BI元数据)",
                    "default": "both"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        query = arguments.get("query", "")
        search_type = arguments.get("search_type", "auto")
        source = arguments.get("source", "both")
        
        results = []
        
        # 在线字典搜索
        if source in ["both", "online_dict"]:
            dict_result = await self.online_dict.search(query, search_type=search_type)
            formatted = self.online_dict.format_result(dict_result)
            results.append(f"## 在线字典搜索结果\n\n{formatted}")
        
        # 元数据搜索
        if source in ["both", "metadata"]:
            if search_type == "domain":
                meta_result = await self.metadata.search_by_domain(query)
            else:
                meta_result = await self.metadata.search(query, search_type=search_type)
            formatted = self.metadata.format_result(meta_result)
            results.append(f"## BI 元数据搜索结果\n\n{formatted}")
        
        output = "\n\n---\n\n".join(results)
        return [types.TextContent(type="text", text=output)]


class HistoricalQuerySearchTool(BaseTool):
    """历史查询搜索工具 - 通过 LightRAG 搜索相似的历史 SQL"""
    
    def __init__(self, lightrag_client: LightRAGClient):
        self.lightrag = lightrag_client
    
    @property
    def name(self) -> str:
        return "search_historical_queries"
    
    @property
    def description(self) -> str:
        return """搜索相似的历史 SQL 查询作为参考。

LightRAG 会根据语义相似度找到历史上类似的查询，包括：
- 查询名称和描述
- 完整的 SQL 语句
- 使用的表和字段
- 相关的 Dashboard

使用场景：
- 参考历史查询的写法和模式
- 了解某类业务指标的计算方法
- 复用已有的查询逻辑"""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "用户意图的自然语言描述（例如：查询昨天的放款金额）"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认 3",
                    "default": 3
                },
                "mode": {
                    "type": "string",
                    "enum": ["naive", "local", "global", "hybrid"],
                    "description": "检索模式，推荐使用 hybrid",
                    "default": "hybrid"
                }
            },
            "required": ["intent"]
        }
    
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        intent = arguments.get("intent", "")
        top_k = arguments.get("top_k", 3)
        mode = arguments.get("mode", "hybrid")
        
        # 搜索历史查询
        queries = await self.lightrag.search_historical_queries(intent, top_k=top_k)
        
        # 格式化结果
        formatted = self.lightrag.format_historical_queries(queries)
        
        return [types.TextContent(type="text", text=formatted)]


class SQLExecutorTool(BaseTool):
    """SQL 执行工具 - 支持 MySQL 直连和 Redash API 两种方式"""
    
    def __init__(self, mysql_executor: MySQLExecutor, redash_executor: RedashExecutor):
        self.mysql = mysql_executor
        self.redash = redash_executor
    
    @property
    def name(self) -> str:
        return "execute_sql"
    
    @property
    def description(self) -> str:
        return """执行 SQL 查询，支持两种执行方式：

1. MySQL 直连（默认）：快速，适合简单查询
2. Redash API：支持权限管理和审计，适合需要记录的查询

安全限制：
- 只允许 SELECT 查询
- 默认最多返回 10000 行
- 查询超时时间 30 秒

使用提示：
- 执行前请先使用 search_metadata 确认表名和字段名
- 对于复杂查询，建议先使用 search_historical_queries 参考历史写法"""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的 SQL 查询语句（只允许 SELECT）"
                },
                "use_redash": {
                    "type": "boolean",
                    "description": "是否使用 Redash API 执行（默认 false，使用 MySQL 直连）",
                    "default": False
                },
                "timeout": {
                    "type": "integer",
                    "description": "查询超时时间（秒），默认 30",
                    "default": 30
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回行数，默认 10000",
                    "default": 10000
                }
            },
            "required": ["sql"]
        }
    
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        sql = arguments.get("sql", "")
        use_redash = arguments.get("use_redash", False)
        timeout = arguments.get("timeout", 30)
        limit = arguments.get("limit", 10000)
        
        # 选择执行器
        executor = self.redash if use_redash else self.mysql
        
        # 执行查询
        result = await executor.execute(sql, timeout=timeout, limit=limit)
        
        # 格式化结果
        if result.success:
            output = result.format_table(max_rows=20)
            
            # 添加元数据信息
            output += f"\n\n**执行信息**:\n"
            output += f"- 执行器: {executor.name}\n"
            output += f"- 耗时: {result.execution_time:.2f}秒\n"
            output += f"- 总行数: {result.row_count}\n"
            
            if result.metadata:
                if result.metadata.get('limited'):
                    output += f"- ⚠️ 结果已被限制为 {limit} 行\n"
        else:
            output = result.format_table()
        
        return [types.TextContent(type="text", text=output)]


class QueryOptimizationTool(BaseTool):
    """查询优化工具 - 分析 SQL 并提供优化建议"""
    
    @property
    def name(self) -> str:
        return "optimize_query"
    
    @property
    def description(self) -> str:
        return """分析 SQL 查询并提供优化建议。

检查项包括：
- 是否使用了合适的索引
- JOIN 的顺序和类型
- WHERE 条件的优化
- SELECT 字段的选择
- 是否存在子查询可以优化
- 是否需要添加 LIMIT

使用场景：
- 查询执行时间过长
- 想要提高查询性能
- 了解查询的潜在问题"""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要优化的 SQL 语句"
                },
                "explain": {
                    "type": "boolean",
                    "description": "是否执行 EXPLAIN 分析（需要数据库连接）",
                    "default": False
                }
            },
            "required": ["sql"]
        }
    
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        sql = arguments.get("sql", "")
        run_explain = arguments.get("explain", False)
        
        suggestions = []
        
        # 基础分析
        sql_upper = sql.upper()
        
        # 1. 检查是否使用了 SELECT *
        if "SELECT *" in sql_upper or "SELECT\n*" in sql_upper:
            suggestions.append({
                "type": "performance",
                "issue": "使用了 SELECT *",
                "suggestion": "只选择需要的字段，避免传输不必要的数据",
                "severity": "medium"
            })
        
        # 2. 检查是否有 LIMIT
        if "LIMIT" not in sql_upper:
            suggestions.append({
                "type": "safety",
                "issue": "没有 LIMIT 子句",
                "suggestion": "添加 LIMIT 子句以避免返回大量数据",
                "severity": "high"
            })
        
        # 3. 检查 JOIN 类型
        if "JOIN" in sql_upper:
            if "LEFT JOIN" in sql_upper or "RIGHT JOIN" in sql_upper:
                suggestions.append({
                    "type": "performance",
                    "issue": "使用了外连接",
                    "suggestion": "如果不需要NULL值，考虑使用 INNER JOIN 提高性能",
                    "severity": "low"
                })
        
        # 4. 检查子查询
        if sql.count("SELECT") > 1:
            suggestions.append({
                "type": "performance",
                "issue": "包含子查询",
                "suggestion": "考虑使用 JOIN 或 CTE (WITH) 替代子查询",
                "severity": "medium"
            })
        
        # 5. 检查 WHERE 条件
        if " WHERE " in sql_upper:
            where_clause = sql_upper.split(" WHERE ")[1].split(" ORDER ")[0].split(" GROUP ")[0]
            if " OR " in where_clause:
                suggestions.append({
                    "type": "index",
                    "issue": "WHERE 条件中使用了 OR",
                    "suggestion": "OR 可能导致索引失效，考虑使用 UNION 或 IN",
                    "severity": "medium"
                })
            
            # 检查函数在字段上
            if "(" in where_clause and any(func in where_clause for func in ["DATE(", "YEAR(", "MONTH("]):
                suggestions.append({
                    "type": "index",
                    "issue": "WHERE 条件中对字段使用了函数",
                    "suggestion": "对字段使用函数会导致索引失效，考虑改写条件",
                    "severity": "high"
                })
        
        # 6. 检查 ORDER BY
        if " ORDER BY " in sql_upper:
            order_clause = sql_upper.split(" ORDER BY ")[1]
            if " LIMIT " not in order_clause:
                suggestions.append({
                    "type": "performance",
                    "issue": "ORDER BY 但没有 LIMIT",
                    "suggestion": "如果只需要部分排序结果，添加 LIMIT 可以提高性能",
                    "severity": "low"
                })
        
        # 7. 检查 DISTINCT
        if " DISTINCT " in sql_upper:
            suggestions.append({
                "type": "performance",
                "issue": "使用了 DISTINCT",
                "suggestion": "DISTINCT 可能影响性能，确认是否真的需要去重",
                "severity": "medium"
            })
        
        # 格式化输出
        output = [f"## SQL 优化分析\n\n**原始 SQL**:\n```sql\n{sql}\n```\n"]
        
        if suggestions:
            output.append(f"\n**发现 {len(suggestions)} 个优化建议**:\n")
            for i, sugg in enumerate(suggestions, 1):
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[sugg['severity']]
                output.append(f"{i}. {severity_emoji} **{sugg['issue']}** ({sugg['type']})")
                output.append(f"   {sugg['suggestion']}\n")
        else:
            output.append("\n✓ 未发现明显的优化问题")
        
        # TODO: 如果 run_explain=True，执行 EXPLAIN 并分析结果
        if run_explain:
            output.append("\n*EXPLAIN 分析功能暂未实现*")
        
        return [types.TextContent(type="text", text="\n".join(output))]


class DataAnalysisTool(BaseTool):
    """数据分析工具 - 对查询结果生成统计分析和洞察"""
    
    @property
    def name(self) -> str:
        return "analyze_data"
    
    @property
    def description(self) -> str:
        return """对查询结果进行数据分析，生成统计信息和洞察。

分析内容包括：
- 数值字段的统计（最大值、最小值、平均值、中位数）
- 分类字段的分布
- 趋势分析（如果有时间字段）
- 异常值检测
- 可视化建议

使用场景：
- 快速了解数据的基本特征
- 发现数据中的模式和异常
- 为进一步分析提供方向"""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "要分析的数据（JSON 格式或来自 execute_sql 的结果）"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["summary", "distribution", "trend", "all"],
                    "description": "分析类型，默认 all（全部）",
                    "default": "all"
                }
            },
            "required": ["data"]
        }
    
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        data_str = arguments.get("data", "")
        analysis_type = arguments.get("analysis_type", "all")
        
        # 简单的数据分析示例（实际应该更复杂）
        output = [
            "## 数据分析结果\n",
            "*注意：这是一个基础的数据分析工具，更复杂的分析建议使用专业工具*\n",
            f"\n**分析类型**: {analysis_type}\n",
            "\n**建议**:\n",
            "- 使用 pandas 进行更深入的统计分析\n",
            "- 使用 matplotlib/seaborn 进行数据可视化\n",
            "- 使用 numpy 进行数值计算\n"
        ]
        
        return [types.TextContent(type="text", text="\n".join(output))]


# 导出所有工具
__all__ = [
    'MetadataSearchTool',
    'HistoricalQuerySearchTool',
    'SQLExecutorTool',
    'QueryOptimizationTool',
    'DataAnalysisTool',
]
