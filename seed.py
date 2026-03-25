"""
CodeSense 数据库播种脚本（与当前模型评分体系一致）

核心约定：
1) Submission.score 使用 0~5 分制（系统展示按 /5 分）
2) User.user_ascore 使用学生提交平均分（0~5），不再写入 60~100
3) Assignment.average_score / count 与 submissions 同步
4) Class 统计通过 Class.sync_from_users() 回填

用法：
python seed.py
"""

import random
import json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

from app import create_app
from models import db, User, Class, Assignment, TestCase, Submission, KnowledgePointScore, AbilityTrend


# 建议使用当前环境配置（由 FLASK_CONFIG/.env 决定）
app = create_app()


def get_or_create_admin():
    admin = User.query.filter_by(username='XiaoCow').first()
    if admin:
        return admin

    admin = User(
        student_id='admin_001',
        username='XiaoCow',
        password_hash=generate_password_hash('admin123'),
        usertype='管理员',
        full_name='代宇鹏',
        submit_count=0,
        user_ascore=0.0,
    )
    db.session.add(admin)
    db.session.commit()
    print('✅ 管理员账号创建成功 (admin_001 / admin123)')
    return admin


def get_or_create_teacher():
    teacher = User.query.filter_by(username='teacher_li').first()
    if teacher:
        return teacher

    teacher = User(
        student_id='t_1001',
        username='teacher_li',
        password_hash=generate_password_hash('teacher123'),
        usertype='教师',
        full_name='李老师',
        submit_count=0,
        user_ascore=0.0,
    )
    db.session.add(teacher)
    db.session.commit()
    print('✅ 教师账号创建成功 (t_1001 / teacher123)')
    return teacher


def get_or_create_classes(teacher):
    class_defs = [
        ('网络工程一班', '2024', '计算机大类'),
        ('计算机科学二班', '2024', '计算机大类'),
        ('软件工程实验班', '2024', '计算机大类'),
    ]

    classes = []
    for name, grade, major in class_defs:
        cls = Class.query.filter_by(name=name).first()
        if not cls:
            cls = Class(name=name, grade=grade, major=major, teacher_id=teacher.student_id)
            db.session.add(cls)
        else:
            # 对齐教师归属，避免“教师无班级”问题
            cls.teacher_id = teacher.student_id
        classes.append(cls)

    db.session.commit()
    print(f'✅ 班级初始化完成: {len(classes)} 个')
    return classes


def get_or_create_students(classes):
    students = []
    # 扩大到45人（每班15人左右）以展示充分的班级对比
    for i in range(1, 46):
        student_id = f's_2024{i:03d}'
        student = User.query.filter_by(student_id=student_id).first()

        if not student:
            # 均匀分配班级
            target_class = classes[i % len(classes)]
            student = User(
                student_id=student_id,
                username=f'student_{i}',
                password_hash=generate_password_hash('student123'),
                usertype='学生',
                full_name=f'学生{i}',
                class_name=target_class.name,
                class_id=target_class.id,
                submit_count=0,
                user_ascore=0.0,
            )
            db.session.add(student)
        else:
            # 已存在学生也保证 class_id 与 class_name 对齐
            if student.class_id is None and student.class_name:
                cls = Class.query.filter_by(name=student.class_name).first()
                if cls:
                    student.class_id = cls.id

        students.append(student)

    db.session.commit()
    print(f'✅ 学生初始化完成: {len(students)} 个')
    return students


