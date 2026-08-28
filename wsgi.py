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

# 使用环境变量选择配置；数据库和密钥由部署环境提供
os.environ['FLASK_CONFIG'] = os.environ.get('FLASK_CONFIG') or 'development'

# 导入Flask应用
from app import app as application

if __name__ == '__main__':
    application.run(debug=True, host='0.0.0.0', port=5000)
