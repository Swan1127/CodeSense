# CodeSense 酷森思

![版本](https://img.shields.io/badge/版本-0.3.0-blue.svg)
![许可证](https://img.shields.io/badge/许可证-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-red.svg)

基于深度学习与大语言模型的智能代码评估平台，为高校编程教学提供自动化、个性化的学情分析解决方案。

---

## 系统简介

CodeSense 酷森思面向高校编程课程，支持**学生、教师、管理员**三种角色，通过 CNN 模型 + 启发式规则 + 智谱 GLM-4-Flash 大模型的混合评分机制，对学生提交的代码进行多维度自动评估，并提供个性化学习建议与 AI 编程助手。

---

## 主要功能

### 学生端
- 在线代码编辑与提交（支持 C++/Python/Java）
- 多维度自动评分与 AI 反馈（实时流式输出）
- 编程能力分析与个性化 AI 学情报告
- AI 编程助手（RAG 增强，关联个人学情与历史错误）
- 代码编辑器选中内容快捷提问
- 近期作业展示（含截止日期、Markdown 渲染）

### 教师端
- 班级管理与学情总览
- 班级横向对比分析
- 学生提交记录与能力详情查看
- 作业发布（含截止日期设置、Markdown 描述）
- 个人资料编辑

### 管理员端
- 用户管理（学生/教师/管理员分角色查看详情）
- 教师邀请注册（24小时有效、单次使用 Token）
- 系统仪表盘（用户统计、活跃度、系统日志）
- 数据导出
- 关于系统 / 使用帮助 / 联系我们页面

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | HTML5 / Bootstrap 5 / Chart.js / CodeMirror / marked.js |
| 后端 | Python 3.8+ / Flask 2.0+ / SQLAlchemy / Flask-Login / Flask-WTF |
| 数据库 | MySQL |
| AI 评估 | PyTorch / TextCNN / 智谱 GLM-4-Flash |
| 其他 | SSE 流式响应 / itsdangerous Token / DOMPurify |

---

## 快速启动

### 1. 环境准备

```bash
# 推荐使用 conda 虚拟环境
conda create -n student-eval python=3.8
conda activate student-eval
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp env.example .env
# 编辑 .env，填写数据库连接、API Key 等配置
```

主要配置项：
```ini
SECRET_KEY=your_secret_key
DATABASE_URL=mysql+pymysql://user:password@localhost/student_code_review
ZHIPU_API_KEY=your_zhipu_api_key
```

### 3. 启动应用

```bash
python app.py
```

应用默认运行在 http://localhost:5000

数据库表结构会在首次启动时自动创建（含新增字段自动迁移）。

---

## 项目结构

```
源代码/
├── app.py                  # 应用入口（唯一启动入口）
├── config.py               # 配置文件
├── models.py               # 数据库模型（含自动迁移）
├── forms.py                # WTForms 表单定义
├── requirements.txt        # 依赖列表
├── env.example             # 环境变量模板
├── routes/                 # 路由蓝图
│   ├── api.py              # AI 评估 / 代码建议 API
│   ├── assignments.py      # 作业管理
│   ├── auth.py             # 认证（登录/注册/邀请教师）
│   ├── classes.py          # 班级管理
│   ├── main.py             # 首页 / 仪表盘 / 通用页面
│   └── users.py            # 用户管理
├── templates/              # Jinja2 模板
│   ├── layout.html         # 全局布局（含 Markdown 渲染）
│   ├── classes/            # 班级相关模板
│   └── components/         # 可复用组件
├── utils/                  # 工具模块
│   ├── code_evaluator.py   # CNN + 启发式评分
│   ├── llm_evaluator.py    # 大模型评估
│   ├── guidance_generator.py # 个性化学习建议生成
│   └── code_advisor.py     # AI 编程助手
├── static/                 # 静态资源
├── migrations/             # 历史迁移脚本（参考用）
├── scripts/                # 运维辅助脚本
└── tests/                  # 单元测试
```

---

## 默认账户

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |

教师账户由管理员通过「邀请教师」功能生成一次性注册链接创建。

---

## 权限说明

| 功能 | 学生 | 教师 | 管理员 |
|------|:----:|:----:|:------:|
| 提交代码 | ✅ | — | — |
| 查看个人学情 | ✅ | — | — |
| AI 编程助手 | ✅ | — | — |
| 班级管理 | — | ✅ | ✅ |
| 作业发布 | — | ✅ | ✅ |
| 用户管理 | — | — | ✅ |
| 邀请教师 | — | — | ✅ |
| 系统仪表盘 | — | — | ✅ |

---

## 更新日志

### v0.3.0 (2026-03-19)
- 新增作业截止日期字段（模型、表单、模板全链路）
- 新增教师邀请 Token 单次使用 + 24小时过期机制（`InviteToken` 模型）
- 新增管理员/教师用户详情分角色页面（`staff_details.html`）
- 用户类型分布图新增教师角色统计
- 管理员仪表盘移除教学类按钮（添加作业/作业管理/能力趋势监控）
- 全站 Markdown 渲染覆盖（学生首页近期作业、作业详情等）
- 修复教师视图越权按钮（编辑班级信息、返回用户管理）
- 修复教师「返回个人中心」路由错误
- 修复作业详情页教师视图显示「开始作答」问题
- 使用帮助页新增教师/管理员功能指南
- 清理冗余脚本、测试模板文件

### v0.2.0
- 集成智谱 GLM-4-Flash 流式评估
- 班级对比分析功能
- AI 个性化学情分析
- SSE 实时反馈

### v0.1.0
- 初始版本：用户管理、作业管理、代码提交与 CNN 评估

---

## 许可证

MIT License © 沈阳航空航天大学分布式系统研究室

联系邮箱：daiyupeng5@gmail.com
