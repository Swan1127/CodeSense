import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    from models import db, Assignment, TestCase, Submission
    
    app = create_app('development')
    with app.app_context():
        # Check latest submission overall
        latest_sub = Submission.query.order_by(Submission.submitted_at.desc()).first()
        if latest_sub:
            print(f"Submission ID: {latest_sub.id}")
            print(f"Assignment ID: {latest_sub.assignment_id}")
            print(f"Status: {latest_sub.status}")
            print(f"Sandbox Status: {latest_sub.sandbox_status}")
            print(f"Sandbox Passed: {latest_sub.sandbox_passed}/{latest_sub.sandbox_total}")
            print(f"Sandbox Detail: {latest_sub.sandbox_detail}")
            print(f"Score: {latest_sub.score}")
            
            # Check if compiler is available
            from utils.sandbox_runner import _find_compiler
            compiler = _find_compiler()
            print(f"Compiler Found: {compiler}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
