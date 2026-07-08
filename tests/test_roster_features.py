import os
import sys
import tempfile
import unittest
import io
import pandas as pd
from datetime import datetime as dt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import Class, User, StudentRoster, db

class RosterFeaturesTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            # 创建教师
            teacher = User(
                student_id='teacher_001',
                username='teacher1',
                usertype='教师',
                full_name='王老师',
            )
            teacher.password = 'password123'

            # 创建班级
            cls = Class(
                name='软工2401',
                grade='2024',
                major='软件工程',
                teacher_id='teacher_001',
            )
            db.session.add_all([teacher, cls])
            db.session.commit()
            
            self.class_id = cls.id
            self.teacher_id = teacher.student_id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def login_teacher(self):
        return self.client.post('/login', data={
            'username': 'teacher1',
            'password': 'password123',
        }, follow_redirects=False)

    def test_download_template(self):
        self.login_teacher()
        
        # 1. 下载 Excel 模板
        response = self.client.get('/classes/download-template?format=xlsx')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # 2. 下载 CSV 模板
        response = self.client.get('/classes/download-template?format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')
        csv_data = response.get_data(as_text=True)
        self.assertIn('学号', csv_data)
        self.assertIn('姓名', csv_data)

    def test_import_students(self):
        self.login_teacher()

        # 构造导入的 CSV 数据
        csv_buffer = io.BytesIO()
        df = pd.DataFrame([
            {'学号': '20260001', '姓名': '张三'},
            {'学号': '20260002', '姓名': '李四'},
            {'学号': '', '姓名': '王五'},  # 会被跳过的空学号
        ])
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_buffer.seek(0)

        # 上传文件
        response = self.client.post(
            f'/classes/{self.class_id}/import-students',
            data={
                'student_file': (csv_buffer, 'students.csv')
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('学生名单导入完成', body)
        self.assertIn('张三', body)
        self.assertIn('李四', body)
        self.assertIn('学号为空', body)

    def test_roster_binding_progress(self):
        self.login_teacher()

        with self.app.app_context():
            # 1. 手动添加名单
            r1 = StudentRoster(student_id='20260001', full_name='张三', class_id=self.class_id, class_name_snapshot='软工2401')
            r2 = StudentRoster(student_id='20260002', full_name='李四', class_id=self.class_id, class_name_snapshot='软工2401')
            db.session.add_all([r1, r2])
            db.session.commit()

            # 2. 创建匹配的学生 (张三)
            s_match = User(
                student_id='20260001',
                username='zhangsan',
                usertype='学生',
                class_id=self.class_id,
                class_name='软工2401',
                full_name='张三'
            )
            s_match.password = 'password123'
            db.session.add(s_match)
            
            # 3. 创建姓名不匹配的学生 (李四被注册为李小四)
            s_mismatch = User(
                student_id='20260002',
                username='lisi',
                usertype='学生',
                class_id=self.class_id,
                class_name='软工2401',
                full_name='李小四'
            )
            s_mismatch.password = 'password123'
            db.session.add(s_mismatch)
            db.session.commit()

        # 访问班级详情页面，验证注册进度表格
        response = self.client.get(f'/classes/{self.class_id}')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        
        self.assertIn('查看学生注册绑定进度详情', body)
        self.assertIn('已注册', body)
        self.assertIn('信息不匹配', body)
        self.assertIn('姓名不匹配', body)

if __name__ == '__main__':
    unittest.main()
