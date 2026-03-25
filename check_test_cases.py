import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app import create_app
    from models import db, Assignment, TestCase, Submission
    
    app = create_app('development')
    with app.app_context():
        assignment_id = 112
        assignment = Assignment.query.get(assignment_id)
        if not assignment:
            print(f"Assignment {assignment_id} not found")
        else:
            print(f"Assignment: {assignment.title}")
            test_cases = TestCase.query.filter_by(assignment_id=assignment_id).all()
            print(f"Total Test Cases: {len(test_cases)}")
            for tc in test_cases:
                print(f"ID: {tc.id}, Input: {repr(tc.input_data)}, Expected: {repr(tc.expected_output)}, Public: {tc.is_public}")
            
            # Check latest submission for this assignment
            latest_sub = Submission.query.filter_by(assignment_id=assignment_id).order_by(Submission.submitted_at.desc()).first()
            if latest_sub:
                print(f"\nLatest Submission ID: {latest_sub.id}")
                # print(f"Code:\n{latest_sub.code}")
                print(f"Sandbox Passed: {latest_sub.sandbox_passed}/{latest_sub.sandbox_total}")
                print(f"Sandbox Detail: {latest_sub.sandbox_detail}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
