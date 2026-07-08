import io
import os
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import Class, StudentRoster, User, db


class ClassBindingRosterTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            admin = User(
                student_id='admin_001',
                username='admin',
                usertype='管理员',
                full_name='管理员',
            )
            admin.password = 'password123'

            teacher = User(
                student_id='teacher_001',
                username='teacher',
                usertype='教师',
                full_name='王老师',
            )
            teacher.password = 'password123'

            cls = Class(
                name='软件2302',
                grade='2023',
                major='软件工程',
                teacher_bind_code='SW2302CODE',
            )

            db.session.add_all([admin, teacher, cls])
            db.session.commit()
            self.class_id = cls.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def login(self, username):
        return self.client.post('/login', data={
            'username': username,
            'password': 'password123',
        }, follow_redirects=False)

    def logout(self):
        self.client.get('/logout', follow_redirects=False)

    def test_teacher_binds_existing_class_with_binding_code(self):
        self.login('teacher')

        response = self.client.post('/classes/bind', data={
            'bind_code': 'SW2302CODE',
        }, follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            cls = Class.query.get(self.class_id)
            self.assertEqual(cls.teacher_id, 'teacher_001')

    def test_imported_roster_allows_student_registration_and_class_binding(self):
        with self.app.app_context():
            cls = Class.query.get(self.class_id)
            cls.teacher_id = 'teacher_001'
            db.session.commit()

        self.login('teacher')

        roster_file = io.BytesIO()
        pd.DataFrame([
            {'学号': '20230001', '姓名': '张三'},
        ]).to_excel(roster_file, index=False)
        roster_file.seek(0)

        import_response = self.client.post(
            f'/classes/{self.class_id}/import-students',
            data={'student_file': (roster_file, 'roster.xlsx')},
            content_type='multipart/form-data',
            follow_redirects=False,
        )

        self.assertEqual(import_response.status_code, 200)
        self.assertIn('导入完成', import_response.get_data(as_text=True))
        with self.app.app_context():
            roster = StudentRoster.query.filter_by(student_id='20230001').one()
            self.assertEqual(roster.full_name, '张三')
            self.assertEqual(roster.class_id, self.class_id)
            self.assertFalse(roster.is_registered)

        self.logout()

        register_response = self.client.post('/register', data={
            'username': 'student_zhangsan',
            'student_id': '20230001',
            'password': 'password123',
            'confirm_password': 'password123',
            'full_name': '张三',
            'class_name': '',
        }, follow_redirects=False)

        self.assertEqual(register_response.status_code, 302)
        with self.app.app_context():
            user = User.query.get('20230001')
            roster = StudentRoster.query.filter_by(student_id='20230001').one()
            self.assertEqual(user.class_id, self.class_id)
            self.assertEqual(user.class_name, '软件2302')
            self.assertTrue(roster.is_registered)
            self.assertEqual(roster.registered_user_id, '20230001')


if __name__ == '__main__':
    unittest.main()
