"""
Mock SQL 执行器
用于测试，不需要真实的数据库连接
"""

import time
from typing import Any, Dict, List, Optional
from .base import SQLExecutor, ExecutionResult


class MockExecutor(SQLExecutor):
    """Mock 执行器 - 用于测试"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Mock 执行器"""
        super().__init__(config)
        self.execution_count = 0
        
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def description(self) -> str:
        return "Mock 执行器 - 用于测试，不需要真实数据库连接"
    
    def _initialize(self):
        """初始化（Mock 不需要实际连接）"""
        print("✓ Mock 执行器初始化成功")
    
    async def execute(
        self,
        sql: str,
        timeout: int = 30,
        limit: Optional[int] = 10000
    ) -> ExecutionResult:
        """
        Mock 执行 SQL（返回模拟数据）
        
        Args:
            sql: SQL 查询语句
            timeout: 超时时间（秒）
            limit: 最大返回行数
        
        Returns:
            执行结果
        """
        start_time = time.time()
        self.execution_count += 1
        
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
        
        # 模拟执行时间
        import asyncio
        await asyncio.sleep(0.1)
        
        execution_time = time.time() - start_time
        
        # 根据 SQL 内容返回不同的模拟数据
        sql_upper = sql.upper()
        
        # 1. 表数量查询
        if "COUNT" in sql_upper and "TABLES" in sql_upper:
            return ExecutionResult(
                success=True,
                rows=[{"count": 150}],
                columns=["count"],
                row_count=1,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
        
        # 2. 表列表查询
        elif "SHOW TABLES" in sql_upper or "TABLE_NAME" in sql_upper:
            return ExecutionResult(
                success=True,
                rows=[
                    {"table_name": "cyc_Loan_summary_app"},
                    {"table_name": "temp_rc_model_daily"},
                    {"table_name": "sgo_orders"},
                    {"table_name": "funnel"},
                    {"table_name": "transaction"}
                ],
                columns=["table_name"],
                row_count=5,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
        
        # 3. 放款数据查询
        elif "LOAN" in sql_upper or "cyc_Loan_summary_app" in sql:
            return ExecutionResult(
                success=True,
                rows=[
                    {
                        "order_id": "ORDER001",
                        "loan_amount": 1000000,
                        "pay_at": "2026-01-11 10:30:00",
                        "status": "paid"
                    },
                    {
                        "order_id": "ORDER002",
                        "loan_amount": 1500000,
                        "pay_at": "2026-01-11 14:20:00",
                        "status": "paid"
                    },
                    {
                        "order_id": "ORDER003",
                        "loan_amount": 800000,
                        "pay_at": "2026-01-11 16:45:00",
                        "status": "pending"
                    }
                ],
                columns=["order_id", "loan_amount", "pay_at", "status"],
                row_count=3,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
        
        # 4. 用户统计查询
        elif "USER" in sql_upper or "COUNT" in sql_upper:
            return ExecutionResult(
                success=True,
                rows=[
                    {"date": "2026-01-11", "user_count": 150},
                    {"date": "2026-01-10", "user_count": 142},
                    {"date": "2026-01-09", "user_count": 138}
                ],
                columns=["date", "user_count"],
                row_count=3,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
        
        # 5. 聚合统计查询
        elif "SUM" in sql_upper or "AVG" in sql_upper:
            return ExecutionResult(
                success=True,
                rows=[
                    {
                        "total_amount": 25000000,
                        "avg_amount": 1250000,
                        "count": 20
                    }
                ],
                columns=["total_amount", "avg_amount", "count"],
                row_count=1,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
        
        # 6. 默认返回简单数据
        else:
            return ExecutionResult(
                success=True,
                rows=[
                    {"id": 1, "value": "data1", "created_at": "2026-01-11 10:00:00"},
                    {"id": 2, "value": "data2", "created_at": "2026-01-11 11:00:00"},
                    {"id": 3, "value": "data3", "created_at": "2026-01-11 12:00:00"}
                ],
                columns=["id", "value", "created_at"],
                row_count=3,
                execution_time=execution_time,
                sql=sql,
                metadata={"executor": self.name, "mock": True}
            )
    
    async def test_connection(self) -> bool:
        """测试连接（Mock 总是返回 True）"""
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取 Mock 执行器统计信息"""
        return {
            "total_executions": self.execution_count,
            "executor_type": "mock"
        }
