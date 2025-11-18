-- 知识点评分系统数据库迁移
-- 创建日期：2025-01-17

-- 1. 创建知识点评分表
CREATE TABLE IF NOT EXISTS knowledge_point_scores (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    student_id VARCHAR(20) NOT NULL,
    knowledge_point VARCHAR(50) NOT NULL COMMENT '知识点名称',
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

-- 2. 创建作业知识点关联表
CREATE TABLE IF NOT EXISTS assignment_knowledge_points (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    assignment_id INTEGER NOT NULL,
    knowledge_point VARCHAR(50) NOT NULL COMMENT '知识点名称',
    weight FLOAT DEFAULT 1.0 COMMENT '权重(该知识点在此题中的重要程度)',
    difficulty FLOAT DEFAULT 1.0 COMMENT '该知识点在此题的难度系数(0.5-2.0)',
    auto_detected BOOLEAN DEFAULT FALSE COMMENT '是否由AI自动检测',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    INDEX idx_assignment (assignment_id),
    INDEX idx_knowledge_point (knowledge_point)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='作业知识点关联表';

-- 验证表创建
SELECT 'knowledge_point_scores table created' AS status;
SELECT 'assignment_knowledge_points table created' AS status;
