"""
表单处理模块
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, HiddenField, RadioField, IntegerField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, EqualTo, Email, ValidationError, Optional, NumberRange


class LoginForm(FlaskForm):
    """登录表单"""
    username = StringField('用户名', validators=[DataRequired(message='用户名不能为空'), Length(1, 50)])
    password = PasswordField('密码', validators=[DataRequired(message='密码不能为空')])
    submit = SubmitField('登录')


class RegistrationForm(FlaskForm):
    """注册表单"""
    username = StringField('用户名', validators=[DataRequired(message='用户名不能为空'), Length(1, 50)])
    student_id = StringField('学号', validators=[DataRequired(message='学号不能为空'), Length(1, 20)])
    password = PasswordField('密码', validators=[DataRequired(message='密码不能为空'), Length(6, 20)])
    confirm_password = PasswordField('确认密码', validators=[
        DataRequired(message='确认密码不能为空'), 
        EqualTo('password', message='两次输入的密码不匹配')
    ])
    full_name = StringField('姓名', validators=[DataRequired(message='姓名不能为空'), Length(1, 50)])
    class_name = StringField('班级', validators=[Optional(), Length(0, 50)])
    usertype = RadioField('用户类型', choices=[('学生', '学生'), ('管理员', '管理员')], default='学生')
    admin_password = PasswordField('管理员密码', validators=[Optional()])
    submit = SubmitField('注册')


class AssignmentForm(FlaskForm):
    """作业表单"""
    assignment_id = IntegerField('作业ID', validators=[DataRequired(message='作业ID不能为空'), 
                                               NumberRange(min=1, message='作业ID必须为正整数')])
    title = StringField('标题', validators=[DataRequired(message='标题不能为空'), Length(1, 100)])
    description = TextAreaField('描述', validators=[DataRequired(message='描述不能为空')])
    due_date = DateTimeLocalField('截止日期', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    submit = SubmitField('提交')


class SubmissionForm(FlaskForm):
    """代码提交表单"""
    code = TextAreaField('代码', validators=[DataRequired(message='代码不能为空')])
    language = HiddenField('编程语言', default='cpp')
    submit = SubmitField('提交')


class EditProfileForm(FlaskForm):
    """编辑资料表单"""
    username = StringField('用户名', validators=[DataRequired(message='用户名不能为空'), Length(1, 50)])
    full_name = StringField('姓名', validators=[DataRequired(message='姓名不能为空'), Length(1, 50)])
    class_name = SelectField('班级', validators=[Optional()])
    submit = SubmitField('保存修改') 