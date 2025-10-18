"""
班级管理路由
"""
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from models import db, Class, User, Assignment, Submission
from utils.auth import admin_required

classes = Blueprint('classes', __name__, url_prefix='/classes')

@classes.route('/')
@login_required
@admin_required
def class_list():
    """班级列表页面"""
    # 获取所有班级及其统计信息
    class_data = []
    all_classes = Class.query.all()
    
    for cls in all_classes:
        stats = cls.get_statistics()
        class_data.append({
            'class': cls,
            'stats': stats,
            'top_students': cls.get_top_students(3)
        })
    
    # 按学生数量排序
    class_data.sort(key=lambda x: x['stats']['student_count'], reverse=True)
    
    return render_template('classes/class_list.html', 
                         class_data=class_data,
                         total_classes=len(all_classes))

@classes.route('/<int:class_id>')
@login_required
@admin_required
def class_detail(class_id):
    """班级详情页面"""
    cls = Class.query.get_or_404(class_id)
    
    # 获取班级统计
    stats = cls.get_statistics()
    
    # 获取班级学生列表（分页）
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    students = cls.students.filter_by(usertype='学生')\
                          .order_by(desc(User.user_ascore))\
                          .paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取作业进度
    assignment_progress = cls.get_assignment_progress()
    
    return render_template('classes/class_detail.html',
                         cls=cls,
                         stats=stats,
                         students=students,
                         assignment_progress=assignment_progress)

@classes.route('/compare')
@login_required
@admin_required
def class_comparison():
    """班级对比分析页面"""
    # 获取主要班级（学生数量>10的班级）
    main_classes = Class.query.filter(Class.student_count > 10).all()
    
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
@admin_required
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

@classes.route('/sync', methods=['POST'])
@login_required
@admin_required
def sync_classes():
    """同步班级数据"""
    try:
        synced_count = Class.sync_from_users()
        flash(f'成功同步 {synced_count} 个班级的数据', 'success')
    except Exception as e:
        flash(f'同步失败: {str(e)}', 'error')
    
    return redirect(url_for('classes.class_list'))

@classes.route('/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_class(class_id):
    """编辑班级信息"""
    cls = Class.query.get_or_404(class_id)
    
    if request.method == 'POST':
        cls.teacher_name = request.form.get('teacher_name')
        cls.major = request.form.get('major')
        cls.grade = request.form.get('grade')
        
        db.session.commit()
        flash('班级信息更新成功', 'success')
        return redirect(url_for('classes.class_detail', class_id=class_id))
    
    return render_template('classes/edit_class.html', cls=cls)
