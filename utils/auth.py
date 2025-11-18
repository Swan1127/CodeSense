"""
身份验证和认证功能模块
"""
import os
from functools import wraps
from flask import session, flash, redirect, url_for, current_app, request
from flask_login import current_user, login_required as flask_login_required
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password):
    """使用werkzeug的安全哈希函数对密码进行哈希处理"""
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """验证密码是否匹配"""
    return check_password_hash(password_hash, password)


# 注意：不再需要login_required装饰器，直接使用flask_login的login_required
# 但为了向后兼容，我们保留一个同名的函数
login_required = flask_login_required


def redirect_if_logged_in(f):
    """如果用户已登录，则重定向到主页的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 使用Flask-Login的current_user检查是否已登录
        if current_user.is_authenticated:
            flash('您已登录')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """检查用户是否是管理员的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 首先确保用户已登录
        if not current_user.is_authenticated:
            flash('请先登录')
            return redirect(url_for('auth.login'))
        
        # 检查是否是管理员
        if not current_user.is_admin:
            flash('需要管理员权限')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function


def admin_password_required(f):
    """检查管理员密码是否正确的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_password = request.form.get('admin_password')
        if not admin_password or not validate_admin_password(admin_password):
            flash('管理员密码错误')
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)
    return decorated_function


def validate_admin_password(password):


    """验证管理员密码是否正确"""


    admin_password = os.environ.get('ADMIN_PASSWORD') or 'admin123'


    return password == admin_password





def admin_or_teacher_required(f):


    """检查用户是否是管理员或教师的装饰器"""


    @wraps(f)


    def decorated_function(*args, **kwargs):


        if not current_user.is_authenticated:


            flash('请先登录', 'warning')


            return redirect(url_for('auth.login', next=request.url))


        


        if not (current_user.is_admin or current_user.is_teacher):


            flash('您没有权限访问此页面', 'danger')


            return redirect(url_for('main.home'))


        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """检查用户是否是教师的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_teacher:
            flash('您没有权限访问此页面，需要教师身份', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function


 