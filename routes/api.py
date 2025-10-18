"""
API路由模块
提供REST API接口
"""
from flask import Blueprint, request, jsonify, session, render_template
from sqlalchemy import desc
from models import db, User, Assignment, Submission, AbilityTrend
from utils.auth import login_required, admin_required
from utils.api import api_response, error_response, user_to_dict, assignment_to_dict, submission_to_dict
from utils.code_evaluator import evaluate_cpp_code, analyze_code_quality
from utils.guidance_generator import generate_guidance, generate_answer_to_question  # 导入指导生成函数和答案生成函数
from utils.code_advisor import generate_code_advice, initialize_code_advisor  # 导入新的代码建议系统
import markdown
import traceback
import os
from datetime import datetime

api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/docs')
def api_docs():
    """API文档页面"""
    return render_template('api_docs.html')


@api.route('/assignments', methods=['GET'])
def get_assignments():
    """获取所有作业列表"""
    try:
        assignments = Assignment.query.all()
        return api_response(
            success=True,
            message="获取作业列表成功",
            data={
                'assignments': [assignment_to_dict(a) for a in assignments]
            }
        )
    except Exception as e:
        return error_response(f"获取作业列表失败: {str(e)}", 500)


@api.route('/assignments/<int:assignment_id>', methods=['GET'])
def get_assignment(assignment_id):
    """获取指定作业详情"""
    try:
        assignment = Assignment.query.get_or_404(assignment_id)
        return api_response(
            success=True,
            message="获取作业详情成功",
            data={
                'assignment': assignment_to_dict(assignment)
            }
        )
    except Exception as e:
        return error_response(f"获取作业详情失败: {str(e)}", 500)


@api.route('/submissions/<string:student_id>', methods=['GET'])
@login_required
def get_student_submissions(student_id):
    """获取学生的提交记录"""
    # 检查权限：只允许管理员或本人查看
    if session.get('usertype') != '管理员' and session.get('student_id') != student_id:
        return error_response("无权访问此学生的提交记录", 403)
        
    try:
        submissions = Submission.query.filter_by(student_id=student_id).order_by(desc(Submission.submitted_at)).all()
        return api_response(
            success=True,
            message="获取提交记录成功",
            data={
                'submissions': [submission_to_dict(s) for s in submissions]
            }
        )
    except Exception as e:
        return error_response(f"获取提交记录失败: {str(e)}", 500)


# 代码块增强辅助函数
def enhance_code_blocks(markdown_text, default_lang='cpp'):
    """增强Markdown中的代码块，确保语言标记正确"""
    import re
    
    # 如果输入为空，直接返回
    if not markdown_text:
        return markdown_text
    
    # 首先，统一换行符格式
    markdown_text = markdown_text.replace('\r\n', '\n')
    
    # 确保标题格式正确（#后有空格）
    markdown_text = re.sub(r'(^|\n)(#{1,6})([^#\s])', r'\1\2 \3', markdown_text)
    
    # 确保标题前后有空行，提高解析准确性
    markdown_text = re.sub(r'([^\n])(#{1,6}\s)', r'\1\n\n\2', markdown_text)
    markdown_text = re.sub(r'(#{1,6}[^\n]+)([^\n])', r'\1\n\n\2', markdown_text)
    
    # 1. 处理已有的Markdown代码块
    # 查找所有代码块
    pattern = r'```(.*?)\n(.*?)```'
    
    def replace_match(match):
        lang = match.group(1).strip()
        code = match.group(2)
        
        # 如果没有指定语言，添加默认语言
        if not lang:
            lang = default_lang
        
        # 如果代码块有语言但没有语法高亮格式，规范格式
        if lang and not any(lang.startswith(x) for x in ['cpp', 'c++', 'python', 'js', 'java']):
            # 尝试映射常见语言简写到标准名称
            lang_map = {
                'c': 'cpp',
                'py': 'python',
                'javascript': 'js',
            }
            lang = lang_map.get(lang.lower(), lang)
        
        return f'```{lang}\n{code}```'
    
    # 应用替换
    enhanced_text = re.sub(pattern, replace_match, markdown_text, flags=re.DOTALL)
    
    # 2. 检测并处理没有使用代码块格式的纯文本代码
    # 首先分割文本为段落
    paragraphs = enhanced_text.split('\n\n')
    for i, para in enumerate(paragraphs):
        # 检查段落是否像是代码（没有Markdown格式，但包含代码特征）
        if ('```' not in para and 
            ('#' not in para[:3]) and  # 不是标题
            ('*' not in para[:2]) and  # 不是列表
            ('>' not in para[:2]) and  # 不是引用
            ('- ' not in para[:2]) and # 不是无序列表
            any(marker in para for marker in [';', '{', '}', '()', 'int ', 'void ', 'for(', 'while(', 'if(', 'else', 'return ']) and
            len(para.strip().split('\n')) >= 2):  # 至少有两行
            
            # 看起来像代码，封装成代码块
            paragraphs[i] = f'```{default_lang}\n{para.strip()}\n```'
    
    # 重新组合文本
    enhanced_text = '\n\n'.join(paragraphs)
    
    # 3. 确保单行换行正确显示（Markdown默认需要两行才换行）
    enhanced_text = enhanced_text.replace('\n', '  \n')
    
    # 调试输出一下结果
    print(f"增强后的Markdown前300个字符: {enhanced_text[:300]}")
    
    return enhanced_text


