"""
三阶段引导式学习系统 — 路由模块
Blueprint: thinking, URL前缀: /thinking
"""
import json
import traceback
from datetime import datetime as dt

from flask import Blueprint, render_template, request, jsonify, session, Response, current_app
from flask_login import current_user

from models import (db, Assignment, AssignmentThinkingPreset,
                    ThinkingSession, ThinkingStageLog)
from utils.auth import login_required
from utils.thinking_ai import (
    generate_preset, evaluate_description, generate_stage1_hint,
    generate_stage2_hint, companion_agent_chat, teacher_agent_chat,
    student_agent_chat, student_agent_write_code, evaluate_feynman_code_fix,
    sanitize_response
)

thinking = Blueprint('thinking', __name__, url_prefix='/thinking')


# ============================================================
# 页面路由
# ============================================================

@thinking.route('/<int:assignment_id>')
@login_required
def arena(assignment_id):
    """三阶段学习主页面"""
    assignment = Assignment.query.get_or_404(assignment_id)
    preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()

    # 检查预设状态，自动触发缺失的任务以防卡死
    preset_status = 'not_found'
    
    if not preset:
        # 1. 预设不存在时：新建并异步触发生成
        try:
            from utils.async_tasks import add_generate_preset_task
            preset = AssignmentThinkingPreset(assignment_id=assignment_id, status='generating')
            db.session.add(preset)
            db.session.commit()
            add_generate_preset_task(assignment_id)
            preset_status = 'generating'
            current_app.logger.info(f"作业 {assignment_id} 预设不存在，已自动触发异步生成")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"自动触发预设生成失败: {e}")
            preset_status = 'failed'
    else:
        # 2. 预设已存在，但如果是处于 'generating' 状态，需要防止由于服务器重启导致队列丢失而无限卡死
        if preset.status == 'generating':
            # 检查 updated_at 或 created_at，如果距离现在超过 120 秒，说明可能已经从队列丢失，重新触发
            from datetime import datetime
            delta = datetime.utcnow() - (preset.updated_at or preset.created_at)
            if delta.total_seconds() > 120:
                try:
                    from utils.async_tasks import add_generate_preset_task
                    preset.status = 'generating'
                    preset.updated_at = datetime.utcnow()
                    db.session.commit()
                    add_generate_preset_task(assignment_id)
                    current_app.logger.info(f"作业 {assignment_id} 的预设已处于 'generating' 超过 120s，已自动重新触发")
                except Exception as e:
                    current_app.logger.error(f"重新触发预设生成任务失败: {e}")
        preset_status = preset.status

    # 检查是否有进行中的会话
    existing_session = ThinkingSession.query.filter_by(
        student_id=current_user.student_id,
        assignment_id=assignment_id,
        status='in_progress'
    ).first()

    return render_template('thinking/arena.html',
                           assignment=assignment,
                           preset_status=preset_status,
                           existing_session=existing_session)


# ============================================================
# API: 会话管理
# ============================================================

@thinking.route('/api/start_session', methods=['POST'])
@login_required
def start_session():
    """创建或恢复学习会话"""
    try:
        data = request.get_json()
        assignment_id = data.get('assignment_id')

        if not assignment_id:
            return jsonify({'error': '缺少作业ID'}), 400

        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'error': '作业不存在'}), 404

        # 检查预设是否就绪
        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
        if not preset or preset.status != 'ready':
            return jsonify({'error': '学习数据尚未准备好，请稍后再试', 'preset_status': preset.status if preset else 'not_found'}), 503

        # 查找现有进行中的会话
        existing = ThinkingSession.query.filter_by(
            student_id=current_user.student_id,
            assignment_id=assignment_id,
            status='in_progress'
        ).first()

        if existing:
            return jsonify({
                'success': True,
                'session_id': existing.id,
                'current_stage': existing.current_stage,
                'resumed': True,
                'preset': _serialize_preset(preset)
            })

        # 创建新会话
        new_session = ThinkingSession(
            student_id=current_user.student_id,
            assignment_id=assignment_id,
            current_stage=1
        )
        db.session.add(new_session)
        db.session.commit()

        # 记录日志
        _log_event(new_session.id, 1, 'session_start', 'student', '开始引导式学习')

        return jsonify({
            'success': True,
            'session_id': new_session.id,
            'current_stage': 1,
            'resumed': False,
            'preset': _serialize_preset(preset)
        })

    except Exception as e:
        print(f"创建学习会话失败: {e}")
        traceback.print_exc()
        return jsonify({'error': f'创建会话失败: {str(e)}'}), 500


