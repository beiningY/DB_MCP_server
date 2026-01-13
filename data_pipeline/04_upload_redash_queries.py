#!/usr/bin/env python3
"""
自动化脚本：将 Redash 查询上传到 RAG 系统
读取 redash_queries.json，将每个查询的 SQL 发送到 RAG 接口
"""

import json
import requests
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# 配置
RAG_API_URL = "http://localhost:9621/documents/text"
REDASH_QUERIES_FILE = Path(__file__).parent.parent / "metadata" / "redash_queries.json"
MAX_WORKERS = 5  # 并发请求数
RETRY_COUNT = 3  # 失败重试次数
RETRY_DELAY = 1  # 重试延迟（秒）


def load_queries(file_path: Path) -> list:
    """加载 Redash 查询数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('queries', [])


def build_file_source(query: dict) -> str:
    """构建 file_source 字段：Query{id}:{name}"""
    query_id = query.get('id', 'unknown')
    query_name = query.get('name', 'untitled')
    return f"Query{query_id}:{query_name}"


def upload_query(query: dict) -> dict:
    """
    上传单个查询到 RAG 系统
    返回: {"success": bool, "file_source": str, "error": str or None}
    """
    file_source = build_file_source(query)
    sql_text = query.get('sql', '')
    
    # 跳过空 SQL
    if not sql_text.strip():
        return {
            "success": False,
            "file_source": file_source,
            "error": "Empty SQL"
        }
    
    payload = {
        "file_source": file_source,
        "text": sql_text
    }
    
    # 带重试的请求
    for attempt in range(RETRY_COUNT):
        try:
            response = requests.post(
                RAG_API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in (200, 201):
                return {
                    "success": True,
                    "file_source": file_source,
                    "error": None
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
        
        # 重试前等待
        if attempt < RETRY_COUNT - 1:
            time.sleep(RETRY_DELAY)
    
    return {
        "success": False,
        "file_source": file_source,
        "error": error_msg
    }


def main():
    """主函数：批量上传所有查询"""
    print(f"📂 读取查询文件: {REDASH_QUERIES_FILE}")
    
    if not REDASH_QUERIES_FILE.exists():
        print(f"❌ 文件不存在: {REDASH_QUERIES_FILE}")
        return
    
    queries = load_queries(REDASH_QUERIES_FILE)
    total = len(queries)
    print(f"📊 共 {total} 个查询待处理")
    
    # 统计结果
    success_count = 0
    failed_count = 0
    failed_queries = []
    
    # 使用线程池并发上传
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_query = {
            executor.submit(upload_query, query): query 
            for query in queries
        }
        
        # 处理结果并显示进度
        with tqdm(total=total, desc="上传进度", unit="query") as pbar:
            for future in as_completed(future_to_query):
                result = future.result()
                
                if result["success"]:
                    success_count += 1
                else:
                    failed_count += 1
                    failed_queries.append(result)
                
                pbar.update(1)
    
    # 打印统计结果
    print("\n" + "=" * 50)
    print(f"✅ 上传成功: {success_count}")
    print(f"❌ 上传失败: {failed_count}")
    
    # 打印失败详情
    if failed_queries:
        print("\n📋 失败详情:")
        for item in failed_queries[:20]:  # 最多显示 20 条
            print(f"  - {item['file_source']}: {item['error']}")
        
        if len(failed_queries) > 20:
            print(f"  ... 还有 {len(failed_queries) - 20} 个失败项")
        
        # 保存失败记录到文件
        failed_log_path = Path(__file__).parent / "upload_failed.json"
        with open(failed_log_path, 'w', encoding='utf-8') as f:
            json.dump(failed_queries, f, ensure_ascii=False, indent=2)
        print(f"\n📝 失败记录已保存到: {failed_log_path}")


if __name__ == "__main__":
    main()

