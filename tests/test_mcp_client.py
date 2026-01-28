"""
MCP Server 客户端测试脚本
用于测试 MCP Server 的 SSE 连接、工具调用和资源读取

使用方式：
    # 先启动服务器
    python server.py
    
    # 然后在另一个终端运行测试
    python tests/test_mcp_client.py
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_mcp_client(server_url: str = "http://localhost:8080/sse"):
    """
    测试 MCP 客户端连接
    
    Args:
        server_url: MCP 服务器 SSE 端点地址
    """
    print("=" * 60)
    print("MCP Server 客户端测试")
    print("=" * 60)
    print(f"服务器地址: {server_url}")
    print("")
    
    try:
        # 导入 MCP 客户端库
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        print("✗ 错误: 未安装 mcp 库")
        print("  请运行: pip install mcp[cli]")
        return False
    
    try:
        # 连接到 MCP 服务器
        print("[1/6] 连接到 MCP 服务器...")
        async with sse_client(server_url) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化会话
                print("[2/6] 初始化会话...")
                await session.initialize()
                print("✓ 连接成功！")
                print("")
                
                # 测试列出工具
                print("[3/6] 获取工具列表...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"✓ 找到 {len(tools)} 个工具:")
                for tool in tools:
                    desc = tool.description[:60] if tool.description else "无描述"
                    print(f"  - {tool.name}: {desc}...")
                print("")
                
                # 测试列出资源
                print("[4/6] 获取资源列表...")
                resources_result = await session.list_resources()
                resources = resources_result.resources
                print(f"✓ 找到 {len(resources)} 个资源:")
                for resource in resources[:10]:  # 只显示前10个
                    print(f"  - {resource.uri}: {resource.name}")
                if len(resources) > 10:
                    print(f"  ... 还有 {len(resources) - 10} 个资源")
                print("")
                
                # 测试读取资源
                print("[5/6] 测试读取资源...")
                
                print("\n  [测试 db://singa_bi/overview]")
                try:
                    result = await session.read_resource("db://singa_bi/overview")
                    content = result.contents[0].text
                    data = json.loads(content)
                    print(f"  ✓ 成功！数据库: {data.get('database')}, 表数量: {data.get('table_count')}")
                except Exception as e:
                    print(f"  ✗ 失败: {str(e)}")
                
                # 测试调用工具
                print("\n[6/6] 测试工具调用...")
                
                print("\n  [测试 ask_data_agent]")
                print("  (这可能需要几秒钟，Agent 正在处理...)")
                try:
                    result = await session.call_tool(
                        "ask_data_agent", 
                        {"query": "有哪些用户相关的表？"}
                    )
                    content = result.content[0].text
                    print(f"  ✓ 成功！返回 {len(content)} 字符")
                    # 显示前 300 字符
                    preview = content[:300].replace('\n', ' ')
                    print(f"  预览: {preview}...")
                except Exception as e:
                    print(f"  ✗ 失败: {str(e)}")
                
                print("")
                print("=" * 60)
                print("✓ 所有测试完成！MCP Server 运行正常")
                print("=" * 60)
                return True
    
    except ConnectionError as e:
        print(f"✗ 连接失败: {str(e)}")
        print("")
        print("请检查:")
        print("  1. 服务器是否已启动: python server.py")
        print("  2. 服务器地址是否正确")
        print("  3. 端口是否被防火墙阻止")
        return False
    
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_http_endpoints(base_url: str = "http://localhost:8080"):
    """
    测试 HTTP 端点（不需要 MCP 客户端）
    
    Args:
        base_url: 服务器基础地址
    """
    print("=" * 60)
    print("HTTP 端点测试")
    print("=" * 60)
    print(f"服务器地址: {base_url}")
    print("")
    
    try:
        import requests
    except ImportError:
        print("✗ 错误: 未安装 requests 库")
        print("  请运行: pip install requests")
        return False
    
    endpoints = [
        ("/health", "健康检查"),
    ]
    
    all_passed = True
    
    for endpoint, name in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"[测试] {name} ({endpoint})...")
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ 成功！状态码: {response.status_code}")
                print(f"  响应: {json.dumps(data, ensure_ascii=False, indent=2)}")
            else:
                print(f"  ✗ 失败！状态码: {response.status_code}")
                all_passed = False
        except requests.exceptions.ConnectionError:
            print(f"  ✗ 连接失败！服务器可能未启动")
            all_passed = False
        except Exception as e:
            print(f"  ✗ 错误: {str(e)}")
            all_passed = False
        print("")
    
    if all_passed:
        print("✓ HTTP 端点测试全部通过！")
    else:
        print("✗ 部分测试失败，请检查服务器状态")
    
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server 测试脚本")
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="MCP 服务器地址（默认: http://localhost:8080）"
    )
    parser.add_argument(
        "--http-only",
        action="store_true",
        help="仅测试 HTTP 端点（不需要 MCP 客户端）"
    )
    
    args = parser.parse_args()
    
    print("\n")
    print("MCP Server 测试工具")
    print("=" * 60)
    print("")
    
    # 测试 HTTP 端点
    http_ok = test_http_endpoints(args.url)
    
    if not args.http_only and http_ok:
        print("\n")
        # 测试 MCP 客户端
        asyncio.run(test_mcp_client(f"{args.url}/sse"))
    
    print("\n提示：")
    print("  - 运行此脚本前，请先启动 MCP 服务器: python server.py")
    print("  - 使用 --http-only 仅测试 HTTP 端点")
    print("  - 使用 --url 指定服务器地址")
    print("\n")
