"""
应用程序单元测试
"""
import unittest
import os
import sys
import tempfile

# 确保正确导入项目模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, User


class AppTestCase(unittest.TestCase):
    """应用测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.db_fd, db_path = tempfile.mkstemp()
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
            # 创建测试管理员用户
            admin = User(
                student_id='test_admin',
                username='test_admin',
                usertype='管理员',
                class_name='测试班级',
                full_name='测试管理员',
                submit_count=0,
                user_ascore=0.0,
                user_tscore=0
            )
            admin.password = 'test_password'
            
            # 创建测试学生用户
            student = User(
                student_id='test_student',
                username='test_student',
                usertype='学生',
                class_name='测试班级',
                full_name='测试学生',
                submit_count=0,
                user_ascore=0.0,
                user_tscore=0
            )
            student.password = 'test_password'
            
            db.session.add(admin)
            db.session.add(student)
            db.session.commit()
    
    def tearDown(self):
        """清理测试环境"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(self.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', ''))
    
    def test_login(self):
        """测试登录功能"""
        # 测试正确的登录
        response = self.client.post('/login', data={
            'username': 'test_admin',
            'password': 'test_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 测试错误的登录
        response = self.client.post('/login', data={
            'username': 'test_admin',
            'password': 'wrong_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'\xe7\x94\xa8\xe6\x88\xb7\xe5\x90\x8d\xe6\x88\x96\xe5\xaf\x86\xe7\xa0\x81\xe9\x94\x99\xe8\xaf\xaf', response.data)  # '用户名或密码错误'的UTF-8编码
    
    def test_home_page(self):
        """测试主页访问"""
        # 登录
        self.client.post('/login', data={
            'username': 'test_admin',
            'password': 'test_password'
        })
        
        # 访问主页
        response = self.client.get('/home')
        self.assertEqual(response.status_code, 200)
    
    def test_api_assignments(self):
        """测试API作业列表"""
        response = self.client.get('/api/assignments')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'success', response.data)


if __name__ == '__main__':
    unittest.main() 