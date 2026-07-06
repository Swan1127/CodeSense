import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from app import create_app
from models import Assignment, Class, Submission, ThinkingSession, ThinkingStageLog, db, User


@pytest.fixture()
def app_context():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app('testing')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['TESTING'] = True

    with app.app_context():
        db.create_all()

        class_a = Class(name='软件工程24-1班', teacher_id='teacher_a')
        class_b = Class(name='软件工程24-2班', teacher_id='teacher_b')
        db.session.add_all([class_a, class_b])
        db.session.flush()

        users = [
            User(student_id='admin', username='admin', usertype='管理员', full_name='管理员'),
            User(student_id='teacher_a', username='teacher_a', usertype='教师', full_name='教师A'),
            User(student_id='teacher_b', username='teacher_b', usertype='教师', full_name='教师B'),
            User(
                student_id='s_a',
                username='s_a',
                usertype='学生',
                full_name='学生甲',
                class_name=class_a.name,
                class_id=class_a.id,
            ),
            User(
                student_id='s_b',
                username='s_b',
                usertype='学生',
                full_name='学生乙',
                class_name=class_b.name,
                class_id=class_b.id,
            ),
        ]
        for user in users:
            user.password = 'password'
        db.session.add_all(users)
        db.session.flush()

        assignment = Assignment(id=1001, title='测试作业', description='测试', creator_id='teacher_a')
        db.session.add(assignment)
        db.session.flush()

        db.session.add(Submission(
            student_id='s_a',
            assignment_id=assignment.id,
            code='int main(){return 0;}',
            score=85,
            status='evaluated',
        ))
        guided_session = ThinkingSession(
            student_id='s_b',
            assignment_id=assignment.id,
            current_stage=2,
            total_time_seconds=0,
        )
        db.session.add(guided_session)
        db.session.flush()
        db.session.add_all([
            ThinkingStageLog(
                session_id=guided_session.id,
                stage=1,
                event_type='session_start',
                role='student',
                content='开始引导式学习',
                created_at=datetime(2026, 7, 6, 10, 0, 0),
            ),
            ThinkingStageLog(
                session_id=guided_session.id,
                stage=1,
                event_type='description_submit',
                role='student',
                content='提交思路',
                created_at=datetime(2026, 7, 6, 10, 10, 0),
            ),
        ])
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username):
    return client.post('/login', data={'username': username, 'password': 'password'})


def test_admin_can_open_grades_page(app_context):
    client = app_context.test_client()
    login(client, 'admin')

    response = client.get('/grades')

    assert response.status_code == 200
    assert '成绩统计'.encode('utf-8') in response.data
    assert '学生甲'.encode('utf-8') in response.data
    assert '学生乙'.encode('utf-8') in response.data
    assert '10 分钟'.encode('utf-8') in response.data


def test_teacher_only_sees_students_in_managed_classes(app_context):
    client = app_context.test_client()
    login(client, 'teacher_a')

    response = client.get('/grades')

    assert response.status_code == 200
    assert '学生甲'.encode('utf-8') in response.data
    assert '学生乙'.encode('utf-8') not in response.data


def test_student_cannot_access_grades_page(app_context):
    client = app_context.test_client()
    login(client, 's_a')

    response = client.get('/grades')

    assert response.status_code == 302


def test_admin_can_export_grades_excel(app_context):
    client = app_context.test_client()
    login(client, 'admin')

    response = client.get('/grades/export')

    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert '.xlsx' in response.headers['Content-Disposition']
    assert response.data.startswith(b'PK')
