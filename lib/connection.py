"""
连接管理模块
"""

import logging
import paramiko
import time
from typing import Dict, Any, Optional, Tuple, List

class ConnectionManager:
    """连接管理器"""
    
    def __init__(self):
        """初始化方法"""
        self.connections = {}
        self.connection_pool = {}
        self.logger = logging.getLogger(__name__)
        self.connect_timeout = 30
        self.command_timeout = 60
        
    def set_timeout(self, connect_timeout: int = 30, command_timeout: int = 60) -> None:
        """设置超时时间"""
        self.connect_timeout = connect_timeout
        self.command_timeout = command_timeout
        
    def get_connection(self, credentials: Dict[str, Any]) -> Any:
        """获取连接"""
        # 生成连接ID
        connection_id = f"{credentials.get('username')}@{credentials.get('ip_address')}:{credentials.get('port', 22)}"
        
        # 检查连接池中是否有可用连接
        if connection_id in self.connections:
            ssh = self.connections[connection_id]
            transport = ssh.get_transport()
            if transport and transport.is_active():
                try:
                    transport.send_ignore()  # 发送空消息测试连接
                    self.logger.info(f"使用现有连接: {connection_id}")
                    return ssh
                except Exception:
                    self.logger.info(f"连接已失效，将重新建立连接: {connection_id}")
                    ssh.close()
        
        # 创建新连接
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 添加连接超时和身份验证超时
            ssh.connect(
                hostname=credentials.get('ip_address'),
                port=credentials.get('port', 22),
                username=credentials.get('username'),
                password=credentials.get('password'),
                timeout=self.connect_timeout,
                auth_timeout=20,
                banner_timeout=15,
                allow_agent=False,
                look_for_keys=False
            )
            
            # 存储连接
            self.connections[connection_id] = ssh
            self.logger.info(f"成功建立新连接: {connection_id}")
            return ssh
        except Exception as e:
            self.logger.error(f"建立连接失败: {str(e)}")
            raise
        
    def close_connection(self, connection_id: str) -> None:
        """关闭连接"""
        if connection_id in self.connections:
            try:
                self.connections[connection_id].close()
                del self.connections[connection_id]
                self.logger.info(f"已关闭连接: {connection_id}")
            except Exception as e:
                self.logger.error(f"关闭连接时出错: {str(e)}")
        
    def execute_command(self, connection_id: str, command: str) -> Tuple[int, str, str]:
        """执行命令"""
        if connection_id not in self.connections:
            raise RuntimeError("连接不存在")
            
        ssh = self.connections[connection_id]
        try:
            stdin, stdout, stderr = ssh.exec_command(command, timeout=self.command_timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_content = stdout.read().decode('utf-8', errors='replace')
            stderr_content = stderr.read().decode('utf-8', errors='replace')
            return exit_code, stdout_content, stderr_content
        except Exception as e:
            self.logger.error(f"执行命令时出错: {str(e)}")
            raise
            
    def cleanup(self) -> None:
        """清理所有连接"""
        for connection_id in list(self.connections.keys()):
            self.close_connection(connection_id)
            
    def __del__(self):
        """析构函数"""
        self.cleanup()
