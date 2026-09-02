"""
WSGI入口点
"""
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加当前目录到Python路径，确保可以正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Gunicorn/WSGI 默认必须走生产配置：不在每个 worker 启动时建表、不开调试。
# 本地直接运行 app.py 仍然使用 development 配置。
os.environ['FLASK_CONFIG'] = os.environ.get('FLASK_CONFIG') or 'production'

# 导入Flask应用
from app import app as application

if __name__ == '__main__':
    application.run(
        debug=os.environ.get('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes'),
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', '5000')),
    )
