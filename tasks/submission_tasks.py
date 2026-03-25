"""后台异步评测任务"""
import threading
import traceback
import json
from datetime import datetime
from models import db, User, Assignment, Submission, SystemLog, TestCase as TC
from utils.code_evaluator import evaluate_cpp_code, llm_evaluator
from utils.sandbox_runner import run_test_cases

def evaluate_submission_async(app, submission_id, assignment_title):
    """
    异步评测学生提交的代码
    触发后台线程执行，不阻塞 Flask 主请求
    """
    def _evaluate():
        with app.app_context():
            try:
                submission = Submission.query.get(submission_id)
                if not submission:
                    print(f"❌ 找不到提交记录: {submission_id}")
                    return
                
                assignment = Assignment.query.get(submission.assignment_id)
                code = submission.code
                student_id = submission.student_id
                
                # 1. AI 基础评估 (使用 C++ 评估器)
                print(f"🚀 开始后台評估提交 {submission_id}，题目: {assignment_title}")
                try:
                    score, feedback = evaluate_cpp_code(code, assignment_title=assignment_title)
                    
                    # 保存 AI 结构化数据
                    if hasattr(llm_evaluator, '_last_structured_data'):
                        structured_data = llm_evaluator._last_structured_data
                        submission.ai_feedback = json.dumps(structured_data, ensure_ascii=False)
                    elif isinstance(feedback, str) and ("【" in feedback or "改进建议" in feedback):
                        submission.ai_feedback = feedback
                    
                    submission.score = score
                    submission.feedback = feedback
                except Exception as ai_err:
                    print(f"AI 评估过程出错: {ai_err}")
                    submission.score = 1
                    submission.feedback = f"AI 评估过程中出错: {str(ai_err)}"
                
                # 2. 沙箱测试用例评判
                try:
                    test_cases = TC.query.filter_by(assignment_id=submission.assignment_id)\
                                        .order_by(TC.order_index).all()
                    if test_cases:
                        tc_list = [tc.to_dict() for tc in test_cases]
                        sandbox_result = run_test_cases(code, tc_list)
                        
                        submission.sandbox_status = sandbox_result['status']
                        submission.sandbox_passed = sandbox_result['passed']
                        submission.sandbox_total = sandbox_result['total']
                        submission.sandbox_detail = json.dumps(sandbox_result['details'], ensure_ascii=False)
                        
                        # 根据沙箱结果修正分数 (5分制)
                        if sandbox_result['total'] > 0:
                            sandbox_score = (sandbox_result['passed'] / sandbox_result['total']) * 5
                            final_score = sandbox_score
                            
                            if sandbox_result['status'] == 'error':
                                final_score = min(final_score, 1)
                            
                            submission.score = round(final_score)
                            print(f"沙箱评判完成: {submission.sandbox_passed}/{submission.sandbox_total}, 最终得分: {submission.score}")
                except Exception as sandbox_err:
                    print(f"沙箱评判过程出错: {sandbox_err}")
                
                # 3. 更新完成状态
                submission.status = 'evaluated'
                
                # 4. 更新作业统计信息
                assignment.total_score += submission.score
                assignment.count += 1
                assignment.average_score = assignment.total_score / assignment.count
                
                # 5. 更新用户统计信息
                user = User.query.get(student_id)
                if user:
                    user.submit_count += 1
                    user.user_tscore += submission.score
                    user.user_ascore = user.user_tscore / user.submit_count
                
                db.session.commit()

                # 6. 更新知识点评分 (新流程：在评测完成后进行)
                try:
                    from models import AssignmentKnowledgePoint, KnowledgePointScore
                    from services.ai_evaluator import AIEvaluator
                    
                    # 获取作业的知识点标签
                    assignment_kps = AssignmentKnowledgePoint.query.filter_by(
                        assignment_id=assignment.id
                    ).all()

                    if assignment_kps:
                        print(f"为作业 {assignment.id} 更新 {len(assignment_kps)} 个既有知识点分数")
                        for kp in assignment_kps:
                            KnowledgePointScore.update_score(
                                student_id=student_id,
                                knowledge_point=kp.knowledge_point,
                                assignment_score=submission.score * 20,  # 转换为0-100分
                                difficulty=kp.difficulty,
                                weight=kp.weight
                            )
                    else:
                        # 如果没有标注，使用AI自动检测 (也移到了后台)
                        print(f"作业 {assignment.id} 无知识点标签，使用AI自动检测")
                        api_key = app.config.get('ZHIPU_API_KEY')
                        if api_key:
                            ai_evaluator = AIEvaluator(api_key)
                            detected_kps = ai_evaluator.detect_code_knowledge_points(code, assignment.title)

                            for kp_data in detected_kps:
                                AssignmentKnowledgePoint.add_to_assignment(
                                    assignment_id=assignment.id,
                                    knowledge_point=kp_data['knowledge_point'],
                                    weight=kp_data.get('weight', 1.0),
                                    difficulty=kp_data.get('difficulty', 1.0),
                                    auto_detected=True
                                )

                                KnowledgePointScore.update_score(
                                    student_id=student_id,
                                    knowledge_point=kp_data['knowledge_point'],
                                    assignment_score=submission.score * 20,
                                    difficulty=kp_data.get('difficulty', 1.0),
                                    weight=kp_data.get('weight', 1.0)
                                )
                            print(f"AI自动检测并更新了 {len(detected_kps)} 个知识点")
                except Exception as kp_err:
                    print(f"更新知识点评分失败: {kp_err}")

                # 7. 触发后台能力分析任务
                try:
                    from tasks.ability_analysis import trigger_analysis_if_needed
                    from models import AbilityTrend
                    AbilityTrend.mark_as_outdated(student_id)
                    trigger_analysis_if_needed(student_id)
                    print(f"已触发学生 {student_id} 的全量能力分析任务")
                except Exception as ability_err:
                    print(f"触发能力分析失败: {ability_err}")

                db.session.commit()
                
                # 8. 添加系统日志
                SystemLog.add_log(
                    log_type='评测完成',
                    content=f'提交 {submission_id} 评测已完成，得分：{submission.score}/5',
                    user_id=student_id,
                    icon='bi bi-check-circle-fill'
                )
                print(f"✅ 提交 {submission_id} 评测全部完成")
                
            except Exception as e:
                print(f"❌ 评测线程崩溃: {e}")
                traceback.print_exc()
                with app.app_context():
                    sub = Submission.query.get(submission_id)
                    if sub:
                        sub.status = 'failed'
                        sub.feedback = f"后台评测发生严重错误: {str(e)}"
                        db.session.commit()

    # 启动后台线程
    thread = threading.Thread(target=_evaluate)
    thread.daemon = True
    thread.start()
    print(f"📤 已启动后台评测线程 - 提交 ID: {submission_id}")
