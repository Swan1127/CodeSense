import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user, login_required

from models import User, Assignment, Submission, db
from utils.auth import student_required, teacher_required

main = Blueprint('main', __name__)

# 添加全局上下文处理器
@main.app_context_processor
def inject_now():
    return {'now': datetime.datetime.now}

@main.route('/')
def index():
    """网站首页"""
    if current_user.is_authenticated:
        if current_user.role == 'teacher':
            return redirect(url_for('main.teacher_dashboard'))
        else:
            return redirect(url_for('main.student_home'))
    return render_template('index.html')

@main.route('/home')
@login_required
@student_required
def student_home():
    """学生首页"""
    user = User.query.get(current_user.id)
    
    # 获取各项统计数据
    assignments = Assignment.query.filter_by(course_id=user.course_id).all()
    assignments_count = len(assignments)
    
    submissions = Submission.query.filter_by(student_id=user.id).all()
    submissions_count = len(submissions)
    
    scores = [sub.score for sub in submissions if sub.score is not None]
    average_score = sum(scores) / len(scores) if scores else 0
    
    # 获取最近的作业
    recent_assignments = Assignment.query.filter_by(course_id=user.course_id).order_by(Assignment.created_at.desc()).limit(4).all()
    submitted_assignments = set(sub.assignment_id for sub in submissions)
    
    # 获取能力评分
    ability_scores = user.get_ability_scores()
    
    # 获取班级平均分
    class_scores = User.get_class_average_scores(user.course_id)
    
    return render_template('student_home.html', 
                           user=user,
                           assignments_count=assignments_count,
                           submissions_count=submissions_count,
                           average_score=average_score,
                           recent_assignments=recent_assignments,
                           submitted_assignments=submitted_assignments,
                           algorithm_score=ability_scores.get('algorithm', 0),
                           style_score=ability_scores.get('style', 0),
                           functionality_score=ability_scores.get('functionality', 0),
                           efficiency_score=ability_scores.get('efficiency', 0),
                           readability_score=ability_scores.get('readability', 0),
                           class_algorithm_score=class_scores.get('algorithm', 0),
                           class_style_score=class_scores.get('style', 0),
                           class_functionality_score=class_scores.get('functionality', 0),
                           class_efficiency_score=class_scores.get('efficiency', 0),
                           class_readability_score=class_scores.get('readability', 0))

@main.route('/dashboard')
@login_required
@teacher_required
def teacher_dashboard():
    """教师仪表盘"""
    return render_template('teacher_dashboard.html', user=current_user)

@main.route('/about')
def about():
    """关于页面"""
    return render_template('about.html') 