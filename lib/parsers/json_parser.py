"""
JSON日志解析器实现
"""

import json
from typing import Dict, Any, List

from .base import LogParser

class JsonLogParser(LogParser):
    """JSON日志解析器"""
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """解析JSON日志"""
        result = {
            'type': 'json',
            'parsed': {},
            'raw': ''
        }
        
        try:
            # 尝试解码为文本
            text = content.decode('utf-8', errors='replace')
            result['raw'] = text
            
            # 尝试解析JSON
            parsed = json.loads(text)
            result['parsed'] = parsed
            result['format'] = 'json'
        except UnicodeDecodeError:
            # 如果解码失败，尝试使用latin-1编码
            try:
                text = content.decode('latin-1', errors='replace')
                result['raw'] = text
                
                # 尝试解析JSON
                parsed = json.loads(text)
                result['parsed'] = parsed
                result['format'] = 'json'
            except (json.JSONDecodeError, UnicodeDecodeError):
                result['format'] = 'invalid_json'
        except json.JSONDecodeError:
            result['format'] = 'invalid_json'
            
        return result
        
    def extract_fields(self, content: bytes, fields: List[str]) -> Dict[str, Any]:
        """提取指定字段"""
        # 先解析整个内容
        parsed = self.parse(content)
        
        # 如果不是有效的JSON，返回空结果
        if parsed.get('format') == 'invalid_json':
            return {}
            
        # 提取请求的字段
        result = {}
        json_data = parsed.get('parsed', {})
        
        for field in fields:
            # 处理嵌套字段，如 "user.name"
            if '.' in field:
                parts = field.split('.')
                value = json_data
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = None
                        break
                if value is not None:
                    result[field] = value
            # 处理普通字段
            elif field in json_data:
                result[field] = json_data[field]
                
        return result