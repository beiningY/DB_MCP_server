"""
MCP Server 并发性能测试

测试项目：
1. 连接池最大并发连接数
2. MCP 服务器最大并发请求处理能力
3. 不同并发级别下的响应时间
4. 连接池在高并发下的表现

运行方式：
    python tests/test_concurrency.py

环境变量配置（在 .env 文件中）：
    # 数据库配置
    DB_HOST=localhost
    DB_PORT=3306
    DB_USERNAME=root
    DB_PASSWORD=
    DB_DATABASE=mydb

    # 连接池配置
    DB_POOL_SIZE=5
    DB_MAX_OVERFLOW=10
    DB_POOL_TIMEOUT=30

环境要求：
    - MCP Server 正在运行
    - 数据库可访问
"""

import asyncio
import time
import statistics
import json
from typing import List, Dict, Any
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

import httpx
from sqlalchemy import text
from tqdm import tqdm

# ============================================================================
# 配置（从环境变量读取）
# ============================================================================

# MCP 服务器配置
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
HEALTH_URL = f"{MCP_SERVER_URL}/health"

# 数据库配置（从环境变量读取）
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USERNAME = os.getenv("DB_USERNAME", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DATABASE = os.getenv("DB_DATABASE", "information_schema")

# 连接池配置（从环境变量读取）
def _get_int_env(key: str, default: int) -> int:
    """从环境变量读取整数配置"""
    try:
        value = os.getenv(key, str(default))
        return int(value)
    except (ValueError, TypeError):
        return default

DEFAULT_POOL_SIZE = _get_int_env("DB_POOL_SIZE", 5)
DEFAULT_MAX_OVERFLOW = _get_int_env("DB_MAX_OVERFLOW", 10)
DEFAULT_POOL_TIMEOUT = _get_int_env("DB_POOL_TIMEOUT", 30)

# 理论最大并发 = pool_size + max_overflow
THEORETICAL_MAX_CONCURRENCY = DEFAULT_POOL_SIZE + DEFAULT_MAX_OVERFLOW

# 测试配置
TEST_QUERIES = [
    "SELECT COUNT(*) as count FROM information_schema.tables",
    "SELECT table_name, table_rows FROM information_schema.tables LIMIT 5",
    "SELECT 1 as test",
]

# 测试场景
TEST_SCENARIOS = [
    {"name": "低并发", "concurrent": 5, "requests": 50},
    {"name": "中等并发", "concurrent": 15, "requests": 150},
    {"name": "高并发", "concurrent": 30, "requests": 300},
    {"name": "极限并发", "concurrent": 50, "requests": 500},
    {"name": "压力测试", "concurrent": 100, "requests": 1000},
]

# ============================================================================
# 打印配置信息
# ============================================================================

def print_config():
    """打印当前配置"""
    print("\n" + "="*60)
    print("当前配置（来自环境变量）")
    print("="*60)
    print(f"MCP 服务器: {MCP_SERVER_URL}")
    print(f"数据库: {DB_HOST}:{DB_PORT}/{DB_DATABASE}")
    print(f"用户: {DB_USERNAME}")
    print("-"*60)
    print(f"连接池配置:")
    print(f"  DB_POOL_SIZE = {DEFAULT_POOL_SIZE}")
    print(f"  DB_MAX_OVERFLOW = {DEFAULT_MAX_OVERFLOW}")
    print(f"  DB_POOL_TIMEOUT = {DEFAULT_POOL_TIMEOUT}")
    print(f"  理论最大并发 = {THEORETICAL_MAX_CONCURRENCY}")
    print("="*60)

# ============================================================================
# 连接池测试
# ============================================================================


async def test_connection_pool_direct(concurrent: int = 20) -> Dict[str, Any]:
    """
    直接测试连接池的最大并发能力

    绕过 MCP 层，直接使用 SQLAlchemy 连接池测试。
    每个任务使用独立的连接（pool_size=1, max_overflow=0）

    Args:
        concurrent: 并发连接数

    Returns:
        测试结果字典
    """
    print(f"\n{'='*60}")
    print(f"连接池直接测试 - 并发数: {concurrent}")
    print(f"{'='*60}")

    from sqlalchemy import create_engine
    from urllib.parse import quote_plus

    # 构建连接 URL
    safe_password = quote_plus(DB_PASSWORD)
    db_url = f"mysql+pymysql://{DB_USERNAME}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_DATABASE}?charset=utf8mb4"

    results = {
        "concurrent": concurrent,
        "success": 0,
        "failed": 0,
        "timeouts": 0,
        "total_time": 0,
        "avg_time": 0,
        "min_time": float('inf'),
        "max_time": 0,
        "errors": [],
    }

    async def run_query(worker_id: int) -> Dict[str, Any]:
        """单个工作线程的查询任务"""
        start_time = time.time()
        try:
            # 为每个任务创建独立的引擎
            engine = create_engine(
                db_url,
                pool_size=1,
                max_overflow=0,
                pool_timeout=30,
                pool_pre_ping=True,
            )

            with engine.connect() as conn:
                result = conn.execute(text("SELECT SLEEP(0.1), CONNECTION_ID() as conn_id"))
                row = result.fetchone()
                elapsed = time.time() - start_time
                engine.dispose()

                return {
                    "worker_id": worker_id,
                    "success": True,
                    "time": elapsed,
                    "conn_id": row[1] if row else None,
                }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "worker_id": worker_id,
                "success": False,
                "time": elapsed,
                "error": str(e),
            }

    # 并发执行
    start_time = time.time()
    tasks = [run_query(i) for i in range(concurrent)]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time

    # 统计结果
    times = []
    conn_ids = set()

    for r in task_results:
        if isinstance(r, Exception):
            results["failed"] += 1
            results["errors"].append(str(r))
        elif r["success"]:
            results["success"] += 1
            times.append(r["time"])
            if r.get("conn_id"):
                conn_ids.add(r["conn_id"])
        else:
            results["failed"] += 1
            results["errors"].append(r.get("error", "Unknown error"))

    if times:
        results["total_time"] = total_time
        results["avg_time"] = statistics.mean(times)
        results["min_time"] = min(times)
        results["max_time"] = max(times)

    print(f"成功: {results['success']}/{concurrent}")
    print(f"失败: {results['failed']}/{concurrent}")
    print(f"总耗时: {results['total_time']:.2f}s")
    print(f"平均响应时间: {results['avg_time']:.3f}s")
    print(f"唯一连接数: {len(conn_ids)}")

    return results


