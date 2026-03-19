"""
基于班级整体数据的学生能力评分系统
"""
import numpy as np
from models import db, User, Submission
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class AbilityScorer:
    """学生能力评分计算器"""
    
    def __init__(self):
        self.weights = {
            'submission_frequency': 0.25,    # 提交频率权重
            'average_score': 0.35,          # 平均分权重  
            'consistency': 0.20,             # 稳定性权重
            'improvement': 0.20              # 进步程度权重
        }
    
    def calculate_student_ability_score(self, student_id: str) -> float:
        """
        计算学生的综合能力评分
        
        参数:
            student_id: 学生ID
            
        返回:
            float: 综合能力评分 (0-5分)
        """
        try:
            user = User.query.get(student_id)
            if not user or user.usertype != '学生':
                return 0.0
            
            # 获取学生的提交记录
            submissions = list(user.submissions.order_by(Submission.submitted_at).all())
            
            if not submissions:
                return 0.0
            
            # 获取班级数据用于相对评分
            class_data = self._get_class_comparison_data(user.class_name)
            
            # 计算各项指标
            submission_score = self._calculate_submission_frequency_score(submissions, class_data)
            average_score = self._calculate_average_score(submissions, class_data)
            consistency_score = self._calculate_consistency_score(submissions)
            improvement_score = self._calculate_improvement_score(submissions)
            
            # 加权平均
            final_score = (
                submission_score * self.weights['submission_frequency'] +
                average_score * self.weights['average_score'] +
                consistency_score * self.weights['consistency'] +
                improvement_score * self.weights['improvement']
            )
            
            # 确保分数在0-5范围内
            final_score = max(0.0, min(5.0, final_score))
            
            logger.info(f"学生 {student_id} 能力评分: {final_score:.2f} (提交频率:{submission_score:.2f}, 平均分:{average_score:.2f}, 稳定性:{consistency_score:.2f}, 进步:{improvement_score:.2f})")
            
            return final_score
            
        except Exception as e:
            logger.error(f"计算学生 {student_id} 能力评分时出错: {e}")
            return 0.0
    
    def _get_class_comparison_data(self, class_name: str) -> Dict:
        """获取班级对比数据"""
        if not class_name:
            return {'avg_submissions': 1, 'avg_score': 2.5, 'total_students': 1}
        
        try:
            # 获取班级学生列表
            class_students = User.query.filter_by(class_name=class_name, usertype='学生').all()
            if not class_students:
                return {'avg_submissions': 1, 'avg_score': 2.5, 'total_students': 1}
            
            # 计算班级统计数据
            total_submissions = sum(s.submit_count for s in class_students)
            avg_submissions = total_submissions / len(class_students) if class_students else 1
            
            # 计算班级平均分
            all_scores = []
            for student in class_students:
                student_submissions = student.submissions.all()
                if student_submissions:
                    student_avg = sum(s.score for s in student_submissions if s.score) / len(student_submissions)
                    all_scores.append(student_avg)
            
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 2.5
            
            return {
                'avg_submissions': max(1, avg_submissions),
                'avg_score': avg_score,
                'total_students': len(class_students)
            }
        except Exception as e:
            logger.error(f"获取班级 {class_name} 对比数据时出错: {e}")
            return {'avg_submissions': 1, 'avg_score': 2.5, 'total_students': 1}
    
    def _calculate_submission_frequency_score(self, submissions: List[Submission], class_data: Dict) -> float:
        """计算提交频率得分 (0-5分)"""
        if not submissions:
            return 0.0
        
        user_submissions = len(submissions)
        class_avg = class_data['avg_submissions']
        
        # 相对于班级平均水平的比例
        ratio = user_submissions / class_avg
        
        # 转换为0-5分，以班级平均为3分
        if ratio >= 2.0:
            return 5.0
        elif ratio >= 1.5:
            return 4.0 + (ratio - 1.5) * 2.0  # 4.0-5.0
        elif ratio >= 1.0:
            return 3.0 + (ratio - 1.0) * 2.0  # 3.0-4.0
        elif ratio >= 0.5:
            return 1.5 + (ratio - 0.5) * 3.0  # 1.5-3.0
        else:
            return ratio * 3.0                 # 0.0-1.5
    
    def _calculate_average_score(self, submissions: List[Submission], class_data: Dict) -> float:
        """计算平均分得分 (0-5分)"""
        if not submissions:
            return 0.0
        
        # 计算学生平均分
        scores = [s.score for s in submissions if s.score is not None]
        if not scores:
            return 0.0
        
        user_avg = sum(scores) / len(scores)
        class_avg = class_data['avg_score']
        
        # 相对于班级平均水平
        ratio = user_avg / class_avg if class_avg > 0 else 1.0
        
        # 转换为0-5分
        if ratio >= 1.5:
            return 5.0
        elif ratio >= 1.2:
            return 4.0 + (ratio - 1.2) / 0.3  # 4.0-5.0
        elif ratio >= 0.8:
            return 2.0 + (ratio - 0.8) / 0.4 * 2.0  # 2.0-4.0  
        else:
            return ratio / 0.8 * 2.0  # 0.0-2.0
    
    def _calculate_consistency_score(self, submissions: List[Submission]) -> float:
        """计算稳定性得分 (0-5分)"""
        if len(submissions) < 2:
            return 3.0  # 默认中等分数
        
        # 计算分数的标准差
        scores = [s.score for s in submissions if s.score is not None]
        if len(scores) < 2:
            return 3.0
        
        std_dev = np.std(scores)
        
        # 标准差越小，稳定性越高
        if std_dev <= 0.5:
            return 5.0
        elif std_dev <= 1.0:
            return 4.0
        elif std_dev <= 1.5:
            return 3.0
        elif std_dev <= 2.0:
            return 2.0
        else:
            return 1.0
    
    def _calculate_improvement_score(self, submissions: List[Submission]) -> float:
        """计算进步程度得分 (0-5分)"""
        if len(submissions) < 3:
            return 3.0  # 默认中等分数
        
        # 获取有分数的提交记录
        scored_submissions = [s for s in submissions if s.score is not None]
        if len(scored_submissions) < 3:
            return 3.0
        
        # 计算前1/3和后1/3的平均分
        n = len(scored_submissions)
        first_third = scored_submissions[:n//3] if n >= 3 else scored_submissions[:1]
        last_third = scored_submissions[-n//3:] if n >= 3 else scored_submissions[-1:]
        
        first_avg = sum(s.score for s in first_third) / len(first_third)
        last_avg = sum(s.score for s in last_third) / len(last_third)
        
        improvement = last_avg - first_avg
        
        # 转换为0-5分
        if improvement >= 2.0:
            return 5.0
        elif improvement >= 1.0:
            return 4.0
        elif improvement >= 0.5:
            return 3.5
        elif improvement >= 0:
            return 3.0
        elif improvement >= -0.5:
            return 2.5
        elif improvement >= -1.0:
            return 2.0
        else:
            return 1.0
    
    def calculate_detailed_ability_scores(self, student_id: str) -> Dict[str, float]:
        """
        计算学生的详细能力评分
        
        返回:
            Dict: 包含各项能力的详细评分
        """
        try:
            user = User.query.get(student_id)
            if not user or user.usertype != '学生':
                return {
                    'algorithm': 0.0,
                    'style': 0.0, 
                    'functionality': 0.0,
                    'efficiency': 0.0,
                    'readability': 0.0
                }
            
            submissions = list(user.submissions.all())
            if not submissions:
                return {
                    'algorithm': 0.0,
                    'style': 0.0,
                    'functionality': 0.0, 
                    'efficiency': 0.0,
                    'readability': 0.0
                }
            
            # 基于综合能力评分和提交表现计算各项能力
            overall_score = self.calculate_student_ability_score(student_id)
            
            # 根据提交数量和质量调整各项分数
            submit_count = len(submissions)
            avg_score = sum(s.score for s in submissions if s.score) / len([s for s in submissions if s.score]) if any(s.score for s in submissions) else 0
            
            # 基础分数（基于综合评分）
            base_score = overall_score * 20  # 转换为100分制
            
            # 各项能力的相对权重调整
            scores = {
                'algorithm': base_score * (0.9 + 0.2 * min(1.0, submit_count / 10)),  # 算法能力与提交数相关
                'functionality': base_score * (0.8 + 0.4 * min(1.0, avg_score / 5)),  # 功能实现与平均分相关
                'efficiency': base_score * (0.7 + 0.3 * min(1.0, overall_score / 5)),  # 效率与整体能力相关
                'readability': base_score * (0.8 + 0.2 * min(1.0, submit_count / 5)),  # 可读性与经验相关
                'style': base_score * (0.75 + 0.25 * min(1.0, overall_score / 5))      # 风格与整体能力相关
            }
            
            # 确保分数在合理范围内 (0-100)
            for key in scores:
                scores[key] = max(0, min(100, scores[key]))
            
            return scores
            
        except Exception as e:
            logger.error(f"计算学生 {student_id} 详细能力评分时出错: {e}")
            return {
                'algorithm': 0.0,
                'style': 0.0,
                'functionality': 0.0,
                'efficiency': 0.0, 
                'readability': 0.0
            }
    
    def update_all_students_scores(self):
        """更新所有学生的能力评分"""
        try:
            students = User.query.filter_by(usertype='学生').all()
            updated_count = 0
            
            logger.info(f"开始更新 {len(students)} 名学生的能力评分...")
            
            for student in students:
                try:
                    new_score = self.calculate_student_ability_score(student.student_id)
                    old_score = student.user_ascore
                    
                    student.user_ascore = new_score
                    db.session.add(student)
                    
                    if abs(new_score - old_score) > 0.1:  # 只记录显著变化
                        logger.info(f"更新学生 {student.student_id}({student.full_name}) 评分: {old_score:.2f} -> {new_score:.2f}")
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"更新学生 {student.student_id} 评分失败: {e}")
                    continue
            
            db.session.commit()
            logger.info(f"✅ 成功更新 {updated_count} 名学生的能力评分")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"批量更新学生评分时出错: {e}")
            db.session.rollback()
            return 0

# 全局评分器实例
ability_scorer = AbilityScorer()
