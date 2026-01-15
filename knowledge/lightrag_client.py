"""
LightRAG API 客户端
调用独立的 LightRAG 服务进行历史查询搜索
"""

import os
import sys
import httpx
from typing import Any, Dict, List, Optional, Literal
import json

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logger_config import get_knowledge_logger

logger = get_knowledge_logger()


class LightRAGClient:
    """LightRAG HTTP API 客户端"""
    
    def __init__(
        self,
        api_url: str = None,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        """
        初始化 LightRAG 客户端
        
        Args:
            api_url: LightRAG 服务地址，如 http://localhost:9621
            api_key: API 密钥（如果服务需要认证）
            timeout: 请求超时时间（秒）
        """
        self.api_url = api_url or os.getenv('LIGHTRAG_API_URL', 'http://localhost:9621')
        self.api_key = api_key or os.getenv('LIGHTRAG_API_KEY')
        self.timeout = timeout
        
        # 移除末尾的斜杠
        self.api_url = self.api_url.rstrip('/')
        
        # 构建请求头
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'
        
        logger.debug(f"LightRAG 客户端已初始化: {self.api_url}")
    
    async def health_check(self) -> bool:
        """
        检查 LightRAG 服务是否可用
        
        Returns:
            服务是否可用
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.api_url}/health",
                    headers=self.headers
                )
                is_healthy = response.status_code == 200
                if is_healthy:
                    logger.debug("LightRAG 服务健康检查成功")
                else:
                    logger.warning(f"LightRAG 服务健康检查失败，状态码: {response.status_code}")
                return is_healthy
        except Exception as e:
            logger.warning(f"⚠️ LightRAG 服务健康检查失败: {e}")
            return False
    
    async def search(
        self,
        query: str,
        mode: Literal["naive", "local", "global", "hybrid", "mix"] = "mix",
        top_k: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """
        搜索相似历史查询
        
        Args:
            query: 查询字符串（自然语言描述或关键词）
            mode: 检索模式
                - naive: 简单向量检索
                - local: 局部图检索
                - global: 全局图检索
                - hybrid: 混合检索（推荐）
            top_k: 返回结果数量
            **kwargs: 其他参数
        
        Returns:
            搜索结果字典
            {
                'mode': 检索模式,
                'query': 原始查询,
                'total': 结果数量,
                'results': 结果列表,
                'response': LightRAG 生成的回答（如果有）
            }
        """
        try:
            logger.debug(f"LightRAG 搜索: query='{query}', mode={mode}, top_k={top_k}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 构建请求体
                payload = {
                    'query': query,
                    'mode': mode,
                    'top_k': top_k,
                    **kwargs
                }
                
                # 调用查询接口
                response = await client.post(
                    f"{self.api_url}/query",
                    json=payload,
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = self._parse_response(data, query, mode)
                    logger.info(f"LightRAG 搜索成功，返回 {result.get('total', 0)} 条结果")
                    return result
                else:
                    logger.error(f'LightRAG API 返回错误: {response.status_code}')
                    return {
                        'error': f'LightRAG API 返回错误: {response.status_code}',
                        'mode': mode,
                        'query': query,
                        'total': 0,
                        'results': []
                    }
        
        except Exception as e:
            logger.error(f'调用 LightRAG API 失败: {str(e)}')
            return {
                'error': f'调用 LightRAG API 失败: {str(e)}',
                'mode': mode,
                'query': query,
                'total': 0,
                'results': []
            }
    
    def _parse_response(self, data: Dict[str, Any], query: str, mode: str) -> Dict[str, Any]:
        """
        解析 LightRAG 响应
        
        Args:
            data: API 响应数据
            query: 原始查询
            mode: 检索模式
        
        Returns:
            标准化的结果格式
        """
        # 根据 LightRAG API 的实际响应格式调整
        # 这里提供一个通用解析示例
        
        results = []
        response_text = data.get('response', '')
        
        # 如果有结构化的上下文或来源
        contexts = data.get('contexts', [])
        sources = data.get('sources', [])
        
        if contexts:
            for ctx in contexts:
                results.append({
                    'content': ctx.get('content', ''),
                    'score': ctx.get('score', 0.0),
                    'metadata': ctx.get('metadata', {})
                })
        elif sources:
            for src in sources:
                results.append({
                    'content': src.get('text', src.get('content', '')),
                    'score': src.get('relevance', src.get('score', 0.0)),
                    'metadata': src.get('metadata', {})
                })
        
        return {
            'mode': mode,
            'query': query,
            'total': len(results),
            'results': results,
            'response': response_text,
            'raw_data': data  # 保留原始响应
        }
    
    async def search_historical_queries(
        self,
        intent: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        搜索相似的历史 SQL 查询（便捷方法）
        
        Args:
            intent: 用户意图描述
            top_k: 返回结果数量
        
        Returns:
            历史查询列表，每个包含：
            - query_name: 查询名称
            - sql: SQL 语句
            - tables_used: 使用的表
            - description: 描述
            - score: 相似度分数
        """
        result = await self.search(intent, mode='hybrid', top_k=top_k)
        
        if 'error' in result:
            print(f"⚠️ {result['error']}")
            return []
        
        # 解析历史查询信息
        historical_queries = []
        for item in result.get('results', []):
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            
            # 尝试提取结构化信息
            query_info = self._extract_query_info(content, metadata)
            if query_info:
                query_info['score'] = item.get('score', 0.0)
                historical_queries.append(query_info)
        
        return historical_queries
    
    def _extract_query_info(self, content: str, metadata: Dict) -> Optional[Dict[str, Any]]:
        """
        从内容中提取查询信息
        
        Args:
            content: 文档内容
            metadata: 元数据
        
        Returns:
            查询信息字典或 None
        """
        # 简单的解析逻辑，根据实际文档格式调整
        info = {}
        
        # 尝试从 metadata 获取
        info['query_id'] = metadata.get('query_id')
        info['query_name'] = metadata.get('query_name', metadata.get('name'))
        info['tables_used'] = metadata.get('tables_used', [])
        info['description'] = metadata.get('description', '')
        
        # 从内容提取 SQL
        # 假设文档格式: Query Name: xxx\n...\n---\nSQL语句
        if '---' in content:
            parts = content.split('---')
            if len(parts) >= 2:
                header = parts[0]
                sql = parts[1].strip()
                info['sql'] = sql
                
                # 从 header 提取信息
                for line in header.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        
                        if key == 'query_name' and not info.get('query_name'):
                            info['query_name'] = value
                        elif key == 'description' and not info.get('description'):
                            info['description'] = value
                        elif key == 'tables_used':
                            # 解析表列表
                            info['tables_used'] = [t.strip() for t in value.split(',')]
        else:
            # 如果没有分隔符，整个内容可能就是 SQL
            info['sql'] = content
        
        # 确保至少有 SQL 或名称
        if info.get('sql') or info.get('query_name'):
            return info
        
        return None
    
    def format_historical_queries(self, queries: List[Dict[str, Any]]) -> str:
        """
        格式化历史查询为可读文本
        
        Args:
            queries: 历史查询列表
        
        Returns:
            格式化的文本
        """
        if not queries:
            return "未找到相似的历史查询"
        
        output = [f"找到 {len(queries)} 个相似的历史查询:\n"]
        
        for i, q in enumerate(queries, 1):
            output.append(f"{i}. {q.get('query_name', '未命名查询')} (相似度: {q.get('score', 0):.2f})")
            
            if q.get('description'):
                output.append(f"   描述: {q['description']}")
            
            if q.get('tables_used'):
                tables = ', '.join(q['tables_used'])
                output.append(f"   使用的表: {tables}")
            
            if q.get('sql'):
                sql_preview = q['sql'][:200] + '...' if len(q['sql']) > 200 else q['sql']
                output.append(f"   SQL: {sql_preview}")
            
            output.append("")
        
        return "\n".join(output)
