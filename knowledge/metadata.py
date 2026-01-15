"""
Singa BI 元数据模块
提供数据库完整结构信息、业务域、表关系等
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .base import KnowledgeModule
from logger_config import get_knowledge_logger

logger = get_knowledge_logger()


class SingaBIMetadataModule(KnowledgeModule):
    """Singa BI 元数据知识模块"""
    
    @property
    def name(self) -> str:
        return "singa_bi_metadata"
    
    @property
    def description(self) -> str:
        return "Singa BI 元数据：提供数据库完整表结构、业务域、字段类型、关系等信息"
    
    def _initialize(self):
        """加载 BI 元数据"""
        metadata_file = self.config.get(
            'metadata_file',
            os.path.join(os.path.dirname(__file__), '..', 'metadata', 'singa_bi_metadata.json')
        )
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            
            # 构建索引
            self._build_indices()
            
            tables = self.metadata.get('tables', [])
            logger.info(f"✓ 成功加载 BI 元数据: {len(tables)} 个表")
        except Exception as e:
            logger.warning(f"⚠️ 加载 BI 元数据失败: {e}")
            self.metadata = {'tables': []}
            self.table_index = {}
            self.domain_index = {}
            self.column_index = {}
    
    def _build_indices(self):
        """构建快速查询索引"""
        self.table_index = {}  # table_name -> table_dict
        self.domain_index = {}  # business_domain -> [tables]
        self.column_index = {}  # column_name -> [(table_name, column_dict)]
        self.pii_tables = set()  # 包含 PII 字段的表
        
        for table in self.metadata.get('tables', []):
            table_name = table['table_name']
            self.table_index[table_name] = table
            
            # 按业务域索引
            domain = table.get('business_domain', 'unknown')
            if domain not in self.domain_index:
                self.domain_index[domain] = []
            self.domain_index[domain].append(table_name)
            
            # 按字段索引
            for column in table.get('columns', []):
                col_name = column['column_name']
                if col_name not in self.column_index:
                    self.column_index[col_name] = []
                self.column_index[col_name].append((table_name, column))
                
                # 标记包含 PII 的表
                if column.get('is_pii', False):
                    self.pii_tables.add(table_name)
    
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        搜索元数据
        
        Args:
            query: 查询字符串
            **kwargs:
                - search_type: 'table' | 'column' | 'domain' | 'auto'
                - business_domain: 按业务域过滤
                - include_pii: 是否包含 PII 敏感字段
        
        Returns:
            搜索结果
        """
        search_type = kwargs.get('search_type', 'auto')
        
        if search_type == 'domain':
            return await self.search_by_domain(query)
        elif search_type == 'column':
            return await self.search_columns(query, **kwargs)
        else:
            return await self.search_tables(query, **kwargs)
    
    async def search_tables(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        搜索表
        
        Args:
            query: 表名或注释关键词
            **kwargs:
                - business_domain: 限定业务域
                - granularity: 限定粒度
                - fuzzy: 模糊匹配
        
        Returns:
            表信息列表
        """
        fuzzy = kwargs.get('fuzzy', True)
        domain_filter = kwargs.get('business_domain')
        granularity_filter = kwargs.get('granularity')
        
        results = []
        query_lower = query.lower()
        
        for table in self.metadata.get('tables', []):
            # 业务域过滤
            if domain_filter and table.get('business_domain') != domain_filter:
                continue
            
            # 粒度过滤
            if granularity_filter and table.get('granularity') != granularity_filter:
                continue
            
            # 名称或注释匹配
            table_name = table['table_name']
            table_comment = table.get('table_comment', '')
            
            match = False
            match_type = 'none'
            
            if fuzzy:
                if query_lower in table_name.lower():
                    match = True
                    match_type = 'name_fuzzy'
                elif query_lower in table_comment.lower():
                    match = True
                    match_type = 'comment_fuzzy'
            else:
                if table_name.lower() == query_lower:
                    match = True
                    match_type = 'name_exact'
            
            if match:
                results.append({
                    'table_name': table_name,
                    'table_comment': table_comment,
                    'business_domain': table.get('business_domain', 'unknown'),
                    'granularity': table.get('granularity', 'unknown'),
                    'owner': table.get('owner', ''),
                    'column_count': len(table.get('columns', [])),
                    'has_pii': table_name in self.pii_tables,
                    'match_type': match_type
                })
        
        return {
            'query': query,
            'search_type': 'table',
            'filters': {
                'business_domain': domain_filter,
                'granularity': granularity_filter
            },
            'total': len(results),
            'results': results
        }
    
    async def search_columns(self, column_name: str, **kwargs) -> Dict[str, Any]:
        """
        搜索字段（跨表）
        
        Args:
            column_name: 字段名
            **kwargs:
                - data_type: 限定数据类型
                - table_filter: 限定表名
        
        Returns:
            字段信息列表
        """
        table_filter = kwargs.get('table_filter')
        data_type = kwargs.get('data_type')
        
        results = []
        
        # 使用索引快速查找
        if column_name in self.column_index:
            for table_name, column in self.column_index[column_name]:
                # 表名过滤
                if table_filter and table_filter.lower() not in table_name.lower():
                    continue
                
                # 数据类型过滤
                if data_type and column.get('data_type', '').lower() != data_type.lower():
                    continue
                
                table_info = self.table_index.get(table_name, {})
                results.append({
                    'table_name': table_name,
                    'table_comment': table_info.get('table_comment', ''),
                    'business_domain': table_info.get('business_domain', 'unknown'),
                    'column_name': column['column_name'],
                    'data_type': column.get('data_type', ''),
                    'comment': column.get('comment', ''),
                    'is_primary_key': column.get('is_primary_key', False),
                    'is_pii': column.get('is_pii', False),
                    'related_table': column.get('related_table'),
                    'related_column': column.get('related_column')
                })
        
        return {
            'query': column_name,
            'search_type': 'column',
            'filters': {
                'table_filter': table_filter,
                'data_type': data_type
            },
            'total': len(results),
            'results': results
        }
    
    async def search_by_domain(self, domain: str) -> Dict[str, Any]:
        """
        按业务域搜索
        
        Args:
            domain: 业务域（collection, marketing, risk, user, order 等）
        
        Returns:
            该业务域的所有表
        """
        domain_lower = domain.lower()
        
        # 精确匹配或模糊匹配
        matched_domains = []
        for d in self.domain_index.keys():
            if domain_lower == d.lower() or domain_lower in d.lower():
                matched_domains.append(d)
        
        results = []
        for d in matched_domains:
            table_names = self.domain_index[d]
            for table_name in table_names:
                table = self.table_index.get(table_name, {})
                results.append({
                    'table_name': table_name,
                    'table_comment': table.get('table_comment', ''),
                    'business_domain': d,
                    'granularity': table.get('granularity', ''),
                    'column_count': len(table.get('columns', []))
                })
        
        return {
            'query': domain,
            'search_type': 'business_domain',
            'matched_domains': matched_domains,
            'total': len(results),
            'results': results
        }
    
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取完整表结构"""
        return self.table_index.get(table_name)
    
    def get_related_tables(self, table_name: str) -> List[str]:
        """获取关联表（通过外键关系推断）"""
        table = self.table_index.get(table_name)
        if not table:
            return []
        
        related = set()
        for column in table.get('columns', []):
            related_table = column.get('related_table')
            if related_table:
                related.add(related_table)
        
        return list(related)
    
    def get_all_domains(self) -> List[str]:
        """获取所有业务域"""
        return list(self.domain_index.keys())
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化搜索结果"""
        if result['total'] == 0:
            return f"未找到与 '{result['query']}' 相关的结果"
        
        output = [f"找到 {result['total']} 个结果:\n"]
        
        for i, item in enumerate(result['results'][:10], 1):
            if result['search_type'] == 'table':
                output.append(f"{i}. 表: {item['table_name']}")
                output.append(f"   注释: {item['table_comment']}")
                output.append(f"   业务域: {item['business_domain']} | 粒度: {item['granularity']}")
                output.append(f"   字段数: {item['column_count']} | PII: {'是' if item.get('has_pii') else '否'}")
            
            elif result['search_type'] == 'column':
                output.append(f"{i}. {item['table_name']}.{item['column_name']}")
                output.append(f"   类型: {item['data_type']} | 主键: {'是' if item['is_primary_key'] else '否'}")
                output.append(f"   注释: {item['comment']}")
                if item.get('related_table'):
                    output.append(f"   关联: {item['related_table']}.{item.get('related_column', '')}")
            
            elif result['search_type'] == 'business_domain':
                output.append(f"{i}. {item['table_name']} ({item['table_comment']})")
                output.append(f"   粒度: {item['granularity']} | 字段数: {item['column_count']}")
            
            output.append("")
        
        if result['total'] > 10:
            output.append(f"... 还有 {result['total'] - 10} 个结果")
        
        return "\n".join(output)
