#!/usr/bin/env python3
"""
异步任务处理系统
简化版实现，用于处理能力趋势分析等耗时任务

升级建议：
- 生产环境建议使用 Celery + Redis/RabbitMQ
- 当前实现适合中小规模应用
"""
import threading
import queue
import time
import json
import traceback
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)

class AsyncTaskManager:
    """异步任务管理器"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.workers = []
        self.is_running = False
        self.app = None  # 保存Flask应用实例
        self.logger = None  # 保存logger引用
        
    def start(self, worker_count=2, app=None):
        """启动异步任务处理器"""
        if self.is_running:
            return
            
        self.app = app  # 保存应用实例
        self.logger = app.logger if app else logger  # 使用Flask应用的logger
        self.is_running = True
        self.logger.info(f"启动异步任务处理器，工作线程数: {worker_count}")
        
        for i in range(worker_count):
            worker = threading.Thread(
                target=self._worker, 
                args=(f"worker-{i+1}",),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            
    def stop(self):
        """停止任务处理器"""
        self.is_running = False
        if self.logger:
            self.logger.info("异步任务处理器已停止")
        
    def add_task(self, task_type, **kwargs):
        """添加任务到队列"""
        task = {
            'id': f"{task_type}_{int(time.time())}_{threading.current_thread().ident}",
            'type': task_type,
            'data': kwargs,
            'created_at': datetime.now(),
            'attempts': 0
        }
        
        self.task_queue.put(task)
        if self.logger:
            self.logger.info(f"任务已添加到队列: {task['id']} (类型: {task_type})")
        return task['id']
        
    def _worker(self, worker_name):
        """工作线程主循环"""
        if self.logger:
            self.logger.info(f"工作线程 {worker_name} 已启动")
        
        while self.is_running:
            try:
                # 从队列获取任务，超时1秒
                task = self.task_queue.get(timeout=1)
                self._process_task(task, worker_name)
                self.task_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续循环
                continue
            except Exception as e:
                if self.logger:
                    self.logger.error(f"工作线程 {worker_name} 处理任务时出错: {e}")
                    self.logger.error(traceback.format_exc())
                
        if self.logger:
            self.logger.info(f"工作线程 {worker_name} 已停止")
        
    def _process_task(self, task, worker_name):
        """处理单个任务"""
        task_id = task['id']
        task_type = task['type']
        
        if self.logger:
            self.logger.info(f"{worker_name} 开始处理任务: {task_id}")
        start_time = time.time()
        
        try:
            if task_type == 'update_ability_trend':
                self._handle_ability_trend_update(task)
            elif task_type == 'batch_update_trends':
                self._handle_batch_update(task)
            else:
                if self.logger:
                    self.logger.warning(f"未知任务类型: {task_type}")
                return
                
            execution_time = time.time() - start_time
            if self.logger:
                self.logger.info(f"任务完成: {task_id} (耗时: {execution_time:.2f}s)")
            
        except Exception as e:
            execution_time = time.time() - start_time
            task['attempts'] += 1
            
            if self.logger:
                self.logger.error(f"任务失败: {task_id} (耗时: {execution_time:.2f}s, 尝试次数: {task['attempts']})")
                self.logger.error(f"错误详情: {e}")
                self.logger.error(traceback.format_exc())
            
            # 重试机制（最多3次）
            if task['attempts'] < 3:
                if self.logger:
                    self.logger.info(f"任务 {task_id} 将在5秒后重试")
                time.sleep(5)
                self.task_queue.put(task)
            else:
                if self.logger:
                    self.logger.error(f"任务 {task_id} 重试次数已达上限，标记为失败")
                self._mark_task_failed(task)
                
    def _handle_ability_trend_update(self, task):
        """处理能力趋势更新任务"""
        from models import db, AbilityTrend, Submission, User, Assignment
        from services.ai_evaluator import AIEvaluator
        import os
        
        data = task['data']
        student_id = data['student_id']
        
        if self.logger:
            self.logger.info(f"开始分析学生 {student_id} 的能力发展趋势")
        
        # 在应用上下文中执行
        if not self.app:
            if self.logger:
                self.logger.error(f"Flask应用实例未设置，无法处理学生 {student_id} 的任务")
            return
            
        with self.app.app_context():
            try:
                # 标记为处理中
                trend = AbilityTrend.get_or_create(student_id)
                trend.status = 'processing'
                db.session.commit()
                
                # 获取学生信息和已分配的作业
                user = User.query.get(student_id)
                if not user:
                    self.logger.warning(f"找不到学生 {student_id}，无法进行能力分析")
                    trend.status = 'failed'
                    db.session.commit()
                    return

                class_name = user.class_name
                assigned_assignment_ids = []
                if class_name:
                    assigned_assignments = Assignment.query.filter(
                        Assignment.target_classes.like(f'%{class_name}%')
                    ).all()
                    assigned_assignment_ids = [a.id for a in assigned_assignments]

                if not assigned_assignment_ids:
                    self.logger.info(f"学生 {student_id} 所在的班级没有分配任何作业，跳过分析")
                    trend.status = 'completed' # No work to do, so it's "complete"
                    trend.trend_data = json.dumps({
                        "trend": "暂无已分配的作业",
                        "improvement": "请等待教师分配作业后再进行分析。",
                        "suggestions": []
                    })
                    db.session.commit()
                    return

                # 获取学生对已分配作业的提交记录
                submissions = Submission.query.filter(
                    Submission.student_id == student_id,
                    Submission.assignment_id.in_(assigned_assignment_ids)
                ).all()
                
                submission_data = []
                for sub in submissions:
                    if sub.code and sub.assignment:
                        submission_data.append({
                            'assignment_title': sub.assignment.title,
                            'code': sub.code,
                            'score': sub.score,
                            'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M:%S')
                        })
                
                if not submission_data:
                    if self.logger:
                        self.logger.info(f"学生 {student_id} 对已分配的作业暂无提交记录，跳过分析")
                    trend.status = 'completed'
                    trend.trend_data = json.dumps({
                        "trend": "您还没有对已分配的作业进行任何提交",
                        "improvement": "请先完成一些作业再来分析能力趋势。",
                        "suggestions": []
                    })
                    db.session.commit()
                    return
                
                # 初始化AI评估器
                api_key = self.app.config.get('ZHIPU_API_KEY', os.environ.get('ZHIPU_API_KEY'))
                if not api_key:
                    if self.logger:
                        self.logger.warning(f"API密钥未设置，无法为学生 {student_id} 进行AI分析")
                    trend.status = 'failed'
                    db.session.commit()
                    return
                    
                ai_evaluator = AIEvaluator(api_key)
                
                # 执行AI分析
                if self.logger:
                    self.logger.info(f"调用AI API分析学生 {student_id} 的 {len(submission_data)} 次提交")
                ability_analysis = ai_evaluator.analyze_ability_trend(submission_data)

                # 检查AI分析是否返回错误
                if isinstance(ability_analysis, dict) and ability_analysis.get("trend") == "分析过程中出现错误":
                    self.logger.error(f"AI分析为学生 {student_id} 返回了一个错误，标记任务为失败")
                    trend.status = 'failed'
                    db.session.commit()
                    return

                # 保存结果
                AbilityTrend.update_trend(student_id, ability_analysis, len(submission_data))
                if self.logger:
                    self.logger.info(f"学生 {student_id} 的能力趋势分析完成并已保存")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"处理学生 {student_id} 的能力趋势分析失败: {e}")
                if self.app:
                    with self.app.app_context():
                        from models import db, AbilityTrend
                        trend = AbilityTrend.get_or_create(student_id)
                        trend.status = 'failed'
                        db.session.commit()
                else:
                    if self.logger:
                        self.logger.error("Flask应用实例未设置，无法标记任务失败状态")
                raise
                
    def _handle_batch_update(self, task):
        """处理批量更新任务"""
        data = task['data']
        student_ids = data.get('student_ids', [])
        
        if self.logger:
            self.logger.info(f"开始批量更新 {len(student_ids)} 个学生的能力趋势")
        
        for student_id in student_ids:
            # 为每个学生创建单独的任务
            self.add_task('update_ability_trend', student_id=student_id)
            
    def _mark_task_failed(self, task):
        """标记任务失败"""
        if task['type'] == 'update_ability_trend':
            student_id = task['data']['student_id']
            try:
                if self.app:
                    with self.app.app_context():
                        from models import db, AbilityTrend
                        trend = AbilityTrend.get_or_create(student_id)
                        trend.status = 'failed'
                        db.session.commit()
                else:
                    if self.logger:
                        self.logger.error("Flask应用实例未设置，无法标记任务失败状态")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"标记任务失败状态时出错: {e}")

# 全局任务管理器实例
task_manager = AsyncTaskManager()

def init_async_tasks(app):
    """初始化异步任务系统"""
    with app.app_context():
        task_manager.start(app=app)  # 传递应用实例
        app.logger.info("异步任务系统已启动")

def add_ability_trend_task(student_id):
    """添加能力趋势分析任务"""
    return task_manager.add_task('update_ability_trend', student_id=student_id)

def add_batch_trend_update(student_ids):
    """添加批量趋势更新任务"""
    return task_manager.add_task('batch_update_trends', student_ids=student_ids)
