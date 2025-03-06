"""
Provider层：负责凭证验证与配置加载
┌─────────────────────────────────────────────────────────────┐
│                         Dify 平台                            │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐ │
│  │   应用层      │    │    LLM 层     │    │   用户界面    │ │
│  │ (应用逻辑处理) │◄──►│ (日志分析能力) │◄──►│ (配置与展示)  │ │
│  └───────┬───────┘    └───────────────┘    └───────────────┘ │
└─────────┬│───────────────────────────────────────────────────┘
          ││    插件接口调用
┌─────────▼│───────────────────────────────────────────────────┐
│          ▼                                                   │
│  ┌───────────────┐                                           │
│  │  插件接口层   │                                           │
│  │ (API定义与验证)│                                           │
│  └───────┬───────┘                                           │
│          │                                                   │
│  ┌───────▼───────┐    ┌───────────────┐    ┌───────────────┐ │
│  │   核心服务层  │    │  日志解析层   │    │  数据缓存层   │ │
│  │ (功能实现)    │◄──►│ (格式识别处理) │◄──►│ (临时存储)    │ │
│  └───────┬───────┘    └───────────────┘    └───────────────┘ │
│          │                                                   │
│  ┌───────▼───────┐    ┌───────────────┐                      │
│  │   连接管理层  │    │  安全控制层   │                      │
│  │ (SSH/连接池)  │◄──►│ (权限与验证)  │                      │
│  └───────────────┘    └───────────────┘                      │
│                                                              │
│                      日志插件                                │
└──────────────────────────────────────────────────────────────┘
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

class LogPluginInterface:
    """日志插件接口"""
    
    def __init__(self, log_service, security_manager):
        """初始化方法"""
        self.log_service = log_service
        self.security_manager = security_manager
        self.configuration = {}
        self.logger = logging.getLogger(__name__)
        
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """验证凭证"""
        return self.security_manager.validate_credentials(credentials)
        
    def set_configuration(self, configuration: Dict[str, Any]) -> None:
        """设置配置"""
        self.configuration = configuration
        self.logger.info(f"已设置配置: {configuration}")
        
    def get_log_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取日志文件列表"""
        return self.log_

