"""
三阶段引导式学习系统 — 路由模块
Blueprint: thinking, URL前缀: /thinking
"""
import json
import traceback
import uuid
from datetime import datetime as dt

from flask import Blueprint, render_template, request, jsonify, session, Response, current_app
from flask_login import current_user

from models import (db, Assignment, AssignmentThinkingPreset,
                    ThinkingSession, ThinkingStageLog)
from utils.auth import login_required
from utils.thinking_ai import (
    generate_preset, evaluate_description, generate_stage1_hint,
    generate_stage2_hint, companion_agent_chat, sanitize_response
)
from utils.agents.contracts import AgentRole
from utils.agents.feynman import build_feynman_runtime
from utils.agents.memory import MemoryStore, SqlAlchemyEventStore

thinking = Blueprint('thinking', __name__, url_prefix='/thinking')


def _extract_stage3_message(data: dict) -> str:
    message = (data.get('message') or '').strip()
    if message:
        return message
    for item in reversed(data.get('messages') or []):
        if isinstance(item, dict) and item.get('role') == 'user':
            return str(item.get('content') or '').strip()
    return ''


def _request_id(data: dict) -> str:
    value = str(data.get('request_id') or '').strip()
    return value[:80] if value else uuid.uuid4().hex


def _stage3_runtime(data: dict):
    thinking_session = ThinkingSession.query.get(data.get('session_id'))
    if not thinking_session or thinking_session.student_id != current_user.student_id:
        return None, None
    assignment = Assignment.query.get(thinking_session.assignment_id)
    preset = AssignmentThinkingPreset.query.filter_by(assignment_id=thinking_session.assignment_id).first()
    if not assignment or not preset:
        return thinking_session, None
    return thinking_session, build_feynman_runtime(thinking_session, assignment, preset)


def _stage3_request_result(session_id: int, request_id: str):
    return MemoryStore(SqlAlchemyEventStore()).find_request_result(session_id, request_id)


def _runtime_role_by_request(logs):
    roles = {}
    for log in logs:
        if log.event_type != 'agent_message' or log.role not in ('teacher_agent', 'student_agent'):
            continue
        request_id = (log.get_metadata() or {}).get('request_id')
        if request_id:
            roles[str(request_id)] = log.role
    return roles


def _public_code_review(log):
    metadata = log.get_metadata() or {}
    result_payload = metadata.get('agent_result') or {}
    public_content = metadata.get('public_content') or (
        result_payload.get('public_content') if isinstance(result_payload, dict) else {}
    ) or {}
    if not isinstance(public_content, dict):
        return None
    tool_call = metadata.get('tool_call') or {}
    generated_by_tool = log.event_type == 'tool_result' and (
        not tool_call or (isinstance(tool_call, dict) and tool_call.get('name') == 'generate_buggy_attempt')
    )
    generated_by_result = log.event_type == 'agent_message' and log.role == 'student_agent'
    buggy_code = public_content.get('buggy_code')
    if not (generated_by_tool or generated_by_result) or not isinstance(buggy_code, str):
        return None
    return {
        'request_id': str(metadata.get('request_id') or ''),
        'buggy_code': buggy_code,
        'message': str(public_content.get('message') or log.content or ''),
    }


def _check_and_trigger_stale_preset(preset, assignment_id):
    """
    检查预设是否是老版本（状态为 ready 但没有 quiz_steps），如果是，则自动触发重新生成。
    """
    if preset and preset.status == 'ready' and (not hasattr(preset, 'quiz_steps') or not preset.quiz_steps or preset.quiz_steps.strip() == '' or preset.quiz_steps == '[]'):
        try:
            preset.status = 'generating'
            preset.error_message = None
            db.session.commit()
            
            from utils.async_tasks import add_generate_preset_task
            add_generate_preset_task(assignment_id)
            
            current_app.logger.info(f"作业 {assignment_id} 预设缺少 quiz_steps 数据，已将其重置为 'generating' 并触发重新生成。")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"重置作业 {assignment_id} 预设状态失败: {e}")
    return preset


