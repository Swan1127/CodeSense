import os
import sys
import tempfile
import unittest
import io
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import Class, User, db

class ClassHierarchyTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

            # 创建管理员
            admin = User(
                student_id='admin_001',
                username='admin1',
                usertype='管理员',
                full_name='系统管理员',
            )
            admin.password = 'admin123'

            # 创建待绑定教师
            teacher = User(
                student_id='teacher_101',
                username='teacher101',
                usertype='教师',
                full_name='高老师',
            )
            teacher.password = 'password123'

            db.session.add_all([admin, teacher])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def login_admin(self):
        return self.client.post('/login', data={
            'username': 'admin1',
            'password': 'admin123',
        }, follow_redirects=False)

    def test_database_model_fields(self):
        with self.app.app_context():
            # 创建带学校学院的班级
            cls = Class(
                name='计科2401',
                school='酷森思理工大学',
                college='数媒学院',
                grade='2024',
                major='数字媒体技术'
            )
            db.session.add(cls)
            db.session.commit()

            fetched = Class.query.filter_by(name='计科2401').first()
            self.assertEqual(fetched.school, '酷森思理工大学')
            self.assertEqual(fetched.college, '数媒学院')

    def test_add_and_edit_class_via_form(self):
        self.login_admin()

        # 1. 提交添加班级
        response = self.client.post('/classes/add', data={
            'name': '软工2403',
            'school': '测试大学',
            'college': '软件学院',
            'grade': '2024',
            'major': '软件工程',
            'teacher_id': ''
        })
        self.assertEqual(response.status_code, 302) # 重定向回 class_list

        with self.app.app_context():
            cls = Class.query.filter_by(name='软工2403').first()
            self.assertIsNotNone(cls)
            self.assertEqual(cls.school, '测试大学')
            self.assertEqual(cls.college, '软件学院')

        # 2. 提交修改班级
        response = self.client.post(f'/classes/{cls.id}/edit', data={
            'name': '软工2403-改',
            'school': '测试大学-改',
            'college': '软件学院-改',
            'grade': '2023',
            'major': '软件工程与开发',
            'teacher_id': 'teacher_101'
        })
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            cls_updated = Class.query.filter_by(teacher_id='teacher_101').first()
            self.assertIsNotNone(cls_updated)
            self.assertEqual(cls_updated.name, '软工2403-改')
            self.assertEqual(cls_updated.school, '测试大学-改')
            self.assertEqual(cls_updated.college, '软件学院-改')
            self.assertEqual(cls_updated.grade, '2023')

    def test_download_class_template(self):
        self.login_admin()

        response = self.client.get('/classes/download-class-template?format=xlsx')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        response = self.client.get('/classes/download-class-template?format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/csv')

    def test_import_classes_parsing(self):
        self.login_admin()

        # 构造 Excel/CSV 内容
        csv_buffer = io.BytesIO()
        df = pd.DataFrame([
            {
                '学校': '南华大学',
                '学院': '信息工程学院',
                '专业': '计算机科学',
                '年级': '2024',
                '班级名称': '计科24-2班',
                '教师工号': 'teacher_101'
            },
            {
                '学校': '北华大学',
                '学院': '软件学院',
                '专业': '软件外包',
                '年级': '2023',
                '班级名称': '外包23-1班',
                '教师工号': 'teacher_nonexistent' # 不存在的教师
            }
        ])
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_buffer.seek(0)

        response = self.client.post(
            '/classes/import-classes',
            data={
                'class_file': (csv_buffer, 'classes.csv')
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('班级导入处理完成', body)
        self.assertIn('计科24-2班', body)
        self.assertIn('外包23-1班', body)
        self.assertIn('高老师', body) # 教师工号 teacher_101 匹配的名字
        self.assertIn('未在系统中注册', body)

        with self.app.app_context():
            cls1 = Class.query.filter_by(name='计科24-2班').first()
            self.assertIsNotNone(cls1)
            self.assertEqual(cls1.school, '南华大学')
            self.assertEqual(cls1.college, '信息工程学院')
            self.assertEqual(cls1.teacher_id, 'teacher_101')

            cls2 = Class.query.filter_by(name='外包23-1班').first()
            self.assertIsNotNone(cls2)
            self.assertEqual(cls2.school, '北华大学')
            self.assertEqual(cls2.teacher_id, None) # 没找到，所以为空

if __name__ == '__main__':
    unittest.main()
