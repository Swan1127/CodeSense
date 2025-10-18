"""
作业相关路由
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, current_app
from models import db, User, Assignment, Submission, SystemLog
from forms import AssignmentForm, SubmissionForm
from utils.auth import login_required, admin_required
from utils.code_evaluator import evaluate_cpp_code, initialize_models
from io import BytesIO
from sqlalchemy import desc
import traceback  # 添加traceback模块
import os
from datetime import datetime

assignments = Blueprint('assignments', __name__)

# 在模块开始时初始化模型
initialize_models()


@assignments.route('/assignments')
@login_required
def manage_assignments():
    """显示作业列表"""
    try:
        per_page = 10  # 每页显示的题目数量
        page = request.args.get('page', 1, type=int)  # 获取当前页码，默认为1
        search_term = request.args.get('search', '')  # 获取搜索关键词
        sort_by = request.args.get('sort_by', 'id')  # 获取排序字段，默认为id
        sort_order = request.args.get('sort_order', 'asc')  # 获取排序顺序，默认为升序
        
        print(f"当前页码: {page}, 搜索词: {search_term}")
        session['apage'] = page
        
        # 构建查询
        query = Assignment.query
        
        # 添加排序逻辑
        if sort_by == 'id':
            if sort_order == 'asc':
                query = query.order_by(Assignment.id.asc())
            else:
                query = query.order_by(Assignment.id.desc())
        elif sort_by == 'title':
            if sort_order == 'asc':
                query = query.order_by(Assignment.title.asc())
            else:
                query = query.order_by(Assignment.title.desc())
        elif sort_by == 'count':
            if sort_order == 'asc':
                query = query.order_by(Assignment.count.asc())
            else:
                query = query.order_by(Assignment.count.desc())
        elif sort_by == 'average_score':
            if sort_order == 'asc':
                query = query.order_by(Assignment.average_score.asc())
            else:
                query = query.order_by(Assignment.average_score.desc())
        
        # 添加搜索条件
        if search_term:
            query = query.filter(
                db.or_(
                    Assignment.title.ilike(f'%{search_term}%'),
                    Assignment.description.ilike(f'%{search_term}%')
                )
            )
        
        # 获取分页的作业列表
        print("正在获取作业列表...")
        assignment_list = query.paginate(page=page, per_page=per_page, error_out=False)
        print(f"获取到 {len(assignment_list.items)} 个作业")
        
        # 获取统计信息
        total_submissions = Submission.query.count()
        student_count = db.session.query(db.func.count(db.distinct(Submission.student_id))).scalar() or 0
        
        # 根据用户类型展示不同视图
        usertype = session.get('usertype')
        print(f"用户类型: {usertype}")
        
        if usertype == '管理员':
            print("显示管理员视图")
            return render_template(
                'assignments.html', 
                assignments=assignment_list,
                total_submissions=total_submissions,
                student_count=student_count,
                search_term=search_term,
                sort_by=sort_by,
                sort_order=sort_order
            )
        else:
            # 对于学生用户，获取每个作业的最高得分
            student_id = session.get('student_id')
            print(f"学生ID: {student_id}")
            
            if not student_id:
                flash('会话已过期，请重新登录')
                return redirect(url_for('auth.login'))
            
            print("获取每个作业的最高得分...")    
            for assignment in assignment_list.items:
                try:
                    max_score = Submission.query.filter_by(
                        assignment_id=assignment.id,
                        student_id=student_id
                    ).order_by(desc(Submission.score)).first()
                    
                    assignment.max_student_score = max_score.score if max_score else 0
                    print(f"作业 {assignment.id} 最高分: {assignment.max_student_score}")
                except Exception as e:
                    print(f"获取作业 {assignment.id} 分数时出错: {str(e)}")
                    assignment.max_student_score = 0
            
            print("渲染学生作业视图...")
            return render_template(
                's_assignments.html', 
                assignments=assignment_list,
                search_term=search_term,
                sort_by=sort_by,
                sort_order=sort_order
            )
    except Exception as e:
        print(f"访问题库时出错: {str(e)}")
        print(traceback.format_exc())  # 打印完整的堆栈跟踪
        flash(f'访问题库时出错: {str(e)}')
        return redirect(url_for('main.home'))


@assignments.route('/add_assignment', methods=['GET', 'POST'])
@login_required
@admin_required
def add_assignment():
    """添加新作业"""
    form = AssignmentForm()
    
    if form.validate_on_submit():
        # 检查作业ID是否已存在
        assignment_id = form.assignment_id.data
        existing_assignment = Assignment.query.get(assignment_id)
        
        if existing_assignment:
            flash('该作业ID已存在，请使用其他ID', 'danger')
            return render_template('add_assignment.html', form=form)
        
        # 创建新作业
        new_assignment = Assignment(
            id=assignment_id,
            title=form.title.data,
            description=form.description.data,
            total_score=0,
            average_score=0.0,
            count=0
        )
        
        try:
            db.session.add(new_assignment)
            db.session.commit()
            
            # 添加系统日志
            admin_id = session.get('student_id')
            admin_user = User.query.get(admin_id)
            SystemLog.add_log(
                log_type='添加作业',
                content=f'管理员 {admin_user.username} 添加了新作业：{new_assignment.title} (ID: {new_assignment.id})',
                user_id=admin_id,
                icon='bi bi-file-earmark-plus'
            )
            
            flash('作业添加成功！', 'success')
            return redirect(url_for('assignments.manage_assignments'))
        except Exception as e:
            db.session.rollback()
            flash(f'添加作业失败: {str(e)}', 'danger')
    
    return render_template('add_assignment.html', form=form)


@assignments.route('/delete_assignment/<int:assignment_id>', methods=['POST'])
@login_required
@admin_required
def delete_assignment(assignment_id):
    """删除作业"""
    assignment_to_delete = Assignment.query.get_or_404(assignment_id)
    assignment_title = assignment_to_delete.title
    
    try:
        db.session.delete(assignment_to_delete)
        db.session.commit()
        
        # 添加系统日志
        admin_id = session.get('student_id')
        admin_user = User.query.get(admin_id)
        SystemLog.add_log(
            log_type='删除作业',
            content=f'管理员 {admin_user.username} 删除了作业：{assignment_title} (ID: {assignment_id})',
            user_id=admin_id,
            icon='bi bi-trash'
        )
        
        flash('作业已成功删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除作业失败: {str(e)}', 'danger')
    
    return redirect(url_for('assignments.manage_assignments'))


@assignments.route('/view_assignment/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    """查看作业详情，不包括代码提交功能"""
    # 获取作业详情
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 获取用户信息
    student_id = session.get('student_id')
    usertype = session.get('usertype')
    if not student_id:
        flash('会话已过期，请重新登录')
        return redirect(url_for('auth.login'))
    
    # 获取该作业的提交总数
    submission_count = Submission.query.filter_by(
        assignment_id=assignment_id
    ).count()
    
    # 获取全部用户的平均分
    average_score = assignment.average_score if assignment and assignment.count > 0 else 0
    
    # 根据用户类型提供不同的数据
    if usertype == '管理员':
        # 管理员视图 - 提供更多统计数据
        
        # 获取参与学生数量
        student_count = db.session.query(db.func.count(db.distinct(Submission.student_id)))\
                        .filter_by(assignment_id=assignment_id).scalar() or 0
        
        # 获取分数分布
        score_counts = db.session.query(
            Submission.score, db.func.count(Submission.id)
        ).filter_by(assignment_id=assignment_id).group_by(Submission.score).all()
        
        score_distribution = {int(score): count for score, count in score_counts}
        
        # 获取最近的10个提交记录
        recent_submissions = Submission.query\
            .filter_by(assignment_id=assignment_id)\
            .order_by(desc(Submission.submitted_at))\
            .limit(10)\
            .all()
            
        # 添加用户信息到提交记录
        for submission in recent_submissions:
            submission.user = User.query.get(submission.student_id)
            
        return render_template(
            'assignment_detail.html',
            assignment=assignment,
            submission_count=submission_count,
            average_score=average_score,
            student_count=student_count,
            score_distribution=score_distribution,
            recent_submissions=recent_submissions,
            usertype=usertype
        )
    else:
        # 学生视图 - 提供个人提交数据
        latest_submission = Submission.query.filter_by(
            student_id=student_id,
            assignment_id=assignment_id
        ).order_by(desc(Submission.id)).first()
        
        # 获取该学生的最高分
        max_score = db.session.query(db.func.max(Submission.score)).filter_by(
            student_id=student_id,
            assignment_id=assignment_id
        ).scalar() or 0
        
        return render_template(
            'assignment_detail.html',
            assignment=assignment,
            latest_submission=latest_submission,
            submission_count=submission_count,
            average_score=average_score,
            max_score=max_score,
            usertype=usertype
        )


@assignments.route('/submit/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def submit_code(assignment_id):
    """提交代码"""
    # 获取作业详情
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 获取用户最近的提交
    student_id = session.get('student_id')
    if not student_id:
        flash('会话已过期，请重新登录')
        return redirect(url_for('auth.login'))
        
    # 获取用户最近的提交及提交历史
    latest_submission = Submission.query.filter_by(
        student_id=student_id,
        assignment_id=assignment_id
    ).order_by(desc(Submission.id)).first()
    
    # 获取该作业的所有提交记录用于显示历史
    submissions = Submission.query.filter_by(
        student_id=student_id,
        assignment_id=assignment_id
    ).order_by(desc(Submission.submitted_at)).all()
    
    # 获取该作业的提交总数
    submission_count = Submission.query.filter_by(
        assignment_id=assignment_id
    ).count()
    
    # 创建提交表单
    form = SubmissionForm()
    
    if form.validate_on_submit():
        # 获取用户提交的代码和语言
        code = form.code.data
        language = form.language.data
        
        # 检查代码长度
        if len(code.strip()) < 10:
            flash('代码太短，请提交更完整的代码。', 'danger')
            return render_template(
                'submit_code.html',
                form=form,
                assignment=assignment,
                latest_submission=latest_submission,
                submissions=submissions,
                submission_count=submission_count
            )
            
        try:
            # 不再显示评估中状态
            # flash('正在评估代码，请稍候...', 'info')
            
            # 创建新的提交记录，设置状态为pending
            submission = Submission(
                student_id=student_id,
                assignment_id=assignment_id,
                code=code,
                language=language,
                status='pending'
            )
            
            # 先保存到数据库获取ID
            db.session.add(submission)
            db.session.commit()
            
            # 调用评估函数
            try:
                # 提供assignment_title作为上下文
                assignment_title = assignment.title
                print(f"开始评估代码，题目: {assignment_title}，语言: cpp")
                
                # 使用C++评估器评估代码
                print(f"使用C++评估器评估代码")
                score, feedback = evaluate_cpp_code(code, assignment_title=assignment_title)
                
                # 更新提交记录
                submission.score = score
                submission.status = 'evaluated'
                
                # 确保feedback是字符串
                if feedback is None:
                    feedback = ""
                elif isinstance(feedback, bytes):
                    feedback = feedback.decode('utf-8', errors='replace')
                
                # 获取结构化评估数据
                from utils.code_evaluator import llm_evaluator
                if hasattr(llm_evaluator, '_last_structured_data'):
                    structured_data = llm_evaluator._last_structured_data
                    import json
                    # 保存结构化数据为JSON格式
                    submission.ai_feedback = json.dumps(structured_data, ensure_ascii=False)
                    print("成功保存结构化AI评估数据")
                else:
                    # 如果没有结构化数据，使用传统方式
                    if isinstance(feedback, str) and len(feedback) > 0:
                        # 检查是否包含评估建议
                        if "【" in feedback and "】" in feedback or "改进建议" in feedback:
                            # 将评估建议保存到ai_feedback字段中
                            submission.ai_feedback = feedback
                            print("使用传统方式保存评估建议")
                
                submission.feedback = feedback
                
            except Exception as e:
                print(f"评估代码时出错: {e}")
                print(traceback.format_exc())
                submission.status = 'failed'
                submission.score = 1  # 出错时给1分
                submission.feedback = f"评估过程中出错: {str(e)}"
                
            # 更新作业统计信息
            assignment.total_score += submission.score
            assignment.count += 1
            assignment.average_score = assignment.total_score / assignment.count
            
            # 更新用户统计信息
            user = User.query.get(student_id)
            user.submit_count += 1
            user.user_tscore += submission.score
            user.user_ascore = user.user_tscore / user.submit_count
            
            # 保存到数据库
            db.session.commit()
            
            # 添加系统日志
            SystemLog.add_log(
                log_type='提交代码',
                content=f'用户 {user.username} ({user.full_name}) 提交了作业 {assignment.title} 的代码，得分：{submission.score}/5',
                user_id=student_id,
                icon='bi bi-code-square'
            )
            
            # 触发异步能力趋势分析更新
            try:
                from utils.async_tasks import add_ability_trend_task
                task_id = add_ability_trend_task(student_id)
                current_app.logger.info(f"已触发学生 {student_id} 的能力趋势异步更新任务: {task_id}")
            except Exception as e:
                current_app.logger.error(f"触发能力趋势异步更新失败: {str(e)}", exc_info=True)
            
            if submission.status == 'evaluated':
                flash(f'代码评估完成！您的得分：{submission.score}/5分', 'success')
                # 不再添加JavaScript脚本
                # flash('<script>setTimeout(function() { const loader = document.getElementById("loading-container"); if (loader) loader.style.display = "none"; }, 500);</script>', 'info')
            else:
                flash(f'代码已提交，但评估过程中出现错误，请联系管理员。', 'warning')
                # 不再添加JavaScript脚本
                # flash('<script>setTimeout(function() { const loader = document.getElementById("loading-container"); if (loader) loader.style.display = "none"; }, 500);</script>', 'info')
                
            return redirect(url_for('assignments.view_submission', submission_id=submission.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"处理提交时出错: {e}")
            print(traceback.format_exc())
            flash(f'提交代码时出错: {str(e)}', 'danger')
    
    return render_template(
        'submit_code.html',
        form=form,
        assignment=assignment,
        latest_submission=latest_submission,
        submissions=submissions,
        submission_count=submission_count
    )


@assignments.route('/download_code/<int:submission_id>')
@login_required
def download_code(submission_id):
    """下载提交的代码"""
    try:
        submission = Submission.query.get_or_404(submission_id)
        
        # 确保只有提交者或管理员可以下载代码
        if session['usertype'] != '管理员' and session['student_id'] != submission.student_id:
            flash('您无权下载该代码', 'danger')
            return redirect(url_for('main.home'))
        
        # 准备代码内容
        code_content = ""
        if submission.code is not None:
            # 处理不同编码的情况
            if isinstance(submission.code, bytes):
                # 尝试不同的编码方式
                encodings = ['utf-8', 'latin1', 'gbk', 'gb2312', 'gb18030', 'big5']
                decoded = False
                for encoding in encodings:
                    try:
                        code_content = submission.code.decode(encoding, errors='replace')
                        decoded = True
                        print(f"下载代码：成功使用 {encoding} 解码")
                        break
                    except Exception as e:
                        print(f"下载代码：使用 {encoding} 解码失败: {str(e)}")
                        continue
                
                if not decoded:
                    # 如果所有编码都失败，使用latin1作为最后的选择
                    code_content = submission.code.decode('latin1', errors='replace')
            else:
                code_content = submission.code
        
        # 移除可能的BOM标记
        if code_content.startswith('\ufeff'):
            code_content = code_content[1:]
        
        # 设置文件扩展名为.cpp
        file_ext = '.cpp'
        
        # 准备文件下载
        text_buffer = BytesIO(code_content.encode('utf-8', errors='replace'))
        
        # 设置响应头
        text_buffer.seek(0)
        response = Response(
            text_buffer,
            headers={'Content-Disposition': f'attachment; filename=submission_{submission_id}{file_ext}'},
            mimetype='text/plain'
        )
        
        return response
    except Exception as e:
        print(f"下载代码时出错: {str(e)}")
        print(traceback.format_exc())
        flash(f'下载代码时出错: {str(e)}', 'danger')
        return redirect(url_for('assignments.view_submission', submission_id=submission_id))


@assignments.route('/student_assignments')
@login_required
def student_assignments():
    """学生查看作业列表"""
    page = request.args.get('page', 1, type=int)
    
    try:
        # 获取学生ID
        student_id = session.get('student_id')
        if not student_id:
            flash('会话已过期，请重新登录', 'danger')
            return redirect(url_for('auth.login'))
        
        # 查询所有作业
        assignments_query = Assignment.query
        
        # 获取排序参数
        sort_by = request.args.get('sort', 'id')
        sort_order = request.args.get('order', 'desc')
        
        # 添加排序逻辑
        if sort_by == 'id':
            if sort_order == 'asc':
                assignments_query = assignments_query.order_by(Assignment.id.asc())
            else:
                assignments_query = assignments_query.order_by(Assignment.id.desc())
        elif sort_by == 'title':
            if sort_order == 'asc':
                assignments_query = assignments_query.order_by(Assignment.title.asc())
            else:
                assignments_query = assignments_query.order_by(Assignment.title.desc())
        elif sort_by == 'count':
            if sort_order == 'asc':
                assignments_query = assignments_query.order_by(Assignment.count.asc())
            else:
                assignments_query = assignments_query.order_by(Assignment.count.desc())
        elif sort_by == 'average_score':
            if sort_order == 'asc':
                assignments_query = assignments_query.order_by(Assignment.average_score.asc())
            else:
                assignments_query = assignments_query.order_by(Assignment.average_score.desc()).order_by(Assignment.created_time.desc())
        else:
            # 默认排序
            assignments_query = assignments_query.order_by(Assignment.id.desc())
            
        assignments = assignments_query.paginate(page=page, per_page=10)
        
        # 获取学生每个作业的最高分
        max_scores = {}
        for assignment in assignments.items:
            submission = Submission.query.filter_by(
                assignment_id=assignment.id,
                student_id=student_id
            ).order_by(Submission.score.desc()).first()
            
            if submission:
                max_scores[assignment.id] = submission.score
            else:
                max_scores[assignment.id] = 0
        
        return render_template('s_assignments.html',
                              assignments=assignments,
                              max_scores=max_scores,
                              sort_by=sort_by,
                              sort_order=sort_order)
    except Exception as e:
        print(f"获取学生作业列表时出错: {str(e)}")
        print(traceback.format_exc())
        flash('获取学生作业列表时出错', 'danger')
        return redirect(url_for('main.home'))


@assignments.route('/view_submission/<int:submission_id>')
@login_required
def view_submission(submission_id):
    """查看提交详情"""
    try:
        submission = Submission.query.get_or_404(submission_id)
        # 检查是否为当前用户的提交或管理员
        if submission.student_id != session.get('student_id') and session.get('usertype') != '管理员':
            flash('您无权查看此提交', 'danger')
            return redirect(url_for('main.home'))
        
        # 处理可能的编码问题
        try:
            if submission.code is not None:
                if isinstance(submission.code, bytes):
                    # 尝试不同的编码方式
                    encodings = ['utf-8', 'latin1', 'cp1252', 'gbk', 'gb2312', 'gb18030', 'big5']
                    decoded = False
                    for encoding in encodings:
                        try:
                            submission.code = submission.code.decode(encoding, errors='replace')
                            decoded = True
                            print(f"成功使用 {encoding} 解码代码内容")
                            break
                        except Exception as e:
                            print(f"使用 {encoding} 解码失败: {str(e)}")
                            continue
                    
                    if not decoded:
                        # 如果所有编码都失败，使用十六进制表示
                        submission.code = f"[代码内容是二进制数据: {submission.code.hex()[:100]}...]"
            else:
                submission.code = ""
        except Exception as e:
            print(f"解码代码内容时出错: {str(e)}")
            print(traceback.format_exc())
            submission.code = "[代码内容无法显示]"
            
        try:
            if submission.feedback is not None:
                if isinstance(submission.feedback, bytes):
                    # 尝试不同的编码方式
                    encodings = ['utf-8', 'latin1', 'cp1252', 'gbk', 'gb2312', 'gb18030', 'big5']
                    decoded = False
                    for encoding in encodings:
                        try:
                            submission.feedback = submission.feedback.decode(encoding, errors='replace')
                            decoded = True
                            print(f"成功使用 {encoding} 解码反馈内容")
                            break
                        except Exception as e:
                            print(f"使用 {encoding} 解码失败: {str(e)}")
                            continue
                    
                    if not decoded:
                        # 如果所有编码都失败，使用十六进制表示
                        submission.feedback = f"[反馈内容是二进制数据: {submission.feedback.hex()[:100]}...]"
            else:
                submission.feedback = ""
        except Exception as e:
            print(f"解码反馈内容时出错: {str(e)}")
            print(traceback.format_exc())
            submission.feedback = "[反馈内容无法显示]"
        
        assignment = Assignment.query.get_or_404(submission.assignment_id)
        return render_template('submission_detail.html', submission=submission, assignment=assignment)
    except Exception as e:
        print(f"查看提交详情时出错: {str(e)}")
        print(traceback.format_exc())
        flash(f'查看提交详情时出错: {str(e)}', 'danger')
        return redirect(url_for('assignments.student_assignments'))


@assignments.route('/all_submissions')
@login_required
@admin_required
def all_submissions():
    """管理员查看所有提交记录"""
    try:
        per_page = 15
        page = request.args.get('page', 1, type=int)
        
        # 获取筛选参数
        student_id = request.args.get('student_id', '')
        assignment_id = request.args.get('assignment_id', '')
        min_score = request.args.get('min_score', '', type=float)
        max_score = request.args.get('max_score', '', type=float)
        
        # 构建查询
        query = Submission.query
        
        if student_id:
            query = query.filter(Submission.student_id == student_id)
        if assignment_id:
            query = query.filter(Submission.assignment_id == assignment_id)
        if min_score:
            query = query.filter(Submission.score >= min_score)
        if max_score:
            query = query.filter(Submission.score <= max_score)
            
        # 分页获取提交记录，并按提交时间降序排序
        submissions = query.order_by(desc(Submission.submitted_at)).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # 获取所有学生和作业，用于筛选下拉框
        students = User.query.filter_by(usertype='学生').all()
        assignments = Assignment.query.all()
        
        # 创建学生ID到用户名的映射字典
        user_dict = {}
        for student in students:
            user_dict[student.student_id] = student.username
        
        return render_template('all_submissions.html', 
                              submissions=submissions,
                              students=students,
                              assignments=assignments,
                              user_dict=user_dict,
                              filters={
                                  'student_id': student_id,
                                  'assignment_id': assignment_id,
                                  'min_score': min_score,
                                  'max_score': max_score
                              })
    except Exception as e:
        print(f"查看所有提交记录时出错: {str(e)}")
        print(traceback.format_exc())
        flash(f'查看所有提交记录时出错: {str(e)}', 'danger')
        return redirect(url_for('main.admin_dashboard'))


@assignments.route('/submission-history/<int:assignment_id>')
@login_required
def submission_history(assignment_id):
    """查看特定作业的提交历史"""
    # 获取作业信息
    assignment = Assignment.query.get_or_404(assignment_id)
    
    # 获取当前学生ID
    student_id = session.get('student_id')
    if not student_id:
        flash('会话已过期，请重新登录', 'danger')
        return redirect(url_for('auth.login'))
    
    # 获取该作业的所有提交记录，按时间降序排列
    submissions = Submission.query.filter_by(
        student_id=student_id,
        assignment_id=assignment_id
    ).order_by(desc(Submission.submitted_at)).all()
    
    # 获取学生信息
    student = User.query.get(student_id)
    
    # 计算提交统计信息
    total_submissions = len(submissions)
    average_score = sum(s.score or 0 for s in submissions) / total_submissions if total_submissions > 0 else 0
    best_submission = max(submissions, key=lambda s: s.score or 0) if submissions else None
    best_score = best_submission.score if best_submission else 0
    
    # 按时间分组的提交
    submissions_by_date = {}
    for submission in submissions:
        date_key = submission.submitted_at.strftime('%Y-%m-%d')
        if date_key not in submissions_by_date:
            submissions_by_date[date_key] = []
        submissions_by_date[date_key].append(submission)
    
    # 渲染模板
    return render_template(
        'submission_history.html',
        assignment=assignment,
        submissions=submissions,
        submissions_by_date=submissions_by_date,
        student=student,
        stats={
            'total': total_submissions,
            'average_score': average_score,
            'best_score': best_score
        }
    ) 