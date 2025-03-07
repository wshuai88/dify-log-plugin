"""
缓存管理模块
"""

import logging
import time
from typing import Dict, Any, Optional
from collections import OrderedDict

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, max_cache_size: int = 100 * 1024 * 1024):  # 默认100MB
        """初始化方法"""
        self.cache = OrderedDict()  # 使用OrderedDict实现LRU
        self.max_cache_size = max_cache_size
        self.current_cache_size = 0
        self.expiry_times = {}
        self.access_times = {}
        self.logger = logging.getLogger(__name__)
        
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None
            
        # 检查是否过期
        if key in self.expiry_times and self.expiry_times[key] < time.time():
            self.clear(key)
            return None
            
        # 更新访问时间和LRU顺序
        self.access_times[key] = time.time()
        value = self.cache.pop(key)
        self.cache[key] = value  # 移动到末尾
        
        return value
        
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """设置缓存"""
        # 计算值的大小（近似）
        value_size = len(str(value)) if isinstance(value, (str, bytes)) else 1024
        
        # 如果已存在，先移除旧值
        if key in self.cache:
            old_value_size = len(str(self.cache[key])) if isinstance(self.cache[key], (str, bytes)) else 1024
            self.current_cache_size -= old_value_size
            del self.cache[key]
            
        # 检查是否需要清理缓存
        while self.current_cache_size + value_size > self.max_cache_size and self.cache:
            self._evict_one()
            
        # 设置缓存
        self.cache[key] = value
        self.current_cache_size += value_size
        self.access_times[key] = time.time()
        
        # 设置过期时间
        if ttl > 0:
            self.expiry_times[key] = time.time() + ttl
            
    def clear(self, key: str = None) -> None:
        """清除缓存"""
        if key is None:
            # 清除所有缓存
            self.cache.clear()
            self.expiry_times.clear()
            self.access_times.clear()
            self.current_cache_size = 0
            self.logger.info("已清除所有缓存")
        elif key in self.cache:
            # 清除指定缓存
            value_size = len(str(self.cache[key])) if isinstance(self.cache[key], (str, bytes)) else 1024
            self.current_cache_size -= value_size
            del self.cache[key]
            if key in self.expiry_times:
                del self.expiry_times[key]
            if key in self.access_times:
                del self.access_times[key]
            self.logger.info(f"已清除缓存: {key}")
            
    def _evict_one(self) -> None:
        """淘汰一个缓存项"""
        if not self.cache:
            return
            
        # 获取最早访问的键
        key, value = self.cache.popitem(last=False)
        value_size = len(str(value)) if isinstance(value, (str, bytes)) else 1024
        self.current_cache_size -= value_size
        
        # 清理相关数据
        if key in self.expiry_times:
            del self.expiry_times[key]
        if key in self.access_times:
            del self.access_times[key]
            
        self.logger.info(f"已淘汰缓存: {key}")
        
    def cleanup_expired(self) -> None:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, expiry_time in self.expiry_times.items()
            if expiry_time < current_time
        ]
        
        for key in expired_keys:
            self.clear(key)
            
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            'total_size': self.current_cache_size,
            'max_size': self.max_cache_size,
            'item_count': len(self.cache),
            'usage_percent': (self.current_cache_size / self.max_cache_size) * 100 if self.max_cache_size > 0 else 0
        }
