"""
Provider层：负责凭证验证与配置加载
"""

import paramiko
import logging
import time
import re
from typing import Dict, Any, Optional

class LogProvider:
    """日志提供者，负责SSH连接和凭证验证"""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.ssh_client = None
        self.credentials = {}
        self._mask_pattern = re.compile(r'password=([^,\s]+)')
        
    def _setup_logging(self):
        """配置日志记录"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _mask_sensitive_info(self, message: str) -> str:
        """遮蔽敏感信息"""
        return self._mask_pattern.sub(r'password=******', message)
    
    def load_credentials(self, credentials: Dict[str, Any]) -> None:
        """加载凭证信息"""
        required_fields = ['ip_address', 'username', 'password']
        for field in required_fields:
            if field not in credentials or not credentials[field]:
                raise ValueError(f"缺少必要的凭证信息: {field}")
                
        # 验证IP地址格式
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if not ip_pattern.match(credentials['ip_address']):
            self.logger.warning(f"IP地址格式可能不正确: {credentials['ip_address']}")
        
        # 设置默认SSH端口
        if 'port' not in credentials or not credentials['port']:
            credentials['port'] = 22
        else:
            # 确保端口是整数
            try:
                credentials['port'] = int(credentials['port'])
                if credentials['port'] < 1 or credentials['port'] > 65535:
                    self.logger.warning(f"SSH端口范围无效: {credentials['port']}，使用默认端口22")
                    credentials['port'] = 22
            except ValueError:
                self.logger.warning(f"SSH端口格式无效: {credentials['port']}，使用默认端口22")
                credentials['port'] = 22
                
        self.credentials = credentials
        self.logger.info(f"已加载凭证信息: {credentials['username']}@{credentials['ip_address']}:{credentials['port']}")
    
    def validate_credentials(self) -> Dict[str, Any]:
        """验证凭证有效性"""
        result = {
            'is_valid': False,
            'error': None
        }
        
        if not self.credentials:
            result['error'] = "未加载凭证信息"
            return result
            
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 添加连接超时和身份验证超时
            ssh.connect(
                hostname=self.credentials['ip_address'],
                port=self.credentials['port'],
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=10,
                auth_timeout=20,
                banner_timeout=15
            )
            
            # 验证是否可以执行命令
            stdin, stdout, stderr = ssh.exec_command('uname -a', timeout=5)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                error_output = stderr.read().decode('utf-8', errors='replace')
                result['error'] = f"命令执行失败: {error_output}"
                ssh.close()
                return result
                
            # 验证是否可以访问日志目录
            stdin, stdout, stderr = ssh.exec_command('ls -la /var/log', timeout=5)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                error_output = stderr.read().decode('utf-8', errors='replace')
                result['error'] = f"无法访问日志目录: {error_output}"
                ssh.close()
                return result
            
            ssh.close()
            result['is_valid'] = True
            self.logger.info(f"凭证验证成功: {self.credentials['username']}@{self.credentials['ip_address']}:{self.credentials['port']}")
        except paramiko.AuthenticationException:
            result['error'] = "认证失败: 用户名或密码错误"
            self.logger.error(f"凭证验证失败: 认证错误")
        except paramiko.SSHException as e:
            result['error'] = f"SSH连接错误: {str(e)}"
            self.logger.error(f"凭证验证失败: SSH错误 - {str(e)}")
        except Exception as e:
            result['error'] = f"连接失败: {str(e)}"
            self.logger.error(f"凭证验证失败: {str(e)}")
            
        return result
    
    def get_connection(self) -> Optional[paramiko.SSHClient]:
        """获取SSH连接"""
        if not self.credentials:
            self.logger.error("未加载凭证信息，无法建立连接")
            return None
            
        try:
            if self.ssh_client:
                # 检查连接是否活跃
                transport = self.ssh_client.get_transport()
                if transport and transport.is_active():
                    # 检查连接是否可用
                    try:
                        transport.send_ignore()
                        return self.ssh_client
                    except Exception:
                        self.logger.info("连接已失效，将重新建立连接")
                        self.ssh_client.close()
                else:
                    self.ssh_client.close()
                
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 添加连接超时和身份验证超时
            self.ssh_client.connect(
                hostname=self.credentials['ip_address'],
                port=self.credentials['port'],
                username=self.credentials['username'],
                password=self.credentials['password'],
                timeout=10,
                auth_timeout=20,
                banner_timeout=15,
                allow_agent=False,
                look_for_keys=False
            )
            
            self.logger.info(f"成功建立SSH连接: {self.credentials['username']}@{self.credentials['ip_address']}:{self.credentials['port']}")
            return self.ssh_client
        except Exception as e:
            error_msg = str(e)
            # 遮蔽日志中的敏感信息
            safe_error_msg = self._mask_sensitive_info(error_msg)
            self.logger.error(f"建立SSH连接失败: {safe_error_msg}")
            return None
    
    def close_connection(self) -> None:
        """关闭SSH连接"""
        if self.ssh_client:
            try:
                self.ssh_client.close()
                self.ssh_client = None
                self.logger.info("SSH连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭SSH连接时出错: {str(e)}")
    
    def __del__(self):
        """确保资源正确释放"""
        self.close_connection() 