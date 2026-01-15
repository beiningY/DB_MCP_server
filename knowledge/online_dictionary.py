"""
在线数据字典模块
提供表和字段的业务含义查询
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path
import re

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .base import KnowledgeModule
from logger_config import get_knowledge_logger

logger = get_knowledge_logger()


class OnlineDictionaryModule(KnowledgeModule):
    """在线数据字典知识模块"""
    
    @property
    def name(self) -> str:
        return "online_dictionary"
    
    @property
    def description(self) -> str:
        return "在线数据字典：提供表和字段的业务含义、枚举值、注释等信息"
    
    def _initialize(self):
        """加载在线数据字典"""
        dict_file = self.config.get(
            'dictionary_file', 
            os.path.join(os.path.dirname(__file__), '..', 'metadata', 'online_dictionary.json')
        )
        
        try:
            with open(dict_file, 'r', encoding='utf-8') as f:
                self.dictionary = json.load(f)
            logger.info(f"✓ 成功加载在线数据字典: {len(self.dictionary)} 个表")
        except Exception as e:
            logger.warning(f"⚠️ 加载在线数据字典失败: {e}")
            self.dictionary = {}
    
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        搜索数据字典
        
        Args:
            query: 查询字符串（表名或字段名）
            **kwargs: 
                - search_type: 'table' | 'column' | 'auto' (默认)
                - fuzzy: 是否模糊匹配 (默认 True)
        
        Returns:
            搜索结果
        """
        search_type = kwargs.get('search_type', 'auto')
        fuzzy = kwargs.get('fuzzy', True)
        
        if search_type == 'table' or (search_type == 'auto' and '.' not in query):
            return await self.search_table(query, fuzzy=fuzzy)
        elif search_type == 'column':
            return await self.search_column(query, fuzzy=fuzzy)
        else:
            # 自动判断：如果包含点号，可能是 table.column
            return await self.search_table_column(query, fuzzy=fuzzy)
    
    async def search_table(self, table_name: str, fuzzy: bool = True) -> Dict[str, Any]:
        """
        搜索表信息
        
        Args:
            table_name: 表名
            fuzzy: 是否模糊匹配
        
        Returns:
            表信息字典
        """
        results = []
        query_lower = table_name.lower()
        
        for tbl_name, tbl_info in self.dictionary.items():
            if fuzzy:
                if query_lower in tbl_name.lower():
                    results.append({
                        'table_name': tbl_name,
                        'table_comment': tbl_info.get('table_comment', ''),
                        'columns': tbl_info.get('columns', {}),
                        'match_type': 'fuzzy'
                    })
            else:
                if tbl_name.lower() == query_lower:
                    results.append({
                        'table_name': tbl_name,
                        'table_comment': tbl_info.get('table_comment', ''),
                        'columns': tbl_info.get('columns', {}),
                        'match_type': 'exact'
                    })
        
        return {
            'query': table_name,
            'search_type': 'table',
            'total': len(results),
            'results': results
        }
    
    async def search_column(self, column_pattern: str, fuzzy: bool = True) -> Dict[str, Any]:
        """
        搜索字段信息（跨所有表）
        
        Args:
            column_pattern: 字段名模式
            fuzzy: 是否模糊匹配
        
        Returns:
            字段信息列表
        """
        results = []
        query_lower = column_pattern.lower()
        
        for tbl_name, tbl_info in self.dictionary.items():
            columns = tbl_info.get('columns', {})
            if not columns:
                continue
            
            for col_name, col_info in columns.items():
                match = False
                if fuzzy:
                    match = query_lower in col_name.lower()
                else:
                    match = col_name.lower() == query_lower
                
                if match:
                    results.append({
                        'table_name': tbl_name,
                        'table_comment': tbl_info.get('table_comment', ''),
                        'column_name': col_name,
                        'column_info': col_info,
                        'match_type': 'fuzzy' if fuzzy else 'exact'
                    })
        
        return {
            'query': column_pattern,
            'search_type': 'column',
            'total': len(results),
            'results': results
        }
    
    async def search_table_column(self, full_name: str, fuzzy: bool = True) -> Dict[str, Any]:
        """
        搜索 table.column 格式
        
        Args:
            full_name: table.column 格式
            fuzzy: 是否模糊匹配
        
        Returns:
            字段详细信息
        """
        if '.' not in full_name:
            return await self.search_table(full_name, fuzzy=fuzzy)
        
        parts = full_name.split('.')
        if len(parts) != 2:
            return {'error': 'Invalid format. Use: table_name.column_name'}
        
        table_name, column_name = parts
        
        # 先找表
        table_result = await self.search_table(table_name, fuzzy=False)
        if not table_result['results']:
            # 尝试模糊匹配
            table_result = await self.search_table(table_name, fuzzy=True)
        
        results = []
        for tbl in table_result['results']:
            columns = tbl.get('columns', {})
            
            # 查找字段
            if column_name in columns:
                results.append({
                    'table_name': tbl['table_name'],
                    'table_comment': tbl['table_comment'],
                    'column_name': column_name,
                    'column_info': columns[column_name],
                    'match_type': 'exact'
                })
            elif fuzzy:
                # 模糊匹配字段
                for col_name, col_info in columns.items():
                    if column_name.lower() in col_name.lower():
                        results.append({
                            'table_name': tbl['table_name'],
                            'table_comment': tbl['table_comment'],
                            'column_name': col_name,
                            'column_info': col_info,
                            'match_type': 'fuzzy'
                        })
        
        return {
            'query': full_name,
            'search_type': 'table.column',
            'total': len(results),
            'results': results
        }
    
    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """直接获取表信息（同步方法）"""
        return self.dictionary.get(table_name)
    
    def get_all_tables(self) -> List[str]:
        """获取所有表名"""
        return list(self.dictionary.keys())
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化搜索结果为可读文本"""
        if 'error' in result:
            return f"❌ {result['error']}"
        
        if result['total'] == 0:
            return f"未找到与 '{result['query']}' 相关的结果"
        
        output = [f"找到 {result['total']} 个结果:\n"]
        
        for i, item in enumerate(result['results'][:10], 1):  # 限制显示前10个
            if result['search_type'] == 'table':
                output.append(f"{i}. 表: {item['table_name']}")
                output.append(f"   注释: {item['table_comment']}")
                if item['columns']:
                    output.append(f"   字段数: {len(item['columns'])}")
            
            elif result['search_type'] in ['column', 'table.column']:
                output.append(f"{i}. {item['table_name']}.{item['column_name']}")
                output.append(f"   表注释: {item['table_comment']}")
                col_info = item['column_info']
                if isinstance(col_info, str):
                    output.append(f"   字段说明: {col_info}")
                elif isinstance(col_info, dict):
                    for k, v in col_info.items():
                        output.append(f"   {k}: {v}")
            
            output.append("")
        
        if result['total'] > 10:
            output.append(f"... 还有 {result['total'] - 10} 个结果")
        
        return "\n".join(output)
