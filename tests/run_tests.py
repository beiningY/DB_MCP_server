"""
便捷的测试运行脚本
运行所有测试并显示结果

使用方式：
    python tests/run_tests.py              # 运行所有测试
    python tests/run_tests.py --unit      # 只运行单元测试
    python tests/run_tests.py --integration # 只运行集成测试
    python tests/run_tests.py --cov       # 运行测试并显示覆盖率
"""

import sys
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_pytest(args: list) -> int:
    """
    运行 pytest

    Args:
        args: pytest 参数列表

    Returns:
        退出码
    """
    cmd = [sys.executable, "-m", "pytest"] + args
    print(f"运行: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="运行 DB MCP Server 测试")
    parser.add_argument("--unit", action="store_true", help="只运行单元测试")
    parser.add_argument("--integration", action="store_true", help="只运行集成测试")
    parser.add_argument("--cov", action="store_true", help="显示测试覆盖率")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--fast", action="store_true", help="跳过慢速测试")
    parser.add_argument("--file", "-f", help="运行特定的测试文件")

    args = parser.parse_args()

    # 构建 pytest 参数
    pytest_args = []

    if args.unit:
        pytest_args.extend(["-m", "unit"])
    elif args.integration:
        pytest_args.extend(["-m", "integration"])
    else:
        # 默认运行所有测试，跳过需要数据库和 LLM 的测试
        pytest_args.extend(["-m", "not requires_db and not requires_llm"])

    if args.fast:
        pytest_args.extend(["-m", "not slow"])

    if args.cov:
        pytest_args.extend([
            "--cov=db_mcp",
            "--cov=tools",
            "--cov-report=term-missing",
            "--cov-report=html",
        ])

    if args.file:
        pytest_args.append(args.file)

    if not args.verbose:
        pytest_args.append("-q")

    # 运行测试
    exit_code = run_pytest(pytest_args)

    # 打印总结
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✓ 所有测试通过！")
    else:
        print("✗ 有测试失败，请查看上面的输出")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
