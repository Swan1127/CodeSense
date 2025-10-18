#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
同步班级数据脚本
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Class, User, Assignment

def sync_class_data():
    """同步班级数据"""
    app = create_app()
    
    with app.app_context():
        print("=== 同步班级数据 ===")
        
        # 创建班级表
        print("1. 创建班级表...")
        db.create_all()
        
        # 从用户数据同步班级
        print("2. 从用户数据同步班级...")
        synced_count = Class.sync_from_users()
        print(f"✓ 同步了 {synced_count} 个班级")
        
        # 手动添加班级详细信息
        print("3. 更新班级详细信息...")
        class_details = {
            '网络2401': {
                'grade': '2024',
                'major': '网络工程',
                'teacher_name': '张老师'
            },
            '网络2402': {
                'grade': '2024', 
                'major': '网络工程',
                'teacher_name': '李老师'
            },
            '计算机科学1班': {
                'grade': '2024',
                'major': '计算机科学与技术',
                'teacher_name': '王老师'
            },
            '计算机科学2班': {
                'grade': '2024',
                'major': '计算机科学与技术',
                'teacher_name': '刘老师'
            }
        }
        
        updated_count = 0
        for class_name, details in class_details.items():
            cls = Class.query.filter_by(name=class_name).first()
            if cls:
                cls.grade = details['grade']
                cls.major = details['major']
                cls.teacher_name = details['teacher_name']
                updated_count += 1
        
        db.session.commit()
        print(f"✓ 更新了 {updated_count} 个班级的详细信息")
        
        # 关联用户到班级
        print("4. 建立用户与班级的关联...")
        users = User.query.filter(User.class_name.isnot(None)).all()
        linked_count = 0
        
        for user in users:
            if user.class_name and not user.class_id:
                cls = Class.query.filter_by(name=user.class_name).first()
                if cls:
                    user.class_id = cls.id
                    linked_count += 1
        
        db.session.commit()
        print(f"✓ 关联了 {linked_count} 个用户到班级")
        
        # 更新现有作业的班级关联
        print("5. 更新作业的班级关联...")
        assignment = Assignment.query.filter_by(title='数据结构与算法 - 编程练习').first()
        if assignment:
            assignment.set_target_classes(['网络2401', '网络2402'])
            assignment.difficulty_level = 3  # 中等难度
            db.session.commit()
            print("✓ 更新了数据结构与算法作业的班级关联")
        
        # 显示最终统计
        print("\n=== 同步完成统计 ===")
        classes = Class.query.all()
        for cls in classes:
            stats = cls.get_statistics()
            print(f"{cls.name}: {stats['student_count']}人, 平均分: {stats['avg_score']}, 提交数: {stats['total_submissions']}")
        
        print(f"\n✅ 班级数据同步完成！共处理 {len(classes)} 个班级")

if __name__ == '__main__':
    sync_class_data()