class LogService:
    """日志服务核心实现"""
    
    def __init__(self, connection_manager, parser_factory, cache_manager):
        self.connection_manager = connection_manager
        self.parser_factory = parser_factory
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        
    def get_log_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取日志文件列表"""
        # 实现获取日志文件列表的逻辑
        # 支持按日期、类型等过滤
        
    def read_log_chunk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """读取日志文件块"""
        result = {
            'content': '',
            'chunk_id': '',
            'has_more': False,
            'total_size': 0,
            'current_position': 0,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        chunk_size = params.get('chunk_size', 5 * 1024 * 1024)  # 默认5MB
        position = params.get('position', 0)
        
        # 验证参数
        if not file_path:
            result['error'] = "缺少必要的参数: file_path"
            return result
            
        # 获取连接
        connection = self.connection_manager.get_connection(params.get('credentials', {}))
        if not connection:
            result['error'] = "无法建立连接"
            return result
            
        try:
            # 获取文件信息
            sftp = connection.open_sftp()
            file_stat = sftp.stat(file_path)
            result['total_size'] = file_stat.st_size
            
            # 检查是否超出文件范围
            if position >= file_stat.st_size:
                result['error'] = "读取位置超出文件范围"
                sftp.close()
                return result
                
            # 读取文件块
            with sftp.open(file_path, 'rb') as f:
                f.seek(position)
                content = f.read(chunk_size)
                
            # 检测编码
            encoding = self._detect_encoding(content)
            
            # 解码内容
            try:
                decoded_content = content.decode(encoding)
            except UnicodeDecodeError:
                # 如果解码失败，尝试使用latin-1编码
                decoded_content = content.decode('latin-1')
                
            # 设置结果
            result['content'] = decoded_content
            result['chunk_id'] = f"{file_path}:{position}"
            result['current_position'] = position + len(content)
            result['has_more'] = position + len(content) < file_stat.st_size
            
            # 关闭SFTP连接
            sftp.close()
        except Exception as e:
            result['error'] = f"读取日志文件时出错: {str(e)}"
            self.logger.error(f"读取日志文件时出错: {str(e)}")
            
        return result
    
    def search_logs(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索日志"""
        result = {
            'matches': [],
            'total_matches': 0,
            'search_time': 0,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        search_fields = params.get('search_fields', {})
        max_results = params.get('max_results', 100)
        
        # 验证参数
        if not file_path:
            result['error'] = "缺少必要的参数: file_path"
            return result
        
        if not search_fields:
            result['error'] = "缺少必要的参数: search_fields"
            return result
        
        # 获取连接
        connection = self.connection_manager.get_connection(params.get('credentials', {}))
        if not connection:
            result['error'] = "无法建立连接"
            return result
        
        start_time = time.time()
        
        try:
            # 获取日志解析器
            log_type = self._detect_log_type(file_path)
            parser = self.parser_factory.get_parser(log_type)
            
            # 构建搜索命令
            search_cmd = self._build_search_command(file_path, search_fields)
            
            # 执行搜索
            exit_code, stdout, stderr = self.connection_manager.execute_command(
                connection.get_id(),
                search_cmd
            )
            
            if exit_code != 0:
                result['error'] = f"搜索失败: {stderr}"
                return result
            
            # 解析搜索结果
            matches = []
            for line in stdout.splitlines():
                # 解析日志行
                parsed_line = parser.parse(line.encode())
                
                # 检查是否匹配所有搜索字段
                if self._match_search_fields(parsed_line, search_fields):
                    matches.append({
                        'line': line,
                        'parsed': parsed_line
                    })
                    
                # 限制结果数量
                if len(matches) >= max_results:
                    break
                
            # 设置结果
            result['matches'] = matches
            result['total_matches'] = len(matches)
        except Exception as e:
            result['error'] = f"搜索日志时出错: {str(e)}"
            self.logger.error(f"搜索日志时出错: {str(e)}")
        finally:
            result['search_time'] = time.time() - start_time
        
        return result
    
    def extract_binary_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """提取16进制报文"""
        result = {
            'messages': [],
            'total_messages': 0,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        message_pattern = params.get('message_pattern')
        max_messages = params.get('max_messages', 100)
        
        # 验证参数
        if not file_path:
            result['error'] = "缺少必要的参数: file_path"
            return result
        
        if not message_pattern:
            result['error'] = "缺少必要的参数: message_pattern"
            return result
        
        # 获取连接
        connection = self.connection_manager.get_connection(params.get('credentials', {}))
        if not connection:
            result['error'] = "无法建立连接"
            return result
        
        try:
            # 获取SFTP客户端
            sftp = connection.open_sftp()
            
            # 读取文件内容
            with sftp.open(file_path, 'rb') as f:
                content = f.read()
                
            # 获取二进制解析器
            parser = self.parser_factory.get_parser("binary")
            
            # 提取16进制报文
            hex_messages = parser.extract_hex_message(content, message_pattern)
            
            # 限制结果数量
            if len(hex_messages) > max_messages:
                hex_messages = hex_messages[:max_messages]
                
            # 解析每个报文
            messages = []
            for hex_msg in hex_messages:
                # 解析16进制报文
                parsed_msg = self._parse_hex_message(hex_msg)
                messages.append({
                    'raw': hex_msg,
                    'parsed': parsed_msg
                })
                
            # 设置结果
            result['messages'] = messages
            result['total_messages'] = len(messages)
            
            # 关闭SFTP连接
            sftp.close()
        except Exception as e:
            result['error'] = f"提取16进制报文时出错: {str(e)}"
            self.logger.error(f"提取16进制报文时出错: {str(e)}")
            
        return result

class LogParserFactory:
    """日志解析器工厂"""
    
    def get_parser(self, log_type: str) -> LogParser:
        """根据日志类型获取对应的解析器"""
        if log_type == "text":
            return TextLogParser()
        elif log_type == "json":
            return JsonLogParser()
        elif log_type == "xml":
            return XmlLogParser()
        elif log_type == "binary":
            return BinaryLogParser()
        else:
            return DefaultLogParser()

class LogParser(ABC):
    """日志解析器基类"""
    
    @abstractmethod
    def parse(self, content: bytes) -> Dict[str, Any]:
        """解析日志内容"""
        pass
        
    @abstractmethod
    def extract_fields(self, content: bytes, fields: List[str]) -> Dict[str, Any]:
        """提取指定字段"""
        pass

class BinaryLogParser(LogParser):
    """二进制日志解析器"""
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """解析二进制日志"""
        # 实现二进制日志解析逻辑
        
    def extract_fields(self, content: bytes, fields: List[str]) -> Dict[str, Any]:
        """从二进制日志中提取字段"""
        # 实现从二进制日志中提取字段的逻辑
        
    def extract_hex_message(self, content: bytes, pattern: str) -> List[str]:
        """提取16进制报文"""
        # 实现16进制报文提取逻辑 

class ConnectionManager:
    """连接管理器"""
    
    def __init__(self):
        self.connections = {}
        self.connection_pool = {}
        self.logger = logging.getLogger(__name__)
        
    def get_connection(self, credentials: Dict[str, Any]) -> Any:
        """获取连接"""
        # 实现连接池管理
        # 支持连接复用
        # 支持连接健康检查
        
    def close_connection(self, connection_id: str) -> None:
        """关闭连接"""
        # 实现连接关闭逻辑
        
    def execute_command(self, connection_id: str, command: str) -> Tuple[int, str, str]:
        """执行命令"""
        # 实现命令执行逻辑
        # 支持超时控制
        # 支持错误处理 

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, max_cache_size: int = 100 * 1024 * 1024):  # 默认100MB
        self.cache = {}
        self.max_cache_size = max_cache_size
        self.current_cache_size = 0
        self.logger = logging.getLogger(__name__)
        
    def get(self, key: str) -> Any:
        """获取缓存"""
        # 实现缓存获取逻辑
        
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """设置缓存"""
        # 实现缓存设置逻辑
        # 支持TTL
        # 支持LRU淘汰策略
        
    def clear(self, key: str = None) -> None:
        """清除缓存"""
        # 实现缓存清除逻辑 

class SecurityManager:
    """安全管理器"""
    
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """验证凭证"""
        # 实现凭证验证逻辑
        
    def validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        # 实现路径安全验证逻辑
        
    def sanitize_command(self, command: str) -> str:
        """命令安全处理"""
        # 实现命令安全处理逻辑
        
    def mask_sensitive_info(self, content: str) -> str:
        """敏感信息遮蔽"""
        # 实现敏感信息遮蔽逻辑 