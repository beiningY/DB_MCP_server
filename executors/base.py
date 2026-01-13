"""
SQL 执行器基类
定义所有 SQL 执行器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ExecutionResult:
    """SQL 执行结果"""
    success: bool
    rows: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time: float  # 秒
    sql: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'rows': self.rows,
            'columns': self.columns,
            'row_count': self.row_count,
            'execution_time': self.execution_time,
            'sql': self.sql,
            'error': self.error,
            'metadata': self.metadata or {}
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)
    
    def format_table(self, max_rows: int = 20) -> str:
        """格式化为表格文本"""
        if not self.success:
            return f"❌ 执行失败: {self.error}"
        
        if self.row_count == 0:
            return "✓ 查询成功，但没有返回结果"
        
        output = []
        output.append(f"✓ 查询成功，返回 {self.row_count} 行，耗时 {self.execution_time:.2f}秒\n")
        
        # 表头
        header = " | ".join(self.columns)
        separator = "-" * len(header)
        output.append(header)
        output.append(separator)
        
        # 数据行（限制显示数量）
        display_rows = self.rows[:max_rows]
        for row in display_rows:
            row_values = [str(row.get(col, '')) for col in self.columns]
            output.append(" | ".join(row_values))
        
        if self.row_count > max_rows:
            output.append(f"\n... 还有 {self.row_count - max_rows} 行未显示")
        
        return "\n".join(output)


class SQLExecutor(ABC):
    """SQL 执行器抽象基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化执行器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._initialize()
    
    @abstractmethod
    def _initialize(self):
        """初始化具体实现（建立连接、加载配置等）"""
        pass
    
    @abstractmethod
    async def execute(
        self,
        sql: str,
        timeout: int = 30,
        limit: Optional[int] = None
    ) -> ExecutionResult:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            timeout: 超时时间（秒）
            limit: 最大返回行数（None 表示不限制）
        
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        测试连接是否可用
        
        Returns:
            连接是否成功
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """执行器名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """执行器描述"""
        pass
    
    def validate_sql(self, sql: str) -> tuple[bool, Optional[str]]:
        """
        验证 SQL 语句的安全性
        
        Args:
            sql: SQL 语句
        
        Returns:
            (是否有效, 错误信息)
        """
        sql_upper = sql.upper().strip()
        
        # 基本安全检查
        dangerous_keywords = [
            'DROP TABLE', 'DROP DATABASE', 'TRUNCATE',
            'DELETE FROM', 'UPDATE', 'INSERT INTO',
            'CREATE TABLE', 'ALTER TABLE', 'GRANT', 'REVOKE'
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"SQL 包含危险操作: {keyword}"
        
        # 检查是否为 SELECT 语句
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            return False, "只允许执行 SELECT 查询语句"
        
        return True, None
    
    def format_error(self, error: Exception) -> str:
        """格式化错误信息"""
        error_type = type(error).__name__
        error_msg = str(error)
        return f"{error_type}: {error_msg}"
