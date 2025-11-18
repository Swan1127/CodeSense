#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移:
1. 在 'users' 表的 'usertype' 枚举中添加 '教师' 角色.
2. 修改 'classes' 表，用 'teacher_id' (外键) 替换 'teacher_name' (字符串).
"""
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s 
        AND COLUMN_NAME = %s
    """, (table_name, column_name))
    return cursor.fetchone()[0] > 0

def run_migration():
    """执行与教师角色和班级关联相关的数据库迁移"""
    app = create_app()
    
    with app.app_context():
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        try:
            print("=== 开始迁移：更新用户角色和班级教师关联 ===")

            # 1. 修改 users.usertype 的 ENUM 定义
            print("1. 正在修改 'users' 表的 'usertype' 枚举...")
            # 获取当前 ENUM 值
            cursor.execute("""
                SELECT COLUMN_TYPE 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'usertype'
            """,)
            result = cursor.fetchone()
            current_enum = result[0] if result else ''
            
            if '教师' not in current_enum:
                alter_enum_sql = "ALTER TABLE users MODIFY COLUMN usertype ENUM('学生', '教师', '管理员') NOT NULL"
                cursor.execute(alter_enum_sql)
                print("✓ 'usertype' 枚举已更新，添加 '教师' 角色。")
            else:
                print("✓ 'usertype' 枚举已包含 '教师' 角色，无需修改。 সন")

            # 2. 修改 classes 表
            print("\n2. 正在修改 'classes' 表...")
            
            # 检查并删除旧的 teacher_name 列
            if column_exists(cursor, 'classes', 'teacher_name'):
                cursor.execute("ALTER TABLE classes DROP COLUMN teacher_name;")
                print("✓ 已删除旧的 'teacher_name' 列。")
            else:
                print("✓ 'teacher_name' 列不存在，无需删除。 সন")

            # 检查并添加新的 teacher_id 列
            if not column_exists(cursor, 'classes', 'teacher_id'):
                cursor.execute("ALTER TABLE classes ADD COLUMN teacher_id VARCHAR(20) NULL AFTER major;")
                # 添加外键约束
                cursor.execute("""
                    ALTER TABLE classes 
                    ADD CONSTRAINT fk_teacher 
                    FOREIGN KEY (teacher_id) REFERENCES users(student_id) 
                    ON DELETE SET NULL;
                """)
                print("✓ 已添加 'teacher_id' 列并设置外键约束。")
            else:
                print("✓ 'teacher_id' 列已存在，无需添加。 সন")

            connection.commit()
            print("\n✅ 数据库迁移成功完成！")

        except Exception as e:
            print(f"❌ 迁移过程中发生错误: {e}")
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

if __name__ == '__main__':
    run_migration()
