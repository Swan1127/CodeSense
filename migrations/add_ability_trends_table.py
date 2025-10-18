#!/usr/bin/env python3
"""
添加能力发展趋势表
创建时间: 2024年
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, AbilityTrend, User
from sqlalchemy import text

def run_migration():
    """执行数据库迁移"""
    print("开始添加能力发展趋势表...")
    
    try:
        # 创建表
        db.create_all()
        print("✅ ability_trends 表创建成功")
        
        # 检查表是否存在
        result = db.session.execute(text("SHOW TABLES LIKE 'ability_trends'")).fetchone()
        if result:
            print("✅ 表结构验证通过")
        else:
            print("❌ 表创建验证失败")
            return False
        
        # 为现有用户创建默认记录（可选）
        existing_users = User.query.all()
        created_count = 0
        
        for user in existing_users:
            existing_trend = AbilityTrend.query.filter_by(student_id=user.student_id).first()
            if not existing_trend:
                trend = AbilityTrend(
                    student_id=user.student_id,
                    status='pending'
                )
                db.session.add(trend)
                created_count += 1
        
        if created_count > 0:
            db.session.commit()
            print(f"✅ 为 {created_count} 个现有用户创建了默认趋势记录")
        
        print("🎉 能力发展趋势表迁移完成！")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # 导入app以初始化数据库连接
    from app import app
    
    with app.app_context():
        success = run_migration()
        if success:
            print("迁移成功完成！")
        else:
            print("迁移失败，请检查错误信息")
            sys.exit(1)

