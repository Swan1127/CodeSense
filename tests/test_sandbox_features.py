import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import Class, User, Assignment, db

class SandboxFeaturesTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_seed_demo_data_creation(self):
        # 1. 初始状态下应该没有演示数据
        with self.app.app_context():
            teacher = User.query.get('demo_t_001')
            self.assertIsNone(teacher)

        # 2. 触发一键数据装载
        response = self.client.post('/classes/seed-demo-data')
        self.assertEqual(response.status_code, 302) # 重定向回首页

        # 3. 验证演示数据已被装载到数据库中
        with self.app.app_context():
            teacher = User.query.get('demo_t_001')
            self.assertIsNotNone(teacher)
            self.assertEqual(teacher.full_name, '李老师（演示）')
            
            cls = Class.query.filter_by(name='软件工程24-演示班').first()
            self.assertIsNotNone(cls)
            self.assertEqual(cls.school, '酷森思大学')
            
            # 赵一（优秀学生）
            s1 = User.query.get('demo_s_001')
            self.assertIsNotNone(s1)
            self.assertEqual(s1.full_name, '赵一（优秀）')
            
            # 验证测试作业和答题记录
            a1 = Assignment.query.filter(Assignment.title.contains('演示作业一')).first()
            self.assertIsNotNone(a1)

    def test_sandbox_login_flows(self):
        # 1. 先装载假数据
        self.client.post('/classes/seed-demo-data')

        # 2. 免密登录为教师
        response = self.client.get('/sandbox-login/demo_t_001')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('usertype'), '教师')
            self.assertEqual(sess.get('student_id'), 'demo_t_001')

        # 3. 免密登录为优秀生赵一
        response = self.client.get('/sandbox-login/demo_s_001')
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('usertype'), '学生')
            self.assertEqual(sess.get('student_id'), 'demo_s_001')

    def test_security_prevents_sandbox_in_production(self):
        # 禁用调试与测试标识，模拟生产环境
        self.app.config['TESTING'] = False
        self.app.config['DEBUG'] = False

        # 1. 尝试触发种子装载应被拒绝 (403)
        response = self.client.post('/classes/seed-demo-data')
        self.assertEqual(response.status_code, 403)

        # 2. 尝试免密登录应被拒绝 (403)
        response = self.client.get('/sandbox-login/demo_t_001')
        self.assertEqual(response.status_code, 403)

if __name__ == '__main__':
    unittest.main()