# ============================================================
# 页面路由
# ============================================================

@thinking.route('/<int:assignment_id>')
@login_required
def arena(assignment_id):
    """三阶段学习主页面"""
    assignment = Assignment.query.get_or_404(assignment_id)
    preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
    
    # 自动检测并重置缺少 quiz_steps 的就绪预设
    preset = _check_and_trigger_stale_preset(preset, assignment_id)

    preset_status = 'not_found'
    
    if not preset:
        try:
            preset = AssignmentThinkingPreset(assignment_id=assignment_id, status='generating')
            db.session.add(preset)
            db.session.commit()
            
            # 异步触发预设生成
            from utils.async_tasks import add_generate_preset_task
            add_generate_preset_task(assignment_id)
            
            preset_status = 'generating'
            current_app.logger.info(f"作业 {assignment_id} 预设不存在，已成功触发后台异步生成任务。")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"为作业 {assignment_id} 触发异步预设任务失败: {e}")
            preset_status = 'failed'
    elif preset.status != 'ready':
        if preset.status == 'failed':
            # 如果先前失败，当用户进入页面时自动重新触发异步生成
            try:
                preset.status = 'generating'
                preset.error_message = None
                db.session.commit()
                
                from utils.async_tasks import add_generate_preset_task
                add_generate_preset_task(assignment_id)
                
                preset_status = 'generating'
                current_app.logger.info(f"作业 {assignment_id} 预设先前失败，已重新触发后台异步生成任务。")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"为作业 {assignment_id} 重新触发异步预设任务失败: {e}")
                preset_status = 'failed'
        else:
            # 如果处于 'generating' 状态已超过 5 分钟，大概率是任务悬空，在此处自动重试触发
            if preset.status == 'generating' and preset.updated_at:
                delta = (dt.utcnow() - preset.updated_at).total_seconds()
                if delta > 300:
                    try:
                        preset.status = 'generating'
                        preset.updated_at = dt.utcnow()
                        preset.error_message = None
                        db.session.commit()
                        
                        from utils.async_tasks import add_generate_preset_task
                        add_generate_preset_task(assignment_id)
                        current_app.logger.warning(f"作业 {assignment_id} 预设处于 'generating' 状态已超 5 分钟，判断为悬空，已自动重载任务")
                    except Exception as e:
                        db.session.rollback()
                        current_app.logger.error(f"为作业 {assignment_id} 自动重载悬空预设任务失败: {e}")
            preset_status = preset.status
    else:
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
        preset = _check_and_trigger_stale_preset(preset, assignment_id)
        if not preset or preset.status != 'ready':
            return jsonify({'error': '学习数据尚未准备好，请稍后再试', 'preset_status': preset.status if preset else 'not_found'}), 503

        # 查找现有进行中的会话
        existing = ThinkingSession.query.filter_by(
            student_id=current_user.student_id,
            assignment_id=assignment_id,
            status='in_progress'
        ).first()

        if existing:
            # 计算已过秒数
            elapsed_seconds = int((dt.utcnow() - existing.started_at).total_seconds())
            
            # 加载伴学历史 (全部阶段)
            companion_logs = ThinkingStageLog.query.filter_by(
                session_id=existing.id,
                event_type='companion_chat'
            ).order_by(ThinkingStageLog.created_at.asc()).all()
            companion_history = [{
                'role': log.role,
                'content': log.content
            } for log in companion_logs]

            # 加载阶段3历史
            stage3_logs = ThinkingStageLog.query.filter_by(
                session_id=existing.id,
                stage=3
            ).order_by(ThinkingStageLog.created_at.asc()).all()

            teacher_history = []
            student_history = []
            buggy_code_info = None
            runtime_roles = _runtime_role_by_request(stage3_logs)
            restored_code_requests = set()
            unattributed_runtime_users = []

            for log in stage3_logs:
                if log.event_type == 'chat':
                    meta = log.get_metadata() or {}
                    if log.role == 'teacher_agent' or (log.role == 'student' and meta.get('panel') == 'teacher_agent'):
                        teacher_history.append({
                            'role': 'user' if log.role == 'student' else 'assistant',
                            'content': log.content
                        })
                    elif log.role == 'student_agent' or (log.role == 'student' and meta.get('panel') == 'student_agent'):
                        student_history.append({
                            'role': 'user' if log.role == 'student' else 'assistant',
                            'content': log.content
                        })
                elif log.event_type == 'write_code':
                    meta = log.get_metadata() or {}
                    buggy_code_info = {'buggy_code': meta.get('buggy_code', ''), 'message': log.content}
                    student_history.append({'role': 'assistant', 'content': log.content})
                elif log.event_type == 'agent_user_message':
                    role = runtime_roles.get(str((log.get_metadata() or {}).get('request_id') or ''))
                    message = {'role': 'user', 'content': log.content}
                    if role == 'teacher_agent':
                        teacher_history.append(message)
                    elif role == 'student_agent':
                        student_history.append(message)
                    else:
                        unattributed_runtime_users.append(message)
                elif log.event_type == 'agent_message':
                    code_review = _public_code_review(log)
                    if code_review and code_review['request_id'] not in restored_code_requests:
                        restored_code_requests.add(code_review['request_id'])
                        buggy_code_info = {'buggy_code': code_review['buggy_code'], 'message': code_review['message']}
                        student_history.append({'role': 'assistant', 'content': code_review['message']})
                        continue
                    message = {'role': 'assistant', 'content': log.content}
                    if log.role == 'teacher_agent':
                        teacher_history.extend(unattributed_runtime_users)
                        unattributed_runtime_users = []
                        teacher_history.append(message)
                    elif log.role == 'student_agent':
                        student_history.extend(unattributed_runtime_users)
                        unattributed_runtime_users = []
                        student_history.append(message)
                elif log.event_type == 'tool_result':
                    code_review = _public_code_review(log)
                    if code_review:
                        restored_code_requests.add(code_review['request_id'])
                        buggy_code_info = {'buggy_code': code_review['buggy_code'], 'message': code_review['message']}
                        student_history.append({'role': 'assistant', 'content': code_review['message']})
                elif log.event_type == 'fix_code':
                    student_history.append({
                        'role': 'user',
                        'content': f"【提交代码修复】\n{log.content}"
                    })

            # 解析块顺序
            stage2_block_order = None
            if existing.stage2_block_order:
                try:
                    stage2_block_order = json.loads(existing.stage2_block_order)
                except Exception:
                    pass

            return jsonify({
                'success': True,
                'session_id': existing.id,
                'current_stage': existing.current_stage,
                'resumed': True,
                'elapsed_seconds': elapsed_seconds,
                'stage1_description': existing.stage1_description,
                'stage1_score': existing.stage1_score,
                'stage2_block_order': stage2_block_order,
                'companion_history': companion_history,
                'teacher_history': teacher_history,
                'student_history': student_history,
                'buggy_code_info': buggy_code_info,
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

        passed = score >= 50
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
        db.session.rollback()
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
    """验证选择与填空答题结果"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        quiz_answers = data.get('quiz_answers', {})

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        preset = AssignmentThinkingPreset.query.filter_by(assignment_id=ts.assignment_id).first()
        quiz_steps = preset.get_quiz_steps() if preset else []

        passed = True
        wrong_steps = []
        
        import re
        def normalize(code):
            if not code:
                return ''
            s = ' '.join(str(code).split()).strip()
            regex = r'\s*([+*/%=<>!&|^~?:,;\(\)\[\]\{\}-])\s*'
            s = re.sub(regex, r'\1', s)
            return s

        from utils.thinking_ai import check_quiz_equivalence

        wrong_step_explanations = {}

        for step in quiz_steps:
            step_id = str(step.get('step_id', ''))
            correct_raw = step.get('correct_answer', '')
            student_raw = quiz_answers.get(step_id, '')

            # 1. 快速空格归一化字符比对
            if normalize(student_raw) == normalize(correct_raw):
                continue

            # 2. 如果不匹配，使用大模型进行语义/逻辑等价性检查
            equiv_check = check_quiz_equivalence(
                student_answer=student_raw,
                correct_answer=correct_raw,
                question=step.get('question', ''),
                reference_code=preset.reference_code or ''
            )

            if equiv_check.get('equivalent'):
                # 语义等价，视为正确！
                continue
            else:
                passed = False
                wrong_steps.append(step_id)
                wrong_step_explanations[step_id] = equiv_check.get('reason') or step.get('explanation', '请再想想')

        # 更新会话答题进度
        ts.stage2_block_order = json.dumps(quiz_answers, ensure_ascii=False)

        if passed:
            ts.stage2_completed = True
            ts.current_stage = 3
            _log_event(session_id, 2, 'stage_pass', 'system', '逐步构建程序验证通过')
        else:
            _log_event(session_id, 2, 'verify_fail', 'system', '验证未通过',
                       metadata={'wrong_steps': wrong_steps, 'wrong_step_explanations': wrong_step_explanations})

        db.session.commit()

        feedback = ''
        if not passed:
            feedback = f'还有 {len(wrong_steps)} 道步骤的答案不正确，请根据提示进行调整。'

        return jsonify({
            'success': True,
            'passed': passed,
            'wrong_steps': wrong_steps,
            'feedback_details': wrong_step_explanations,
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
        student_state = data.get('student_state', {})
        if not stage2_state and 'stage2' in student_state:
            stage2_state = student_state.get('stage2', {})

        response_text = companion_agent_chat(
            messages,
            assignment.title,
            preset.get_key_steps() if preset else [],
            ts.stage1_description or '',
            current_stage=current_stage,
            stage2_state=stage2_state,
            assignment_description=assignment.description or "",
            student_state=student_state
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


@thinking.route('/api/stt/optimize', methods=['POST'])
@login_required
def stt_optimize():
    """使用大模型智能优化语音识别文本（修正错别字并自动添加中文标点）"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'success': True, 'optimized_text': ''})
            
        from services.llm_client import SharedLLMClient
        client = SharedLLMClient()
        if not client.is_available():
            return jsonify({'success': True, 'optimized_text': text})
            
        system_prompt = """你是一个语音转文字（STT）优化助手。
你的任务是将一段可能有语音识别错误（如同音字错误、中英混杂标点缺失、没有断句）的粗糙口语文本，整理为通顺、排版正确、带合适中文标点的自然文本。

优化规则：
1. 【仅修正语音识别错误和错别字】：例如将 "大小安" 修正为 "大小n"，"目标之K" 修正为 "目标值k"，"在输入" 修正为 "再输入"，"最后输出目标时" 修正为 "最后输出目标值"。
2. 【补充缺失的标点】：合理添加逗号（，）、句号（。）、顿号（、）、问号（？）等中文标点。
3. 【保持原意和口语化语气】：绝对不要重写、扩写或改变用户的原意和口语叙述节奏。只做最小程度的纠错和标点补充。
4. 【直接输出结果】：只返回优化后的文本，不要输出任何解释或多余的文字。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请优化以下语音识别文本：\n{text}"}
        ]
        
        optimized_text = client.chat(messages, temperature=0.2, max_tokens=300)
        if optimized_text:
            optimized_text = optimized_text.strip()
            # 移除可能的多余包围引号
            if optimized_text.startswith('"') and optimized_text.endswith('"'):
                optimized_text = optimized_text[1:-1]
            elif optimized_text.startswith('“') and optimized_text.endswith('”'):
                optimized_text = optimized_text[1:-1]
            return jsonify({'success': True, 'optimized_text': optimized_text})
        else:
            return jsonify({'success': True, 'optimized_text': text})
    except Exception as e:
        print(f"STT优化失败: {e}")
        return jsonify({'success': True, 'optimized_text': text})


@thinking.route('/api/stt/transcribe', methods=['POST'])
@login_required
def stt_transcribe():
    """接收上传的录音文件，调用大模型（Whisper 或 GLM-ASR-2512）识别为文本并自动润色纠错"""
    temp_path = None
    try:
        if 'file' not in request.files:
            return jsonify({'error': '未包含音频文件'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '文件名为空'}), 400
            
        import uuid
        import os
        
        # 确保临时上传目录存在
        upload_dir = os.path.join(current_app.root_path, 'uploads', 'audio')
        os.makedirs(upload_dir, exist_ok=True)
        
        # 保存为临时文件
        ext = os.path.splitext(file.filename)[1] or '.webm'
        filename = f"{uuid.uuid4()}{ext}"
        temp_path = os.path.join(upload_dir, filename)
        file.save(temp_path)
        
        from services.llm_client import SharedLLMClient
        client = SharedLLMClient()
        if not client.is_available():
            return jsonify({'error': '大模型客户端不可用'}), 503
            
        provider = client.provider
        raw_text = ""
        
        # 1. 音频转文字 (ASR)
        with open(temp_path, 'rb') as audio_file:
            if provider == 'openai':
                response = client._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                raw_text = getattr(response, 'text', '') or getattr(response, 'transcript', '') or str(response)
            elif provider == 'zhipu':
                response = client._client.audio.transcriptions.create(
                    model="glm-asr-2512",
                    file=audio_file
                )
                raw_text = getattr(response, 'text', '') or getattr(response, 'transcript', '') or str(response)
                
        raw_text = raw_text.strip()
        if not raw_text:
            return jsonify({'success': True, 'text': ''})
            
        # 2. 润色纠错
        system_prompt = """你是一个语音转文字（STT）优化助手。
你的任务是将一段可能有语音识别错误（如同音字错误、中英混杂标点缺失、没有断句）的粗糙口语文本，整理为通顺、排版正确、带合适中文标点的自然文本。

优化规则：
1. 【仅修正语音识别错误和错别字】：例如将 "大小安" 修正为 "大小n"，"目标之K" 修正为 "目标值k"，"在输入" 修正为 "再输入"，"最后输出目标时" 修正为 "最后输出目标值"。
2. 【补充缺失的标点】：合理添加逗号（，）、句号（。）、顿号（、）、问号（？）等中文标点。
3. 【保持原意和口语化语气】：绝对不要重写、扩写或改变用户的原意和口语叙述节奏。只做最小程度 of 纠错和标点补充。
4. 【直接输出结果】：只返回优化后的文本，不要输出任何解释或多余的文字。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请优化以下语音识别文本：\n{raw_text}"}
        ]
        
        optimized_text = client.chat(messages, temperature=0.2, max_tokens=300)
        if optimized_text:
            optimized_text = optimized_text.strip()
            if optimized_text.startswith('"') and optimized_text.endswith('"'):
                optimized_text = optimized_text[1:-1]
            elif optimized_text.startswith('“') and optimized_text.endswith('”'):
                optimized_text = optimized_text[1:-1]
            return jsonify({'success': True, 'text': optimized_text})
            
        return jsonify({'success': True, 'text': raw_text})
        
    except Exception as e:
        print(f"音频识别失败: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        # 清理临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ============================================================
# API: 阶段3 — 费曼教学
# ============================================================

@thinking.route('/api/stage3/chat', methods=['POST'])
@login_required
def stage3_teacher_chat():
    """费曼阶段 — 老师Agent对话"""
    try:
        data = request.get_json() or {}
        message = _extract_stage3_message(data)
        if not message:
            return jsonify({'error': '缺少消息'}), 400
        ts, runtime = _stage3_runtime(data)
        if not ts:
            return jsonify({'error': '会话不存在'}), 403
        if not runtime:
            return jsonify({'error': '学习数据尚未准备好'}), 503
        result = runtime.handle_chat(AgentRole.TEACHER_AGENT, message, request_id=_request_id(data))
        return jsonify(result.to_public_dict())
    except Exception:
        db.session.rollback()
        current_app.logger.exception('阶段3老师Agent对话失败')
        return jsonify({'error': '服务暂时不可用'}), 500


@thinking.route('/api/stage3/teach', methods=['POST'])
@login_required
def stage3_student_teach():
    """费曼阶段 — 教坏学生对话"""
    try:
        data = request.get_json() or {}
        message = _extract_stage3_message(data)
        if not message:
            return jsonify({'error': '缺少消息'}), 400
        ts, runtime = _stage3_runtime(data)
        if not ts:
            return jsonify({'error': '会话不存在'}), 403
        if not runtime:
            return jsonify({'error': '学习数据尚未准备好'}), 503

        # 验证学生发给小明的解答质量（防止刷屏/复读绕过）
        request_id = _request_id(data)
        completed = _stage3_request_result(ts.id, request_id)
        if completed is not None:
            return jsonify(completed.to_public_dict())
        cleaned_current = "".join(message.split())
        if len(cleaned_current) < 5:
            return jsonify({'success': True, 'response': '呃，你说的这也太简短了（需要5字以上），我感觉完全听不明白。能稍微详细一点解释吗？', 'ready_for_code': False})
        import difflib
        history_logs = ThinkingStageLog.query.filter_by(session_id=ts.id, stage=3).all()
        runtime_roles = _runtime_role_by_request(history_logs)
        for log in history_logs:
            if log.role != 'student':
                continue
            meta = log.get_metadata() or {}
            if meta.get('request_id') == request_id:
                continue
            is_runtime_student_message = (
                log.event_type == 'agent_user_message' and
                runtime_roles.get(str(meta.get('request_id') or '')) == 'student_agent'
            )
            is_legacy_student_message = log.event_type == 'chat' and meta.get('panel') == 'student_agent'
            if not (is_runtime_student_message or is_legacy_student_message):
                continue
            if difflib.SequenceMatcher(None, "".join(log.content.split()).lower(), cleaned_current.lower()).ratio() > 0.8:
                return jsonify({'success': True, 'response': '咦，这句话你刚才已经解释过一遍了呀！能不能换个思路，或者用别的话跟我说一下？', 'ready_for_code': False})
        result = runtime.handle_chat(AgentRole.STUDENT_AGENT, message, request_id=request_id)
        return jsonify(result.to_public_dict())
    except Exception:
        db.session.rollback()
        current_app.logger.exception('阶段3学生Agent对话失败')
        return jsonify({'error': '服务暂时不可用'}), 500


@thinking.route('/api/stage3/write_code', methods=['POST'])
@login_required
def stage3_write_code():
    """费曼阶段 — 坏学生尝试写代码（带陷阱）"""
    try:
        data = request.get_json() or {}
        ts, runtime = _stage3_runtime(data)
        if not ts:
            return jsonify({'error': '会话不存在'}), 403
        if not runtime:
            return jsonify({'error': '学习数据尚未准备好'}), 503
        result = runtime.generate_buggy_attempt(request_id=_request_id(data))
        return jsonify(result.to_public_dict())
    except Exception:
        db.session.rollback()
        current_app.logger.exception('阶段3代码生成失败')
        return jsonify({'error': '服务暂时不可用'}), 500


@thinking.route('/api/stage3/fix_code', methods=['POST'])
@login_required
def stage3_fix_code():
    """费曼阶段 — 学生帮坏学生修复代码"""
    try:
        data = request.get_json() or {}
        fixed_code = data.get('fixed_code', '')  # 修改后的代码或自然语言描述
        ts, runtime = _stage3_runtime(data)
        if not ts:
            return jsonify({'error': '会话不存在'}), 403
        if not runtime:
            return jsonify({'error': '学习数据尚未准备好'}), 503
        result = runtime.evaluate_fix(str(fixed_code or ''), request_id=_request_id(data))
        return jsonify(result.to_public_dict())
    except Exception:
        db.session.rollback()
        current_app.logger.exception('阶段3代码修复评估失败')
        return jsonify({'error': '服务暂时不可用'}), 500


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
            preset.quiz_steps = json.dumps(result.get('quiz_steps', []), ensure_ascii=False)
            preset.difficulty_config = json.dumps(result.get('difficulty_config', {}), ensure_ascii=False)
            preset.algorithm_summary = result.get('algorithm_summary', '')
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
        preset = _check_and_trigger_stale_preset(preset, assignment_id)
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

    # 合并并打乱代码块（不暴露哪些是噪声块），同时向后兼容旧前端代码，并注入 part_name 等字段
    all_blocks = []
    for block in code_blocks:
        all_blocks.append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1),
            'part_name': block.get('part_name', '核心程序'),
            'part_header': (block.get('part_header') or 'int main() {\n').replace('{{', '{').replace('}}', '}'),
            'part_footer': (block.get('part_footer') or '    return 0;\n}\n').replace('{{', '{').replace('}}', '}')
        })
    for block in noise_blocks:
        all_blocks.append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1),
            'part_name': block.get('part_name', '核心程序'),
            'part_header': (block.get('part_header') or 'int main() {\n').replace('{{', '{').replace('}}', '}'),
            'part_footer': (block.get('part_footer') or '    return 0;\n}\n').replace('{{', '{').replace('}}', '}')
        })

    random.shuffle(all_blocks)

    # 按照 Part 逻辑分组与单独打乱噪声块/打乱顺序
    parts_list = []
    parts_map = {}
    
    # 1. 搜集正确积木块并确定 Part 顺序
    for block in code_blocks:
        p_name = block.get('part_name') or '核心程序'
        p_header = (block.get('part_header') or 'int main() {\n').replace('{{', '{').replace('}}', '}')
        p_footer = (block.get('part_footer') or '    return 0;\n}\n').replace('{{', '{').replace('}}', '}')
        
        if p_name not in parts_map:
            p_data = {
                'part_name': p_name,
                'part_header': p_header,
                'part_footer': p_footer,
                'blocks': []
            }
            parts_map[p_name] = p_data
            parts_list.append(p_data)
            
        parts_map[p_name]['blocks'].append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1),
            'part_name': p_name,
            'part_header': p_header,
            'part_footer': p_footer
        })

    # 2. 将噪声干扰块归入对应 Part
    for block in noise_blocks:
        p_name = block.get('part_name') or '核心程序'
        p_header = (block.get('part_header') or 'int main() {\n').replace('{{', '{').replace('}}', '}')
        p_footer = (block.get('part_footer') or '    return 0;\n}\n').replace('{{', '{').replace('}}', '}')
        
        if p_name not in parts_map:
            # 如果噪声块的 part_name 在正确块中未定义，归入首个 Part
            if parts_list:
                p_name = parts_list[0]['part_name']
            else:
                p_data = {
                    'part_name': p_name,
                    'part_header': p_header,
                    'part_footer': p_footer,
                    'blocks': []
                }
                parts_map[p_name] = p_data
                parts_list.append(p_data)
                
        parts_map[p_name]['blocks'].append({
            'id': str(block.get('id', '')),
            'code': block.get('code', ''),
            'label': block.get('label', ''),
            'indent': block.get('indent', 0),
            'phase': block.get('phase', 1),
            'part_name': p_name,
            'part_header': p_header,
            'part_footer': p_footer
        })

    # 3. 独立对每个 Part 内部进行打乱，保证噪声和顺序在局部是随机的
    for part in parts_list:
        random.shuffle(part['blocks'])

    # 惰性回填：如果旧预设缺少 algorithm_summary，尝试后台异步生成，避免阻塞主请求
    algorithm_summary = preset.get_algorithm_summary()
    if not algorithm_summary and preset.status == 'ready' and preset.reference_code:
        import threading
        app = current_app._get_current_object()
        preset_id = preset.id
        
        def run_backfill():
            with app.app_context():
                try:
                    from models import AssignmentThinkingPreset
                    p = AssignmentThinkingPreset.query.get(preset_id)
                    if p:
                        _lazy_backfill_summary(p)
                except Exception as ex:
                    app.logger.warning(f"后台惰性回填算法简述失败: {ex}")
                    
        threading.Thread(target=run_backfill, daemon=True).start()

    difficulty = preset.get_difficulty_config() or {}
    guided_questions = difficulty.get('guided_questions', [])

    # 获取逐步选择/填空题数据
    quiz_steps = preset.get_quiz_steps()

    return {
        'key_steps': preset.get_key_steps(),
        'blocks': all_blocks,
        'parts': parts_list,
        'quiz_steps': quiz_steps,
        'difficulty': difficulty,
        'algorithm_summary': algorithm_summary,
        'guided_questions': guided_questions,
        'status': preset.status
    }


