"""
MCP Resources - 数据库资源定义
为每个数据库表创建独立的资源
"""

import json
from sqlalchemy import text, inspect


def get_table_schema(table_name: str, get_db_engine, get_database_name) -> dict:
    """
    获取单个表的详细 Schema 信息
    
    Args:
        table_name: 表名
        get_db_engine: 获取数据库引擎的函数
        get_database_name: 获取数据库名的函数
    
    Returns:
        表的详细 Schema 信息
    """
    engine = get_db_engine()
    if engine is None:
        return {"error": "数据库未配置"}
    
    try:
        inspector = inspect(engine)
        
        # 获取表注释
        try:
            table_comment = inspector.get_table_comment(table_name).get("text", "")
        except Exception:
            table_comment = ""
        
        # 获取主键
        try:
            pk_constraint = inspector.get_pk_constraint(table_name)
            primary_keys = set(pk_constraint.get("constrained_columns", []))
        except Exception:
            primary_keys = set()
        
        # 获取字段信息
        columns = []
        for col in inspector.get_columns(table_name):
            col_info = {
                "name": col.get("name", ""),
                "type": str(col.get("type", "")),
                "nullable": col.get("nullable", True),
                "default": str(col.get("default")) if col.get("default") else None,
                "comment": col.get("comment", "") or "",
                "is_primary_key": col.get("name") in primary_keys
            }
            columns.append(col_info)
        
        # 获取外键
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_keys.append({
                "columns": fk.get("constrained_columns", []),
                "referred_table": fk.get("referred_table", ""),
                "referred_columns": fk.get("referred_columns", [])
            })
        
        # 获取索引
        indexes = []
        for idx in inspector.get_indexes(table_name):
            indexes.append({
                "name": idx.get("name", ""),
                "columns": idx.get("column_names", []),
                "unique": idx.get("unique", False)
            })
        
        # 获取表行数估算
        row_count = None
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_NAME = :table"),
                    {"table": table_name}
                )
                row = result.fetchone()
                if row:
                    row_count = row[0]
        except Exception:
            pass
        
        return {
            "name": table_name,
            "database": get_database_name(),
            "comment": table_comment,
            "column_count": len(columns),
            "row_count_estimate": row_count,
            "columns": columns,
            "primary_keys": list(primary_keys) if primary_keys else None,
            "foreign_keys": foreign_keys if foreign_keys else None,
            "indexes": indexes if indexes else None
        }
    
    except Exception as e:
        return {"error": f"获取表信息失败: {str(e)}"}


def get_all_table_names(get_db_engine) -> list[str]:
    """获取所有表名"""
    engine = get_db_engine()
    if engine is None:
        return []
    
    try:
        inspector = inspect(engine)
        return inspector.get_table_names()
    except Exception:
        return []


def register_resources(mcp, get_database_name, get_db_engine):
    """
    注册 MCP 资源到服务器
    为每个数据库表创建独立的资源
    
    Args:
        mcp: FastMCP 实例
        get_database_name: 获取数据库名的函数
        get_db_engine: 获取数据库引擎的函数
    """
    database = get_database_name()
    
    # 尝试获取表名，数据库不可用时优雅降级
    try:
        table_names = get_all_table_names(get_db_engine)
    except Exception as e:
        print(f"[警告] 无法连接数据库，跳过表资源注册: {e}")
        return
    
    if not table_names:
        print("[提示] 未发现数据库表，跳过表资源注册")
        return
    
    # 为每个表动态创建资源
    for table_name in table_names:
        # 获取表注释作为描述（失败时使用默认描述）
        description = f"{table_name} 表结构"
        try:
            engine = get_db_engine()
            if engine:
                inspector = inspect(engine)
                comment = inspector.get_table_comment(table_name).get("text", "")
                columns = inspector.get_columns(table_name)
                description = comment if comment else f"{table_name} 表结构（{len(columns)} 个字段）"
        except Exception:
            pass  # 使用默认描述
        
        # 使用闭包捕获当前的 table_name
        def make_resource_func(tbl_name):
            def get_table_resource() -> str:
                schema = get_table_schema(tbl_name, get_db_engine, get_database_name)
                return json.dumps(schema, ensure_ascii=False, indent=2)
            return get_table_resource
        
        # 注册资源
        resource_uri = f"db://{database}/table/{table_name}"
        mcp.resource(resource_uri, description=description)(make_resource_func(table_name))