# 增强Markdown格式
def enhance_markdown(text):
    """增强Markdown格式，确保标题和代码块等标记正确渲染"""
    import re
    
    if not text:
        return text
        
    # 统一换行符
    text = text.replace('\r\n', '\n')
    
    # 确保标题格式正确（#后有空格）
    text = re.sub(r'(^|\n)(#{1,6})([^#\s])', r'\1\2 \3', text)
    
    # 确保标题前后有空行，提高解析准确性
    text = re.sub(r'([^\n])(#{1,6}\s)', r'\1\n\n\2', text)
    text = re.sub(r'(#{1,6}[^\n]+)([^\n])', r'\1\n\n\2', text)
    
    # 确保代码块格式正确
    # 检查是否有不完整的代码块标记
    if '```' in text:
        # 计算代码块开始和结束标记数量
        start_count = text.count('```')
        
        # 如果是奇数，说明有不匹配的标记，添加一个结束标记
        if start_count % 2 != 0:
            text += '\n```'
    
    # 确保Markdown列表格式正确
    lines = text.split('\n')
    formatted_lines = []
    in_code_block = False
    
    for i, line in enumerate(lines):
        # 检测是否在代码块内
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            formatted_lines.append(line)
            continue
        
        # 在代码块内的不做特殊处理
        if in_code_block:
            formatted_lines.append(line)
            continue
        
        # 检查列表标记后是否有空格
        if re.match(r'^[*\-+](?!\s)', line):
            line = line[0] + ' ' + line[1:]
        
        # 如果这行是标题，且前一行不是空行，添加空行
        if (re.match(r'^#{1,6}\s', line) and 
            i > 0 and formatted_lines and formatted_lines[-1].strip()):
            formatted_lines.append('')
        
        # 添加当前行
        formatted_lines.append(line)
        
        # 如果这行是标题，且下一行不是空行，添加空行
        if (re.match(r'^#{1,6}\s', line) and 
            i < len(lines) - 1 and lines[i+1].strip() and not lines[i+1].startswith('#')):
            formatted_lines.append('')
    
    # 重新组合文本
    enhanced_text = '\n'.join(formatted_lines)
    
    # 输出增强后的前300个字符，便于调试
    print(f"增强后的Markdown前300个字符: {enhanced_text[:300]}")
    
    return enhanced_text