# ============================================================
# API: 阶段1 — 自然语言描述
# ============================================================

@thinking.route('/api/stage1/submit', methods=['POST'])
@login_required
def stage1_submit():
    """提交自然语言描述并获取AI评判"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        description = data.get('description', '').strip()

        if not description or len(description) < 5:
            return jsonify({'error': '请提供更详细的思路描述（至少5个字）'}), 400

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在或无权访问'}), 403

        # 获取预设的关键步骤
        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        if not preset:
            return jsonify({'error': '预设数据不存在'}), 500

        key_steps = preset.get_key_steps()
        assignment = Assignment.query.get(ts.assignment_id)

        # AI评判
        score, feedback = evaluate_description(description, key_steps, assignment.title)

        # 更新会话
        ts.stage1_description = description
        ts.stage1_score = score

        # 记录日志
        _log_event(session_id, 1, 'description_submit', 'student', description,
                   metadata={'score': score, 'feedback': feedback})

        passed = score >= 80
        if passed:
            ts.current_stage = 2
            _log_event(session_id, 1, 'stage_pass', 'system', f'阶段1通过，匹配度: {score}%')

        db.session.commit()

        return jsonify({
            'success': True,
            'score': score,
            'feedback': feedback,
            'passed': passed
        })

    except Exception as e:
        print(f"阶段1提交失败: {e}")
        traceback.print_exc()
        return jsonify({'error': f'提交失败: {str(e)}'}), 500


@thinking.route('/api/stage1/hint', methods=['POST'])
@login_required
def stage1_hint():
    """阶段1请求AI提示"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        description = data.get('description', '')

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)
        key_steps = preset.get_key_steps() if preset else []

        hint = generate_stage1_hint(description, key_steps, assignment.title, ts.stage1_hint_count)

        # 更新提示计数
        ts.stage1_hint_count += 1
        _log_event(session_id, 1, 'hint_request', 'student', description,
                   metadata={'hint': hint, 'hint_count': ts.stage1_hint_count})

        db.session.commit()

        return jsonify({
            'success': True,
            'hint': hint,
            'hint_count': ts.stage1_hint_count
        })

    except Exception as e:
        print(f"阶段1提示失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: 阶段2 — 积木编程
# ============================================================

@thinking.route('/api/stage2/verify', methods=['POST'])
@login_required
def stage2_verify():
    """验证积木拼装结果"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        block_order = data.get('block_order', [])  # [{id, indent}]

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        correct_blocks = preset.get_code_blocks() if preset else []

        # 严格匹配：ID顺序和缩进层级都要完全一致
        student_ids = [str(b.get('id', '')) for b in block_order]
        student_indents = [b.get('indent', 0) for b in block_order]
        
        correct_ids = [str(b.get('id', '')) for b in correct_blocks]
        correct_indents = [b.get('indent', 0) for b in correct_blocks]

        id_match = student_ids == correct_ids
        indent_match = student_indents == correct_indents
        passed = id_match and indent_match

        # 更新会话
        ts.stage2_block_order = json.dumps(block_order, ensure_ascii=False)

        if passed:
            ts.stage2_completed = True
            ts.current_stage = 3
            _log_event(session_id, 2, 'stage_pass', 'system', '积木编程验证通过')
        else:
            # 提供模糊反馈（不透露具体哪里错了）
            _log_event(session_id, 2, 'verify_fail', 'system', '验证未通过',
                       metadata={'student_order': student_ids})

        db.session.commit()

        feedback = ''
        if not passed:
            if not id_match:
                feedback = '代码块的顺序还不太对，试着回忆一下你的解题思路，从头到尾应该是怎样的流程？'
            elif not indent_match:
                feedback = '代码块顺序正确了！但部分代码的缩进层级需要调整，想想哪些代码应该嵌套在其他代码里面？'

        return jsonify({
            'success': True,
            'passed': passed,
            'feedback': feedback
        })

    except Exception as e:
        print(f"阶段2验证失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/stage2/hint', methods=['POST'])
@login_required
def stage2_hint():
    """阶段2请求AI提示"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        current_block_ids = data.get('current_blocks', [])

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)

        hint = generate_stage2_hint(
            ts.stage1_description or '',
            current_block_ids,
            preset.get_code_blocks() if preset else [],
            assignment.title,
            ts.stage2_hint_count
        )

        ts.stage2_hint_count += 1
        _log_event(session_id, 2, 'hint_request', 'student', json.dumps(current_block_ids),
                   metadata={'hint': hint})

        db.session.commit()

        return jsonify({
            'success': True,
            'hint': hint,
            'hint_count': ts.stage2_hint_count
        })

    except Exception as e:
        print(f"阶段2提示失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/companion/chat', methods=['POST'])
@login_required
def companion_chat():
    """伴学自由对话"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        messages = data.get('messages', [])

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)

        current_stage = data.get('current_stage', 1)
        stage2_state = data.get('stage2_state', {})

        response_text = companion_agent_chat(
            messages,
            assignment.title,
            preset.get_key_steps() if preset else [],
            ts.stage1_description or '',
            current_stage=current_stage,
            stage2_state=stage2_state,
            assignment_description=assignment.description or ""
        )

        # 记录日志
        if messages:
            last_user_msg = messages[-1].get('content', '')
            _log_event(session_id, ts.current_stage, 'companion_chat', 'student', last_user_msg)
        _log_event(session_id, ts.current_stage, 'companion_chat', 'companion_agent', response_text)

        db.session.commit()

        return jsonify({
            'success': True,
            'response': response_text
        })

    except Exception as e:
        print(f"伴学对话失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: 阶段3 — 费曼教学
# ============================================================

@thinking.route('/api/stage3/chat', methods=['POST'])
@login_required
def stage3_teacher_chat():
    """费曼阶段 — 老师Agent对话"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        messages = data.get('messages', [])

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)

        response_text = teacher_agent_chat(
            messages,
            assignment.title,
            preset.get_key_steps() if preset else [],
            ts.stage1_description or '',
            assignment_description=assignment.description or ""
        )

        # 记录日志
        if messages:
            last_user_msg = messages[-1].get('content', '')
            _log_event(session_id, 3, 'chat', 'student', last_user_msg, metadata={'panel': 'teacher'})
        _log_event(session_id, 3, 'chat', 'teacher_agent', response_text)

        ts.stage3_teacher_rounds += 1
        db.session.commit()

        return jsonify({
            'success': True,
            'response': response_text
        })

    except Exception as e:
        print(f"老师Agent对话失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/stage3/teach', methods=['POST'])
@login_required
def stage3_student_teach():
    """费曼阶段 — 教坏学生对话"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        messages = data.get('messages', [])

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)
        difficulty = preset.get_difficulty_config() if preset else {}

        # 验证学生发给小明的解答质量（防止刷屏/复读绕过）
        if messages:
            current_msg = messages[-1].get('content', '').strip()
            cleaned_current = "".join(current_msg.split())
            
            # 1. 极简文本拦截（少于5个字符）
            if len(cleaned_current) < 5:
                response_text = "呃，你说的这也太简短了（需要5字以上），我感觉完全听不明白。能稍微详细一点解释吗？"
                return jsonify({
                    'success': True,
                    'response': response_text,
                    'ready_for_code': False
                })
            
            # 从数据库中查询该会话已记录的有效学生发言历史，进行相似度校验
            # （即使学生刷新页面或者篡改前端 payload，数据库记录也是无法绕过的）
            prev_logs = ThinkingStageLog.query.filter_by(
                session_id=session_id,
                stage=3,
                role='student',
                event_type='chat'
            ).all()
            
            prev_student_teach_msgs = []
            for log in prev_logs:
                meta = log.get_metadata() or {}
                if meta.get('panel') == 'student_agent':
                    prev_student_teach_msgs.append(log.content.strip())
            
            # 2. 复读机/高相似度文本拦截（与历史发送的消息相似度大于 0.8）
            is_repetitive = False
            import difflib
            for prev_msg in prev_student_teach_msgs:
                s1 = "".join(prev_msg.split()).lower()
                s2 = "".join(current_msg.split()).lower()
                if difflib.SequenceMatcher(None, s1, s2).ratio() > 0.8:
                    is_repetitive = True
                    break
            
            if is_repetitive:
                response_text = "咦，这句话你刚才已经解释过一遍了呀！能不能换个思路，或者用别的话跟我说一下？"
                return jsonify({
                    'success': True,
                    'response': response_text,
                    'ready_for_code': False
                })

        response_text = student_agent_chat(
            messages,
            assignment.title,
            preset.get_key_steps() if preset else [],
            difficulty,
            round_number=ts.stage3_student_rounds,
            assignment_description=assignment.description or ""
        )

        # 记录日志
        if messages:
            last_user_msg = messages[-1].get('content', '')
            _log_event(session_id, 3, 'chat', 'student', last_user_msg, metadata={'panel': 'student_agent'})
        _log_event(session_id, 3, 'chat', 'student_agent', response_text)

        ts.stage3_student_rounds += 1

        # 判断是否进入"写代码"阶段（达到目标轮次后触发）
        target_rounds = difficulty.get('feynman_rounds', 5)
        ready_for_code = ts.stage3_student_rounds >= target_rounds

        db.session.commit()

        return jsonify({
            'success': True,
            'response': response_text,
            'ready_for_code': ready_for_code
        })

    except Exception as e:
        print(f"坏学生Agent对话失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/stage3/write_code', methods=['POST'])
@login_required
def stage3_write_code():
    """费曼阶段 — 坏学生尝试写代码（带陷阱）"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        messages = data.get('messages', [])

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        assignment = Assignment.query.get(ts.assignment_id)

        code_result = student_agent_write_code(
            assignment.title,
            preset.get_key_steps() if preset else [],
            preset.reference_code or '',
            messages
        )

        _log_event(session_id, 3, 'write_code', 'student_agent', code_result.get('message', ''),
                   metadata={'buggy_code': code_result.get('buggy_code', ''),
                             'bugs_count': len(code_result.get('bugs', []))})

        db.session.commit()

        return jsonify({
            'success': True,
            'buggy_code': code_result.get('buggy_code', ''),
            'message': code_result.get('message', '我写了一份代码，你帮我看看？')
        })

    except Exception as e:
        print(f"坏学生写代码失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/stage3/fix_code', methods=['POST'])
@login_required
def stage3_fix_code():
    """费曼阶段 — 学生帮坏学生修复代码"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        buggy_code = data.get('buggy_code', '')
        fixed_code = data.get('fixed_code', '')  # 修改后的代码或自然语言描述

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()

        # 获取之前生成的bug列表
        last_code_log = ThinkingStageLog.query.filter_by(
            session_id=session_id, event_type='write_code'
        ).order_by(ThinkingStageLog.created_at.desc()).first()
        bugs = last_code_log.get_metadata().get('bugs', []) if last_code_log else []

        is_correct, feedback = evaluate_feynman_code_fix(
            buggy_code, fixed_code, bugs, preset.reference_code or ''
        )

        _log_event(session_id, 3, 'fix_code', 'student', fixed_code,
                   metadata={'is_correct': is_correct, 'feedback': feedback})

        if is_correct:
            ts.stage3_completed = True
            ts.status = 'completed'
            ts.completed_at = dt.utcnow()
            _log_event(session_id, 3, 'stage_pass', 'system', f'费曼教学完成: {feedback}')

        db.session.commit()

        return jsonify({
            'success': True,
            'correct': is_correct,
            'feedback': feedback
        })

    except Exception as e:
        print(f"修复代码评估失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/complete_session', methods=['POST'])
@login_required
def complete_session():
    """手动标记完成（用于阶段3判定通过后）"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        total_time = data.get('total_time_seconds', 0)

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        ts.total_time_seconds = total_time
        if ts.status != 'completed':
            ts.status = 'completed'
            ts.completed_at = dt.utcnow()

        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: 预设生成（内部调用）
# ============================================================

@thinking.route('/api/generate_preset', methods=['POST'])
@login_required
def api_generate_preset():
    """手动触发预设生成（用于测试或老师手动触发）"""
    try:
        data = request.get_json()
        assignment_id = data.get('assignment_id')
        reference_code = data.get('reference_code', '')

        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'error': '作业不存在'}), 404

        # 检查是否已有预设
        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
        if not preset:
            preset = AssignmentThinkingPreset(assignment_id=assignment_id)
            db.session.add(preset)

        preset.status = 'generating'
        db.session.commit()

        try:
            result = generate_preset(
                assignment.title,
                assignment.description or ''
            )

            preset.reference_code = result.get('reference_code', '')
            preset.key_steps = json.dumps(result.get('key_steps', []), ensure_ascii=False)
            preset.code_blocks = json.dumps(result.get('code_blocks', []), ensure_ascii=False)
            preset.noise_blocks = json.dumps(result.get('noise_blocks', []), ensure_ascii=False)
            preset.difficulty_config = json.dumps(result.get('difficulty_config', {}), ensure_ascii=False)
            preset.status = 'ready'
            preset.error_message = None

        except Exception as gen_err:
            preset.status = 'failed'
            preset.error_message = str(gen_err)
            print(f"预设生成失败: {gen_err}")
            traceback.print_exc()

        db.session.commit()

        return jsonify({
            'success': preset.status == 'ready',
            'status': preset.status,
            'error': preset.error_message
        })

    except Exception as e:
        print(f"生成预设API失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/preset_status/<int:assignment_id>', methods=['GET'])
@login_required
def preset_status(assignment_id):
    """轮询预设状态"""
    try:
        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
        if not preset:
            return jsonify({'status': 'not_found'})
        return jsonify({
            'status': preset.status,
            'error': preset.error_message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/retry_preset/<int:assignment_id>', methods=['POST'])
@login_required
def retry_preset(assignment_id):
    """重新尝试生成预设（异步）"""
    try:
        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
        if not preset:
            preset = AssignmentThinkingPreset(assignment_id=assignment_id)
            db.session.add(preset)
            
        preset.status = 'generating'
        preset.updated_at = dt.utcnow()
        preset.error_message = None
        db.session.commit()
        
        from utils.async_tasks import add_generate_preset_task
        add_generate_preset_task(assignment_id)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# API: 老师查看学习日志
# ============================================================

@thinking.route('/api/session/<int:session_id>/log')
@login_required
def get_session_log(session_id):
    """获取学习会话日志（老师/管理员用）"""
    try:
        ts = ThinkingSession.query.get_or_404(session_id)

        # 权限检查：管理员、老师、或学生本人可查看
        if not (current_user.is_admin or current_user.is_teacher or
                current_user.student_id == ts.student_id):
            return jsonify({'error': '无权查看'}), 403

        logs = ThinkingStageLog.query.filter_by(session_id=session_id)\
            .order_by(ThinkingStageLog.created_at.asc()).all()

        return jsonify({
            'success': True,
            'session': ts.to_summary_dict(),
            'logs': [{
                'id': log.id,
                'stage': log.stage,
                'event_type': log.event_type,
                'role': log.role,
                'content': log.content,
                'metadata': log.get_metadata(),
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
            } for log in logs]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@thinking.route('/api/assignment/<int:assignment_id>/sessions')
@login_required
def get_assignment_sessions(assignment_id):
    """获取某作业的所有学习会话（老师用）"""
    if not (current_user.is_admin or current_user.is_teacher):
        return jsonify({'error': '无权查看'}), 403

    sessions = ThinkingSession.query.filter_by(assignment_id=assignment_id)\
        .order_by(ThinkingSession.started_at.desc()).all()

    return jsonify({
        'success': True,
        'sessions': [s.to_summary_dict() for s in sessions]
    })


# ============================================================
# 辅助函数
# ============================================================

def _log_event(session_id: int, stage: int, event_type: str,
               role: str, content: str, metadata: dict = None):
    """记录交互日志"""
    log = ThinkingStageLog(
        session_id=session_id,
        stage=stage,
        event_type=event_type,
        role=role,
        content=content,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None
    )
    db.session.add(log)


def _serialize_preset(preset: AssignmentThinkingPreset) -> dict:
    """序列化预设数据（供前端使用，不暴露标准答案）"""
    if not preset:
        return {}

    import random
    code_blocks = preset.get_code_blocks()
    noise_blocks = preset.get_noise_blocks()

    # 合并并打乱代码块（不暴露哪些是噪声块）
    all_blocks = []
    for block in code_blocks:
        all_blocks.append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1)
        })
    for block in noise_blocks:
        all_blocks.append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1)
        })

    random.shuffle(all_blocks)

    return {
        'key_steps': preset.get_key_steps(),
        'blocks': all_blocks,
        'difficulty': preset.get_difficulty_config(),
        'status': preset.status
    }
