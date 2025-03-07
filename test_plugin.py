"""
测试脚本
用于测试日志查看器插件功能
"""

import logging
import json
from dify_compat import PluginContext, PluginCredentials, PluginConfiguration
from main import plugin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_plugin():
    """测试插件功能"""
    print("开始测试插件...")
    
    # 初始化插件
    plugin.setup(PluginContext())
    
    # 加载凭证
    credentials = PluginCredentials({
        'ip_address': '192.168.1.100',  # 替换为实际的服务器IP
        'port': 22,
        'username': 'test',  # 替换为实际的用户名
        'password': 'password'  # 替换为实际的密码
    })
    
    try:
        # 修改：直接设置凭证，不进行验证
        plugin.provider.credentials = credentials.copy()
        print("凭证加载成功")
    except Exception as e:
        print(f"凭证加载失败: {str(e)}")
        return
    
    # 加载配置
    configuration = PluginConfiguration({
        'default_log_path': '/var/log',
        'max_file_size': 1048576,
        'max_preview_lines': 50,
        'chunk_size': 5242880,
        'cache_size': 104857600
    })
    
    try:
        plugin.load_configuration(configuration)
        print("配置加载成功")
    except Exception as e:
        print(f"配置加载失败: {str(e)}")
        return
    
    # 测试列出日志文件
    try:
        result = plugin.execute_tool('list_log_files', {
            'log_path': '/var/log',
            'pattern': '*.log',
            'recursive': True,
            'max_depth': 2
        })
        print("列出日志文件结果:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"列出日志文件失败: {str(e)}")
    
    # 测试读取日志块
    try:
        result = plugin.execute_tool('read_log_chunk', {
            'file_path': '/var/log/syslog',
            'position': 0,
            'chunk_size': 1024
        })
        print("读取日志块结果:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"读取日志块失败: {str(e)}")
    
    # 测试搜索日志内容
    try:
        result = plugin.execute_tool('search_log_content', {
            'file_path': '/var/log/syslog',
            'pattern': 'error',
            'max_matches': 10,
            'context_lines': 2
        })
        print("搜索日志内容结果:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"搜索日志内容失败: {str(e)}")
    
    # 测试查看文件末尾内容
    try:
        result = plugin.execute_tool('tail_log_file', {
            'file_path': '/var/log/syslog',
            'lines': 10
        })
        print("查看文件末尾内容结果:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"查看文件末尾内容失败: {str(e)}")
    
    # 清理资源
    plugin.cleanup()
    print("测试完成")

if __name__ == "__main__":
    test_plugin() 