@api.route('/submit', methods=['POST'])
@login_required
def submit_code():
    """提交代码API"""
    try:
        data = request.get_json()
        if not data or 'code' not in data or 'assignment_id' not in data:
            return error_response("请提供代码和作业ID", 400)
            
        code = data['code']
        assignment_id = data['assignment_id']
        student_id = session['student_id']
        language = data.get('language', 'cpp')  # 默认为C++
        
        # 检查作业是否存在
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return error_response("作业不存在", 404)
        
        # 创建新的提交记录，状态为pending
        submission = Submission(
            student_id=student_id,
            assignment_id=assignment_id,
            code=code,
            language=language,
            status='pending'
        )
        
        # 先保存到数据库获取ID
        db.session.add(submission)
        db.session.commit()
        
        # 评估代码
        try:
            score, feedback = evaluate_cpp_code(
                code_str=code, 
                model=None, 
                assignment_title=assignment.title
            )
            
            # 更新提交记录
            submission.score = score
            submission.feedback = feedback
            submission.status = 'evaluated'
            
            # 检查是否有AI反馈
            import re
            import json
            
            # 尝试从评估结果中提取AI反馈
            if isinstance(feedback, str) and ('{' in feedback or '}' in feedback):
                try:
                    pattern = r'{.*}'
                    matches = re.search(pattern, feedback, re.DOTALL)
                    if matches:
                        json_str = matches.group(0)
                        try:
                            feedback_data = json.loads(json_str)
                            if 'feedback' in feedback_data:
                                ai_feedback = feedback_data['feedback']
                                submission.ai_feedback = ai_feedback
                        except Exception as e:
                            print(f"解析JSON反馈失败: {e}")
                except Exception as e:
                    print(f"处理AI反馈时出错: {e}")
            
            # 更新作业统计信息
            assignment.total_score += score
            assignment.count += 1
            assignment.average_score = assignment.total_score / assignment.count
            
            db.session.commit()
            
            return api_response(
                success=True,
                message="代码提交成功",
                data={
                    'submission_id': submission.id,
                    'score': submission.score,
                    'status': submission.status
                }
            )
            
        except Exception as e:
            print(f"评估代码时出错: {e}")
            print(traceback.format_exc())
            
            submission.status = 'failed'
            db.session.commit()
            
            return error_response(f"代码评估失败: {str(e)}", 500)
            
    except Exception as e:
        print(f"处理提交失败: {e}")
        print(traceback.format_exc())
        return error_response(f"处理提交失败: {str(e)}", 500)


@api.route('/submission/<int:submission_id>', methods=['GET'])
@login_required
def get_submission(submission_id):
    """获取提交详情"""
    try:
        submission = Submission.query.get_or_404(submission_id)
        
        # 检查权限
        student_id = session.get('student_id')
        user_type = session.get('user_type')
        
        if user_type != '管理员' and student_id != submission.student_id:
            return error_response("您没有权限查看此提交", 403)
        
        return api_response(
            success=True,
            message="获取提交详情成功",
            data={
                'submission': submission_to_dict(submission)
            }
        )
    except Exception as e:
        return error_response(f"获取提交详情失败: {str(e)}", 500)


