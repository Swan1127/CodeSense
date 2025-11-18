#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移：添加知识点评分系统
创建日期：2025-01-17

功能说明：
1. 创建 knowledge_point_scores 表 - 存储学生各知识点的评分
2. 创建 assignment_knowledge_points 表 - 存储作业与知识点的关联
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text

def upgrade():
    """执行数据库升级"""
    with app.app_context():
        print("开始创建知识点评分系统表...\n")

        # 1. 创建知识点评分表
        print("[1/2] 创建 knowledge_point_scores 表...")
        create_knowledge_scores_sql = """
        CREATE TABLE IF NOT EXISTS knowledge_point_scores (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            student_id VARCHAR(20) NOT NULL,
            knowledge_point VARCHAR(50) NOT NULL,
            score FLOAT DEFAULT 0.0 COMMENT '知识点得分(0-100)',
            total_attempts INTEGER DEFAULT 0 COMMENT '总尝试次数',
            correct_attempts INTEGER DEFAULT 0 COMMENT '正确次数',
            average_difficulty FLOAT DEFAULT 0.0 COMMENT '平均题目难度',
            last_updated DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_student_point (student_id, knowledge_point),
            FOREIGN KEY (student_id) REFERENCES users(student_id) ON DELETE CASCADE,
            INDEX idx_student (student_id),
            INDEX idx_knowledge_point (knowledge_point)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生知识点评分表';
        """

        db.session.execute(text(create_knowledge_scores_sql))
        print("  ✓ knowledge_point_scores 表创建成功")

        # 2. 创建作业知识点关联表
        print("[2/2] 创建 assignment_knowledge_points 表...")
        create_assignment_kp_sql = """
        CREATE TABLE IF NOT EXISTS assignment_knowledge_points (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            assignment_id INTEGER NOT NULL,
            knowledge_point VARCHAR(50) NOT NULL,
            weight FLOAT DEFAULT 1.0 COMMENT '权重(该知识点在此题中的重要程度)',
            difficulty FLOAT DEFAULT 1.0 COMMENT '该知识点在此题的难度系数(0.5-2.0)',
            auto_detected BOOLEAN DEFAULT FALSE COMMENT '是否由AI自动检测',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            INDEX idx_assignment (assignment_id),
            INDEX idx_knowledge_point (knowledge_point)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作业知识点关联表';
        """

        db.session.execute(text(create_assignment_kp_sql))
        print("  ✓ assignment_knowledge_points 表创建成功")

        db.session.commit()
        print("\n✓ 数据库迁移完成！")
        print("\n支持的C语言知识点：")
        print("  - basic_syntax (基础语法)")
        print("  - pointer (指针)")
        print("  - function (函数)")
        print("  - array (数组)")
        print("  - string (字符串)")
        print("  - struct (结构体)")
        print("  - file_io (文件操作)")
        print("  - dynamic_memory (动态内存)")
        print("  - linked_list (链表)")
        print("  - tree (树)")
        print("  - sorting (排序算法)")
        print("  - searching (搜索算法)")
        print("  - recursion (递归)")

def downgrade():
    """回滚数据库更改"""
    with app.app_context():
        print("开始回滚知识点评分系统...\n")

        print("[1/2] 删除 assignment_knowledge_points 表...")
        db.session.execute(text("DROP TABLE IF EXISTS assignment_knowledge_points"))
        print("  ✓ 表已删除")

        print("[2/2] 删除 knowledge_point_scores 表...")
        db.session.execute(text("DROP TABLE IF EXISTS knowledge_point_scores"))
        print("  ✓ 表已删除")

        db.session.commit()
        print("\n✓ 回滚完成！")

if __name__ == '__main__':
    print("="*60)
    print("知识点评分系统 - 数据库迁移")
    print("="*60)
    print()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['upgrade', 'downgrade'],
                        help='upgrade: 创建表, downgrade: 删除表')
    args = parser.parse_args()

    if args.action == 'upgrade':
        upgrade()
    else:
        downgrade()
