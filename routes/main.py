"""
主要功能路由
"""
import datetime
import csv
import io
import json  # 添加json模块导入
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, User, Assignment, Submission, SystemLog, SystemConfig
from utils.auth import admin_required

main = Blueprint('main', __name__)

# 添加编辑器测试路由
@main.route('/test_editor')
def test_editor():
    """编辑器测试页面"""
    return render_template('test_editor.html')

# 添加C++代码编辑器示例路由
@main.route('/cpp_editor_demo')
def cpp_editor_demo():
    """C++代码编辑器示例页面"""
    return render_template('cpp_editor_demo.html')

# 添加全局上下文处理器，使模板可以使用now()函数
@main.app_context_processor
def inject_now():
    return {'now': datetime.datetime.now}

@main.route('/home')
@login_required
def home():
    """用户主页"""
    # 初始化页码
    session['apage'] = 1
    session['spage'] = 1
    session['upage'] = 1
    
    # 获取当前登录用户的个人信息
    user = current_user
    
    # 根据用户类型显示不同页面
    if user.is_admin:
        return redirect(url_for('main.admin_dashboard'))
    elif user.is_teacher:
        return redirect(url_for('main.teacher_dashboard'))
    else:
        student_id = current_user.student_id
        class_name = current_user.class_name

        # 1. 获取分配给该学生班级的作业
        assigned_assignments_query = Assignment.query
        if class_name:
            assigned_assignments_query = assigned_assignments_query.filter(
                Assignment.target_classes.like(f'%{class_name}%')
            )
        else:
            # 如果没有班级，则没有作业
            assigned_assignments_query = assigned_assignments_query.filter(db.false())
        
        assigned_assignments = assigned_assignments_query.all()
        assigned_assignment_ids = [a.id for a in assigned_assignments]

        # 2. 基于已分配的作业重新计算统计数据
        assignments_count = len(assigned_assignment_ids)

        # 筛选只针对已分配作业的提交
        submissions_query = Submission.query.filter(
            Submission.student_id == student_id,
            Submission.assignment_id.in_(assigned_assignment_ids)
        )
        
        submissions_count = submissions_query.count()

        average_score_query = db.session.query(func.avg(Submission.score)).filter(
            Submission.student_id == student_id,
            Submission.assignment_id.in_(assigned_assignment_ids)
        ).scalar()
        average_score = average_score_query if average_score_query else 0

        # 3. 获取用于显示的提交记录（也需要筛选）
        submissions = submissions_query.order_by(Submission.submitted_at.desc()).all()
        

        # 准备提交记录数据
        submission_data = []
        for sub in submissions:
            if sub.code and sub.assignment:
                submission_data.append({
                    'assignment_title': sub.assignment.title,
                    'code': sub.code,
                    'score': sub.score,
                    'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                })
        
        # 异步架构：检查能力趋势分析任务状态
        from models import AbilityTrend
        trend_record = AbilityTrend.get_or_create(student_id)
        
        print(f"🔍 检查趋势记录 - 状态: {trend_record.status}, 数据存在: {bool(trend_record.trend_data)}")
        print(f"🔍 详细检查: trend_data类型={type(trend_record.trend_data)}, 长度={len(trend_record.trend_data) if trend_record.trend_data else 0}")
        print(f"🔍 条件1 (status=='completed'): {trend_record.status == 'completed'}")
        print(f"🔍 条件2 (trend_data存在): {bool(trend_record.trend_data)}")
        print(f"🔍 条件3 (trend_data非空): {trend_record.trend_data is not None and len(str(trend_record.trend_data)) > 0}")
        
        # 修复条件判断逻辑
        if trend_record.status == 'failed':
            ability_analysis = {
                "trend": "能力分析失败",
                "improvement": "在上次分析过程中出现问题，请稍后点击重试。",
                "suggestions": [],
                "_status": "failed",
                "_last_updated": trend_record.last_updated.strftime('%Y-%m-%d %H:%M:%S') if trend_record.last_updated else None
            }
        elif (trend_record.status == 'completed' and 
            trend_record.trend_data is not None and 
            len(str(trend_record.trend_data)) > 0):
            # 有已完成的分析结果，使用它
            try:
                ability_analysis = trend_record.get_trend_dict()
                # 添加状态信息供前端使用
                ability_analysis['_status'] = 'completed'
                ability_analysis['_last_updated'] = trend_record.last_updated.strftime('%Y-%m-%d %H:%M:%S') if trend_record.last_updated else None
                print(f"✅ 使用已缓存的能力趋势分析结果 (状态: {trend_record.status})")
                print(f"📊 趋势: {ability_analysis.get('trend', '')[:80]}...")
                print(f"💡 建议: {ability_analysis.get('improvement', '')[:80]}...")
                print(f"📝 措施数量: {len(ability_analysis.get('suggestions', []))}")
            except Exception as e:
                print(f"❌ 解析趋势数据失败: {e}")
                # 解析失败时使用加载状态
                ability_analysis = {
                    "trend": "解析趋势数据时出现问题，请点击刷新重试",
                    "improvement": "数据解析错误，请稍后重试",
                    "suggestions": [],
                    "_status": "failed",
                    "_last_updated": trend_record.last_updated.strftime('%Y-%m-%d %H:%M:%S') if trend_record.last_updated else None
                }
        else:
            # 分析中或未开始，返回默认状态
            ability_analysis = {
                "trend": "正在为您分析编程能力发展趋势...",
                "improvement": "AI正在深度分析您的代码提交记录，请稍候...",
                "suggestions": [],
                "_status": trend_record.status,  # 添加状态信息供前端使用
                "_last_updated": trend_record.last_updated.strftime('%Y-%m-%d %H:%M:%S') if trend_record.last_updated else None
            }
            print(f"⏳ 能力趋势分析状态: {trend_record.status}")
            print(f"📈 显示默认加载状态")
        
        # 最终验证输出
        print(f"🎯 最终结果预览:")
        print(f"   趋势: {ability_analysis.get('trend', 'N/A')[:60]}...")
        print(f"   建议: {ability_analysis.get('improvement', 'N/A')[:60]}...")
        print(f"   措施: {len(ability_analysis.get('suggestions', []))} 条")
        print(f"   状态: {ability_analysis.get('_status', 'unknown')}")
        
        # 获取最近的作业
        class_name = current_user.class_name
        if class_name:
            recent_assignments = Assignment.query.filter(
                Assignment.target_classes.like(f'%{class_name}%')
            ).order_by(Assignment.created_time.desc()).limit(4).all()
        else:
            recent_assignments = []
        
        # 初始化能力得分变量
        # 学生能力得分（默认值为60，如果有评估结果则使用实际值）
        algorithm_score = 60
        style_score = 60
        functionality_score = 60
        efficiency_score = 60
        readability_score = 60
        
        # 班级平均得分（默认值）
        class_algorithm_score = 65
        class_style_score = 65
        class_functionality_score = 65
        class_efficiency_score = 65
        class_readability_score = 65
        
        # 如果有提交记录，计算学生的能力得分
        if submissions:
            # 最近一次提交记录中的AI评估结果
            recent_submission = max(submissions, key=lambda s: s.submitted_at if s.submitted_at else datetime.datetime.min)
            if recent_submission and recent_submission.ai_feedback:
                try:
                    ai_feedback = json.loads(recent_submission.ai_feedback)
                    # 检查是否为新的结构化数据格式
                    if 'algorithm_score' in ai_feedback:
                        algorithm_score = ai_feedback.get('algorithm_score', algorithm_score)
                        style_score = ai_feedback.get('style_score', style_score)
                        functionality_score = ai_feedback.get('functionality_score', functionality_score)
                        efficiency_score = ai_feedback.get('efficiency_score', efficiency_score)
                        readability_score = ai_feedback.get('readability_score', readability_score)
                        print(f"成功从结构化数据中获取学生能力分数")
                    else:
                        # 旧格式数据，使用默认值
                        print(f"使用旧格式AI反馈数据，采用默认分数")
                except (json.JSONDecodeError, TypeError) as e:
                    # 如果解析失败，可能是纯文本格式，使用默认值
                    print(f"AI反馈解析失败，使用默认分数: {e}")
                    pass
        
        # 从数据库获取班级平均能力得分
        # 获取当前用户班级的所有提交记录并计算平均值
        if current_user.class_name:
            # 根据班级名称过滤提交记录
            class_users = User.query.filter_by(class_name=current_user.class_name).all()
            user_ids = [user.student_id for user in class_users]
            class_submissions = Submission.query.filter(
                Submission.student_id.in_(user_ids),
                Submission.ai_feedback.isnot(None)
            ).all()
        else:
            # 如果用户没有班级信息，则获取所有提交记录
            class_submissions = Submission.query.filter(Submission.ai_feedback.isnot(None)).all()
        
        # 初始化计数器和累加器
        algorithm_total = 0
        style_total = 0
        functionality_total = 0
        efficiency_total = 0
        readability_total = 0
        valid_count = 0
        
        # 计算总和
        for sub in class_submissions:
            if sub.ai_feedback:
                try:
                    ai_data = json.loads(sub.ai_feedback)
                    # 检查是否为新的结构化数据格式
                    if 'algorithm_score' in ai_data:
                        algorithm_total += float(ai_data.get('algorithm_score', 0))
                        style_total += float(ai_data.get('style_score', 0))
                        functionality_total += float(ai_data.get('functionality_score', 0))
                        efficiency_total += float(ai_data.get('efficiency_score', 0))
                        readability_total += float(ai_data.get('readability_score', 0))
                        valid_count += 1
                    # 如果是旧格式数据，暂时跳过
                except (json.JSONDecodeError, TypeError, ValueError):
                    # 跳过无法解析的记录
                    pass
        
        # 计算平均值（如果没有有效记录则使用默认值）
        if valid_count > 0:
            class_algorithm_score = round(algorithm_total / valid_count, 1)
            class_style_score = round(style_total / valid_count, 1)
            class_functionality_score = round(functionality_total / valid_count, 1)
            class_efficiency_score = round(efficiency_total / valid_count, 1)
            class_readability_score = round(readability_total / valid_count, 1)
            print(f"从{valid_count}条记录中计算得出班级平均分")
        # 否则使用默认值
        
        # 获取班级平均能力得分（实际项目中应从数据库获取）
        # 这里简化处理，使用固定值
        
        # 准备能力数据的JSON格式，方便模板中使用
        skills_data = {
            'student': {
                'algorithm': float(algorithm_score),
                'style': float(style_score),
                'functionality': float(functionality_score),
                'efficiency': float(efficiency_score),
                'readability': float(readability_score)
            },
            'class_average': {
                'algorithm': float(class_algorithm_score),
                'style': float(class_style_score),
                'functionality': float(class_functionality_score),
                'efficiency': float(class_efficiency_score),
                'readability': float(class_readability_score)
            }
        }
        
        # 打印调试信息
        print("雷达图数据:")
        print(f"算法能力: {algorithm_score}")
        print(f"代码风格: {style_score}")
        print(f"功能实现: {functionality_score}")
        print(f"效率优化: {efficiency_score}")
        print(f"代码可读性: {readability_score}")
        print(f"班级平均算法能力: {class_algorithm_score}")
        print(f"班级平均代码风格: {class_style_score}")
        print(f"班级平均功能实现: {class_functionality_score}")
        print(f"班级平均效率优化: {class_efficiency_score}")
        print(f"班级平均代码可读性: {class_readability_score}")
        print(f"JSON数据: {json.dumps(skills_data)}")
        
        # 计算学生已提交的作业
        submitted_assignments = [sub.assignment_id for sub in submissions]
        
        # 准备渲染数据
        context = {
            'user': user,
            'assignments_count': assignments_count,
            'submissions_count': submissions_count,
            'average_score': average_score,
            'recent_assignments': recent_assignments,
            'ability_analysis': ability_analysis,
            'submissions': submissions,
            'submitted_assignments': submitted_assignments,
            # 雷达图数据
            'algorithm_score': float(algorithm_score),
            'style_score': float(style_score),
            'functionality_score': float(functionality_score),
            'efficiency_score': float(efficiency_score),
            'readability_score': float(readability_score),
            'class_algorithm_score': float(class_algorithm_score),
            'class_style_score': float(class_style_score),
            'class_functionality_score': float(class_functionality_score),
            'class_efficiency_score': float(class_efficiency_score),
            'class_readability_score': float(class_readability_score),
            'skills_data_json': json.dumps(skills_data)  # 添加JSON格式的技能数据
        }
        
        return render_template('student_home.html', **context)

@main.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """管理员仪表盘"""
    try:
        import json
        
        # 获取系统统计数据
        total_users = User.query.count()
        total_assignments = Assignment.query.count()
        total_submissions = Submission.query.count()
        
        # 获取平均分
        average_score_query = db.session.query(func.avg(Submission.score)).scalar()
        average_score = average_score_query if average_score_query else 0
        
        # 获取最近活动（从数据库中获取真实数据）
        recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
        
        # 将日志转换为活动格式，添加相对时间表示
        recent_activities = []
        for log in recent_logs:
            # 计算时间差
            time_diff = datetime.datetime.now() - log.created_at
            if time_diff.days > 0:
                time_str = f"{time_diff.days}天前"
            elif time_diff.seconds >= 3600:
                hours = time_diff.seconds // 3600
                time_str = f"{hours}小时前"
            elif time_diff.seconds >= 60:
                minutes = time_diff.seconds // 60
                time_str = f"{minutes}分钟前"
            else:
                time_str = "刚刚"
            
            # 创建活动对象
            activity = {
                'icon': log.icon,
                'message': log.content,
                'time': time_str
            }
            recent_activities.append(activity)
        
        # 为图表准备数据
        chart_data = {
            'assignments': {'labels': [], 'counts': []},
            'scores': {'labels': [], 'counts': [], 'colors': []},
            'activity': {'labels': [], 'counts': []}
        }
        
        print("开始准备图表数据...")
        use_demo_data = False
        
        # 1. 作业提交数量统计
        try:
            print("查询作业提交数据...")
            assignments_data = db.session.query(
                Assignment.title,
                func.count(Submission.id).label('submit_count')
            ).outerjoin(
                Submission, Assignment.id == Submission.assignment_id
            ).group_by(
                Assignment.id
            ).order_by(
                func.count(Submission.id).desc()
            ).limit(10).all()
            
            if assignments_data:
                print(f"获取到 {len(assignments_data)} 条作业数据")
                chart_data['assignments']['labels'] = [a.title for a in assignments_data]
                chart_data['assignments']['counts'] = [int(a.submit_count) for a in assignments_data]  # 确保是整数
            else:
                print("没有作业提交数据")
                use_demo_data = True
        except Exception as e:
            print(f"获取作业提交数据时出错: {str(e)}")
            use_demo_data = True
        
        # 2. 得分分布统计
        try:
            print("查询得分分布数据...")
            score_distribution = db.session.query(
                Submission.score,
                func.count(Submission.id).label('count')
            ).filter(Submission.score.isnot(None)).group_by(
                Submission.score
            ).order_by(
                Submission.score
            ).all()
            
            if score_distribution:
                print(f"获取到 {len(score_distribution)} 条得分分布数据")
                chart_data['scores']['labels'] = [f"{s.score}分" for s in score_distribution]
                chart_data['scores']['counts'] = [int(s.count) for s in score_distribution]  # 确保是整数
                
                # 生成足够的颜色
                colors = [
                    'rgba(255, 99, 132, 0.8)',   # 红色
                    'rgba(255, 159, 64, 0.8)',   # 橙色
                    'rgba(255, 205, 86, 0.8)',   # 黄色
                    'rgba(75, 192, 192, 0.8)',   # 绿色
                    'rgba(54, 162, 235, 0.8)'    # 蓝色
                ]
                # 确保颜色数量足够
                while len(colors) < len(chart_data['scores']['labels']):
                    colors.extend(colors)
                
                chart_data['scores']['colors'] = colors[:len(chart_data['scores']['labels'])]
            else:
                print("没有得分分布数据")
                use_demo_data = True
        except Exception as e:
            print(f"获取得分分布数据时出错: {str(e)}")
            use_demo_data = True
        
        # 3. 用户活跃度统计（每日提交数量）
        try:
            print("查询用户活跃度数据...")
            today = datetime.datetime.now().date()
            thirty_days_ago = today - datetime.timedelta(days=30)
            
            daily_submissions = db.session.query(
                func.date(Submission.submitted_at).label('day'),
                func.count(Submission.id).label('count')
            ).filter(
                Submission.submitted_at >= thirty_days_ago
            ).group_by(
                func.date(Submission.submitted_at)
            ).order_by(
                func.date(Submission.submitted_at)
            ).all()
            
            print(f"获取到 {len(daily_submissions)} 天的活跃度数据")
            
            # 创建包含30天的完整日期列表
            date_range = [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, 0, -1)]
            daily_counts = [0] * 30  # 初始化为全0
            
            # 填充实际有数据的日期
            submission_dict = {}
            for day in daily_submissions:
                day_str = day.day.strftime('%Y-%m-%d') if hasattr(day.day, 'strftime') else str(day.day)
                submission_dict[day_str] = int(day.count)
            
            for i, date in enumerate(date_range):
                if date in submission_dict:
                    daily_counts[i] = submission_dict[date]
            
            chart_data['activity']['labels'] = date_range
            chart_data['activity']['counts'] = daily_counts
            
            # 如果所有天的提交数都是0，使用演示数据
            if all(count == 0 for count in daily_counts):
                print("所有日期的提交数量均为0")
                use_demo_data = True
        except Exception as e:
            print(f"获取活跃度数据时出错: {str(e)}")
            use_demo_data = True
        
        # 转换为JSON字符串，确保数据格式正确
        try:
            chart_data_json = json.dumps(chart_data, ensure_ascii=False)
            print(f"生成的图表数据长度: {len(chart_data_json)}")
        except Exception as e:
            print(f"序列化图表数据时出错: {str(e)}")
            chart_data_json = "{}"
            use_demo_data = True
        
        # 检查是否需要使用演示数据
        # 如果图表数据为空或各个图表数据都为空，或者明确设置了使用演示数据，则使用演示数据
        if (use_demo_data or len(chart_data_json) < 50 or
            (not chart_data['assignments']['labels'] and 
             not chart_data['scores']['labels'] and
             not chart_data['activity']['counts'])):
            
            print("使用演示数据，原因：图表数据有问题或为空")
            # 添加演示数据，确保前端可以看到图表
            demo_data = {
                'assignments': {
                    'labels': ['演示作业1', '演示作业2', '演示作业3', '演示作业4', '演示作业5'],
                    'counts': [15, 12, 8, 6, 4]
                },
                'scores': {
                    'labels': ['5分', '4分', '3分', '2分', '1分'],
                    'counts': [18, 14, 8, 5, 2],
                    'colors': [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(255, 205, 86, 0.8)',
                        'rgba(255, 159, 64, 0.8)',
                        'rgba(255, 99, 132, 0.8)'
                    ]
                },
                'activity': {
                    'labels': [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, 0, -1)],
                    'counts': [0, 1, 2, 0, 3, 5, 2, 0, 0, 1, 3, 2, 4, 6, 2, 1, 0, 0, 2, 1, 3, 4, 2, 2, 1, 0, 1, 2, 3, 5]
                }
            }
            
            chart_data_json = json.dumps(demo_data, ensure_ascii=False)
            print(f"演示数据JSON长度: {len(chart_data_json)}")
            
            # 提示用户正在使用演示数据
            flash("图表数据为演示数据：数据库中可视化数据不足。请添加一些作业和提交以查看实际统计数据。", "info")
        
        # 最后的安全检查
        if len(chart_data_json) < 10:
            print("JSON数据异常短，使用空对象")
            chart_data_json = "{}"
        
        # 打印最终输出的JSON前100个字符
        print(f"最终输出JSON(前100字符): {chart_data_json[:100]}...")
        
        return render_template('admin_dashboard.html', 
                              total_users=total_users,
                              total_assignments=total_assignments,
                              total_submissions=total_submissions,
                              average_score=average_score,
                              recent_activities=recent_activities,
                              chart_data=chart_data_json)
    
    except Exception as e:
        import traceback
        error_msg = f"加载管理员仪表盘时出错: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        flash(error_msg, 'danger')
        
        # 返回一个带有演示数据的简化版仪表盘
        print("由于错误，使用备用演示数据")
        today = datetime.datetime.now().date()
        
        demo_data = {
            'assignments': {
                'labels': ['备用演示1', '备用演示2', '备用演示3', '备用演示4', '备用演示5'],
                'counts': [10, 8, 6, 4, 2]
            },
            'scores': {
                'labels': ['5分', '4分', '3分', '2分', '1分'],
                'counts': [10, 8, 6, 4, 2],
                'colors': [
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(255, 205, 86, 0.8)',
                    'rgba(255, 159, 64, 0.8)',
                    'rgba(255, 99, 132, 0.8)'
                ]
            },
            'activity': {
                'labels': [(today - datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30, 0, -1)],
                'counts': [1, 0, 2, 0, 1, 3, 1, 0, 0, 1, 2, 1, 3, 2, 1, 1, 0, 0, 1, 1, 2, 3, 1, 1, 0, 0, 1, 1, 2, 3]
            }
        }
        
        return render_template('admin_dashboard.html', 
                             total_users=User.query.count(),
                             total_assignments=Assignment.query.count(),
                             total_submissions=Submission.query.count(),
                             average_score=0,
                             recent_activities=[],
                             chart_data=json.dumps(demo_data, ensure_ascii=False))

