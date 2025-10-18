"""
数据库模型定义
"""
import datetime
import json  # 添加json导入
from datetime import datetime as dt
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin  # 添加UserMixin导入
from sqlalchemy import func

db = SQLAlchemy()


class Class(db.Model):
    """班级模型"""
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 班级名称
    grade = db.Column(db.String(20))  # 年级
    major = db.Column(db.String(50))  # 专业
    teacher_name = db.Column(db.String(50))  # 班主任姓名
    student_count = db.Column(db.Integer, default=0)  # 学生数量
    avg_score = db.Column(db.Float, default=0.0)  # 班级平均分
    total_submissions = db.Column(db.Integer, default=0)  # 班级总提交数
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.utcnow, onupdate=dt.utcnow)
    
    # 与学生的一对多关系
    students = db.relationship('User', backref='class_info', lazy='dynamic',
                             foreign_keys='User.class_id')
    
    def get_statistics(self):
        """获取班级统计信息"""
        students = self.students.filter_by(usertype='学生').all()
        
        if not students:
            return {
                'student_count': 0,
                'avg_score': 0.0,
                'total_submissions': 0,
                'active_students': 0,
                'assignments_completed': 0
            }
        
        # 计算统计数据
        total_submissions = sum(s.submit_count for s in students)
        avg_score = sum(s.user_ascore for s in students) / len(students) if students else 0.0
        active_students = len([s for s in students if s.submit_count > 0])
        
        # 计算完成作业数 - 使用当前模块避免循环导入
        assignments_completed = db.session.query(Submission.assignment_id).join(User)\
                                .filter(User.class_name == self.name)\
                                .distinct().count()
        
        return {
            'student_count': len(students),
            'avg_score': round(avg_score, 2),
            'total_submissions': total_submissions,
            'active_students': active_students,
            'assignments_completed': assignments_completed
        }
    
    def get_top_students(self, limit=5):
        """获取班级前N名学生"""
        return self.students.filter_by(usertype='学生')\
                           .order_by(User.user_ascore.desc())\
                           .limit(limit).all()
    
    def get_assignment_progress(self):
        """获取班级作业完成进度"""
        # 获取所有作业 - 使用当前模块避免循环导入
        assignments = Assignment.query.all()
        progress = []
        
        for assignment in assignments:
            # 计算该作业的班级完成情况
            completed = db.session.query(Submission).join(User)\
                       .filter(User.class_name == self.name,
                              Submission.assignment_id == assignment.id)\
                       .count()
            
            total = self.students.filter_by(usertype='学生').count()
            progress.append({
                'assignment': assignment,
                'completed': completed,
                'total': total,
                'progress_rate': round(completed / total * 100, 1) if total > 0 else 0
            })
        
        return progress
    
    @staticmethod
    def sync_from_users():
        """从用户数据同步班级信息"""
        # 获取所有不同的班级名称
        class_names = db.session.query(User.class_name)\
                     .filter(User.class_name.isnot(None))\
                     .distinct().all()
        
        for (class_name,) in class_names:
            if not class_name:
                continue
                
            # 检查班级是否已存在
            existing_class = Class.query.filter_by(name=class_name).first()
            if not existing_class:
                # 创建新班级
                new_class = Class(
                    name=class_name,
                    grade='2024',  # 默认年级
                    major='计算机相关专业'  # 默认专业
                )
                db.session.add(new_class)
        
        db.session.commit()
        
        # 更新班级统计信息
        classes = Class.query.all()
        for cls in classes:
            stats = cls.get_statistics()
            cls.student_count = stats['student_count']
            cls.avg_score = stats['avg_score']
            cls.total_submissions = stats['total_submissions']
        
        db.session.commit()
        return len(classes)


