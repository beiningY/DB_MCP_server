"""
LightRAG 知识图谱搜索工具
用于查询历史 SQL、相关表和字段的业务逻辑
"""

import os
import json
import requests
from typing import Optional, Literal
from langchain_core.tools import tool


@tool
def search_knowledge_graph(
    query: str,
    mode: Literal["naive", "local", "global", "hybrid", "mix", "bypass"] = "mix",
    top_k: int = 5
) -> str:
    """
    在知识图谱中搜索相关信息（历史 SQL 查询、表字段说明、业务逻辑）
    
    Args:
        query: 搜索查询，支持自然语言描述
               例如：
               - "如何计算放款金额"
               - "temp_rc_model_daily 表的用途"
               - "machine_status 字段的含义"
               - "查询昨天新增用户的 SQL"
        mode: 搜索模式（默认 "mix"，推荐）
            - "naive": 简单向量相似度搜索，不使用知识图谱
            - "local": 关注特定实体及其直接关系
            - "global": 分析知识图谱中更广泛的模式和关系
            - "hybrid": 结合 local 和 global 方法
            - "mix": 集成知识图谱检索和向量搜索（推荐）
            - "bypass": 直接 LLM 查询，不使用知识检索
        top_k: 返回的结果数量，默认 5（注意：LightRAG 可能不支持此参数）
    
    Returns:
        JSON 格式的搜索结果，包含：
        - success: 是否成功
        - results: 搜索结果（LightRAG 返回的智能回答）
        - mode: 使用的搜索模式
        - message: 提示信息或错误信息
    
    Examples:
        >>> search_knowledge_graph.invoke({"query": "如何计算 NPL 率"})
        >>> search_knowledge_graph.invoke({"query": "temp_rc_model_daily 表", "mode": "local"})
        >>> search_knowledge_graph.invoke({"query": "查询昨天的放款金额", "top_k": 3})
    """
    # 参数验证
    if not query or not query.strip():
        return json.dumps({
            "success": False,
            "message": "查询内容不能为空",
            "results": []
        }, ensure_ascii=False)
    
    # 获取 LightRAG API 配置
    lightrag_url = os.getenv("LIGHTRAG_API_URL", "http://localhost:9621")
    
    # 构建 API 端点
    api_endpoint = f"{lightrag_url.rstrip('/')}/query"
    
    # 构建请求体（根据 LightRAG API 文档）
    payload = {
        "query": query.strip(),
        "mode": mode
        # 注意：LightRAG API 可能不支持 top_k 参数，这里仅保留 query 和 mode
    }
    
    try:
        # 发送请求
        response = requests.post(
            api_endpoint,
            json=payload,
            timeout=600
        )
        
        # 检查响应状态
        if response.status_code == 200:
            result_data = response.json()
            
            # LightRAG 返回格式可能是 {"response": "..."} 或直接是文本
            if isinstance(result_data, dict):
                if "response" in result_data:
                    content = result_data["response"]
                elif "result" in result_data:
                    content = result_data["result"]
                else:
                    content = json.dumps(result_data, ensure_ascii=False)
            else:
                content = str(result_data)
            
            return json.dumps({
                "success": True,
                "results": content,
                "mode": mode,
                "top_k": top_k,
                "message": "搜索成功"
            }, ensure_ascii=False)
        
        elif response.status_code == 404:
            return json.dumps({
                "success": False,
                "message": f"LightRAG 服务未找到，请检查服务地址：{lightrag_url}",
                "results": []
            }, ensure_ascii=False)
        
        else:
            return json.dumps({
                "success": False,
                "message": f"LightRAG API 返回错误：{response.status_code} - {response.text[:200]}",
                "results": []
            }, ensure_ascii=False)
    
    except requests.exceptions.ConnectionError:
        return json.dumps({
            "success": False,
            "message": f"无法连接到 LightRAG 服务（{lightrag_url}），请确认服务是否启动",
            "results": []
        }, ensure_ascii=False)
    
    except requests.exceptions.Timeout:
        return json.dumps({
            "success": False,
            "message": "LightRAG 查询超时（30秒），请稍后重试",
            "results": []
        }, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"查询失败：{str(e)}",
            "results": []
        }, ensure_ascii=False)
