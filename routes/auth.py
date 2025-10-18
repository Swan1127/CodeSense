"""
身份验证相关路由
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import logging
import traceback
from flask_login import login_user, logout_user, current_user  # 添加Flask-Login导入
from models import db, User, SystemLog, SystemConfig
from forms import LoginForm, RegistrationForm
from utils.auth import validate_admin_password, redirect_if_logged_in, admin_password_required

auth = Blueprint('auth', __name__)


@auth.route('/')
def index():
    """首页，重定向到登录页面"""
    # 如果用户已登录，直接跳转到首页
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    session.clear()  # 清除会话
    return redirect(url_for('auth.login'))


@auth.route('/login', methods=['GET', 'POST'])
@redirect_if_logged_in
def login():
    """登录页面"""
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        # 记录登录尝试
        current_app.logger.info(f"登录尝试 - 用户名: {username}, IP: {request.remote_addr}")
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.verify_password(password):
            # 使用Flask-Login进行登录
            login_user(user)
            
            # 保存信息到session以便其他地方使用
            session['student_id'] = user.student_id
            session['username'] = user.username
            session['full_name'] = user.full_name
            session['usertype'] = user.usertype
            session['login'] = True
            
            # 记录登录日志
            SystemLog.add_log(
                log_type='用户登录',
                content=f'用户 {user.username} ({user.full_name}) 登录了系统',
                user_id=user.student_id
            )
            
            # Flask应用日志记录成功登录
            current_app.logger.info(f"登录成功 - 用户: {user.username} ({user.full_name}), 类型: {user.usertype}, IP: {request.remote_addr}")
            
            # 登录成功后，触发异步能力趋势分析任务
            try:
                from utils.async_tasks import add_ability_trend_task
                task_id = add_ability_trend_task(user.student_id)
                current_app.logger.info(f"用户 {user.student_id} 登录成功，已触发能力趋势分析任务: {task_id}")
            except Exception as e:
                current_app.logger.warning(f"触发能力趋势分析任务失败: {e}")
            
            flash('登录成功！', 'success')
            # 立即重定向到主页（不等待分析完成）
            return redirect(url_for('main.home'))
        else:
            # 记录失败的登录尝试
            current_app.logger.warning(f"登录失败 - 用户名: {username}, IP: {request.remote_addr}, 原因: {'用户不存在' if not user else '密码错误'}")
            flash('用户名或密码错误，请重试！', 'danger')
    
    # 从系统设置获取登录消息和网站名称
    login_message = SystemConfig.get_value('login_message', '欢迎登录学生程序设计能力评价系统')
    site_name = SystemConfig.get_value('site_name', '学生程序设计能力评价系统')
    
    return render_template('login.html', form=form, login_message=login_message, site_name=site_name)


@auth.route('/register', methods=['GET', 'POST'])
@redirect_if_logged_in
def register():
    """注册页面"""
    # 检查是否允许注册
    enable_registration = SystemConfig.get_value('enable_registration', True)
    if not enable_registration:
        flash('系统当前不允许新用户注册，请联系管理员', 'warning')
        return redirect(url_for('auth.login'))
    
    form = RegistrationForm()
    
    if form.validate_on_submit():
        username = form.username.data
        student_id = form.student_id.data
        usertype = form.usertype.data
        
        # 记录注册尝试
        current_app.logger.info(f"注册尝试 - 用户名: {username}, 学号: {student_id}, 类型: {usertype}, IP: {request.remote_addr}")
        
        # 检查用户名和学号是否已存在
        existing_user = User.query.filter(
            (User.username == username) | 
            (User.student_id == student_id)
        ).first()
        
        if existing_user:
            current_app.logger.warning(f"注册失败 - 用户名或学号已存在: {username}/{student_id}, IP: {request.remote_addr}")
            flash('用户名或学号已存在，请使用其他的用户名和学号', 'danger')
            return render_template('register.html', form=form)
        
        # 管理员身份验证
        if usertype == '管理员':
            if form.admin_password.data != 'admin123':  # 修改为您的管理员密码
                current_app.logger.warning(f"管理员注册失败 - 密码错误: {username}, IP: {request.remote_addr}")
                flash('管理员密码错误', 'danger')
                return render_template('register.html', form=form)
        
        try:
            # 创建新用户
            user = User(
                username=username,
                student_id=student_id,
                usertype=usertype,
                full_name=form.full_name.data,
                class_name=form.class_name.data,
                submit_count=0,
                user_ascore=0.0,
                user_tscore=0
            )
            user.password = form.password.data  # 密码会在模型中自动加密
            
            # 保存到数据库
            db.session.add(user)
            db.session.commit()
            
            # 记录注册日志
            SystemLog.add_log(
                log_type='用户注册',
                content=f'新用户 {user.username} ({user.full_name}) 注册成功，用户类型：{user.usertype}',
                user_id=user.student_id
            )
            
            # Flask应用日志记录成功注册
            current_app.logger.info(f"注册成功 - 用户: {user.username} ({user.full_name}), 学号: {user.student_id}, 类型: {user.usertype}, 班级: {user.class_name}, IP: {request.remote_addr}")
            
            flash('注册成功，请登录！', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"注册失败 - 数据库错误: {username}, 错误: {str(e)}"
            current_app.logger.error(error_msg, exc_info=True)
            flash('注册失败，请稍后重试', 'danger')
            return render_template('register.html', form=form)
        
    return render_template('register.html', form=form)


@auth.route('/logout')
def logout():
    """登出处理"""
    user_id = session.get('student_id')
    username = session.get('username')
    full_name = session.get('full_name', '未知用户')
    
    # 记录登出日志
    current_app.logger.info(f"用户登出 - 用户: {username} ({full_name}), 学号: {user_id}, IP: {request.remote_addr}")
    
    # 使用Flask-Login登出
    logout_user()
    
    # 清除所有会话数据
    session.clear()
    
    # 如果有用户ID，记录登出日志
    if user_id:
        SystemLog.add_log(
            log_type='用户登出',
            content=f'用户 {username} ({full_name}) 退出了系统',
            user_id=user_id,
            icon='bi bi-box-arrow-right'
        )
    
    flash('您已成功退出', 'info')
    return redirect(url_for('auth.login')) 