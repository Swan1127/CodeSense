"""
执行数据库迁移的主脚本
"""
from migrations.add_created_time import run_migration as run_created_time_migration
from migrations.add_language_field import run_migration as run_language_field_migration
from migrations.add_feedback_field import run_migration as run_feedback_field_migration

if __name__ == "__main__":
    print("开始执行数据库迁移...")
    
    # 执行添加created_time字段的迁移
    print("\n1. 为assignments表添加created_time字段:")
    run_created_time_migration()
    
    # 执行添加language字段的迁移
    print("\n2. 为submissions表添加language字段:")
    run_language_field_migration()
    
    # 执行添加feedback字段的迁移
    print("\n3. 为submissions表添加feedback字段:")
    run_feedback_field_migration()
    
    print("\n所有迁移过程已完成") 