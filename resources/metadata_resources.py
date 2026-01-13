"""
元数据相关的 MCP Resources
提供在线字典、BI 元数据、历史查询等资源的访问
"""

import json
import os
from typing import Any
from .base import BaseResource

# 导入知识模块
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from knowledge import OnlineDictionaryModule, SingaBIMetadataModule, LightRAGClient


class OnlineDictionaryResource(BaseResource):
    """在线数据字典资源"""
    
    def __init__(self):
        self.module = OnlineDictionaryModule()
    
    @property
    def uri(self) -> str:
        return "metadata://online_dictionary"
    
    @property
    def name(self) -> str:
        return "在线数据字典"
    
    @property
    def description(self) -> str:
        return "表和字段的业务含义、枚举值、注释等信息"
    
    @property
    def mime_type(self) -> str:
        return "application/json"
    
    async def read(self) -> str:
        """返回完整的在线字典数据"""
        return json.dumps(
            self.module.dictionary,
            ensure_ascii=False,
            indent=2
        )


class SingaBIMetadataResource(BaseResource):
    """Singa BI 元数据资源"""
    
    def __init__(self):
        self.module = SingaBIMetadataModule()
    
    @property
    def uri(self) -> str:
        return "metadata://singa_bi"
    
    @property
    def name(self) -> str:
        return "Singa BI 元数据"
    
    @property
    def description(self) -> str:
        return "BI 数据库的完整表结构、业务域、字段类型、关系等信息"
    
    @property
    def mime_type(self) -> str:
        return "application/json"
    
    async def read(self) -> str:
        """返回完整的元数据"""
        return json.dumps(
            self.module.metadata,
            ensure_ascii=False,
            indent=2
        )


class MetadataSummaryResource(BaseResource):
    """元数据摘要资源"""
    
    def __init__(self):
        try:
            self.online_dict = OnlineDictionaryModule()
        except:
            self.online_dict = None
        
        try:
            self.metadata = SingaBIMetadataModule()
        except:
            self.metadata = None
    
    @property
    def uri(self) -> str:
        return "metadata://summary"
    
    @property
    def name(self) -> str:
        return "元数据摘要"
    
    @property
    def description(self) -> str:
        return "数据库元数据的统计摘要信息"
    
    @property
    def mime_type(self) -> str:
        return "application/json"
    
    async def read(self) -> str:
        """返回元数据摘要"""
        summary = {
            "database": "singa_bi",
            "generated_at": None
        }
        
        if self.online_dict:
            summary["online_dictionary"] = {
                "total_tables": len(self.online_dict.dictionary),
                "tables": list(self.online_dict.dictionary.keys())[:50]  # 前50个
            }
        
        if self.metadata:
            tables = self.metadata.metadata.get('tables', [])
            summary["bi_metadata"] = {
                "total_tables": len(tables),
                "business_domains": list(self.metadata.domain_index.keys()),
                "pii_tables_count": len(self.metadata.pii_tables)
            }
        
        return json.dumps(summary, ensure_ascii=False, indent=2)


class BusinessDomainResource(BaseResource):
    """业务域资源"""
    
    def __init__(self, domain: str):
        self.domain = domain
        try:
            self.metadata = SingaBIMetadataModule()
        except:
            self.metadata = None
    
    @property
    def uri(self) -> str:
        return f"metadata://domain/{self.domain}"
    
    @property
    def name(self) -> str:
        return f"业务域: {self.domain}"
    
    @property
    def description(self) -> str:
        return f"{self.domain} 业务域的所有表和字段信息"
    
    @property
    def mime_type(self) -> str:
        return "application/json"
    
    async def read(self) -> str:
        """返回指定业务域的表信息"""
        if not self.metadata:
            return json.dumps({"error": "元数据模块未加载"}, ensure_ascii=False)
        
        table_names = self.metadata.domain_index.get(self.domain, [])
        tables_info = []
        
        for table_name in table_names:
            table = self.metadata.table_index.get(table_name)
            if table:
                tables_info.append({
                    "table_name": table["table_name"],
                    "table_comment": table.get("table_comment", ""),
                    "granularity": table.get("granularity", ""),
                    "column_count": len(table.get("columns", [])),
                    "has_pii": table_name in self.metadata.pii_tables
                })
        
        return json.dumps({
            "domain": self.domain,
            "table_count": len(tables_info),
            "tables": tables_info
        }, ensure_ascii=False, indent=2)


class MetadataResources:
    """元数据资源集合"""
    
    @classmethod
    def get_all_resources(cls) -> list[BaseResource]:
        """获取所有元数据资源"""
        resources = [
            OnlineDictionaryResource(),
            SingaBIMetadataResource(),
            MetadataSummaryResource()
        ]
        
        # 添加业务域资源
        try:
            metadata = SingaBIMetadataModule()
            for domain in metadata.domain_index.keys():
                resources.append(BusinessDomainResource(domain))
        except:
            pass
        
        return resources
