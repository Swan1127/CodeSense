"""添加 analysis_markdown 字段到 ability_trends 表

使用方法：
在项目根目录运行：python migrations/add_analysis_markdown.py
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from sqlalchemy import text

def migrate_add_analysis_markdown():
    """添加 analysis_markdown 字段到 ability_trends 表"""
    try:
        # 检查字段是否已存在
        result = db.session.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_NAME = 'ability_trends'
            AND COLUMN_NAME = 'analysis_markdown'
        """))

        exists = result.scalar() > 0

        if exists:
            print("✅ analysis_markdown 字段已存在，无需迁移")
            return True

        # 添加新字段
        db.session.execute(text("""
            ALTER TABLE ability_trends
            ADD COLUMN analysis_markdown TEXT NULL AFTER student_id
        """))

        db.session.commit()
        print("✅ 成功添加 analysis_markdown 字段到 ability_trends 表")
        return True

    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    from app import app

    with app.app_context():
        migrate_add_analysis_markdown()
