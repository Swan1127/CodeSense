"""
班级管理路由
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from models import db, Class, User, Assignment, Submission
from utils.auth import admin_required, admin_or_teacher_required

classes = Blueprint('classes', __name__, url_prefix='/classes')

@classes.route('/')
@login_required
@admin_or_teacher_required
def class_list():
    """班级列表页面. 管理员可以看到所有班级, 教师只能看到自己管理的班级."""
    class_data = []
    
    if current_user.is_admin:
        all_classes = Class.query.order_by(Class.name).all()
    else: # is_teacher
        all_classes = current_user.managed_classes.order_by(Class.name).all()

    for cls in all_classes:
        stats = cls.get_statistics()
        class_data.append({
            'class': cls,
            'stats': stats,
            'top_students': cls.get_top_students(3)
        })
    
    # 按学生数量排序
    class_data.sort(key=lambda x: x['stats']['student_count'], reverse=True)
    
    # 计算总体统计数据
    total_students = sum(cd['stats']['student_count'] for cd in class_data)
    total_submissions = sum(cd['stats']['total_submissions'] for cd in class_data)
    total_weighted_score = sum(cd['stats']['avg_score'] * cd['stats']['student_count'] for cd in class_data)
    
    overall_avg_score = total_weighted_score / total_students if total_students > 0 else 0
    
    # 为管理员加载可用教师列表供添加班级使用
    teachers = []
    if current_user.is_admin:
        teachers = User.query.filter_by(usertype='教师').all()
        
    return render_template('classes/class_list.html', 
                         class_data=class_data,
                         total_classes=len(all_classes),
                         total_students=total_students,
                         total_submissions_overall=total_submissions,
                         overall_avg_score=overall_avg_score,
                         teachers=teachers)

@classes.route('/<int:class_id>')
@login_required
@admin_or_teacher_required
def class_detail(class_id):
    """班级详情页面. 教师只能访问自己管理的班级."""
    cls = Class.query.get_or_404(class_id)

    # 权限检查: 管理员可以访问任何班级, 教师只能访问自己的班级
    if not current_user.is_admin and cls.teacher_id != current_user.student_id:
        flash('您没有权限访问此班级详情', 'danger')
        return redirect(url_for('classes.class_list'))

    # 获取班级统计
    stats = cls.get_statistics()
    
    # 获取班级学生列表（分页）
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    students = cls.students.filter_by(usertype='学生')\
                          .order_by(desc(User.user_ascore))\
                          .paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取作业进度 (支持分页)
    assign_page = request.args.get('assign_page', 1, type=int)
    assignment_progress = cls.get_assignment_progress(page=assign_page, per_page=10)
    
    return render_template('classes/class_detail.html',
                         cls=cls,
                         stats=stats,
                         students=students,
                         assignment_progress=assignment_progress['items'],
                         assignment_pagination=assignment_progress['pagination'])

@classes.route('/<int:class_id>/assignment/<int:assignment_id>')
@login_required
@admin_or_teacher_required
def class_assignment_detail(class_id, assignment_id):
    """查看某班级在特定作业上的所有学生答题情况"""
    cls = Class.query.get_or_404(class_id)
    assignment = Assignment.query.get_or_404(assignment_id)

    # 权限检查
    if not current_user.is_admin and cls.teacher_id != current_user.student_id:
        flash('您没有权限访问此班级详情', 'danger')
        return redirect(url_for('classes.class_list'))

    # 获取分页学生
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    students_query = cls.students.filter_by(usertype='学生').order_by(desc(User.user_ascore))
    students_paginated = students_query.paginate(page=page, per_page=per_page, error_out=False)
    
    student_records = []
    
    for student in students_paginated.items:
        # 获取该学生在这个作业下的最高得分提交（也可以根据需要改成最新提交）
        best_submission = Submission.query.filter_by(
            student_id=student.student_id, 
            assignment_id=assignment.id
        ).order_by(Submission.score.desc()).first()
        
        # 获取总提交次数
        submit_count = Submission.query.filter_by(
            student_id=student.student_id, 
            assignment_id=assignment.id
        ).count()
        
        student_records.append({
            'student': student,
            'best_submission': best_submission,
            'submit_count': submit_count
        })

    return render_template('classes/class_assignment_stats.html',
                           cls=cls,
                           assignment=assignment,
                           student_records=student_records,
                           pagination=students_paginated)

@classes.route('/compare')
@login_required
@admin_or_teacher_required
def class_comparison():
    """班级对比分析页面"""
    # 教师只看自己的班级，管理员看全部
    if current_user.usertype == '管理员':
        main_classes = Class.query.all()
    else:
        main_classes = Class.query.filter_by(teacher_id=current_user.student_id).all()
    
    comparison_data = []
    for cls in main_classes:
        stats = cls.get_statistics()
        
        # 获取班级在各个作业上的平均分
        assignment_scores = []
        assignments = Assignment.query.all()
        
        for assignment in assignments:
            avg_score = db.session.query(func.avg(Submission.score))\
                       .join(User).filter(User.class_name == cls.name,
                                        Submission.assignment_id == assignment.id)\
                       .scalar()
            
            assignment_scores.append({
                'assignment': assignment.title,
                'avg_score': round(avg_score, 2) if avg_score else 0
            })
        
        comparison_data.append({
            'class': cls,
            'stats': stats,
            'assignment_scores': assignment_scores
        })
    
    return render_template('classes/class_comparison.html',
                         comparison_data=comparison_data)

@classes.route('/api/stats')
@login_required
@admin_or_teacher_required
def api_class_stats():
    """获取班级统计数据API"""
    all_classes = Class.query.all()
    
    data = {
        'labels': [],
        'datasets': [
            {
                'label': '学生数量',
                'data': [],
                'backgroundColor': 'rgba(54, 162, 235, 0.6)'
            },
            {
                'label': '平均分',
                'data': [],
                'backgroundColor': 'rgba(255, 99, 132, 0.6)'
            },
            {
                'label': '总提交数',
                'data': [],
                'backgroundColor': 'rgba(75, 192, 192, 0.6)'
            }
        ]
    }
    
    for cls in all_classes:
        if cls.student_count > 0:  # 只显示有学生的班级
            stats = cls.get_statistics()
            data['labels'].append(cls.name)
            data['datasets'][0]['data'].append(stats['student_count'])
            data['datasets'][1]['data'].append(stats['avg_score'])
            data['datasets'][2]['data'].append(stats['total_submissions'])
    
    return jsonify(data)

@classes.route('/api/<int:class_id>/progress')
@login_required
@admin_required
def api_class_progress(class_id):
    """获取班级作业进度API"""
    cls = Class.query.get_or_404(class_id)
    progress = cls.get_assignment_progress()
    
    data = {
        'labels': [p['assignment'].title for p in progress],
        'data': [p['progress_rate'] for p in progress]
    }
    
    return jsonify(data)

@classes.route('/sync', methods=['GET', 'POST'])
@login_required
@admin_or_teacher_required
def sync_classes():
    """同步班级数据"""
    try:
        synced_count = Class.sync_from_users()
        flash(f'成功同步 {synced_count} 个班级的数据', 'success')
    except Exception as e:
        flash(f'同步失败: {str(e)}', 'error')
    
    return redirect(url_for('classes.class_list'))

@classes.route('/add', methods=['POST'])
@login_required
@admin_required
def add_class():
    """添加新班级 (管理员专属)"""
    name = request.form.get('name')
    grade = request.form.get('grade')
    major = request.form.get('major')
    teacher_id = request.form.get('teacher_id')
    
    if not name:
        flash('班级名称不能为空', 'danger')
        return redirect(url_for('classes.class_list'))
        
    # 检查重名
    if Class.query.filter_by(name=name).first():
        flash(f'班级 "{name}" 已存在', 'danger')
        return redirect(url_for('classes.class_list'))
        
    try:
        new_class = Class(
            name=name,
            grade=grade,
            major=major,
            teacher_id=teacher_id if teacher_id else None
        )
        db.session.add(new_class)
        db.session.commit()
        flash(f'成功添加班级 "{name}"', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'添加班级失败: {str(e)}', 'danger')
        
    return redirect(url_for('classes.class_list'))


@classes.route('/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_class(class_id):
    """编辑班级信息 (管理员专属)"""
    cls = Class.query.get_or_404(class_id)
    # 获取所有教师用户以供选择
    teachers = User.query.filter_by(usertype='教师').all()
    
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        cls.teacher_id = teacher_id if teacher_id else None
        cls.major = request.form.get('major')
        cls.grade = request.form.get('grade')
        cls.name = request.form.get('name')
        
        db.session.commit()
        flash('班级信息更新成功', 'success')
        return redirect(url_for('classes.class_detail', class_id=class_id))
    
    return render_template('classes/edit_class.html', cls=cls, teachers=teachers)
