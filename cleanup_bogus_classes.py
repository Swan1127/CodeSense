import os
import sys

sys.path.append('e:/CodeSense/源代码')

from app import create_app
from models import db, Class, User

app = create_app()

with app.app_context():
    print("Starting DB cleanup for bogus classes...")
    
    classes = Class.query.all()
    bogus_classes = []
    
    for cls in classes:
        real_students_count = User.query.filter_by(class_name=cls.name, usertype='学生').count()
        
        if real_students_count == 0 or cls.name in ['教师', '管理员', '管理部门']:
            bogus_classes.append(cls)
            
    if bogus_classes:
        print(f"Found {len(bogus_classes)} bogus classes to delete:")
        for bc in bogus_classes:
            print(f" - ID: {bc.id}, Name: {bc.name}")
            db.session.delete(bc)
        db.session.commit()
        print("Successfully deleted bogus classes.")
    else:
        print("No bogus classes found in the database. Clean!")
