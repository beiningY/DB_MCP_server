"""
Redash API 执行器
通过 Redash API 执行 SQL 查询（支持权限管理和审计）
"""

import os
import sys
import time
import asyncio
from typing import Any, Dict, List, Optional
import httpx

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from .base import SQLExecutor, ExecutionResult
from logger_config import get_executor_logger

logger = get_executor_logger()


class RedashExecutor(SQLExecutor):
    """Redash API 执行器"""
    
    @property
    def name(self) -> str:
        return "redash_api"
    
    @property
    def description(self) -> str:
        return "Redash API 执行器：通过 Redash 平台执行查询，支持权限管理和审计"
    
    def _initialize(self):
        """初始化 Redash 客户端"""
        # 从配置或环境变量获取
        self.redash_url = (
            self.config.get('redash_url') or 
            os.getenv('REDASH_URL')
        )
        self.api_key = (
            self.config.get('api_key') or 
            os.getenv('REDASH_API_KEY')
        )
        self.data_source_id = self.config.get('data_source_id', 1)  # 默认数据源
        
        if not self.redash_url or not self.api_key:
            raise ValueError("缺少 Redash 配置：请提供 redash_url 和 api_key")
        
        # 移除末尾斜杠
        self.redash_url = self.redash_url.rstrip('/')
        
        # 构建请求头
        self.headers = {
            'Authorization': f'Key {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # SSL 验证（内网可能需要关闭）
        self.verify_ssl = self.config.get('verify_ssl', False)
        
        logger.info(f"✓ Redash 客户端初始化成功: {self.redash_url}")
    
    async def execute(
        self,
        sql: str,
        timeout: int = 30,
        limit: Optional[int] = 10000
    ) -> ExecutionResult:
        """
        通过 Redash API 执行 SQL
        
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
            logger.warning(f"SQL 验证失败: {error_msg}")
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=0,
                sql=sql,
                error=error_msg
            )
        
        # 添加 LIMIT
        sql_with_limit = self._add_limit(sql, limit)
        
        try:
            logger.debug(f"通过 Redash 执行 SQL: {sql_with_limit[:200]}...")
            
            # 1. 创建临时查询
            query_id = await self._create_adhoc_query(sql_with_limit)
            logger.debug(f"创建查询成功，query_id: {query_id}")
            
            # 2. 执行查询
            job_id = await self._execute_query(query_id)
            logger.debug(f"提交执行任务，job_id: {job_id}")
            
            # 3. 轮询查询状态
            result_data = await self._wait_for_result(job_id, timeout)
            
            execution_time = time.time() - start_time
            
            # 4. 解析结果
            rows, columns = self._parse_result(result_data)
            
            logger.info(f"Redash 查询成功，返回 {len(rows)} 行，耗时 {execution_time:.3f}s")
            
            return ExecutionResult(
                success=True,
                rows=rows,
                columns=columns,
                row_count=len(rows),
                execution_time=execution_time,
                sql=sql,
                metadata={
                    'executor': self.name,
                    'query_id': query_id,
                    'job_id': job_id,
                    'data_source_id': self.data_source_id
                }
            )
        
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Redash 查询超时（{timeout}秒）")
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=execution_time,
                sql=sql,
                error=f"查询超时（{timeout}秒）"
            )
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = self.format_error(e)
            logger.error(f"Redash 查询失败: {error_msg}")
            return ExecutionResult(
                success=False,
                rows=[],
                columns=[],
                row_count=0,
                execution_time=execution_time,
                sql=sql,
                error=error_msg
            )
    
    async def _create_adhoc_query(self, sql: str) -> int:
        """
        创建临时查询
        
        Args:
            sql: SQL 语句
        
        Returns:
            查询 ID
        """
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            payload = {
                'name': f'Agent Query {int(time.time())}',
                'query': sql,
                'data_source_id': self.data_source_id,
                'is_draft': False
            }
            
            response = await client.post(
                f'{self.redash_url}/api/queries',
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f'创建查询失败: {response.status_code} - {response.text}')
            
            data = response.json()
            return data['id']
    
    async def _execute_query(self, query_id: int) -> str:
        """
        执行查询
        
        Args:
            query_id: 查询 ID
        
        Returns:
            任务 ID
        """
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.post(
                f'{self.redash_url}/api/queries/{query_id}/results',
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f'执行查询失败: {response.status_code} - {response.text}')
            
            data = response.json()
            return data['job']['id']
    
    async def _wait_for_result(self, job_id: str, timeout: int) -> Dict[str, Any]:
        """
        等待查询完成并获取结果
        
        Args:
            job_id: 任务 ID
            timeout: 超时时间
        
        Returns:
            查询结果数据
        """
        start = time.time()
        
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            while time.time() - start < timeout:
                response = await client.get(
                    f'{self.redash_url}/api/jobs/{job_id}',
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code != 200:
                    raise Exception(f'获取任务状态失败: {response.status_code}')
                
                job_data = response.json()
                status = job_data['job']['status']
                
                if status == 3:  # 完成
                    query_result_id = job_data['job']['query_result_id']
                    return await self._get_query_result(query_result_id)
                
                elif status == 4:  # 失败
                    error = job_data['job'].get('error', '未知错误')
                    raise Exception(f'查询执行失败: {error}')
                
                # 等待一段时间后重试
                await asyncio.sleep(0.5)
            
            raise asyncio.TimeoutError(f'查询未在 {timeout} 秒内完成')
    
    async def _get_query_result(self, result_id: int) -> Dict[str, Any]:
        """
        获取查询结果
        
        Args:
            result_id: 结果 ID
        
        Returns:
            结果数据
        """
        async with httpx.AsyncClient(verify=self.verify_ssl) as client:
            response = await client.get(
                f'{self.redash_url}/api/query_results/{result_id}',
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f'获取查询结果失败: {response.status_code}')
            
            return response.json()
    
    def _parse_result(self, result_data: Dict[str, Any]) -> tuple[List[Dict], List[str]]:
        """
        解析 Redash 结果格式
        
        Args:
            result_data: Redash 返回的结果数据
        
        Returns:
            (行列表, 列名列表)
        """
        query_result = result_data.get('query_result', {})
        data = query_result.get('data', {})
        
        rows = data.get('rows', [])
        columns_info = data.get('columns', [])
        
        # 提取列名
        columns = [col['name'] for col in columns_info]
        
        return rows, columns
    
    async def test_connection(self) -> bool:
        """测试 Redash API 连接"""
        try:
            async with httpx.AsyncClient(verify=self.verify_ssl) as client:
                response = await client.get(
                    f'{self.redash_url}/api/session',
                    headers=self.headers,
                    timeout=5
                )
                success = response.status_code == 200
                if success:
                    logger.debug("Redash 连接测试成功")
                else:
                    logger.warning(f"Redash 连接测试失败，状态码: {response.status_code}")
                return success
        except Exception as e:
            logger.error(f"Redash 连接测试失败: {e}")
            return False
    
    def _add_limit(self, sql: str, limit: Optional[int]) -> str:
        """添加 LIMIT 子句"""
        if limit is None:
            return sql
        
        sql_upper = sql.upper().strip()
        if 'LIMIT' in sql_upper:
            return sql
        
        return f"{sql.rstrip(';')} LIMIT {limit}"
