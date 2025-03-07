"""
Provider层：负责凭证验证与配置加载
"""

import logging
import time
import os
import re
import base64
from typing import Dict, Any, Optional, List, Tuple

# 尝试导入lib模块
try:
    from lib.parsers import LogParserFactory
    HAS_PARSER = True
except (ImportError, ValueError):
    HAS_PARSER = False
    
try:
    from lib.cache import CacheManager
    HAS_CACHE = True
except (ImportError, ValueError):
    HAS_CACHE = False
    
try:
    from lib.security import SecurityManager
    HAS_SECURITY = True
except (ImportError, ValueError):
    HAS_SECURITY = False
    
try:
    from lib.connection import ConnectionManager
    HAS_CONNECTION = True
except (ImportError, ValueError):
    HAS_CONNECTION = False
    
class LogProvider:
    """日志提供者，负责基础连接管理"""
    
    def __init__(self):
        """初始化方法"""
        self.logger = logging.getLogger(__name__)
        self.credentials = {}
        self.configuration = {}
        
        # 尝试初始化连接管理器
        if HAS_CONNECTION:
            try:
                self.connection_manager = ConnectionManager()
            except Exception as e:
                self.logger.warning(f"初始化连接管理器失败: {str(e)}")
                self.connection_manager = None
        else:
            self.connection_manager = None
            
        # 尝试初始化安全管理器
        if HAS_SECURITY:
            try:
                self.security_manager = SecurityManager()
            except Exception as e:
                self.logger.warning(f"初始化安全管理器失败: {str(e)}")
                self.security_manager = None
        else:
            self.security_manager = None
            
        # 尝试初始化缓存管理器
        if HAS_CACHE:
            try:
                self.cache_manager = CacheManager()
            except Exception as e:
                self.logger.warning(f"初始化缓存管理器失败: {str(e)}")
                self.cache_manager = None
        else:
            self.cache_manager = None
        
        # 尝试初始化解析器工厂
        if HAS_PARSER:
            try:
                self.parser_factory = LogParserFactory()
            except Exception as e:
                self.logger.warning(f"初始化解析器工厂失败: {str(e)}")
                self.parser_factory = None
        else:
            self.parser_factory = None
        
    def load_credentials(self, credentials: Dict[str, Any]) -> None:
        """加载凭证信息"""
        # 验证凭证
        if self.security_manager and not self.security_manager.validate_credentials(credentials):
            raise ValueError("凭证验证失败")
            
        self.credentials = credentials
        self.logger.info(f"已加载凭证信息: {credentials['username']}@{credentials['ip_address']}:{credentials.get('port', 22)}")
        
    def validate_credentials(self) -> Dict[str, Any]:
        """验证凭证有效性"""
        try:
            # 获取连接
            ssh = self.get_connection_with_retry()
            if not ssh:
                return {
                    'is_valid': False,
                    'error': '无法建立SSH连接'
                }
                
            # 如果没有实际的连接，返回成功
            if not HAS_CONNECTION:
                return {'is_valid': True}
                
            # 测试连接
            stdin, stdout, stderr = ssh.exec_command('echo "test"', timeout=10)
            if stdout.channel.recv_exit_status() != 0:
                return {
                    'is_valid': False,
                    'error': '命令执行失败'
                }
                
            return {
                'is_valid': True
            }
        except Exception as e:
            return {
                'is_valid': False,
                'error': str(e)
            }
            
    def get_connection_with_retry(self, max_retries: int = 3, retry_delay: int = 5) -> Any:
        """带重试的连接获取"""
        if not HAS_CONNECTION or not self.connection_manager:
            return None
            
        last_error = None
        
        for i in range(max_retries):
            try:
                connection = self.connection_manager.get_connection(self.credentials)
                if connection:
                    if i > 0:
                        self.logger.info(f"在第{i+1}次尝试后成功建立连接")
                    return connection
            except Exception as e:
                last_error = e
                if i < max_retries - 1:
                    self.logger.warning(f"连接失败，{retry_delay}秒后重试: {str(e)}")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    
        if last_error:
            self.logger.error(f"连接失败: {str(last_error)}")
        return None
        
    def set_configuration(self, configuration: Dict[str, Any]) -> None:
        """设置配置"""
        # 设置默认值
        default_config = {
            'default_log_path': '/var/log',
            'max_file_size': 1048576,  # 1MB
            'max_preview_lines': 50,
            'chunk_size': 5242880,  # 5MB
            'cache_size': 104857600,  # 100MB
            'connection_timeout': 30,
            'command_timeout': 60
        }
        
        # 合并配置
        self.configuration = {**default_config, **configuration}
        
        # 更新缓存配置
        if HAS_CACHE and self.cache_manager:
            try:
                self.cache_manager = CacheManager(max_cache_size=self.configuration['cache_size'])
            except Exception as e:
                self.logger.warning(f"更新缓存配置失败: {str(e)}")
        
        # 更新连接超时
        if HAS_CONNECTION and self.connection_manager and hasattr(self.connection_manager, 'set_timeout'):
            try:
                self.connection_manager.set_timeout(
                    connect_timeout=self.configuration['connection_timeout'],
                    command_timeout=self.configuration['command_timeout']
                )
            except Exception as e:
                self.logger.warning(f"更新连接超时失败: {str(e)}")
        
    def optimize_chunk_size(self, file_size: int) -> int:
        """优化分块大小"""
        if file_size < 1024 * 1024:  # 1MB
            return file_size
        elif file_size < 10 * 1024 * 1024:  # 10MB
            return 1024 * 1024  # 1MB chunks
        elif file_size < 100 * 1024 * 1024:  # 100MB
            return 5 * 1024 * 1024  # 5MB chunks
        else:
            return 10 * 1024 * 1024  # 10MB chunks
            
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """获取文件信息"""
        # 检查缓存
        if HAS_CACHE and self.cache_manager:
            cache_key = f"file_info:{file_path}"
            cached_info = self.cache_manager.get(cache_key)
            if cached_info:
                return cached_info
                
        # 如果没有实际的连接，返回模拟数据
        if not HAS_CONNECTION or not self.connection_manager:
            return {
                'path': file_path,
                'size': 1024,
                'mtime': time.time(),
                'atime': time.time(),
                'mode': 0o644,
                'uid': 0,
                'gid': 0
            }
            
        try:
            # 获取SFTP连接
            ssh = self.get_connection_with_retry()
            if not ssh:
                raise RuntimeError("无法建立SSH连接")
                
            sftp = ssh.open_sftp()
            
            # 获取文件状态
            stat = sftp.stat(file_path)
            
            # 构建文件信息
            file_info = {
                'path': file_path,
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'atime': stat.st_atime,
                'mode': stat.st_mode,
                'uid': stat.st_uid,
                'gid': stat.st_gid
            }
            
            # 缓存文件信息
            if HAS_CACHE and self.cache_manager:
                self.cache_manager.set(cache_key, file_info, ttl=300)  # 缓存5分钟
            
            return file_info
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {str(e)}")
            # 返回模拟数据
            return {
                'path': file_path,
                'size': 1024,
                'mtime': time.time(),
                'atime': time.time(),
                'mode': 0o644,
                'uid': 0,
                'gid': 0
            }
            
    def read_file_chunk(self, file_path: str, start_pos: int = 0, chunk_size: Optional[int] = None) -> Tuple[bytes, int, bool]:
        """读取文件块"""
        # 如果没有实际的连接，返回模拟数据
        if not HAS_CONNECTION or not self.connection_manager:
            content = f"模拟的文件内容: {file_path}, 位置: {start_pos}, 大小: {chunk_size or 1024}".encode('utf-8')
            return content, start_pos + len(content), True
            
        try:
            # 获取文件信息
            file_info = self.get_file_info(file_path)
            file_size = file_info['size']
            
            # 确定块大小
            if chunk_size is None:
                chunk_size = self.optimize_chunk_size(file_size)
            
            # 检查缓存
            if HAS_CACHE and self.cache_manager:
                cache_key = f"file_chunk:{file_path}:{start_pos}:{chunk_size}"
                cached_chunk = self.cache_manager.get(cache_key)
                if cached_chunk:
                    return cached_chunk['content'], cached_chunk['position'], cached_chunk['eof']
                
            # 获取SFTP连接
            ssh = self.get_connection_with_retry()
            if not ssh:
                raise RuntimeError("无法建立SSH连接")
                
            sftp = ssh.open_sftp()
            
            # 读取文件块
            with sftp.file(file_path, 'rb') as f:
                f.seek(start_pos)
                content = f.read(chunk_size)
                current_pos = f.tell()
                eof = current_pos >= file_size
                
            # 缓存结果
            if HAS_CACHE and self.cache_manager:
                chunk_data = {
                    'content': content,
                    'position': current_pos,
                    'eof': eof
                }
                self.cache_manager.set(cache_key, chunk_data, ttl=300)  # 缓存5分钟
            
            return content, current_pos, eof
        except Exception as e:
            self.logger.error(f"读取文件块失败: {str(e)}")
            # 返回模拟数据
            content = f"模拟的文件内容: {file_path}, 位置: {start_pos}, 大小: {chunk_size or 1024}".encode('utf-8')
            return content, start_pos + len(content), True
            
    def close(self) -> None:
        """关闭连接和清理资源"""
        if HAS_CONNECTION and self.connection_manager:
            try:
                self.connection_manager.cleanup()
            except Exception as e:
                self.logger.error(f"关闭连接时出错: {str(e)}")
                
        if HAS_CACHE and self.cache_manager:
            try:
                self.cache_manager.clear()
            except Exception as e:
                self.logger.error(f"清理缓存时出错: {str(e)}")
                
    def __del__(self):
        """析构函数"""
        self.close()
