import os
import json
import re
import requests
import sqlglot
from sqlglot import exp
from dotenv import load_dotenv
import time
import urllib3

# 禁用 SSL 警告（内网证书可能不受信任）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 加载环境变量
load_dotenv()

# ============ 网络配置 ============
# Redash 走本地网络，不使用代理
# 如果之前设置了代理环境变量，这里清除
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
print("✓ 使用本地网络连接 Redash（无代理）")
# =================================

REDASH_HOST = os.getenv("REDASH_URL")
API_KEY = os.getenv("REDASH_API_KEY")
HEADERS = {"Authorization": f"Key {API_KEY}"}

# SSL 验证设置（内网可能需要关闭）
VERIFY_SSL = False

# ================= 工具函数 =================

def get_all_items(endpoint):
    """
    处理分页，获取 Redash 所有数据 (Dashboard 或 Queries)
    """
    items = []
    page = 1
    page_size = 100
    
    print(f"📡 开始获取 {endpoint} ...")
    
    while True:
        try:
            url = f"{REDASH_HOST}/api/{endpoint}?page={page}&page_size={page_size}"
            response = requests.get(url, headers=HEADERS, verify=VERIFY_SSL, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Redash API 的返回结构通常是 {'results': [...], 'count': ...}
            current_results = data.get('results', [])
            if not current_results:
                break
                
            items.extend(current_results)
            print(f"   - 第 {page} 页获取成功，当前总数: {len(items)}")
            
            # 检查是否还有下一页
            if len(current_results) < page_size:
                break
                
            page += 1
            # 避免对服务器造成过大压力
            time.sleep(0.2)
            
        except Exception as e:
            print(f"❌ 获取第 {page} 页失败: {e}")
            break
            
    return items

def extract_tables_regex_fallback(sql_text):
    """
    正则兜底：当 sqlglot 解析失败时，用正则提取表名
    """
    tables = set()
    
    # 匹配 FROM/JOIN/INTO/UPDATE 后的表名（支持 schema.table 格式）
    patterns = [
        r'\bFROM\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)',
        r'\bJOIN\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)',
        r'\bINTO\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)',
        r'\bUPDATE\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, sql_text, re.IGNORECASE)
        tables.update(matches)
    
    # 过滤掉 SQL 关键字
    keywords = {'SELECT', 'SET', 'VALUES', 'NULL', 'TRUE', 'FALSE', 'AS', 'ON', 'AND', 'OR', 'NOT'}
    tables = {t for t in tables if t.upper() not in keywords}
    
    return list(tables)


def extract_tables_from_sql(sql_text):
    """
    使用 sqlglot 解析 SQL，提取用到的表名（增强版）
    """
    if not sql_text:
        return []
    
    try:
        clean_sql = sql_text
        
        # 1. 将 {{ param }} 替换为带引号的占位符（处理参数中的空格）
        def replace_param(match):
            param_name = match.group(1).strip().replace(' ', '_').replace('.', '_')
            return f"'__PARAM_{param_name}__'"
        clean_sql = re.sub(r'\{\{\s*([^}]+?)\s*\}\}', replace_param, clean_sql)
        
        # 2. 将 MySQL 的 # 注释转换为标准 -- 注释
        clean_sql = re.sub(r'#(.*)$', r'-- \1', clean_sql, flags=re.MULTILINE)
        
        # 3. 移除用户变量赋值 @var:=value（MySQL 特有语法）
        clean_sql = re.sub(r'@\w+\s*:=\s*', '', clean_sql)
        
        # 4. 使用 sqlglot.parse 解析多条语句
        parsed_statements = sqlglot.parse(clean_sql, dialect="mysql")
        
        tables = set()
        for statement in parsed_statements:
            if statement:
                for t in statement.find_all(exp.Table):
                    table_name = t.sql()
                    if table_name and not table_name.startswith("'__PARAM_"):
                        tables.add(table_name)
        
        return list(tables)
        
    except Exception as e:
        # sqlglot 解析失败时，使用正则兜底
        return extract_tables_regex_fallback(sql_text)

# ================= 核心处理逻辑 =================

def main():
    if not REDASH_HOST or not API_KEY:
        print("❌ 请在 .env 文件中配置 REDASH_URL 和 REDASH_API_KEY")
        return

    # 1. 获取所有 Dashboard
    # 我们需要 Dashboard 的详细信息才能知道它包含哪些 Widget (Query)
    # 列表接口通常不给 widgets 详情，所以先拿列表，再由 Query 反查或者后续增强
    # 但为了给 LightRAG 最好的语料，我们尝试获取 Dashboard -> Query 的关系
    
    dashboards = get_all_items("dashboards")
    queries = get_all_items("queries")

    # 为了快速查找 Dashboard 信息，建立一个映射
    # 注意：Redash 的 Query API 返回中并没有直接包含 "属于哪个 Dashboard"
    # 关系存储在 Dashboard 对象里的 widgets 列表里
    
    query_usage_map = {} # query_id -> [dashboard_names]
    
    print("\n🔍 正在分析 Dashboard 与 Query 的关联...")
    for dash in dashboards:
        # 获取 Dashboard 详情（因为列表里通常没有 widgets 字段）
        try:
            slug = dash.get('slug')
            resp = requests.get(f"{REDASH_HOST}/api/dashboards/{slug}", headers=HEADERS, verify=VERIFY_SSL, timeout=30)
            if resp.status_code == 200:
                dash_detail = resp.json()
                dash_name = dash_detail.get('name', 'Unknown Dashboard')
                
                # 遍历 widgets 找 query
                for widget in dash_detail.get('widgets', []):
                    visualization = widget.get('visualization')
                    if visualization and 'query' in visualization:
                        q_id = visualization['query'].get('id')
                        if q_id:
                            if q_id not in query_usage_map:
                                query_usage_map[q_id] = []
                            query_usage_map[q_id].append(dash_name)
            time.sleep(0.1)
        except Exception as e:
            print(f"⚠️ 获取 Dashboard {slug} 详情失败: {e}")

    # 2. 构建结构化的 Query 列表
    query_list = []
    
    print("\n📝 正在处理 Query 数据...")
    
    for q in queries:
        q_id = q.get('id')
        q_name = q.get('name', '未命名查询')
        description = q.get('description') or ""
        sql = q.get('query', '')
        created_at = q.get('created_at', '')
        updated_at = q.get('updated_at', '')
        user = q.get('user', {})
        user_name = user.get('name', '') if user else ''
        
        # 提取表名
        tables = extract_tables_from_sql(sql)
        
        # 获取所属 Dashboard
        related_dashboards = query_usage_map.get(q_id, [])
        
        # 构建结构化数据
        query_data = {
            "id": q_id,
            "name": q_name,
            "description": description,
            "sql": sql,
            "tables_used": tables,
            "related_dashboards": related_dashboards,
            "created_by": user_name,
            "created_at": created_at,
            "updated_at": updated_at
        }
        
        query_list.append(query_data)

    # 3. 输出保存为 JSON
    output_file = "../metadata/redash_queries.json"
    
    result = {
        "total_queries": len(query_list),
        "total_dashboards": len(dashboards),
        "queries": query_list
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
            
    print(f"\n✅ 处理完成！")
    print(f"共提取 {len(query_list)} 个查询，关联 {len(dashboards)} 个仪表板")
    print(f"数据已保存至: {output_file}")

if __name__ == "__main__":
    main()