def get_or_create_assignments(teacher, class_names):
    assignments_data = [
        {
            'title': 'C语言基础：两数之和',
            'desc': '编写一个 C 程序，读取两个整数并输出它们的和。',
            'difficulty': 1,
            'cases': [('1 2', '3'), ('10 20', '30'), ('-5 5', '0')],
        },
        {
            'title': '数组操作：查找最大值',
            'desc': '给定一个整数数组，编写函数返回数组中的最大值。',
            'difficulty': 2,
            'cases': [('5\n1 4 2 8 5', '8'), ('3\n-1 -5 -2', '-1')],
        },
        {
            'title': '字符串处理：回文判断',
            'desc': '输入一个字符串，判断它是否是回文串（正读和反读都一样）。',
            'difficulty': 2,
            'cases': [('level', '1'), ('hello', '0'), ('madam', '1')],
        },
        {
            'title': '指针基础：交换变量',
            'desc': '使用指针编写一个函数 `swap(int *a, int *b)` 实现在主函数中交换两个变量的值。',
            'difficulty': 3,
            'cases': [('5 10', '10 5'), ('-1 1', '1 -1')],
        },
        {
            'title': '链表操作：反转单链表',
            'desc': '给出一个单链表，将其反转并输出反转后的结果。',
            'difficulty': 4,
            'cases': [('1 2 3 4 5', '5 4 3 2 1'), ('10 20', '20 10')],
        },
        {
            'title': '算法应用：动态规划（爬楼梯）',
            'desc': '假设你正在爬楼梯。需要 n 阶你才能到达楼顶。每次你可以爬 1 或 2 个台阶。你有多少种不同的方法可以爬到楼顶？',
            'difficulty': 4,
            'cases': [('2', '2'), ('3', '3'), ('5', '8')],
        },
    ]

    created = []
    for item in assignments_data:
        assignment = Assignment.query.filter_by(title=item['title']).first()
        if not assignment:
            assignment = Assignment(
                title=item['title'],
                description=item['desc'],
                creator_id=teacher.student_id,
                target_classes=','.join(class_names),
                difficulty_level=item['difficulty'],
                due_date=datetime.utcnow() + timedelta(days=7),
            )
            db.session.add(assignment)
            db.session.commit()  # 先拿到 assignment.id

            for idx, (inp, out) in enumerate(item['cases']):
                case = TestCase(
                    assignment_id=assignment.id,
                    input_data=inp,
                    expected_output=out,
                    order_index=idx,
                    is_public=(idx == 0),
                )
                db.session.add(case)
            db.session.commit()

        created.append(assignment)

    print(f'✅ 作业初始化完成: {len(created)} 个')
    return created


def seed_submissions(students, assignments):
    """只补齐不存在的提交，制造差异化的成绩分布。"""
    created_count = 0

    for idx, student in enumerate(students):
        # 制造班级间和学生间的差异
        # 根据学生索引设定他的擅长程度
        proficiency = (idx % 5) + 1  # 1 到 5

        for assignment in assignments:
            # 已有该学生该作业提交则跳过（幂等）
            exists = Submission.query.filter_by(
                student_id=student.student_id,
                assignment_id=assignment.id,
            ).first()
            if exists:
                continue

            # 90% 概率生成一次提交，留一点未提交的空白
            if random.random() > 0.9:
                continue

            # 依据学生特长与作业难度生成得分
            # difficulty = assignment.difficulty_level (1~5)
            # score range: max(1, proficiency - difficulty + 3 +/- 1), clipped to 1~5
            base_score = proficiency - (assignment.difficulty_level * 0.5) + 2
            rand_mod = random.choice([-1, 0, 1])
            score = max(1, min(5, int(round(base_score + rand_mod))))

            total_cases = assignment.test_cases.count() or 5
            passed_cases = max(0, min(total_cases, round(score / 5 * total_cases)))
            
            # 生成一些简单的沙箱评判详情
            feedback_msg = "代码结构清晰，算法逻辑正确。" if score >= 4 else "部分样例未通过，建议检查边界条件和特殊情况。"

            submission = Submission(
                student_id=student.student_id,
                assignment_id=assignment.id,
                code='#include <stdio.h>\nint main(){\n    /* seeded code */\n    return 0;\n}',
                score=score,
                language='cpp',
                status='evaluated',
                ai_feedback=f'自动播种样例：{feedback_msg}',
                sandbox_passed=passed_cases,
                sandbox_total=total_cases,
                submitted_at=datetime.utcnow() - timedelta(days=random.randint(0, 15)),
            )
            db.session.add(submission)
            created_count += 1

    db.session.commit()
    print(f'✅ 提交记录补齐完成: 新增 {created_count} 条')