async def test_connection_pool_shared(concurrent: int = 20) -> Dict[str, Any]:
    """
    测试共享连接池的并发能力

    使用实际项目中的连接池配置（从环境变量读取）。

    Args:
        concurrent: 并发连接数

    Returns:
        测试结果字典
    """
    print(f"\n{'='*60}")
    print(f"共享连接池测试 - 并发数: {concurrent}")
    print(f"(pool_size={DEFAULT_POOL_SIZE}, max_overflow={DEFAULT_MAX_OVERFLOW})")
    print(f"{'='*60}")

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from db_mcp.connection_pool import get_engine, get_pool_stats, close_all_pools

    # 清理旧的连接池
    close_all_pools()

    results = {
        "concurrent": concurrent,
        "pool_size": DEFAULT_POOL_SIZE,
        "max_overflow": DEFAULT_MAX_OVERFLOW,
        "success": 0,
        "failed": 0,
        "timeouts": 0,
        "total_time": 0,
        "avg_time": 0,
        "min_time": float('inf'),
        "max_time": 0,
        "pool_stats_before": {},
        "pool_stats_after": {},
        "errors": [],
    }

    async def run_query(worker_id: int) -> Dict[str, Any]:
        """单个工作线程的查询任务"""
        start_time = time.time()
        try:
            # 使用环境变量中的连接池配置
            engine = get_engine(
                DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE,
                pool_size=DEFAULT_POOL_SIZE,
                max_overflow=DEFAULT_MAX_OVERFLOW,
                pool_timeout=DEFAULT_POOL_TIMEOUT,
            )

            with engine.connect() as conn:
                result = conn.execute(text("SELECT SLEEP(0.1), CONNECTION_ID() as conn_id"))
                row = result.fetchone()
                elapsed = time.time() - start_time

                return {
                    "worker_id": worker_id,
                    "success": True,
                    "time": elapsed,
                    "conn_id": row[1] if row else None,
                }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "worker_id": worker_id,
                "success": False,
                "time": elapsed,
                "error": str(e),
            }

    # 获取初始连接池状态
    results["pool_stats_before"] = get_pool_stats()

    # 并发执行
    start_time = time.time()
    tasks = [run_query(i) for i in range(concurrent)]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time

    # 获取结束后的连接池状态
    results["pool_stats_after"] = get_pool_stats()

    # 统计结果
    times = []
    conn_ids = set()

    for r in task_results:
        if isinstance(r, Exception):
            results["failed"] += 1
            results["errors"].append(str(r))
        elif r["success"]:
            results["success"] += 1
            times.append(r["time"])
            if r.get("conn_id"):
                conn_ids.add(r["conn_id"])
        else:
            results["failed"] += 1
            results["errors"].append(r.get("error", "Unknown error"))

    if times:
        results["total_time"] = total_time
        results["avg_time"] = statistics.mean(times)
        results["min_time"] = min(times)
        results["max_time"] = max(times)

    print(f"成功: {results['success']}/{concurrent}")
    print(f"失败: {results['failed']}/{concurrent}")
    print(f"总耗时: {results['total_time']:.2f}s")
    print(f"平均响应时间: {results['avg_time']:.3f}s")
    print(f"唯一连接数: {len(conn_ids)}")

    return results


