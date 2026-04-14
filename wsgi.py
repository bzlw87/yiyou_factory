"""
WSGI 入口文件 - Gunicorn 用这个文件启动应用

WSGI 是 Python Web 应用和 Web 服务器之间的标准接口。
Gunicorn 是一个 WSGI 服务器，比 Flask 自带的开发服务器更强大、更安全。

Gunicorn 启动命令：
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
    
参数说明：
    -w 4    表示启动 4 个工作进程（通常设为 CPU 核心数 × 2 + 1）
    -b      绑定地址和端口
    wsgi:app  表示从 wsgi.py 文件中导入 app 变量
"""
import os
from app import create_app

config_name = os.environ.get('FLASK_CONFIG', 'production')
app = create_app(config_name)
