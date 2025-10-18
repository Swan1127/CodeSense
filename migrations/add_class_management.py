#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
添加班级管理功能的数据库迁移
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
import pymysql

def run_migration():
    """运行班级管理相关的数据库迁移"""
    app = create_app()
    
    with app.app_context():
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        try:
            print("=== 班级管理数据库迁移 ===")
            
            # 1. 创建classes表
            print("1. 创建classes表...")
            create_classes_table = """
            CREATE TABLE IF NOT EXISTS classes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                grade VARCHAR(20),
                major VARCHAR(50),
                teacher_name VARCHAR(50),
                student_count INT DEFAULT 0,
                avg_score FLOAT DEFAULT 0.0,
                total_submissions INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_classes_table)
            print("✓ classes表创建完成")
            
            # 2. 检查users表是否已有class_id列
            print("2. 检查并添加users表的class_id列...")
            check_column_query = """
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'class_id';
            """
            cursor.execute(check_column_query)
            result = cursor.fetchone()
            
            if result[0] == 0:  # 列不存在
                add_class_id_column = """
                ALTER TABLE users 
                ADD COLUMN class_id INT,
                ADD FOREIGN KEY (class_id) REFERENCES classes(id);
                """
                cursor.execute(add_class_id_column)
                print("✓ users表添加class_id列完成")
            else:
                print("✓ users表已存在class_id列")
            
            # 3. 检查并添加assignments表的新列
            print("3. 检查并添加assignments表的新列...")
            
            # 检查target_classes列
            check_target_classes = """
            SELECT COUNT(*) as count
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'assignments' 
            AND COLUMN_NAME = 'target_classes';
            """
            cursor.execute(check_target_classes)
            result = cursor.fetchone()
            
            if result[0] == 0:
                alter_assignments_1 = """
                ALTER TABLE assignments 
                ADD COLUMN target_classes TEXT,
                ADD COLUMN difficulty_level INT DEFAULT 1;
                """
                cursor.execute(alter_assignments_1)
                print("✓ assignments表添加新列完成")
            else:
                print("✓ assignments表已存在新列")
            
            # 4. 提交更改
            connection.commit()
            print("✓ 所有数据库更改已提交")
            
            # 5. 初始化classes数据
            print("4. 初始化classes数据...")
            
            # 获取现有的班级名称
            get_class_names = """
            SELECT DISTINCT class_name FROM users 
            WHERE class_name IS NOT NULL AND class_name != '';
            """
            cursor.execute(get_class_names)
            class_names = [row[0] for row in cursor.fetchall()]
            
            print(f"发现班级: {class_names}")
            
            # 为每个班级创建记录
            for class_name in class_names:
                check_class_exists = "SELECT COUNT(*) FROM classes WHERE name = %s"
                cursor.execute(check_class_exists, (class_name,))
                
                if cursor.fetchone()[0] == 0:  # 班级不存在
                    # 确定班级详细信息
                    if '网络240' in class_name:
                        grade, major, teacher = '2024', '网络工程', '张老师' if '01' in class_name else '李老师'
                    elif '计算机科学' in class_name:
                        grade, major, teacher = '2024', '计算机科学与技术', '王老师' if '1班' in class_name else '刘老师'
                    else:
                        grade, major, teacher = '2024', '计算机相关专业', '未分配'
                    
                    insert_class = """
                    INSERT INTO classes (name, grade, major, teacher_name) 
                    VALUES (%s, %s, %s, %s)
                    """
                    cursor.execute(insert_class, (class_name, grade, major, teacher))
                    print(f"✓ 创建班级: {class_name}")
            
            # 6. 更新用户的class_id
            print("5. 更新用户的class_id关联...")
            update_user_class_id = """
            UPDATE users u 
            JOIN classes c ON u.class_name = c.name 
            SET u.class_id = c.id 
            WHERE u.class_name IS NOT NULL;
            """
            cursor.execute(update_user_class_id)
            affected_rows = cursor.rowcount
            print(f"✓ 更新了 {affected_rows} 个用户的班级关联")
            
            # 7. 更新现有作业的班级关联
            print("6. 更新作业的班级关联...")
            update_assignment = """
            UPDATE assignments 
            SET target_classes = '网络2401,网络2402', difficulty_level = 3
            WHERE title = '数据结构与算法 - 编程练习';
            """
            cursor.execute(update_assignment)
            print("✓ 更新了数据结构与算法作业的班级关联")
            
            # 最终提交
            connection.commit()
            print("\n✅ 班级管理数据库迁移完成！")
            
        except Exception as e:
            print(f"❌ 迁移过程中出错: {e}")
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

if __name__ == '__main__':
    run_migration()
