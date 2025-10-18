#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量更新学生能力评分的管理脚本
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Class
from utils.ability_scorer import ability_scorer

def update_scores():
    """快速更新所有学生评分"""
    app = create_app()
    
    with app.app_context():
        print("正在更新学生能力评分...")
        updated_count = ability_scorer.update_all_students_scores()
        
        # 更新班级统计
        for cls in Class.query.all():
            stats = cls.get_statistics()
            cls.avg_score = stats['avg_score']
            db.session.add(cls)
        
        db.session.commit()
        print(f"✅ 更新完成！共更新 {updated_count} 名学生的评分")

if __name__ == '__main__':
    update_scores()
