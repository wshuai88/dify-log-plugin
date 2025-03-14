"""
安全管理模块
"""

import re
import os
import shlex
import logging
from typing import Dict, Any, List

class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        """初始化方法"""
        self.logger = logging.getLogger(__name__)
        
        # 定义危险路径，防止访问敏感文件
        self.dangerous_paths = [
            '/etc/shadow',
            '/etc/passwd',
            '/etc/ssh',
            '/root',
            '/home',
            '/boot',
            '/proc',
            '/sys',
            '/dev'
        ]
        
        # 定义危险命令，防止命令注入
        self.dangerous_commands = [
            'rm',
            'mv',
            'cp',
            'chmod',
            'chown',
            'dd',
            'mkfs',
            'mount',
            'umount',
            'sudo',
            'su',
            'reboot',
            'shutdown'
        ]
        
        # 敏感信息模式
        self.sensitive_patterns = [
            re.compile(r'password=([^,\s]+)'),
            re.compile(r'passwd=([^,\s]+)'),
            re.compile(r'secret=([^,\s]+)'),
            re.compile(r'token=([^,\s]+)')
        ]
        
    def validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """验证凭证"""
        # 检查必要字段
        required_fields = ['ip_address', 'username', 'password']
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                self.logger.warning(f"缺少必要的凭证字段: {field}")
                return False
                
        # 验证IP地址格式
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if not ip_pattern.match(credentials['ip_address']):
            self.logger.warning(f"IP地址格式不正确: {credentials['ip_address']}")
            return False
            
        # 验证端口
        if 'port' in credentials and credentials['port']:
            try:
                port = int(credentials['port'])
                if port < 1 or port > 65535:
                    self.logger.warning(f"端口范围无效: {port}")
                    return False
            except (ValueError, TypeError):
                self.logger.warning(f"端口格式无效: {credentials['port']}")
                return False
                
        return True
        
    def validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        # 规范化路径
        normalized_path = os.path.normpath(path)
        
        # 检查是否为绝对路径
        if not normalized_path.startswith('/'):
            self.logger.warning(f"路径不是绝对路径: {path}")
            return False
            
        # 检查是否为危险路径
        for dangerous_path in self.dangerous_paths:
            if normalized_path == dangerous_path or normalized_path.startswith(f"{dangerous_path}/"):
                self.logger.warning(f"尝试访问危险路径: {path}")
                return False
                
        # 检查是否包含可疑模式
        suspicious_patterns = ['../', '/../', '/./', '*', '?', '|', '>', '<', ';', '&', '$', '`', '\\']
        for pattern in suspicious_patterns:
            if pattern in path:
                self.logger.warning(f"路径包含可疑模式: {path}, 模式: {pattern}")
                return False
                
        return True
        
    def sanitize_command(self, command: str) -> str:
        """命令安全处理"""
        # 检查是否包含危险命令
        for dangerous_cmd in self.dangerous_commands:
            if re.search(r'\b' + re.escape(dangerous_cmd) + r'\b', command):
                self.logger.warning(f"命令包含危险操作: {command}")
                return ""
                
        # 检查是否包含可疑字符
        suspicious_chars = [';', '&', '|', '>', '<', '`', '$', '\\', '"', "'"]
        for char in suspicious_chars:
            if char in command:
                self.logger.warning(f"命令包含可疑字符: {command}, 字符: {char}")
                return ""
                
        # 使用shlex.quote处理命令参数
        parts = command.split()
        sanitized_parts = [shlex.quote(part) if i > 0 else part for i, part in enumerate(parts)]
        return ' '.join(sanitized_parts)
        
    def mask_sensitive_info(self, content: str) -> str:
        """敏感信息遮蔽"""
        masked_content = content
        for pattern in self.sensitive_patterns:
            masked_content = pattern.sub(r'\1=******', masked_content)
        return masked_content
