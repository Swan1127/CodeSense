"""
用户管理相关路由
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from itsdangerous import URLSafeTimedSerializer
from models import db, User, Submission
from utils.auth import login_required, admin_required
from sqlalchemy import desc, or_
from forms import EditProfileForm
import pandas as pd
import io
from datetime import datetime
import random

users = Blueprint('users', __name__)


@users.route('/users')
@login_required
@admin_required
def manage_users():
    # 获取搜索参数
    search = request.args.get('search', '')
    user_type = request.args.get('user_type', '')
    page = request.args.get('page', 1, type=int)
    
    # 构建查询
    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.student_id.ilike(f'%{search}%'),
                User.full_name.ilike(f'%{search}%')
            )
        )
    if user_type:
        query = query.filter_by(usertype=user_type)
    
    # 分页
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    users = pagination.items
    
    # 计算统计数据
    total_users = User.query.count()
    total_submissions = sum(user.submit_count for user in User.query.all())
    student_count = User.query.filter_by(usertype='学生').count()
    admin_count = User.query.filter_by(usertype='管理员').count()
    
    print("\n=== 用户统计数据 ===")
    print(f"总用户数: {total_users}")
    print(f"学生数量: {student_count}")
    print(f"管理员数量: {admin_count}")
    print(f"总提交数: {total_submissions}")
    
    # 准备图表数据
    user_type_chart_data = {
        'labels': ['学生', '管理员'],
        'data': [student_count, admin_count]
    }
    
    print("\n=== 用户类型图表数据 ===")
    print(user_type_chart_data)
    
    # 准备提交数量分布数据
    submission_counts = db.session.query(
        db.func.count(User.student_id).label('count'),
        db.case(
            (User.submit_count <= 5, '0-5次'),
            (User.submit_count <= 10, '6-10次'),
            (User.submit_count <= 15, '11-15次'),
            (User.submit_count <= 20, '16-20次'),
            (db.true(), '20次以上')
        ).label('range')
    ).group_by('range').all()
    
    print("\n=== 原始提交数量分布数据 ===")
    print(submission_counts)
    
    submission_chart_data = [0] * 5  # 初始化5个区间
    for count, range_name in submission_counts:
        if range_name == '0-5次':
            submission_chart_data[0] = count
        elif range_name == '6-10次':
            submission_chart_data[1] = count
        elif range_name == '11-15次':
            submission_chart_data[2] = count
        elif range_name == '16-20次':
            submission_chart_data[3] = count
        else:
            submission_chart_data[4] = count
    
    # 将列表转换为与user_type_chart_data相同格式的对象
    submission_chart_data = {
        'labels': ['0-5次', '6-10次', '11-15次', '16-20次', '20次以上'],
        'data': submission_chart_data
    }
    
    print("\n=== 处理后的提交数量图表数据 ===")
    print(submission_chart_data)
    
    return render_template('users.html',
                         users=users,
                         pagination=pagination,
                         search_term=search,
                         user_type=user_type,
                         total_users=total_users,
                         total_submissions=total_submissions,
                         student_count=student_count,
                         admin_count=admin_count,
                         user_type_chart_data=user_type_chart_data,
                         submission_chart_data=submission_chart_data)


@users.route('/delete_user/<string:student_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_user(student_id):
    """删除用户"""
    user_to_delete = User.query.get_or_404(student_id)
    
    # 只允许删除学生用户，不允许删除管理员
    if user_to_delete.usertype == '学生':
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('用户删除成功！')
    else:
        flash('无法删除管理员用户')
        
    return redirect(url_for('users.manage_users'))


@users.route('/view_submission')
@login_required
def view_submissions():
    """查看学生提交记录和学情分析"""
    try:
        # 优先使用URL参数中的student_id，如果没有则使用会话中的student_id
        student_id = request.args.get('student_id') or session.get('student_id')
        if not student_id:
            flash('会话已过期，请重新登录')
            return redirect(url_for('auth.login'))
            
        # 检查权限：只允许管理员或本人查看
        if session.get('usertype') != '管理员' and session.get('student_id') != student_id:
            flash('您无权查看此学生的提交记录', 'danger')
            return redirect(url_for('main.home'))
            
        per_page = 10
        page = request.args.get('page', 1, type=int)  # 获取当前页码，默认为1
        session['spage'] = page
        
        # 查询学生的所有提交记录（用于统计）
        all_submissions = Submission.query.filter_by(student_id=student_id).all()
        scores = [sub.score for sub in all_submissions if sub.score is not None]
        
        # 分页获取提交记录
        submissions = (Submission.query
                    .filter_by(student_id=student_id)
                    .order_by(desc(Submission.submitted_at))
                    .paginate(page=page, per_page=per_page, error_out=False))
        
        # 获取学生信息
        user = User.query.get_or_404(student_id)
        
        # 准备图表数据
        chart_data = {
            'x': [sub.assignment_id for sub in submissions.items],
            'y': [sub.score if sub.score is not None else 0 for sub in submissions.items],
            'pie_data': [
                scores.count(5) if 5 in scores else 0,
                scores.count(4) if 4 in scores else 0,
                scores.count(3) if 3 in scores else 0,
                scores.count(2) if 2 in scores else 0,
                scores.count(1) if 1 in scores else 0
            ]
        }
        
        # 计算能力分析数据（示例数据，实际应根据业务逻辑计算）
        # 这里我们使用随机数据进行演示，实际应用中应基于提交记录计算
        ability_data = {
            'student': {
                'algorithm': random.randint(60, 95),  # 算法能力
                'style': random.randint(60, 95),      # 代码风格
                'functionality': random.randint(60, 95), # 功能实现
                'efficiency': random.randint(60, 95),   # 效率优化
                'readability': random.randint(60, 95)   # 代码可读性
            },
            'class_avg': {
                'algorithm': random.randint(65, 85),
                'style': random.randint(65, 85),
                'functionality': random.randint(65, 85),
                'efficiency': random.randint(65, 85),
                'readability': random.randint(65, 85)
            }
        }
        
        return render_template('submissions.html', 
                            submissions=submissions, 
                            user=user, 
                            chart_data=chart_data,
                            ability_data=ability_data)
    except Exception as e:
        import traceback
        print(f'访问学情分析时出错: {str(e)}')
        print(traceback.format_exc())
        flash(f'访问学情分析时出错: {str(e)}')
        return redirect(url_for('main.home'))


@users.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """编辑个人资料"""
    form = EditProfileForm()
    user = User.query.get(session.get('student_id'))
    
    if form.validate_on_submit():
        try:
            # 更新用户信息
            user.username = form.username.data
            user.full_name = form.full_name.data
            user.class_name = form.class_name.data
            
            db.session.commit()
            flash('资料更新成功！', 'success')
            return redirect(url_for('users.view_submissions'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'danger')
    
    # 如果是GET请求，预填充表单
    if request.method == 'GET':
        form.username.data = user.username
        form.full_name.data = user.full_name
        form.class_name.data = user.class_name
    
    return render_template('edit_profile.html', form=form, user=user)


@users.route('/export_users')
@login_required
@admin_required
def export_users():
    """导出用户数据为Excel"""
    try:
        # 获取所有用户数据
        users_data = User.query.all()
        
        # 准备数据
        data = []
        for user in users_data:
            data.append({
                '用户名': user.username,
                '学号': user.student_id,
                '姓名': user.full_name,
                '用户类型': user.usertype,
                '班级': user.class_name,
                '提交次数': user.submit_count,
                '平均分数': round(user.user_ascore, 2) if user.user_ascore else 0,
                '总分': round(user.user_tscore, 2) if user.user_tscore else 0
            })
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 创建一个内存中的Excel文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='用户数据', index=False)
            
            # 获取工作表对象
            worksheet = writer.sheets['用户数据']
            
            # 调整列宽
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, max_length)
        
        output.seek(0)
        
        # 生成文件名 - 使用英文命名避免编码问题
        filename = f'user_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'导出数据时发生错误：{str(e)}', 'danger')
        return redirect(url_for('users.manage_users'))


@users.route('/view_student_details/<string:student_id>')
@login_required
@admin_required
def view_student_details(student_id):
    """管理员查看学生详情页面"""
    try:
        # 获取学生信息
        user = User.query.get_or_404(student_id)
        
        # 查询学生的所有提交记录
        all_submissions = Submission.query.filter_by(student_id=student_id).all()
        scores = [sub.score for sub in all_submissions if sub.score is not None]
        
        # 分页获取提交记录
        per_page = 10
        page = request.args.get('page', 1, type=int)
        submissions = (Submission.query
                     .filter_by(student_id=student_id)
                     .order_by(desc(Submission.submitted_at))
                     .paginate(page=page, per_page=per_page, error_out=False))
        
        # 准备图表数据
        chart_data = {
            'x': [sub.assignment_id for sub in submissions.items],
            'y': [sub.score if sub.score is not None else 0 for sub in submissions.items],
            'pie_data': [
                scores.count(5) if 5 in scores else 0,
                scores.count(4) if 4 in scores else 0,
                scores.count(3) if 3 in scores else 0,
                scores.count(2) if 2 in scores else 0,
                scores.count(1) if 1 in scores else 0
            ]
        }
        
        # 计算学生的提交统计
        submission_stats = {
            'total': len(all_submissions),
            'average_score': round(sum(scores) / len(scores), 2) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'score_distribution': {
                '5分': scores.count(5) if 5 in scores else 0,
                '4分': scores.count(4) if 4 in scores else 0,
                '3分': scores.count(3) if 3 in scores else 0,
                '2分': scores.count(2) if 2 in scores else 0,
                '1分': scores.count(1) if 1 in scores else 0
            }
        }
        
        # 获取最近提交记录
        recent_submissions = (Submission.query
                            .filter_by(student_id=student_id)
                            .order_by(desc(Submission.submitted_at))
                            .limit(5)
                            .all())
        
        # 获取学生排名信息
        all_students = (User.query
                       .filter_by(usertype='学生')
                       .order_by(desc(User.user_ascore))
                       .all())
        student_ranks = {student.student_id: i+1 for i, student in enumerate(all_students)}
        
        return render_template('student_details.html', 
                              user=user,
                              submissions=submissions,
                              chart_data=chart_data,
                              submission_stats=submission_stats,
                              recent_submissions=recent_submissions,
                              student_rank=student_ranks.get(student_id, 'N/A'),
                              total_students=len(all_students))
                              
    except Exception as e:
        import traceback
        print(f'访问学生详情页面时出错: {str(e)}')
        print(traceback.format_exc())
        flash(f'访问学生详情页面时出错: {str(e)}', 'danger')
        return redirect(url_for('users.manage_users'))


@users.route('/invite-teacher')
@login_required
@admin_required
def invite_teacher():
    """生成一个用于教师注册的邀请链接"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    # The token will be valid for 24 hours.
    token = serializer.dumps('teacher-invitation', salt='teacher-reg-salt')
    
    # Create the full invitation URL
    invite_url = url_for('auth.register_teacher', token=token, _external=True)
    
    return render_template('invite_teacher.html', invite_url=invite_url) 