@api.route('/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """获取所有用户列表(管理员专用)"""
    try:
        users = User.query.all()
        return api_response(
            success=True,
            message="获取用户列表成功",
            data={
                'users': [user_to_dict(u) for u in users]
            }
        )
    except Exception as e:
        return error_response(f"获取用户列表失败: {str(e)}", 500)


@api.route('/get_programming_guidance', methods=['POST'])
@login_required
def get_programming_guidance():
    """获取编程指导"""
    try:
        data = request.get_json()
        if not data or 'code' not in data or 'assignment_id' not in data:
            return error_response("请提供代码和作业ID", 400)
            
        code = data['code']
        assignment_id = data['assignment_id']
        language = data.get('language', 'cpp')  # 默认为C++
        
        # 检查代码长度
        if len(code.strip()) < 5:
            return error_response("代码太短，无法提供有针对性的指导", 400)
        
        # 获取作业信息
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return error_response("作业不存在", 404)
        
        try:
            # 输出调试信息
            print(f"正在为代码（长度:{len(code)}）生成编程指导...")
            
            # 生成编程指导
            guidance_text = generate_guidance(
                code=code,
                assignment_title=assignment.title,
                assignment_description=assignment.description,
                language=language
            )
            
            # 输出调试信息
            print(f"获取到指导内容，长度: {len(guidance_text if guidance_text else 'None')}")
            
            # 处理指导内容
            if guidance_text:
                # 增强Markdown格式，确保标题正确渲染
                guidance_text = enhance_markdown(guidance_text)
                
                # 增强代码块
                enhanced_guidance = enhance_code_blocks(guidance_text, default_lang=language)
                
                # 直接返回Markdown文本，不转换为HTML
                formatted_guidance = enhanced_guidance
                
                # 输出调试信息
                print(f"返回格式化后的指导内容，长度: {len(formatted_guidance)}")
                print(f"指导内容前200个字符: {formatted_guidance[:200].replace(chr(10), ' ')}")
            else:
                formatted_guidance = "无法生成针对您代码的指导内容，请稍后再试。"
                print(f"无法获取指导内容，返回默认消息")
            
            # 返回成功响应
            response = api_response(
                success=True,
                message="生成编程指导成功",
                data={
                    'guidance': formatted_guidance
                }
            )
            
            # 检查响应大小
            response_size = len(response.data) if hasattr(response, 'data') else 0
            print(f"响应数据大小: {response_size} 字节")
            
            return response
            
        except Exception as e:
            print(f"生成编程指导失败: {e}")
            print(traceback.format_exc())
            return error_response(f"生成编程指导失败: {str(e)}", 500)
            
    except Exception as e:
        print(f"处理编程指导请求失败: {e}")
        print(traceback.format_exc())
        return error_response(f"处理请求失败: {str(e)}", 500)


@api.route('/ask_question', methods=['POST'])
@login_required
def ask_question():
    """学生提问获取AI回答"""
    try:
        # 获取当前用户信息
        user_id = session.get('user_id')
        student_id = session.get('student_id')
        
        # 简单的请求限制检查
        now = datetime.now()
        last_request_time = session.get('last_ai_question_time')
        
        if last_request_time:
            last_time = datetime.fromisoformat(last_request_time)
            time_diff = (now - last_time).total_seconds()
            # 设置10秒冷却时间防止过于频繁请求
            if time_diff < 10:
                return error_response(f"请求过于频繁，请等待{10-int(time_diff)}秒后再试", 429)
        
        # 更新最后请求时间
        session['last_ai_question_time'] = now.isoformat()
                
        data = request.get_json()
        if not data:
            return error_response("请求数据为空", 400)
            
        # 检查必要参数
        required_fields = ['code', 'question', 'assignment_id']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return error_response(f"缺少必要参数: {', '.join(missing_fields)}", 400)
            
        code = data['code']
        question = data['question']
        assignment_id = data['assignment_id']
        language = data.get('language', 'cpp')  # 默认为C++
        
        # 输入验证
        if len(question.strip()) < 2:
            return error_response("请提供具体的问题，至少2个字符", 400)
        
        if len(code.strip()) < 5:
            return error_response("请提供足够的代码内容以便AI更好地理解您的问题，至少5个字符", 400)
        
        # 获取作业信息
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            return error_response("作业不存在", 404)
        
        try:
            # 显示处理中状态
            print(f"正在处理学生问题: '{question}'")
            print(f"代码长度: {len(code)}")
            
            # 使用大模型生成回答
            answer = generate_answer_to_question(
                code=code,
                question=question,
                assignment_title=assignment.title,
                assignment_description=assignment.description,
                language=language
            )
            
            # 输出调试信息
            print(f"获取到AI回答，长度: {len(answer if answer else 'None')}")
            
            # 使用markdown库正确地将Markdown转换为HTML
            if answer:
                try:
                    # 增强Markdown格式，确保标题正确渲染
                    answer = enhance_markdown(answer)
                    
                    # 增强代码块
                    enhanced_answer = enhance_code_blocks(answer, default_lang=language)
                    
                    # 直接返回Markdown文本，不转换为HTML
                    formatted_answer = enhanced_answer
                    
                    # 输出调试信息
                    print(f"返回格式化后的回答，长度: {len(formatted_answer)}")
                    print(f"回答前200个字符: {formatted_answer[:200].replace(chr(10), ' ')}")
                except Exception as md_error:
                    print(f"Markdown转换出错: {md_error}")
                    print(traceback.format_exc())
                    # 如果Markdown转换失败，至少返回纯文本
                    escaped_answer = answer.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                    formatted_answer = f"<p>{escaped_answer}</p>"
                    print(f"返回纯文本HTML格式，长度: {len(formatted_answer)}")
            else:
                formatted_answer = "很抱歉，我无法理解您的问题或无法基于当前代码生成回答。请尝试重新表述您的问题或提供更多代码上下文。"
                print(f"无法获取回答，返回默认消息")
            
            # 记录学生提问日志
            if student_id:
                try:
                    from models import StudentQuestion
                    new_question = StudentQuestion(
                        student_id=student_id,
                        assignment_id=assignment_id,
                        question=question,
                        code_snapshot=code,
                        answer=answer,
                        asked_at=datetime.now()
                    )
                    db.session.add(new_question)
                    db.session.commit()
                    print(f"已记录学生({student_id})提问: '{question}'")
                except Exception as e:
                    print(f"记录学生提问日志时出错: {e}")
                    print(traceback.format_exc())
                    # 不影响主流程，忽略错误
            
            # 返回成功响应
            response = api_response(
                success=True,
                message="问题回答成功",
                data={
                    'answer': formatted_answer
                }
            )
            
            # 检查响应大小
            response_size = len(response.data) if hasattr(response, 'data') else 0
            print(f"响应数据大小: {response_size} 字节")
            
            return response
            
        except Exception as e:
            print(f"生成问题回答时出错: {e}")
            print(traceback.format_exc())
            
            # 提供更友好的错误信息
            error_message = str(e)
            if "API调用失败" in error_message:
                return error_response("AI服务暂时不可用，请稍后再试", 503)
            elif "超时" in error_message:
                return error_response("AI服务响应超时，请稍后再试", 504)
            else:
                return error_response(f"生成问题回答失败: {error_message}", 500)
            
    except Exception as e:
        print(f"处理学生提问请求失败: {e}")
        print(traceback.format_exc())
        return error_response(f"处理请求失败: {str(e)}", 500)


@api.route('/code_advice', methods=['POST'])
@login_required
def get_code_advice():
    """获取代码建议API - 使用新的代码建议系统"""
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'code' not in data:
            return error_response("请提供代码内容", 400)
            
        # 提取参数
        code = data['code']
        assignment_id = data.get('assignment_id')
        language = data.get('language', 'cpp')
        advanced_mode = data.get('advanced', False)
        
        # 获取学生ID
        student_id = session.get('student_id')
        if not student_id:
            return error_response("会话已过期，请重新登录", 401)
        
        # 日志记录
        print(f"处理代码建议请求: 学生 {student_id}, 语言 {language}, 高级模式 {advanced_mode}")
        print(f"代码长度: {len(code)}")

        # 如果提供了作业ID，获取作业详情作为上下文
        assignment_title = None
        assignment_description = None
        if assignment_id:
            assignment = Assignment.query.get(assignment_id)
            if assignment:
                assignment_title = assignment.title
                assignment_description = assignment.description
                print(f"作业标题: {assignment_title}")
            else:
                print(f"警告: 提供的作业ID {assignment_id} 无效")
                
        # 使用新的代码建议系统生成建议
        try:
            print(f"使用新的代码建议系统为{language}代码生成建议...")
            analysis_result = generate_code_advice(
                code=code,
                language=language,
                assignment_title=assignment_title,
                assignment_description=assignment_description,
                advanced_mode=advanced_mode
            )
            
            # 检查分析结果
            if not analysis_result:
                print("代码建议系统返回空结果")
                return error_response("无法生成代码建议，请稍后再试", 500)
                
            print(f"代码建议生成成功，总体评分: {(analysis_result.get('algorithm_score', 0) + analysis_result.get('style_score', 0) + analysis_result.get('functionality_score', 0) + analysis_result.get('efficiency_score', 0)) / 4:.1f}")
            
            # 根据模式构建不同格式的建议文本
            if advanced_mode:
                # 高级模式：直接返回简洁的指导内容
                advice = analysis_result.get('overall_feedback', '无法生成指导建议')
            else:
                # 基础模式：构建详细的分析报告
                advice = f"""## 代码分析报告

### 总体评价
{analysis_result.get('overall_feedback', '无法生成评估')}

### 详细分析

#### 算法能力 ({analysis_result.get('algorithm_score', 60)}/100)
{analysis_result.get('algorithm_feedback', '算法设计与问题解决能力的分析暂不可用')}

#### 代码风格 ({analysis_result.get('style_score', 60)}/100)
{analysis_result.get('style_feedback', '代码风格与命名规范分析暂不可用')}

### 改进建议
"""
                
                # 添加建议列表
                suggestions = analysis_result.get('suggestions', [])
                if suggestions:
                    for i, suggestion in enumerate(suggestions, 1):
                        advice += f"{i}. {suggestion}\n"
                else:
                    advice += "- 暂无具体改进建议\n"
                
                # 添加学习资源（仅基础模式）
                advice += """
### 学习资源
"""
                if language == 'cpp':
                    advice += """- [C++核心指南](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [Effective Modern C++](https://www.oreilly.com/library/view/effective-modern-c/9781491908419/)
- [C++参考手册](https://en.cppreference.com/w/)"""
                elif language == 'python':
                    advice += """- [Python官方文档](https://docs.python.org/zh-cn/3/)
- [Python编程规范(PEP 8)](https://peps.python.org/pep-0008/)
- [Python进阶](https://eastlakeside.gitbook.io/interpy-zh/)"""
                elif language == 'java':
                    advice += """- [Java编程规范](https://www.oracle.com/java/technologies/javase/codeconventions-introduction.html)
- [Effective Java](https://www.oreilly.com/library/view/effective-java-3rd/9780134686097/)
- [Java教程](https://www.w3schools.com/java/)"""
                
            # 返回API响应
            return api_response(
                success=True,
                message="代码建议生成成功",
                data={
                    'advice': advice,
                    'metrics': {
                        'algorithm_score': analysis_result.get('algorithm_score', 60),
                        'style_score': analysis_result.get('style_score', 60),
                        'functionality_score': analysis_result.get('functionality_score', 60),
                        'efficiency_score': analysis_result.get('efficiency_score', 60)
                    }
                }
            )
                
        except Exception as e:
            print(f"生成代码建议失败: {e}")
            print(traceback.format_exc())
            
            # 回退到基本分析作为应急方案
            print("使用基本代码质量分析作为回退方案")
            analysis_result = analyze_code_quality(code)
            
            # 构建简单的建议文本
            advice = f"""## 代码分析 (基础版)

### 总体评价
我们的基本代码分析系统检测到您的代码已经完成了基本功能，但仍有一些可以改进的地方。

### 代码结构
{analysis_result.get('structure_feedback', '代码结构分析暂不可用')}

### 代码风格
{analysis_result.get('style_feedback', '代码风格分析暂不可用')}

### 改进建议
"""
            suggestions = analysis_result.get('suggestions', [])
            if suggestions:
                for i, suggestion in enumerate(suggestions, 1):
                    advice += f"{i}. {suggestion}\n"
            else:
                advice += """1. 添加更多注释，解释关键算法和逻辑
2. 使用更有意义的变量名，提高代码可读性
3. 考虑边界情况和错误处理，提高代码健壮性"""
                
            return api_response(
                success=True,
                message="代码建议生成成功 (基础版)",
                data={
                    'advice': advice,
                    'metrics': {
                        'algorithm_score': analysis_result.get('algorithm_score', 65),
                        'style_score': analysis_result.get('style_score', 70),
                        'functionality_score': analysis_result.get('functionality_score', 75),
                        'efficiency_score': analysis_result.get('efficiency_score', 65)
                    }
                }
            )
            
    except Exception as e:
        print(f"处理代码建议请求失败: {e}")
        print(traceback.format_exc())
        return error_response(f"处理请求失败: {str(e)}", 500)


@api.route('/student/ability-trend-status', methods=['GET'])
@login_required
def get_ability_trend_status():
    """获取学生能力趋势分析状态"""
    try:
        # 获取当前学生ID
        if session.get('usertype') != '学生':
            return error_response("只有学生可以查询能力趋势状态", 403)
        
        student_id = session.get('student_id')
        if not student_id:
            return error_response("学生ID未找到", 400)
        
        # 查询能力趋势记录
        trend_record = AbilityTrend.query.filter_by(student_id=student_id).first()
        
        if not trend_record:
            # 如果没有记录，创建一个
            trend_record = AbilityTrend.get_or_create(student_id)
        
        response_data = {
            'status': trend_record.status,
            'last_updated': trend_record.last_updated.strftime('%Y-%m-%d %H:%M:%S') if trend_record.last_updated else None,
            'submissions_count': trend_record.submissions_count
        }
        
        # 如果状态是已完成，返回分析结果
        if trend_record.status == 'completed':
            response_data['analysis'] = trend_record.get_trend_dict()
        
        return api_response("获取状态成功", data=response_data)
        
    except Exception as e:
        print(f"获取能力趋势状态失败: {e}")
        print(traceback.format_exc())
        return error_response(f"获取状态失败: {str(e)}", 500)


@api.route('/admin/batch-update-trends', methods=['POST'])
@admin_required
def batch_update_trends():
    """管理员批量更新学生能力趋势"""
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            # 如果没有指定学生ID，更新所有学生
            all_users = User.query.filter_by(usertype='学生').all()
            student_ids = [user.student_id for user in all_users]
        
        # 触发批量异步更新
        from utils.async_tasks import add_batch_trend_update
        task_id = add_batch_trend_update(student_ids)
        
        return api_response("批量更新任务已启动", data={
            'task_id': task_id,
            'student_count': len(student_ids),
            'message': f'已为 {len(student_ids)} 个学生启动能力趋势分析任务'
        })
        
    except Exception as e:
        print(f"批量更新能力趋势失败: {e}")
        print(traceback.format_exc())
        return error_response(f"批量更新失败: {str(e)}", 500)


@api.route('/admin/trend-statistics', methods=['GET'])
@admin_required  
def get_trend_statistics():
    """获取能力趋势分析统计信息"""
    try:
        # 统计各状态的数量
        from sqlalchemy import func
        
        stats = db.session.query(
            AbilityTrend.status,
            func.count(AbilityTrend.id).label('count')
        ).group_by(AbilityTrend.status).all()
        
        status_counts = {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0
        }
        
        for status, count in stats:
            status_counts[status] = count
        
        # 获取最近更新的记录
        recent_updates = AbilityTrend.query.filter(
            AbilityTrend.status == 'completed'
        ).order_by(
            AbilityTrend.last_updated.desc()
        ).limit(10).all()
        
        recent_list = []
        for trend in recent_updates:
            recent_list.append({
                'student_id': trend.student_id,
                'last_updated': trend.last_updated.strftime('%Y-%m-%d %H:%M:%S'),
                'submissions_count': trend.submissions_count
            })
        
        return api_response("获取统计信息成功", data={
            'status_counts': status_counts,
            'recent_updates': recent_list,
            'total_students': sum(status_counts.values())
        })
        
    except Exception as e:
        print(f"获取趋势统计信息失败: {e}")
        print(traceback.format_exc())
        return error_response(f"获取统计信息失败: {str(e)}", 500) 