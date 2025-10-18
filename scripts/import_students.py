#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从点名册.xlsx导入学生数据的脚本
"""
import os
import sys
import pandas as pd
import re
from werkzeug.security import generate_password_hash

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User, Assignment, SystemLog

def extract_class_info(class_info_str):
    """从班级信息字符串中提取班级列表"""
    # "班级：网络2401;网络2402" -> ["网络2401", "网络2402"]
    if '班级：' in class_info_str:
        class_part = class_info_str.replace('班级：', '')
        classes = [cls.strip() for cls in class_part.split(';') if cls.strip()]
        return classes
    return []

def extract_course_info(course_info_str):
    """从课程信息字符串中提取课程名称"""
    # "课程名称：数据结构与算法" -> "数据结构与算法"
    if '课程名称：' in course_info_str:
        return course_info_str.replace('课程名称：', '').strip()
    return course_info_str.strip()

def generate_username(student_id, full_name):
    """生成用户名（学号+姓名前两个字符）"""
    name_prefix = full_name[:2] if len(full_name) >= 2 else full_name
    return f"{student_id}_{name_prefix}"

def import_students_from_excel(excel_path):
    """从Excel文件导入学生数据"""
    
    print(f"正在读取Excel文件: {excel_path}")
    
    # 读取Excel文件
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"读取Excel文件失败: {e}")
        return False
    
    # 提取班级和课程信息
    class_info = str(df.iloc[0, 0])  # 第1行第1列：班级信息
    course_info = str(df.iloc[1, 2])  # 第2行第3列：课程信息
    
    classes = extract_class_info(class_info)
    course_name = extract_course_info(course_info)
    
    print(f"检测到班级: {classes}")
    print(f"检测到课程: {course_name}")
    
    # 解析学生数据（从第4行开始，索引为4）
    students_data = []
    
    for i in range(4, len(df)):
        # 获取序号、学号、姓名
        seq_num = df.iloc[i, 0]
        student_id = df.iloc[i, 1]
        full_name = df.iloc[i, 2]
        
        # 检查数据有效性
        if pd.isna(seq_num) or pd.isna(student_id) or pd.isna(full_name):
            continue
        
        # 转换为字符串并检查格式
        seq_num = str(seq_num).strip()
        student_id = str(student_id).strip()
        full_name = str(full_name).strip()
        
        # 验证序号是数字，学号是长数字
        if not seq_num.isdigit() or not student_id.isdigit() or len(student_id) < 10:
            if seq_num or student_id or full_name:  # 不是空行
                print(f"跳过无效数据行 {i}: 序号={seq_num}, 学号={student_id}, 姓名={full_name}")
            continue
        
        # 确定班级（根据学号前几位判断，或使用第一个班级作为默认）
        class_name = classes[0] if classes else "默认班级"
        if len(classes) > 1:
            # 可以根据学号规律分配班级，这里简单使用奇偶数分配
            try:
                if int(seq_num) % 2 == 0:
                    class_name = classes[1] if len(classes) > 1 else classes[0]
            except:
                pass
        
        students_data.append({
            'seq_num': int(seq_num),
            'student_id': student_id,
            'full_name': full_name,
            'class_name': class_name
        })
    
    print(f"解析到 {len(students_data)} 名学生数据")
    
    if not students_data:
        print("没有找到有效的学生数据")
        return False
    
    # 开始数据库操作
    success_count = 0
    error_count = 0
    existing_count = 0
    
    for student in students_data:
        try:
            # 检查学生是否已存在
            existing_user = User.query.filter_by(student_id=student['student_id']).first()
            
            if existing_user:
                print(f"学生已存在，跳过: {student['student_id']} - {student['full_name']}")
                existing_count += 1
                continue
            
            # 生成用户名
            username = generate_username(student['student_id'], student['full_name'])
            
            # 检查用户名是否重复，如果重复则添加序号
            counter = 1
            original_username = username
            while User.query.filter_by(username=username).first():
                username = f"{original_username}_{counter}"
                counter += 1
            
            # 创建新用户（默认密码为学号）
            new_user = User(
                student_id=student['student_id'],
                username=username,
                password=student['student_id'],  # 默认密码为学号
                usertype='学生',
                class_name=student['class_name'],
                full_name=student['full_name'],
                submit_count=0,
                user_ascore=0.0,
                user_tscore=0
            )
            
            db.session.add(new_user)
            success_count += 1
            print(f"添加学生: {student['student_id']} - {student['full_name']} (用户名: {username}, 班级: {student['class_name']})")
            
        except Exception as e:
            error_count += 1
            print(f"添加学生失败 {student['student_id']} - {student['full_name']}: {e}")
            db.session.rollback()
            continue
    
    # 提交数据库更改
    try:
        db.session.commit()
        print(f"\n=== 导入完成 ===")
        print(f"成功导入: {success_count} 名学生")
        print(f"已存在跳过: {existing_count} 名学生")
        print(f"导入失败: {error_count} 名学生")
        
        # 添加系统日志
        SystemLog.add_log(
            log_type='批量导入学生',
            content=f'从{excel_path}成功导入{success_count}名学生到系统',
            icon='bi bi-people-fill'
        )
        
        # 创建课程作业
        if course_name and course_name != 'nan':
            create_course_assignment(course_name, classes)
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"数据库提交失败: {e}")
        return False

def create_course_assignment(course_name, classes):
    """为课程创建一个默认作业"""
    try:
        # 检查是否已经存在该课程的作业
        existing_assignment = Assignment.query.filter_by(title=f"{course_name} - 编程练习").first()
        
        if existing_assignment:
            print(f"作业已存在: {course_name} - 编程练习")
            return
        
        # 创建作业
        assignment = Assignment(
            title=f"{course_name} - 编程练习",
            description=f"这是{course_name}课程的编程练习作业。请完成相关的编程题目并提交代码。\n\n适用班级: {', '.join(classes)}",
            total_score=0,
            average_score=0.0,
            count=0
        )
        
        db.session.add(assignment)
        db.session.commit()
        
        print(f"已创建作业: {course_name} - 编程练习")
        
        # 添加系统日志
        SystemLog.add_log(
            log_type='添加作业',
            content=f'自动创建作业：{course_name} - 编程练习',
            icon='bi bi-file-earmark-code'
        )
        
    except Exception as e:
        print(f"创建作业失败: {e}")
        db.session.rollback()

def main():
    """主函数"""
    # 创建Flask应用上下文
    app = create_app()
    
    with app.app_context():
        excel_path = "点名册.xlsx"
        
        if not os.path.exists(excel_path):
            print(f"错误: 找不到Excel文件 {excel_path}")
            return
        
        # 确保数据库表已创建
        db.create_all()
        
        # 执行导入
        success = import_students_from_excel(excel_path)
        
        if success:
            print("\n✅ 学生数据导入成功！")
            print("默认密码为学号，请提醒学生首次登录后修改密码。")
        else:
            print("\n❌ 学生数据导入失败！")

if __name__ == '__main__':
    main()
