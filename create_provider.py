"""
创建provider.py文件
"""

content = '''"""
Provider层：负责凭证验证与配置加载
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple

from lib.connection import ConnectionManager
from lib.security import SecurityManager
from lib.cache import CacheManager
from lib.parsers import LogParserFactory

class LogProvider:
    """日志提供者，负责基础连接管理"""
    
    def __init__(self):
        """初始化方法"""
        self.logger = logging.getLogger(__name__)
        self.connection_manager = ConnectionManager()
        self.security_manager = SecurityManager()
        self.cache_manager = CacheManager()
        self.parser_factory = LogParserFactory()
        self.credentials = {}
        self.configuration = {}
        
    def load_credentials(self, credentials: Dict[str, Any]) -> None:
        """加载凭证信息"""
        # 验证凭证
        if not self.security_manager.validate_credentials(credentials):
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
                    
        raise last_error or RuntimeError("无法建立连接")
        
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
        self.cache_manager = CacheManager(max_cache_size=self.configuration['cache_size'])
        
        # 更新连接超时
        if hasattr(self.connection_manager, 'set_timeout'):
            self.connection_manager.set_timeout(
                connect_timeout=self.configuration['connection_timeout'],
                command_timeout=self.configuration['command_timeout']
            )
        
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
        try:
            # 检查缓存
            cache_key = f"file_info:{file_path}"
            cached_info = self.cache_manager.get(cache_key)
            if cached_info:
                return cached_info
                
            # 获取SFTP连接
            ssh = self.get_connection_with_retry()
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
            self.cache_manager.set(cache_key, file_info, ttl=300)  # 缓存5分钟
            
            return file_info
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {str(e)}")
            raise
            
    def read_file_chunk(self, file_path: str, start_pos: int = 0, chunk_size: Optional[int] = None) -> Tuple[bytes, int, bool]:
        """读取文件块"""
        try:
            # 获取文件信息
            file_info = self.get_file_info(file_path)
            file_size = file_info['size']
            
            # 确定块大小
            if chunk_size is None:
                chunk_size = self.optimize_chunk_size(file_size)
            
            # 检查缓存
            cache_key = f"file_chunk:{file_path}:{start_pos}:{chunk_size}"
            cached_chunk = self.cache_manager.get(cache_key)
            if cached_chunk:
                return cached_chunk['content'], cached_chunk['position'], cached_chunk['eof']
                
            # 获取SFTP连接
            ssh = self.get_connection_with_retry()
            sftp = ssh.open_sftp()
            
            # 读取文件块
            with sftp.file(file_path, 'rb') as f:
                f.seek(start_pos)
                content = f.read(chunk_size)
                current_pos = f.tell()
                eof = current_pos >= file_size
                
            # 缓存结果
            chunk_data = {
                'content': content,
                'position': current_pos,
                'eof': eof
            }
            self.cache_manager.set(cache_key, chunk_data, ttl=300)  # 缓存5分钟
            
            return content, current_pos, eof
        except Exception as e:
            self.logger.error(f"读取文件块失败: {str(e)}")
            raise
            
    def close(self) -> None:
        """关闭连接和清理资源"""
        try:
            self.connection_manager.cleanup()
            self.cache_manager.clear()
        except Exception as e:
            self.logger.error(f"关闭资源时出错: {str(e)}")
            
    def __del__(self):
        """析构函数"""
        self.close()
'''

# 使用二进制模式写入，避免编码问题
with open('provider.py', 'wb') as f:
    f.write(content.encode('utf-8')) 