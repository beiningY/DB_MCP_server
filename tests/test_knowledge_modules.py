"""
知识模块测试
"""

import asyncio
import pytest
from knowledge import OnlineDictionaryModule, SingaBIMetadataModule, LightRAGClient


@pytest.mark.asyncio
async def test_online_dictionary():
    """测试在线字典模块"""
    module = OnlineDictionaryModule()
    
    # 测试搜索表
    result = await module.search_table("temp_rc_model_daily")
    assert result['total'] > 0
    print(f"✓ 找到表: {result['total']} 个")
    
    # 测试搜索字段
    result = await module.search_column("status")
    assert result['total'] > 0
    print(f"✓ 找到字段: {result['total']} 个")


@pytest.mark.asyncio
async def test_metadata_module():
    """测试 BI 元数据模块"""
    module = SingaBIMetadataModule()
    
    # 测试搜索表
    result = await module.search_tables("loan")
    assert result['total'] >= 0
    print(f"✓ 找到表: {result['total']} 个")
    
    # 测试按业务域搜索
    domains = module.get_all_domains()
    print(f"✓ 业务域: {domains}")
    
    if domains:
        result = await module.search_by_domain(domains[0])
        print(f"✓ {domains[0]} 域有 {result['total']} 个表")


@pytest.mark.asyncio
async def test_lightrag_client():
    """测试 LightRAG 客户端"""
    client = LightRAGClient()
    
    # 测试健康检查
    is_healthy = await client.health_check()
    if is_healthy:
        print("✓ LightRAG 服务可用")
        
        # 测试搜索
        result = await client.search("放款金额统计", mode="hybrid", top_k=3)
        print(f"✓ 搜索结果: {result.get('total', 0)} 个")
    else:
        print("⚠️ LightRAG 服务不可用（可能未启动）")


if __name__ == "__main__":
    print("=== 测试知识模块 ===\n")
    
    print("1. 测试在线字典模块")
    asyncio.run(test_online_dictionary())
    print()
    
    print("2. 测试 BI 元数据模块")
    asyncio.run(test_metadata_module())
    print()
    
    print("3. 测试 LightRAG 客户端")
    asyncio.run(test_lightrag_client())
    print()
    
    print("=== 所有测试完成 ===")
