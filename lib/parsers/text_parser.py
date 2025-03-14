"""
文本日志解析器实现
"""

import re
from typing import Dict, Any, List

from .base import LogParser

class TextLogParser(LogParser):
    """文本日志解析器"""
    
    def __init__(self):
        # 常见日志格式的正则表达式
        self.patterns = {
            # 标准日志格式: 2023-03-01 12:34:56 [INFO] Message
            'standard': re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[([A-Z]+)\] (.+)'),
            
            # Apache日志格式
            'apache': re.compile(r'(\S+) \S+ \S+ \[([^]]+)\] "([^"]+)" (\d+) (\d+)'),
            
            # Nginx日志格式
            'nginx': re.compile(r'(\S+) - \S+ \[([^]]+)\] "([^"]+)" (\d+) (\d+) "([^"]*)" "([^"]*)"'),
            
            # 简单键值对格式: key1=value1 key2=value2
            'key_value': re.compile(r'(\w+)=([^ ]+)')
        }
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """解析文本日志"""
        try:
            # 尝试解码为文本
            text = content.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            # 如果解码失败，尝试使用latin-1编码
            text = content.decode('latin-1', errors='replace')
            
        result = {
            'type': 'text',
            'raw': text,
            'parsed': {}
        }
        
        # 尝试使用不同的模式解析
        for format_name, pattern in self.patterns.items():
            match = pattern.match(text)
            if match:
                result['format'] = format_name
                
                if format_name == 'standard':
                    result['parsed'] = {
                        'timestamp': match.group(1),
                        'level': match.group(2),
                        'message': match.group(3)
                    }
                elif format_name == 'apache':
                    result['parsed'] = {
                        'ip': match.group(1),
                        'time': match.group(2),
                        'request': match.group(3),
                        'status': match.group(4),
                        'size': match.group(5)
                    }
                elif format_name == 'nginx':
                    result['parsed'] = {
                        'ip': match.group(1),
                        'time': match.group(2),
                        'request': match.group(3),
                        'status': match.group(4),
                        'size': match.group(5),
                        'referer': match.group(6),
                        'user_agent': match.group(7)
                    }
                elif format_name == 'key_value':
                    # 提取所有键值对
                    result['parsed'] = dict(pattern.findall(text))
                    
                break
                
        # 如果没有匹配任何格式，尝试提取常见字段
        if not result.get('format'):
            result['format'] = 'unknown'
            
            # 尝试提取时间戳
            timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
            timestamp_match = timestamp_pattern.search(text)
            if timestamp_match:
                result['parsed']['timestamp'] = timestamp_match.group(0)
                
            # 尝试提取日志级别
            level_pattern = re.compile(r'\b(INFO|DEBUG|WARNING|ERROR|CRITICAL)\b')
            level_match = level_pattern.search(text)
            if level_match:
                result['parsed']['level'] = level_match.group(0)
                
            # 尝试提取IP地址
            ip_pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
            ip_match = ip_pattern.search(text)
            if ip_match:
                result['parsed']['ip'] = ip_match.group(0)
                
        return result
        
    def extract_fields(self, content: bytes, fields: List[str]) -> Dict[str, Any]:
        """提取指定字段"""
        # 先解析整个内容
        parsed = self.parse(content)
        
        # 提取请求的字段
        result = {}
        for field in fields:
            # 检查解析结果中是否有该字段
            if field in parsed.get('parsed', {}):
                result[field] = parsed['parsed'][field]
            else:
                # 尝试使用正则表达式提取
                try:
                    text = parsed.get('raw', '')
                    pattern = re.compile(rf'\b{field}[=:]\s*([^\s,;]+)')
                    match = pattern.search(text)
                    if match:
                        result[field] = match.group(1)
                except re.error:
                    # 如果正则表达式无效，跳过
                    pass
                    
        return result