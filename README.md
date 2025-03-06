# 日志查看器插件

一个功能强大的日志查看插件，支持通过SSH协议远程访问和分析服务器日志文件。

## 功能特点

- 支持多种日志格式解析（文本、JSON、二进制）
- 智能日志字段提取和分析
- 安全的SSH连接管理
- 高效的缓存机制
- 灵活的配置选项

## 项目结构

```
.
├── lib/                    # 核心库文件
│   ├── __init__.py        # 库初始化文件
│   ├── parsers/           # 日志解析器
│   │   ├── __init__.py    # 解析器初始化文件
│   │   ├── base.py        # 解析器基类
│   │   ├── text_parser.py # 文本日志解析器
│   │   ├── json_parser.py # JSON日志解析器
│   │   └── binary_parser.py # 二进制日志解析器
│   ├── cache.py           # 缓存管理
│   ├── security.py        # 安全管理
│   └── connection.py      # 连接管理
├── tools/                 # 工具目录
├── assets/                # 资源文件
├── main.py               # 主程序入口
├── provider.py           # 服务提供者
├── plugin.yaml           # 插件配置文件
├── requirements.txt      # 依赖项
└── README.md            # 说明文档
```

## 配置说明

### 凭证配置

- `ip_address`: 服务器IP地址（必填）
- `username`: SSH登录用户名（必填）
- `password`: SSH登录密码（必填）
- `port`: SSH服务端口，默认为22（可选）

### 功能配置

- `default_log_path`: 默认日志文件目录，默认为"/var/log"（可选）
- `max_file_size`: 最大文件读取大小，默认为1MB（可选）
- `max_preview_lines`: 最大预览行数，默认为50行（可选）
- `chunk_size`: 日志分块读取大小，默认为5MB（可选）
- `search_fields`: 可搜索的日志字段列表（可选）
- `binary_patterns`: 16进制报文的模式定义（可选）

## 日志解析器

### 文本日志解析器

支持以下格式：
- 标准日志格式：`2023-03-01 12:34:56 [INFO] Message`
- Apache日志格式
- Nginx日志格式
- 键值对格式：`key1=value1 key2=value2`

### JSON日志解析器

- 支持标准JSON格式解析
- 支持嵌套字段提取（如：`user.name`）
- 自动编码检测和处理

### 二进制日志解析器

- 支持多种二进制格式识别（gzip、zip、png、jpeg等）
- 提供16进制报文提取功能
- 支持自定义字段提取规则

## 安全特性

- 凭证加密存储
- 敏感信息自动遮蔽
- 路径访问控制
- 命令注入防护
- 连接超时控制

## 缓存机制

- 智能缓存管理
- 可配置缓存大小
- LRU淘汰策略
- 自动过期清理

## 使用示例

### 基本使用

```python
from lib import LogParserFactory

# 创建日志解析器
parser_factory = LogParserFactory()
text_parser = parser_factory.get_parser("text")

# 解析日志内容
with open("app.log", "rb") as f:
    content = f.read()
    result = text_parser.parse(content)

# 提取特定字段
fields = ["timestamp", "level", "message"]
extracted = text_parser.extract_fields(content, fields)
```

### 远程日志分析

```python
from lib import LogProvider

# 初始化日志提供者
provider = LogProvider()

# 设置凭证
credentials = {
    "ip_address": "192.168.1.100",
    "username": "admin",
    "password": "password",
    "port": 22
}
provider.load_credentials(credentials)

# 获取连接
ssh = provider.get_connection()

# 读取日志文件
with ssh.open_sftp() as sftp:
    with sftp.file("/var/log/app.log", "rb") as f:
        content = f.read()
        
# 解析日志
parser = LogParserFactory().get_parser("text")
result = parser.parse(content)
```

### 二进制日志分析

```python
from lib import LogParserFactory

# 创建二进制解析器
binary_parser = LogParserFactory().get_parser("binary")

# 读取二进制日志
with open("device.log", "rb") as f:
    content = f.read()
    
# 提取16进制报文
pattern = "48454C4C4F"  # "HELLO"的16进制表示
messages = binary_parser.extract_hex_message(content, pattern)
```

## 注意事项

1. **性能考虑**
   - 大文件处理时建议使用分块读取
   - 合理配置缓存大小
   - 避免频繁建立SSH连接

2. **安全建议**
   - 定期更新SSH密码
   - 避免使用root用户
   - 及时清理敏感日志

3. **最佳实践**
   - 根据日志格式选择合适的解析器
   - 使用字段提取而不是全文解析
   - 合理设置超时时间

## 依赖项

- paramiko>=2.8.1
- cryptography>=35.0.0
- pyyaml>=6.0.0

## 安装方法

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/log-viewer.git
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 许可证

MIT License

name: advanced_log_analyzer
version: 2.0.0
description: 高级日志分析插件，支持分块读取、关键字段搜索和16进制报文提取
author: Dify Plugin Developer
repository: https://github.com/yourusername/advanced-log-analyzer
license: MIT
icon: assets/icon.png

permissions:
  - network
  - file_system
  - process

credentials:
  - name: ip_address
    type: string
    required: true
    label: 服务器IP
    description: 服务器的IP地址
  
  - name: port
    type: integer
    required: false
    default: 22
    label: SSH端口
    description: SSH服务端口，默认为22
  
  - name: username
    type: string
    required: true
    label: 用户名
    description: SSH登录用户名
  
  - name: password
    type: password
    required: true
    label: 密码
    description: SSH登录密码

configuration:
  - name: log_directory
    type: string
    required: false
    default: "/var/log"
    label: 日志目录
    description: 日志文件所在的目录
  
  - name: chunk_size
    type: integer
    required: false
    default: 5242880  # 5MB
    label: 块大小
    description: 每次读取的日志块大小（字节）
  
  - name: search_fields
    type: array
    required: false
    default: ["timestamp", "level", "message"]
    label: 搜索字段
    description: 可搜索的日志字段列表
  
  - name: binary_patterns
    type: object
    required: false
    default: {}
    label: 二进制模式
    description: 16进制报文的模式定义