"""
SQL 执行工具
支持直接连接 MySQL 数据库执行查询
"""

import os
import json
import time
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.tools import tool


@tool
def execute_sql_query(
    sql: str,
    database: str = "singa_bi",
    limit: Optional[int] = None
) -> str:
    """
    执行 SQL 查询并返回结果
    
    Args:
        sql: 要执行的 SQL 查询语句（仅支持 SELECT 查询）
        database: 目标数据库名称，默认 "singa_bi"
        limit: 最大返回行数，默认 100。如果 SQL 中已有 LIMIT，则使用 SQL 中的值
    
    Returns:
        JSON 格式的查询结果，包含：
        - success: 是否成功
        - data: 查询结果（列表形式，每行是一个字典）
        - columns: 列名列表
        - row_count: 返回行数
        - execution_time: 执行时间（毫秒）
        - message: 提示信息或错误信息
    
    Examples:
        >>> execute_sql_query("SELECT * FROM users WHERE id = 1")
        >>> execute_sql_query("SELECT COUNT(*) as cnt FROM orders", limit=1)
    """
    # 基本参数验证
    sql = sql.strip()
    if not sql:
        return json.dumps({
            "success": False,
            "message": "SQL 查询不能为空",
            "data": [],
            "columns": [],
            "row_count": 0
        }, ensure_ascii=False)
    
    # 安全检查：只允许 SELECT 查询
    sql_upper = sql.upper()
    if not sql_upper.startswith("SELECT"):
        return json.dumps({
            "success": False,
            "message": "仅支持 SELECT 查询，不允许执行修改语句（INSERT/UPDATE/DELETE/DROP 等）",
            "data": [],
            "columns": [],
            "row_count": 0
        }, ensure_ascii=False)
    
    # 自动添加 LIMIT 保护（如果没有）
    if limit is None:
        limit = 100
    
    if "LIMIT" not in sql_upper:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"
    
    # 获取数据库连接
    db_url = os.getenv("DB_URL")
    if not db_url:
        return json.dumps({
            "success": False,
            "message": "数据库连接未配置，请设置 DB_URL 环境变量",
            "data": [],
            "columns": [],
            "row_count": 0
        }, ensure_ascii=False)
    
    try:
        # 创建数据库引擎
        engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        start_time = time.time()
        
        # 执行查询
        with engine.connect() as conn:
            # 设置查询超时（30秒）
            conn.execute(text("SET SESSION MAX_EXECUTION_TIME=30000"))
            
            # 执行 SQL
            result = conn.execute(text(sql))
            
            # 获取列名
            columns = list(result.keys())
            
            # 获取数据
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
            
            # 处理特殊类型（日期、Decimal 等）
            for row in data:
                for key, value in row.items():
                    if value is not None:
                        # 转换 Decimal 为 float
                        if hasattr(value, '__class__') and 'Decimal' in str(value.__class__):
                            row[key] = float(value)
                        # 转换日期时间为字符串
                        elif hasattr(value, 'isoformat'):
                            row[key] = value.isoformat()
            
            execution_time = (time.time() - start_time) * 1000  # 转为毫秒
            
            return json.dumps({
                "success": True,
                "data": data,
                "columns": columns,
                "row_count": len(data),
                "execution_time": round(execution_time, 2),
                "message": f"查询成功，返回 {len(data)} 行数据"
            }, ensure_ascii=False, default=str)
    
    except SQLAlchemyError as e:
        return json.dumps({
            "success": False,
            "message": f"SQL 执行错误: {str(e)}",
            "data": [],
            "columns": [],
            "row_count": 0
        }, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"未知错误: {str(e)}",
            "data": [],
            "columns": [],
            "row_count": 0
        }, ensure_ascii=False)
    
    finally:
        # 关闭引擎
        if 'engine' in locals():
            engine.dispose()