def seed_knowledge_points(students):
    """为每个学生填充一些知识点评分，使得雷达图能展示多边形效果"""
    knowledge_points = list(KnowledgePointScore.KNOWLEDGE_POINTS.keys())
    created_count = 0
    
    for idx, student in enumerate(students):
        # 创造一些具有特长的学生数据
        student_type = idx % 3 # 0: 综合强, 1: 偏科(算法强), 2: 基础较弱
        
        for kp in knowledge_points:
            score_record = KnowledgePointScore.query.filter_by(
                student_id=student.student_id,
                knowledge_point=kp
            ).first()
            
            if score_record:
                continue
                
            # 根据类型生成不同分数 (雷达图需要100分满分制)
            if student_type == 0:
                base = random.randint(75, 95)
            elif student_type == 1:
                if kp in ['pointer', 'tree', 'linked_list', 'sorting', 'recursion']:
                    base = random.randint(85, 95)
                else:
                    base = random.randint(55, 75)
            else:
                base = random.randint(45, 75)
                
            # 加入一些随机波动使得多边形更自然
            final_score = base + random.randint(-5, 5)
            final_score = max(0, min(100, final_score))
                
            score_record = KnowledgePointScore(
                student_id=student.student_id,
                knowledge_point=kp,
                score=final_score,
                total_attempts=random.randint(2, 10),
                correct_attempts=random.randint(1, 8),
                average_difficulty=random.uniform(1.0, 3.0),
                last_updated=datetime.utcnow()
            )
            db.session.add(score_record)
            created_count += 1
            
    db.session.commit()
    print(f'✅ 知识点评分数据填充完成: 新增 {created_count} 条')


def seed_ability_trends(students):
    """填充学生能力趋势记录"""
    created_count = 0
    for student in students:
        trend = AbilityTrend.query.filter_by(student_id=student.student_id).first()
        if not trend:
            # 制造一些假趋势历史数据 (模拟近期的进步)
            scores_algo = [random.randint(50, 70)] + sorted([random.randint(60, 90) for _ in range(4)])
            
            trend_data = {
                "algorithm": scores_algo,
                "style": [random.randint(65, 85) for _ in range(5)],
                "functionality": [random.randint(70, 90) for _ in range(5)],
                "efficiency": [random.randint(60, 85) for _ in range(5)],
                "readability": [random.randint(65, 85) for _ in range(5)],
                "trend": "能力整体呈现稳步上升趋势，基础语法掌握较好，算法设计上逐渐体现出优化思路。",
                "improvement": "在近期练习中，对数据结构的理解有明显提高，特别是算法部分进步最为明显。",
                "suggestions": [
                    "多练习树与图相关的算法题目",
                    "注意代码的规范命名和注释",
                    "尝试优化双层循环逻辑以提升执行效率"
                ]
            }
            trend = AbilityTrend(
                student_id=student.student_id,
                trend_data=json.dumps(trend_data, ensure_ascii=False),
                analysis_markdown="### 综合评价\\n该学生近期表现良好，能力稳步上升，**算法设计**上进步明显，建议继续保持。\\n\\n### 注意事项\\n避免在复杂的算法逻辑中忽略边界条件的处理。",
                last_updated=datetime.utcnow(),
                submissions_count=random.randint(5, 20),
                status='completed'
            )
            db.session.add(trend)
            created_count += 1
            
    db.session.commit()
    print(f'✅ 能力趋势数据填充完成: 新增 {created_count} 条')


def recalc_all_stats():
    """回填学生、作业、班级统计字段。"""
    # 1) 学生统计
    students = User.query.filter_by(usertype='学生').all()
    for stu in students:
        qs = Submission.query.filter_by(student_id=stu.student_id)
        cnt = qs.count()
        avg = db.session.query(db.func.avg(Submission.score)).filter_by(student_id=stu.student_id).scalar() or 0.0
        stu.submit_count = cnt
        stu.user_ascore = round(float(avg), 2)  # 0~5

    # 2) 作业统计
    assignments = Assignment.query.all()
    for a in assignments:
        cnt = Submission.query.filter_by(assignment_id=a.id).count()
        avg = db.session.query(db.func.avg(Submission.score)).filter_by(assignment_id=a.id).scalar() or 0.0
        a.count = cnt
        a.average_score = round(float(avg), 2)  # 0~5

    db.session.commit()

    # 3) 班级统计
    Class.sync_from_users()
    print('✅ 统计字段回填完成（学生/作业/班级）')


def seed_database():
    with app.app_context():
        print('🚀 开始初始化测试数据...')
        random.seed(42)  # 固定种子使得生成的样例一致

        get_or_create_admin()
        teacher = get_or_create_teacher()
        classes = get_or_create_classes(teacher)
        students = get_or_create_students(classes)
        assignments = get_or_create_assignments(teacher, [c.name for c in classes])

        seed_submissions(students, assignments)
        seed_knowledge_points(students)
        seed_ability_trends(students)
        
        recalc_all_stats()

        print('🎉 数据播种完成！')


if __name__ == '__main__':
    seed_database()
