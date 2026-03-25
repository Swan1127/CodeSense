import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    from models import db, Assignment
    
    app = create_app('development')
    with app.app_context():
        assignment_id = 112
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            print(f"Assignment {assignment_id} not found")
        else:
            print(f"Assignment: {assignment.title}")
            print(f"Description:\n{assignment.description}")
except Exception as e:
    print(f"Error: {e}")
