"""
Dify插件入口文件
连接Provider层和Tool层，实现插件功能
"""

import logging
import os
import re
from typing import Dict, Any, List, Optional

from dify_client import Plugin, PluginContext, PluginCredentials, PluginConfiguration

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
                'max_preview_lines': 50
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
                else:
                    config['max_file_size'] = max_file_size
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
                else:
                    config['max_preview_lines'] = max_preview_lines
            except (ValueError, TypeError):
                self.logger.warning(f"预览行数格式无效: {config['max_preview_lines']}，使用默认值: 50")
                config['max_preview_lines'] = 50
                
            self.configuration = config
            self.logger.info(f"配置加载成功: {config}")
        except Exception as e:
            self.logger.error(f"加载配置时出错: {str(e)}")
            raise
            
    def list_log_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出日志文件"""
        if not self.provider or not self.tool:
            raise RuntimeError("插件未初始化")
            
        try:
            # 设置默认参数
            if 'log_path' not in params or not params['log_path']:
                params['log_path'] = self.configuration.get('default_log_path', '/var/log')
                
            # 验证路径
            if not params['log_path'].startswith('/'):
                self.logger.warning(f"日志路径不是绝对路径: {params['log_path']}，使用默认值: {self.configuration.get('default_log_path', '/var/log')}")
                params['log_path'] = self.configuration.get('default_log_path', '/var/log')
                
            # 设置最大文件大小
            if 'max_file_size' not in params or not params['max_file_size']:
                params['max_file_size'] = self.configuration.get('max_file_size', 1048576)
                
            # 设置预览行数
            if 'max_preview_lines' not in params or not params['max_preview_lines']:
                params['max_preview_lines'] = self.configuration.get('max_preview_lines', 50)
                
            self.logger.info(f"列出日志文件: {params}")
            result = self.tool.list_log_files(params)
            return result
        except Exception as e:
            self.logger.error(f"列出日志文件时出错: {str(e)}")
            return {
                'error': f"列出日志文件时出错: {str(e)}",
                'file_list': [],
                'total_files': 0,
                'total_size': 0,
                'filtered_files': 0,
                'execution_time': 0
            }
            
    def read_log_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """读取日志文件内容"""
        if not self.provider or not self.tool:
            raise RuntimeError("插件未初始化")
            
        try:
            # 验证参数
            if 'file_path' not in params or not params['file_path']:
                raise ValueError("缺少必要的参数: file_path")
                
            # 验证路径
            if not params['file_path'].startswith('/'):
                raise ValueError(f"文件路径必须是绝对路径: {params['file_path']}")
                
            # 设置最大文件大小
            if 'max_file_size' not in params or not params['max_file_size']:
                params['max_file_size'] = self.configuration.get('max_file_size', 1048576)
                
            # 设置预览行数
            if 'max_preview_lines' not in params or not params['max_preview_lines']:
                params['max_preview_lines'] = self.configuration.get('max_preview_lines', 50)
                
            # 验证搜索模式
            if 'search_pattern' in params and params['search_pattern']:
                try:
                    re.compile(params['search_pattern'])
                except re.error:
                    self.logger.warning(f"搜索模式无效: {params['search_pattern']}，将被忽略")
                    params['search_pattern'] = None
                    
            self.logger.info(f"读取日志文件: {params['file_path']}")
            result = self.tool.read_log_file(params)
            return result
        except Exception as e:
            self.logger.error(f"读取日志文件时出错: {str(e)}")
            return {
                'error': f"读取日志文件时出错: {str(e)}",
                'content': '',
                'preview': '',
                'matches': [],
                'total_lines': 0,
                'is_truncated': False,
                'encoding': 'unknown',
                'is_binary': False
            }
            
    def download_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """下载日志文件"""
        if not self.provider or not self.tool:
            raise RuntimeError("插件未初始化")
            
        try:
            # 验证参数
            if 'file_path' not in params or not params['file_path']:
                raise ValueError("缺少必要的参数: file_path")
                
            # 验证路径
            if not params['file_path'].startswith('/'):
                raise ValueError(f"文件路径必须是绝对路径: {params['file_path']}")
                
            # 设置最大下载大小
            if 'max_download_size' not in params or not params['max_download_size']:
                params['max_download_size'] = 10485760  # 默认10MB
                
            # 验证下载大小限制
            try:
                max_download_size = int(params['max_download_size'])
                if max_download_size <= 0:
                    self.logger.warning(f"最大下载大小必须大于0: {max_download_size}，使用默认值: 10485760")
                    params['max_download_size'] = 10485760
                elif max_download_size > 104857600:  # 100MB
                    self.logger.warning(f"最大下载大小超过限制: {max_download_size}，使用最大值: 104857600")
                    params['max_download_size'] = 104857600
                else:
                    params['max_download_size'] = max_download_size
            except (ValueError, TypeError):
                self.logger.warning(f"最大下载大小格式无效: {params['max_download_size']}，使用默认值: 10485760")
                params['max_download_size'] = 10485760
                
            self.logger.info(f"下载日志文件: {params['file_path']}")
            result = self.tool.download_file(params)
            return result
        except Exception as e:
            self.logger.error(f"下载日志文件时出错: {str(e)}")
            return {
                'error': f"下载日志文件时出错: {str(e)}",
                'success': False,
                'file_name': os.path.basename(params.get('file_path', '')),
                'file_size': 0,
                'file_content_base64': ''
            }
            
    def tail_log_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查看日志文件末尾内容"""
        if not self.provider or not self.tool:
            raise RuntimeError("插件未初始化")
            
        try:
            # 验证参数
            if 'file_path' not in params or not params['file_path']:
                raise ValueError("缺少必要的参数: file_path")
                
            # 验证路径
            if not params['file_path'].startswith('/'):
                raise ValueError(f"文件路径必须是绝对路径: {params['file_path']}")
                
            # 设置行数
            if 'lines' not in params or not params['lines']:
                params['lines'] = 10
                
            # 验证行数
            try:
                lines = int(params['lines'])
                if lines <= 0:
                    self.logger.warning(f"行数必须大于0: {lines}，使用默认值: 10")
                    params['lines'] = 10
                elif lines > 1000:
                    self.logger.warning(f"行数超过限制: {lines}，使用最大值: 1000")
                    params['lines'] = 1000
                else:
                    params['lines'] = lines
            except (ValueError, TypeError):
                self.logger.warning(f"行数格式无效: {params['lines']}，使用默认值: 10")
                params['lines'] = 10
                
            self.logger.info(f"查看日志文件末尾: {params['file_path']}, 行数: {params['lines']}")
            result = self.tool.tail_log_file(params)
            return result
        except Exception as e:
            self.logger.error(f"查看日志文件末尾时出错: {str(e)}")
            return {
                'error': f"查看日志文件末尾时出错: {str(e)}",
                'lines': []
            }
            
    def cleanup(self) -> None:
        """清理资源"""
        self.logger.info("正在清理资源...")
        
        if self.provider:
            try:
                self.provider.close_connection()
            except Exception as e:
                self.logger.error(f"关闭连接时出错: {str(e)}")
                
        self.logger.info("资源清理完成")
        
# 创建插件实例
plugin = LogPlugin() 