@main.route('/teacher_dashboard')
@login_required
def teacher_dashboard():
    """教师仪表盘"""
    if not current_user.is_teacher:
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('main.home'))

    teacher = current_user
    managed_classes = teacher.managed_classes.all()
    class_ids = [c.id for c in managed_classes]
    
    student_count = User.query.filter(User.class_id.in_(class_ids)).count() if class_ids else 0
    
    # 获取这些班级学生的ID
    student_ids = db.session.query(User.student_id).filter(User.class_id.in_(class_ids)).scalar_subquery()
    
    # 获取最近的提交
    recent_submissions = Submission.query.filter(
        Submission.student_id.in_(student_ids)
    ).order_by(Submission.submitted_at.desc()).limit(10).all() if class_ids else []

    # 统计数据
    total_submissions = Submission.query.filter(Submission.student_id.in_(student_ids)).count() if class_ids else 0

    # 准备图表数据: 1) 各班级学生人数 2) 各班级平均分
    class_names = []
    class_sizes = []
    class_avg_scores = []
    
    for c in managed_classes:
        class_names.append(c.name)
        class_sizes.append(c.student_count)
        # 获取班级平均分
        stats = c.get_statistics()
        class_avg_scores.append(round(stats.get('avg_score', 0), 1))
        
    chart_data = {
        'labels': class_names,
        'sizes': class_sizes,
        'scores': class_avg_scores
    }

    return render_template('teacher_home.html',
                           teacher=teacher,
                           managed_classes=managed_classes,
                           student_count=student_count,
                           total_submissions=total_submissions,
                           recent_submissions=recent_submissions,
                           chart_data=chart_data)

