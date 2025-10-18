"""
为Assignment表添加created_time字段的数据库迁移脚本
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
        cursor.execute("DESCRIBE assignments")
        columns = [column['Field'] for column in cursor.fetchall()]
        
        if 'created_time' not in columns:
            # 添加created_time字段
            print("正在添加created_time字段...")
            cursor.execute("""
                ALTER TABLE assignments 
                ADD COLUMN created_time DATETIME DEFAULT CURRENT_TIMESTAMP
            """)
            
            # 更新现有记录的created_time为当前时间
            print("更新现有记录...")
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(f"""
                UPDATE assignments 
                SET created_time = '{current_time}'
                WHERE created_time IS NULL
            """)
            
            # 提交更改
            conn.commit()
            print("迁移成功完成！")
        else:
            print("created_time字段已存在，无需迁移")
            
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration() 