class User(db.Model, UserMixin):  # 添加UserMixin继承
    """用户模型"""
    __tablename__ = 'users'
    student_id = db.Column(db.String(20), unique=True, nullable=False, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    usertype = db.Column(db.Enum('学生', '管理员'), nullable=False)
    class_name = db.Column(db.String(50))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)  # 新增班级外键
    full_name = db.Column(db.String(50))
    submit_count = db.Column(db.Integer, default=0)
    user_ascore = db.Column(db.Float, default=0.0)
    user_tscore = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=dt.utcnow)
    
    # 定义与submissions的关系
    submissions = db.relationship('Submission', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    # 实现Flask-Login需要的属性和方法
    def get_id(self):
        """返回用户唯一标识符"""
        return self.student_id
    
    @property
    def is_active(self):
        """用户是否处于活动状态"""
        return True
    
    @property
    def is_authenticated(self):
        """用户是否已通过身份验证"""
        return True
    
    @property
    def is_anonymous(self):
        """用户是否是匿名用户"""
        return False
    
    @property
    def password(self):
        raise AttributeError('password不可读')
    
    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property 
    def is_admin(self):
        return self.usertype == '管理员'
        
    def get_ability_scores(self):
        """获取学生的详细能力评分
        
        返回:
            一个包含各种能力评分的字典
        """
        try:
            from utils.ability_scorer import ability_scorer
            return ability_scorer.calculate_detailed_ability_scores(self.student_id)
        except Exception as e:
            # 如果计算失败，返回基于现有数据的简单评分
            submissions = self.submissions.all()
            
            if not submissions:
                return {
                    'algorithm': 0,
                    'style': 0,
                    'functionality': 0,
                    'efficiency': 0,
                    'readability': 0
                }
            
            # 基于现有提交数据进行简单计算
            avg_score = sum(s.score for s in submissions if s.score) / len([s for s in submissions if s.score]) if any(s.score for s in submissions) else 0
            base_score = min(100, max(0, avg_score * 20))  # 转换为100分制
            
            return {
                'algorithm': base_score * 0.9,      # 算法能力
                'style': base_score * 0.8,          # 代码风格
                'functionality': base_score * 0.95, # 功能实现
                'efficiency': base_score * 0.75,    # 效率优化
                'readability': base_score * 0.85    # 代码可读性
            }
    
    @staticmethod
    def get_class_average_scores(course_id=None):
        """获取班级平均能力评分
        
        参数:
            course_id: 课程ID，可选
            
        返回:
            一个包含班级平均能力评分的字典
        """
        try:
            from utils.ability_scorer import ability_scorer
            
            # 获取所有有学生的班级
            classes = db.session.query(User.class_name).filter(
                User.class_name.isnot(None),
                User.usertype == '学生'
            ).distinct().all()
            
            result = {}
            
            for (class_name,) in classes:
                if not class_name:
                    continue
                
                # 获取该班级的学生
                students = User.query.filter_by(class_name=class_name, usertype='学生').all()
                
                if not students:
                    continue
                
                # 计算班级各项能力的平均分
                total_scores = {
                    'algorithm': 0.0,
                    'style': 0.0,
                    'functionality': 0.0,
                    'efficiency': 0.0,
                    'readability': 0.0
                }
                
                valid_count = 0
                for student in students:
                    try:
                        scores = student.get_ability_scores()
                        if any(scores.values()):  # 如果有有效评分
                            for key in total_scores:
                                total_scores[key] += scores.get(key, 0)
                            valid_count += 1
                    except Exception:
                        continue
                
                if valid_count > 0:
                    # 计算平均值
                    avg_scores = {key: value / valid_count for key, value in total_scores.items()}
                    result[class_name] = avg_scores
            
            return result
            
        except Exception as e:
            # 如果出错，返回空字典
            import logging
            logging.error(f"获取班级平均能力评分时出错: {e}")
            return {}


class Assignment(db.Model):
    """作业模型"""
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    total_score = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    count = db.Column(db.Integer, default=0)
    created_time = db.Column(db.DateTime, default=dt.utcnow)
    target_classes = db.Column(db.Text)  # 存储目标班级列表，用逗号分隔
    difficulty_level = db.Column(db.Integer, default=1)  # 难度级别：1-5
    
    # 定义与submissions的关系
    submissions = db.relationship('Submission', backref='assignment', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_target_class_list(self):
        """获取目标班级列表"""
        if not self.target_classes:
            return []
        return [cls.strip() for cls in self.target_classes.split(',') if cls.strip()]
    
    def set_target_classes(self, class_list):
        """设置目标班级列表"""
        if isinstance(class_list, list):
            self.target_classes = ','.join(class_list)
        else:
            self.target_classes = str(class_list)
    
    def get_class_progress(self):
        """获取各班级的完成进度"""
        target_classes = self.get_target_class_list()
        if not target_classes:
            return []
        
        progress = []
        for class_name in target_classes:
            # 获取该班级的学生数
            total_students = User.query.filter_by(class_name=class_name, usertype='学生').count()
            
            # 获取该班级完成该作业的学生数
            completed_students = db.session.query(Submission).join(User)\
                               .filter(User.class_name == class_name,
                                      Submission.assignment_id == self.id)\
                               .count()
            
            progress.append({
                'class_name': class_name,
                'total': total_students,
                'completed': completed_students,
                'progress_rate': round(completed_students / total_students * 100, 1) if total_students > 0 else 0
            })
        
        return progress


class Submission(db.Model):
    """提交记录模型"""
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('users.student_id', ondelete='CASCADE'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer)
    language = db.Column(db.String(20), default='cpp')
    submitted_at = db.Column(db.DateTime, default=dt.utcnow)
    feedback = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # 状态：pending, evaluated, failed
    ai_feedback = db.Column(db.Text, nullable=True)  # 大模型评估结果


class SystemLog(db.Model):
    """系统活动日志模型"""
    __tablename__ = 'system_logs'
    id = db.Column(db.Integer, primary_key=True)
    log_type = db.Column(db.String(50), nullable=False)  # 日志类型：用户注册、作业添加、代码提交等
    user_id = db.Column(db.String(20), db.ForeignKey('users.student_id', ondelete='SET NULL'), nullable=True)  # 关联用户ID，可能为空
    content = db.Column(db.Text, nullable=False)  # 日志内容
    created_at = db.Column(db.DateTime, default=dt.utcnow)  # 创建时间
    icon = db.Column(db.String(50), default='bi bi-activity')  # 图标class，用于前端显示
    
    # 关联用户，nullable=True 允许用户被删除后日志依然保留
    user = db.relationship('User', backref=db.backref('logs', lazy='dynamic'), foreign_keys=[user_id])
    
    @staticmethod
    def add_log(log_type, content, user_id=None, icon=None):
        """添加日志的便捷方法"""
        # 根据不同类型设置默认图标
        if icon is None:
            if log_type == '用户注册':
                icon = 'bi bi-person-plus'
            elif log_type == '添加作业':
                icon = 'bi bi-file-earmark-code'
            elif log_type == '提交代码':
                icon = 'bi bi-code'
            elif log_type == '用户登录':
                icon = 'bi bi-box-arrow-in-right'
            else:
                icon = 'bi bi-activity'
                
        log = SystemLog(log_type=log_type, content=content, user_id=user_id, icon=icon)
        db.session.add(log)
        db.session.commit()
        return log
    
    
class AbilityTrend(db.Model):
    """学生能力发展趋势缓存表"""
    __tablename__ = 'ability_trends'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('users.student_id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    trend_data = db.Column(db.Text, nullable=True)  # JSON格式存储趋势分析结果
    last_updated = db.Column(db.DateTime, default=dt.utcnow)  # 最后更新时间
    submissions_count = db.Column(db.Integer, default=0)  # 基于多少次提交生成的分析
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    
    # 关联用户
    user = db.relationship('User', backref=db.backref('ability_trend', uselist=False))
    
    @staticmethod
    def get_or_create(student_id):
        """获取或创建学生的能力趋势记录"""
        trend = AbilityTrend.query.filter_by(student_id=student_id).first()
        if not trend:
            trend = AbilityTrend(student_id=student_id)
            db.session.add(trend)
            db.session.commit()
        return trend
    
    @staticmethod
    def update_trend(student_id, trend_data, submissions_count):
        """更新学生的能力趋势数据"""
        trend = AbilityTrend.get_or_create(student_id)
        trend.trend_data = trend_data if isinstance(trend_data, str) else json.dumps(trend_data, ensure_ascii=False)
        trend.submissions_count = submissions_count
        trend.last_updated = dt.utcnow()
        trend.status = 'completed'
        db.session.commit()
        return trend
    
    def get_trend_dict(self):
        """获取趋势数据的字典格式"""
        if not self.trend_data:
            return {
                "trend": "暂无足够数据进行能力趋势分析",
                "improvement": "请继续提交更多代码作业以获得个性化分析",
                "suggestions": [
                    "完成更多编程作业，积累提交记录",
                    "注意代码规范和可读性",
                    "尝试不同难度的编程问题"
                ]
            }
        try:
            return json.loads(self.trend_data)
        except (json.JSONDecodeError, TypeError):
            return {
                "trend": "数据格式异常，请联系管理员",
                "improvement": "系统将在下次提交后重新分析",
                "suggestions": []
            }


class SystemConfig(db.Model):
    """系统配置模型"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(200))
    type = db.Column(db.String(20), default='string')
    updated_at = db.Column(db.DateTime, default=dt.now, onupdate=dt.now)
    
    @staticmethod
    def get_value(key, default=None):
        """获取配置值"""
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            return default
        
        # 根据类型转换值
        if config.type == 'int':
            return int(config.value) if config.value else 0
        elif config.type == 'float':
            return float(config.value) if config.value else 0.0
        elif config.type == 'bool':
            return config.value.lower() in ('true', '1', 'yes', 'y') if config.value else False
        else:
            return config.value
    
    @staticmethod
    def set_value(key, value, description=None, value_type='string'):
        """设置配置值"""
        # 将值转换为字符串进行存储
        str_value = str(value) if value is not None else None
        
        # 查找或创建配置项
        config = SystemConfig.query.filter_by(key=key).first()
        if not config:
            config = SystemConfig(
                key=key,
                value=str_value,
                description=description or key,
                type=value_type
            )
            db.session.add(config)
        else:
            config.value = str_value
            if description:
                config.description = description
            config.type = value_type
        
        db.session.commit()
        return config


class StudentQuestion(db.Model):
    """学生提问记录模型"""
    __tablename__ = 'student_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey('users.student_id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)  # 学生的问题
    code_snapshot = db.Column(db.Text, nullable=True)  # 提问时的代码快照
    answer = db.Column(db.Text, nullable=True)  # AI的回答
    is_helpful = db.Column(db.Boolean, nullable=True)  # 学生是否标记为有帮助（可选）
    asked_at = db.Column(db.DateTime, default=dt.now)
    
    # 关联
    student = db.relationship('User', backref=db.backref('questions', lazy=True))
    assignment = db.relationship('Assignment', backref=db.backref('questions', lazy=True))
    
    def __repr__(self):
        return f'<StudentQuestion {self.id} by {self.student_id} for assignment {self.assignment_id}>'


class CodeAdviceRequest(db.Model):
    """代码建议请求记录"""
    __tablename__ = 'code_advice_requests'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(50), db.ForeignKey('users.student_id'), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=True)
    code_snapshot = db.Column(db.Text, nullable=False, comment='请求时的代码快照')
    language = db.Column(db.String(20), nullable=False, default='cpp', comment='代码语言')
    advice = db.Column(db.Text, nullable=True, comment='生成的建议内容')
    requested_at = db.Column(db.DateTime, nullable=False, default=dt.now)
    
    # 关联
    student = db.relationship('User', backref=db.backref('advice_requests', lazy=True))
    assignment = db.relationship('Assignment', backref=db.backref('advice_requests', lazy=True))
    
    def __init__(self, student_id, code_snapshot, language='cpp', assignment_id=None, advice=None, requested_at=None):
        self.student_id = student_id
        self.assignment_id = assignment_id
        self.code_snapshot = code_snapshot
        self.language = language
        self.advice = advice
        self.requested_at = requested_at or dt.now()
    
    def __repr__(self):
        return f'<CodeAdviceRequest {self.id}: {self.student_id} - {self.requested_at}>'


def init_db(app):
    """初始化数据库"""
    with app.app_context():
        db.create_all()  # 创建数据库表
        
        # 初始化系统设置
        default_settings = {
            'site_name': {
                'value': '学生程序设计能力评价系统',
                'description': '网站名称',
                'type': 'string'
            },
            'site_description': {
                'value': '一个用于评估学生编程能力的在线平台',
                'description': '网站描述',
                'type': 'string'
            },
            'enable_registration': {
                'value': 'true',
                'description': '是否允许新用户注册',
                'type': 'bool'
            },
            'login_message': {
                'value': '欢迎登录学生程序设计能力评价系统',
                'description': '登录页面欢迎消息',
                'type': 'string'
            },
            'default_user_score': {
                'value': '60',
                'description': '新用户默认初始分数',
                'type': 'int'
            },
            'submissions_per_day': {
                'value': '10',
                'description': '每日最大提交次数',
                'type': 'int'
            },
            'admin_email': {
                'value': 'daiyupeng5@gmail.com',
                'description': '管理员联系邮箱',
                'type': 'string'
            },
            'system_version': {
                'value': '1.0.0',
                'description': '系统版本',
                'type': 'string'
            }
        }
        
        # 检查并添加默认设置
        for key, setting in default_settings.items():
            config = SystemConfig.query.filter_by(key=key).first()
            if not config:
                config = SystemConfig(
                    key=key,
                    value=setting['value'],
                    description=setting['description'],
                    type=setting['type']
                )
                db.session.add(config)
        
        try:
            db.session.commit()
        except Exception as e:
            print(f"初始化系统设置时出错: {str(e)}")
            db.session.rollback() 