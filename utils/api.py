"""
API功能支持模块
提供JSON响应和API结构
"""
from flask import jsonify
import json


def api_response(success=True, message="", data=None, code=200):
    """
    创建标准化的API响应
    
    参数:
        success: 操作是否成功
        message: 响应消息
        data: 响应数据
        code: HTTP状态码
    
    返回:
        JSON响应对象及状态码
    """
    response = {
        "success": success,
        "message": message,
        "data": data or {}
    }
    
    # 确保所有数据可JSON序列化
    try:
        # 尝试预序列化以捕获任何问题
        json.dumps(response)
    except (TypeError, ValueError, OverflowError) as e:
        print(f"API响应序列化错误: {e}")
        # 这里可能需要清理无法序列化的数据结构
        if data and "answer" in data:
            print(f"尝试清理answer字段，原长度: {len(data['answer'] if data['answer'] else 'None')}")
            # 确保答案为字符串并移除非ASCII字符
            data["answer"] = str(data["answer"]).encode('ascii', 'ignore').decode('ascii')
            print(f"清理后answer长度: {len(data['answer'])}")
            response["data"] = data
        elif data and "guidance" in data:
            print(f"尝试清理guidance字段，原长度: {len(data['guidance'] if data['guidance'] else 'None')}")
            # 确保指导为字符串并移除非ASCII字符
            data["guidance"] = str(data["guidance"]).encode('ascii', 'ignore').decode('ascii')
            print(f"清理后guidance长度: {len(data['guidance'])}")
            response["data"] = data
    
    return jsonify(response), code


def error_response(message, code=400):
    """
    创建错误响应
    
    参数:
        message: 错误消息
        code: HTTP状态码
    
    返回:
        JSON错误响应对象及状态码
    """
    return api_response(success=False, message=message, code=code)


def user_to_dict(user):
    """将用户对象转换为字典"""
    return {
        'student_id': user.student_id,
        'username': user.username,
        'full_name': user.full_name,
        'class_name': user.class_name,
        'usertype': user.usertype,
        'submit_count': user.submit_count,
        'user_ascore': user.user_ascore
    }


def assignment_to_dict(assignment):
    """将作业对象转换为字典"""
    return {
        'id': assignment.id,
        'title': assignment.title,
        'description': assignment.description,
        'average_score': assignment.average_score,
        'count': assignment.count
    }


def submission_to_dict(submission):
    """将提交记录对象转换为字典"""
    return {
        'id': submission.id,
        'student_id': submission.student_id,
        'assignment_id': submission.assignment_id,
        'score': submission.score,
        'language': submission.language,
        'status': submission.status,
        'feedback': submission.feedback,
        'ai_feedback': submission.ai_feedback,
        'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None
    } 