@main.route('/profile')
@login_required
def profile():
    """个人信息页面 - 根据用户类型显示不同的模板"""
    import datetime
    from datetime import datetime as dt, timedelta
    
    user = current_user
    
    # 根据用户类型分发到不同的个人资料页
    if user.is_admin:
        # 获取系统统计数据
        total_students = User.query.filter_by(usertype='学生').count()
        total_assignments = Assignment.query.count()
        total_submissions = Submission.query.count()
        
        # 获取今天的统计数据
        today = dt.now().date()
        today_start = dt.combine(today, datetime.time.min)
        today_end = dt.combine(today, datetime.time.max)
        
        today_submissions = Submission.query.filter(
            Submission.submitted_at.between(today_start, today_end)
        ).count()
        
        # 获取今日登录次数（通过系统日志）
        today_logins = SystemLog.query.filter(
            SystemLog.created_at.between(today_start, today_end),
            SystemLog.log_type == '用户登录'
        ).count()
        
        # 获取平均分数
        average_score_query = db.session.query(func.avg(Submission.score)).scalar()
        average_score = average_score_query if average_score_query else 0
        
        # 获取管理员邮箱
        admin_email = SystemConfig.get_value('admin_email', 'daiyupeng5@gmail.com')
        
        # 获取最近活动
        recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(5).all()
        recent_activities = []
        
        for log in recent_logs:
            # 计算相对时间
            time_diff = dt.now() - log.created_at
            if time_diff.days > 0:
                time_str = f"{time_diff.days}天前"
            elif time_diff.seconds >= 3600:
                hours = time_diff.seconds // 3600
                time_str = f"{hours}小时前"
            elif time_diff.seconds >= 60:
                minutes = time_diff.seconds // 60
                time_str = f"{minutes}分钟前"
            else:
                time_str = "刚刚"
                
            activity = {
                'icon': log.icon,
                'message': log.content,
                'time': time_str
            }
            recent_activities.append(activity)
        
        # 为图表准备数据 - 近7天的登录和提交数据
        chart_dates = []
        login_counts = []
        submission_counts = []
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime('%m-%d')
            chart_dates.append(date_str)
            
            day_start = dt.combine(date, datetime.time.min)
            day_end = dt.combine(date, datetime.time.max)
            
            # 当天登录数
            login_count = SystemLog.query.filter(
                SystemLog.created_at.between(day_start, day_end),
                SystemLog.log_type == '用户登录'
            ).count()
            login_counts.append(login_count)
            
            # 当天提交数
            submission_count = Submission.query.filter(
                Submission.submitted_at.between(day_start, day_end)
            ).count()
            submission_counts.append(submission_count)
        
        import json
        
        return render_template(
            'admin_profile.html',
            user=user,
            total_students=total_students,
            total_assignments=total_assignments,
            total_submissions=total_submissions,
            today_submissions=today_submissions,
            today_logins=today_logins,
            average_score=average_score,
            admin_email=admin_email,
            recent_activities=recent_activities,
            chart_dates=json.dumps(chart_dates),
            login_counts=json.dumps(login_counts),
            submission_counts=json.dumps(submission_counts)
        )
    elif user.is_teacher:
        managed_classes = user.managed_classes.all()
        return render_template('teacher_profile.html', user=user, managed_classes=managed_classes)
    else:
        # 学生用户使用原有模板
        return render_template('profile.html', user=user)

