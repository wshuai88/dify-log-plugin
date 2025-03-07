"""
Dify插件入口文件
连接Provider层和Tool层，实现插件功能
"""

import logging
import os
import re
from typing import Dict, Any, List, Optional

# 使用自定义兼容层
from dify_compat import Plugin, PluginContext, PluginCredentials, PluginConfiguration

from provider import LogProvider
from tools.tool_impl import LogTool

class LogPlugin(Plugin):
    """日志查看器插件"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.provider = None
        self.tool = None
        self.configuration = {}
        self._version = "1.0.0"
        
    def setup(self, context: PluginContext) -> None:
        """初始化插件"""
        self.logger.info(f"正在初始化日志查看器插件 v{self._version}...")
        
        # 初始化Provider
        self.provider = LogProvider()
        
        # 初始化Tool
        self.tool = LogTool(self.provider)
        
        self.logger.info("日志查看器插件初始化完成")
        
    def load_credentials(self, credentials: PluginCredentials) -> None:
        """加载凭证信息"""
        if not self.provider:
            raise RuntimeError("插件未初始化")
            
        try:
            # 验证凭证完整性
            required_fields = ['ip_address', 'username', 'password']
            for field in required_fields:
                if not credentials.get(field):
                    raise ValueError(f"缺少必要的凭证信息: {field}")
                    
            # 验证IP地址格式
            ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
            if not ip_pattern.match(credentials.get('ip_address', '')):
                self.logger.warning(f"IP地址格式可能不正确: {credentials.get('ip_address')}")
                
            # 加载凭证
            self.provider.load_credentials(credentials)
            
            # 验证凭证有效性
            validation_result = self.provider.validate_credentials()
            if not validation_result['is_valid']:
                error_message = validation_result.get('error', '未知错误')
                self.logger.error(f"凭证验证失败: {error_message}")
                raise ValueError(f"凭证验证失败: {error_message}")
                
            self.logger.info("凭证加载成功")
        except Exception as e:
            self.logger.error(f"加载凭证时出错: {str(e)}")
            raise
            
    def load_configuration(self, configuration: PluginConfiguration) -> None:
        """加载配置信息"""
        if not self.provider:
            raise RuntimeError("插件未初始化")
            
        try:
            # 设置默认配置
            default_config = {
                'default_log_path': '/var/log',
                'max_file_size': 1048576,  # 1MB
                'max_preview_lines': 50,
                'chunk_size': 5242880,  # 5MB
                'cache_size': 104857600,  # 100MB
                'connection_timeout': 30,
                'command_timeout': 60
            }
            
            # 合并用户配置
            config = {**default_config, **configuration}
            
            # 验证配置
            # 检查路径是否为绝对路径
            if not config['default_log_path'].startswith('/'):
                self.logger.warning(f"默认日志路径不是绝对路径: {config['default_log_path']}，使用默认值: /var/log")
                config['default_log_path'] = '/var/log'
                
            # 检查文件大小限制
            try:
                max_file_size = int(config['max_file_size'])
                if max_file_size <= 0:
                    self.logger.warning(f"最大文件大小必须大于0: {max_file_size}，使用默认值: 1048576")
                    config['max_file_size'] = 1048576
                elif max_file_size > 104857600:  # 100MB
                    self.logger.warning(f"最大文件大小超过限制: {max_file_size}，使用最大值: 104857600")
                    config['max_file_size'] = 104857600
            except (ValueError, TypeError):
                self.logger.warning(f"最大文件大小格式无效: {config['max_file_size']}，使用默认值: 1048576")
                config['max_file_size'] = 1048576
                
            # 检查预览行数
            try:
                max_preview_lines = int(config['max_preview_lines'])
                if max_preview_lines <= 0:
                    self.logger.warning(f"预览行数必须大于0: {max_preview_lines}，使用默认值: 50")
                    config['max_preview_lines'] = 50
                elif max_preview_lines > 1000:
                    self.logger.warning(f"预览行数超过限制: {max_preview_lines}，使用最大值: 1000")
                    config['max_preview_lines'] = 1000
            except (ValueError, TypeError):
                self.logger.warning(f"预览行数格式无效: {config['max_preview_lines']}，使用默认值: 50")
                config['max_preview_lines'] = 50
                
            # 设置配置
            self.configuration = config
            self.provider.set_configuration(config)
            
            self.logger.info("配置加载成功")
        except Exception as e:
            self.logger.error(f"加载配置时出错: {str(e)}")
            raise
            
    def execute_tool(self, tool_name: str, tool_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        if not self.tool:
            raise RuntimeError("插件未初始化")
            
        try:
            # 检查工具是否存在
            if not hasattr(self.tool, tool_name):
                raise ValueError(f"工具不存在: {tool_name}")
                
            # 获取工具方法
            tool_method = getattr(self.tool, tool_name)
            
            # 执行工具
            self.logger.info(f"执行工具: {tool_name}, 参数: {tool_parameters}")
            result = tool_method(tool_parameters)
            
            return result
        except Exception as e:
            self.logger.error(f"执行工具时出错: {str(e)}")
            return {
                'error': str(e)
            }
            
    def cleanup(self) -> None:
        """清理资源"""
        try:
            if self.provider:
                self.provider.close()
                
            self.logger.info("插件资源已清理")
        except Exception as e:
            self.logger.error(f"清理资源时出错: {str(e)}")

# 创建插件实例
plugin = LogPlugin() 