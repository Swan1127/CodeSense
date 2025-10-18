"""
数据库迁移脚本 - 添加AI反馈字段和状态字段
"""
import os
import sys
from flask import Flask
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from config import config
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()  # 加载环境变量


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)
    
    # 从配置对象中加载配置
    app.config.from_object(config['development'])
    
    # 设置MySQL数据库URI
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:root@localhost/student_code_review'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 初始化数据库
    db.init_app(app)
    
    return app


def run_migration():
    """运行数据库迁移"""
    app = create_app()
    with app.app_context():
        # 检查submissions表是否存在
        try:
            db.session.execute(text("SHOW TABLES LIKE 'submissions'"))
            print("检查submissions表是否存在...")
            
            # 检查status字段是否存在
            check_status = db.session.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'submissions' AND TABLE_SCHEMA = DATABASE() 
                AND COLUMN_NAME = 'status'
            """)).fetchone()
            
            if not check_status:
                print("添加status字段...")
                db.session.execute(text("""
                    ALTER TABLE submissions 
                    ADD COLUMN status VARCHAR(20) DEFAULT 'pending' 
                    COMMENT '状态：pending, evaluated, failed'
                """))
                db.session.commit()
                print("status字段添加成功")
            else:
                print("status字段已存在，跳过")
                
            # 检查ai_feedback字段是否存在
            check_ai_feedback = db.session.execute(text("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'submissions' AND TABLE_SCHEMA = DATABASE() 
                AND COLUMN_NAME = 'ai_feedback'
            """)).fetchone()
            
            if not check_ai_feedback:
                print("添加ai_feedback字段...")
                db.session.execute(text("""
                    ALTER TABLE submissions 
                    ADD COLUMN ai_feedback TEXT NULL 
                    COMMENT '大模型评估结果'
                """))
                db.session.commit()
                print("ai_feedback字段添加成功")
            else:
                print("ai_feedback字段已存在，跳过")
                
            print("数据库迁移完成")
            return True
        except Exception as e:
            print(f"迁移过程中出错: {str(e)}")
            return False


if __name__ == "__main__":
    # 运行迁移
    success = run_migration()
    if success:
        print("迁移成功完成！")
    else:
        print("迁移失败，请检查错误信息") 