@main.route('/user_profile/<string:user_username>')
@login_required
def user_profile(user_username):
    """查看指定用户的信息"""
    user = User.query.filter_by(username=user_username).first_or_404()
    return render_template('sprofile.html', user=user)

@main.route('/debug_session')
def debug_session():
    """调试会话状态"""
    if 'student_id' in session:
        return jsonify({
            'status': 'logged_in',
            'student_id': session['student_id'],
            'username': session.get('username', ''),
            'usertype': session.get('usertype', ''),
            'login': session.get('login', False)
        })
    else:
        return jsonify({
            'status': 'not_logged_in',
            'session_data': {k: v for k, v in session.items()}
        })

@main.route('/about')
def about():
    """关于系统页面"""
    return render_template('about.html')

@main.route('/help')
def help():
    """使用帮助页面"""
    return render_template('help.html')

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    """联系我们页面"""
    if request.method == 'POST':
        try:
            # 获取表单数据
            name = request.form.get('name')
            email = request.form.get('email')
            subject = request.form.get('subject')
            message = request.form.get('message')
            
            # 验证必要的字段
            if not all([name, email, subject, message]):
                flash('请填写所有必填字段', 'warning')
                return render_template('contact.html')
                
            # 记录反馈信息到系统日志
            log_entry = SystemLog(
                user_id=session.get('student_id', '游客'),
                action='提交反馈',
                details=f'主题: {subject}, 联系人: {name}, 邮箱: {email}'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            # 在实际应用中，还可以发送电子邮件通知管理员
            # send_feedback_email(name, email, subject, message)
            
            flash('感谢您的反馈！我们会尽快回复您。', 'success')
            return redirect(url_for('main.contact'))
            
        except Exception as e:
            flash(f'提交失败，请稍后再试。错误: {str(e)}', 'danger')
            db.session.rollback()
            
    return render_template('contact.html')

@main.route('/trend_monitor')
@login_required
@admin_required
def trend_monitor():
    """能力趋势分析监控页面"""
    return render_template('admin_trend_monitor.html')

@main.route('/export_data')
@login_required
@admin_required
def export_data():
    """显示导出数据选项页面"""
    # 获取所有班级列表用于筛选
    classes = db.session.query(User.class_name).filter(
        User.class_name.isnot(None),
        User.class_name != ''
    ).distinct().order_by(User.class_name).all()
    class_list = [c[0] for c in classes]
    
    return render_template('export_data.html', class_list=class_list)

@main.route('/download_data/<export_type>')
@login_required
@admin_required
def download_data(export_type):
    """导出数据为CSV格式
    
    参数:
        export_type: 导出数据类型，可选 'users', 'assignments', 'submissions', 'all'
    """
    # 获取筛选参数
    class_name = request.args.get('class_name', '').strip()
    student_id = request.args.get('student_id', '').strip()
    
    # 记录导出操作
    filter_desc = ""
    if class_name:
        filter_desc += f" (班级: {class_name})"
    if student_id:
        filter_desc += f" (学号: {student_id})"
    
    SystemLog.add_log(
        log_type="数据导出",
        user_id=session.get('student_id'),
        content=f"管理员 {session.get('username')} ({session.get('full_name')}) 导出了{export_type}数据{filter_desc}",
        icon="bi bi-file-earmark-text"
    )
    
    try:
        if export_type == 'users':
            # 导出用户数据
            query = User.query
            
            # 应用筛选条件
            if class_name:
                query = query.filter(User.class_name == class_name)
            if student_id:
                query = query.filter(User.student_id == student_id)
            
            data = query.all()
            
            # 创建内存文件对象
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(['学号', '用户名', '姓名', '班级', '用户类型', '提交次数', '平均分'])
            
            # 写入数据行
            for user in data:
                writer.writerow([
                    user.student_id,
                    user.username,
                    user.full_name,
                    user.class_name or '未设置',
                    user.usertype,
                    user.submit_count,
                    user.user_ascore
                ])
            
            # 设置响应
            return make_csv_response(output, '用户数据')
            
        elif export_type == 'assignments':
            # 导出作业数据
            data = Assignment.query.all()
            
            # 创建内存文件对象
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(['作业ID', '标题', '描述', '创建时间', '提交次数', '平均分'])
            
            # 写入数据行
            for assignment in data:
                writer.writerow([
                    assignment.id,
                    assignment.title,
                    assignment.description[:50] + '...' if len(assignment.description) > 50 else assignment.description,
                    assignment.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                    assignment.count,
                    assignment.average_score
                ])
            
            # 设置响应
            return make_csv_response(output, '作业数据')
            
        elif export_type == 'submissions':
            # 导出提交记录数据
            query = Submission.query
            
            # 应用筛选条件
            if class_name:
                # 通过学生的班级筛选提交记录
                student_ids = db.session.query(User.student_id).filter(
                    User.class_name == class_name
                ).all()
                student_ids = [s[0] for s in student_ids]
                query = query.filter(Submission.student_id.in_(student_ids))
            if student_id:
                query = query.filter(Submission.student_id == student_id)
            
            data = query.all()
            
            # 创建内存文件对象
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(['提交ID', '作业ID', '学号', '提交时间', '代码', '评分', '反馈'])
            
            # 写入数据行
            for submission in data:
                writer.writerow([
                    submission.id,
                    submission.assignment_id,
                    submission.student_id,
                    submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                    submission.code[:50] + '...' if len(submission.code) > 50 else submission.code,
                    submission.score,
                    submission.feedback[:50] + '...' if submission.feedback and len(submission.feedback) > 50 else submission.feedback or ''
                ])
            
            # 设置响应
            return make_csv_response(output, '提交记录数据')
            
        elif export_type == 'all':
            # 导出所有数据（ZIP压缩包）
            from zipfile import ZipFile
            from io import BytesIO
            
            # 创建内存ZIP文件
            memory_file = BytesIO()
            with ZipFile(memory_file, 'w') as zf:
                # 添加用户数据
                users_query = User.query
                if class_name:
                    users_query = users_query.filter(User.class_name == class_name)
                if student_id:
                    users_query = users_query.filter(User.student_id == student_id)
                
                users_data = io.StringIO()
                users_writer = csv.writer(users_data)
                users_writer.writerow(['学号', '用户名', '姓名', '班级', '用户类型', '提交次数', '平均分'])
                for user in users_query.all():
                    users_writer.writerow([
                        user.student_id,
                        user.username,
                        user.full_name,
                        user.class_name or '未设置',
                        user.usertype,
                        user.submit_count,
                        user.user_ascore
                    ])
                zf.writestr('users.csv', users_data.getvalue())
                
                # 添加作业数据（作业不筛选）
                assignments_data = io.StringIO()
                assignments_writer = csv.writer(assignments_data)
                assignments_writer.writerow(['作业ID', '标题', '描述', '创建时间', '提交次数', '平均分'])
                for assignment in Assignment.query.all():
                    assignments_writer.writerow([
                        assignment.id,
                        assignment.title,
                        assignment.description[:50] + '...' if len(assignment.description) > 50 else assignment.description,
                        assignment.created_time.strftime('%Y-%m-%d %H:%M:%S'),
                        assignment.count,
                        assignment.average_score
                    ])
                zf.writestr('assignments.csv', assignments_data.getvalue())
                
                # 添加提交记录数据
                submissions_query = Submission.query
                if class_name:
                    student_ids = db.session.query(User.student_id).filter(
                        User.class_name == class_name
                    ).all()
                    student_ids = [s[0] for s in student_ids]
                    submissions_query = submissions_query.filter(Submission.student_id.in_(student_ids))
                if student_id:
                    submissions_query = submissions_query.filter(Submission.student_id == student_id)
                
                submissions_data = io.StringIO()
                submissions_writer = csv.writer(submissions_data)
                submissions_writer.writerow(['提交ID', '作业ID', '学号', '提交时间', '代码', '评分', '反馈'])
                for submission in submissions_query.all():
                    submissions_writer.writerow([
                        submission.id,
                        submission.assignment_id,
                        submission.student_id,
                        submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                        submission.code[:50] + '...' if len(submission.code) > 50 else submission.code,
                        submission.score,
                        submission.feedback[:50] + '...' if submission.feedback and len(submission.feedback) > 50 else submission.feedback or ''
                    ])
                zf.writestr('submissions.csv', submissions_data.getvalue())
                
                # 添加系统日志数据
                logs_data = io.StringIO()
                logs_writer = csv.writer(logs_data)
                logs_writer.writerow(['日志ID', '类型', '用户ID', '内容', '创建时间'])
                for log in SystemLog.query.all():
                    logs_writer.writerow([
                        log.id,
                        log.log_type,
                        log.user_id,
                        log.content,
                        log.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    ])
                zf.writestr('system_logs.csv', logs_data.getvalue())
                
            # 设置响应
            memory_file.seek(0)
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            response = Response(
                memory_file.getvalue(),
                mimetype='application/zip',
                headers={'Content-Disposition': f'attachment;filename=all_data_{timestamp}.zip'}
            )
            return response
        
        else:
            flash('无效的导出类型', 'danger')
            return redirect(url_for('main.export_data'))
            
    except Exception as e:
        flash(f'导出数据时出错: {str(e)}', 'danger')
        return redirect(url_for('main.export_data'))

def make_csv_response(string_io, filename_prefix):
    """创建CSV响应"""
    output = string_io.getvalue()
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    response = Response(output, mimetype='text/csv')
    
    # 使用英文文件名前缀避免编码问题
    english_prefix = {
        '用户数据': 'user_data',
        '作业数据': 'assignment_data',
        '提交记录数据': 'submission_data',
        '系统日志数据': 'system_log_data'
    }.get(filename_prefix, 'data')
    
    response.headers['Content-Disposition'] = f'attachment; filename={english_prefix}_{timestamp}.csv'
    return response

@main.route('/system_settings', methods=['GET', 'POST'])
@login_required
@admin_required
def system_settings():
    """系统设置页面"""
    # 按照需求，暂时禁用系统设置功能
    flash('系统设置功能已暂时禁用', 'warning')
    return redirect(url_for('main.admin_dashboard'))
    
    # 以下代码保留但不再执行
    """
    from models import SystemConfig
    
    if request.method == 'POST':
        try:
            # 从表单获取设置并保存到数据库
            SystemConfig.set_value('site_name', request.form.get('site_name'), '网站名称', 'string')
            SystemConfig.set_value('site_description', request.form.get('site_description'), '网站描述', 'string')
            SystemConfig.set_value('enable_registration', 'enable_registration' in request.form, '是否允许新用户注册', 'bool')
            SystemConfig.set_value('login_message', request.form.get('login_message'), '登录页面欢迎消息', 'string')
            SystemConfig.set_value('default_user_score', request.form.get('default_user_score', '60'), '新用户默认初始分数', 'int')
            SystemConfig.set_value('submissions_per_day', request.form.get('submissions_per_day', '10'), '每日最大提交次数', 'int')
            SystemConfig.set_value('admin_email', request.form.get('admin_email'), '管理员联系邮箱', 'string')
            
            # 记录设置更改
            SystemLog.add_log(
                log_type="系统设置",
                user_id=session.get('student_id'),
                content=f"管理员 {session.get('username')} ({session.get('full_name')}) 更新了系统设置",
                icon="bi bi-gear"
            )
            
            flash('系统设置已更新并保存到数据库', 'success')
            return redirect(url_for('main.system_settings'))
            
        except Exception as e:
            flash(f'更新系统设置时出错: {str(e)}', 'danger')
    
    # 从数据库获取当前设置
    settings = {
        'site_name': SystemConfig.get_value('site_name', 'CodeSense 酷森思'),
        'site_description': SystemConfig.get_value('site_description', '一个用于评估学生编程能力的在线平台'),
        'enable_registration': SystemConfig.get_value('enable_registration', True),
        'login_message': SystemConfig.get_value('login_message', '欢迎登录 CodeSense 酷森思'),
        'default_user_score': SystemConfig.get_value('default_user_score', 60),
        'submissions_per_day': SystemConfig.get_value('submissions_per_day', 10),
        'admin_email': SystemConfig.get_value('admin_email', 'daiyupeng5@gmail.com'),
        'system_version': SystemConfig.get_value('system_version', '1.0.0')
    }
    
    return render_template('system_settings.html', settings=settings)
    """ 