def _lazy_backfill_summary(preset: AssignmentThinkingPreset):
    """为缺少 algorithm_summary 的旧预设惰性生成算法简述"""
    from utils.thinking_ai import SharedLLMClient
    client = SharedLLMClient()
    if not client.is_available():
        return

    assignment = preset.assignment
    if not assignment:
        return

    prompt = f"""你是一位数据结构与算法课程的教师。请根据以下编程题目和标准答案代码，
用简洁的自然语言为学生编写一段"算法简述"。

要求：用2~4个编号步骤描述核心流程，使用自然语言，不要包含代码，100~250字。
直接输出"算法流程："开头的内容。

题目：{assignment.title}
描述：{(assignment.description or '')[:500]}

标准答案代码：
{preset.reference_code[:1500]}"""

    response = client.chat(
        [{"role": "system", "content": "你是数据结构课程教师，善于用简洁的自然语言总结算法流程。"},
         {"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=600
    )
    if response and response.strip():
        preset.algorithm_summary = response.strip()
        db.session.commit()
        current_app.logger.info(f"已为作业 {preset.assignment_id} 惰性回填算法简述")


@thinking.route('/api/debug/jump_stage', methods=['POST'])
@login_required
def debug_jump_stage():
    """开发者调试模式：快速跳过或跳转阶段"""
    # 限制仅在开发环境（本地运行或 Flask DEBUG 模式）允许访问
    is_local = request.host.startswith('localhost') or request.host.startswith('127.0.0.1')
    if not (current_app.debug or is_local):
        return jsonify({'error': '非开发环境，拒绝访问该调试接口'}), 403

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        target_stage = data.get('stage')

        ts = ThinkingSession.query.get(session_id)
        if not ts or ts.student_id != current_user.student_id:
            return jsonify({'error': '会话不存在'}), 403

        if target_stage == 1:
            ts.current_stage = 1
            ts.stage1_score = None
            ts.stage1_description = None
            ts.stage2_block_order = None
            ts.stage2_completed = False
            ts.stage3_completed = False
            ts.status = 'in_progress'
        elif target_stage == 2:
            ts.current_stage = 2
            ts.stage1_score = 100
            ts.stage1_description = "【开发者调试跳过阶段一】"
            ts.stage2_block_order = None
            ts.stage2_completed = False
            ts.stage3_completed = False
            ts.status = 'in_progress'
        elif target_stage == 3:
            ts.current_stage = 3
            ts.stage1_score = 100
            ts.stage1_description = "【开发者调试跳过阶段一】"
            ts.stage2_completed = True
            ts.stage3_completed = False
            ts.status = 'in_progress'
        elif target_stage == 4:  # Completed
            ts.current_stage = 3
            ts.stage1_score = 100
            ts.stage1_description = "【开发者调试跳过阶段一】"
            ts.stage2_completed = True
            ts.stage3_completed = True
            ts.status = 'completed'
            ts.completed_at = dt.utcnow()

        db.session.commit()
        return jsonify({'success': True, 'current_stage': ts.current_stage, 'status': ts.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
