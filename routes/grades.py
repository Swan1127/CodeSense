from collections import defaultdict

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from models import Class, Submission, ThinkingSession, ThinkingStageLog, User
from services.course_grading import build_gradebook
from utils.auth import admin_or_teacher_required


grades = Blueprint('grades', __name__)


def _accessible_classes():
    if current_user.is_admin:
        return Class.query.order_by(Class.name.asc()).all()
    return current_user.managed_classes.order_by(Class.name.asc()).all()


def _students_for_classes(classes, selected_class_id=None):
    if selected_class_id:
        classes = [cls for cls in classes if cls.id == selected_class_id]

    class_ids = [cls.id for cls in classes]
    class_names = [cls.name for cls in classes]
    if not class_ids and not class_names:
        return []

    filters = []
    if class_ids:
        filters.append(User.class_id.in_(class_ids))
    if class_names:
        filters.append(User.class_name.in_(class_names))

    return User.query.filter(
        User.usertype == '学生',
        or_(*filters),
    ).order_by(User.class_name.asc(), User.student_id.asc()).all()


def _group_by_student(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.student_id].append(row)
    return grouped


def _thinking_log_metrics(session_ids):
    if not session_ids:
        return {}

    rows = (
        ThinkingStageLog.query.with_entities(
            ThinkingStageLog.session_id,
            func.count(ThinkingStageLog.id).label('log_count'),
            func.min(ThinkingStageLog.created_at).label('first_at'),
            func.max(ThinkingStageLog.created_at).label('last_at'),
        )
        .filter(ThinkingStageLog.session_id.in_(session_ids))
        .group_by(ThinkingStageLog.session_id)
        .all()
    )

    return {
        row.session_id: {
            'count': row.log_count,
            'first_at': row.first_at,
            'last_at': row.last_at,
        }
        for row in rows
    }


@grades.route('/grades')
@login_required
@admin_or_teacher_required
def grade_statistics():
    classes = _accessible_classes()
    selected_class_id = request.args.get('class_id', type=int)
    selected_class = None
    if selected_class_id:
        selected_class = next((cls for cls in classes if cls.id == selected_class_id), None)
        if selected_class is None:
            selected_class_id = None

    students = _students_for_classes(classes, selected_class_id)
    student_ids = [student.student_id for student in students]

    submissions = []
    thinking_sessions = []
    if student_ids:
        submissions = Submission.query.filter(Submission.student_id.in_(student_ids)).all()
        thinking_sessions = ThinkingSession.query.filter(ThinkingSession.student_id.in_(student_ids)).all()

    records, summary = build_gradebook(
        students,
        _group_by_student(submissions),
        _group_by_student(thinking_sessions),
        _thinking_log_metrics([session.id for session in thinking_sessions]),
    )

    return render_template(
        'grades.html',
        classes=classes,
        selected_class_id=selected_class_id,
        selected_class=selected_class,
        records=records,
        summary=summary,
    )
