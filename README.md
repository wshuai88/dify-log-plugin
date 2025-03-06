# 日志查看器插件

这是一个Dify平台插件，用于通过SSH协议远程访问服务器的日志文件。

## 功能特点

- 远程连接服务器
- 浏览和搜索日志文件
- 支持文件内容预览和搜索
- 支持文件过滤和模式匹配
- 提供文件元数据（大小、权限、修改时间等）
- 支持文件下载功能
- 支持查看文件末尾内容（类似tail命令）
- 自动检测文件编码和MIME类型
- 二进制文件识别
- 安全性保护（路径验证、命令注入防护）

## 安装方法

1. 将此插件目录复制到Dify插件目录中
2. 安装依赖：`pip install -r requirements.txt`
3. 在Dify平台中启用插件

## 配置说明

### 凭证配置

- **服务器IP**：服务器的IP地址
- **SSH端口**：SSH服务端口，默认为22
- **用户名**：SSH登录用户名
- **密码**：SSH登录密码

### 插件配置

- **默认日志路径**：默认的日志文件目录，默认为`/var/log`
- **最大文件大小**：最大读取文件大小（字节），默认为1MB
- **预览行数**：文件预览的最大行数，默认为50行

## 使用方法

### 列出日志文件

```python
# 示例代码
result = plugin.list_log_files({
    "log_path": "/var/log",
    "file_pattern": "*.log",
    "read_content": False,
    "max_depth": 3  # 最大递归深度
})
```

### 读取日志文件内容

```python
# 示例代码
result = plugin.read_log_file({
    "file_path": "/var/log/syslog",
    "max_preview_lines": 100,
    "search_pattern": "ERROR|WARN"
})
```

### 下载日志文件

```python
# 示例代码
result = plugin.download_file({
    "file_path": "/var/log/syslog",
    "max_download_size": 10485760  # 10MB
})

# 获取Base64编码的文件内容
file_content_base64 = result["file_content_base64"]
```

### 查看文件末尾内容

```python
# 示例代码
result = plugin.tail_log_file({
    "file_path": "/var/log/syslog",
    "lines": 20  # 显示最后20行
})

# 显示结果
for line in result["lines"]:
    print(line)
```

## 高级功能

### 文件编码检测

插件会自动检测文件编码，支持以下编码：
- UTF-8
- Latin-1
- GBK
- GB2312
- UTF-16

### MIME类型检测

插件使用`file`命令检测文件的MIME类型，可以更准确地识别文件类型，避免读取不支持的文件格式。

### 二进制文件处理

插件会自动识别二进制文件，避免读取二进制文件内容导致的问题。识别方法包括：
- 文件扩展名检查
- MIME类型检测

### 递归目录遍历

可以通过设置`max_depth`参数控制递归遍历的深度，避免遍历过深导致性能问题。

### 安全性保护

插件实现了多层安全保护机制：
- 路径安全检查：防止访问敏感系统文件
- 命令注入防护：使用`shlex.quote`防止命令注入
- 正则表达式验证：防止恶意正则表达式导致的DoS攻击
- 敏感信息保护：日志中自动遮蔽密码等敏感信息

## 注意事项

- 请确保服务器允许SSH连接
- 用户需要有足够的权限访问日志文件
- 大文件处理可能会消耗较多资源
- 下载大文件时请注意内存使用
- 插件默认限制了对系统敏感文件的访问

## 许可证

MIT 