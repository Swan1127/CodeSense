"""后台能力分析任务"""
import threading
import os
from models import db, Submission, AbilityTrend
from services.ai_evaluator import AIEvaluator
from services.api_keys import api_keys  # 导入 API 密钥管理器
from flask import current_app


def generate_ability_analysis_async(app, student_id):
    """
    异步生成学生能力分析
    在后台线程中执行，不阻塞主请求

    Args:
        app: Flask应用实例
        student_id: 学生ID
    """
    def _generate():
        with app.app_context():
            try:
                # 1. 标记为处理中
                AbilityTrend.mark_as_processing(student_id)

                # 2. 获取最近20次提交
                submissions = Submission.query.filter_by(student_id=student_id)\
                    .order_by(Submission.submitted_at.desc())\
                    .limit(20)\
                    .all()

                if not submissions:
                    # 没有提交记录，标记为完成但无数据
                    AbilityTrend.update_analysis(
                        student_id=student_id,
                        analysis_markdown="暂无提交记录，请先完成一些作业。",
                        submissions_count=0
                    )
                    return

                # 3. 准备提交数据
                submission_data = []
                for sub in submissions:
                    if sub.code and sub.assignment:
                        submission_data.append({
                            'assignment_title': sub.assignment.title,
                            'code': sub.code[:500],  # 只取前500字符
                            'score': sub.score,
                            'submitted_at': sub.submitted_at.strftime('%Y-%m-%d %H:%M')
                        })

                # 4. 调用AI生成分析（添加超时重试机制）
                api_key = api_keys.zhipu_key
                if not api_key:
                    print(f"❌ AI服务未配置，无法生成分析 - 学生 {student_id}")
                    AbilityTrend.update_analysis(
                        student_id=student_id,
                        analysis_markdown="AI服务未配置，无法生成分析",
                        submissions_count=len(submissions)
                    )
                    return

                ai_evaluator = AIEvaluator(api_key)

                # 收集完整的Markdown分析（带重试）
                analysis_markdown = ""
                print(f"🚀 开始后台生成能力分析 - 学生 {student_id}")

                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        for chunk in ai_evaluator.analyze_ability_trend_stream(submission_data):
                            analysis_markdown += chunk

                        # 成功完成，跳出重试循环
                        break
                    except Exception as chunk_error:
                        print(f"⚠️ 生成分析时出错（尝试 {attempt + 1}/{max_retries}）: {str(chunk_error)}")
                        if attempt < max_retries - 1:
                            print(f"⏳ 等待3秒后重试...")
                            import time
                            time.sleep(3)
                            analysis_markdown = ""  # 重置
                        else:
                            # 最后一次重试也失败了
                            raise

                # 5. 保存到数据库
                AbilityTrend.update_analysis(
                    student_id=student_id,
                    analysis_markdown=analysis_markdown,
                    submissions_count=len(submissions)
                )

                print(f"✅ 能力分析生成完成 - 学生 {student_id}, 长度: {len(analysis_markdown)} 字符")

            except Exception as e:
                print(f"❌ 生成能力分析失败 - 学生 {student_id}: {str(e)}")
                import traceback
                traceback.print_exc()

                # 标记为失败
                trend = AbilityTrend.get_or_create(student_id)
                trend.status = 'failed'
                db.session.commit()

    # 在后台线程中执行
    thread = threading.Thread(target=_generate)
    thread.daemon = True
    thread.start()
    print(f"📤 已启动后台分析任务 - 学生 {student_id}")


def trigger_analysis_if_needed(student_id, force=False):
    """
    检查是否需要触发分析

    Args:
        student_id: 学生ID
        force: 是否强制重新生成

    Returns:
        bool: 是否触发了新的分析任务
    """
    from flask import current_app

    trend = AbilityTrend.query.filter_by(student_id=student_id).first()

    # 如果强制更新或没有分析记录，触发分析
    if force or not trend or trend.status in ['pending', 'outdated', 'failed']:
        generate_ability_analysis_async(current_app._get_current_object(), student_id)
        return True

    # 如果正在处理中，不重复触发
    if trend.status == 'processing':
        return False

    return False
