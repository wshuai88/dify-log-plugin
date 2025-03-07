"""
解析器模块初始化文件
"""

from .base import LogParser
from .text_parser import TextLogParser
from .json_parser import JsonLogParser
from .binary_parser import BinaryLogParser

class LogParserFactory:
    """日志解析器工厂"""
    
    def get_parser(self, log_type: str) -> LogParser:
        """根据日志类型获取对应的解析器"""
        if log_type == "text":
            return TextLogParser()
        elif log_type == "json":
            return JsonLogParser()
        elif log_type == "binary":
            return BinaryLogParser()
        else:
            return TextLogParser()  # 默认使用文本解析器

__all__ = ['LogParser', 'TextLogParser', 'JsonLogParser', 'BinaryLogParser', 'LogParserFactory']