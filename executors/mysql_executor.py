"""
MySQL 直连执行器
通过 SQLAlchemy 直接连接 MySQL 数据库执行查询
"""

import os
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

from .base import SQLExecutor, ExecutionResult


class MySQLExecutor(SQLExecutor):
    """MySQL 直连执行器"""
    
    @property
    def name(self) -> str:
        return "mysql_direct"
    
    @property
    def description(self) -> str:
        return "MySQL 直连执行器：通过 SQLAlchemy 直接连接数据库，适合快速查询"
    
    def _initialize(self):
        """初始化数据库连接"""
        # 从配置或环境变量获取连接字符串
        db_url = self.config.get('db_url') or os.getenv('DB_URL')
        
        if not db_url:
            raise ValueError("缺少数据库连接配置：请提供 db_url 或设置 DB_URL 环境变量")
        
        try:
            # 创建数据库引擎
            self.engine: Engine = create_engine(
                db_url,
                pool_size=self.config.get('pool_size', 5),
                max_overflow=self.config.get('max_overflow', 10),
                pool_pre_ping=True,  # 自动检测失效连接
                pool_recycle=3600,   # 1小时回收连接
                echo=self.config.get('echo', False)  # 是否打印 SQL
            )
            
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            print(f"✓ MySQL 连接成功: {self.engine.url.database}")
        
        except Exception as e:
            print(f"❌ MySQL 连接失败: {e}")
            raise
    
    async def execute(
        self,
        sql: str,
        timeout: int = 30,
        limit: Optional[int] = 10000
    ) -> ExecutionResult:
        """
        执行 SQL 查询
        
        Args:
            sql: SQL 查询语句
            timeout: 超时时间（秒）
            limit: 最大返回行数
        
        Returns:
            执行结果
        """
        start_time = time.time()
        
        # 验证 SQL 安全性
        is_valid, error_msg = self.validate_sql(sql)
        if not is_valid:
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=0,
                sql=sql,
                error=error_msg
            )
        
        # 添加 LIMIT 子句（如果没有）
        sql_with_limit = self._add_limit(sql, limit)
        
        try:
            # 执行查询
            with self.engine.connect() as conn:
                # 设置查询超时
                if timeout:
                    conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}"))
                
                # 使用 pandas 读取结果（更方便）
                df = pd.read_sql(sql_with_limit, conn)
                
                execution_time = time.time() - start_time
                
                # 转换为标准格式
                columns = df.columns.tolist()
                rows = df.to_dict('records')
                
                return ExecutionResult(
                    success=True,
                    rows=rows,
                    columns=columns,
                    row_count=len(rows),
                    execution_time=execution_time,
                    sql=sql,
                    metadata={
                        'executor': self.name,
                        'database': self.engine.url.database,
                        'limited': limit is not None and len(rows) == limit
                    }
                )
        
        except SQLAlchemyError as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=execution_time,
                sql=sql,
                error=self.format_error(e)
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=execution_time,
                sql=sql,
                error=f"未知错误: {self.format_error(e)}"
            )
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False
    
    def _add_limit(self, sql: str, limit: Optional[int]) -> str:
        """
        为 SQL 添加 LIMIT 子句（如果需要）
        
        Args:
            sql: 原始 SQL
            limit: 限制行数
        
        Returns:
            添加 LIMIT 后的 SQL
        """
        if limit is None:
            return sql
        
        sql_upper = sql.upper().strip()
        
        # 如果已经有 LIMIT，不添加
        if 'LIMIT' in sql_upper:
            return sql
        
        # 添加 LIMIT
        return f"{sql.rstrip(';')} LIMIT {limit}"
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表信息（同步方法）
        
        Args:
            table_name: 表名
        
        Returns:
            表信息字典
        """
        try:
            with self.engine.connect() as conn:
                # 获取表结构
                result = conn.execute(text(f"DESCRIBE {table_name}"))
                columns = result.fetchall()
                
                # 获取表行数
                count_result = conn.execute(text(f"SELECT COUNT(*) as cnt FROM {table_name}"))
                row_count = count_result.fetchone()[0]
                
                return {
                    'table_name': table_name,
                    'columns': [
                        {
                            'name': col[0],
                            'type': col[1],
                            'null': col[2],
                            'key': col[3],
                            'default': col[4],
                            'extra': col[5]
                        }
                        for col in columns
                    ],
                    'row_count': row_count
                }
        except Exception as e:
            return {'error': self.format_error(e)}
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            print("✓ MySQL 连接已关闭")
