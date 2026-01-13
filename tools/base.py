"""
工具基类和注册器
提供工具定义和注册的基础设施
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar
import mcp.types as types


class BaseTool(ABC):
    """工具基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """输入参数 JSON Schema"""
        pass
    
    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> list[types.TextContent]:
        """执行工具"""
        pass
    
    def to_mcp_tool(self) -> types.Tool:
        """转换为 MCP Tool 类型"""
        return types.Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema
        )


class ToolRegistry:
    """工具注册器 - 管理所有已注册的工具"""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """取消注册工具"""
        if name in self._tools:
            del self._tools[name]
    
    def get(self, name: str) -> BaseTool | None:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> list[types.Tool]:
        """列出所有工具"""
        return [tool.to_mcp_tool() for tool in self._tools.values()]
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        """调用工具"""
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"工具未找到: {name}")
        return await tool.execute(arguments)
    
    @property
    def tool_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())


# 全局工具注册器实例
global_registry = ToolRegistry()


def register_tool(tool: BaseTool) -> BaseTool:
    """工具注册装饰器"""
    global_registry.register(tool)
    return tool

