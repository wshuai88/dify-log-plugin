"""
Tool层：业务逻辑实现
"""

import time
import re
import io
import os
import stat
import base64
import tempfile
import shlex
from typing import List, Dict, Any, Optional, Tuple, BinaryIO
from datetime import datetime
from fnmatch import fnmatch

# 使用绝对导入
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from provider import LogProvider

class LogTool:
    """日志工具，实现日志文件查询和内容读取功能"""
    
    def __init__(self, provider: LogProvider):
        self.provider = provider
        self.logger = provider.logger
        # 定义危险路径模式
        self._dangerous_paths = [
            '/etc/shadow', '/etc/passwd', '/etc/sudoers', 
            '/root/.ssh', '/home/*/.ssh', '/var/lib/mysql',
            '/etc/ssl/private', '/etc/ssh'
        ]
        # 定义危险命令模式
        self._dangerous_commands = [
            ';', '&&', '||', '`', '$(',  # 命令链接和替换
            '>', '>>', '<', '<<',  # 重定向
            '|', 'rm', 'mv', 'cp',  # 管道和文件操作
            'wget', 'curl', 'nc',  # 网络工具
            'chmod', 'chown', 'sudo', 'su'  # 权限相关
        ]
        
    def _human_readable_size(self, size: int) -> str:
        """将字节大小转换为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def _is_path_safe(self, path: str) -> bool:
        """检查路径是否安全"""
        # 规范化路径
        normalized_path = os.path.normpath(path)
        
        # 检查是否为绝对路径
        if not normalized_path.startswith('/'):
            self.logger.warning(f"路径不是绝对路径: {path}")
            return False
            
        # 检查是否为危险路径
        for dangerous_path in self._dangerous_paths:
            if fnmatch(normalized_path, dangerous_path):
                self.logger.warning(f"尝试访问危险路径: {path}")
                return False
                
        return True
        
    def _is_command_safe(self, command: str) -> bool:
        """检查命令是否安全"""
        # 检查危险命令
        for dangerous_cmd in self._dangerous_commands:
            if dangerous_cmd in command:
                self.logger.warning(f"命令包含危险操作: {command}")
                return False
                
        return True
        
    def _detect_encoding(self, sftp, file_path: str) -> str:
        """检测文件编码"""
        try:
            # 尝试使用file命令检测编码
            ssh = self.provider.get_connection()
            if not ssh:
                return 'utf-8'  # 默认编码
                
            # 使用file命令检测文件类型和编码
            cmd = f"file -i {shlex.quote(file_path)}"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8', errors='replace')
            
            # 解析输出
            if 'charset=' in output:
                charset = output.split('charset=')[1].strip()
                if charset == 'binary':
                    return 'binary'
                elif charset in ['utf-8', 'us-ascii', 'iso-8859-1', 'utf-16', 'gbk', 'gb2312']:
                    return charset
            
            # 如果file命令无法确定，尝试读取文件头部进行检测
            with sftp.open(file_path, 'rb') as f:
                content = f.read(4096)  # 读取前4KB
                
            # 检测BOM标记
            if content.startswith(b'\xef\xbb\xbf'):
                return 'utf-8-sig'
            elif content.startswith(b'\xff\xfe') or content.startswith(b'\xfe\xff'):
                return 'utf-16'
                
            # 尝试不同的编码解码
            for encoding in ['utf-8', 'latin-1', 'gbk', 'gb2312']:
                try:
                    content.decode(encoding)
                    return encoding
                except UnicodeDecodeError:
                    continue
                    
            return 'utf-8'  # 默认使用UTF-8
        except Exception as e:
            self.logger.warning(f"检测文件编码时出错: {str(e)}")
            return 'utf-8'  # 默认使用UTF-8
            
    def _read_file_content(self, sftp, file_path: str, max_size: int, max_lines: int, search_pattern: Optional[str] = None) -> Dict[str, Any]:
        """读取文件内容"""
        result = {
            'content': '',
            'preview': '',
            'matches': [],
            'total_lines': 0,
            'is_truncated': False,
            'encoding': 'utf-8',
            'is_binary': False,
            'mime_type': None,
            'error': None
        }
        
        try:
            # 检查文件是否存在
            try:
                file_stat = sftp.stat(file_path)
            except FileNotFoundError:
                result['error'] = f"文件不存在: {file_path}"
                return result
                
            # 检查文件大小
            file_size = file_stat.st_size
            if file_size > max_size:
                result['is_truncated'] = True
                self.logger.warning(f"文件大小超过限制: {file_size} > {max_size}，将只读取前{self._human_readable_size(max_size)}")
                
            # 检测MIME类型
            mime_type = self._detect_mime_type(sftp, file_path)
            result['mime_type'] = mime_type
            
            # 检查是否为二进制文件
            is_binary = False
            if mime_type and ('binary' in mime_type or 'application/' in mime_type) and 'text/' not in mime_type:
                is_binary = True
            elif self._is_likely_binary(file_path):
                is_binary = True
                
            result['is_binary'] = is_binary
            if is_binary:
                result['error'] = f"二进制文件不支持读取内容: {file_path} (MIME类型: {mime_type})"
                return result
                
            # 检测文件编码
            encoding = self._detect_encoding(sftp, file_path)
            result['encoding'] = encoding
            if encoding == 'binary':
                result['is_binary'] = True
                result['error'] = "二进制文件不支持读取内容"
                return result
                
            # 读取文件内容
            with sftp.open(file_path, 'rb') as f:
                content = f.read(max_size)
                
            # 解码内容
            try:
                text_content = content.decode(encoding, errors='replace')
            except Exception as e:
                self.logger.warning(f"解码文件内容时出错: {str(e)}，将使用latin-1编码")
                text_content = content.decode('latin-1', errors='replace')
                
            # 分割行
            lines = text_content.splitlines()
            result['total_lines'] = len(lines)
            
            # 处理搜索模式
            if search_pattern:
                try:
                    pattern = re.compile(search_pattern)
                    matches = []
                    for i, line in enumerate(lines):
                        if pattern.search(line):
                            matches.append({
                                'line_number': i + 1,
                                'content': line
                            })
                    result['matches'] = matches[:100]  # 最多返回100个匹配
                except re.error as e:
                    self.logger.warning(f"无效的正则表达式: {search_pattern} - {str(e)}")
                    result['error'] = f"无效的正则表达式: {str(e)}"
                    
            # 设置预览内容
            if max_lines > 0 and len(lines) > 0:
                preview_lines = lines[:min(max_lines, len(lines))]
                result['preview'] = '\n'.join(preview_lines)
                
            # 设置完整内容
            result['content'] = text_content
            
            return result
        except Exception as e:
            self.logger.error(f"读取文件内容时出错: {str(e)}")
            result['error'] = f"读取文件内容时出错: {str(e)}"
            return result
            
    def _detect_mime_type(self, sftp, file_path: str) -> Optional[str]:
        """检测文件MIME类型"""
        try:
            ssh = self.provider.get_connection()
            if not ssh:
                return None
                
            # 使用file命令检测MIME类型
            cmd = f"file --mime-type -b {shlex.quote(file_path)}"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                error = stderr.read().decode('utf-8', errors='replace')
                self.logger.warning(f"检测MIME类型时出错: {error}")
                return None
                
            mime_type = stdout.read().decode('utf-8', errors='replace').strip()
            return mime_type
        except Exception as e:
            self.logger.warning(f"检测MIME类型时出错: {str(e)}")
            return None
            
    def _list_files(self, sftp, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出目录中的文件"""
        result = {
            'file_list': [],
            'total_files': 0,
            'total_size': 0,
            'filtered_files': 0,
            'error': None,
            'execution_time': 0
        }
        
        start_time = time.time()
        
        try:
            # 检查路径是否安全
            if not self._is_path_safe(path):
                result['error'] = f"路径不安全: {path}"
                return result
                
            # 检查路径是否存在
            try:
                path_stat = sftp.stat(path)
            except FileNotFoundError:
                result['error'] = f"路径不存在: {path}"
                return result
                
            # 检查是否为目录
            if not path_stat.st_mode & 0o40000:  # 检查是否为目录
                result['error'] = f"路径不是目录: {path}"
                return result
                
            # 获取文件模式
            file_pattern = params.get('file_pattern', '*')
            
            # 获取递归深度
            max_depth = params.get('max_depth', 1)
            if max_depth < 0:
                max_depth = 0
            elif max_depth > 5:
                max_depth = 5
                
            # 是否读取内容
            read_content = params.get('read_content', False)
            
            # 最大文件大小和预览行数
            max_file_size = params.get('max_file_size', 1048576)  # 默认1MB
            max_preview_lines = params.get('max_preview_lines', 50)
            
            # 搜索模式
            search_pattern = params.get('search_pattern')
            
            # 递归列出文件
            file_list = []
            total_size = 0
            total_files = 0
            filtered_files = 0
            
            def list_dir_recursive(current_path, depth):
                nonlocal total_size, total_files, filtered_files
                
                if depth > max_depth:
                    return
                    
                try:
                    # 列出目录内容
                    dir_entries = sftp.listdir_attr(current_path)
                    
                    for entry in dir_entries:
                        # 构建完整路径
                        entry_path = os.path.join(current_path, entry.filename)
                        
                        # 检查是否为目录
                        is_dir = entry.st_mode & 0o40000
                        
                        # 如果是目录且需要递归
                        if is_dir and depth < max_depth:
                            list_dir_recursive(entry_path, depth + 1)
                        elif not is_dir:  # 如果是文件
                            total_files += 1
                            
                            # 检查文件名是否匹配模式
                            if not fnmatch(entry.filename, file_pattern):
                                filtered_files += 1
                                continue
                                
                            # 获取文件信息
                            file_size = entry.st_size
                            total_size += file_size
                            
                            # 创建文件信息对象
                            file_info = {
                                'name': entry.filename,
                                'path': entry_path,
                                'size': file_size,
                                'human_size': self._human_readable_size(file_size),
                                'modified_time': datetime.fromtimestamp(entry.st_mtime).isoformat(),
                                'permissions': oct(entry.st_mode)[-3:],  # 获取权限的八进制表示
                                'is_dir': False
                            }
                            
                            # 如果需要读取内容
                            if read_content and file_size > 0:
                                # 检查文件大小
                                if file_size <= max_file_size:
                                    content_result = self._read_file_content(
                                        sftp, entry_path, max_file_size, max_preview_lines, search_pattern
                                    )
                                    
                                    # 只有在有搜索模式且有匹配时，或者没有搜索模式时，才添加文件
                                    if (search_pattern and content_result['matches']) or not search_pattern:
                                        file_info.update({
                                            'preview': content_result['preview'],
                                            'matches': content_result['matches'],
                                            'total_lines': content_result['total_lines'],
                                            'is_truncated': content_result['is_truncated'],
                                            'encoding': content_result['encoding'],
                                            'is_binary': content_result['is_binary'],
                                            'mime_type': content_result['mime_type']
                                        })
                                        file_list.append(file_info)
                                    else:
                                        filtered_files += 1
                                else:
                                    # 文件太大，不读取内容
                                    file_info.update({
                                        'preview': f"文件太大，超过{self._human_readable_size(max_file_size)}",
                                        'matches': [],
                                        'total_lines': 0,
                                        'is_truncated': True,
                                        'encoding': 'unknown',
                                        'is_binary': False
                                    })
                                    file_list.append(file_info)
                            else:
                                # 不读取内容，直接添加文件信息
                                file_list.append(file_info)
                except Exception as e:
                    self.logger.warning(f"列出目录时出错: {current_path} - {str(e)}")
                    
            # 开始递归列出文件
            list_dir_recursive(path, 1)
            
            # 按修改时间排序，最新的在前面
            file_list.sort(key=lambda x: x['modified_time'], reverse=True)
            
            # 更新结果
            result['file_list'] = file_list
            result['total_files'] = total_files
            result['total_size'] = total_size
            result['filtered_files'] = filtered_files
            
        except Exception as e:
            self.logger.error(f"列出文件时出错: {str(e)}")
            result['error'] = f"列出文件时出错: {str(e)}"
            
        # 计算执行时间
        result['execution_time'] = time.time() - start_time
        
        return result
        
    def _is_likely_binary(self, filename: str) -> bool:
        """根据文件扩展名判断是否可能是二进制文件"""
        # 常见的二进制文件扩展名
        binary_extensions = [
            '.bin', '.exe', '.dll', '.so', '.dylib', '.obj', '.o',
            '.pyc', '.pyd', '.pyo', '.class', '.jar', '.war',
            '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.tif', '.tiff',
            '.mp3', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.wav', '.ogg',
            '.db', '.sqlite', '.mdb', '.accdb'
        ]
        
        # 获取文件扩展名
        _, ext = os.path.splitext(filename.lower())
        return ext in binary_extensions
        
    def download_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """下载文件"""
        result = {
            'success': False,
            'file_name': None,
            'file_size': 0,
            'file_content_base64': None,
            'mime_type': None,
            'error': None
        }
        
        try:
            # 获取参数
            file_path = params.get('file_path')
            if not file_path:
                result['error'] = "未指定文件路径"
                return result
                
            # 检查路径是否安全
            if not self._is_path_safe(file_path):
                result['error'] = f"路径不安全: {file_path}"
                return result
                
            # 获取最大下载大小
            max_download_size = params.get('max_download_size', 10485760)  # 默认10MB
            
            # 获取SSH连接
            ssh = self.provider.get_connection()
            if not ssh:
                result['error'] = "无法建立SSH连接"
                return result
                
            # 获取SFTP客户端
            sftp = ssh.open_sftp()
            
            try:
                # 检查文件是否存在
                try:
                    file_stat = sftp.stat(file_path)
                except FileNotFoundError:
                    result['error'] = f"文件不存在: {file_path}"
                    return result
                    
                # 检查是否为目录
                if file_stat.st_mode & 0o40000:  # 检查是否为目录
                    result['error'] = f"路径是目录，不是文件: {file_path}"
                    return result
                    
                # 检查文件大小
                file_size = file_stat.st_size
                if file_size > max_download_size:
                    result['error'] = f"文件太大: {self._human_readable_size(file_size)} > {self._human_readable_size(max_download_size)}"
                    return result
                    
                # 检测MIME类型
                mime_type = self._detect_mime_type(sftp, file_path)
                result['mime_type'] = mime_type
                
                # 读取文件内容
                with sftp.open(file_path, 'rb') as f:
                    file_content = f.read()
                    
                # 转换为Base64
                file_content_base64 = base64.b64encode(file_content).decode('utf-8')
                
                # 获取文件名
                file_name = os.path.basename(file_path)
                
                # 更新结果
                result['success'] = True
                result['file_name'] = file_name
                result['file_size'] = file_size
                result['file_content_base64'] = file_content_base64
                
            finally:
                sftp.close()
                
        except Exception as e:
            self.logger.error(f"下载文件时出错: {str(e)}")
            result['error'] = f"下载文件时出错: {str(e)}"
            
        return result
        
    def list_log_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出日志文件"""
        result = {
            'files': [],
            'total_count': 0,
            'error': None
        }
        
        # 获取参数
        log_path = params.get('log_path', '/var/log')
        pattern = params.get('pattern', '*.log')
        recursive = params.get('recursive', False)
        max_depth = params.get('max_depth', 3)
        
        # 验证路径
        if not self._is_path_safe(log_path):
            result['error'] = "路径不安全"
            return result
            
        try:
            # 获取SFTP连接
            ssh = self.provider.get_connection_with_retry()
            sftp = ssh.open_sftp()
            
            # 递归列出文件
            files = []
            self._list_files_recursive(sftp, log_path, pattern, files, 0, max_depth if recursive else 1)
            
            # 处理文件信息
            for file_info in files:
                # 获取文件状态
                try:
                    stat = sftp.stat(file_info['path'])
                    file_info.update({
                        'size': stat.st_size,
                        'size_human': self._human_readable_size(stat.st_size),
                        'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'mode': stat.st_mode
                    })
                except Exception as e:
                    self.logger.warning(f"获取文件状态失败: {str(e)}")
                    continue
                    
            # 设置结果
            result['files'] = files
            result['total_count'] = len(files)
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"列出日志文件时出错: {str(e)}")
            
        return result
        
    def _list_files_recursive(self, sftp, path: str, pattern: str, files: List[Dict[str, Any]], 
                            current_depth: int, max_depth: int) -> None:
        """递归列出文件"""
        if current_depth >= max_depth:
            return
            
        try:
            # 列出目录内容
            for entry in sftp.listdir_attr(path):
                name = entry.filename
                full_path = os.path.join(path, name)
                
                if stat.S_ISDIR(entry.st_mode):
                    # 递归处理子目录
                    self._list_files_recursive(sftp, full_path, pattern, files, 
                                            current_depth + 1, max_depth)
                elif fnmatch(name, pattern):
                    # 添加匹配的文件
                    files.append({
                        'name': name,
                        'path': full_path
                    })
        except Exception as e:
            self.logger.warning(f"列出目录失败: {path}, 错误: {str(e)}")
            
    def read_log_chunk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """读取日志块"""
        result = {
            'content': '',
            'position': 0,
            'eof': False,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        start_pos = params.get('position', 0)
        chunk_size = params.get('chunk_size')
        
        # 验证参数
        if not file_path:
            result['error'] = "缺少必要的参数: file_path"
            return result
            
        # 验证路径
        if not self._is_path_safe(file_path):
            result['error'] = "路径不安全"
            return result
            
        try:
            # 读取文件块
            content, position, eof = self.provider.read_file_chunk(file_path, start_pos, chunk_size)
            
            # 设置结果
            result['content'] = base64.b64encode(content).decode('utf-8')
            result['position'] = position
            result['eof'] = eof
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"读取日志块时出错: {str(e)}")
            
        return result
        
    def search_log_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索日志内容"""
        result = {
            'matches': [],
            'total_matches': 0,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        pattern = params.get('pattern')
        max_matches = params.get('max_matches', 100)
        context_lines = params.get('context_lines', 2)
        
        # 验证参数
        if not file_path or not pattern:
            result['error'] = "缺少必要的参数"
            return result
            
        # 验证路径
        if not self._is_path_safe(file_path):
            result['error'] = "路径不安全"
            return result
            
        try:
            # 构建grep命令
            grep_cmd = f"grep -C {context_lines} -n '{pattern}' '{file_path}'"
            if not self._is_command_safe(grep_cmd):
                result['error'] = "命令不安全"
                return result
                
            # 执行搜索
            ssh = self.provider.get_connection_with_retry()
            stdin, stdout, stderr = ssh.exec_command(grep_cmd)
            
            # 处理结果
            matches = []
            for line in stdout:
                line = line.strip()
                if line:
                    # 解析行号和内容
                    if ':' in line:
                        line_num, content = line.split(':', 1)
                        matches.append({
                            'line_number': int(line_num),
                            'content': content
                        })
                        
                    if len(matches) >= max_matches:
                        break
                        
            # 设置结果
            result['matches'] = matches
            result['total_matches'] = len(matches)
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"搜索日志内容时出错: {str(e)}")
            
        return result
        
    def extract_binary_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """提取二进制报文"""
        result = {
            'messages': [],
            'total_messages': 0,
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        pattern = params.get('pattern')
        max_messages = params.get('max_messages', 100)
        
        # 验证参数
        if not file_path or not pattern:
            result['error'] = "缺少必要的参数"
            return result
            
        # 验证路径
        if not self._is_path_safe(file_path):
            result['error'] = "路径不安全"
            return result
            
        try:
            # 读取文件内容
            content, _, _ = self.provider.read_file_chunk(file_path)
            
            # 获取二进制解析器
            parser = self.provider.parser_factory.get_parser("binary")
            
            # 提取报文
            messages = parser.extract_hex_message(content, pattern)
            
            # 限制结果数量
            if len(messages) > max_messages:
                messages = messages[:max_messages]
                
            # 设置结果
            result['messages'] = messages
            result['total_messages'] = len(messages)
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"提取二进制报文时出错: {str(e)}")
            
        return result
        
    def tail_log_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查看文件末尾内容"""
        result = {
            'lines': [],
            'error': None
        }
        
        # 获取参数
        file_path = params.get('file_path')
        line_count = params.get('lines', 10)
        
        # 验证参数
        if not file_path:
            result['error'] = "缺少必要的参数: file_path"
            return result
            
        # 验证路径
        if not self._is_path_safe(file_path):
            result['error'] = "路径不安全"
            return result
            
        try:
            # 构建tail命令
            tail_cmd = f"tail -n {line_count} '{file_path}'"
            if not self._is_command_safe(tail_cmd):
                result['error'] = "命令不安全"
                return result
                
            # 执行命令
            ssh = self.provider.get_connection_with_retry()
            stdin, stdout, stderr = ssh.exec_command(tail_cmd)
            
            # 处理结果
            result['lines'] = [line.strip() for line in stdout]
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"查看文件末尾内容时出错: {str(e)}")
            
        return result 