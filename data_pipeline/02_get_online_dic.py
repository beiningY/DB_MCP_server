"""
从 Google Sheets 获取在线数据字典，处理成 JSON 格式
输出格式：以表名为键，包含表注释和列信息
"""
import sys
import os
import json
from collections import defaultdict

# ============ 代理配置 ============
PROXY = "http://127.0.0.1:7897"
os.environ['HTTP_PROXY'] = PROXY
os.environ['HTTPS_PROXY'] = PROXY
os.environ['http_proxy'] = PROXY
os.environ['https_proxy'] = PROXY
print(f"✓ 代理配置: {PROXY}")
# =================================

import requests
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from dotenv import load_dotenv

load_dotenv()

# 配置
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SERVICE_ACCOUNT_FILE = 'credentials.json'
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
RANGE_NAME = 'Sheet1!A:D'
OUTPUT_FILE = '../metadata/online_dictionary.json'


def process_data_to_dict(rows: list) -> dict:
    """
    将原始行数据处理成以表名为键的字典
    
    输入格式: [Table_Name, Table_Comment, Column_Name, Column_Comment]
    输出格式:
    {
        "表名": {
            "table_comment": "表注释（多个会拼接）",
            "columns": {
                "列名": "列注释",
                ...
            }
        }
    }
    """
    result = defaultdict(lambda: {
        "table_comment": "",
        "columns": {}
    })
    
    # 跳过标题行
    data_rows = rows[1:] if rows and rows[0][0] in ['Table_Name', 'table_name', '表名'] else rows
    
    for row in data_rows:
        # 补齐列数
        while len(row) < 4:
            row.append('')
        
        table_name = row[0].strip() if row[0] else ''
        table_comment = row[1].strip() if row[1] else ''
        column_name = row[2].strip() if row[2] else ''
        column_comment = row[3].strip() if row[3] else ''
        
        if not table_name:
            continue
        
        # 清理表名（移除数据库前缀 singa_bi.）
        clean_table_name = table_name
        if '.' in table_name:
            clean_table_name = table_name.split('.')[-1]
        
        # 设置表注释（多个直接拼接）
        if table_comment:
            if result[clean_table_name]["table_comment"]:
                # 如果已有表注释且新注释不同，直接拼接
                if table_comment not in result[clean_table_name]["table_comment"]:
                    result[clean_table_name]["table_comment"] += f"；{table_comment}"
            else:
                result[clean_table_name]["table_comment"] = table_comment
        
        # 添加列信息
        if column_name:
            if column_name in result[clean_table_name]["columns"]:
                # 如果列已存在，追加注释
                existing = result[clean_table_name]["columns"][column_name]
                if column_comment and column_comment not in existing:
                    result[clean_table_name]["columns"][column_name] = f"{existing}；{column_comment}"
            else:
                result[clean_table_name]["columns"][column_name] = column_comment
    
    # 转换为普通字典并清理空值
    final_result = {}
    for table_name, info in result.items():
        final_result[table_name] = {
            "table_comment": info["table_comment"],
            "columns": info["columns"] if info["columns"] else None
        }
        # 移除 None 值
        final_result[table_name] = {k: v for k, v in final_result[table_name].items() if v is not None}
    
    return final_result


def main():
    print("--- 在线数据字典获取脚本 ---\n")
    
    # 1. 加载凭据
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        print("✓ 凭据加载成功")
    except Exception as e:
        print(f"✗ 凭据加载失败: {e}", file=sys.stderr)
        return

    # 2. 获取数据
    try:
        print("✓ 正在连接 Google Sheets API...")
        session = AuthorizedSession(creds)
        
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{RANGE_NAME}"
        response = session.get(url, timeout=60)
        
        if response.status_code != 200:
            print(f"✗ API 请求失败: {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            return
        
        data = response.json()
        rows = data.get('values', [])
        print(f"✓ 获取到 {len(rows)} 行数据")
        
    except requests.exceptions.Timeout:
        print("✗ 请求超时，请检查网络或代理", file=sys.stderr)
        return
    except Exception as e:
        print(f"✗ 请求失败: {e}", file=sys.stderr)
        return

    # 3. 处理数据
    print("✓ 正在处理数据...")
    result = process_data_to_dict(rows)
    print(f"✓ 处理完成，共 {len(result)} 张表")
    
    # 4. 保存 JSON 文件
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✓ 已保存到: {OUTPUT_FILE}")
    
    # 5. 打印预览
    print("\n--- 数据预览（前 5 张表）---")
    for i, (table_name, info) in enumerate(list(result.items())[:5]):
        print(f"\n📋 {table_name}:")
        print(f"   注释: {info.get('table_comment', '无')[:50]}...")
        if info.get('columns'):
            print(f"   字段: {list(info['columns'].keys())[:3]}...")


if __name__ == '__main__':
    main()
