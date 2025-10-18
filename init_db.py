"""
数据库初始化脚本
用于创建表和添加初始数据
"""
import os
import sys
import pymysql
from flask import Flask
from models import db, User, Assignment, Submission, init_db, SystemLog
from dotenv import load_dotenv

# 添加当前目录到Python路径，确保可以正确导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入配置
from config import config

# 加载环境变量
load_dotenv()


def create_app(config_name='default'):
    """创建测试应用实例"""
    app = Flask(__name__)  
    
    # 从配置对象中加载配置
    app.config.from_object(config[config_name])
    
    # 直接设置关键配置
    app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-for-testing-only'
    
    # 使用MySQL数据库
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:root@localhost/student_code_review'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 调用配置初始化
    config[config_name].init_app(app)
    
    # 初始化数据库
    db.init_app(app)
    
    return app


def init_database():
    """初始化数据库"""
    # 首先创建数据库（如果不存在）
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='root',
        )
        with conn.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS student_code_review CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.close()
        print("已创建数据库student_code_review")
    except Exception as e:
        print(f"创建数据库出错: {e}")
        return

    app = create_app('development')
    
    with app.app_context():
        # 删除所有表
        db.drop_all()
        print("已删除所有表")
        
        # 创建表
        db.create_all()
        print("已创建所有表")
        
        # 添加初始管理员用户
        admin = User(
            student_id='admin',
            username='admin',
            usertype='管理员',
            full_name='系统管理员',
            class_name='管理部门',
            submit_count=0,
            user_ascore=0.0,
            user_tscore=0
        )
        admin.password = 'admin123'  # 设置密码会自动哈希
        
        # 添加测试用户
        test_user = User(
            student_id='test123',
            username='testuser',
            usertype='学生',
            full_name='测试用户',
            class_name='测试班级',
            submit_count=0,
            user_ascore=0.0,
            user_tscore=0
        )
        test_user.password = 'test123'  # 设置密码会自动哈希
        
        # 添加测试作业
        test_assignment = Assignment(
            title='测试作业：冒泡排序算法',
            description='请实现一个冒泡排序算法，对整数数组进行排序。',
            total_score=0,
            average_score=0.0,
            count=0
        )
        
        # 将对象添加到会话
        db.session.add(admin)
        db.session.add(test_user)
        db.session.add(test_assignment)
        
        # 提交会话，确保上面的对象先保存到数据库获得ID
        db.session.commit()
        
        # 添加初始系统日志
        from datetime import datetime, timedelta
        
        # 计算初始日志的时间，确保它们按时间顺序排列
        now = datetime.utcnow()
        
        # 添加系统初始化日志
        init_log = SystemLog(
            log_type='系统初始化',
            content='系统初始化完成，数据库和基本配置已设置',
            icon='bi bi-gear',
            created_at=now - timedelta(minutes=30)
        )
        
        # 添加管理员创建日志
        admin_log = SystemLog(
            log_type='用户注册',
            content=f'系统管理员账户已创建',
            user_id=admin.student_id,
            icon='bi bi-person-plus',
            created_at=now - timedelta(minutes=25)
        )
        
        # 添加测试用户创建日志
        user_log = SystemLog(
            log_type='用户注册',
            content=f'新用户 {test_user.username} ({test_user.full_name}) 注册成功，用户类型：{test_user.usertype}',
            user_id=test_user.student_id,
            icon='bi bi-person-plus',
            created_at=now - timedelta(minutes=20)
        )
        
        # 添加测试作业创建日志
        assignment_log = SystemLog(
            log_type='添加作业',
            content=f'管理员 {admin.username} 添加了新作业：{test_assignment.title} (ID: {test_assignment.id})',
            user_id=admin.student_id,
            icon='bi bi-file-earmark-plus',
            created_at=now - timedelta(minutes=15)
        )
        
        # 将日志添加到会话
        db.session.add(init_log)
        db.session.add(admin_log)
        db.session.add(user_log)
        db.session.add(assignment_log)
        
        # 再次提交会话
        db.session.commit()
        
        print("已添加初始数据及系统日志")


if __name__ == '__main__':
    init_database()
    print("数据库初始化完成!") 