"""
Dify 兼容层
提供与 dify_client 兼容的类和接口
"""

from typing import Dict, Any, Optional


class PluginContext:
    """插件上下文"""
    
    def __init__(self, **kwargs):
        self.data = kwargs
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.data.get(key, default)


class PluginCredentials(dict):
    """插件凭证"""
    
    def __init__(self, data: Dict[str, Any] = None):
        super().__init__(data or {})
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取凭证数据"""
        return super().get(key, default)


class PluginConfiguration(dict):
    """插件配置"""
    
    def __init__(self, data: Dict[str, Any] = None):
        super().__init__(data or {})
        
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置数据"""
        return super().get(key, default)


class Plugin:
    """插件基类"""
    
    def setup(self, context: PluginContext) -> None:
        """初始化插件"""
        pass
        
    def load_credentials(self, credentials: PluginCredentials) -> None:
        """加载凭证信息"""
        pass
        
    def load_configuration(self, configuration: PluginConfiguration) -> None:
        """加载配置信息"""
        pass
        
    def execute_tool(self, tool_name: str, tool_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        raise NotImplementedError("子类必须实现此方法")
        
    def cleanup(self) -> None:
        """清理资源"""
        pass 