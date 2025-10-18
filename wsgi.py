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

# 确保设置了密钥
if 'SECRET_KEY' not in os.environ:
    os.environ['SECRET_KEY'] = 'dev-key-for-testing-only'
    print("警告：使用默认密钥，生产环境请设置SECRET_KEY环境变量")

# 设置使用MySQL数据库
os.environ['FLASK_CONFIG'] = os.environ.get('FLASK_CONFIG') or 'development'
os.environ['DATABASE_URL'] = 'mysql+pymysql://root:root@localhost/student_code_review'

# 导入Flask应用
from app import app as application

if __name__ == '__main__':
    application.run(debug=True, host='0.0.0.0', port=5000) 