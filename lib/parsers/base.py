"""
日志解析器基类定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

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