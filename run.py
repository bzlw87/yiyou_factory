"""
项目启动入口 - 运行这个文件就能启动网站

使用方法：
    开发环境：python run.py
    生产环境：用 Gunicorn 启动（见部署文档）
"""
import os
from app import create_app

# 读取环境变量决定用哪个配置，默认用开发配置
config_name = os.environ.get('FLASK_CONFIG', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
