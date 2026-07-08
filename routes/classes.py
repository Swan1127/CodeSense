"""
班级管理路由
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, desc
import pandas as pd
from models import db, Class, StudentRoster, User, Assignment, Submission
from services.teacher_analytics import build_class_learning_rows
from utils.auth import admin_required, admin_or_teacher_required

classes = Blueprint('classes', __name__, url_prefix='/classes')


def _can_manage_class(cls):
    return current_user.is_admin or cls.teacher_id == current_user.student_id


def _clean_cell(value):
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


def _pick_column(df, candidates):
    normalized = {str(col).strip(): col for col in df.columns}
    for name in candidates:
        if name in normalized:
            return normalized[name]
    return None


def _read_roster_dataframe(file_storage):
    filename = (file_storage.filename or '').lower()
    if filename.endswith(('.xlsx', '.xls')):
        return pd.read_excel(file_storage, dtype=str)
    if filename.endswith('.csv'):
        return pd.read_csv(file_storage, dtype=str, encoding='utf-8-sig')
    raise ValueError('仅支持 .xlsx、.xls、.csv 格式的学生名单')

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
        cls.ensure_teacher_bind_code()
    db.session.commit()

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


@classes.route('/bind', methods=['POST'])
@login_required
@admin_or_teacher_required
def bind_class():
    """教师使用班级绑定码绑定已有班级。"""
    if not current_user.is_teacher:
        flash('只有教师账号可以使用班级绑定码', 'danger')
        return redirect(url_for('classes.class_list'))

    bind_code = (request.form.get('bind_code') or '').strip().upper()
    if not bind_code:
        flash('请输入班级绑定码', 'danger')
        return redirect(url_for('classes.class_list'))

    cls = Class.query.filter(func.upper(Class.teacher_bind_code) == bind_code).first()
    if not cls:
        flash('班级绑定码无效，请检查后重试', 'danger')
        return redirect(url_for('classes.class_list'))

    if cls.teacher_id and cls.teacher_id != current_user.student_id:
        flash(f'班级 "{cls.name}" 已绑定其他教师，请联系管理员处理', 'danger')
        return redirect(url_for('classes.class_list'))

    cls.teacher_id = current_user.student_id
    db.session.commit()
    flash(f'已绑定班级 "{cls.name}"', 'success')
    return redirect(url_for('classes.class_list'))


@classes.route('/<int:class_id>/unbind', methods=['POST'])
@login_required
@admin_or_teacher_required
def unbind_class(class_id):
    """解绑教师与班级的关系。"""
    cls = Class.query.get_or_404(class_id)
    if not _can_manage_class(cls):
        flash('您没有权限解绑此班级', 'danger')
        return redirect(url_for('classes.class_list'))

    cls.teacher_id = None
    db.session.commit()
    flash(f'已解绑班级 "{cls.name}"', 'success')
    return redirect(url_for('classes.class_list'))


@classes.route('/<int:class_id>/reset-bind-code', methods=['POST'])
@login_required
@admin_required
def reset_bind_code(class_id):
    """管理员重置班级绑定码。"""
    cls = Class.query.get_or_404(class_id)
    new_code = cls.reset_teacher_bind_code()
    db.session.commit()
    flash(f'班级 "{cls.name}" 的新绑定码为 {new_code}', 'success')
    return redirect(url_for('classes.class_detail', class_id=class_id))


@classes.route('/<int:class_id>/import-students', methods=['POST'])
@login_required
@admin_or_teacher_required
def import_students(class_id):
    """导入当前班级学生名单，供学生注册时自动绑定班级。"""
    cls = Class.query.get_or_404(class_id)
    if not _can_manage_class(cls):
        flash('您没有权限导入此班级的学生名单', 'danger')
        return redirect(url_for('classes.class_list'))

    upload = request.files.get('student_file')
    if not upload or not upload.filename:
        flash('请选择要导入的学生名单文件', 'danger')
        return redirect(url_for('classes.class_detail', class_id=class_id))

    try:
        df = _read_roster_dataframe(upload)
        student_id_col = _pick_column(df, ['学号', 'student_id', '学生学号', '账号'])
        full_name_col = _pick_column(df, ['姓名', 'full_name', '学生姓名', '名字'])
        if not student_id_col or not full_name_col:
            flash('名单必须包含“学号”和“姓名”两列', 'danger')
            return redirect(url_for('classes.class_detail', class_id=class_id))

        imported_count = 0
        bound_existing_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            student_id = _clean_cell(row.get(student_id_col))
            full_name = _clean_cell(row.get(full_name_col))
            if not student_id or not full_name:
                skipped_count += 1
                continue

            existing_user = User.query.get(student_id)
            if existing_user and existing_user.usertype != '学生':
                skipped_count += 1
                continue

            roster = StudentRoster.query.filter_by(student_id=student_id).first()
            if not roster:
                roster = StudentRoster(student_id=student_id, full_name=full_name, class_id=cls.id,
                                       class_name_snapshot=cls.name)
                db.session.add(roster)

            roster.full_name = full_name
            roster.class_id = cls.id
            roster.class_name_snapshot = cls.name
            roster.imported_by = current_user.student_id

            if existing_user:
                existing_user.full_name = existing_user.full_name or full_name
                existing_user.class_id = cls.id
                existing_user.class_name = cls.name
                roster.is_registered = True
                roster.registered_user_id = existing_user.student_id
                bound_existing_count += 1
            else:
                roster.is_registered = False
                roster.registered_user_id = None
                imported_count += 1

        db.session.commit()
        flash(f'名单导入完成：新增待注册 {imported_count} 人，已绑定现有学生 {bound_existing_count} 人，跳过 {skipped_count} 行', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'导入失败：{str(e)}', 'danger')

    return redirect(url_for('classes.class_detail', class_id=class_id))

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
    cls.ensure_teacher_bind_code()
    db.session.commit()
    roster_total = StudentRoster.query.filter_by(class_id=cls.id).count()
    roster_registered = StudentRoster.query.filter_by(class_id=cls.id, is_registered=True).count()
    
    # 获取班级学生列表（分页）
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    students = cls.students.filter_by(usertype='学生')\
                          .order_by(desc(User.user_ascore))\
                          .paginate(page=page, per_page=per_page, error_out=False)
    learning_rows = build_class_learning_rows(cls, students=students.items)
    
    # 获取作业进度 (支持分页)
    assign_page = request.args.get('assign_page', 1, type=int)
    assignment_progress = cls.get_assignment_progress(page=assign_page, per_page=10)
    
    return render_template('classes/class_detail.html',
                         cls=cls,
                         stats=stats,
                         students=students,
                         learning_rows=learning_rows,
                         assignment_progress=assignment_progress['items'],
                         assignment_pagination=assignment_progress['pagination'],
                         roster_total=roster_total,
                         roster_registered=roster_registered)

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
