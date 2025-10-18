"""
为Submission表添加language字段的数据库迁移脚本
"""
from datetime import datetime
import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接配置
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'root'),
    'database': os.environ.get('DB_NAME', 'student_code_review'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def run_migration():
    """执行迁移操作"""
    conn = None
    try:
        # 连接到数据库
        print("正在连接到数据库...")
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        print("检查字段是否已存在...")
        cursor.execute("DESCRIBE submissions")
        columns = [column['Field'] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            # 添加language字段
            print("正在添加language字段...")
            cursor.execute("""
                ALTER TABLE submissions 
                ADD COLUMN language VARCHAR(20) DEFAULT 'cpp'
            """)
            
            # 更新现有记录的language为默认值'cpp'
            print("更新现有记录...")
            cursor.execute("""
                UPDATE submissions 
                SET language = 'cpp'
                WHERE language IS NULL
            """)
            
            # 提交更改
            conn.commit()
            print("迁移成功完成！")
        else:
            print("language字段已存在，无需迁移")
            
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration() 