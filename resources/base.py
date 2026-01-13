"""
资源基类和注册器
提供资源定义和注册的基础设施
"""
from abc import ABC, abstractmethod
from typing import Any
import mcp.types as types


class BaseResource(ABC):
    """资源基类"""
    
    @property
    @abstractmethod
    def uri(self) -> str:
        """资源 URI"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """资源名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """资源描述"""
        pass
    
    @property
    def mime_type(self) -> str:
        """MIME 类型，默认为 text/plain"""
        return "text/plain"
    
    @abstractmethod
    async def read(self) -> str:
        """读取资源内容"""
        pass
    
    def to_mcp_resource(self) -> types.Resource:
        """转换为 MCP Resource 类型"""
        return types.Resource(
            uri=self.uri,
            name=self.name,
            description=self.description,
            mimeType=self.mime_type
        )


class ResourceRegistry:
    """资源注册器 - 管理所有已注册的资源"""
    
    def __init__(self):
        self._resources: dict[str, BaseResource] = {}
    
    def register(self, resource: BaseResource) -> None:
        """注册资源"""
        self._resources[resource.uri] = resource
    
    def unregister(self, uri: str) -> None:
        """取消注册资源"""
        if uri in self._resources:
            del self._resources[uri]
    
    def get(self, uri: str) -> BaseResource | None:
        """获取资源"""
        return self._resources.get(uri)
    
    def list_resources(self) -> list[types.Resource]:
        """列出所有资源"""
        return [resource.to_mcp_resource() for resource in self._resources.values()]
    
    async def read_resource(self, uri: str) -> str:
        """读取资源"""
        resource = self.get(uri)
        if resource is None:
            raise ValueError(f"资源未找到: {uri}")
        return await resource.read()
    
    @property
    def resource_uris(self) -> list[str]:
        """获取所有资源 URI"""
        return list(self._resources.keys())


# 全局资源注册器实例
global_registry = ResourceRegistry()


def register_resource(resource: BaseResource) -> BaseResource:
    """资源注册装饰器"""
    global_registry.register(resource)
    return resource