# ============================================================================
# MCP HTTP 端点测试
# ============================================================================


async def test_mcp_health() -> bool:
    """检查 MCP 服务器健康状态"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(HEALTH_URL)
            return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False


async def test_mcp_http_endpoint(concurrent: int = 10, requests: int = 100) -> Dict[str, Any]:
    """
    测试 MCP HTTP 端点的并发处理能力

    Args:
        concurrent: 并发数
        requests: 总请求数

    Returns:
        测试结果字典
    """
    print(f"\n{'='*60}")
    print(f"MCP HTTP 端点测试 - 并发: {concurrent}, 总请求: {requests}")
    print(f"{'='*60}")

    results = {
        "concurrent": concurrent,
        "total_requests": requests,
        "success": 0,
        "failed": 0,
        "total_time": 0,
        "requests_per_second": 0,
        "avg_time": 0,
        "min_time": float('inf'),
        "max_time": 0,
        "p50_time": 0,
        "p95_time": 0,
        "p99_time": 0,
        "errors": [],
    }

    semaphore = asyncio.Semaphore(concurrent)
    times = []
    errors = []

    async def make_request(request_id: int) -> Dict[str, Any]:
        """单个请求任务"""
        async with semaphore:
            start_time = time.time()
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(HEALTH_URL)
                    elapsed = time.time() - start_time

                    return {
                        "request_id": request_id,
                        "success": response.status_code == 200,
                        "time": elapsed,
                        "status": response.status_code,
                    }
            except Exception as e:
                elapsed = time.time() - start_time
                return {
                    "request_id": request_id,
                    "success": False,
                    "time": elapsed,
                    "error": str(e),
                }

    # 执行请求
    start_time = time.time()
    with tqdm(total=requests, desc=f"并发 {concurrent}") as pbar:
        # 分批执行
        batch_size = concurrent
        for i in range(0, requests, batch_size):
            batch_size_actual = min(batch_size, requests - i)
            tasks = [make_request(i + j) for j in range(batch_size_actual)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in batch_results:
                if isinstance(r, Exception):
                    results["failed"] += 1
                    errors.append(str(r))
                elif r["success"]:
                    results["success"] += 1
                    times.append(r["time"])
                else:
                    results["failed"] += 1
                    errors.append(r.get("error", f"HTTP {r.get('status')}"))

                pbar.update(1)

    total_time = time.time() - start_time
    results["total_time"] = total_time
    results["requests_per_second"] = requests / total_time if total_time > 0 else 0

    if times:
        times_sorted = sorted(times)
        results["avg_time"] = statistics.mean(times)
        results["min_time"] = min(times)
        results["max_time"] = max(times)
        results["p50_time"] = times_sorted[int(len(times) * 0.5)]
        results["p95_time"] = times_sorted[int(len(times) * 0.95)]
        results["p99_time"] = times_sorted[int(len(times) * 0.99)]

    results["errors"] = errors[:10]  # 只保留前10个错误

    print(f"成功: {results['success']}/{requests}")
    print(f"失败: {results['failed']}/{requests}")
    print(f"总耗时: {results['total_time']:.2f}s")
    print(f"QPS: {results['requests_per_second']:.2f}")
    print(f"P50 响应时间: {results['p50_time']:.3f}s")
    print(f"P95 响应时间: {results['p95_time']:.3f}s")

    return results


# ============================================================================
# 完整的并发测试套件
# ============================================================================


async def run_full_test_suite():
    """运行完整的并发测试套件"""

    # 打印配置
    print_config()

    print("\n" + "="*70)
    print(" " * 15 + "MCP Server 并发性能测试")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"理论最大连接池并发: {THEORETICAL_MAX_CONCURRENCY}")
    print("="*70)

    # 检查服务器健康状态
    print("\n[1/5] 检查服务器状态...")
    if not await test_mcp_health():
        print("错误: MCP 服务器未响应，请确保服务器正在运行")
        return
    print("服务器状态: 健康")

    all_results = {
        "test_time": datetime.now().isoformat(),
        "config": {
            "mcp_server": MCP_SERVER_URL,
            "database": f"{DB_HOST}:{DB_PORT}/{DB_DATABASE}",
            "pool_size": DEFAULT_POOL_SIZE,
            "max_overflow": DEFAULT_MAX_OVERFLOW,
            "theoretical_max": THEORETICAL_MAX_CONCURRENCY,
        },
        "results": {},
    }

    # 测试 1: 连接池直接测试（递增并发）
    print("\n[2/5] 连接池直接测试（递增并发）...")
    pool_direct_results = []
    for concurrency in [5, 10, 15, 20, 30]:
        result = await test_connection_pool_direct(concurrency)
        pool_direct_results.append(result)
        # 等待一下让连接释放
        await asyncio.sleep(1)
    all_results["results"]["pool_direct"] = pool_direct_results

    # 测试 2: 共享连接池测试
    print("\n[3/5] 共享连接池测试...")
    pool_shared_results = []
    # 测试从理论最大值以下到超过理论最大值
    test_concurrencies = [
        DEFAULT_POOL_SIZE,           # 核心连接数
        THEORETICAL_MAX_CONCURRENCY, # 理论最大值
        THEORETICAL_MAX_CONCURRENCY + 10,  # 超过理论值
        THEORETICAL_MAX_CONCURRENCY + 20,  # 更多超过
    ]
    for concurrency in test_concurrencies:
        result = await test_connection_pool_shared(concurrency)
        pool_shared_results.append(result)
        await asyncio.sleep(1)
    all_results["results"]["pool_shared"] = pool_shared_results

    # 测试 3: MCP HTTP 端点测试
    print("\n[4/5] MCP HTTP 端点并发测试...")
    http_results = []
    for scenario in TEST_SCENARIOS[:4]:  # 只运行前4个场景
        result = await test_mcp_http_endpoint(
            concurrent=scenario["concurrent"],
            requests=scenario["requests"]
        )
        result["scenario"] = scenario["name"]
        http_results.append(result)
        await asyncio.sleep(2)
    all_results["results"]["http_endpoint"] = http_results

    # 生成报告
    print("\n[5/5] 生成测试报告...")
    generate_report(all_results)

    return all_results


def generate_report(results: Dict[str, Any]):
    """生成测试报告"""
    report = []
    report.append("\n" + "="*70)
    report.append(" " * 20 + "测试结果汇总")
    report.append("="*70)

    # 连接池配置
    pool_size = results["config"]["pool_size"]
    max_overflow = results["config"]["max_overflow"]
    theoretical_max = results["config"]["theoretical_max"]

    # 连接池直接测试结果
    report.append("\n## 连接池直接测试")
    report.append("-" * 70)
    report.append(f"{'并发数':<10} {'成功':<10} {'失败':<10} {'平均时间':<15} {'总时间':<10}")
    report.append("-" * 70)

    for r in results["results"]["pool_direct"]:
        report.append(
            f"{r['concurrent']:<10} {r['success']:<10} {r['failed']:<10} "
            f"{r['avg_time']:<15.3f} {r['total_time']:<10.2f}"
        )

    # 共享连接池测试结果
    report.append("\n## 共享连接池测试")
    report.append(f"连接池配置: pool_size={pool_size}, max_overflow={max_overflow}")
    report.append(f"理论最大并发: {theoretical_max}")
    report.append("-" * 70)
    report.append(f"{'并发数':<10} {'成功':<10} {'失败':<10} {'平均时间':<15} {'借用连接':<10}")
    report.append("-" * 70)

    for r in results["results"]["pool_shared"]:
        conn_stats = r.get('pool_stats_after', {})
        checked_out = 0
        for pool in conn_stats.values():
            checked_out = max(checked_out, pool.get('checked_out', 0))

        status = "✓" if r['failed'] == 0 else "✗"
        report.append(
            f"{r['concurrent']:<10} {r['success']:<10} {r['failed']:<10} "
            f"{r['avg_time']:<15.3f} {checked_out:<10} {status}"
        )

    # HTTP 端点测试结果
    report.append("\n## MCP HTTP 端点测试")
    report.append("-" * 70)
    report.append(
        f"{'场景':<15} {'并发':<8} {'请求':<8} {'QPS':<10} {'P50':<10} {'P95':<10}"
    )
    report.append("-" * 70)

    for r in results["results"]["http_endpoint"]:
        report.append(
            f"{r['scenario']:<15} {r['concurrent']:<8} {r['total_requests']:<8} "
            f"{r['requests_per_second']:<10.2f} {r['p50_time']:<10.3f} {r['p95_time']:<10.3f}"
        )

    # 结论
    report.append("\n## 测试结论")
    report.append("-" * 70)

    # 分析连接池容量
    pool_shared = results["results"]["pool_shared"]
    # 找到所有成功的测试中最大的并发数
    successful_tests = [r for r in pool_shared if r['failed'] == 0]
    max_successful = max([r['concurrent'] for r in successful_tests]) if successful_tests else 0

    report.append(f"1. 连接池测试结果:")
    report.append(f"   - 配置: pool_size={pool_size}, max_overflow={max_overflow}")
    report.append(f"   - 理论最大并发: {theoretical_max}")
    report.append(f"   - 实际最大稳定并发: {max_successful}")

    if max_successful >= theoretical_max:
        report.append(f"   - 结论: ✓ 达到理论最大值")
    else:
        report.append(f"   - 结论: ✗ 低于理论值 {theoretical_max - max_successful}")

    # 检查超过理论值的情况
    overflow_tests = [r for r in pool_shared if r['concurrent'] > theoretical_max]
    if overflow_tests:
        report.append(f"\n2. 超过理论并发测试:")
        for r in overflow_tests:
            status = "成功" if r['failed'] == 0 else f"失败 {r['failed']} 个"
            report.append(f"   - 并发 {r['concurrent']}: {status}")

    # 分析 HTTP 处理能力
    http_results = results["results"]["http_endpoint"]
    max_qps = max([r['requests_per_second'] for r in http_results])
    report.append(f"\n3. MCP 服务器 HTTP 处理能力:")
    report.append(f"   - 最大 QPS: {max_qps:.2f}")

    print("\n".join(report))

    # 保存到文件
    report_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(
        report_dir,
        f"concurrency_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n详细结果已保存到: {report_file}")


# ============================================================================
# 主入口
# ============================================================================


if __name__ == "__main__":
    asyncio.run(run_full_test_suite())
