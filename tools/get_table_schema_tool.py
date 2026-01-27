"""
数据库表结构查询工具
获取表的字段、类型、注释等元数据信息，输出为易读的文本格式
"""

import os
import json
from pathlib import Path
from typing import Optional, List
from langchain_core.tools import tool


def format_table_info(table: dict, online_dict: dict = None) -> str:
    """
    将表结构信息格式化为文本
    
    Args:
        table: 表的元数据字典
        online_dict: 在线字典（包含额外的表注释和字段枚举值）
    
    Returns:
        格式化的文本字符串
    """
    table_name = table.get("table_name", "")
    table_comment = table.get("table_comment", "")
    #business_domain = table.get("business_domain", "")
    #granularity = table.get("granularity", "")
    
    # 检查在线字典是否有额外信息
    extra_info = None
    extra_columns_info = {}
    if online_dict and table_name.lower() in online_dict:
        extra_info = online_dict[table_name.lower()]
        # 如果在线字典有更详细的表注释，使用它
        if extra_info.get("table_comment"):
            table_comment = extra_info.get("table_comment")
        # 获取额外的字段说明
        if extra_info.get("columns"):
            extra_columns_info = extra_info.get("columns", {})
    
    # 构建表头信息
    lines = [
        f"【表名】{table_name}",
        f"【表注释】{table_comment}" if table_comment else "",
        "",
        "【字段列表】"
    ]
    
    # 处理字段信息
    columns = table.get("columns", [])
    column_names = set()  # 记录元数据中的字段名
    
    for col in columns:
        col_name = col.get("column_name", "")
        column_names.add(col_name)
        data_type = col.get("data_type", "")
        comment = col.get("comment", "")
        is_pk = col.get("is_primary_key", False)
        is_pii = col.get("is_pii", False)
        related_table = col.get("related_table", "")
        related_column = col.get("related_column", "")
        
        # 构建字段描述
        col_desc = f"  - {col_name} ({data_type})"
        
        # 添加注释
        if comment:
            col_desc += f": {comment}"
        
        # 添加标记
        marks = []
        if is_pk:
            marks.append("主键")
        if is_pii:
            marks.append("敏感字段")
        if related_table:
            marks.append(f"关联 {related_table}.{related_column}")
        
        if marks:
            col_desc += f" [{', '.join(marks)}]"
        
        # 如果在线字典有额外说明（如枚举值）
        if col_name in extra_columns_info:
            extra_desc = extra_columns_info[col_name]
            col_desc += f"\n      └─ 补充说明: {extra_desc}"
        
        lines.append(col_desc)
    
    # 添加在线字典中有但元数据中没有的字段说明
    extra_only_columns = {k: v for k, v in extra_columns_info.items() if k not in column_names}
    if extra_only_columns:
        lines.append("")
        lines.append("【在线字典补充说明】（字段可能为计算字段或已更新）")
        for col_name, desc in extra_only_columns.items():
            lines.append(f"  - {col_name}: {desc}")
    
    # 过滤空行并拼接
    return "\n".join(line for line in lines if line is not None)


@tool
def get_table_schema(
    table_name: Optional[str] = None,
    database: str = "singa_bi"
) -> str:
    """
    获取数据库表的结构信息（字段、类型、注释等），返回易读的文本格式
    
    Args:
        table_name: 表名。
            - 如果为 None：返回所有表的摘要列表
            - 如果指定表名：返回该表的详细结构（包含所有字段信息）
        database: 数据库名称，默认 "singa_bi"
    
    Returns:
        文本格式的表结构信息：
        - 表名、表注释、业务域
        - 字段名、类型、注释
        - 主键、敏感字段、关联表等标记
        - 在线字典中的额外说明（如枚举值）
    
    Examples:
        >>> get_table_schema.invoke({})  # 获取所有表列表
        >>> get_table_schema.invoke({"table_name": "temp_rc_model_daily"})  # 获取指定表
    """
    # 加载元数据文件
    metadata_path = Path("metadata/singa_bi_metadata.json")
    online_dict_path = Path("metadata/online_dictionary.json")
    
    if not metadata_path.exists():
        return f"元数据文件不存在：{metadata_path}"
    
    try:
        # 读取元数据
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 读取在线字典（如果存在）
        online_dict = {}
        if online_dict_path.exists():
            try:
                with open(online_dict_path, 'r', encoding='utf-8') as f:
                    online_dict = json.load(f)
            except Exception:
                pass
        
        tables = metadata.get("tables", [])
        
        # ====== 如果未指定表名，返回所有表的摘要 ======
        if not table_name:
            lines = [
                f"数据库 {database} 表结构摘要",
                f"共 {len(tables)} 个表",
                "=" * 60,
                ""
            ]
            
            # 按业务域分组
            domain_tables = {}
            for table in tables:
                domain = table.get("business_domain", "其他")
                if domain not in domain_tables:
                    domain_tables[domain] = []
                domain_tables[domain].append(table)
            
            for domain, domain_table_list in sorted(domain_tables.items()):
                lines.append(f"\n【{domain}】({len(domain_table_list)} 个表)")
                lines.append("-" * 40)
                
                for table in domain_table_list[:20]:  # 每个域最多显示20个表
                    t_name = table.get("table_name", "")
                    t_comment = table.get("table_comment", "")
                    col_count = len(table.get("columns", []))
                    
                    # 截断过长的注释
                    if len(t_comment) > 50:
                        t_comment = t_comment[:47] + "..."
                    
                    lines.append(f"  • {t_name} ({col_count}字段)")
                    if t_comment:
                        lines.append(f"    {t_comment}")
                
                if len(domain_table_list) > 20:
                    lines.append(f"    ... 还有 {len(domain_table_list) - 20} 个表")
            
            lines.append("")
            lines.append("=" * 60)
            lines.append("提示: 使用 get_table_schema('表名') 查看具体表的详细结构")
            
            return "\n".join(lines)
        
        # ====== 查找指定表 ======
        table_name_lower = table_name.lower()
        target_table = None
        
        for table in tables:
            if table.get("table_name", "").lower() == table_name_lower:
                target_table = table
                break
        
        if not target_table:
            # 尝试模糊匹配
            similar_tables = []
            for table in tables:
                t_name = table.get("table_name", "")
                if table_name_lower in t_name.lower():
                    similar_tables.append(t_name)
            
            msg = f"表 '{table_name}' 不存在\n"
            if similar_tables:
                msg += f"\n你可能想查找以下表：\n"
                for t in similar_tables[:10]:
                    msg += f"  • {t}\n"
            return msg
        
        # ====== 返回表的详细结构 ======
        result = format_table_info(target_table, online_dict)
        
        # 添加统计信息
        col_count = len(target_table.get("columns", []))
        result += f"\n\n 共 {col_count} 个字段"
        
        return result
    
    except json.JSONDecodeError as e:
        return f"元数据文件格式错误：{str(e)}"
    
    except Exception as e:
        return f"查询失败：{str(e)}"
